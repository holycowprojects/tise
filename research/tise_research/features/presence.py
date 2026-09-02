"""T-B — `browsing_next_hour`: will you be here?

> For each clock hour in the observed span: will at least one visit occur in the next hour?

**D94 fixed the label, the subject, the cluster unit, the bar and the adoption rule before
any of this existed.** What D94 did *not* fix is the feature set, so `pr_1` below is
declared here and committed **unrun**, ahead of the numbers, for the same reason D81 and
D99 were: choosing features after seeing what scores is the forking path pre-registration
exists to close.

## The label

One per hour boundary `t`: positive if any visit falls in `[t, t + 1h)`. `window_end` is
`t` itself, so a feature vector may read everything strictly before `t` and nothing at or
after it — the leakage guard in its usual form.

**Both boundary hours are excluded, because both are positive by construction.** The first
labelled hour of a corpus contains the first visit and the last contains the last visit, so
scoring either would be scoring a row whose answer is fixed by where the data was cut. The
span therefore runs over boundaries strictly after the first visit's hour and strictly
before the last visit's hour.

**Empty hours are labels, not gaps.** An hour with no browsing is a real negative — it is
most of the target, since a person sleeps — and dropping it is the T19b defect in a new
place, where a week nobody browsed vanished and lifted every median after it. Roughly a
third of these labels are hours a person was asleep, which is exactly why D94 made the bar
the per-hour rhythm rather than a constant.

## The subject is the hour of day *being predicted*

`subject` is `t.hour`, zero-padded. That is deliberate and it is what makes
`category_base_rate` the per-hour rate with no new baseline code — D94 said so before this
module existed. Keying on the hour Tise is standing *in* would make the bar a rhythm lagged
by an hour, which is a different and weaker thing.

## `session_id` carries the calendar day

D94's cluster unit for this target is the **calendar day**, and `run_backtest` clusters on
whatever `session_id` holds. A session is not a meaningful unit here — a label exists for
3am whether or not anyone was awake — so the field carries the day and every interval built
from it is printed with `unit="day"` so the name on the number is the thing that was
resampled. D86 and D87 are both about a right number under a wrong label.

## `pr_1`

Eight features, every scale **declared and not fitted** (D81), everything unbounded
saturated, and **all of them `history` compat class** — nothing here needs dwell, so unlike
`as_2` this set is shippable the day it clears a bar rather than waiting on a permission.

The set has to contain the rhythm. The bar *is* the rhythm, so a model denied the hour of
day could not beat it even in principle, and a test rigged that way is worth nothing in
either direction. What the model has that the bar does not is three things: the hour as a
smooth cycle rather than 24 independent buckets, the day of the week, and what the person
has been doing in the last few hours.

**No TypeScript twin.** The parity contract binds features the extension computes, and
nothing ships until a target is adopted — same position `bs_1` was in at D91.
"""

from __future__ import annotations

import math
from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from tise_research.features.events import Event
from tise_research.features.labels import Label
from tise_research.features.vector import FeatureRow, feature_names, saturate

__all__ = [
    "ACTIVITY_WINDOW_HOURS",
    "LAST_VISIT_SCALE_MINUTES",
    "PRESENCE_FEATURE_SET",
    "RHYTHM_WINDOW_DAYS",
    "TARGET",
    "VISITS_LAST_HOUR_SCALE",
    "VISITS_LAST_SIX_HOURS_SCALE",
    "PresenceExample",
    "presence_examples",
]

TARGET = "browsing_next_hour"

PRESENCE_FEATURE_SET = "pr_1"

#: Minutes since the last visit at which `minutesSinceLast` reaches 0.5. An hour, matching
#: the length of the window being predicted, so there is one notion of "just now" rather
#: than two. Declared, not fitted.
LAST_VISIT_SCALE_MINUTES = 60.0

#: Visits in the hour just ended at which `visitsLastHour` reaches 0.5.
VISITS_LAST_HOUR_SCALE = 5.0

#: Visits in the last six hours at which `visitsLastSixHours` reaches 0.5. Six hours is a
#: sitting-length window rather than a day, and the scale is the hourly one times six so
#: the two features agree about what a busy hour looks like.
VISITS_LAST_SIX_HOURS_SCALE = 30.0

#: How many previous days `sameHourRate7d` looks back over. Seven, matching every other
#: 7-day window in the project (D81's reason for `FIRST_SEEN_SCALE_HOURS`).
RHYTHM_WINDOW_DAYS = 7

#: How many hours back `activeHourShare7d` looks. The same seven days, in hours.
ACTIVITY_WINDOW_HOURS = 168

HOUR = timedelta(hours=1)


@dataclass(frozen=True, slots=True)
class PresenceExample:
    label: Label
    row: FeatureRow


def _floor_hour(moment: datetime) -> datetime:
    return moment.replace(minute=0, second=0, microsecond=0)


