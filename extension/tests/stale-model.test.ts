/**
 * A model stored by an earlier build, and the prediction outage it caused.
 *
 * **This is a regression test for a bug that reached a real browser.** T-G1 added
 * `Preprocessor.featureSet` and a check in `transform` — correctly, because two feature
 * sets can have the same width, so an `fs_3` row transforms cleanly through an `as_2`
 * preprocessor and every coefficient after the first differing column lands on the wrong
 * feature with no error at all. What T-G1 did not add was the migration. A model already
 * sitting in IndexedDB carried no `featureSet`, `transform` threw on every prediction, and
 * the extension silently stopped predicting:
 *
 *     Uncaught (in promise) Error: row is fs_3 and this preprocessor was fitted on
 *     undefined; nothing downstream would notice.
 *
 * It surfaced in a screenshot of `chrome://extensions`, not from a failing test — the same
 * way D101 did. Every test in the suite trains its own model, so every preprocessor in the
 * suite was written by the current build and none of them could ever be missing the field.
 * That is the gap this file closes: it writes the *old* shape deliberately.
 *
 * The fix discards rather than guesses. Stamping the stored model with today's feature set
 * would usually be right, and when it was wrong the result would not be an error — it would
 * be a wrong probability, produced silently, which is the exact failure the check exists to
 * prevent.
 */
import "fake-indexeddb/auto";
import { IDBFactory } from "fake-indexeddb";
import { beforeEach, describe, expect, it } from "vitest";
import { closeTiseDb, readMeta, writeMeta } from "../src/storage/db";
import { FEATURE_SET } from "../src/features/vector";
import { DEFAULT_SPEC } from "../src/model/logreg";
import { identityCalibrator } from "../src/model/calibrate";
import { isStaleModel, readModel, readModelIncludingStale } from "../src/model/train";
import type { TrainedModel } from "../src/model/train";
import type { Preprocessor } from "../src/model/prep";

const MODEL_KEY = "model:return_24h";

function modelWith(preprocessor: Preprocessor): TrainedModel {
  return {
    target: "return_24h",
    featureSet: FEATURE_SET,
    trainedAt: "2026-08-29T12:00:00.000Z",
    rowCount: 334,
    positiveCount: 240,
    spec: DEFAULT_SPEC,
    preprocessor,
    state: { weights: [0, 0], bias: 0, iterations: 4000, finalGradient: 1e-6 },
    transition: { vocabulary: [], counts: {}, marginal: {}, smoothing: 1 },
    calibrator: identityCalibrator(),
    policy: null,
    nCalibration: 0,
  } as unknown as TrainedModel;
}

/** Exactly what T-G1's build wrote: no `featureSet` on the preprocessor. */
const LEGACY = modelWith({
  columns: ["a", "b"],
  fills: [0, 0],
  means: [0, 0],
  scales: [1, 1],
} as unknown as Preprocessor);

const CURRENT = modelWith({
  featureSet: FEATURE_SET,
  columns: ["a", "b"],
  fills: [0, 0],
  means: [0, 0],
  scales: [1, 1],
});

beforeEach(async () => {
  closeTiseDb();
  globalThis.indexedDB = new IDBFactory();
});

describe("recognising a model an earlier build wrote", () => {
  it("calls the pre-T-G1 shape stale", () => {
    expect(isStaleModel(LEGACY)).toBe(true);
  });

  it("does not call a current model stale", () => {
    expect(isStaleModel(CURRENT)).toBe(false);
  });

  it("treats an empty feature set as stale too", () => {
    // An empty string would pass a `typeof` check and fail every comparison against a real
    // feature set, which is the same outage wearing a different value.
    const empty = modelWith({ ...CURRENT.preprocessor, featureSet: "" });
    expect(isStaleModel(empty)).toBe(true);
  });

  it("says nothing about an absent model", () => {
    // "No model" and "a model that cannot be used" are different states, and only one of
    // them needs telling the person about.
    expect(isStaleModel(undefined)).toBe(false);
  });
});

describe("what callers see", () => {
  it("hides a stale model, so no caller can transform a row through it", () => {
    // Reported as "no model" rather than as a broken one: every caller already handles
    // absence, and none of them handled a throw from deep inside `transform`.
    return writeMeta(MODEL_KEY, LEGACY).then(async () => {
      expect(await readModel()).toBeUndefined();
    });
  });

  it("returns a current model unchanged", async () => {
    await writeMeta(MODEL_KEY, CURRENT);
    const read = await readModel();
    expect(read?.preprocessor.featureSet).toBe(FEATURE_SET);
  });

  it("does not delete the stale model, so the popup can explain the retrain", async () => {
    // Deleting it would leave the person with "no model yet" after months of browsing,
    // which reads as a bug rather than as a one-off retrain.
    await writeMeta(MODEL_KEY, LEGACY);
    expect(await readModel()).toBeUndefined();
    expect(await readModelIncludingStale()).toBeDefined();
    expect(await readMeta(MODEL_KEY)).toBeDefined();
  });

  it("is undefined either way when nothing was ever stored", async () => {
    expect(await readModel()).toBeUndefined();
    expect(await readModelIncludingStale()).toBeUndefined();
  });
});
