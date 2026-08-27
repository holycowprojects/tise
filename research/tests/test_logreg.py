"""The hand-written optimiser.

Two properties carry the weight here. **Convergence** is asserted from the gradient norm
rather than inferred from the iteration count, because an unconverged fit is not wrong in
any way a Brier score reveals — it is just quietly worse. And **chunked training equals
whole training**, asserted by interrupting at every possible point, because that is the
property that makes MV3 killing the worker survivable rather than merely tolerable.
"""

from __future__ import annotations

import math

import pytest
from tise_research.models.logreg import (
    DEFAULT_SPEC,
    LogRegSpec,
    initial_state,
    predict_proba,
    step_size,
    train,
    train_chunk,
)


def _curvature_bound(matrix: list[list[float]], spec: LogRegSpec) -> float:
    """The `L` that `step_size` inverts, restated here so the test does not reuse it."""
    n = len(matrix)
    mean_squared_norm = sum(1.0 + sum(v * v for v in row) for row in matrix) / n
    return mean_squared_norm / 4.0 + spec.l2 / n


#: A signal the optimiser must be able to find: column 0 decides the outcome, column 1 is
#: noise-free but irrelevant. Synthetic, and used here as a unit test rather than a
#: benchmark — SPEC.md permits the first and forbids the second.
MATRIX = [
    [-1.5, 0.4],
    [-1.0, -0.2],
    [-0.5, 0.9],
    [0.5, -0.9],
    [1.0, 0.2],
    [1.5, -0.4],
]
OUTCOMES = [False, False, False, True, True, True]


class TestConvergence:
    def test_the_gradient_norm_reaches_zero_rather_than_the_iteration_count(self) -> None:
        state = train(MATRIX, OUTCOMES)
        assert state.iterations_done == DEFAULT_SPEC.iterations
        assert state.gradient_norm < 1e-8

    def test_it_actually_learns_the_signal(self) -> None:
        state = train(MATRIX, OUTCOMES)
        for row, outcome in zip(MATRIX, OUTCOMES, strict=True):
            probability = predict_proba(state, row)
            assert (probability > 0.5) is outcome

    def test_the_l2_penalty_stops_separable_data_running_to_infinity(self) -> None:
        """Perfectly separable data has no finite maximum-likelihood solution."""
        unpenalised = train(MATRIX, OUTCOMES, spec=LogRegSpec(l2=0.0))
        penalised = train(MATRIX, OUTCOMES, spec=LogRegSpec(l2=10.0))
        assert abs(penalised.weights[0]) < abs(unpenalised.weights[0])

    def test_the_derived_step_is_below_the_divergence_threshold(self) -> None:
        """`2/L` is where gradient descent stops descending. `1/L` is half of it."""
        spec = LogRegSpec()
        assert 0.0 < step_size(MATRIX, spec) < 2.0 / _curvature_bound(MATRIX, spec)

    def test_pushing_past_the_bound_does_diverge(self) -> None:
        """The guarantee is only worth something if the thing it prevents is real.

        Without this the bound could be arithmetic nobody had ever checked did anything.
        """
        safe = train(MATRIX, OUTCOMES)
        reckless = train(MATRIX, OUTCOMES, spec=LogRegSpec(step_scale=400.0))
        assert safe.gradient_norm < 1e-8
        assert not math.isfinite(reckless.gradient_norm) or reckless.gradient_norm > 1.0

    def test_collinear_columns_do_not_break_it(self) -> None:
        """The case a hand-picked learning rate fails on, and the reason for the bound."""
        duplicated = [[value, value, value, value] for value, _ in MATRIX]
        state = train(duplicated, OUTCOMES)
        assert math.isfinite(state.bias)
        assert state.gradient_norm < 1e-6

    def test_the_bias_is_not_penalised(self) -> None:
        """Penalising it would drag the base rate toward 0.5 — a claim nobody made."""
        skewed = [[0.0], [0.0], [0.0], [0.0]]
        state = train(skewed, [True, True, True, False], spec=LogRegSpec(l2=10.0))
        # Every column is zero, so only the bias can move. It should find log(3/1).
        assert state.weights == (0.0,)
        assert predict_proba(state, [0.0]) == pytest.approx(0.75, abs=1e-6)


class TestResumability:
    def test_chunked_training_equals_one_call_exactly(self) -> None:
        whole = train(MATRIX, OUTCOMES)

        state = initial_state(len(MATRIX[0]))
        while state.iterations_done < DEFAULT_SPEC.iterations:
            state = train_chunk(state, MATRIX, OUTCOMES)

        assert state.weights == whole.weights
        assert state.bias == whole.bias
        assert state.iterations_done == whole.iterations_done

    @pytest.mark.parametrize("chunk", [1, 3, 7, 50, 999, 10_000])
    def test_the_chunk_size_never_changes_the_answer(self, chunk: int) -> None:
        """Interrupted at every plausible point, and after the end."""
        spec = LogRegSpec(chunk_iterations=chunk)
        whole = train(MATRIX, OUTCOMES)
        resumed = train(MATRIX, OUTCOMES, spec=spec)
        assert resumed.weights == whole.weights
        assert resumed.bias == whole.bias

    def test_calling_past_the_end_returns_the_same_state(self) -> None:
        """A caller that keeps going must not quietly train a different model."""
        finished = train(MATRIX, OUTCOMES)
        again = train_chunk(finished, MATRIX, OUTCOMES)
        assert again == finished

    def test_a_state_is_small_enough_to_be_worth_persisting(self) -> None:
        """It is written to IndexedDB after every chunk, so its size is a design fact."""
        state = train(MATRIX, OUTCOMES)
        assert len(state.weights) == len(MATRIX[0])


class TestEdges:
    def test_no_training_data_predicts_one_half_and_says_it_is_finished(self) -> None:
        """A new profile has none. Zero weights predict 0.5, which is the honest answer."""
        state = train([], [], n_columns=3)
        assert state.iterations_done == DEFAULT_SPEC.iterations
        assert predict_proba(state, [1.0, 2.0, 3.0]) == 0.5

    def test_misaligned_rows_and_outcomes_raise(self) -> None:
        with pytest.raises(ValueError, match="must be aligned"):
            train_chunk(initial_state(2), MATRIX, OUTCOMES[:-1])

    def test_a_row_of_the_wrong_width_raises_rather_than_being_padded(self) -> None:
        with pytest.raises(ValueError, match="columns"):
            predict_proba(initial_state(2), [1.0])

    def test_the_sigmoid_stays_finite_at_absurd_inputs(self) -> None:
        """The clamp is a guard against overflow, not a change to any real value."""
        state = initial_state(1)
        huge = train_chunk(state, [[1e6]], [True], spec=LogRegSpec(iterations=1))
        assert math.isfinite(huge.bias)
        assert 0.0 < predict_proba(huge, [1e6]) <= 1.0

    def test_initialisation_is_deterministic_and_carries_no_seed(self) -> None:
        assert initial_state(4).weights == (0.0, 0.0, 0.0, 0.0)
        assert train(MATRIX, OUTCOMES).weights == train(MATRIX, OUTCOMES).weights

    @pytest.mark.parametrize(
        "spec",
        [
            {"iterations": -1},
            {"chunk_iterations": 0},
            {"l2": -0.5},
        ],
    )
    def test_a_nonsensical_spec_is_refused_at_construction(self, spec: dict) -> None:
        with pytest.raises(ValueError):
            LogRegSpec(**spec)
