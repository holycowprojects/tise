"""The first feature implemented in two languages.

`extension/src/features/recency.ts` is the mirror, and
`research/fixtures/parity_expected.json` is the oracle both are measured against. The
tests here are the Python half: the maths, the boundaries, and the leakage guard.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from tise_research.features.events import Event
from tise_research.features.recency import hours_since_last_seen
from tise_research.features.vector import FEATURE_SET

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "parity_expected.json"


def at(hour: int, minute: int = 0, day: int = 1) -> datetime:
    return datetime(2026, 6, day, hour, minute, tzinfo=UTC)


def event(category: str, when: datetime, event_id: str = "e") -> Event:
    return Event(
        event_id=event_id,
        occurred_at=when,
        domain="example.com",
        category=category,
        transition="link",
        dwell_seconds=None,
        source="import",
    )


def test_measures_from_the_most_recent_matching_event() -> None:
    events = [event("video", at(9)), event("video", at(10)), event("dev", at(11))]
    assert hours_since_last_seen(events, "video", window_end=at(12)) == 2.0


def test_is_none_when_the_category_was_never_seen() -> None:
    events = [event("video", at(9))]
    assert hours_since_last_seen(events, "dev", window_end=at(12)) is None


def test_is_none_rather_than_a_sentinel() -> None:
    """A stand-in like 9999 is a number the model would fit a coefficient to."""
    assert hours_since_last_seen([], "video", window_end=at(12)) is None


def test_an_event_exactly_at_window_end_is_excluded() -> None:
    """Strictly before. This is the case that produces a null in the parity fixture."""
    events = [event("video", at(12))]
    assert hours_since_last_seen(events, "video", window_end=at(12)) is None


def test_an_event_a_microsecond_before_window_end_is_included() -> None:
    window_end = at(12)
    events = [event("video", window_end - timedelta(microseconds=1))]
    value = hours_since_last_seen(events, "video", window_end=window_end)
    assert value is not None
    assert value == pytest.approx(1e-6 / 3600, rel=1e-12)


def test_future_events_cannot_move_a_value() -> None:
    """The leakage guard, asserted the way the suite asserts it everywhere else."""
    events = [event("video", at(9)), event("video", at(10))]
    before = hours_since_last_seen(events, "video", window_end=at(11))

    with_future = [*events, event("video", at(23), event_id="future")]
    assert hours_since_last_seen(with_future, "video", window_end=at(11)) == before


def test_order_of_input_does_not_matter() -> None:
    forward = [event("video", at(9), "a"), event("video", at(10), "b")]
    assert hours_since_last_seen(forward, "video", window_end=at(12)) == hours_since_last_seen(
        list(reversed(forward)), "video", window_end=at(12)
    )


def test_a_naive_window_end_is_refused() -> None:
    with pytest.raises(ValueError, match="naive window_end"):
        hours_since_last_seen([], "video", window_end=datetime(2026, 6, 1, 12))


@pytest.mark.parity
class TestAgainstTheFixture:
    """The oracle side. TypeScript asserts against exactly these rows."""

    def setup_method(self) -> None:
        self.expected = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_the_fixture_declares_the_feature_set(self) -> None:
        assert self.expected["featureSet"] == FEATURE_SET

    def test_there_is_one_feature_row_per_label(self) -> None:
        assert len(self.expected["features"]) == len(self.expected["labels"])
        for feature, label in zip(
            self.expected["features"], self.expected["labels"], strict=True
        ):
            assert feature["subject"] == label["subject"]
            assert feature["windowEnd"] == label["windowEnd"]

    def test_the_fixture_contains_a_never_seen_case(self) -> None:
        """Without one, TypeScript could substitute a sentinel and still pass."""
        nulls = [
            row
            for row in self.expected["features"]
            if row["values"]["hoursSinceLastSeen"] is None
        ]
        assert nulls, "a fixture with no null cannot catch a sentinel"

    def test_the_fixture_contains_a_non_terminating_value(self) -> None:
        """A value with a long decimal expansion is where a float bug shows."""
        long_values = [
            row
            for row in self.expected["features"]
            if row["values"]["hoursSinceLastSeen"] is not None
            and len(str(row["values"]["hoursSinceLastSeen"])) > 8
        ]
        assert long_values, "a fixture of round numbers proves very little"
