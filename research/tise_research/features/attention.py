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

**Two feature sets, one label.** `as_1` is what D93 measured. `as_2` adds domain and
sequence features and is what T-A tests, and the label is deliberately **identical** so any
change in score is attributable to the features and the cluster unit rather than to a
redefinition. Both are computed in one pass and the requested set is selected, following
`compute_features`: recomputing the traversals per set would be the same work twice with
two chances to disagree. Regenerating the `as_1` report must move no figure, which is a
check on that claim rather than a hope.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median

from tise_research.features.events import Event
from tise_research.features.labels import Label
from tise_research.features.sessions import sessionise
from tise_research.features.vector import FeatureRow, feature_names, saturate

__all__ = [
    "ATTENTION_FEATURE_SET",
    "DAILY_DOMAIN_MIN_DAYS",
    "DAILY_DOMAIN_WINDOW_DAYS",
    "DEFAULT_MIN_PRIOR_VISITS",
    "DEFAULT_TRAILING_VISITS",
    "DOMAIN_SHARE_WINDOW",
    "DOMAIN_VISIT_SCALE",
    "ENGAGED_FEATURE_SET",
    "VISIT_ENGAGED_TARGET",
    "AttentionExample",
    "attention_examples",
]

#: One name for one thing. SPEC.md's `Prediction.target` union has said `visit_engaged`
#: since D94 while this constant said `attention_dwell`, which is two names for a single
#: target and exactly how a divergence starts — D87 found the same shape three times. The
#: label is unchanged; only what it is called is. No published figure moves, because no
#: report prints the target string.
VISIT_ENGAGED_TARGET = "visit_engaged"

#: What D93 measured. Kept so that report stays reproducible.
ATTENTION_FEATURE_SET = "as_1"

#: What T-A measures. Same label, more features — see the module docstring.
ENGAGED_FEATURE_SET = "as_2"

#: Visits of the same category the median is taken over.
DEFAULT_TRAILING_VISITS = 20

#: Visits of a category before it can be predicted at all.
DEFAULT_MIN_PRIOR_VISITS = 10

#: Dwell at which `dwellLevel` reaches 0.5, in seconds. Thirty seconds is an ordinary page
#: read; declared, not fitted, per D81.
DWELL_SCALE_SECONDS = 30.0

#: Session position saturation, in visits. Declared.
POSITION_SCALE = 10.0

#: Prior visits at which `domainVisits` reaches 0.5. Twenty, matching the trailing window
#: the median is taken over, so there is one notion of "enough history" and not two.
#: Declared, not fitted.
DOMAIN_VISIT_SCALE = 20.0

#: Visits `domainShare` is taken over. A hundred is a few days of this person's browsing —
#: long enough that a share is not one visit's worth of noise, short enough that a domain
#: abandoned last month has left it. Declared.
DOMAIN_SHARE_WINDOW = 100

#: `isDailyDomain` looks back this many calendar days and fires at this many of them.
#: Four of seven is a majority of the week, which is what "daily" is being used to mean.
#: Declared.
DAILY_DOMAIN_WINDOW_DAYS = 7
DAILY_DOMAIN_MIN_DAYS = 4


