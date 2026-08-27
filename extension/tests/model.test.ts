/**
 * The model, on the TypeScript side.
 *
 * The parity suite proves these agree with Python; these prove the TypeScript side is
 * right in the first place, which parity alone would not — two implementations can agree
 * and both be wrong.
 *
 * The properties that carry the weight are **convergence**, asserted from the gradient
 * norm rather than inferred from the iteration count, and **chunked training equals whole
 * training**, asserted by interrupting at every plausible point. The second is the one
 * that makes MV3 killing the worker survivable rather than merely tolerable.
 */
import { describe, expect, it } from "vitest";
import { FEATURE_NAMES, type FeatureName, type FeatureRow } from "../src/features/vector";
import {
  DEFAULT_SPEC,
  initialState,
  predictProba,
  stepSize,
  train,
  trainChunk,
  type LogRegSpec,
} from "../src/model/logreg";
import {
  buildMatrix,
  DESIGN_COLUMNS,
  fitPreprocessor,
  MISSING_SUFFIX,
  NULLABLE_FEATURES,
  rawRow,
  transform,
} from "../src/model/prep";
import {
  distribution,
  fitTransitionTable,
  marginalDistribution,
  mostLikely,
  primaryCategory,
} from "../src/model/transition";
import { sessionise } from "../src/features/sessions";
import type { TiseEvent } from "../src/types";

const WINDOW_END = "2026-06-01T00:00:00.000Z";

/** A feature row with every value at 1 unless named. */
function row(overrides: Partial<Record<FeatureName, number | null>> = {}): FeatureRow {
  const values = Object.fromEntries(
    FEATURE_NAMES.map((name) => [name, 1]),
  ) as Record<FeatureName, number | null>;
  return {
    subject: "video",
    windowEnd: WINDOW_END,
    featureSet: "fs_2",
    compat: "history",
    values: { ...values, ...overrides },
  };
}

/**
 * A signal the optimiser must be able to find: column 0 decides the outcome, column 1 is
 * noise-free but irrelevant. Synthetic, and used here as a unit test rather than a
 * benchmark — SPEC.md permits the first and forbids the second.
 */
const MATRIX = [
  [-1.5, 0.4],
  [-1.0, -0.2],
  [-0.5, 0.9],
  [0.5, -0.9],
  [1.0, 0.2],
  [1.5, -0.4],
];
const OUTCOMES = [false, false, false, true, true, true];

/** The `L` that `stepSize` inverts, restated so the test does not reuse the source. */
function curvatureBound(matrix: number[][], spec: LogRegSpec): number {
  const n = matrix.length;
  let total = 0;
  for (const r of matrix) total += 1 + r.reduce((sum, v) => sum + v * v, 0);
  return total / n / 4 + spec.l2 / n;
}

describe("design columns", () => {
  it("puts features first, then indicators, in the declared order", () => {
    expect(DESIGN_COLUMNS.slice(0, FEATURE_NAMES.length)).toEqual([...FEATURE_NAMES]);
    expect(DESIGN_COLUMNS.slice(FEATURE_NAMES.length)).toEqual(
      NULLABLE_FEATURES.map((name) => name + MISSING_SUFFIX),
    );
  });

  it("has one indicator per nullable feature and no others", () => {
    expect(DESIGN_COLUMNS).toHaveLength(FEATURE_NAMES.length + NULLABLE_FEATURES.length);
    for (const name of NULLABLE_FEATURES) {
      expect(FEATURE_NAMES as readonly string[]).toContain(name);
    }
  });
});

