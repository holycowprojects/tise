"""Chrome history parsing: the WebKit epoch, transitions, and domain reduction.

The domain tests are privacy tests. If `registrable_domain` ever returns a path or a
query string, invariant 2 in SPEC.md is broken at the point where events are born.
"""

from datetime import UTC, datetime

import pytest
from conftest import CHROME_REDIRECT_CHAIN, write_chrome_history
from tise_research.data.chrome_history import (
    SECONDS_1601_TO_1970,
    datetime_to_webkit,
    is_chain_end,
    is_redirect,
    load_visits,
    registrable_domain,
    transition_core,
    webkit_to_datetime,
)


class TestWebkitEpoch:
    def test_unix_epoch_anchor(self):
        """1970-01-01 is exactly SECONDS_1601_TO_1970 seconds after the WebKit epoch."""
        assert webkit_to_datetime(SECONDS_1601_TO_1970 * 1_000_000) == datetime(
            1970, 1, 1, tzinfo=UTC
        )

    def test_webkit_epoch_itself(self):
        assert webkit_to_datetime(0) == datetime(1601, 1, 1, tzinfo=UTC)

    def test_roundtrip(self):
        original = datetime(2026, 8, 26, 14, 52, 3, tzinfo=UTC)
        assert webkit_to_datetime(datetime_to_webkit(original)) == original

    def test_result_is_timezone_aware(self):
        """Naive datetimes silently compare wrong against window_end. Never emit one."""
        assert webkit_to_datetime(13_000_000_000_000_000).tzinfo is not None

    def test_zero_is_not_treated_as_unix_epoch(self):
        """A Chrome 0 means 1601, not 1970. Getting this backwards shifts every gap."""
        assert webkit_to_datetime(0).year == 1601


class TestTransitionCore:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (0, "link"),
            (1, "typed"),
            (2, "auto_bookmark"),
            (3, "auto_subframe"),
            (7, "form_submit"),
            (8, "reload"),
            # Chrome packs qualifier flags into the high bits; only the low byte is the type.
            (0x1800_0001, "typed"),
            (0xC000_0000, "link"),
        ],
    )
    def test_core_type_is_the_low_byte(self, raw, expected):
        assert transition_core(raw) == expected

    def test_unknown_core_type_does_not_raise(self):
        assert transition_core(200) == "unknown"


class TestIsRedirect:
    """Redirect hops are recorded as visits but nobody chose to go there.

    Counting them inflates visit volume and fills the gap distribution with sub-second
    entries, which buries the within-session mode the session boundary depends on.
    """

    def test_server_redirect_flag(self):
        assert is_redirect(0x8000_0000 | 0) is True

    def test_client_redirect_flag(self):
        assert is_redirect(0x4000_0000 | 0) is True

    def test_both_flags(self):
        assert is_redirect(0xC000_0000 | 1) is True

    @pytest.mark.parametrize("raw", [0, 1, 7, 8, 0x1800_0001, 0x0100_0000, 0x2000_0000])
    def test_ordinary_navigations_are_not_redirects(self, raw):
        """Chain-start/chain-end and forward-back qualifiers must not be misread."""
        assert is_redirect(raw) is False


class TestIsChainEnd:
    """What the `chrome.history` API will hand the extension at all (D78)."""

    def test_chain_end_bit(self):
        assert is_chain_end(0x2000_0000 | 0) is True

    def test_a_redirect_hop_can_be_a_chain_end(self):
        """The last hop of a chain is where the person landed. It is not plumbing."""
        assert is_chain_end(0x2000_0000 | 0x4000_0000 | 0) is True

    @pytest.mark.parametrize("raw", [0, 1, 0x1000_0000, 0x4000_0000, 0x8000_0000])
    def test_chain_starts_and_interior_hops_are_not_chain_ends(self, raw):
        """A chain *start* carries no redirect bit, and the API withholds it anyway."""
        assert is_chain_end(raw) is False


class TestVisitViews:
    """Three views of one chain, and they disagree about where the person went (D78).

    This is the concrete case D65 traced. `chosen` — the pre-D78 default — keeps
    `google.com/url`, which is plumbing, and discards the hotel page, which is the
    navigation. `shipped` keeps what the extension is actually given.
    """

    @pytest.fixture
    def history(self, tmp_path):
        path = tmp_path / "History"
        write_chrome_history(path, CHROME_REDIRECT_CHAIN)
        return path

    def test_shipped_keeps_the_landing_page(self, history):
        domains = [visit.domain for visit in load_visits(history, view="shipped")]
        assert domains == ["zivasuites.com", "example.com"]

    def test_chosen_keeps_the_plumbing_and_drops_the_landing_page(self, history):
        """Documented, not endorsed: this is what every benchmark before D78 measured."""
        domains = [visit.domain for visit in load_visits(history, view="chosen")]
        assert domains == ["google.com", "example.com"]

    def test_raw_keeps_every_hop(self, history):
        assert len(load_visits(history, view="raw")) == 5

    def test_the_two_filtered_views_agree_on_count_and_not_on_content(self, history):
        """The trap D65 named: equal totals are not agreement."""
        shipped = {visit.domain for visit in load_visits(history, view="shipped")}
        chosen = {visit.domain for visit in load_visits(history, view="chosen")}
        assert len(shipped) == len(chosen)
        assert shipped != chosen

    def test_the_default_is_the_view_that_ships(self, history):
        assert load_visits(history) == load_visits(history, view="shipped")


class TestRegistrableDomain:
    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://www.amazon.in/dp/B0XYZ?ref=nav", "amazon.in"),
            ("https://news.ycombinator.com/item?id=1", "ycombinator.com"),
            ("https://mail.google.com/mail/u/0/#inbox", "google.com"),
            ("https://foo.bar.co.uk/x/y", "bar.co.uk"),
            ("https://example.com", "example.com"),
            ("HTTPS://EXAMPLE.COM/Path", "example.com"),
            ("https://example.com:8443/x", "example.com"),
        ],
    )
    def test_reduces_to_registrable_domain(self, url, expected):
        assert registrable_domain(url) == expected

    @pytest.mark.parametrize(
        "url",
        [
            "chrome://settings/privacy",
            "chrome-extension://abcdefg/popup.html",
            "file:///C:/Users/akash/secret.txt",
            "about:blank",
            "http://localhost:3000/admin",
            "http://127.0.0.1:8000/",
            "http://192.168.1.1/",
            "",
            "not a url",
        ],
    )
    def test_non_web_and_local_urls_are_dropped(self, url):
        """These are not browsing behaviour, and file:// paths are private."""
        assert registrable_domain(url) is None

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.amazon.in/dp/B0XYZ?ref=nav&pass=hunter2",
            "https://bank.example.com/transfer?amount=5000&to=12345",
            "https://example.com/reset#token=abc123",
        ],
    )
    def test_never_leaks_path_query_or_fragment(self, url):
        """SPEC.md invariant 2. The reduction happens before an event exists."""
        result = registrable_domain(url)
        assert result is not None
        for forbidden in ("/", "?", "#", "&", "=", ":"):
            assert forbidden not in result

    def test_multi_part_suffix_is_not_over_reduced(self):
        """'co.uk' is a public suffix, so bbc.co.uk is registrable, co.uk is not."""
        assert registrable_domain("https://www.bbc.co.uk/news") == "bbc.co.uk"

    def test_output_is_lowercase(self):
        assert registrable_domain("https://WWW.Example.COM/") == "example.com"
