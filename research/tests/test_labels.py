"""`return_24h` label generation, and the leakage test that guards it.

One label per (category, session), per D16. The window closes at the **end of the
session**; the label is positive if that category recurs strictly after the close and
within the horizon.

The leakage test is the important one in this file. Every label carries an explicit
`window_end`, and nothing at or after that instant may change any label already emitted.
If injecting a future event changes an earlier label, the pipeline is reading the future
and every backtest number is worthless.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from tise_research.features.events import Event
from tise_research.features.labels import Label, return_24h_labels


def t(day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(2026, 6, day, hour, minute, tzinfo=UTC)


def event(when: datetime, category: str = "video") -> Event:
    return Event(
        event_id=f"e-{when.isoformat()}-{category}",
        occurred_at=when,
        domain=f"{category}.example",
        category=category,
        transition="link",
        dwell_seconds=None,
    )


def labels_for(events, *, timeout_seconds: float = 1800) -> list[Label]:
    return return_24h_labels(events, timeout_seconds=timeout_seconds)


class TestLabelGeneration:
    def test_one_label_per_category_per_session(self):
        events = [event(t(1, 10, 0)), event(t(1, 10, 5)), event(t(1, 14, 0))]
        assert len(labels_for(events)) == 2

    def test_two_categories_in_one_session_yield_two_labels(self):
        events = [event(t(1, 10, 0), "video"), event(t(1, 10, 5), "news")]
        labels = labels_for(events)
        assert len(labels) == 2
        assert {label.subject for label in labels} == {"video", "news"}

    def test_window_end_is_the_session_end(self):
        events = [event(t(1, 10, 0)), event(t(1, 10, 20))]
        (label,) = labels_for(events)
        assert label.window_end == t(1, 10, 20)

    def test_recurrence_within_the_horizon_is_positive(self):
        events = [event(t(1, 10, 0)), event(t(1, 14, 0))]
        first, second = labels_for(events)
        assert first.outcome is True
        assert second.outcome is False

    def test_recurrence_after_the_horizon_is_negative(self):
        events = [event(t(1, 10, 0)), event(t(3, 10, 0))]
        assert [label.outcome for label in labels_for(events)] == [False, False]

    def test_a_different_category_does_not_satisfy_the_label(self):
        events = [event(t(1, 10, 0), "video"), event(t(1, 14, 0), "news")]
        by_subject = {label.subject: label for label in labels_for(events)}
        assert by_subject["video"].outcome is False

    def test_labels_are_returned_in_window_end_order(self):
        events = [event(t(1, h)) for h in (10, 14, 18)]
        labels = labels_for(events)
        assert [label.window_end for label in labels] == sorted(
            label.window_end for label in labels
        )

    def test_every_label_records_its_horizon_and_target(self):
        (label,) = labels_for([event(t(1, 10))])
        assert label.target == "return_24h"
        assert label.horizon_hours == 24.0

    def test_empty_input(self):
        assert labels_for([]) == []


class TestLeakage:
    """The structural defence. If these fail, no benchmark from this repo means anything."""

    def test_an_event_after_window_end_does_not_change_an_earlier_label(self):
        base = [event(t(1, 10, 0)), event(t(1, 14, 0))]
        before = labels_for(base)

        # A visit three days later cannot retroactively alter what was already decided.
        after = labels_for([*base, event(t(4, 9, 0))])

        assert after[: len(before)] == before

    def test_appending_history_never_rewrites_existing_labels(self):
        events = [event(t(day, 10)) for day in range(1, 6)]
        full = labels_for(events)
        for cut in range(1, len(events)):
            partial = labels_for(events[:cut])
            # Labels whose horizon has fully elapsed within the truncated data must
            # match the full run exactly.
            settled = [
                label
                for label in partial
                if label.window_end + _horizon(label) <= events[cut - 1].occurred_at
            ]
            for label in settled:
                assert label in full

    def test_no_label_uses_an_event_at_exactly_window_end(self):
        """The boundary is strictly after. An event landing exactly on the close is
        part of the session that produced the label, not evidence of a return."""
        events = [event(t(1, 10, 0)), event(t(1, 10, 20))]
        (label,) = labels_for(events)
        assert label.window_end == t(1, 10, 20)
        assert label.outcome is False


class TestTimeoutSensitivity:
    def test_shorter_timeout_yields_at_least_as_many_labels(self):
        events = [
            event(t(1, 0, 0) + timedelta(minutes=m)) for m in range(0, 300, 20)
        ]
        counts = [len(labels_for(events, timeout_seconds=s)) for s in (600, 1800, 7200)]
        assert counts == sorted(counts, reverse=True)

    def test_timeout_is_required(self):
        with pytest.raises(TypeError):
            return_24h_labels([event(t(1, 10))])  # type: ignore[call-arg]


def _horizon(label: Label):
    from datetime import timedelta

    return timedelta(hours=label.horizon_hours)
