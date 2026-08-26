"""Baselines for `return_24h`.

Five models, none of which learns anything interesting. That is the point: with a base
rate near 70% and `video` at 90%, any headline number is meaningless without these
underneath it. The majority-class baseline is mandatory in every report (D24).

**Every baseline is fitted on the training window and then frozen.** Nothing updates
while the test window is scored. That makes "same as last time" weaker than a true online
version would be — and the honest move is to say so in the report rather than quietly
build the stronger one and let the reader assume the simpler thing.

Two shared behaviours worth knowing:

* **Cold start is normal, not exceptional.** A new user has no history, and the first
  backtest fold has almost none. Unseen categories fall back to the global base rate;
  an empty training window predicts 0.5.
* **Sparse categories are smoothed toward the global rate.** D26 found nine of fifteen
  categories with fewer than ten labels. Unsmoothed, a category with two positives claims
  100% and is confidently, uselessly wrong.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from tise_research.features.labels import Label

__all__ = [
    "ALL_BASELINES",
    "Baseline",
    "fit_category_base_rate",
    "fit_global_base_rate",
    "fit_majority_class",
    "fit_same_as_last",
    "fit_time_of_day",
]

#: Used when the training window is empty. Maximally uninformative, which is honest.
NO_INFORMATION = 0.5


class Baseline(ABC):
    """A fitted, frozen predictor.

    `predict` receives the `Label` because it needs the subject and `window_end`. It must
    never read `outcome` — `test_baselines.py` asserts this by flipping the outcome of
    the row being predicted and checking the prediction does not move.
    """

    name: str

    @abstractmethod
    def predict(self, label: Label) -> float:
        """Probability that this label's outcome is positive."""


def _base_rate(labels: Sequence[Label]) -> float:
    if not labels:
        return NO_INFORMATION
    return sum(1 for label in labels if label.outcome) / len(labels)


def _smoothed_rate(
    positives: int, total: int, *, prior: float, smoothing: float
) -> float:
    """Rate pulled toward `prior` by `smoothing` pseudo-observations."""
    if total + smoothing == 0:
        return prior
    return (positives + smoothing * prior) / (total + smoothing)


@dataclass(frozen=True, slots=True)
class _Constant(Baseline):
    name: str
    value: float

    def predict(self, label: Label) -> float:  # noqa: ARG002 - signature is the contract
        return self.value


def fit_majority_class(labels: Sequence[Label]) -> Baseline:
    """Always predicts the training majority, as a hard 0 or 1.

    Mandatory in every report (D24). It is also the clearest demonstration of why log
    loss needs a clamp: the first time a hard classifier is wrong, its true log loss is
    infinite.
    """
    if not labels:
        return _Constant("majority_class", NO_INFORMATION)
    return _Constant("majority_class", 1.0 if _base_rate(labels) > 0.5 else 0.0)


def fit_global_base_rate(labels: Sequence[Label]) -> Baseline:
    """Always predicts the overall training base rate. The reference for skill score."""
    return _Constant("global_base_rate", _base_rate(labels))


@dataclass(frozen=True, slots=True)
class _PerKeyRate(Baseline):
    name: str
    rates: dict[str, float]
    fallback: float
    key: Callable[[Label], str] = field(compare=False)

    def predict(self, label: Label) -> float:
        return self.rates.get(self.key(label), self.fallback)


def _fit_per_key(
    labels: Sequence[Label],
    *,
    name: str,
    key: Callable[[Label], str],
    smoothing: float,
) -> Baseline:
    prior = _base_rate(labels)
    if not labels:
        return _Constant(name, NO_INFORMATION)

    totals: dict[str, int] = defaultdict(int)
    positives: dict[str, int] = defaultdict(int)
    for label in labels:
        bucket = key(label)
        totals[bucket] += 1
        if label.outcome:
            positives[bucket] += 1

    rates = {
        bucket: _smoothed_rate(
            positives[bucket], totals[bucket], prior=prior, smoothing=smoothing
        )
        for bucket in totals
    }
    return _PerKeyRate(name=name, rates=rates, fallback=prior, key=key)


def fit_category_base_rate(
    labels: Sequence[Label], *, smoothing: float = 5.0
) -> Baseline:
    """Base rate per category, smoothed toward the global rate.

    The strongest of the baselines on this data, because category is by far the most
    informative single fact about a `return_24h` label — `video` returns 90% of the time
    and `travel` almost never.
    """
    return _fit_per_key(
        labels,
        name="category_base_rate",
        key=lambda label: label.subject,
        smoothing=smoothing,
    )


def fit_time_of_day(
    labels: Sequence[Label], *, bucket_hours: int = 6, smoothing: float = 5.0
) -> Baseline:
    """Base rate per time-of-day bucket of `window_end`."""
    return _fit_per_key(
        labels,
        name=f"time_of_day_{bucket_hours}h",
        key=lambda label: str(label.window_end.hour // bucket_hours),
        smoothing=smoothing,
    )


@dataclass(frozen=True, slots=True)
class _SameAsLast(Baseline):
    name: str
    last_outcome: dict[str, bool]
    fallback: float
    alpha: float

    def predict(self, label: Label) -> float:
        previous = self.last_outcome.get(label.subject)
        if previous is None:
            return self.fallback
        return 1.0 - self.alpha if previous else self.alpha


def fit_same_as_last(labels: Sequence[Label], *, alpha: float = 0.05) -> Baseline:
    """Repeats the last training outcome for that category.

    `alpha` is declared smoothing, not a fudge: a hard repeat has infinite log loss the
    first time it is wrong, and burying that inside the metric's clamp would let the
    number look like a measurement.

    Frozen after fitting, so it repeats the last outcome *in training* for the whole test
    window rather than updating as it goes. Weaker than an online version, and reported
    as such.
    """
    if not labels:
        return _Constant("same_as_last", NO_INFORMATION)

    last_outcome: dict[str, bool] = {}
    for label in sorted(labels, key=lambda item: item.window_end):
        last_outcome[label.subject] = label.outcome

    return _SameAsLast(
        name="same_as_last",
        last_outcome=last_outcome,
        fallback=_base_rate(labels),
        alpha=alpha,
    )


#: Every baseline, by name. A report that omits any of these is incomplete.
ALL_BASELINES: dict[str, Callable[[Sequence[Label]], Baseline]] = {
    "majority_class": fit_majority_class,
    "global_base_rate": fit_global_base_rate,
    "category_base_rate": fit_category_base_rate,
    "same_as_last": fit_same_as_last,
    "time_of_day": fit_time_of_day,
}
