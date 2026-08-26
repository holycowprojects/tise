"""Sessionisation.

A session is a run of events with no gap longer than the timeout. The timeout is a
**declared hyperparameter** (D17), not a discovered constant — T1 found no empirical
trough to derive one from — so every function here takes it explicitly and nothing
defaults to 30 minutes behind your back.

The boundary is **strictly greater than**. That single choice has to be identical in
TypeScript or every session-derived feature shifts by one event, so it is asserted here
rather than left as a comment.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from tise_research.features.events import Event
from tise_research.features.sessions import Session, session_boundaries, sessionise


def t(day: int, hour: int = 0, minute: int = 0, second: int = 0) -> datetime:
    return datetime(2026, 6, day, hour, minute, second, tzinfo=UTC)


def event(when: datetime, category: str = "video", domain: str = "youtube.com") -> Event:
    return Event(
        event_id=f"e-{when.isoformat()}-{domain}",
        occurred_at=when,
        domain=domain,
        category=category,
        transition="link",
        dwell_seconds=None,
    )


class TestSessionBoundaries:
    def test_splits_on_gap_exceeding_timeout(self):
        times = [t(1, 10, 0), t(1, 10, 20), t(1, 12, 0)]
        assert [len(s) for s in session_boundaries(times, timeout_seconds=1800)] == [2, 1]

    def test_gap_exactly_at_timeout_stays_in_session(self):
        times = [t(1, 10, 0), t(1, 10, 30)]
        assert len(session_boundaries(times, timeout_seconds=1800)) == 1

    def test_one_second_over_timeout_splits(self):
        times = [t(1, 10, 0), t(1, 10, 30, 1)]
        assert len(session_boundaries(times, timeout_seconds=1800)) == 2

    def test_unsorted_input_is_sorted_first(self):
        times = [t(1, 12, 0), t(1, 10, 0), t(1, 10, 20)]
        assert [len(s) for s in session_boundaries(times, timeout_seconds=1800)] == [2, 1]

    def test_empty_input(self):
        assert session_boundaries([], timeout_seconds=1800) == []


class TestSessionise:
    def test_groups_events_into_sessions(self):
        events = [event(t(1, 10, 0)), event(t(1, 10, 10)), event(t(1, 14, 0))]
        sessions = sessionise(events, timeout_seconds=1800)
        assert len(sessions) == 2
        assert [len(s.events) for s in sessions] == [2, 1]

    def test_session_id_is_derived_from_the_start_instant(self):
        """Not from an index. The extension assigns ids live and cannot renumber
        earlier sessions, so an index-based id would never match the research tier."""
        events = [event(t(1, 10, 0)), event(t(1, 14, 0))]
        first, second = sessionise(events, timeout_seconds=1800)
        assert first.session_id == t(1, 10, 0).isoformat()
        assert second.session_id == t(1, 14, 0).isoformat()

    def test_session_ids_are_unique(self):
        events = [event(t(1, h)) for h in range(0, 12, 2)]
        sessions = sessionise(events, timeout_seconds=1800)
        assert len({s.session_id for s in sessions}) == len(sessions)

    def test_started_and_ended_bound_the_events(self):
        events = [event(t(1, 10, 0)), event(t(1, 10, 10)), event(t(1, 10, 20))]
        (session,) = sessionise(events, timeout_seconds=1800)
        assert session.started_at == t(1, 10, 0)
        assert session.ended_at == t(1, 10, 20)

    def test_duration_of_a_single_event_session_is_zero_not_none(self):
        """A one-event session lasted no measurable time. That is a real zero."""
        (session,) = sessionise([event(t(1, 10))], timeout_seconds=1800)
        assert session.duration_seconds == 0.0

    def test_categories_collapses_duplicates(self):
        events = [
            event(t(1, 10, 0), "video"),
            event(t(1, 10, 5), "video"),
            event(t(1, 10, 9), "search", "google.com"),
        ]
        (session,) = sessionise(events, timeout_seconds=1800)
        assert session.categories == frozenset({"video", "search"})

    def test_every_event_lands_in_exactly_one_session(self):
        events = [event(t(1, h, m)) for h in range(0, 10, 3) for m in (0, 5)]
        sessions = sessionise(events, timeout_seconds=1800)
        placed = [e.event_id for s in sessions for e in s.events]
        assert sorted(placed) == sorted(e.event_id for e in events)

    def test_returns_session_objects(self):
        (session,) = sessionise([event(t(1, 10))], timeout_seconds=1800)
        assert isinstance(session, Session)

    def test_empty_input(self):
        assert sessionise([], timeout_seconds=1800) == []


class TestTimeoutIsExplicit:
    def test_timeout_is_keyword_only_and_required(self):
        """No default. A silent 30 minutes is how an undefended constant gets in."""
        with pytest.raises(TypeError):
            sessionise([event(t(1, 10))])  # type: ignore[call-arg]

    @pytest.mark.parametrize("timeout", [900, 1800, 3600])
    def test_longer_timeouts_never_produce_more_sessions(self, timeout):
        events = [
            event(t(1, 0, 0) + timedelta(minutes=m)) for m in range(0, 240, 17)
        ]
        counts = [
            len(sessionise(events, timeout_seconds=s)) for s in (600, timeout, 7200)
        ]
        assert counts == sorted(counts, reverse=True)
