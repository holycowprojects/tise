"""Is attention predictable? Dwell labels and features, one per visit.

> Given a page you have just opened, will you stay longer than you usually stay on pages of
> this category?

**This is the `full` compat class, and that is the point of measuring it now.** Since T1 the
duration trap has been recorded as permanent: the history *file* has `visit_duration`, the
`chrome.history` API does not, so every dwell analysis was research-only and unshippable.
`chrome.tabs` would let the extension measure dwell live — so the question stops being
academic, and the file lets us answer it **before** asking for that permission rather than
after.

**Why a visit is the right unit.** `return_24h` had one label per (category, session);
`block_volume` had one per (category, day) and produced 403 across three corpora. A visit
gives one label per *event* — thousands. Label scarcity has been the binding constraint on
every target this project has tried, and this is the finest unit the data contains.

**Why the label is a median split against the category's own recent dwell.** It makes the
base rate ~50% for any person and any category by construction — the property D88 wanted and
D90 measured as false for daily blocks, where the unit was coarse enough for volume trends to
dominate. At visit level the trailing window spans hours rather than weeks, so there is far
less room for drift.

**No URL, no path.** `Visit` drops the URL at the reader boundary and nothing here reaches
past it. Path-derived features are a separate decision that has not been made.

Leakage is structural, as in `block_labels.py`: a visit's label and features are emitted
before that visit joins any state.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median

from tise_research.features.events import Event
from tise_research.features.labels import Label
from tise_research.features.sessions import sessionise
from tise_research.features.vector import FeatureRow, saturate

__all__ = [
    "ATTENTION_FEATURE_SET",
    "ATTENTION_TARGET",
    "DEFAULT_MIN_PRIOR_VISITS",
    "DEFAULT_TRAILING_VISITS",
    "AttentionExample",
    "attention_examples",
]

ATTENTION_TARGET = "attention_dwell"
ATTENTION_FEATURE_SET = "as_1"

#: Visits of the same category the median is taken over.
DEFAULT_TRAILING_VISITS = 20

#: Visits of a category before it can be predicted at all.
DEFAULT_MIN_PRIOR_VISITS = 10

#: Dwell at which `dwellLevel` reaches 0.5, in seconds. Thirty seconds is an ordinary page
#: read; declared, not fitted, per D81.
DWELL_SCALE_SECONDS = 30.0

#: Session position saturation, in visits. Declared.
POSITION_SCALE = 10.0


@dataclass(frozen=True, slots=True)
class AttentionExample:
    label: Label
    row: FeatureRow


def _transition_flags(transition: str) -> dict[str, float]:
    """How the person arrived. The one genuinely *conditional* fact each visit carries.

    `typed` and `auto_bookmark` are deliberate acts; `link` is incidental. Nothing in this
    project has ever used the distinction, though it has been collected since T1.
    """
    core = transition.lower()
    return {
        "arrivedTyped": 1.0 if core in {"typed", "generated", "keyword"} else 0.0,
        "arrivedBookmark": 1.0 if "bookmark" in core else 0.0,
        "arrivedLink": 1.0 if core == "link" else 0.0,
    }


def attention_examples(
    events: Sequence[Event],
    *,
    timeout_seconds: float,
    trailing: int = DEFAULT_TRAILING_VISITS,
    min_prior: int = DEFAULT_MIN_PRIOR_VISITS,
) -> list[AttentionExample]:
    """One example per visit that has enough history of its own category.

    Visits with no recorded dwell are skipped rather than imputed: a missing duration is not
    a short one, and inventing a value here would be the defect D51 forbids.
    """
    sessions = sessionise(events, timeout_seconds=timeout_seconds)

    history: dict[str, list[float]] = {}
    examples: list[AttentionExample] = []
    previous_category: str | None = None

    for session in sessions:
        for position, event in enumerate(session.events):
            dwell = event.dwell_seconds
            prior = history.get(event.category, [])
            window = prior[-trailing:]

            if dwell is not None and len(prior) >= min_prior:
                threshold = median(window)
                hour_angle = 2.0 * math.pi * event.occurred_at.hour / 24.0
                values: dict[str, float | None] = {
                    "dwellLevel": saturate(float(threshold), DWELL_SCALE_SECONDS),
                    "lastDwellRatio": window[-1] / (threshold + 1.0),
                    "meanRatio": (sum(window) / len(window)) / (threshold + 1.0),
                    "sessionPosition": saturate(float(position), POSITION_SCALE),
                    "isSessionStart": 1.0 if position == 0 else 0.0,
                    "sameAsPrevious": (
                        1.0 if previous_category == event.category else 0.0
                    ),
                    "hourSin": math.sin(hour_angle),
                    "hourCos": math.cos(hour_angle),
                    "isWeekend": 1.0 if event.occurred_at.weekday() >= 5 else 0.0,
                    **_transition_flags(event.transition),
                }
                examples.append(
                    AttentionExample(
                        label=Label(
                            target=ATTENTION_TARGET,
                            subject=event.category,
                            window_end=event.occurred_at,
                            outcome=dwell > threshold,
                            horizon_hours=0.0,
                            session_id=event.event_id,
                        ),
                        row=FeatureRow(
                            subject=event.category,
                            window_end=event.occurred_at,
                            feature_set=ATTENTION_FEATURE_SET,
                            compat="full",
                            values=values,
                        ),
                    )
                )

            # Only now does this visit become history.
            if dwell is not None:
                history.setdefault(event.category, []).append(dwell)
            previous_category = event.category

    return examples
