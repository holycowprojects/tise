"""Group events into sessions.

A session is a run of events with no gap **strictly greater** than the timeout. That
strictness is part of the contract, not an implementation detail: a `>` versus `>=`
disagreement between TypeScript and Python shifts every session-derived feature by one
event, and it is invisible until the parity suite catches it.

The timeout is a declared hyperparameter (D17). T1 looked for an empirical trough in the
gap distribution and did not find one, so there is no "natural" value to discover. Every
function here therefore takes it explicitly, keyword-only, with **no default** — a silent
30 minutes is exactly how an undefended constant gets into a benchmark.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from tise_research.features.events import Event

__all__ = ["Session", "session_boundaries", "sessionise"]


def session_boundaries(
    times: Sequence[datetime], *, timeout_seconds: float
) -> list[list[datetime]]:
    """Group timestamps into sessions. The primitive the rest of the pipeline builds on.

    Input is sorted first: a browser's visit table is ordered in practice but not by
    contract, and one out-of-order row produces a negative gap that silently merges two
    sessions.
    """
    ordered = sorted(times)
    if not ordered:
        return []

    sessions: list[list[datetime]] = [[ordered[0]]]
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if (current - previous).total_seconds() > timeout_seconds:
            sessions.append([current])
        else:
            sessions[-1].append(current)
    return sessions


@dataclass(frozen=True, slots=True)
class Session:
    """A run of events with no long gap.

    `session_id` is derived from the start instant rather than from a running index. The
    extension assigns ids as browsing happens and can never renumber earlier sessions, so
    an index-based id would disagree with the research tier the moment history is
    imported out of order.
    """

    session_id: str
    started_at: datetime
    ended_at: datetime
    events: tuple[Event, ...]

    @property
    def duration_seconds(self) -> float:
        """Zero for a single-event session — a real measurement, not an absence."""
        return (self.ended_at - self.started_at).total_seconds()

    @property
    def categories(self) -> frozenset[str]:
        return frozenset(event.category for event in self.events)


def sessionise(events: Sequence[Event], *, timeout_seconds: float) -> list[Session]:
    """Group events into sessions, in chronological order."""
    ordered = sorted(events, key=lambda event: (event.occurred_at, event.event_id))
    if not ordered:
        return []

    groups = session_boundaries(
        [event.occurred_at for event in ordered], timeout_seconds=timeout_seconds
    )

    sessions: list[Session] = []
    position = 0
    for group in groups:
        members = tuple(ordered[position : position + len(group)])
        position += len(group)
        sessions.append(
            Session(
                session_id=members[0].occurred_at.isoformat(),
                started_at=members[0].occurred_at,
                ended_at=members[-1].occurred_at,
                events=members,
            )
        )
    return sessions
