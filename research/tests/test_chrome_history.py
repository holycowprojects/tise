"""Chrome history parsing: the WebKit epoch, transitions, and domain reduction.

The domain tests are privacy tests. If `registrable_domain` ever returns a path or a
query string, invariant 2 in SPEC.md is broken at the point where events are born.
"""

from datetime import UTC, datetime

import pytest
from tise_research.data.chrome_history import (
    SECONDS_1601_TO_1970,
    datetime_to_webkit,
    is_redirect,
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
