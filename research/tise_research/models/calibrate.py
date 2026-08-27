"""Platt scaling: turn a model's scores into probabilities that mean what they say.

`extension/src/model/calibrate.ts` is the mirror.

A logistic regression already emits something in [0, 1], which is why calibration is easy
to skip. It is not the same thing as a probability: "0.8" is only a probability if, across
every occasion the model said 0.8, the thing happened about 80% of the time. A model can
have a respectable Brier score and still be systematically over- or under-confident, and
abstention (`eval/abstain.py`) is meaningless until the number it thresholds is honest.

**Platt, not isotonic.** Isotonic regression is the more flexible calibrator and the wrong
one here. It fits a free-form monotone step function, which needs a lot of data; on the
few hundred labels a real profile produces it would fit the calibration set's noise and
report it as confidence. Platt fits **two parameters**, which is about the most this data
can support. Isotonic becomes the right answer at roughly ten times the labels, and that
is a reason to revisit it then rather than a reason to reach for it now.

**It is a one-feature logistic regression, so it reuses the same optimiser.** The input is
the *logit* of the raw probability, not the probability, which makes `a = 1, b = 0` exactly
the identity — a calibrator that has learned "you were already right" is visibly the
identity rather than some arbitrary pair. Reusing `logreg.train` means there is one
optimiser in this project to keep in parity, not two, and it is the one already measured
agreeing across languages to 2e-16.

**Soft targets, from Platt's original paper.** Fitting to hard 0/1 on a small calibration
set drives the coefficients toward separating it perfectly, which is exactly the
overconfidence calibration exists to remove. The targets are pulled in from the ends by
one pseudo-count each — the same shape of fix as the smoothing in `baselines.py` and the
transition table, for the same reason.

**The calibration set must be data the model did not train on.** Fitting Platt on the
model's own training rows learns the model's memorisation rather than its error, and
produces a calibrator that is confidently wrong in the direction of the training set. This
module cannot enforce that — it only sees numbers — so `eval/backtest.py` owns the split
and `test_calibrate.py` asserts the shape of it.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from tise_research.models.logreg import LogRegSpec, predict_proba, train

__all__ = [
    "CALIBRATION_METHOD",
    "CALIBRATION_VERSION",
    "Calibrator",
    "apply_calibration",
    "fit_platt",
    "identity_calibrator",
    "logit",
]

#: Travels with every calibrated prediction. A probability is only reproducible if you
#: know what turned it into one, so this is bumped whenever the method or its fitting
#: changes — the same contract `FEATURE_SET` carries for the feature vector.
CALIBRATION_VERSION = "cal_1"
CALIBRATION_METHOD = "platt"

#: Probabilities are clamped before the logarithm. A raw 0 or 1 has infinite logit, and a
#: single such row would otherwise dominate the fit or produce a NaN coefficient.
PROBABILITY_EPSILON = 1e-9

#: Platt scaling is two parameters on one column; it needs far fewer steps than the
#: fourteen-feature model, and the budget is kept generous rather than tuned because the
#: cost is negligible and `gradient_norm` reports whether it was enough.
CALIBRATION_SPEC = LogRegSpec(iterations=2000, l2=0.0, chunk_iterations=200)


def logit(probability: float) -> float:
    """Log-odds, with the ends clamped. The inverse of the sigmoid the model applied."""
    clamped = min(max(probability, PROBABILITY_EPSILON), 1.0 - PROBABILITY_EPSILON)
    return math.log(clamped / (1.0 - clamped))


@dataclass(frozen=True, slots=True)
class Calibrator:
    """A fitted mapping from raw score to honest probability.

    `a` and `b` are the slope and intercept on the logit scale. `a = 1, b = 0` is the
    identity. `a < 1` means the raw model was over-confident and is being pulled toward
    the base rate; `a > 1` means it was under-confident.

    The counts travel with it because a calibrator fitted on 30 rows and one fitted on 300
    are different objects, and nothing downstream can tell them apart from `a` and `b`.
    """

    a: float
    b: float
    method: str = CALIBRATION_METHOD
    version: str = CALIBRATION_VERSION
    n_calibration: int = 0
    n_positive: int = 0
    #: Gradient norm the fit stopped at. Small means converged; carried so nobody has to
    #: take the iteration count on trust (D62).
    gradient_norm: float = 0.0

    @property
    def is_identity(self) -> bool:
        return self.a == 1.0 and self.b == 0.0


def identity_calibrator() -> Calibrator:
    """Leaves every probability alone.

    Used when there is nothing to calibrate on. It is deliberately **not** a neutral
    default that quietly does nothing: a prediction carrying an identity calibrator is
    visibly uncalibrated, which is a different claim from a calibrated one.
    """
    return Calibrator(a=1.0, b=0.0)


def apply_calibration(calibrator: Calibrator, probability: float) -> float:
    """Map one raw probability through the fitted calibrator."""
    z = calibrator.a * logit(probability) + calibrator.b
    clamped = min(max(z, -40.0), 40.0)
    return 1.0 / (1.0 + math.exp(-clamped))


def _soft_targets(outcomes: Sequence[bool]) -> tuple[float, float]:
    """Platt's targets: the ends pulled in by one pseudo-count each.

    With hard 0/1 on a small set the fit runs toward perfect separation and reports the
    result as confidence, which is the thing calibration is supposed to remove.
    """
    positives = sum(1 for outcome in outcomes if outcome)
    negatives = len(outcomes) - positives
    high = (positives + 1.0) / (positives + 2.0)
    low = 1.0 / (negatives + 2.0)
    return high, low


def fit_platt(
    probabilities: Sequence[float],
    outcomes: Sequence[bool],
    *,
    spec: LogRegSpec = CALIBRATION_SPEC,
) -> Calibrator:
    """Fit on held-out predictions. Never on the rows the model was trained on.

    Returns the identity when there is nothing to learn from — no data, or one class only.
    A calibration set that is all positives contains no information about where the model
    is over-confident, and inventing a slope from it would be worse than leaving the raw
    numbers alone and saying so.
    """
    if len(probabilities) != len(outcomes):
        raise ValueError(
            f"{len(probabilities)} probabilities but {len(outcomes)} outcomes; "
            "they must be aligned"
        )
    positives = sum(1 for outcome in outcomes if outcome)
    if not outcomes or positives == 0 or positives == len(outcomes):
        return identity_calibrator()

    high, low = _soft_targets(outcomes)
    matrix = [[logit(probability)] for probability in probabilities]
    targets = [high if outcome else low for outcome in outcomes]

    state = train(matrix, targets, spec=spec, n_columns=1)
    return Calibrator(
        a=state.weights[0],
        b=state.bias,
        n_calibration=len(outcomes),
        n_positive=positives,
        gradient_norm=state.gradient_norm,
    )


def calibrated_probability(
    calibrator: Calibrator, state, row: Sequence[float]
) -> float:
    """Score a row and calibrate it in one step, so the two cannot be separated by accident."""
    return apply_calibration(calibrator, predict_proba(state, row))