@dataclass(frozen=True, slots=True)
class AttentionExample:
    label: Label
    row: FeatureRow
    #: The domain this visit was to. Carried so a per-domain **baseline** can be fitted —
    #: D24 makes baselines mandatory, and once four of `as_2`'s six features read the
    #: domain, "a per-domain rate table would do the same job" is the first thing a reader
    #: should be able to check. It is not on the `Label`, because a label is a question and
    #: the domain is an input to answering it.
    #:
    #: **Never published.** It stays inside the research tier: reports may print counts of
    #: domains, never a domain. Invariant 2 is enforced upstream — `Visit` drops the URL at
    #: the reader boundary — and this is the reduced host, which `Event` has carried since
    #: T1 and no report has ever printed.
    domain: str = ""


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
    feature_set: str = ATTENTION_FEATURE_SET,
) -> list[AttentionExample]:
    """One example per visit that has enough history of its own category.

    Visits with no recorded dwell are skipped rather than imputed: a missing duration is not
    a short one, and inventing a value here would be the defect D51 forbids.

    `feature_set` selects `as_1` or `as_2`. **It changes only the features.** The label —
    outcome, subject, `window_end`, and which visits get one at all — is identical either
    way, which is what makes D93's numbers and T-A's comparable (D94).
    """
    names = feature_names(feature_set)
    sessions = sessionise(events, timeout_seconds=timeout_seconds)

    history: dict[str, list[float]] = {}
    domain_dwell: dict[str, list[float]] = {}
    domain_visits: dict[str, int] = {}
    domain_days: dict[str, set[date]] = {}
    #: Bounded, so `domainShare` describes recent browsing rather than all of it.
    recent_domains: deque[str] = deque(maxlen=DOMAIN_SHARE_WINDOW)

    examples: list[AttentionExample] = []
    seen: set[str] = set()
    previous_category: str | None = None
    previous_domain: str | None = None
    previous_dwell: float | None = None

    for session in sessions:
        for position, event in enumerate(session.events):
            dwell = event.dwell_seconds
            prior = history.get(event.category, [])
            window = prior[-trailing:]

            if dwell is not None and len(prior) >= min_prior:
                threshold = median(window)
                hour_angle = 2.0 * math.pi * event.occurred_at.hour / 24.0

                # --- domain state, all of it strictly before this visit ---
                domain_window = domain_dwell.get(event.domain, [])[-trailing:]
                first_day = event.occurred_at.date() - timedelta(
                    days=DAILY_DOMAIN_WINDOW_DAYS - 1
                )
                days_recently = sum(
                    1 for day in domain_days.get(event.domain, ()) if day >= first_day
                )
                # Guaranteed non-empty: `min_prior` prior visits of this category are
                # themselves prior visits. Asserted rather than given a zero fallback,
                # because a share over nothing is undefined and not zero.
                assert recent_domains, "a labelled visit always has prior visits"

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
                    # --- as_2 ---
                    "domainVisits": saturate(
                        float(domain_visits.get(event.domain, 0)), DOMAIN_VISIT_SCALE
                    ),
                    "domainShare": (
                        sum(1 for name in recent_domains if name == event.domain)
                        / len(recent_domains)
                    ),
                    "isDailyDomain": (
                        1.0 if days_recently >= DAILY_DOMAIN_MIN_DAYS else 0.0
                    ),
                    "domainDwellLevel": (
                        saturate(float(median(domain_window)), DWELL_SCALE_SECONDS)
                        if domain_window
                        else None
                    ),
                    "prevSameDomain": 1.0 if previous_domain == event.domain else 0.0,
                    "prevDwellRatio": (
                        None
                        if previous_dwell is None
                        else previous_dwell / (threshold + 1.0)
                    ),
                }

                # The key consumers index rows by. It is the *event* id, not the
                # (category, instant) pair those consumers used until D99: that pair is
                # unique on Akash's browsing and not unique in general — the GESIS panel
                # records to the second, and one person can visit two pages of a category
                # within one. The guard stays, now on the thing that actually has to be
                # unique, because a duplicate here silently scores one row against two
                # labels.
                if event.event_id in seen:
                    raise ValueError(
                        f"duplicate event id {event.event_id!r}. Feature rows are indexed "
                        "by it, so one row would be scored against two labels and nothing "
                        "would report it."
                    )
                seen.add(event.event_id)

                examples.append(
                    AttentionExample(
                        domain=event.domain,
                        label=Label(
                            target=VISIT_ENGAGED_TARGET,
                            subject=event.category,
                            window_end=event.occurred_at,
                            outcome=dwell > threshold,
                            horizon_hours=0.0,
                            # The session, not the visit. D94 makes the session the
                            # resampling unit; it does not touch the label's meaning.
                            session_id=session.session_id,
                            label_id=event.event_id,
                        ),
                        row=FeatureRow(
                            subject=event.category,
                            window_end=event.occurred_at,
                            feature_set=feature_set,
                            compat="full",
                            values={name: values[name] for name in names},
                        ),
                    )
                )

            # Only now does this visit become history.
            if dwell is not None:
                history.setdefault(event.category, []).append(dwell)
                domain_dwell.setdefault(event.domain, []).append(dwell)
            domain_visits[event.domain] = domain_visits.get(event.domain, 0) + 1
            domain_days.setdefault(event.domain, set()).add(event.occurred_at.date())
            recent_domains.append(event.domain)
            previous_category = event.category
            previous_domain = event.domain
            previous_dwell = dwell

    return examples
