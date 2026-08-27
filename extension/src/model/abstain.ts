/**
 * Deciding when not to answer.
 *
 * PARITY-CRITICAL: `research/tise_research/eval/abstain.py` is the mirror.
 *
 * Abstention is a headline capability of this project, not a fallback. A forecaster that
 * says "I don't know" on the third of cases it would have got wrong is more useful than
 * one that answers everything at the same average accuracy — and far more useful than one
 * that answers everything and is silently wrong a third of the time.
 *
 * **The threshold comes from a curve, never from intuition.** "0.7 feels confident" is a
 * number nobody measured. What is measured here is the trade the threshold makes: raise it
 * and accuracy on the answered cases goes up while coverage goes down.
 *
 * **Confidence is distance from the coin flip, not the probability.** 0.05 is as confident
 * as 0.95; both say the outcome is nearly settled.
 *
 * **The threshold must clear the target on a lower confidence bound.** Picking the lowest
 * threshold whose *observed* accuracy clears a target is optimistically biased twice over:
 * it takes an argmin over fifty noisy estimates, and on a slice of ~100 rows the standard
 * error on an accuracy near 90% is about 3 points, so a threshold measured at exactly the
 * target is below it about half the time. Measured on real browsing, the naive rule
 * qualified on 4 of 5 folds and kept its promise on 1 of them.
 */

/**
 * The accuracy the answered cases must reach. **Declared, not tuned** — the same status as
 * the 30-minute session timeout (D17). With a base rate near 70%, answering everything
 * already scores about 0.70, so a lower target would be met by abstaining from nothing.
 */
export const DEFAULT_TARGET_ACCURACY = 0.9;

/** One-sided 95% normal quantile. `0` recovers the naive point-estimate rule exactly. */
export const DEFAULT_CONFIDENCE_Z = 1.645;

/** From "answer everything" upward. 0.5 is the floor: confidence cannot be lower. */
export const DEFAULT_THRESHOLDS: readonly number[] = Array.from(
  { length: 50 },
  (_unused, step) => 0.5 + 0.01 * step,
);

/** Distance from the coin flip, in [0.5, 1]. */
export function confidence(probability: number): number {
  return Math.max(probability, 1 - probability);
}

/**
 * Lower end of the Wilson score interval for a binomial proportion.
 *
 * Preferred to the textbook normal approximation because that one misbehaves exactly where
 * this is used — proportions near 1 with modest samples, where it can produce a bound
 * above 1 or below 0. Wilson stays inside [0, 1] and stays sensible at 20 rows.
 */
export function wilsonLowerBound(
  successes: number,
  total: number,
  z: number = DEFAULT_CONFIDENCE_Z,
): number {
  if (total <= 0) return 0;
  const proportion = successes / total;
  if (z <= 0) return proportion;
  const z2 = z * z;
  const denominator = 1 + z2 / total;
  const centre = proportion + z2 / (2 * total);
  const margin =
    z * Math.sqrt((proportion * (1 - proportion)) / total + z2 / (4 * total * total));
  return Math.max(0, (centre - margin) / denominator);
}

export interface CoveragePoint {
  readonly threshold: number;
  readonly coverage: number;
  readonly answered: number;
  readonly accuracy: number | null;
  readonly abstainedAccuracy: number | null;
}

/**
 * A probability above 0.5 predicts the positive class; exactly 0.5 predicts negative.
 * The tie breaks toward the minority class so an exactly-0.5 prediction cannot inflate
 * accuracy by riding the base rate.
 */
function isCorrect(outcome: boolean, probability: number): boolean {
  return probability > 0.5 === outcome;
}

