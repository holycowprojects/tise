"""Logistic regression, written out rather than imported.

`extension/src/model/logreg.ts` is the mirror, and this is the reason the optimiser is
hand-written: scikit-learn solves this with LBFGS, which is a line search over a
quasi-Newton approximation, and no browser implementation is going to reproduce its
iterates to 1e-9. A model whose coefficients cannot be reproduced in the extension is a
model the extension does not ship, and the whole point of Tise is that training happens
on the user's own machine over the user's own browsing.

So the optimiser is **full-batch gradient descent with a fixed iteration count**. It
converges more slowly than LBFGS, and that is the price of being reproducible. Everything
it does is addition, multiplication and `exp`, in a fixed order, from a fixed starting
point of all zeros — there is no random initialisation and no seed anywhere, so two runs
are identical and so are two languages.

**The step size is derived from the data, not declared.** A hand-picked learning rate is
a constant that works on the data it was picked on: gradient descent diverges once the
step exceeds `2/L`, and `L` depends on how collinear the columns are. Two of the eighteen
columns are close to collinear already (`prep.py` says which), so "0.5 worked on my
browsing" is not a claim worth shipping to someone else's. Instead the step is `1/L` for
an upper bound on `L` computed from the design matrix itself, which cannot diverge for
any input. It is a smaller step than hand-tuning would choose, and it costs iterations —
the honest trade, since the alternative fails silently on a profile nobody tested.

**Convergence is measured, not assumed.** A fixed iteration count can stop early without
saying so, and an unconverged model is not wrong in any way a Brier score reveals — it is
just quietly worse. So the fitted state carries the gradient norm it stopped at, and the
tests assert it is small rather than trusting the iteration count to have been enough.

**Training is chunked because MV3 will kill it.** `train_chunk` advances a fixed number
of iterations and returns a state small enough to persist. Running the chunks back to
back must produce exactly what `train` produces in one call — that is not an
implementation detail, it is the property that makes interruption survivable, and
`test_logreg.py` asserts it by interrupting at every possible point.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

#: A label. `bool` for a real outcome; a float in [0, 1] for a *soft* target, which is
#: what Platt scaling needs — see `models/calibrate.py`. The gradient `p - y` is identical
#: either way, so one optimiser serves both and there is only one thing to keep in parity.
Target = bool | float

__all__ = [
    "DEFAULT_SPEC",
    "Target",
    "LogRegSpec",
    "LogRegState",
    "gradient_norm",
    "initial_state",
    "predict_proba",
    "step_size",
    "train",
    "train_chunk",
]

#: `exp` overflows for large negative inputs on the way to a probability. Clamping the
#: linear term keeps the sigmoid finite without changing any value that matters: at 40 the
#: sigmoid is already 1 to within 4e-18, far below anything the parity tolerance can see.
LINEAR_CLAMP = 40.0


@dataclass(frozen=True, slots=True)
class LogRegSpec:
    """Every number that decides what the fitted model is.

    All four travel with the model, because a coefficient vector without the spec that
    produced it is not reproducible.
    """

    #: Total gradient steps. Fixed rather than "until converged" so two runs on the same
    #: data take the same path and produce the same answer. 4000 reaches a gradient norm
    #: below 1e-8 on the hardest case in the suite — deliberately separable synthetic
    #: data, where the weights want to run to infinity and only L2 holds them back. Real
    #: browsing is not separable and converges sooner; the fitted state carries the norm
    #: it actually reached, so nobody has to take that on trust.
    iterations: int = 4000
    #: L2 penalty in pseudo-observations, applied to the weights and never to the bias.
    #: Penalising the bias would drag the model's base rate toward 0.5, which is a
    #: statement about the data nobody made.
    l2: float = 1.0
    #: Iterations per resumable chunk. Affects only how the work is divided, never the
    #: result — `train` and chunked training agree exactly.
    chunk_iterations: int = 50

    #: Multiplies the derived step. 1.0 is the provably safe choice; the field exists so
    #: a test can push the optimiser past `2/L` and show that it does diverge, which is
    #: the only way to demonstrate the bound is doing anything.
    step_scale: float = 1.0

    def __post_init__(self) -> None:
        if self.iterations < 0:
            raise ValueError("iterations cannot be negative")
        if self.chunk_iterations < 1:
            raise ValueError("chunk_iterations must be at least 1")
        if self.l2 < 0:
            raise ValueError("l2 cannot be negative")


DEFAULT_SPEC = LogRegSpec()


@dataclass(frozen=True, slots=True)
class LogRegState:
    """A model mid-training or finished. Small enough to persist after every chunk."""

    weights: tuple[float, ...]
    bias: float
    iterations_done: int
    #: L2 norm of the gradient at the current point. Falls toward zero as the fit
    #: converges; carried so a caller can see whether it did.
    gradient_norm: float

    @property
    def n_columns(self) -> int:
        return len(self.weights)


def initial_state(n_columns: int) -> LogRegState:
    """All zeros. Deterministic by construction, which is why no seed appears anywhere."""
    return LogRegState(
        weights=tuple(0.0 for _ in range(n_columns)),
        bias=0.0,
        iterations_done=0,
        gradient_norm=math.inf,
    )


def _sigmoid(z: float) -> float:
    clamped = min(max(z, -LINEAR_CLAMP), LINEAR_CLAMP)
    return 1.0 / (1.0 + math.exp(-clamped))


def predict_proba(state: LogRegState, row: Sequence[float]) -> float:
    """Probability for one already-preprocessed row."""
    if len(row) != state.n_columns:
        raise ValueError(f"row has {len(row)} columns, model has {state.n_columns}")
    total = state.bias
    for value, weight in zip(row, state.weights, strict=True):
        total += value * weight
    return _sigmoid(total)


def _gradient(
    state: LogRegState,
    matrix: Sequence[Sequence[float]],
    outcomes: Sequence[Target],
    spec: LogRegSpec,
) -> tuple[list[float], float]:
    """Mean-log-loss gradient with the L2 term. Row order is part of the contract.

    Floating-point addition is not associative, so the mirror has to accumulate in this
    same order to land on the same bits. It iterates rows outer, columns inner.
    """
    n = len(matrix)
    weight_gradient = [0.0 for _ in range(state.n_columns)]
    bias_gradient = 0.0

    for row, outcome in zip(matrix, outcomes, strict=True):
        # `float(outcome)` rather than `1.0 if outcome else 0.0`: a bool converts the same
        # way, and a soft target in [0, 1] survives instead of being rounded up to 1.
        error = predict_proba(state, row) - float(outcome)
        bias_gradient += error
        for index, value in enumerate(row):
            weight_gradient[index] += error * value

    for index in range(state.n_columns):
        weight_gradient[index] = (
            weight_gradient[index] + spec.l2 * state.weights[index]
        ) / n
    return weight_gradient, bias_gradient / n


def step_size(matrix: Sequence[Sequence[float]], spec: LogRegSpec) -> float:
    """`1/L` for an upper bound on the objective's curvature. Cannot diverge, by design.

    The Hessian of the mean log loss is `(1/n) Xᵀ D X` with `D = p(1-p)`, which is at most
    a quarter. Its largest eigenvalue is therefore no more than a quarter of the mean
    squared row norm, and the L2 term adds `l2/n`. The bias column contributes the `+1`.

    Descending with a step of `1/L` guarantees the objective decreases every iteration for
    **any** design matrix — including one whose columns are perfectly collinear, which is
    exactly where a hand-picked learning rate blows up. The bound is loose when the
    columns are well conditioned, so this trades iterations for a guarantee.
    """
    n = len(matrix)
    if n == 0:
        return 0.0
    total = 0.0
    for row in matrix:
        squared = 1.0  # the bias column
        for value in row:
            squared += value * value
        total += squared
    curvature = total / (4.0 * n) + spec.l2 / n
    if curvature <= 0.0:
        # Every column is zero and there is no penalty: the objective is linear in the
        # bias alone, so any finite step is safe. One is as defensible as any other.
        return spec.step_scale
    return spec.step_scale / curvature


def gradient_norm(weight_gradient: Sequence[float], bias_gradient: float) -> float:
    total = bias_gradient * bias_gradient
    for value in weight_gradient:
        total += value * value
    return math.sqrt(total)


def train_chunk(
    state: LogRegState,
    matrix: Sequence[Sequence[float]],
    outcomes: Sequence[Target],
    *,
    spec: LogRegSpec = DEFAULT_SPEC,
) -> LogRegState:
    """Advance at most `spec.chunk_iterations` steps and return a persistable state.

    Stops at `spec.iterations` regardless of how many chunks are requested, so a caller
    that keeps calling after training finished gets the same state back rather than
    quietly training a different model.
    """
    if not matrix:
        # No training data is not an error — a new profile has none — but it is also not
        # a model. Zero weights predict 0.5 for everything, which is the honest answer.
        return LogRegState(
            weights=state.weights,
            bias=state.bias,
            iterations_done=spec.iterations,
            gradient_norm=0.0,
        )
    if len(matrix) != len(outcomes):
        raise ValueError(
            f"{len(matrix)} rows but {len(outcomes)} outcomes; they must be aligned"
        )

    remaining = spec.iterations - state.iterations_done
    if remaining <= 0:
        return state

    steps = min(spec.chunk_iterations, remaining)
    weights = list(state.weights)
    bias = state.bias
    done = state.iterations_done
    norm = state.gradient_norm
    # A pure function of the matrix, so every chunk derives the same value and chunked
    # training cannot drift from training in one call.
    step = step_size(matrix, spec)

    for _ in range(steps):
        current = LogRegState(
            weights=tuple(weights),
            bias=bias,
            iterations_done=done,
            gradient_norm=norm,
        )
        weight_gradient, bias_gradient = _gradient(current, matrix, outcomes, spec)
        norm = gradient_norm(weight_gradient, bias_gradient)
        for index in range(len(weights)):
            weights[index] -= step * weight_gradient[index]
        bias -= step * bias_gradient
        done += 1

    return LogRegState(
        weights=tuple(weights),
        bias=bias,
        iterations_done=done,
        gradient_norm=norm,
    )


def train(
    matrix: Sequence[Sequence[float]],
    outcomes: Sequence[Target],
    *,
    spec: LogRegSpec = DEFAULT_SPEC,
    n_columns: int | None = None,
) -> LogRegState:
    """Run every chunk back to back. Identical to chunked training, by construction."""
    columns = n_columns if n_columns is not None else (len(matrix[0]) if matrix else 0)
    state = initial_state(columns)
    while state.iterations_done < spec.iterations:
        advanced = train_chunk(state, matrix, outcomes, spec=spec)
        if advanced.iterations_done == state.iterations_done:
            break
        state = advanced
    return state
