"""T-C's three models: the bar, the challenger, and one rival worth being embarrassed by.

**The bar is `global_mode`** — always predict the single most common next category. D94
named "the always-the-global-mode floor" and this is that rule, fitted on each fold's
training window and evaluated on its test window like every other model here.

**The rule is what was pre-registered; the 33.2% is not the number.** T19 measured 33.2%
for this rule over a different label set — one primary category per session, self-
transitions permitted. T-C's labels are category *changes* (D94), so the same rule scores
differently, and its value on these labels is measured rather than assumed. Fixing the
*number* would also have made the adoption rule impossible to apply: a paired bootstrap
needs the reference's prediction on each row, and a constant 33.2% has none.

**The challenger is `transition_table`** — the table that has existed in both languages
since T10 and has never been benchmarked. That is the whole point of T-C. It is the shipped
`TransitionTable`, fitted through `fit_transition_pairs`, not a research re-implementation.

**The rival is `bounce_back`** — predict the category you were on *before* the one you just
finished. It reads no counts at all and encodes one hypothesis: browsing alternates. A→B→A
is a real pattern (reading, then the thing you were reading about, then back), and if it
alone matches the fitted table, the table is not learning anything a two-line rule does not
already know. **It is not the bar** — promoting it after seeing the scores would be choosing
the rule from the result, which is the failure D91 and D94 exist to prevent. It is reported
beside the verdict and never inside it, exactly as `domain_base_rate` is in T-A.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from tise_research.eval.multiclass import MulticlassModel
from tise_research.features.transitions import CategoryTransition
from tise_research.models.transition import (
    DEFAULT_SMOOTHING,
    TransitionTable,
    fit_transition_pairs,
)

__all__ = [
    "BAR_MODEL",
    "BOUNCE_BACK_MODEL",
    "CHALLENGER_MODEL",
    "BounceBack",
    "GlobalMode",
    "TransitionRanker",
    "fit_bounce_back",
    "fit_global_mode",
    "fit_transition_ranker",
]

#: D94's floor, and the model the adoption interval is measured against.
BAR_MODEL = "global_mode"

#: The thing being tested: the table that ships and has never been scored.
CHALLENGER_MODEL = "transition_table"

#: Reported alongside, never as the bar. See the module docstring.
BOUNCE_BACK_MODEL = "bounce_back"


def _by_frequency(counts: dict[str, int]) -> tuple[str, ...]:
    """Categories most-common first, ties broken by name.

    The tie-break is not decoration. With few labels several categories genuinely tie, and
    without it top-1 would depend on dict insertion order — which is training-set order,
    which means the score would move when nothing about the model did.
    """
    return tuple(sorted(counts, key=lambda name: (-counts[name], name)))


@dataclass(frozen=True, slots=True)
class GlobalMode(MulticlassModel):
    """Always the most common next category in the training window."""

    name: str = BAR_MODEL
    order: tuple[str, ...] = ()

    def ranking(self, transition: CategoryTransition) -> tuple[str, ...]:
        return self.order


def fit_global_mode(transitions: Sequence[CategoryTransition]) -> GlobalMode:
    counts: dict[str, int] = {}
    for item in transitions:
        counts[item.to_category] = counts.get(item.to_category, 0) + 1
    return GlobalMode(order=_by_frequency(counts))


@dataclass(frozen=True, slots=True)
class TransitionRanker(MulticlassModel):
    """The shipped transition table, ranked.

    Ties inside a smoothed distribution are broken by name for the reason `_by_frequency`
    gives; `TransitionTable.most_likely` already does this and the ordering here matches it,
    so top-1 from either route is the same category.
    """

    table: TransitionTable
    name: str = CHALLENGER_MODEL
    #: Used when the table is empty and has no opinion about anything.
    fallback: tuple[str, ...] = field(default=())

    def ranking(self, transition: CategoryTransition) -> tuple[str, ...]:
        distribution = self.table.distribution(transition.from_category)
        if not distribution:
            return self.fallback
        return tuple(
            sorted(distribution, key=lambda name: (-distribution[name], name))
        )


def fit_transition_ranker(
    transitions: Sequence[CategoryTransition], *, smoothing: float = DEFAULT_SMOOTHING
) -> TransitionRanker:
    table = fit_transition_pairs(
        [(item.from_category, item.to_category) for item in transitions],
        smoothing=smoothing,
    )
    return TransitionRanker(table=table, fallback=fit_global_mode(transitions).order)


@dataclass(frozen=True, slots=True)
class BounceBack(MulticlassModel):
    """Predict the category before the one just finished; fall back to the global mode.

    The fallback matters more than it looks: at the very start of the corpus, and whenever
    the previous category is one the training window never saw, this model has nothing of
    its own to say. Falling back to the bar rather than guessing keeps the comparison a
    comparison — any gap it opens is a gap the bounce-back rule earned on rows where it
    actually applied.
    """

    order: tuple[str, ...] = ()
    name: str = BOUNCE_BACK_MODEL

    def ranking(self, transition: CategoryTransition) -> tuple[str, ...]:
        previous = transition.previous_category
        if previous is None or previous not in self.order:
            return self.order
        return (previous,) + tuple(name for name in self.order if name != previous)


def fit_bounce_back(transitions: Sequence[CategoryTransition]) -> BounceBack:
    return BounceBack(order=fit_global_mode(transitions).order)
