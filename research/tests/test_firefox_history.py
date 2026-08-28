"""Firefox history parsing.

Firefox differs from Chromium in every way that matters here:

* timestamps are microseconds since the **Unix** epoch, not the WebKit 1601 epoch
* visits live in `moz_historyvisits` joined to `moz_places`, not `visits`/`urls`
* redirects and subframes are distinct `visit_type` values rather than bit flags
* there is **no duration column at all**, so Firefox is `history`-class throughout

Values here were verified against a real `places.sqlite`, not recalled.
"""

from datetime import UTC, datetime

import pytest
from conftest import FIREFOX_REDIRECT_CHAIN, write_firefox_places
from tise_research.data.firefox_history import (
    is_download,
    is_redirect,
    is_subframe,
    load_visits,
    unix_micros_to_datetime,
    visit_type_name,
)


class TestUnixEpoch:
    def test_zero_is_the_unix_epoch_not_1601(self):
        """The whole point of a separate parser. Reusing the Chrome conversion here
        would place every Firefox visit in the wrong millennium."""
        assert unix_micros_to_datetime(0) == datetime(1970, 1, 1, tzinfo=UTC)

    def test_known_value(self):
        # Taken from the real database probe: max(visit_date) on 2026-08-25.
        assert unix_micros_to_datetime(1_787_679_276_364_000) == datetime(
            2026, 8, 25, 17, 34, 36, 364_000, tzinfo=UTC
        )

    def test_result_is_timezone_aware(self):
        assert unix_micros_to_datetime(1_787_679_276_364_000).tzinfo is not None


class TestVisitTypes:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (1, "link"),
            (2, "typed"),
            (3, "auto_bookmark"),
            (4, "auto_subframe"),
            (5, "redirect_permanent"),
            (6, "redirect_temporary"),
            (7, "download"),
            (8, "manual_subframe"),
            (9, "reload"),
        ],
    )
    def test_names_match_firefox_constants(self, raw, expected):
        assert visit_type_name(raw) == expected

    def test_unknown_type_does_not_raise(self):
        assert visit_type_name(99) == "unknown"

    @pytest.mark.parametrize("raw", [5, 6])
    def test_redirects(self, raw):
        assert is_redirect(raw) is True

    @pytest.mark.parametrize("raw", [1, 2, 3, 4, 7, 8, 9])
    def test_non_redirects(self, raw):
        assert is_redirect(raw) is False

    @pytest.mark.parametrize("raw", [4, 8])
    def test_subframes(self, raw):
        assert is_subframe(raw) is True

    @pytest.mark.parametrize("raw", [1, 2, 3, 5, 6, 7, 9])
    def test_non_subframes(self, raw):
        assert is_subframe(raw) is False

    def test_download_is_not_a_page_view(self):
        """Chromium has no equivalent transition, so excluding it keeps the two
        browsers' definitions of 'a visit' comparable."""
        assert is_download(7) is True
        assert is_download(1) is False


class TestTransitionNamesAlignWithChromium:
    """Cross-browser comparison is only meaningful if the vocabularies match."""

    def test_link_and_typed_use_the_same_names_as_the_chromium_parser(self):
        from tise_research.data.chrome_history import transition_core

        assert visit_type_name(1) == transition_core(0) == "link"
        assert visit_type_name(2) == transition_core(1) == "typed"


class TestVisitViews:
    """Firefox's flag is on the other end of the chain, and the inversion is the same.

    Dropping `redirect_*` types keeps `google.com/url` — plumbing — and discards the page
    the person landed on. Tise never runs on Firefox, so `shipped` here is not what any
    product saw; it is the same *definition of a visit*, which is what makes a fold count
    compared across browsers mean anything (D78).
    """

    @pytest.fixture
    def places(self, tmp_path):
        path = tmp_path / "places.sqlite"
        write_firefox_places(path, FIREFOX_REDIRECT_CHAIN)
        return path

    def test_shipped_keeps_the_landing_page(self, places):
        domains = [visit.domain for visit in load_visits(places, view="shipped")]
        assert domains == ["zivasuites.com", "example.com"]

    def test_chosen_keeps_the_plumbing_and_drops_the_landing_page(self, places):
        domains = [visit.domain for visit in load_visits(places, view="chosen")]
        assert domains == ["google.com", "example.com"]

    def test_raw_keeps_every_hop(self, places):
        assert len(load_visits(places, view="raw")) == 4

    def test_the_default_is_the_view_that_ships(self, places):
        assert load_visits(places) == load_visits(places, view="shipped")

    def test_a_visit_redirected_to_but_never_away_from_is_a_landing_page(self, places):
        """Visit 3 carries `redirect_permanent` and is still where the person ended up."""
        kept = load_visits(places, view="shipped")
        assert [visit.transition for visit in kept] == ["redirect_permanent", "typed"]
