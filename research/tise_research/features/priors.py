"""The person's own history of returning — the feature that has to be built carefully.

`extension/src/features/priors.ts` is the mirror.

`prior_return_rate` is how often this category has *already* been returned to within the
horizon. It is the strongest feature in the set, because the bar it has to help clear is
`category_base_rate` (D28) and this is that baseline expressed as a number the model can
weigh against everything else.

**It is also the one that leaks if you write it the obvious way.** Deciding whether a past
session was returned to means looking at what happened in the 24 hours after it — and for
a recent session, some of those 24 hours are still in the future at `window_end`. Counting
it either way is wrong: as a miss it says "no return" when the return may be an hour away,
and as a hit it is reading the future outright.

So a past session counts only when **its entire horizon has already elapsed**:

    session_end + horizon <= window_end

Sessions whose outcome is not yet knowable are excluded from both numerator and
denominator. `prior_session_count` reports how many were counted, so a rate computed from
two sessions is visibly different from one computed from forty.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from datetime import datetime, timedelta

from tise_research.features.events import Event
from tise_research.features.sessions import sessionise

__all__ = ["prior_return_rate", "prior_session_count", "resolved_prior_sessions"]


def resolved_prior_sessions(
    events: Sequence[Event],
    category: str,
    *,
    window_end: datetime,
    timeout_seconds: float,
    horizon_hours: float,
) -> list[tuple[datetime, bool]]:
    """(session_end, returned) for every prior session whose horizon has fully elapsed.

    Both the sessions and the returns are derived from events strictly before
    `window_end`, so nothing here can see past the boundary even indirectly.
    """
    horizon = timedelta(hours=horizon_hours)
    past = [event for event in events if event.occurred_at < window_end]
    if not past:
        return []

    times = sorted(
        event.occurred_at for event in past if event.category == category
    )

    resolved: list[tuple[datetime, bool]] = []
    for session in sessionise(past, timeout_seconds=timeout_seconds):
        if category not in session.categories:
            continue
        if session.ended_at + horizon > window_end:
            continue  # outcome not yet knowable — excluded from both sides of the ratio

        # Strictly after the session closed, at or before the horizon.
        index = bisect_right(times, session.ended_at)
        returned = index < len(times) and times[index] <= session.ended_at + horizon
        resolved.append((session.ended_at, returned))

    return resolved


def prior_session_count(
    events: Sequence[Event],
    category: str,
    *,
    window_end: datetime,
    timeout_seconds: float,
    horizon_hours: float,
) -> int:
    """How many prior sessions the rate below was computed from."""
    return len(
        resolved_prior_sessions(
            events,
            category,
            window_end=window_end,
            timeout_seconds=timeout_seconds,
            horizon_hours=horizon_hours,
        )
    )


def prior_return_rate(
    events: Sequence[Event],
    category: str,
    *,
    window_end: datetime,
    timeout_seconds: float,
    horizon_hours: float,
) -> float | None:
    """Share of resolved prior sessions that were returned to inside the horizon.

    None when nothing has resolved yet. A default of 0.5 would be a prior invented here
    and then fitted downstream as though it had been measured.
    """
    resolved = resolved_prior_sessions(
        events,
        category,
        window_end=window_end,
        timeout_seconds=timeout_seconds,
        horizon_hours=horizon_hours,
    )
    if not resolved:
        return None
    return sum(1 for _, returned in resolved if returned) / len(resolved)