def presence_examples(
    events: Sequence[Event],
    *,
    feature_set: str = PRESENCE_FEATURE_SET,
) -> list[PresenceExample]:
    """One example per hour boundary in the observed span, in chronological order.

    Nothing reads an event at or after the boundary being labelled. The only global fact
    any feature uses is where the corpus *starts*, which is known at every boundary; where
    it **ends** is used to decide which boundaries get a label and is never visible to a
    feature, because that would be the future.
    """
    names = feature_names(feature_set)
    if not events:
        return []

    moments = sorted(event.occurred_at for event in events)
    first_hour = _floor_hour(moments[0])
    last_hour = _floor_hour(moments[-1])

    #: Every hour in which something happened. A set rather than a scan, because both
    #: rhythm features ask the same question about a lot of hours.
    active: set[datetime] = {_floor_hour(moment) for moment in moments}

    examples: list[PresenceExample] = []
    boundary = first_hour + HOUR
    while boundary < last_hour:
        examples.append(
            PresenceExample(
                label=_label(boundary, active=active),
                row=_row(
                    boundary,
                    moments=moments,
                    active=active,
                    corpus_start=first_hour,
                    names=names,
                    feature_set=feature_set,
                ),
            )
        )
        boundary += HOUR

    return examples


def _label(boundary: datetime, *, active: set[datetime]) -> Label:
    """Positive if the hour opening at `boundary` holds a visit.

    `active` is a set of floored hours, so membership *is* the outcome — there is no
    comparison against `boundary + HOUR` to get inclusive-versus-exclusive wrong.
    """
    return Label(
        target=TARGET,
        subject=f"{boundary.hour:02d}",
        window_end=boundary,
        outcome=boundary in active,
        horizon_hours=1.0,
        # D94's cluster unit. See the module docstring — this is a day, not a session.
        session_id=boundary.date().isoformat(),
        label_id=boundary.isoformat(),
    )


def _count_between(moments: Sequence[datetime], start: datetime, end: datetime) -> int:
    """Visits in `[start, end)`. Half-open at both ends, so adjacent windows cannot
    double-count a visit landing exactly on a boundary."""
    return bisect_left(moments, end) - bisect_left(moments, start)


def _row(
    boundary: datetime,
    *,
    moments: Sequence[datetime],
    active: set[datetime],
    corpus_start: datetime,
    names: tuple[str, ...],
    feature_set: str,
) -> FeatureRow:
    # Strictly before the boundary: `bisect_left` puts the cut at the first visit at or
    # after it, so the visit immediately before is at index-1 and a visit landing exactly
    # on the boundary is excluded. That is the leakage guard.
    cut = bisect_left(moments, boundary)
    minutes_since_last = (boundary - moments[cut - 1]).total_seconds() / 60.0

    # Only hours the corpus actually covers count. Without the clamp the first week of any
    # corpus reads as unusually quiet, because hours before collection began would be
    # counted as hours the person chose not to browse — the T19b defect, where a block
    # nobody browsed was dropped instead of counted, in the opposite direction.
    rhythm_hours = [
        boundary - timedelta(days=day)
        for day in range(1, RHYTHM_WINDOW_DAYS + 1)
        if boundary - timedelta(days=day) >= corpus_start
    ]
    same_hour_rate = (
        None
        if not rhythm_hours
        else sum(1 for hour in rhythm_hours if hour in active) / len(rhythm_hours)
    )

    window_hours = [
        boundary - timedelta(hours=back)
        for back in range(1, ACTIVITY_WINDOW_HOURS + 1)
        if boundary - timedelta(hours=back) >= corpus_start
    ]
    # Never empty: a boundary is only labelled once it is at least one hour past the
    # corpus start, so the hour before it is always inside the span.
    active_share = sum(1 for hour in window_hours if hour in active) / len(window_hours)

    values: dict[str, float | None] = {
        "hourSin": math.sin(2.0 * math.pi * boundary.hour / 24.0),
        "hourCos": math.cos(2.0 * math.pi * boundary.hour / 24.0),
        "isWeekend": 1.0 if boundary.weekday() >= 5 else 0.0,
        "minutesSinceLast": saturate(minutes_since_last, LAST_VISIT_SCALE_MINUTES),
        "visitsLastHour": saturate(
            float(_count_between(moments, boundary - HOUR, boundary)),
            VISITS_LAST_HOUR_SCALE,
        ),
        "visitsLastSixHours": saturate(
            float(_count_between(moments, boundary - timedelta(hours=6), boundary)),
            VISITS_LAST_SIX_HOURS_SCALE,
        ),
        "sameHourRate7d": same_hour_rate,
        "activeHourShare7d": active_share,
    }

    missing = set(names) - set(values)
    if missing:
        raise AssertionError(f"feature set {feature_set} is missing: {missing}")

    return FeatureRow(
        subject=f"{boundary.hour:02d}",
        window_end=boundary,
        feature_set=feature_set,
        compat="history",
        values={name: values[name] for name in names},
    )
