"""How much of a score difference is real, and how much is the size of the test set.

**Why this exists.** D60 reported that `logreg_fs2` clears D28's bar on Edge, 0.1119
against 0.1254, while winning 2 of 5 folds. D78 and D79 then re-ran the same corpus twice
and reported the model moving to 0.2096, 0.1124, 0.2219 — differences quoted to four
decimals on folds holding around fifty test rows each. None of those reports could say
whether any of it was distinguishable from noise, because nothing here could produce an
interval. That is the gap this module closes, and the first thing it does is put a bound on
claims this project has already published.

**The comparison is paired.** Both models score the *same* rows, so the quantity with a
meaningful interval is the per-row difference in squared error, not two separately
estimated Brier scores. Comparing two independent intervals and checking whether they
overlap is a weaker and commonly wrong test: two overlapping intervals can still describe
a difference that reliably excludes zero.

**Sign convention:** `reference - challenger`, so **positive means the challenger is
better** — it has less error. It is spelled out on every function because getting it
backwards inverts every conclusion and nothing else would catch it.

**Two units, both reported.** Resampling rows treats every (category, session) label as
independent, which they are not: the same handful of categories generate all of them, and
sessions within a category share whatever makes that category predictable. Resampling
*subjects* respects that and is the honest bound, at the cost of very few clusters. The
row interval is the optimistic one and the subject interval is the defensible one; a claim
that survives only the first is a claim about this corpus rather than about the model.

**The cluster does not have to be the category, and until D94 it always was.** Width
shrinks roughly with one over the square root of the cluster count, and every interval this
project published resampled 9-12 clusters, because the subject was always the category.
That is why nothing here could ever resolve a small effect — the sample size that mattered
was never the row count. The unit is therefore an argument now: pass whatever grouping the
target's dependence actually runs along, and pass `unit=` so the printed interval says
which. An interval that resampled sessions while reporting `subjects, n=11` would be a
right number with a wrong label, which is the defect D86 and D87 are both about.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass

__all__ = [
    "BOOTSTRAP_SEED",
    "DEFAULT_LEVEL",
    "DEFAULT_RESAMPLES",
    "Interval",
    "brier_difference",
    "brier_difference_interval",
    "rows_to_exclude_zero",
    "fold_win_probability",
]

#: Declared, committed, and never tuned. The optimiser deliberately has no seed (D54) —
#: it has to be reproducible in a browser. This is research-only and randomness *is* the
#: method here, so a seed is the honest way to make a published interval reproducible.
#: `test_intervals.py` asserts the bounds barely move across other seeds; if that ever
#: stops holding, the resample count is too low and the seed is doing real work.
BOOTSTRAP_SEED = 20260828

#: Enough that the third decimal of a percentile bound is stable on corpora this size.
DEFAULT_RESAMPLES = 10_000

DEFAULT_LEVEL = 0.95


@dataclass(frozen=True, slots=True)
class Interval:
    """A point estimate with a percentile bootstrap interval around it."""

    point: float
    low: float
    high: float
    level: float
    resamples: int
    #: What was resampled. `"row"` treats labels as independent; anything else names the
    #: cluster they were grouped by — `"subject"` (the category) until D94, `"session"`
    #: from T-A onward.
    unit: str
    #: How many things could be resampled. For `subject` this is often single digits, and
    #: an interval built from four clusters is a different object from one built from 250.
    units: int

    @property
    def excludes_zero(self) -> bool:
        """Whether the interval supports a directional claim at all."""
        return self.low > 0.0 or self.high < 0.0

    def describe(self) -> str:
        verdict = "excludes zero" if self.excludes_zero else "**includes zero**"
        return (
            f"{self.point:+.4f} [{self.low:+.4f}, {self.high:+.4f}] "
            f"({self.level:.0%}, {self.unit}s, n={self.units}) — {verdict}"
        )


def _squared_errors(
    outcomes: Sequence[bool], probabilities: Sequence[float]
) -> list[float]:
    if len(outcomes) != len(probabilities):
        raise ValueError(
            f"length mismatch: {len(outcomes)} outcomes, {len(probabilities)} probabilities"
        )
    return [
        (probability - float(outcome)) ** 2
        for outcome, probability in zip(outcomes, probabilities, strict=True)
    ]


def brier_difference(
    outcomes: Sequence[bool],
    challenger: Sequence[float],
    reference: Sequence[float],
) -> float | None:
    """`reference - challenger` Brier. **Positive means the challenger is better.**"""
    if not outcomes:
        return None
    challenger_errors = _squared_errors(outcomes, challenger)
    reference_errors = _squared_errors(outcomes, reference)
    return (sum(reference_errors) - sum(challenger_errors)) / len(outcomes)


def _percentile(values: list[float], fraction: float) -> float:
    """Linear-interpolated percentile of an already-sorted list."""
    if len(values) == 1:
        return values[0]
    position = fraction * (len(values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    weight = position - lower
    return values[lower] * (1.0 - weight) + values[upper] * weight


def brier_difference_interval(
    outcomes: Sequence[bool],
    challenger: Sequence[float],
    reference: Sequence[float],
    *,
    subjects: Sequence[str] | None = None,
    unit: str = "subject",
    resamples: int = DEFAULT_RESAMPLES,
    level: float = DEFAULT_LEVEL,
    seed: int = BOOTSTRAP_SEED,
) -> Interval | None:
    """Paired percentile bootstrap on `reference - challenger` Brier.

    **Positive means the challenger is better.**

    Pass `subjects` to resample whole clusters instead of individual rows. That is the
    conservative unit and the one a claim about *the model* has to survive; resampling
    rows assumes labels are independent, and labels drawn from six categories are not.

    `unit` names what a cluster **is**, and only labels the result — it changes no
    arithmetic. It exists because the cluster stopped always being the category (D94), and
    a printed interval that names the wrong unit is unfalsifiable by the reader.

    Returns None for empty input rather than a zero-width interval at zero, which would
    read as a confident finding of no difference.
    """
    point = brier_difference(outcomes, challenger, reference)
    if point is None:
        return None

    challenger_errors = _squared_errors(outcomes, challenger)
    reference_errors = _squared_errors(outcomes, reference)
    paired = [r - c for c, r in zip(challenger_errors, reference_errors, strict=True)]

    rng = random.Random(seed)
    if subjects is None:
        groups = [[index] for index in range(len(paired))]
        unit_name = "row"
    else:
        if len(subjects) != len(paired):
            raise ValueError(
                f"length mismatch: {len(subjects)} subjects, {len(paired)} rows"
            )
        clustered: dict[str, list[int]] = {}
        for index, subject in enumerate(subjects):
            clustered.setdefault(subject, []).append(index)
        groups = list(clustered.values())
        unit_name = unit

    draws: list[float] = []
    count = len(groups)
    for _ in range(resamples):
        total = 0.0
        rows = 0
        for _ in range(count):
            for index in groups[rng.randrange(count)]:
                total += paired[index]
                rows += 1
        # A resample cannot be empty: every group holds at least one row.
        draws.append(total / rows)

    draws.sort()
    tail = (1.0 - level) / 2.0
    return Interval(
        point=point,
        low=_percentile(draws, tail),
        high=_percentile(draws, 1.0 - tail),
        level=level,
        resamples=resamples,
        unit=unit_name,
        units=count,
    )


def rows_to_exclude_zero(interval: Interval, observed_rows: int) -> int | None:
    """Roughly how many test rows it would take for this difference to clear zero.

    A bootstrap half-width shrinks about as fast as one over the square root of the sample,
    so the rows needed scale with `(half_width / |point|)²`. Returns None when the interval
    already excludes zero, or when the point estimate is zero and no amount of data helps.

    **This assumes the point estimate survives collecting that data, which is exactly what
    is not known.** It is a statement about how far the current evidence is from being
    decisive, not a promise that more browsing would settle it the same way — the true
    difference may be zero, in which case no sample size ever excludes zero. Reported for
    the same reason T12 reported the >12,800 rows abstention needed: "not established" is
    much more useful next to how far off establishing it would be.
    """
    if interval.excludes_zero or interval.point == 0.0:
        return None
    half_width = (interval.high - interval.low) / 2.0
    return math.ceil(observed_rows * (half_width / abs(interval.point)) ** 2)


def fold_win_probability(wins: int, folds: int) -> float | None:
    """P(a coin-flip model wins at least `wins` of `folds`). Exact, not bootstrapped.

    "Wins 2 of 5 folds" reads like a weak result and "wins 4 of 5" like a strong one, but
    neither means anything until compared against what chance produces. A model no better
    than the baseline wins each fold with probability one half, so this is a binomial tail
    and needs no simulation.

    A large value means the fold count is consistent with chance. It is not a hypothesis
    test to pass or fail — with five folds the smallest attainable value is 0.031, so this
    can never be small on a five-fold backtest, which is itself the point worth reporting.
    """
    if folds <= 0 or wins < 0 or wins > folds:
        return None
    return sum(math.comb(folds, k) for k in range(wins, folds + 1)) / (2.0**folds)
