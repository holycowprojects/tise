"""Deciding when not to answer. **Retired as a gate (D88); kept as a measurement.**

Nothing in the shipped path calls `should_answer` any more. D70 measured that no
confidence threshold certified the 90% target on any fold — certifying a margin that thin
needed >12,800 answered rows against calibration slices of 61-133 — so the policy reported
`target_met: False` and the extension withheld every prediction, permanently and by design.
D88 retired that rule and replaced it with *show everything, always with its denominator*;
`extension/src/model/nextCategory.ts` is the replacement, and the only floor that remains is
on evidence rather than on confidence.

This module survives because D88 also kept the accuracy-versus-coverage curve as a
**published result**. Read every mention of "showing" and "answering" below as describing
that curve, not the UI.

`extension/src/model/abstain.ts` is the mirror.

The original argument, kept because it is still why the curve is worth publishing:
abstention is a headline capability of this project, not a fallback. A forecaster that
says "I don't know" on the third of cases it would have got wrong is more useful than one
that answers everything at the same average accuracy — and it is far more useful than one
that answers everything and is silently wrong a third of the time.

**The threshold comes from a curve, never from intuition.** "0.7 feels confident" is a
number nobody measured. What is measured here is the trade the threshold actually makes:
raise it and accuracy on the answered cases goes up while coverage goes down. The policy
picks a point on that curve, and both halves of the point are reported — a threshold
quoted without its coverage is half a result.

**Confidence is distance from the coin flip, not the probability.** A prediction of 0.05
is as confident as one of 0.95; both say the outcome is nearly settled. `max(p, 1 - p)`
puts confidence in [0.5, 1] where 0.5 is "no idea".

**The curve is computed on validation data, and the threshold applies to future data.**
Choosing the threshold on the same predictions it will be scored on reports the best point
on a sample rather than a decision rule, which is the same leak as fitting a scaler on the
test set. `eval/backtest.py` owns that split.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

__all__ = [
    "DEFAULT_CONFIDENCE_Z",
    "DEFAULT_TARGET_ACCURACY",
    "AbstentionPolicy",
    "CoveragePoint",
    "accuracy_coverage_curve",
    "confidence",
    "select_threshold",
    "wilson_lower_bound",
]

#: The accuracy the answered cases must reach. **Declared, not tuned** — the same status as
#: the 30-minute session timeout (D17): a policy choice stated in advance so that whether
#: it is reachable becomes a finding rather than a knob. A base rate near 70% means
#: answering everything already scores about 0.70, so a target below that would be met by
#: abstaining from nothing and would measure nothing.
DEFAULT_TARGET_ACCURACY = 0.90

#: One-sided 95% normal quantile. The threshold must clear the target on the **lower
#: confidence bound** of its accuracy, not on the point estimate.
#:
#: This is not a tuning knob and it was not chosen by trying values. Selecting the lowest
#: threshold whose *observed* accuracy clears a target is optimistically biased twice over:
#: it takes an argmin over fifty noisy estimates, and on a calibration slice of ~100 rows
#: the standard error on an accuracy near 90% is about 3 points — so a threshold measured
#: at exactly the target is below it roughly half the time. Requiring a lower bound prices
#: that sampling error in directly. `0.0` recovers the point-estimate rule exactly, which
#: is how the two are compared.
DEFAULT_CONFIDENCE_Z = 1.645

#: Candidate thresholds, from "answer everything" upward. 0.5 is the floor because
#: confidence cannot be lower than a coin flip.
DEFAULT_THRESHOLDS: tuple[float, ...] = tuple(
    0.50 + 0.01 * step for step in range(0, 50)
)


def confidence(probability: float) -> float:
    """Distance from the coin flip, in [0.5, 1]. 0.05 and 0.95 are equally confident."""
    return max(probability, 1.0 - probability)


def wilson_lower_bound(successes: int, total: int, *, z: float = DEFAULT_CONFIDENCE_Z) -> float:
    """Lower end of the Wilson score interval for a binomial proportion.

    Preferred to the textbook normal approximation because that one misbehaves exactly
    where this is used — proportions near 1 with modest samples, where it can produce a
    bound above 1 or below 0. Wilson stays inside [0, 1] and stays sensible at 20 rows.

    `z = 0` returns the plain observed proportion, so the stricter rule and the naive one
    differ by a single parameter and can be compared on identical folds.
    """
    if total <= 0:
        return 0.0
    proportion = successes / total
    if z <= 0.0:
        return proportion
    z2 = z * z
    denominator = 1.0 + z2 / total
    centre = proportion + z2 / (2.0 * total)
    margin = z * math.sqrt(
        proportion * (1.0 - proportion) / total + z2 / (4.0 * total * total)
    )
    return max(0.0, (centre - margin) / denominator)


@dataclass(frozen=True, slots=True)
class CoveragePoint:
    """What one threshold would have done."""

    threshold: float
    #: Share of cases answered rather than abstained on.
    coverage: float
    answered: int
    #: Accuracy on the answered cases only. `None` when the threshold answers nothing.
    accuracy: float | None
    #: Accuracy on the cases abstained from, had they been answered. Reported because a
    #: threshold that abstains from cases it would have got right is throwing away value.
    abstained_accuracy: float | None


def _correct(outcome: bool, probability: float) -> bool:
    """A probability above 0.5 predicts the positive class. 0.5 exactly predicts negative.

    The tie has to break somewhere and it breaks toward the negative class, which is the
    minority here — so an exactly-0.5 prediction cannot inflate accuracy by riding the
    base rate.
    """
    return (probability > 0.5) == outcome


def accuracy_coverage_curve(
    outcomes: Sequence[bool],
    probabilities: Sequence[float],
    *,
    thresholds: Sequence[float] = DEFAULT_THRESHOLDS,
) -> list[CoveragePoint]:
    """Accuracy and coverage at each candidate threshold."""
    if len(outcomes) != len(probabilities):
        raise ValueError(
            f"{len(outcomes)} outcomes but {len(probabilities)} probabilities"
        )
    total = len(outcomes)
    curve: list[CoveragePoint] = []
    for threshold in thresholds:
        answered: list[bool] = []
        abstained: list[bool] = []
        for outcome, probability in zip(outcomes, probabilities, strict=True):
            bucket = answered if confidence(probability) >= threshold else abstained
            bucket.append(_correct(outcome, probability))
        curve.append(
            CoveragePoint(
                threshold=threshold,
                coverage=len(answered) / total if total else 0.0,
                answered=len(answered),
                accuracy=(sum(answered) / len(answered)) if answered else None,
                abstained_accuracy=(
                    sum(abstained) / len(abstained) if abstained else None
                ),
            )
        )
    return curve


@dataclass(frozen=True, slots=True)
class AbstentionPolicy:
    """A threshold and the evidence for it. Never one without the other."""

    threshold: float
    target_accuracy: float
    #: Accuracy and coverage measured on the validation set at this threshold.
    accuracy: float
    #: Lower confidence bound on `accuracy` at the selection `z`. This, not `accuracy`, is
    #: what had to clear the target.
    accuracy_lower_bound: float
    coverage: float
    n_validation: int
    #: The `z` the selection used. 0 means the naive point-estimate rule.
    confidence_z: float
    #: False when no threshold reached the target. The policy still carries a threshold —
    #: the highest one tried — and the caller is expected to treat it as "answer nothing".
    target_met: bool

    @property
    def answers_anything(self) -> bool:
        return self.target_met and self.coverage > 0.0


def select_threshold(
    outcomes: Sequence[bool],
    probabilities: Sequence[float],
    *,
    target_accuracy: float = DEFAULT_TARGET_ACCURACY,
    thresholds: Sequence[float] = DEFAULT_THRESHOLDS,
    min_answered: int = 20,
    confidence_z: float = DEFAULT_CONFIDENCE_Z,
) -> AbstentionPolicy | None:
    """The **lowest** threshold whose answered cases reach the target accuracy.

    Lowest, not best: the point is to answer as much as possible while keeping the promise,
    so among thresholds that meet the target the one with the most coverage wins. Picking
    the threshold with the highest accuracy instead would abstain from almost everything
    and report a wonderful number about four predictions.

    `min_answered` stops a threshold qualifying on a handful of cases — 3 for 3 is 100%
    accuracy and no evidence. `None` when there is no data at all; a policy with
    `target_met=False` when the target is simply unreachable, which is a finding and not
    an error.
    """
    if not outcomes:
        return None

    curve = accuracy_coverage_curve(outcomes, probabilities, thresholds=thresholds)
    for point in curve:
        if point.accuracy is None or point.answered < min_answered:
            continue
        correct = round(point.accuracy * point.answered)
        bound = wilson_lower_bound(correct, point.answered, z=confidence_z)
        if bound >= target_accuracy:
            return AbstentionPolicy(
                threshold=point.threshold,
                target_accuracy=target_accuracy,
                accuracy=point.accuracy,
                accuracy_lower_bound=bound,
                coverage=point.coverage,
                n_validation=len(outcomes),
                confidence_z=confidence_z,
                target_met=True,
            )

    # Nothing reached it. Report the strictest point tried, marked as not meeting the
    # target. Reported as unmet rather than quietly lowering the bar; no caller gates
    # on it now, and the number is what the model panel shows.
    last = curve[-1]
    accuracy = last.accuracy if last.accuracy is not None else 0.0
    return AbstentionPolicy(
        threshold=last.threshold,
        target_accuracy=target_accuracy,
        accuracy=accuracy,
        accuracy_lower_bound=wilson_lower_bound(
            round(accuracy * last.answered), last.answered, z=confidence_z
        ),
        coverage=last.coverage,
        n_validation=len(outcomes),
        confidence_z=confidence_z,
        target_met=False,
    )
