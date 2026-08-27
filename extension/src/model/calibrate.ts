/**
 * Platt scaling: turn the model's scores into probabilities that mean what they say.
 *
 * PARITY-CRITICAL: `research/tise_research/models/calibrate.py` is the mirror.
 *
 * A logistic regression already emits something in [0, 1], which is why calibration is
 * easy to skip. It is not the same thing as a probability: "0.8" is only a probability if,
 * across every occasion the model said 0.8, the thing happened about 80% of the time. A
 * model can have a respectable Brier score and still be systematically over-confident, and
 * abstention (`abstain.ts`) is meaningless until the number it thresholds is honest.
 *
 * **Platt, not isotonic.** Isotonic regression is the more flexible calibrator and the
 * wrong one here. It fits a free-form monotone step function, which needs a lot of data;
 * on the few hundred labels a real profile produces it would fit the calibration set's
 * noise and report it as confidence. Platt fits **two parameters**, which is about the
 * most this data can support.
 *
 * **It is a one-feature logistic regression, so it reuses the same optimiser.** The input
 * is the *logit* of the raw probability, which makes `a = 1, b = 0` exactly the identity.
 * One optimiser to keep in parity rather than two, and it is the one already measured
 * agreeing across languages to 2e-16.
 *
 * **The calibration set must be data the model did not train on.** Fitting Platt on the
 * model's own training rows learns memorisation rather than error. `train.ts` owns that
 * split; this module only sees numbers and cannot enforce it.
 */
import { type LogRegSpec, train } from "./logreg";

/** Bumped whenever the method or its fitting changes. Travels with every prediction. */
export const CALIBRATION_VERSION = "cal_1";
export const CALIBRATION_METHOD = "platt";

/**
 * Probabilities are clamped before the logarithm. A raw 0 or 1 has infinite logit, and a
 * single such row would otherwise dominate the fit or produce a NaN coefficient.
 */
const PROBABILITY_EPSILON = 1e-9;

/**
 * Two parameters on one column needs far fewer steps than the fourteen-feature model. The
 * budget is generous rather than tuned because the cost is negligible, and `gradientNorm`
 * reports whether it was enough (D62).
 */
export const CALIBRATION_SPEC: LogRegSpec = {
  iterations: 2000,
  l2: 0,
  chunkIterations: 200,
  stepScale: 1,
};

export interface Calibrator {
  /** Slope on the logit scale. Below 1 shrinks toward the base rate. */
  readonly a: number;
  readonly b: number;
  readonly method: string;
  readonly version: string;
  readonly nCalibration: number;
  readonly nPositive: number;
  readonly gradientNorm: number;
}

/** Log-odds, with the ends clamped. The inverse of the sigmoid the model applied. */
export function logit(probability: number): number {
  const clamped = Math.min(
    Math.max(probability, PROBABILITY_EPSILON),
    1 - PROBABILITY_EPSILON,
  );
  return Math.log(clamped / (1 - clamped));
}

/**
 * Leaves every probability alone.
 *
 * Deliberately **not** a neutral default that quietly does nothing: a prediction carrying
 * an identity calibrator is visibly uncalibrated, which is a different claim from a
 * calibrated one.
 */
export function identityCalibrator(): Calibrator {
  return {
    a: 1,
    b: 0,
    method: CALIBRATION_METHOD,
    version: CALIBRATION_VERSION,
    nCalibration: 0,
    nPositive: 0,
    gradientNorm: 0,
  };
}

export function isIdentity(calibrator: Calibrator): boolean {
  return calibrator.a === 1 && calibrator.b === 0;
}

/** Map one raw probability through the fitted calibrator. */
export function applyCalibration(calibrator: Calibrator, probability: number): number {
  const z = calibrator.a * logit(probability) + calibrator.b;
  const clamped = Math.min(Math.max(z, -40), 40);
  return 1 / (1 + Math.exp(-clamped));
}

/**
 * Fit on held-out predictions. Never on the rows the model was trained on.
 *
 * Returns the identity when there is nothing to learn from — no data, or one class only.
 * An all-positive calibration set contains no information about where the model is
 * over-confident, and inventing a slope from it would be worse than leaving the raw
 * numbers alone and saying so.
 */
export function fitPlatt(
  probabilities: readonly number[],
  outcomes: readonly boolean[],
  spec: LogRegSpec = CALIBRATION_SPEC,
): Calibrator {
  if (probabilities.length !== outcomes.length) {
    throw new Error(
      `${probabilities.length} probabilities but ${outcomes.length} outcomes; ` +
        "they must be aligned",
    );
  }
  const positives = outcomes.filter(Boolean).length;
  if (outcomes.length === 0 || positives === 0 || positives === outcomes.length) {
    return identityCalibrator();
  }

  // Platt's soft targets. Fitting to hard 0/1 on a small set drives the coefficients
  // toward separating it perfectly, which is exactly the overconfidence calibration
  // exists to remove. The same shape of fix as the smoothing in the transition table.
  const negatives = outcomes.length - positives;
  const high = (positives + 1) / (positives + 2);
  const low = 1 / (negatives + 2);

  const matrix = probabilities.map((probability) => [logit(probability)]);
  const targets = outcomes.map((outcome) => (outcome ? high : low));
  const state = train(matrix, targets, spec, 1);

  return {
    a: state.weights[0] as number,
    b: state.bias,
    method: CALIBRATION_METHOD,
    version: CALIBRATION_VERSION,
    nCalibration: outcomes.length,
    nPositive: positives,
    gradientNorm: state.gradientNorm,
  };
}
