"""Is a probability worth its face value? Reliability curves and calibration error.

`extension/src/model/calibrate.ts` mirrors the scoring side; this module is the reporting
side and stays in Python.

Brier score already rewards calibration, but it mixes it with discrimination: a model can
improve its Brier by separating the classes better while staying just as over-confident,
and the single number will not say which happened. These functions separate the two.

**Binning is a choice, and it changes the answer.** Expected calibration error is a
weighted average over bins, so a different bin count gives a different ECE for the same
predictions — it is not a property of the model alone. The bin count is therefore declared
and travels with the number. Equal-width bins are used rather than equal-count because a
reliability curve is read against the diagonal, and equal-count bins put the x-axis on a
scale nobody can read against it.

**Every bin's population is reported.** With a few hundred labels and a base rate near
70%, most predictions crowd into the top bins and the low ones can hold three points. An
ECE that averages a bin of three against a bin of two hundred is arithmetic, not a
measurement, and the only defence is printing the counts next to it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

__all__ = [
    "DEFAULT_BINS",
    "ReliabilityBin",
    "expected_calibration_error",
    "maximum_calibration_error",
    "reliability_curve",
]

#: Ten equal-width bins. Declared, because ECE is not comparable across bin counts.
DEFAULT_BINS = 10


def _bin_index(probability: float, bins: int) -> int:
    """Which bin a probability falls in. Bins are half-open; the top one is closed.

    Written as a comparison against each edge rather than `int(probability * bins)`,
    because the arithmetic version is wrong at exactly the values that matter most.
    `0.3 * 10` is 2.9999999999999996, so `int()` puts a prediction of 0.3 in [0.2, 0.3)
    — and predictions cluster on round numbers, so the error is not rare. It shifts whole
    populations one bin left and quietly tilts the reliability curve.

    Comparing against `(candidate + 1) / bins` is exact: it is the same double the bin
    edge is reported as, so a value sitting on an edge lands in the bin that edge opens.
    """
    for candidate in range(bins):
        if probability < (candidate + 1) / bins:
            return candidate
    return bins - 1


@dataclass(frozen=True, slots=True)
class ReliabilityBin:
    """One point on the reliability curve, with the population behind it."""

    low: float
    high: float
    count: int
    #: Mean predicted probability inside the bin. `None` when the bin is empty.
    mean_predicted: float | None
    #: Share of positives actually observed. `None` when the bin is empty.
    observed_rate: float | None

    @property
    def gap(self) -> float | None:
        """How far this bin sits from the diagonal. Positive means over-confident."""
        if self.mean_predicted is None or self.observed_rate is None:
            return None
        return self.mean_predicted - self.observed_rate


def reliability_curve(
    outcomes: Sequence[bool],
    probabilities: Sequence[float],
    *,
    bins: int = DEFAULT_BINS,
) -> list[ReliabilityBin]:
    """Group predictions into equal-width bins and compare predicted against observed.

    Empty bins are kept rather than dropped. A gap in the curve is information — it says
    the model never made a prediction in that range — and silently closing it would draw a
    line through territory nothing was ever measured in.
    """
    if len(outcomes) != len(probabilities):
        raise ValueError(
            f"{len(outcomes)} outcomes but {len(probabilities)} probabilities"
        )
    if bins < 1:
        raise ValueError("a reliability curve needs at least one bin")

    width = 1.0 / bins
    grouped: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    for probability, outcome in zip(probabilities, outcomes, strict=True):
        grouped[_bin_index(probability, bins)].append((probability, outcome))

    curve: list[ReliabilityBin] = []
    for index, members in enumerate(grouped):
        low, high = index * width, (index + 1) * width
        if not members:
            curve.append(ReliabilityBin(low, high, 0, None, None))
            continue
        mean_predicted = sum(p for p, _ in members) / len(members)
        observed = sum(1 for _, outcome in members if outcome) / len(members)
        curve.append(
            ReliabilityBin(low, high, len(members), mean_predicted, observed)
        )
    return curve


def expected_calibration_error(
    outcomes: Sequence[bool],
    probabilities: Sequence[float],
    *,
    bins: int = DEFAULT_BINS,
) -> float | None:
    """Population-weighted mean distance from the diagonal. Lower is better; 0 is perfect.

    `None` for empty input rather than 0.0, following `metrics.py`: zero is a perfect
    score and no data is not a score at all.
    """
    if not outcomes:
        return None
    curve = reliability_curve(outcomes, probabilities, bins=bins)
    total = len(outcomes)
    error = 0.0
    for entry in curve:
        gap = entry.gap
        if gap is None:
            continue
        error += (entry.count / total) * abs(gap)
    return error


def maximum_calibration_error(
    outcomes: Sequence[bool],
    probabilities: Sequence[float],
    *,
    bins: int = DEFAULT_BINS,
    min_count: int = 1,
) -> float | None:
    """The worst bin, ignoring bins below `min_count`.

    Reported alongside ECE because an average hides the failure that matters: a model can
    have a fine ECE while being badly wrong in exactly the range where a user would act on
    it. `min_count` exists so the answer is not decided by a bin holding two points.
    """
    if not outcomes:
        return None
    gaps = [
        abs(entry.gap)
        for entry in reliability_curve(outcomes, probabilities, bins=bins)
        if entry.gap is not None and entry.count >= min_count
    ]
    return max(gaps) if gaps else None
