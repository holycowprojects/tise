"""T-C's labels: every category change, within sessions and across their boundaries.

The properties asserted here are the definition. D94 fixed T-C's label in one sentence and
`transitions.py` turns it into code; a wrong turn would produce a plausible-looking label
set that answers a different question, and no score would reveal it.

Four things are checked directly:

* a run is maximal, so `from_category != to_category` always holds
* the clock on a label is when the *answer* arrived, which is what folds are cut on
* the session recorded is the one the question was asked in, not the one that answered it
* `previous_category` looks strictly backwards, so `bounce_back` cannot be reading ahead
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from tise_research.features.events import Event
from tise_research.features.sessions import Session
from tise_research.features.transitions import (
    category_transitions,
    session_boundaries_without_change,
)

START = datetime(2026, 3, 1, 9, tzinfo=UTC)


def event(index: int, category: str, *, minutes: float = 0.0) -> Event:
    return Event(
        event_id=f"e{index}",
        occurred_at=START + timedelta(minutes=minutes if minutes else index),
        domain=f"{category}.example",
        category=category,
        transition="link",
    )


def session(session_id: str, events: list[Event]) -> Session:
    return Session(
        session_id=session_id,
        started_at=events[0].occurred_at,
        ended_at=events[-1].occurred_at,
        events=tuple(events),
    )


def one_session(categories: list[str]) -> list[Session]:
    return [session("s1", [event(i, c) for i, c in enumerate(categories)])]


class TestRuns:
    def test_consecutive_same_category_is_one_run(self):
        # Five events, two changes. A per-event label would have produced four.
        transitions = category_transitions(
            one_session(["news", "news", "video", "video", "news"])
        )
        assert [(t.from_category, t.to_category) for t in transitions] == [
            ("news", "video"),
            ("video", "news"),
        ]

    def test_source_and_target_always_differ(self):
        transitions = category_transitions(
            one_session(["news", "news", "video", "news", "news", "video"])
        )
        assert transitions
        assert all(t.from_category != t.to_category for t in transitions)

    def test_a_single_category_produces_no_labels(self):
        # Not an empty edge case: a person who only ever browses one topic has no
        # "what comes next" to answer, and inventing one would be a fabricated label.
        assert category_transitions(one_session(["news"] * 6)) == []

    def test_run_length_is_recorded(self):
        transitions = category_transitions(one_session(["news", "news", "news", "video"]))
        assert [t.from_run_events for t in transitions] == [3]

    def test_no_sessions_is_empty_rather_than_an_error(self):
        assert category_transitions([]) == []


class TestClock:
    def test_label_is_stamped_when_the_answer_arrived(self):
        # Folds are cut on `at`. Stamping it with the source run's end would place a
        # label before the event that determined it.
        transitions = category_transitions(one_session(["news", "video"]))
        assert transitions[0].at == START + timedelta(minutes=1)
        assert transitions[0].transition_id == "e1"

    def test_labels_come_out_in_chronological_order(self):
        transitions = category_transitions(one_session(["a", "b", "c", "d"]))
        assert [t.at for t in transitions] == sorted(t.at for t in transitions)

    def test_out_of_order_input_does_not_merge_runs(self):
        # A stream handed over unsorted would otherwise collapse two runs that never
        # touched, and the resulting label set looks entirely normal.
        events = [event(0, "news"), event(2, "news"), event(1, "video")]
        shuffled = Session(
            session_id="s1",
            started_at=events[0].occurred_at,
            ended_at=events[1].occurred_at,
            events=tuple(events),
        )
        assert [(t.from_category, t.to_category) for t in category_transitions([shuffled])] == [
            ("news", "video"),
            ("video", "news"),
        ]


class TestSessions:
    def test_within_session_changes_are_flagged(self):
        transitions = category_transitions(one_session(["news", "video"]))
        assert transitions[0].within_session is True

    def test_a_change_across_a_boundary_is_flagged_and_kept(self):
        # The between-session transitions T19 measured are a subset of these, not a
        # separate label set.
        sessions = [
            session("s1", [event(0, "news")]),
            session("s2", [event(1, "video", minutes=600)]),
        ]
        transitions = category_transitions(sessions)
        assert len(transitions) == 1
        assert transitions[0].within_session is False

    def test_the_question_is_clustered_with_the_session_that_asked_it(self):
        # D94's cluster unit is the session. A boundary label belongs to the sitting that
        # produced the question, which is the earlier one.
        sessions = [
            session("s1", [event(0, "news")]),
            session("s2", [event(1, "video", minutes=600)]),
        ]
        assert category_transitions(sessions)[0].session_id == "s1"

    def test_a_boundary_with_no_change_produces_no_label(self):
        # The documented cost of "a label is a change". `session_boundaries_without_change`
        # is what makes it visible in the report.
        sessions = [
            session("s1", [event(0, "news")]),
            session("s2", [event(1, "news", minutes=600)]),
        ]
        assert category_transitions(sessions) == []
        assert session_boundaries_without_change(sessions) == 1

    def test_boundaries_with_a_change_are_not_counted_as_lost(self):
        sessions = [
            session("s1", [event(0, "news")]),
            session("s2", [event(1, "video", minutes=600)]),
        ]
        assert session_boundaries_without_change(sessions) == 0


class TestPreviousCategory:
    def test_the_first_label_has_no_previous(self):
        transitions = category_transitions(one_session(["news", "video", "news"]))
        assert transitions[0].previous_category is None

    def test_previous_is_the_run_before_the_source(self):
        # news -> video -> work: the second label's source is `video` and its previous
        # is `news`, which is what makes A-B-A detectable.
        transitions = category_transitions(one_session(["news", "video", "work"]))
        assert transitions[1].from_category == "video"
        assert transitions[1].previous_category == "news"

    def test_previous_never_looks_forward(self):
        # The leakage question for this field. Every `previous_category` must have
        # occurred strictly before its own label.
        transitions = category_transitions(one_session(["a", "b", "c", "d", "e"]))
        seen: list[str] = []
        for transition in transitions:
            if transition.previous_category is not None:
                assert transition.previous_category in seen
            seen.append(transition.from_category)


class TestDuplicateIds:
    def test_a_repeated_event_id_raises(self):
        # Two labels sharing a `transition_id` would silently double-count one row in the
        # bootstrap. T-A hit this shape on the GESIS panel; here it is made loud.
        duplicated = Session(
            session_id="s1",
            started_at=START,
            ended_at=START + timedelta(minutes=1),
            events=(event(0, "news"), Event(
                event_id="e0",
                occurred_at=START + timedelta(minutes=1),
                domain="video.example",
                category="video",
                transition="link",
            )),
        )
        with pytest.raises(ValueError, match="duplicate event id"):
            category_transitions([duplicated])

    def test_ids_are_unique_across_the_label_set(self):
        transitions = category_transitions(one_session(["a", "b", "a", "b", "a"]))
        assert len({t.transition_id for t in transitions}) == len(transitions)
