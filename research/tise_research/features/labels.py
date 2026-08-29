"""Generate `return_24h` labels.

One label per (category, session), per D16. The window closes at the **end of the
session**; the label is positive if that category is seen again strictly after the close
and within the horizon.

Two properties matter more than the arithmetic:

* **Every label carries an explicit `window_end`.** Nothing downstream has to infer when
  a label became knowable.
* **A label is decided only by events strictly after its `window_end`.** Activity inside
  the session that produced it can never make it positive. That is the leakage guard in
  its simplest form, and `research/tests/test_labels.py` asserts it directly by appending
  future events and checking that no earlier label moves.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from tise_research.features.events import Event
from tise_research.features.sessions import sessionise

__all__ = ["DEFAULT_HORIZON_HOURS", "Label", "return_24h_labels", "session_label_pairs"]

DEFAULT_HORIZON_HOURS = 24.0

TARGET = "return_24h"


@dataclass(frozen=True, slots=True)
class Label:
    """One training example.

    `window_end` is the instant the label became decidable. A feature vector for this
    label may look at everything strictly before it and nothing at or after it.
    """

    target: str
    subject: str
    window_end: datetime
    outcome: bool
    horizon_hours: float
    session_id: str
    #: Unique per example, where the emitter can supply one.
    #:
    #: Consumers need to map a label back to its feature row, and every analysis in this
    #: project keyed that on `(subject, window_end)` — which is unique on Akash's browsing
    #: and **not** unique in general. The GESIS panel (D99) records visits to one second, so
    #: one person visiting two pages of the same category within a second produces two
    #: labels sharing that key: 0.02% of rows, never more than two, and enough to score one
    #: feature row against two different labels with nothing reporting it.
    #:
    #: Empty for targets whose emitter predates this and whose subjects are unique by
    #: construction (`return_24h` has one label per category *per session*).
    label_id: str = ""


def session_label_pairs(
    events: Sequence[Event], *, timeout_seconds: float
) -> list[tuple[datetime, str, str]]:
    """(window_end, category, session_id) for every (category, session) combination.

    Separated from outcome resolution so the two can be tested apart, and so a future
    target with the same subjects but a different horizon reuses this unchanged.
    """
    pairs: list[tuple[datetime, str, str]] = []
    for session in sessionise(events, timeout_seconds=timeout_seconds):
        for category in sorted(session.categories):
            pairs.append((session.ended_at, category, session.session_id))
    return pairs


def return_24h_labels(
    events: Sequence[Event],
    *,
    timeout_seconds: float,
    horizon_hours: float = DEFAULT_HORIZON_HOURS,
) -> list[Label]:
    """Emit one `return_24h` label per (category, session), in window-end order."""
    if not events:
        return []

    by_category: dict[str, list[datetime]] = defaultdict(list)
    for event in events:
        by_category[event.category].append(event.occurred_at)
    for moments in by_category.values():
        moments.sort()

    horizon = timedelta(hours=horizon_hours)
    labels: list[Label] = []

    for window_end, category, session_id in session_label_pairs(
        events, timeout_seconds=timeout_seconds
    ):
        moments = by_category[category]
        # bisect_right puts the cut past any exact match, which is what makes the
        # boundary strictly after window_end even when an event lands on it.
        index = bisect_right(moments, window_end)
        outcome = index < len(moments) and moments[index] <= window_end + horizon
        labels.append(
            Label(
                target=TARGET,
                subject=category,
                window_end=window_end,
                outcome=outcome,
                horizon_hours=horizon_hours,
                session_id=session_id,
            )
        )

    labels.sort(key=lambda label: (label.window_end, label.subject))
    return labels
