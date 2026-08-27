"""The transition table: what tends to follow what.

`extension/src/model/transition.ts` is the mirror.

This is the model behind `next_session_category`, which is a **UI-only** target — it is
displayed and it is not the number this project claims skill on. `return_24h` is the
evaluated target, and nothing here feeds it.

**A session gets one category, and choosing it is a declared simplification.** Real
sessions contain several, so "the next session's category" needs a rule before it means
anything. The rule is: the category with the most events in the session, ties broken by
name so the answer never depends on iteration order. A session that is half video and
half news is recorded as whichever wins, and that loses information — the honest
alternative, a multi-label table of P(c appears next | b appeared now), does not produce
a distribution over categories, which is what a "what's next" surface needs. The
simplification is recorded rather than hidden, and it is the reason this target is
displayed rather than scored.

**Smoothing is mandatory, for the reason D26 found.** A category seen twice, both times
followed by the same thing, would otherwise claim 100%. Every row is pulled toward the
marginal distribution of what follows anything, by a declared number of pseudo-counts.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from tise_research.features.sessions import Session

__all__ = [
    "DEFAULT_SMOOTHING",
    "TransitionTable",
    "fit_transition_table",
    "primary_category",
]

#: Pseudo-observations pulled from the marginal. One is enough to stop a two-observation
#: row claiming certainty, and small enough that a well-populated row keeps its shape.
DEFAULT_SMOOTHING = 1.0


def primary_category(session: Session) -> str:
    """The category with the most events in the session; ties broken by name.

    The tie-break is alphabetical rather than "first seen" on purpose: first-seen depends
    on within-session ordering, which two implementations could resolve differently for
    events sharing a timestamp.
    """
    counts: dict[str, int] = defaultdict(int)
    for event in session.events:
        counts[event.category] += 1
    return min(counts, key=lambda category: (-counts[category], category))


@dataclass(frozen=True, slots=True)
class TransitionTable:
    """Fitted counts plus the smoothing that turns them into probabilities.

    `vocabulary` is sorted, and it is the column order of every distribution this table
    produces — the same contract `FEATURE_NAMES` carries for the feature vector.
    """

    vocabulary: tuple[str, ...]
    #: from-category -> to-category -> raw count. Sparse: absent means zero.
    counts: dict[str, dict[str, int]]
    #: to-category -> raw count, over every transition. The fallback distribution.
    marginal: dict[str, int]
    smoothing: float

    @property
    def transition_count(self) -> int:
        return sum(self.marginal.values())

    def marginal_distribution(self) -> dict[str, float]:
        """What follows anything. Used when the current category was never seen."""
        total = self.transition_count
        if total == 0 or not self.vocabulary:
            uniform = 1.0 / len(self.vocabulary) if self.vocabulary else 0.0
            return {category: uniform for category in self.vocabulary}
        return {
            category: self.marginal.get(category, 0) / total
            for category in self.vocabulary
        }

    def distribution(self, from_category: str) -> dict[str, float]:
        """P(next session's primary category | this one), smoothed toward the marginal."""
        marginal = self.marginal_distribution()
        row = self.counts.get(from_category)
        if row is None:
            return marginal

        total = sum(row.values())
        denominator = total + self.smoothing
        if denominator == 0:
            return marginal
        return {
            category: (
                row.get(category, 0) + self.smoothing * marginal.get(category, 0.0)
            )
            / denominator
            for category in self.vocabulary
        }

    def most_likely(self, from_category: str) -> tuple[str, float] | None:
        """The top category and its probability, ties broken by name. `None` if unfitted."""
        distribution = self.distribution(from_category)
        if not distribution:
            return None
        best = min(distribution, key=lambda name: (-distribution[name], name))
        return best, distribution[best]


def fit_transition_table(
    sessions: Sequence[Session], *, smoothing: float = DEFAULT_SMOOTHING
) -> TransitionTable:
    """Count consecutive session pairs. Sessions must already be in chronological order.

    `sessionise` returns them that way, and re-sorting here would hide a caller that
    handed over something out of order.
    """
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    marginal: dict[str, int] = defaultdict(int)
    vocabulary: set[str] = set()

    primaries = [primary_category(session) for session in sessions if session.events]
    for category in primaries:
        vocabulary.add(category)

    for current, following in zip(primaries, primaries[1:], strict=False):
        counts[current][following] += 1
        marginal[following] += 1

    return TransitionTable(
        vocabulary=tuple(sorted(vocabulary)),
        counts={key: dict(value) for key, value in sorted(counts.items())},
        marginal=dict(sorted(marginal.items())),
        smoothing=smoothing,
    )
