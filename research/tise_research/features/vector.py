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

__all__ = [
    "DEFAULT_FEATURE_SET",
    "FEATURE_NAMES",
    "FEATURE_SET",
    "FEATURE_SETS",
    "FIRST_SEEN_SCALE_HOURS",
    "PRIOR_SESSION_RATE_SCALE",
    "CompatClass",
    "FeatureRow",
    "compute_features",
    "feature_names",
    "saturate",
]

#: Bumped whenever a feature is added, removed, or changes meaning. fs_1 was one feature;
#: fs_2 is the full V1 set; fs_3 replaces the two features that grow with the calendar
#: (D81). `fs_2` is what the extension ships until that is decided.
DEFAULT_FEATURE_SET = "fs_3"
FEATURE_SET = DEFAULT_FEATURE_SET

#: Hours at which `firstSeenSaturation` reaches 0.5. Seven days, matching the 7-day
#: windows already in the set, so there is one notion of "recent" rather than two.
#: Declared, not fitted — see D81.
FIRST_SEEN_SCALE_HOURS = 168.0

#: Sessions per day at which `priorSessionRate` reaches 0.5. One a day is the natural unit
#: of a daily habit. Declared, not fitted.
PRIOR_SESSION_RATE_SCALE = 1.0


def saturate(value: float, scale: float) -> float:
    """Map [0, inf) onto [0, 1), reaching 0.5 at `scale`.

    The point is the bound, not the shape. A feature that can only grow lets a test row
    land arbitrarily far outside the range its coefficient was fitted on; a feature in
    [0, 1) cannot. See D81 for why the two features this is applied to had to go.
    """
    if value < 0.0:
        raise ValueError(f"refusing to saturate a negative value: {value}")
    return value / (value + scale)

CompatClass = Literal["history", "full"]

#: Ordered, and the order is part of the contract: it is the column order of any matrix
#: built from these rows, and a silent reordering would swap two coefficients.
#:
#: `fs_3` differs in exactly two positions, and keeps them: replacing a feature in place
#: rather than appending keeps the two sets comparable column by column, which is what
#: makes a coefficient from one readable next to the other.
_FS2: tuple[str, ...] = (
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

_FS3: tuple[str, ...] = tuple(
    {
        "hoursSinceFirstSeen": "firstSeenSaturation",
        "priorSessionCount": "priorSessionRate",
    }.get(name, name)
    for name in _FS2
)

#: `bs_1` — the first feature set for `block_volume` (D91). **Declared before any model was
#: fitted to it**, and computed from blocks rather than from a session, so nothing in
#: `fs_2`/`fs_3` applies: those describe a category at the instant a session closed.
#:
#: Three ideas, and each is here for a stated reason rather than because it was available:
#:
#: * **Persistence** — `prevAbove`, `lastRatio`, `streakAbove`, `daysSinceAbove`. D91's
#:   third prediction is that `same_as_last` beats a per-topic table, because daily browsing
#:   is bursty. If that holds, these carry it; if it fails, they should be near-useless, and
#:   either way the prediction is checkable against these coefficients.
#: * **Level** — `medianLevel`, `activeRate10`, `topicShare10`. How large and how regular
#:   this topic is, which conditions everything else.
#: * **Calendar** — `dayOfWeekSin`/`dayOfWeekCos`. D86 measured an 18-29 point day-of-week
#:   spread that is **non-monotone**, so a plain integer cannot represent it and a cyclic
#:   pair can. This is the first place that finding is acted on.
#:
#: Everything unbounded is saturated, per D81: a feature that can only grow lets a test row
#: land arbitrarily far outside the range its coefficient was fitted on.
#:
#: **No TypeScript twin yet.** The parity contract binds features the extension computes,
#: and nothing here ships until the target is adopted. Recorded so the gap is deliberate.
_BS1: tuple[str, ...] = (
    "prevAbove",
    "lastRatio",
    "streakAbove",
    "daysSinceAbove",
    "medianLevel",
    "activeRate10",
    "topicShare10",
    "totalRatio",
    "dayOfWeekSin",
    "dayOfWeekCos",
)

#: `as_1` — attention (dwell) features, one row per visit. **`full` compat class**: it needs
#: dwell time, which the `chrome.history` API cannot supply. Research-only unless the
#: `tabs` permission is added, which is exactly the decision this measurement informs.
#:
#: `arrivedTyped` / `arrivedBookmark` / `arrivedLink` are the first use in this project of
#: the `transition` field, which has been collected since T1 and read by no feature.
_AS1: tuple[str, ...] = (
    "dwellLevel",
    "lastDwellRatio",
    "meanRatio",
    "sessionPosition",
    "isSessionStart",
    "sameAsPrevious",
    "hourSin",
    "hourCos",
    "isWeekend",
    "arrivedTyped",
    "arrivedBookmark",
    "arrivedLink",
)

FEATURE_SETS: dict[str, tuple[str, ...]] = {
    "fs_2": _FS2,
    "fs_3": _FS3,
    "bs_1": _BS1,
    "as_1": _AS1,
}

FEATURE_NAMES: tuple[str, ...] = FEATURE_SETS[DEFAULT_FEATURE_SET]


def feature_names(feature_set: str) -> tuple[str, ...]:
    """The ordered names of a feature set, or a loud failure.

    Guessing at an unknown name would produce a design matrix of the wrong width and a
    model whose coefficients mean something other than their labels.
    """
    try:
        return FEATURE_SETS[feature_set]
    except KeyError:
        raise ValueError(
            f"unknown feature set {feature_set!r}; known: {sorted(FEATURE_SETS)}"
        ) from None


#: Every one of them, by D35. See the module docstring.
COMPAT: dict[str, CompatClass] = {
    name: "history" for names in FEATURE_SETS.values() for name in names
}


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
    feature_set: str = DEFAULT_FEATURE_SET,
) -> FeatureRow:
    """Every feature for one (category, window_end) pair.

    Nothing here reads an event at or after `window_end` except the session-context
    functions, which take events *up to and including* it — that instant is the end of
    the session being described, not the future. See `context.py`.

    Both feature sets are computed and the requested one is selected, because `fs_3`'s two
    features are pure transforms of `fs_2`'s and recomputing the traversals to get them
    would be the same work twice with two chances to disagree.
    """
    names = feature_names(feature_set)
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

    # --- fs_3: bounded replacements for the two features that grow with the calendar ---
    #
    # `firstSeenSaturation` stays None exactly when `hoursSinceFirstSeen` is None — the
    # category has not been seen before `window_end` — because "never seen" is an absence,
    # not a saturation of zero, and the missing-indicator column is what carries it.
    hours_first = values["hoursSinceFirstSeen"]
    values["firstSeenSaturation"] = (
        None if hours_first is None else saturate(hours_first, FIRST_SEEN_SCALE_HOURS)
    )

    # `priorSessionRate` is never None: with no prior sessions the rate is zero, which is a
    # measured zero rather than an absence. The one-day floor on the denominator stops a
    # category first seen an hour ago from reporting a rate of twenty-four a day.
    observed_days = 0.0 if hours_first is None else hours_first / 24.0
    prior_sessions = values["priorSessionCount"]
    assert prior_sessions is not None  # a count, never absent
    values["priorSessionRate"] = saturate(
        prior_sessions / max(observed_days, 1.0), PRIOR_SESSION_RATE_SCALE
    )

    missing = set(names) - set(values)
    if missing:
        raise AssertionError(f"feature set {feature_set} is missing: {missing}")

    return FeatureRow(
        subject=category,
        window_end=window_end,
        feature_set=feature_set,
        compat="history",
        values={name: values[name] for name in names},
    )
