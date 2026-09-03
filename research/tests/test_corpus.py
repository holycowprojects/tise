"""The corpus loader: which dataset a benchmark is actually computed on.

`load_events` is the single door every published number comes through. If it drops the
`view` it was handed, the benchmark silently describes a different corpus than the one
requested — and nothing else in the suite would notice, because every downstream test
builds its own events in memory.

That is not hypothetical. Deliberately removing the pass-through failed **zero** tests
before this file existed (D78), which is the fourth time counting break failures has
found a hole rather than a bug.
"""

from __future__ import annotations

import sqlite3

import pytest
from conftest import (
    CHROME_REDIRECT_CHAIN,
    FIREFOX_REDIRECT_CHAIN,
    write_chrome_history,
    write_firefox_places,
)
from tise_research.data.corpus import load_events, load_labels


@pytest.fixture
def chrome(tmp_path):
    path = tmp_path / "History"
    write_chrome_history(path, CHROME_REDIRECT_CHAIN)
    return path


@pytest.fixture
def firefox(tmp_path):
    path = tmp_path / "places-firefox.sqlite"
    write_firefox_places(path, FIREFOX_REDIRECT_CHAIN)
    return path


class TestViewReachesTheReader:
    """The pass-through, asserted rather than assumed."""

    def test_chrome_views_produce_different_events(self, chrome):
        shipped = [event.domain for event in load_events(chrome, view="shipped")]
        chosen = [event.domain for event in load_events(chrome, view="chosen")]
        assert shipped == ["zivasuites.com", "example.com"]
        assert chosen == ["google.com", "example.com"]

    def test_firefox_views_produce_different_events(self, firefox):
        shipped = [event.domain for event in load_events(firefox, view="shipped")]
        chosen = [event.domain for event in load_events(firefox, view="chosen")]
        assert shipped == ["zivasuites.com", "example.com"]
        assert chosen == ["google.com", "example.com"]

    def test_raw_reaches_the_reader_too(self, chrome):
        assert len(load_events(chrome, view="raw")) == len(CHROME_REDIRECT_CHAIN)

    def test_the_default_is_the_shipped_view(self, chrome):
        assert load_events(chrome) == load_events(chrome, view="shipped")

    def test_labels_are_built_on_the_requested_view(self, firefox):
        """`load_labels` calls `load_events`; a view dropped there is dropped for labels.

        The subjects are spelled out rather than merely compared, because the interesting
        part is *what* changes: the pre-D78 view invents a `search` label out of a
        redirect chain's plumbing, and loses the hotel page the person actually read.
        """
        shipped = load_labels(firefox, timeout_seconds=1800, view="shipped")
        chosen = load_labels(firefox, timeout_seconds=1800, view="chosen")
        assert sorted(label.subject for label in shipped) == ["unknown"]
        assert sorted(label.subject for label in chosen) == ["search", "unknown"]


class TestEventsAreWellFormed:
    def test_event_ids_are_unique_and_stable(self, chrome):
        events = load_events(chrome)
        assert len({event.event_id for event in events}) == len(events)
        assert [e.event_id for e in events] == [e.event_id for e in load_events(chrome)]

    def test_no_url_survives_into_an_event(self, chrome):
        """Invariant 2. A path or query string here means it can be persisted."""
        for event in load_events(chrome, view="raw"):
            assert "/" not in event.domain
            assert "?" not in event.domain

    def test_imported_events_are_marked_as_imports(self, chrome):
        assert {event.source for event in load_events(chrome)} == {"import"}

    def test_chromium_surfaces_the_duration_the_api_cannot(self, tmp_path):
        """The `full`/`history` split, at the point where it is created.

        The file has `visit_duration` and the `chrome.history` API does not (D35), so a
        corpus loaded from a file carries a column no shipped feature may ever read. It is
        asserted here rather than assumed, because the danger is a reader believing an
        event from a file and an event from the extension are the same kind of object.
        """
        path = tmp_path / "History"
        write_chrome_history(path, CHROME_REDIRECT_CHAIN)
        connection = sqlite3.connect(path)
        # 4000000, not 4_000_000: the underscore is Python's digit separator and this is a
        # SQL string. SQLite only accepts separators from 3.46, so the bundled library on
        # Windows parsed it and the one on Ubuntu did not — found by CI on its first run.
        connection.execute("UPDATE visits SET visit_duration = 4000000 WHERE id = 5")
        connection.commit()
        connection.close()

        durations = {event.domain: event.dwell_seconds for event in load_events(path)}
        assert durations["example.com"] == 4.0
        assert durations["zivasuites.com"] is None  # 0 means "not recorded", not zero dwell

    def test_firefox_can_never_supply_a_duration(self, firefox):
        """Firefox has no duration column at all, so it is honest `history` class."""
        assert all(event.dwell_seconds is None for event in load_events(firefox, view="raw"))
