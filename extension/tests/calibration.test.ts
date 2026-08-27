/**
 * Calibration and abstention, on the TypeScript side.
 *
 * The parity suite proves these agree with Python; these prove the TypeScript side is
 * right in the first place, which parity alone would not — two implementations can agree
 * and both be wrong.
 *
 * Two failures are worth more attention than the rest. A calibrator must not invent a
 * correction from a calibration set that contains no information. And a threshold must not
 * qualify on evidence too thin to support it — which is the failure real browsing actually
 * exhibited, not a hypothetical.
 */
import { describe, expect, it } from "vitest";
import {
  applyCalibration,
  CALIBRATION_METHOD,
  CALIBRATION_VERSION,
  fitPlatt,
  identityCalibrator,
  isIdentity,
  logit,
} from "../src/model/calibrate";
import {
  accuracyCoverageCurve,
  confidence,
  DEFAULT_CONFIDENCE_Z,
  DEFAULT_TARGET_ACCURACY,
  selectThreshold,
  shouldAnswer,
  wilsonLowerBound,
} from "../src/model/abstain";

function sigmoid(z: number): number {
  return 1 / (1 + Math.exp(-z));
}

/** A model that says 0.95 when the truth is `rate`, and 0.05 when it is `1 - rate`. */
function overconfident(rate: number, n: number): [number[], boolean[]] {
  const probabilities: number[] = [];
  const outcomes: boolean[] = [];
  for (let index = 0; index < n; index += 1) {
    if (index % 2 === 0) {
      probabilities.push(0.95);
      outcomes.push(Math.floor(index / 2) % 10 < rate * 10);
    } else {
      probabilities.push(0.05);
      outcomes.push(Math.floor(index / 2) % 10 < (1 - rate) * 10);
    }
  }
  return [probabilities, outcomes];
}

/** Confident predictions usually right; uncertain ones coin flips. */
function graded(n = 200): [boolean[], number[]] {
  const outcomes: boolean[] = [];
  const probabilities: number[] = [];
  for (let index = 0; index < n; index += 1) {
    if (index % 2 === 0) {
      probabilities.push(0.95);
      outcomes.push(index % 20 !== 0);
    } else {
      probabilities.push(0.55);
      outcomes.push(index % 4 === 1);
    }
  }
  return [outcomes, probabilities];
}

function brier(outcomes: readonly boolean[], probabilities: readonly number[]): number {
  let total = 0;
  outcomes.forEach((outcome, index) => {
    total += ((probabilities[index] as number) - (outcome ? 1 : 0)) ** 2;
  });
  return total / outcomes.length;
}

describe("logit", () => {
  it("is the inverse of the sigmoid", () => {
    for (const probability of [0.1, 0.25, 0.5, 0.75, 0.9]) {
      expect(sigmoid(logit(probability))).toBeCloseTo(probability, 12);
    }
  });

  it("clamps the ends instead of returning infinity", () => {
    // One raw 0 or 1 would otherwise dominate the fit or produce a NaN coefficient.
    expect(Number.isFinite(logit(0))).toBe(true);
    expect(Number.isFinite(logit(1))).toBe(true);
    expect(logit(0)).toBeLessThan(-18);
    expect(logit(1)).toBeGreaterThan(18);
  });
});

describe("the identity calibrator", () => {
  it("leaves every probability alone", () => {
    const calibrator = identityCalibrator();
    for (const probability of [0.01, 0.3, 0.5, 0.77, 0.99]) {
      expect(applyCalibration(calibrator, probability)).toBeCloseTo(probability, 9);
    }
  });

  it("is recognisable as the identity", () => {
    // A prediction carrying it is visibly uncalibrated, which is its own claim.
    expect(isIdentity(identityCalibrator())).toBe(true);
  });

  it("is what an empty calibration set produces", () => {
    expect(isIdentity(fitPlatt([], []))).toBe(true);
  });

  it("is what a single-class calibration set produces", () => {
    // All-positive data says nothing about where the model is over-confident.
    expect(isIdentity(fitPlatt([0.9, 0.8, 0.7], [true, true, true]))).toBe(true);
    expect(isIdentity(fitPlatt([0.9, 0.8, 0.7], [false, false, false]))).toBe(true);
  });
});

