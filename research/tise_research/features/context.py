"""Where the label sits: the session that produced it, and when.

`extension/src/features/context.ts` is the mirror.

**These are the features that leak most easily**, and the reason is worth stating. A
label's `window_end` is the end of its own session, so the session is fully observed at
that instant and including its events is correct. But re-deriving that session from the
whole corpus is not: an event twenty minutes *after* `window_end` is inside the timeout
and would merge into the same session, changing its event count retroactively.

So every function here sessionises `events where occurred_at <= window_end` and takes the
last session. A later event cannot join a session it is not in the input for.

Hour and day are **UTC**, for the same reason as `frequency.py`: the browser's local
timezone and the research machine's are different, and a feature that depends on which
computer ran it cannot be in a parity suite. It costs real signal — 9pm behaviour is not
9pm UTC behaviour — and that cost is recorded rather than hidden.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from tise_research.features.events import Event
from tise_research.features.sessions import Session, sessionise

__all__ = [
    "category_events_in_session",
    "day_of_week",
    "hour_of_day",
    "session_at",
    "session_category_count",
    "session_event_count",
]


def session_at(
    events: Sequence[Event], *, window_end: datetime, timeout_seconds: float
) -> Session | None:
    """The session that closes at `window_end`, derived only from events up to it."""
    upto = [event for event in events if event.occurred_at <= window_end]
    sessions = sessionise(upto, timeout_seconds=timeout_seconds)
    return sessions[-1] if sessions else None


def session_event_count(
    events: Sequence[Event], *, window_end: datetime, timeout_seconds: float
) -> int:
    session = session_at(events, window_end=window_end, timeout_seconds=timeout_seconds)
    return len(session.events) if session else 0


def session_category_count(
    events: Sequence[Event], *, window_end: datetime, timeout_seconds: float
) -> int:
    """How many distinct categories this session touched. A proxy for browsing breadth."""
    session = session_at(events, window_end=window_end, timeout_seconds=timeout_seconds)
    return len(session.categories) if session else 0


def category_events_in_session(
    events: Sequence[Event], category: str, *, window_end: datetime, timeout_seconds: float
) -> int:
    session = session_at(events, window_end=window_end, timeout_seconds=timeout_seconds)
    if session is None:
        return 0
    return sum(1 for event in session.events if event.category == category)


def hour_of_day(window_end: datetime) -> int:
    """UTC hour, 0–23. See the module docstring for what UTC costs here."""
    return window_end.hour


def day_of_week(window_end: datetime) -> int:
    """UTC weekday, Monday=0 through Sunday=6, matching `datetime.weekday()`.

    JavaScript's `getUTCDay()` is Sunday=0, so the TypeScript mirror converts. That
    off-by-one is exactly the kind of silent disagreement the parity fixture exists for.
    """
    return window_end.weekday()
