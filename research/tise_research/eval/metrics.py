"""Scoring rules for probabilistic predictions.

Brier score and log loss are both **proper** scoring rules: each is minimised by
reporting your actual belief. A model cannot improve either by pushing probabilities
toward 0 and 1 to look confident. That property is why this project reports them and not
accuracy.

**Accuracy is not a headline metric here.** With a 70% base rate, always answering "yes"
scores 70% while having learned nothing at all — and the base rate for `return_24h` on
real browsing is around 70%.

Every function returns `None` for empty input rather than 0.0. Zero is a perfect Brier
score; an empty fold has no score. Conflating the two would put a fictional perfect
result into a published table.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

__all__ = [
    "LOG_LOSS_EPSILON",
    "base_rate",
    "brier_score",
    "log_loss",
    "skill_score",
]

#: Probabilities are clamped into [eps, 1-eps] before taking a logarithm. A hard 0/1
#: predictor that is wrong otherwise has infinite log loss. The clamp keeps the number
#: finite, but it is a floor rather than a measurement, and any report showing log loss
#: for a hard classifier has to say so.
LOG_LOSS_EPSILON = 1e-6


def _check(outcomes: Sequence[bool], probabilities: Sequence[float]) -> None:
    if len(outcomes) != len(probabilities):
        raise ValueError(
            f"length mismatch: {len(outcomes)} outcomes, {len(probabilities)} probabilities"
        )


def brier_score(
    outcomes: Sequence[bool], probabilities: Sequence[float]
) -> float | None:
    """Mean squared error of the probability. Lower is better; 0.25 is uninformative."""
    _check(outcomes, probabilities)
    if not outcomes:
        return None
    return sum(
        (probability - float(outcome)) ** 2
        for outcome, probability in zip(outcomes, probabilities, strict=True)
    ) / len(outcomes)


def log_loss(outcomes: Sequence[bool], probabilities: Sequence[float]) -> float | None:
    """Mean negative log likelihood. Lower is better; ln(2) ~ 0.693 is uninformative.

    Punishes confident mistakes far harder than Brier does, which is exactly what makes
    it worth reporting alongside: a model can have a respectable Brier score and still be
    dangerously overconfident on the cases it gets wrong.
    """
    _check(outcomes, probabilities)
    if not outcomes:
        return None
    total = 0.0
    for outcome, probability in zip(outcomes, probabilities, strict=True):
        clamped = min(max(probability, LOG_LOSS_EPSILON), 1.0 - LOG_LOSS_EPSILON)
        total -= math.log(clamped) if outcome else math.log(1.0 - clamped)
    return total / len(outcomes)


def base_rate(outcomes: Sequence[bool]) -> float | None:
    """Share of positives. The number every model has to beat before it is interesting."""
    if not outcomes:
        return None
    return sum(1 for outcome in outcomes if outcome) / len(outcomes)


def skill_score(score: float | None, reference: float | None) -> float | None:
    """Fractional improvement over a reference score. 0 means no better than reference.

    The honest headline when the base rate is high. "Brier 0.19" sounds respectable until
    you learn that simply reporting the base rate scores 0.21 — a skill score of 0.10,
    which is a much more truthful summary of what was gained.
    """
    if score is None or reference is None or reference == 0:
        return None
    return 1.0 - (score / reference)