describe("fitting Platt", () => {
  it("pulls an over-confident model toward the base rate", () => {
    const [probabilities, outcomes] = overconfident(0.7, 200);
    const calibrator = fitPlatt(probabilities, outcomes);
    expect(calibrator.a).toBeLessThan(1);
    expect(applyCalibration(calibrator, 0.95)).toBeLessThan(0.95);
    expect(applyCalibration(calibrator, 0.05)).toBeGreaterThan(0.05);
  });

  it("improves the Brier score of an over-confident model", () => {
    const [probabilities, outcomes] = overconfident(0.7, 200);
    const calibrator = fitPlatt(probabilities, outcomes);
    const after = probabilities.map((p) => applyCalibration(calibrator, p));
    expect(brier(outcomes, after)).toBeLessThan(brier(outcomes, probabilities));
  });

  it("leaves an already honest model close to the identity", () => {
    const probabilities = [...Array<number>(100).fill(0.7), ...Array<number>(100).fill(0.3)];
    const outcomes = [
      ...Array.from({ length: 100 }, (_u, i) => i < 70),
      ...Array.from({ length: 100 }, (_u, i) => i < 30),
    ];
    const calibrator = fitPlatt(probabilities, outcomes);
    for (const probability of [0.3, 0.7]) {
      expect(applyCalibration(calibrator, probability)).toBeCloseTo(probability, 1);
    }
  });

  it("stops a six-row set being separated perfectly", () => {
    // Hard 0/1 targets would drive the fit toward certainty, which is the thing
    // calibration removes. Platt's soft targets pull the ends in by a pseudo-count each.
    const calibrator = fitPlatt(
      [0.6, 0.6, 0.6, 0.4, 0.4, 0.4],
      [true, true, true, false, false, false],
    );
    expect(applyCalibration(calibrator, 0.6)).toBeLessThan(0.95);
  });

  it("converges rather than running out of iterations", () => {
    const [probabilities, outcomes] = overconfident(0.7, 200);
    expect(fitPlatt(probabilities, outcomes).gradientNorm).toBeLessThan(1e-6);
  });

  it("records the method, the version and what it saw", () => {
    const [probabilities, outcomes] = overconfident(0.7, 50);
    const calibrator = fitPlatt(probabilities, outcomes);
    expect(calibrator.method).toBe(CALIBRATION_METHOD);
    expect(calibrator.version).toBe(CALIBRATION_VERSION);
    expect(calibrator.nCalibration).toBe(50);
  });

  it("throws on misaligned input rather than truncating", () => {
    expect(() => fitPlatt([0.5, 0.6], [true])).toThrow(/aligned/);
  });

  it("never reorders predictions", () => {
    // Platt is monotone: it changes what the numbers mean, not who is ahead. That is what
    // lets the abstention threshold act on the same ordering before and after.
    const [probabilities, outcomes] = overconfident(0.7, 100);
    const calibrator = fitPlatt(probabilities, outcomes);
    const mapped = [0.02, 0.1, 0.3, 0.5, 0.6, 0.85, 0.98].map((p) =>
      applyCalibration(calibrator, p),
    );
    expect(mapped).toEqual([...mapped].sort((a, b) => a - b));
  });

  it("always returns a probability", () => {
    const [probabilities, outcomes] = overconfident(0.9, 100);
    const calibrator = fitPlatt(probabilities, outcomes);
    for (const probability of [0, 1e-12, 0.5, 1 - 1e-12, 1]) {
      const value = applyCalibration(calibrator, probability);
      expect(Number.isFinite(value)).toBe(true);
      expect(value).toBeGreaterThanOrEqual(0);
      expect(value).toBeLessThanOrEqual(1);
    }
  });
});

describe("confidence and coverage", () => {
  it("measures distance from the coin flip, not the probability", () => {
    expect(confidence(0.95)).toBeCloseTo(0.95, 12);
    expect(confidence(0.05)).toBeCloseTo(0.95, 12);
    expect(confidence(0.5)).toBeCloseTo(0.5, 12);
  });

  it("falls in coverage as the threshold rises", () => {
    const [outcomes, probabilities] = graded();
    const coverages = accuracyCoverageCurve(outcomes, probabilities).map((p) => p.coverage);
    expect(coverages).toEqual([...coverages].sort((a, b) => b - a));
  });

  it("raises accuracy on what is left", () => {
    // The whole premise. If this is not true, abstention buys nothing.
    const [outcomes, probabilities] = graded();
    const curve = accuracyCoverageCurve(outcomes, probabilities);
    const all = curve[0]?.accuracy as number;
    const strict = curve.find((p) => p.threshold >= 0.9 && p.accuracy !== null);
    expect(strict?.accuracy).toBeGreaterThan(all);
    expect(strict?.coverage).toBeLessThan(1);
  });

  it("gives a threshold that answers nothing no accuracy, rather than zero", () => {
    // Zero would mean it got everything wrong.
    const curve = accuracyCoverageCurve([true, false], [0.55, 0.45], [0.99]);
    expect(curve[0]?.answered).toBe(0);
    expect(curve[0]?.accuracy).toBeNull();
  });

  it("throws on misaligned input", () => {
    expect(() => accuracyCoverageCurve([true, false], [0.5])).toThrow(/outcomes/);
  });
});

