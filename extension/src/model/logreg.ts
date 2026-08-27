/**
 * Logistic regression, written out rather than imported.
 *
 * PARITY-CRITICAL: `research/tise_research/models/logreg.py` is the mirror, and it is the
 * reason the optimiser is hand-written on both sides. scikit-learn solves this with
 * LBFGS, which is a line search over a quasi-Newton approximation, and nothing here is
 * going to reproduce its iterates to 1e-9. A model whose coefficients cannot be
 * reproduced in the extension is a model the extension does not ship, and the whole point
 * of Tise is that training happens on the user's own machine over the user's own
 * browsing.
 *
 * So the optimiser is **full-batch gradient descent with a fixed iteration count**. It
 * converges more slowly than LBFGS, and that is the price of being reproducible.
 * Everything it does is addition, multiplication and `exp`, in a fixed order, from a
 * fixed starting point of all zeros — there is no random initialisation and no seed
 * anywhere, so two runs are identical and so are two languages.
 *
 * **The step size is derived from the data, not declared.** A hand-picked learning rate
 * is a constant that works on the data it was picked on: gradient descent diverges once
 * the step exceeds `2/L`, and `L` depends on how collinear the columns are. Two of the
 * eighteen columns are close to collinear already (`prep.ts` says which), so "0.5 worked
 * on my browsing" is not a claim worth shipping to someone else's. Instead the step is
 * `1/L` for an upper bound on `L` computed from the design matrix itself, which cannot
 * diverge for any input.
 *
 * **Training is chunked because MV3 will kill it.** `trainChunk` advances a fixed number
 * of iterations and returns a state small enough to persist. Running the chunks back to
 * back must produce exactly what `train` produces in one call — that is not an
 * implementation detail, it is the property that makes interruption survivable.
 */

/**
 * `exp` overflows for large negative inputs on the way to a probability. Clamping the
 * linear term keeps the sigmoid finite without changing any value that matters: at 40 the
 * sigmoid is already 1 to within 4e-18, far below anything the parity tolerance can see.
 */
const LINEAR_CLAMP = 40;

export interface LogRegSpec {
  /**
   * Total gradient steps. Fixed rather than "until converged" so two runs on the same
   * data take the same path and produce the same answer.
   */
  readonly iterations: number;
  /**
   * L2 penalty in pseudo-observations, applied to the weights and never to the bias.
   * Penalising the bias would drag the model's base rate toward 0.5, which is a statement
   * about the data nobody made.
   */
  readonly l2: number;
  /**
   * Iterations per resumable chunk. Affects only how the work is divided, never the
   * result — `train` and chunked training agree exactly.
   */
  readonly chunkIterations: number;
  /** Multiplies the derived step. 1 is the provably safe choice. */
  readonly stepScale: number;
}

export const DEFAULT_SPEC: LogRegSpec = {
  iterations: 4000,
  l2: 1,
  chunkIterations: 50,
  stepScale: 1,
};

/**
 * A label. `boolean` for a real outcome; a number in [0, 1] for a *soft* target, which is
 * what Platt scaling needs — see `model/calibrate.ts`. The gradient `p - y` is identical
 * either way, so one optimiser serves both and there is only one thing to keep in parity.
 */
export type Target = boolean | number;

function targetValue(target: Target): number {
  return typeof target === "boolean" ? (target ? 1 : 0) : target;
}

/** A model mid-training or finished. Small enough to persist after every chunk. */
export interface LogRegState {
  readonly weights: readonly number[];
  readonly bias: number;
  readonly iterationsDone: number;
  /**
   * L2 norm of the gradient at the current point. Falls toward zero as the fit
   * converges; carried so a caller can see whether it did.
   */
  readonly gradientNorm: number;
}

/** All zeros. Deterministic by construction, which is why no seed appears anywhere. */
export function initialState(nColumns: number): LogRegState {
  return {
    weights: new Array<number>(nColumns).fill(0),
    bias: 0,
    iterationsDone: 0,
    gradientNorm: Number.POSITIVE_INFINITY,
  };
}

function sigmoid(z: number): number {
  const clamped = Math.min(Math.max(z, -LINEAR_CLAMP), LINEAR_CLAMP);
  return 1 / (1 + Math.exp(-clamped));
}

/** Probability for one already-preprocessed row. */
export function predictProba(state: LogRegState, row: readonly number[]): number {
  if (row.length !== state.weights.length) {
    throw new Error(`row has ${row.length} columns, model has ${state.weights.length}`);
  }
  let total = state.bias;
  for (let index = 0; index < row.length; index += 1) {
    total += (row[index] as number) * (state.weights[index] as number);
  }
  return sigmoid(total);
}

/**
 * `1/L` for an upper bound on the objective's curvature. Cannot diverge, by design.
 *
 * The Hessian of the mean log loss is `(1/n) Xᵀ D X` with `D = p(1-p)`, which is at most
 * a quarter. Its largest eigenvalue is therefore no more than a quarter of the mean
 * squared row norm, and the L2 term adds `l2/n`. The bias column contributes the `+1`.
 *
 * Descending with a step of `1/L` guarantees the objective decreases every iteration for
 * **any** design matrix — including one whose columns are perfectly collinear, which is
 * exactly where a hand-picked learning rate blows up. The bound is loose when the columns
 * are well conditioned, so this trades iterations for a guarantee.
 */