describe("preprocessing", () => {
  it("throws on a null in a feature that is not declared nullable", () => {
    // Silently imputing it would hide either a bug or a changed feature.
    expect(() => rawRow(row({ eventCount7d: null }))).toThrow(/not declared nullable/);
  });

  it("records which values were absent", () => {
    const split = rawRow(row({ priorReturnRate: null }));
    expect(split.values[FEATURE_NAMES.indexOf("priorReturnRate")]).toBeNull();
    expect(split.indicators).toEqual(
      NULLABLE_FEATURES.map((name) => (name === "priorReturnRate" ? 1 : 0)),
    );
  });

  it("fills from the mean of observed values only", () => {
    const fitted = fitPreprocessor([
      row({ priorReturnRate: null }),
      row({ priorReturnRate: 0.4 }),
      row({ priorReturnRate: 0.6 }),
    ]);
    expect(fitted.fills[FEATURE_NAMES.indexOf("priorReturnRate")]).toBeCloseTo(0.5, 12);
  });

  it("turns a column with no variation into zeros rather than dividing by zero", () => {
    const rows = [row(), row(), row()];
    const fitted = fitPreprocessor(rows);
    expect(fitted.scales.every((scale) => scale === 1)).toBe(true);
    expect(buildMatrix(fitted, rows)).toEqual([
      DESIGN_COLUMNS.map(() => 0),
      DESIGN_COLUMNS.map(() => 0),
      DESIGN_COLUMNS.map(() => 0),
    ]);
  });

  it("uses the population deviation — n, not n-1", () => {
    const fitted = fitPreprocessor([row({ eventCount7d: 0 }), row({ eventCount7d: 2 })]);
    const index = FEATURE_NAMES.indexOf("eventCount7d");
    expect(fitted.means[index]).toBeCloseTo(1, 12);
    expect(fitted.scales[index]).toBeCloseTo(1, 12); // n-1 would give sqrt(2)
  });

  it("reapplies the training scale unchanged to a row far outside it", () => {
    // Refitting over train and test together is the textbook leak, and it does not look
    // like one — it looks like a slightly better score.
    const fitted = fitPreprocessor([row({ eventCount7d: 0 }), row({ eventCount7d: 2 })]);
    const index = FEATURE_NAMES.indexOf("eventCount7d");
    expect(transform(fitted, row({ eventCount7d: 100 }))[index]).toBeCloseTo(99, 9);
  });

  it("never lets one row's transform depend on another", () => {
    const rows = [row({ eventCount7d: 0 }), row({ eventCount7d: 2 })];
    const fitted = fitPreprocessor(rows);
    expect(transform(fitted, rows[0]!)).toEqual(buildMatrix(fitted, rows)[0]);
  });

  it("gives the identity transform for an empty training window", () => {
    // A new profile has no history. Numerically it does not matter — an untrained model
    // predicts 0.5 whatever the columns hold — but it is a contract the mirror matches.
    const fitted = fitPreprocessor([]);
    expect(fitted.means.every((value) => value === 0)).toBe(true);
    expect(fitted.scales.every((value) => value === 1)).toBe(true);
  });
});

describe("the optimiser", () => {
  it("reaches a gradient norm near zero rather than merely running out of steps", () => {
    const state = train(MATRIX, OUTCOMES);
    expect(state.iterationsDone).toBe(DEFAULT_SPEC.iterations);
    expect(state.gradientNorm).toBeLessThan(1e-8);
  });

  it("actually learns the signal", () => {
    const state = train(MATRIX, OUTCOMES);
    MATRIX.forEach((r, index) => {
      expect(predictProba(state, r) > 0.5).toBe(OUTCOMES[index]);
    });
  });

  it("keeps separable data finite through the L2 penalty", () => {
    const unpenalised = train(MATRIX, OUTCOMES, { ...DEFAULT_SPEC, l2: 0 });
    const penalised = train(MATRIX, OUTCOMES, { ...DEFAULT_SPEC, l2: 10 });
    expect(Math.abs(penalised.weights[0]!)).toBeLessThan(Math.abs(unpenalised.weights[0]!));
  });

  it("does not penalise the bias", () => {
    // Penalising it would drag the base rate toward 0.5 — a claim nobody made.
    const state = train([[0], [0], [0], [0]], [true, true, true, false], {
      ...DEFAULT_SPEC,
      l2: 10,
    });
    expect(state.weights).toEqual([0]);
    expect(predictProba(state, [0])).toBeCloseTo(0.75, 6);
  });

  it("derives a step below the divergence threshold", () => {
    // `2/L` is where gradient descent stops descending. `1/L` is half of it.
    expect(stepSize(MATRIX, DEFAULT_SPEC)).toBeGreaterThan(0);
    expect(stepSize(MATRIX, DEFAULT_SPEC)).toBeLessThan(2 / curvatureBound(MATRIX, DEFAULT_SPEC));
  });

  it("does diverge when pushed past the bound", () => {
    // The guarantee is only worth something if the thing it prevents is real. Without
    // this the bound could be arithmetic nobody had ever checked did anything.
    const reckless = train(MATRIX, OUTCOMES, { ...DEFAULT_SPEC, stepScale: 400 });
    expect(!Number.isFinite(reckless.gradientNorm) || reckless.gradientNorm > 1).toBe(true);
  });

  it("survives perfectly collinear columns", () => {
    // The case a hand-picked learning rate fails on, and the reason for the bound.
    const duplicated = MATRIX.map(([value]) => [value!, value!, value!, value!]);
    const state = train(duplicated, OUTCOMES);
    expect(Number.isFinite(state.bias)).toBe(true);
    expect(state.gradientNorm).toBeLessThan(1e-6);
  });

  it("is deterministic and carries no seed", () => {
    expect(initialState(4).weights).toEqual([0, 0, 0, 0]);
    expect(train(MATRIX, OUTCOMES).weights).toEqual(train(MATRIX, OUTCOMES).weights);
  });
});