describe("the confidence bound, and why the threshold rests on it", () => {
  it("recovers the observed proportion at z = 0", () => {
    expect(wilsonLowerBound(90, 100, 0)).toBeCloseTo(0.9, 12);
  });

  it("is never above what was observed", () => {
    for (const [successes, total] of [
      [90, 100],
      [18, 20],
      [450, 500],
    ]) {
      expect(wilsonLowerBound(successes as number, total as number)).toBeLessThanOrEqual(
        (successes as number) / (total as number),
      );
    }
  });

  it("stays a probability at the extremes", () => {
    // Where the textbook normal approximation escapes [0, 1] and Wilson does not.
    for (const [successes, total] of [
      [20, 20],
      [0, 20],
      [1, 1],
    ]) {
      const bound = wilsonLowerBound(successes as number, total as number);
      expect(bound).toBeGreaterThanOrEqual(0);
      expect(bound).toBeLessThanOrEqual(1);
    }
  });

  it("punishes a small sample more than a large one", () => {
    // 90% of 20 is much weaker evidence than 90% of 500, and the bound says so.
    expect(wilsonLowerBound(18, 20)).toBeLessThan(wilsonLowerBound(450, 500));
    expect(wilsonLowerBound(450, 500)).toBeLessThan(0.9);
  });

  it("returns zero for no data rather than dividing", () => {
    expect(wilsonLowerBound(0, 0)).toBe(0);
  });

  it("is a one-sided 95% quantile by default", () => {
    expect(DEFAULT_CONFIDENCE_Z).toBeCloseTo(1.645, 10);
  });
});

describe("selecting a threshold", () => {
  it("picks the lowest threshold meeting the target", () => {
    // Lowest, not best: among thresholds that keep the promise, most coverage wins.
    // z=0 isolates that mechanic from the confidence bound.
    const [outcomes, probabilities] = graded();
    const policy = selectThreshold(outcomes, probabilities, {
      targetAccuracy: 0.85,
      confidenceZ: 0,
    });
    expect(policy?.targetMet).toBe(true);
    expect(policy?.accuracy).toBeGreaterThanOrEqual(0.85);
  });

  it("will not qualify on a handful of cases", () => {
    // 3 for 3 is 100% accuracy and no evidence.
    const outcomes = [true, true, true, ...Array<boolean>(40).fill(false)];
    const probabilities = [0.99, 0.99, 0.99, ...Array<number>(40).fill(0.55)];
    const policy = selectThreshold(outcomes, probabilities, {
      targetAccuracy: 0.95,
      minAnswered: 20,
    });
    expect(policy?.targetMet).toBe(false);
  });

  it("treats an unreachable target as a finding, not an error", () => {
    const outcomes = Array.from({ length: 100 }, (_u, i) => i % 2 === 0);
    const policy = selectThreshold(outcomes, Array<number>(100).fill(0.51), {
      targetAccuracy: 0.99,
    });
    expect(policy).not.toBeNull();
    expect(policy?.targetMet).toBe(false);
  });

  it("gives no policy at all when there is no data", () => {
    expect(selectThreshold([], [])).toBeNull();
  });

  it("never picks a lower threshold than the naive rule would", () => {
    const [outcomes, probabilities] = graded();
    const naive = selectThreshold(outcomes, probabilities, {
      targetAccuracy: 0.85,
      confidenceZ: 0,
    });
    const strict = selectThreshold(outcomes, probabilities, { targetAccuracy: 0.85 });
    if (strict?.targetMet && naive?.targetMet) {
      expect(strict.threshold).toBeGreaterThanOrEqual(naive.threshold);
    }
  });

  it("keeps the target above the base rate, or it would measure nothing", () => {
    // Answering everything already scores about 0.70 on this data.
    expect(DEFAULT_TARGET_ACCURACY).toBeGreaterThan(0.75);
  });
});

describe("what the UI is allowed to show", () => {
  it("shows nothing when no policy exists", () => {
    expect(shouldAnswer(null, 0.99)).toBe(false);
  });

  it("shows nothing when the policy could not meet its target", () => {
    // The branch real browsing takes. Shipping a promise that cannot be kept would be
    // worse than silence.
    const outcomes = Array.from({ length: 100 }, (_u, i) => i % 2 === 0);
    const policy = selectThreshold(outcomes, Array<number>(100).fill(0.51), {
      targetAccuracy: 0.99,
    });
    expect(policy?.targetMet).toBe(false);
    expect(shouldAnswer(policy, 0.999)).toBe(false);
  });

  it("shows a prediction only when it clears the threshold", () => {
    const [outcomes, probabilities] = graded();
    const policy = selectThreshold(outcomes, probabilities, {
      targetAccuracy: 0.85,
      confidenceZ: 0,
    });
    expect(policy?.targetMet).toBe(true);
    const threshold = policy?.threshold as number;
    expect(shouldAnswer(policy, threshold)).toBe(true);
    expect(shouldAnswer(policy, 1 - threshold)).toBe(true); // symmetric
    expect(shouldAnswer(policy, 0.5)).toBe(false);
  });
});
