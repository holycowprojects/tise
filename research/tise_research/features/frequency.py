"""Frequency features — how much, how often, how spread out.

`extension/src/features/frequency.ts` is the mirror.

Every window here is **half-open**: `[window_end - span, window_end)`. An event exactly at
`window_end` is excluded, the same rule `recency.py` uses, because a feature that includes
the instant its label became decidable is reading the boundary from the wrong side.

Calendar days are **UTC**. Local days would be the more behavioural unit — people have
mornings, not 00:00 UTC — but the browser's local timezone and the research machine's are
not the same thing, and a feature that depends on which computer ran it cannot be in a
parity suite. Recorded as a known limitation rather than smoothed over.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta

from tise_research.features.events import Event
from tise_research.features.sessions import sessionise

__all__ = [
    "category_share",
    "days_seen",
    "event_count",
    "session_count",
]

SECONDS_PER_DAY = 86400.0


def _in_window(
    events: Sequence[Event], *, window_end: datetime, days: float
) -> list[Event]:
    """Events in `[window_end - days, window_end)`. The half-open rule, in one place."""
    start = window_end - timedelta(days=days)
    return [event for event in events if start <= event.occurred_at < window_end]


def event_count(
    events: Sequence[Event], category: str, *, window_end: datetime, days: float
) -> int:
    """How many events in this category fell inside the window. Zero is a measurement."""
    return sum(
        1
        for event in _in_window(events, window_end=window_end, days=days)
        if event.category == category
    )


def days_seen(
    events: Sequence[Event], category: str, *, window_end: datetime, days: float
) -> int:
    """Distinct UTC calendar days on which the category appeared.

    Separates a habit from a binge: thirty events on one afternoon and thirty spread over
    a fortnight have the same `event_count` and mean very different things.
    """
    return len(
        {
            event.occurred_at.date()
            for event in _in_window(events, window_end=window_end, days=days)
            if event.category == category
        }
    )


def session_count(
    events: Sequence[Event],
    category: str,
    *,
    window_end: datetime,
    days: float,
    timeout_seconds: float,
) -> int:
    """Distinct sessions inside the window that contained this category.

    Sessions are derived from the windowed events only. Sessionising the whole corpus and
    then filtering would let an event after `window_end` merge two earlier sessions into
    one, and the count would move — which is exactly what the leakage test checks for.
    """
    windowed = _in_window(events, window_end=window_end, days=days)
    return sum(
        1
        for session in sessionise(windowed, timeout_seconds=timeout_seconds)
        if category in session.categories
    )


def category_share(
    events: Sequence[Event], category: str, *, window_end: datetime, days: float
) -> float | None:
    """This category's share of all events in the window.

    None when the window holds nothing at all. Zero would claim "you never do this",
    which is a different statement from "there is nothing to divide by".
    """
    windowed = _in_window(events, window_end=window_end, days=days)
    if not windowed:
        return None
    matching = sum(1 for event in windowed if event.category == category)
    return matching / len(windowed)
