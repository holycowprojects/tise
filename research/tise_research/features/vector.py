"""Assemble one feature row. The single place that decides what the model sees.

`extension/src/features/vector.ts` is the mirror, and the two must produce identical
dictionaries — same keys, same order-independent values, within 1e-9.

**Compat classes.** Every feature declares whether it belongs to the `history` class
(computable from what `chrome.history` and `webNavigation` provide) or the `full` class
(needs dwell time, which only the history *database* has). In V1 **every feature is
`history`** and the `full` class is empty — a direct consequence of D35, which stopped
Tise from measuring dwell in either direction. The mechanism stays because the
distinction is real and the day it stops being empty must not be the day it gets invented.

**`FEATURE_SET` is part of the contract.** A benchmark is only reproducible if you know
which features produced it, so the version travels on every row and is bumped whenever
this dictionary's keys or semantics change.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from tise_research.features.context import (
    category_events_in_session,
    day_of_week,
    hour_of_day,
    session_category_count,
    session_event_count,
)
from tise_research.features.events import Event
from tise_research.features.frequency import (
    category_share,
    days_seen,
    event_count,
    session_count,
)
from tise_research.features.priors import prior_return_rate, prior_session_count
from tise_research.features.recency import hours_since_first_seen, hours_since_last_seen

__all__ = ["FEATURE_NAMES", "FEATURE_SET", "CompatClass", "FeatureRow", "compute_features"]

#: Bumped whenever a feature is added, removed, or changes meaning. fs_1 was one feature;
#: fs_2 is the full V1 set.
FEATURE_SET = "fs_2"

CompatClass = Literal["history", "full"]

#: Ordered, and the order is part of the contract: it is the column order of any matrix
#: built from these rows, and a silent reordering would swap two coefficients.
FEATURE_NAMES: tuple[str, ...] = (
    "hoursSinceLastSeen",
    "hoursSinceFirstSeen",
    "eventCount7d",
    "eventCount30d",
    "daysSeen7d",
    "sessionCount7d",
    "categoryShare30d",
    "priorReturnRate",
    "priorSessionCount",
    "sessionEventCount",
    "sessionCategoryCount",
    "categoryEventsInSession",
    "hourOfDay",
    "dayOfWeek",
)

#: Every one of them, by D35. See the module docstring.
COMPAT: dict[str, CompatClass] = {name: "history" for name in FEATURE_NAMES}


@dataclass(frozen=True, slots=True)
class FeatureRow:
    """One feature vector, and everything needed to reproduce it.

    Survives raw deletion (D11), so this shape is effectively permanent.
    """

    subject: str
    window_end: datetime
    feature_set: str
    compat: CompatClass
    values: dict[str, float | None]


def compute_features(
    events: Sequence[Event],
    category: str,
    *,
    window_end: datetime,
    timeout_seconds: float,
    horizon_hours: float,
) -> FeatureRow:
    """Every feature for one (category, window_end) pair.

    Nothing here reads an event at or after `window_end` except the session-context
    functions, which take events *up to and including* it — that instant is the end of
    the session being described, not the future. See `context.py`.
    """
    values: dict[str, float | None] = {
        "hoursSinceLastSeen": hours_since_last_seen(
            events, category, window_end=window_end
        ),
        "hoursSinceFirstSeen": hours_since_first_seen(
            events, category, window_end=window_end
        ),
        "eventCount7d": float(
            event_count(events, category, window_end=window_end, days=7)
        ),
        "eventCount30d": float(
            event_count(events, category, window_end=window_end, days=30)
        ),
        "daysSeen7d": float(days_seen(events, category, window_end=window_end, days=7)),
        "sessionCount7d": float(
            session_count(
                events,
                category,
                window_end=window_end,
                days=7,
                timeout_seconds=timeout_seconds,
            )
        ),
        "categoryShare30d": category_share(
            events, category, window_end=window_end, days=30
        ),
        "priorReturnRate": prior_return_rate(
            events,
            category,
            window_end=window_end,
            timeout_seconds=timeout_seconds,
            horizon_hours=horizon_hours,
        ),
        "priorSessionCount": float(
            prior_session_count(
                events,
                category,
                window_end=window_end,
                timeout_seconds=timeout_seconds,
                horizon_hours=horizon_hours,
            )
        ),
        "sessionEventCount": float(
            session_event_count(
                events, window_end=window_end, timeout_seconds=timeout_seconds
            )
        ),
        "sessionCategoryCount": float(
            session_category_count(
                events, window_end=window_end, timeout_seconds=timeout_seconds
            )
        ),
        "categoryEventsInSession": float(
            category_events_in_session(
                events, category, window_end=window_end, timeout_seconds=timeout_seconds
            )
        ),
        "hourOfDay": float(hour_of_day(window_end)),
        "dayOfWeek": float(day_of_week(window_end)),
    }

    missing = set(FEATURE_NAMES) - set(values)
    extra = set(values) - set(FEATURE_NAMES)
    if missing or extra:
        raise AssertionError(f"feature set mismatch: missing={missing} extra={extra}")

    return FeatureRow(
        subject=category,
        window_end=window_end,
        feature_set=FEATURE_SET,
        compat="history",
        values=values,
    )