export function stepSize(matrix: readonly (readonly number[])[], spec: LogRegSpec): number {
  const n = matrix.length;
  if (n === 0) return 0;
  let total = 0;
  for (const row of matrix) {
    let squared = 1; // the bias column
    for (const value of row) squared += value * value;
    total += squared;
  }
  const curvature = total / (4 * n) + spec.l2 / n;
  if (curvature <= 0) {
    // Every column is zero and there is no penalty: the objective is linear in the bias
    // alone, so any finite step is safe. One is as defensible as any other.
    return spec.stepScale;
  }
  return spec.stepScale / curvature;
}

export function gradientNorm(weightGradient: readonly number[], biasGradient: number): number {
  let total = biasGradient * biasGradient;
  for (const value of weightGradient) total += value * value;
  return Math.sqrt(total);
}

/**
 * Mean-log-loss gradient with the L2 term. Row order is part of the contract.
 *
 * Floating-point addition is not associative, so the mirror has to accumulate in this
 * same order to land on the same bits. It iterates rows outer, columns inner.
 */
function gradient(
  state: LogRegState,
  matrix: readonly (readonly number[])[],
  outcomes: readonly Target[],
  spec: LogRegSpec,
): { weightGradient: number[]; biasGradient: number } {
  const n = matrix.length;
  const weightGradient = new Array<number>(state.weights.length).fill(0);
  let biasGradient = 0;

  for (let rowIndex = 0; rowIndex < n; rowIndex += 1) {
    const row = matrix[rowIndex] as readonly number[];
    const error = predictProba(state, row) - targetValue(outcomes[rowIndex] as Target);
    biasGradient += error;
    for (let index = 0; index < row.length; index += 1) {
      weightGradient[index] = (weightGradient[index] as number) + error * (row[index] as number);
    }
  }

  for (let index = 0; index < weightGradient.length; index += 1) {
    weightGradient[index] =
      ((weightGradient[index] as number) + spec.l2 * (state.weights[index] as number)) / n;
  }
  return { weightGradient, biasGradient: biasGradient / n };
}

/**
 * Advance at most `spec.chunkIterations` steps and return a persistable state.
 *
 * Stops at `spec.iterations` regardless of how many chunks are requested, so a caller
 * that keeps calling after training finished gets the same state back rather than quietly
 * training a different model.
 */
export function trainChunk(
  state: LogRegState,
  matrix: readonly (readonly number[])[],
  outcomes: readonly Target[],
  spec: LogRegSpec = DEFAULT_SPEC,
): LogRegState {
  if (matrix.length === 0) {
    // No training data is not an error — a new profile has none — but it is also not a
    // model. Zero weights predict 0.5 for everything, which is the honest answer.
    return {
      weights: state.weights,
      bias: state.bias,
      iterationsDone: spec.iterations,
      gradientNorm: 0,
    };
  }
  if (matrix.length !== outcomes.length) {
    throw new Error(
      `${matrix.length} rows but ${outcomes.length} outcomes; they must be aligned`,
    );
  }

  const remaining = spec.iterations - state.iterationsDone;
  if (remaining <= 0) return state;

  const steps = Math.min(spec.chunkIterations, remaining);
  const weights = [...state.weights];
  let bias = state.bias;
  let done = state.iterationsDone;
  let norm = state.gradientNorm;
  // A pure function of the matrix, so every chunk derives the same value and chunked
  // training cannot drift from training in one call.
  const step = stepSize(matrix, spec);

  for (let iteration = 0; iteration < steps; iteration += 1) {
    const current: LogRegState = {
      weights,
      bias,
      iterationsDone: done,
      gradientNorm: norm,
    };
    const { weightGradient, biasGradient } = gradient(current, matrix, outcomes, spec);
    norm = gradientNorm(weightGradient, biasGradient);
    for (let index = 0; index < weights.length; index += 1) {
      weights[index] = (weights[index] as number) - step * (weightGradient[index] as number);
    }
    bias -= step * biasGradient;
    done += 1;
  }

  return { weights, bias, iterationsDone: done, gradientNorm: norm };
}

/** Run every chunk back to back. Identical to chunked training, by construction. */
export function train(
  matrix: readonly (readonly number[])[],
  outcomes: readonly Target[],
  spec: LogRegSpec = DEFAULT_SPEC,
  nColumns?: number,
): LogRegState {
  const columns = nColumns ?? (matrix.length > 0 ? (matrix[0] as readonly number[]).length : 0);
  let state = initialState(columns);
  while (state.iterationsDone < spec.iterations) {
    const advanced = trainChunk(state, matrix, outcomes, spec);
    if (advanced.iterationsDone === state.iterationsDone) break;
    state = advanced;
  }
  return state;
}
