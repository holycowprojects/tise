"""T-C — `next_category` labels: given the category just finished, which comes next?

**Pre-registered in D94, before anything was fitted.** The definition below is the one
sentence in that entry that has to be turned into code, and the turning is where the
choices are, so each is stated rather than made silently.

> **Labels:** every category change, **within** sessions as well as between them.

**A label is a change, so consecutive same-category visits are one run.** The event stream
is collapsed into maximal runs of the same category and each adjacent pair of runs is one
label. `from_category != to_category` therefore holds by construction — "what comes next"
when the answer is "more of the same" is not a change, and D94 says changes.

That is the whole reason this is not simply "the next visit's category", which would have
produced roughly one label per event and a floor dominated by persistence. It also makes
the target the *hard* half of the problem: the easy, high-volume, highly predictable mass
is exactly what run-collapsing removes.

**A session boundary with no category change produces no label.** If a session ends on
`video` and the next begins on `video`, the run continues across the gap and nothing is
recorded. That differs from T19's between-session measurement, which used one primary
category per session and permitted a self-transition, and it is why the 33.2% floor that
entry reported is **not** the number this target scores against — see `analysis/
next_category.py`. The count of boundaries lost this way is reported, so the cost is
visible rather than assumed.

**The clock on a label is when the *next* run starts**, because that is the instant the
answer becomes known. Folds are cut on that instant, which is what keeps a transition out
of any training window that precedes it.

**The session recorded is the one the prediction is made from** — the session holding the
source run's last event. A between-session label therefore clusters with the sitting that
produced the question, not the one that answered it, and every within-session label from a
sitting clusters with it. D94 fixed the cluster unit as the session; this is what that
means for a label that straddles two.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from tise_research.features.events import Event
from tise_research.features.sessions import Session

__all__ = [
    "CategoryTransition",
    "category_transitions",
    "session_boundaries_without_change",
]


@dataclass(frozen=True, slots=True)
class CategoryTransition:
    """One category change. The multiclass analogue of `Label`.

    `Label.outcome` is a bool and cannot hold this; that is the reason `run_backtest` could
    not score T-C and `run_multiclass_backtest` exists.
    """

    #: Unique per label. The first event of the run being predicted — each event starts at
    #: most one run, so this cannot collide.
    transition_id: str
    #: When the next run's first event occurred: the moment the answer became known.
    at: datetime
    #: The category just finished. What the model conditions on.
    from_category: str
    #: The category that followed. The thing being predicted.
    to_category: str
    #: The session the source run ended in — the sitting the question was asked in (D94).
    session_id: str
    #: False when the two runs are separated by a session boundary.
    within_session: bool
    #: The category of the run *before* the source run, or None at the start of the
    #: corpus. Strictly earlier than `at`, so it is available at prediction time and
    #: leaks nothing. It exists so `bounce_back` — did you return to what you were doing
    #: before? — can be scored as a rival; no feature vector reads it.
    previous_category: str | None
    #: How many events the source run held. Reported, never a feature: no feature code
    #: reads this module, and adding one would need its own leakage guard.
    from_run_events: int


def _runs(events: Sequence[tuple[Event, str]]) -> list[list[tuple[Event, str]]]:
    """Collapse a chronological `(event, session_id)` stream into same-category runs."""
    runs: list[list[tuple[Event, str]]] = []
    for item in events:
        if runs and runs[-1][-1][0].category == item[0].category:
            runs[-1].append(item)
        else:
            runs.append([item])
    return runs


def _flatten(sessions: Sequence[Session]) -> list[tuple[Event, str]]:
    """Every event with the session it belongs to, in chronological order.

    Sessions arrive ordered from `sessionise` and their events are ordered within them, so
    this is the corpus's event stream. It is re-sorted anyway — an out-of-order stream
    would silently merge two runs that never touched, and that is invisible afterwards.
    """
    flat = [(event, session.session_id) for session in sessions for event in session.events]
    flat.sort(key=lambda item: (item[0].occurred_at, item[0].event_id))
    return flat


def category_transitions(sessions: Sequence[Session]) -> list[CategoryTransition]:
    """Every category change in the corpus, within sessions and across their boundaries.

    Raises on a duplicate event id rather than silently producing two labels with the same
    `transition_id`. T-A hit exactly this on the GESIS panel — 0.02% of rows were a second
    visit by one person in the same second — and the fix there was to key labels properly,
    not to discard real visits, so the same defect is made loud here.
    """
    flat = _flatten(sessions)
    seen: set[str] = set()
    for event, _ in flat:
        if event.event_id in seen:
            raise ValueError(
                f"duplicate event id {event.event_id!r}: transition ids would collide"
            )
        seen.add(event.event_id)

    runs = _runs(flat)
    transitions: list[CategoryTransition] = []
    for index, (source, target) in enumerate(zip(runs, runs[1:], strict=False)):
        last_event, source_session = source[-1]
        first_event, target_session = target[0]
        transitions.append(
            CategoryTransition(
                transition_id=first_event.event_id,
                at=first_event.occurred_at,
                from_category=last_event.category,
                to_category=first_event.category,
                session_id=source_session,
                within_session=source_session == target_session,
                previous_category=runs[index - 1][0][0].category if index else None,
                from_run_events=len(source),
            )
        )
    return transitions


def session_boundaries_without_change(sessions: Sequence[Session]) -> int:
    """How many session boundaries the run-collapse absorbed because nothing changed.

    Reported in the benchmark so the reader can see what the "a label is a change"
    definition costs against T19's between-session count, rather than being told it is
    small.
    """
    lost = 0
    for previous, following in zip(sessions, sessions[1:], strict=False):
        if not previous.events or not following.events:
            continue
        if previous.events[-1].category == following.events[0].category:
            lost += 1
    return lost