export function accuracyCoverageCurve(
  outcomes: readonly boolean[],
  probabilities: readonly number[],
  thresholds: readonly number[] = DEFAULT_THRESHOLDS,
): CoveragePoint[] {
  if (outcomes.length !== probabilities.length) {
    throw new Error(
      `${outcomes.length} outcomes but ${probabilities.length} probabilities`,
    );
  }
  const total = outcomes.length;
  return thresholds.map((threshold) => {
    const answered: boolean[] = [];
    const abstained: boolean[] = [];
    outcomes.forEach((outcome, index) => {
      const probability = probabilities[index] as number;
      const bucket = confidence(probability) >= threshold ? answered : abstained;
      bucket.push(isCorrect(outcome, probability));
    });
    return {
      threshold,
      coverage: total > 0 ? answered.length / total : 0,
      answered: answered.length,
      accuracy:
        answered.length > 0 ? answered.filter(Boolean).length / answered.length : null,
      abstainedAccuracy:
        abstained.length > 0
          ? abstained.filter(Boolean).length / abstained.length
          : null,
    };
  });
}

/** A threshold and the evidence for it. Never one without the other. */
export interface AbstentionPolicy {
  readonly threshold: number;
  readonly targetAccuracy: number;
  readonly accuracy: number;
  /** What actually had to clear the target. */
  readonly accuracyLowerBound: number;
  readonly coverage: number;
  readonly nValidation: number;
  readonly confidenceZ: number;
  /** False when no threshold reached the target — the caller answers nothing. */
  readonly targetMet: boolean;
}

export interface SelectOptions {
  readonly targetAccuracy?: number;
  readonly thresholds?: readonly number[];
  readonly minAnswered?: number;
  readonly confidenceZ?: number;
}

/**
 * The **lowest** threshold whose answered cases clear the target on their lower bound.
 *
 * Lowest, not best: the point is to answer as much as possible while keeping the promise.
 * Picking the highest-accuracy threshold would abstain from nearly everything and report a
 * wonderful number about four predictions. `minAnswered` stops a threshold qualifying on a
 * handful of cases — 3 for 3 is 100% accuracy and no evidence.
 *
 * `null` when there is no data. A policy with `targetMet: false` when the target is simply
 * unreachable, which is a finding and not an error.
 */
export function selectThreshold(
  outcomes: readonly boolean[],
  probabilities: readonly number[],
  options: SelectOptions = {},
): AbstentionPolicy | null {
  if (outcomes.length === 0) return null;
  const targetAccuracy = options.targetAccuracy ?? DEFAULT_TARGET_ACCURACY;
  const thresholds = options.thresholds ?? DEFAULT_THRESHOLDS;
  const minAnswered = options.minAnswered ?? 20;
  const confidenceZ = options.confidenceZ ?? DEFAULT_CONFIDENCE_Z;

  const curve = accuracyCoverageCurve(outcomes, probabilities, thresholds);
  for (const point of curve) {
    if (point.accuracy === null || point.answered < minAnswered) continue;
    const correct = Math.round(point.accuracy * point.answered);
    const bound = wilsonLowerBound(correct, point.answered, confidenceZ);
    if (bound >= targetAccuracy) {
      return {
        threshold: point.threshold,
        targetAccuracy,
        accuracy: point.accuracy,
        accuracyLowerBound: bound,
        coverage: point.coverage,
        nValidation: outcomes.length,
        confidenceZ,
        targetMet: true,
      };
    }
  }

  // Nothing reached it. Report the strictest point tried, marked as not meeting the
  // target, so the caller shows nothing rather than quietly lowering the bar.
  const last = curve[curve.length - 1] as CoveragePoint;
  const accuracy = last.accuracy ?? 0;
  return {
    threshold: last.threshold,
    targetAccuracy,
    accuracy,
    accuracyLowerBound: wilsonLowerBound(
      Math.round(accuracy * last.answered),
      last.answered,
      confidenceZ,
    ),
    coverage: last.coverage,
    nValidation: outcomes.length,
    confidenceZ,
    targetMet: false,
  };
}

/**
 * Whether a calibrated probability is confident enough to show.
 *
 * A policy that did not meet its target answers nothing at all. Abstained predictions are
 * **absent from the UI**, not greyed out: a greyed-out prediction is still a prediction,
 * and the person reads it anyway.
 */
export function shouldAnswer(
  policy: AbstentionPolicy | null,
  probability: number,
): boolean {
  if (policy === null || !policy.targetMet) return false;
  return confidence(probability) >= policy.threshold;
}
