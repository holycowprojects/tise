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
from tise_research.data.firefox_history import (
    is_download,
    is_redirect,
    is_subframe,
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