describe("resumability — the property MV3 makes load-bearing", () => {
  it("reaches the same answer chunk by chunk as in one call", () => {
    const whole = train(MATRIX, OUTCOMES);
    let state = initialState(MATRIX[0]!.length);
    while (state.iterationsDone < DEFAULT_SPEC.iterations) {
      state = trainChunk(state, MATRIX, OUTCOMES);
    }
    expect(state.weights).toEqual(whole.weights);
    expect(state.bias).toBe(whole.bias);
  });

  it.each([1, 3, 7, 50, 999, 10_000])(
    "gives the same answer at a chunk size of %i",
    (chunkIterations) => {
      const whole = train(MATRIX, OUTCOMES);
      const resumed = train(MATRIX, OUTCOMES, { ...DEFAULT_SPEC, chunkIterations });
      expect(resumed.weights).toEqual(whole.weights);
      expect(resumed.bias).toBe(whole.bias);
    },
  );

  it("returns the same state when called past the end", () => {
    // A caller that keeps going must not quietly train a different model.
    const finished = train(MATRIX, OUTCOMES);
    expect(trainChunk(finished, MATRIX, OUTCOMES)).toEqual(finished);
  });

  it("treats no training data as finished, predicting one half", () => {
    // A new profile has none. Zero weights predict 0.5, which is the honest answer.
    const state = train([], [], DEFAULT_SPEC, 3);
    expect(state.iterationsDone).toBe(DEFAULT_SPEC.iterations);
    expect(predictProba(state, [1, 2, 3])).toBe(0.5);
  });

  it("throws rather than padding when rows and outcomes disagree", () => {
    expect(() => trainChunk(initialState(2), MATRIX, OUTCOMES.slice(0, -1))).toThrow(
      /must be aligned/,
    );
  });

  it("throws rather than padding a row of the wrong width", () => {
    expect(() => predictProba(initialState(2), [1])).toThrow(/columns/);
  });
});

describe("the transition table", () => {
  const START = Date.parse("2026-06-01T09:00:00.000Z");

  function event(category: string, minutes: number, eventId: string): TiseEvent {
    return {
      eventId,
      occurredAt: new Date(START + minutes * 60_000).toISOString(),
      source: "import",
      domain: "example.com",
      category,
      transition: "link",
      dwellSeconds: null,
      sessionId: "",
    };
  }

  /** One session per group, separated by well over the timeout. */
  function sessionsFrom(...groups: string[][]) {
    const events: TiseEvent[] = [];
    groups.forEach((categories, index) => {
      categories.forEach((category, offset) => {
        events.push(event(category, index * 24 * 60 + offset, `s${index}-e${offset}`));
      });
    });
    return sessionise(events, 1800);
  }

  it("picks the most frequent category as primary", () => {
    expect(primaryCategory(sessionsFrom(["video", "video", "dev"])[0]!)).toBe("video");
  });

  it("breaks ties by name, not by order of appearance", () => {
    // First-seen would depend on within-session ordering, which two implementations
    // could resolve differently for events sharing a timestamp.
    expect(primaryCategory(sessionsFrom(["video", "dev"])[0]!)).toBe("dev");
    expect(primaryCategory(sessionsFrom(["dev", "video"])[0]!)).toBe("dev");
  });

  it("counts consecutive pairs and nothing else", () => {
    const table = fitTransitionTable(sessionsFrom(["dev"], ["video"], ["dev"]));
    expect(table.counts["dev"]).toEqual({ video: 1 });
    expect(table.counts["video"]).toEqual({ dev: 1 });
  });

  it("sorts the vocabulary, because it is a column order", () => {
    const table = fitTransitionTable(sessionsFrom(["video"], ["dev"], ["search"]));
    expect(table.vocabulary).toEqual(["dev", "search", "video"]);
  });

  it("treats no sessions as an empty table rather than an error", () => {
    const table = fitTransitionTable([]);
    expect(table.vocabulary).toEqual([]);
    expect(mostLikely(table, "dev")).toBeNull();
    expect(distribution(table, "dev")).toEqual({});
  });

  it("keeps a two-observation row short of certainty", () => {
    // The D26 problem in its smallest form.
    const table = fitTransitionTable(
      sessionsFrom(["dev"], ["video"], ["dev"], ["video"], ["search"]),
    );
    const probability = distribution(table, "dev")["video"]!;
    expect(probability).toBeGreaterThan(0.5);
    expect(probability).toBeLessThan(1);
  });

  it("sums every distribution to one", () => {
    const table = fitTransitionTable(
      sessionsFrom(["dev"], ["video"], ["dev"], ["video"], ["search"]),
    );
    const total = Object.values(distribution(table, "dev")).reduce((a, b) => a + b, 0);
    expect(total).toBeCloseTo(1, 12);
  });

  it("falls back to what follows anything for an unseen category", () => {
    const table = fitTransitionTable(sessionsFrom(["dev"], ["video"], ["dev"], ["video"]));
    expect(distribution(table, "never-browsed")).toEqual(marginalDistribution(table));
  });
});
