"""T-E — what a browsing session *is like*, as eight numbers per session.

D95 adopted session intent clustering from an outside plan: group sessions into recurring
types — it guessed "research, routine checking, entertainment, exploration" — from
session-level features rather than predicting anything. **Descriptive, so it ships without
clearing a prediction bar**, which is why it is worth doing at all given D92: a per-topic
rate table is very hard to beat, and this does not have to beat it.

**These are deliberately not in `FEATURE_SETS`.** Everything in `vector.py` is a model
feature: it carries a compat class, it is bound by the parity contract, and the extension
owes a TypeScript twin for it. These describe a session for a clustering routine that
predicts nothing, and registering them there would claim three obligations that do not
apply. The ordered tuple lives here instead.

**Two of D95's suggested inputs are missing, and both for stated reasons:**

* **Idle periods.** Only the `idle` permission can measure them (D96), and no history
  database records them. They would be the most informative feature here — a 40-minute
  session with one visit is a different thing depending on whether the person was there —
  and they are simply not available offline.
* **Time of day.** Deliberately excluded from the clustering, and reported *beside* it
  instead. A clustering handed the clock will happily recover morning-versus-evening and
  present it as a discovery about session types. Holding it out means the clusters are
  defined by what the session was *like*, and "do these types happen at different times?"
  becomes a question the report can then ask and answer.

Everything unbounded is saturated (D81), on scales declared here and never fitted.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from tise_research.features.sessions import Session

__all__ = [
    "DOMAIN_COUNT_SCALE",
    "DURATION_SCALE_MINUTES",
    "SESSION_FEATURES",
    "SESSION_FEATURE_SET",
    "VISIT_COUNT_SCALE",
    "SessionShape",
    "session_shapes",
]

SESSION_FEATURE_SET = "ss_1"

#: Visits at which `visitCount` reaches 0.5. Chrome averages ~35 visits a session (D95), so
#: twenty puts the median session near the middle of the range rather than at its floor.
VISIT_COUNT_SCALE = 20.0

#: Distinct domains at which `domainCount` reaches 0.5.
DOMAIN_COUNT_SCALE = 8.0

#: Minutes at which `durationMinutes` reaches 0.5. Half the 30-minute session timeout, which
#: is the only timescale this project has already committed to (D17).
DURATION_SCALE_MINUTES = 15.0

#: Ordered, and the order is the contract: it is the column order of the matrix these build.
SESSION_FEATURES: tuple[str, ...] = (
    "visitCount",
    "domainCount",
    "categoryCount",
    "durationMinutes",
    "domainRepeatRate",
    "categoryEvenness",
    "typedShare",
    "linkShare",
)


@dataclass(frozen=True, slots=True)
class SessionShape:
    session_id: str
    values: tuple[float, ...]
    #: Held out of the clustering and reported beside it — see the module docstring.
    started_hour: int
    is_weekend: bool
    #: Raw, unsaturated, for the report's cluster profiles. A saturated 0.71 means nothing
    #: to a reader; "17 visits" does.
    visits: int
    domains: int
    duration_minutes: float


def _saturate(value: float, scale: float) -> float:
    return value / (value + scale)


def _evenness(counts: Sequence[int]) -> float:
    """Normalised Shannon entropy of a distribution: 0 when one bucket holds everything.

    Divided by `log(k)` for the **k buckets actually present**, so this measures how evenly
    a session is spread across the categories it touched, and never how many it touched.
    `categoryCount` carries that separately, and collapsing the two into one number is how
    a diverse session and an even one stop being distinguishable.
    """
    total = sum(counts)
    present = [count for count in counts if count > 0]
    if total == 0 or len(present) < 2:
        return 0.0
    entropy = -sum((count / total) * math.log(count / total) for count in present)
    return entropy / math.log(len(present))


def session_shapes(sessions: Sequence[Session]) -> list[SessionShape]:
    """One row per session, in chronological order.

    No leakage guard is needed and none is claimed: a session is described entirely by its
    own events, nothing here looks outside it, and there is no outcome to leak. That is a
    property of a descriptive analysis rather than a virtue of this code, and saying so
    stops the absence of the usual `window_end` argument from reading as an oversight.
    """
    shapes: list[SessionShape] = []
    for session in sessions:
        events = session.events
        visits = len(events)
        domains: dict[str, int] = {}
        categories: dict[str, int] = {}
        typed = 0
        link = 0
        for event in events:
            domains[event.domain] = domains.get(event.domain, 0) + 1
            categories[event.category] = categories.get(event.category, 0) + 1
            core = event.transition.lower()
            if core in {"typed", "generated", "keyword"}:
                typed += 1
            elif core == "link":
                link += 1

        duration = session.duration_seconds / 60.0
        shapes.append(
            SessionShape(
                session_id=session.session_id,
                values=(
                    _saturate(float(visits), VISIT_COUNT_SCALE),
                    _saturate(float(len(domains)), DOMAIN_COUNT_SCALE),
                    _saturate(float(len(categories)), DOMAIN_COUNT_SCALE),
                    _saturate(duration, DURATION_SCALE_MINUTES),
                    # A session of one visit repeats nothing, which is a measured zero
                    # rather than an absence: it was counted and found not to repeat.
                    1.0 - (len(domains) / visits) if visits else 0.0,
                    _evenness(list(categories.values())),
                    typed / visits if visits else 0.0,
                    link / visits if visits else 0.0,
                ),
                started_hour=session.started_at.hour,
                is_weekend=session.started_at.weekday() >= 5,
                visits=visits,
                domains=len(domains),
                duration_minutes=duration,
            )
        )
    return shapes
