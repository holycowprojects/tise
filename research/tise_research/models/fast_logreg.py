"""The same logistic regression as `logreg.py`, vectorised. Research tier only.

**This module ships nothing and changes nothing about the model.** `logreg.py` stays the
definition: hand-written full-batch gradient descent, mirrored in
`extension/src/model/logreg.ts`, reproducible to 1e-9 across two languages because it must
run in a browser. Nothing here is imported by the extension, and nothing here may be used to
justify changing what the extension does.

**Why it exists.** D99 replicates `visit_engaged` across ~1,400 real people, one fit per
person per fold per model. The pure-Python trainer costs 4,000 full-batch passes over a
matrix of a few thousand rows, which measured at over 600 seconds for 25 people — hundreds
of hours for the corpus. The choice was a fast trainer or a sample small enough to throw away
the reason the corpus is worth having.

**The claim this module has to earn.** It computes the *same function*, not a similar one.
Every constant comes from `logreg.py` — the step size, the L2 term, the clamp, the iteration
count, the all-zeros start — and `test_fast_logreg.py` fits both on real feature rows and
compares weights, bias and probabilities. If that test fails, this module is wrong and the
published number is the slow trainer's.

**Where it is not bit-identical, and why that is expected.** `logreg.py` accumulates the
gradient row by row, and says so: floating-point addition is not associative, and the
TypeScript mirror matches that order deliberately. NumPy sums via BLAS in a different order,
so the two disagree in the last bits of each step. Gradient descent near a minimum is a
contraction, so those perturbations are damped rather than amplified — but that is an
argument, and the test measures the difference instead of trusting it.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

from tise_research.models.logreg import (
    DEFAULT_SPEC,
    LINEAR_CLAMP,
    LogRegSpec,
    LogRegState,
    Target,
)

__all__ = ["train_fast"]


def _step_size(matrix: np.ndarray, spec: LogRegSpec) -> float:
    """`logreg.step_size`, vectorised. The `+ 1.0` is the bias column, as there."""
    n = matrix.shape[0]
    if n == 0:
        return 0.0
    total = float(np.sum(matrix * matrix) + n)
    curvature = total / (4.0 * n) + spec.l2 / n
    if curvature <= 0.0:
        return spec.step_scale
    return spec.step_scale / curvature


def train_fast(
    matrix: Sequence[Sequence[float]],
    outcomes: Sequence[Target],
    *,
    spec: LogRegSpec = DEFAULT_SPEC,
    n_columns: int | None = None,
) -> LogRegState:
    """Fit and return a `LogRegState` the rest of the project cannot tell apart.

    Returns the same dataclass `logreg.train` does, carrying the gradient norm it stopped
    at, so `predict_proba` and every report read it unchanged.
    """
    columns = n_columns if n_columns is not None else (len(matrix[0]) if matrix else 0)

    if not matrix:
        # `logreg.train_chunk`'s empty case: not an error, and not a model either.
        return LogRegState(
            weights=tuple(0.0 for _ in range(columns)),
            bias=0.0,
            iterations_done=spec.iterations,
            gradient_norm=0.0,
        )
    if len(matrix) != len(outcomes):
        raise ValueError(
            f"{len(matrix)} rows but {len(outcomes)} outcomes; they must be aligned"
        )

    x = np.asarray(matrix, dtype=np.float64)
    y = np.asarray([float(outcome) for outcome in outcomes], dtype=np.float64)
    n = x.shape[0]

    weights = np.zeros(columns, dtype=np.float64)
    bias = 0.0
    step = _step_size(x, spec)
    norm = math.inf

    for _ in range(spec.iterations):
        # Clamped exactly as `logreg._sigmoid` does, for the same overflow reason.
        linear = np.clip(x @ weights + bias, -LINEAR_CLAMP, LINEAR_CLAMP)
        error = 1.0 / (1.0 + np.exp(-linear)) - y

        weight_gradient = (x.T @ error + spec.l2 * weights) / n
        bias_gradient = float(np.sum(error)) / n

        norm = math.sqrt(
            float(np.dot(weight_gradient, weight_gradient)) + bias_gradient**2
        )
        weights = weights - step * weight_gradient
        bias -= step * bias_gradient

    return LogRegState(
        weights=tuple(float(value) for value in weights),
        bias=float(bias),
        iterations_done=spec.iterations,
        gradient_norm=norm,
    )
