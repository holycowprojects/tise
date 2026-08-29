"""`fast_logreg` must compute the same function as `logreg`, or it may not produce a number.

This is the parity contract applied a third time. It binds TypeScript to Python for the
features, Python to itself for chunked-versus-whole training, and here the vectorised
trainer to the hand-written one that actually ships.

**The direction of authority matters.** `logreg.py` is the definition — it is mirrored in
the browser and reproducible to 1e-9 across languages. If these disagree, `fast_logreg` is
wrong, and the fix is never to relax the tolerance until it passes.

Bit-identity is not the claim and is not achievable: `logreg` accumulates the gradient row
by row on purpose, and NumPy sums via BLAS in a different order. These tests measure how far
apart that leaves them after all 4,000 iterations rather than assuming it is negligible.
"""

from __future__ import annotations

import math

import pytest
from tise_research.models.fast_logreg import train_fast
from tise_research.models.logreg import (
    DEFAULT_SPEC,
    LogRegSpec,
    predict_proba,
    step_size,
    train,
)

#: The project's parity tolerance, used for TypeScript/Python feature agreement.
TOLERANCE = 1e-9


def _separable(n: int = 120, columns: int = 6) -> tuple[list[list[float]], list[bool]]:
    """Deliberately hard: nearly separable, so the weights want to run away and only L2
    holds them back. `logreg.py` names this as its worst convergence case."""
    matrix, outcomes = [], []
    for index in range(n):
        sign = 1.0 if index % 2 else -1.0
        row = [sign * (1.0 + 0.1 * ((index * (column + 3)) % 7)) for column in range(columns)]
        matrix.append(row)
        outcomes.append(sign > 0)
    return matrix, outcomes


def _realistic(n: int = 400, columns: int = 20) -> tuple[list[list[float]], list[bool]]:
    """Standardised columns of mixed scale with a weak signal — the shape `prep.py`
    produces, including a column that never varies and two that are near-collinear."""
    matrix, outcomes = [], []
    for index in range(n):
        base = math.sin(index * 0.7)
        row = []
        for column in range(columns):
            if column == 0:
                row.append(0.0)  # a column with no variation
            elif column == 1:
                row.append(base)
            elif column == 2:
                row.append(base + 1e-6)  # near-collinear with column 1
            else:
                row.append(math.cos(index * 0.31 * column) * (1.0 + column % 4))
        matrix.append(row)
        outcomes.append(math.sin(index * 0.7 + 0.4) > 0.0)
    return matrix, outcomes


CASES = {"separable": _separable(), "realistic": _realistic()}


class TestTheStepIsTheSame:
    @pytest.mark.parametrize("name", sorted(CASES))
    def test_step_size_agrees(self, name: str) -> None:
        """If the step differs, every later iterate differs and nothing else matters."""
        import numpy as np
        from tise_research.models.fast_logreg import _step_size

        matrix, _ = CASES[name]
        slow = step_size(matrix, DEFAULT_SPEC)
        fast = _step_size(np.asarray(matrix, dtype=np.float64), DEFAULT_SPEC)
        assert fast == pytest.approx(slow, rel=1e-12, abs=0.0)


class TestSameFunction:
    @pytest.mark.parametrize("name", sorted(CASES))
    def test_weights_agree_to_the_parity_tolerance(self, name: str) -> None:
        matrix, outcomes = CASES[name]
        slow = train(matrix, outcomes, spec=DEFAULT_SPEC)
        fast = train_fast(matrix, outcomes, spec=DEFAULT_SPEC)

        assert len(fast.weights) == len(slow.weights)
        worst = max(
            abs(a - b) for a, b in zip(slow.weights, fast.weights, strict=True)
        )
        assert worst < TOLERANCE, f"worst weight disagreement {worst:.3e}"
        assert abs(slow.bias - fast.bias) < TOLERANCE

    @pytest.mark.parametrize("name", sorted(CASES))
    def test_probabilities_agree(self, name: str) -> None:
        """What actually reaches a Brier score. Weights could differ harmlessly; these
        cannot, because every published number is computed from them."""
        matrix, outcomes = CASES[name]
        slow = train(matrix, outcomes, spec=DEFAULT_SPEC)
        fast = train_fast(matrix, outcomes, spec=DEFAULT_SPEC)
        worst = max(
            abs(predict_proba(slow, row) - predict_proba(fast, row)) for row in matrix
        )
        assert worst < TOLERANCE, f"worst probability disagreement {worst:.3e}"

    @pytest.mark.parametrize("name", sorted(CASES))
    def test_iterations_and_norm_are_carried(self, name: str) -> None:
        matrix, outcomes = CASES[name]
        slow = train(matrix, outcomes, spec=DEFAULT_SPEC)
        fast = train_fast(matrix, outcomes, spec=DEFAULT_SPEC)
        assert fast.iterations_done == slow.iterations_done == DEFAULT_SPEC.iterations
        # The norm is a diagnostic the reports print; it has to mean the same thing.
        assert fast.gradient_norm == pytest.approx(slow.gradient_norm, rel=1e-6)


class TestEdgesMatch:
    def test_no_rows_produces_the_same_non_model(self) -> None:
        slow = train([], [], n_columns=4)
        fast = train_fast([], [], n_columns=4)
        assert fast.weights == slow.weights == (0.0, 0.0, 0.0, 0.0)
        assert fast.bias == slow.bias == 0.0
        assert fast.gradient_norm == slow.gradient_norm == 0.0

    def test_misaligned_input_raises_in_both(self) -> None:
        with pytest.raises(ValueError, match="aligned"):
            train_fast([[1.0], [2.0]], [True])

    def test_zero_iterations_leaves_the_starting_point(self) -> None:
        spec = LogRegSpec(iterations=0)
        matrix, outcomes = CASES["realistic"]
        fast = train_fast(matrix, outcomes, spec=spec)
        assert fast.weights == tuple(0.0 for _ in fast.weights)
        assert fast.bias == 0.0

    @pytest.mark.parametrize("l2", [0.0, 5.0])
    def test_the_l2_term_agrees(self, l2: float) -> None:
        """L2 enters the weight gradient and the step size; a mismatch in either would
        show up only as a slightly different model, never as an error."""
        spec = LogRegSpec(l2=l2)
        matrix, outcomes = CASES["realistic"]
        slow = train(matrix, outcomes, spec=spec)
        fast = train_fast(matrix, outcomes, spec=spec)
        worst = max(abs(a - b) for a, b in zip(slow.weights, fast.weights, strict=True))
        assert worst < TOLERANCE


class TestItIsActuallyFaster:
    def test_fast_is_not_slower(self) -> None:
        """The only reason this module exists. If it is not faster it should be deleted
        rather than kept as a second thing to keep in parity."""
        import time

        matrix, outcomes = _realistic(n=600, columns=20)

        start = time.perf_counter()
        train(matrix, outcomes, spec=DEFAULT_SPEC)
        slow_seconds = time.perf_counter() - start

        start = time.perf_counter()
        train_fast(matrix, outcomes, spec=DEFAULT_SPEC)
        fast_seconds = time.perf_counter() - start

        assert fast_seconds < slow_seconds, (
            f"vectorised {fast_seconds:.2f}s vs hand-written {slow_seconds:.2f}s"
        )
