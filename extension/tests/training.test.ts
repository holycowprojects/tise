/**
 * Training against real storage, which is where T11's acceptance criteria actually live.
 *
 * `model.test.ts` proves the arithmetic. This proves the thing MV3 makes hard: that a run
 * split across many wake-ups, with the worker free to die between any two of them,
 * produces exactly the model an uninterrupted run would have produced. Nothing else in
 * the suite would notice if it did not — a half-trained model is not an error, it is just
 * quietly worse.
 */
import "fake-indexeddb/auto";
import { IDBFactory } from "fake-indexeddb";
import { beforeEach, describe, expect, it } from "vitest";
import { closeTiseDb } from "../src/storage/db";
import { deleteEverything, isEmpty } from "../src/storage/delete";
import { putEvents } from "../src/storage/events";
import { allFeatureRows, countFeatureRows, putFeatureRows } from "../src/storage/features";
import { allLabels, countLabels, putLabels } from "../src/storage/labels";
import { enforceRetention } from "../src/storage/retention";
import { DEFAULT_SETTINGS } from "../src/storage/settings";
import { computeFeatures } from "../src/features/vector";
import { return24hLabels } from "../src/features/labels";
import { joinStored } from "../src/model/dataset";
import { DEFAULT_SPEC, train } from "../src/model/logreg";
import { buildMatrix, DESIGN_COLUMNS, fitPreprocessor } from "../src/model/prep";
import {
  cancelTraining,
  readJob,
  readModel,
  refreshDataset,
  runTrainingChunk,
} from "../src/model/train";
import type { TiseEvent } from "../src/types";

const TIMEOUT = 1800;
const HORIZON = 24;
const OPTIONS = { timeoutSeconds: TIMEOUT, horizonHours: HORIZON };
const START = Date.parse("2026-06-01T09:00:00.000Z");
const HOUR = 3_600_000;

function event(category: string, hours: number, eventId: string): TiseEvent {
  const at = new Date(START + hours * HOUR).toISOString();
  return {
    eventId,
    occurredAt: at,
    source: "import",
    domain: "example.com",
    category,
    transition: "link",
    dwellSeconds: null,
    sessionId: at,
  };
}

/** `video` recurs daily, `travel` about twice a month. A signal a model should find. */
function corpus(days = 30): TiseEvent[] {
  const events: TiseEvent[] = [];
  for (let day = 0; day < days; day += 1) {
    events.push(event("video", day * 24, `v${day}`));
    events.push(event("video", day * 24 + 0.25, `v${day}b`));
    if (day % 11 === 0) events.push(event("travel", day * 24 + 3, `t${day}`));
  }
  return events;
}

/** What an uninterrupted fit over the same stored data would produce. */
async function referenceModel() {
  const [rows, labels] = await Promise.all([allFeatureRows(), allLabels()]);
  const joined = joinStored(rows, labels);
  const preprocessor = fitPreprocessor(joined.rows);
  const matrix = buildMatrix(preprocessor, joined.rows);
  return train(matrix, joined.outcomes, DEFAULT_SPEC, DESIGN_COLUMNS.length);
}

beforeEach(async () => {
  await closeTiseDb();
  globalThis.indexedDB = new IDBFactory();
});

describe("turning browsing into training data", () => {
  it("writes one row and one label per (category, session)", async () => {
    const events = corpus(5);
    await putEvents(events);
    const written = await refreshDataset(OPTIONS);

    const expected = return24hLabels(events, TIMEOUT, HORIZON).length;
    expect(written.labels).toBe(expected);
    expect(await countFeatureRows()).toBe(expected);
    expect(await countLabels()).toBe(expected);
  });

  it("is idempotent — running twice adds nothing", async () => {
    await putEvents(corpus(5));
    await refreshDataset(OPTIONS);
    const first = await countFeatureRows();
    await refreshDataset(OPTIONS);
    expect(await countFeatureRows()).toBe(first);
    expect(await countLabels()).toBe(first);
  });

  it("rewrites a provisional outcome once its horizon has elapsed", async () => {
    // This is why labels live in their own store: a feature vector is final when it is
    // computed, an outcome is not. The last session of a corpus has nothing after it, so
    // its label is negative — until the return arrives.
    await putEvents([event("video", 0, "a")]);
    await refreshDataset(OPTIONS);
    expect((await allLabels()).every((label) => !label.outcome)).toBe(true);

    await putEvents([event("video", 12, "b")]);
    await refreshDataset(OPTIONS);
    const labels = await allLabels();
    expect(labels[0]?.outcome).toBe(true);
    // Rewritten, not duplicated.
    expect(labels.filter((label) => label.subject === "video")).toHaveLength(2);
  });

  it("does nothing at all when there is no browsing yet", async () => {
    expect(await refreshDataset(OPTIONS)).toEqual({ rows: 0, labels: 0 });
    expect(await countFeatureRows()).toBe(0);
  });

  it("keeps rows and labels aligned by index", async () => {
    await putEvents(corpus(8));
    await refreshDataset(OPTIONS);
    const joined = joinStored(await allFeatureRows(), await allLabels());
    expect(joined.unmatched).toBe(0);
    expect(joined.rows).toHaveLength(joined.outcomes.length);
    joined.rows.forEach((row, index) => {
      expect(row.values).toEqual(
        computeFeatures(corpus(8), row.subject, Date.parse(row.windowEnd), OPTIONS).values,
      );
      expect(typeof joined.outcomes[index]).toBe("boolean");
    });
  });
});

describe("chunked training", () => {
  it("reports idle rather than failing when there is nothing to learn from", async () => {
    const outcome = await runTrainingChunk({ timeoutSeconds: TIMEOUT });
    expect(outcome.state).toBe("idle");
    expect(outcome.reason).toBe("no-data");
    expect(await readModel()).toBeUndefined();
  });

  it("advances one chunk per call and leaves a resumable job behind", async () => {
    await putEvents(corpus(10));
    await refreshDataset(OPTIONS);

    const first = await runTrainingChunk({ timeoutSeconds: TIMEOUT });
    expect(first.state).toBe("training");
    expect(first.iterationsDone).toBe(DEFAULT_SPEC.chunkIterations);

    const job = await readJob();
    expect(job?.state.iterationsDone).toBe(DEFAULT_SPEC.chunkIterations);
    // No model exists until the run finishes: a half-trained model shown as finished is
    // exactly the failure this design is built to avoid.
    expect(await readModel()).toBeUndefined();
  });

  it("reaches the same coefficients across many wake-ups as in one uninterrupted fit", async () => {
    await putEvents(corpus(10));
    await refreshDataset(OPTIONS);

    const expected = await referenceModel();

    let outcome = await runTrainingChunk({ timeoutSeconds: TIMEOUT });
    let calls = 1;
    while (outcome.state === "training") {
      outcome = await runTrainingChunk({ timeoutSeconds: TIMEOUT });
      calls += 1;
    }

    expect(outcome.state).toBe("done");
    expect(calls).toBe(DEFAULT_SPEC.iterations / DEFAULT_SPEC.chunkIterations);

    const model = await readModel();
    expect(model?.state.weights).toEqual(expected.weights);
    expect(model?.state.bias).toBe(expected.bias);
    expect(model?.state.gradientNorm).toBe(expected.gradientNorm);
  });

  it("survives the worker being killed between any two chunks", async () => {
    // The database handle is dropped mid-run, which is as close as this suite can get to
    // Chrome terminating the service worker. Everything the next chunk needs has to come
    // back off disk, because nothing in memory survives.
    await putEvents(corpus(10));
    await refreshDataset(OPTIONS);
    const expected = await referenceModel();

    for (let chunk = 0; chunk < 3; chunk += 1) {
      await runTrainingChunk({ timeoutSeconds: TIMEOUT });
      await closeTiseDb();
    }

    let outcome = await runTrainingChunk({ timeoutSeconds: TIMEOUT });
    while (outcome.state === "training") {
      await closeTiseDb();
      outcome = await runTrainingChunk({ timeoutSeconds: TIMEOUT });
    }

    expect((await readModel())?.state.weights).toEqual(expected.weights);
  });

  it("clears the job when the run finishes, so the next alarm starts a fresh one", async () => {
    await putEvents(corpus(6));
    await refreshDataset(OPTIONS);
    let outcome = await runTrainingChunk({ timeoutSeconds: TIMEOUT });
    while (outcome.state === "training") {
      outcome = await runTrainingChunk({ timeoutSeconds: TIMEOUT });
    }
    expect(await readJob()).toBeUndefined();
    expect(await readModel()).toBeDefined();
  });

  it("records what the model was trained on, not only the coefficients", async () => {
    await putEvents(corpus(10));
    await refreshDataset(OPTIONS);
    let outcome = await runTrainingChunk({ timeoutSeconds: TIMEOUT });
    while (outcome.state === "training") {
      outcome = await runTrainingChunk({ timeoutSeconds: TIMEOUT });
    }

    const model = await readModel();
    expect(model?.featureSet).toBe("fs_2");
    expect(model?.rowCount).toBe(await countLabels());
    expect(model?.positiveCount).toBeGreaterThan(0);
    expect(model?.positiveCount).toBeLessThan(model?.rowCount ?? 0);
    expect(model?.spec).toEqual(DEFAULT_SPEC);
    expect(model?.preprocessor.columns).toEqual(DESIGN_COLUMNS);
  });

  it("converges rather than merely running out of iterations", async () => {
    await putEvents(corpus(10));
    await refreshDataset(OPTIONS);
    let outcome = await runTrainingChunk({ timeoutSeconds: TIMEOUT });
    while (outcome.state === "training") {
      outcome = await runTrainingChunk({ timeoutSeconds: TIMEOUT });
    }
    expect((await readModel())?.state.gradientNorm).toBeLessThan(1e-6);
  });
});

describe("a training set that moves underneath a job", () => {
  it("restarts rather than blending two sets", async () => {
    // Continuing would produce a fit that is neither of the two sets and looks like
    // neither problem. Restarting is visible and cheap; continuing is invisible and wrong.
    await putEvents(corpus(10));
    await refreshDataset(OPTIONS);

    // Two chunks in, so a restart is visibly a step backwards rather than a no-op.
    await runTrainingChunk({ timeoutSeconds: TIMEOUT });
    await runTrainingChunk({ timeoutSeconds: TIMEOUT });
    const before = await readJob();
    expect(before?.state.iterationsDone).toBe(DEFAULT_SPEC.chunkIterations * 2);
    const rowsBefore = before?.rowCount ?? 0;

    // A backdated pair lands inside the window this job had already fixed — the shape an
    // import of older history produces. Both halves are written: a label with no row is
    // dropped by the join and would leave the count unchanged, which is how an earlier
    // version of this test passed while exercising nothing.
    const template = (await allLabels())[0]!;
    const templateRow = (await allFeatureRows())[0]!;
    const backdatedAt = new Date(Date.parse(template.windowEnd) - HOUR).toISOString();
    await putLabels([{ ...template, subject: "news", windowEnd: backdatedAt }]);
    await putFeatureRows([{ ...templateRow, subject: "news", windowEnd: backdatedAt }]);

    const outcome = await runTrainingChunk({ timeoutSeconds: TIMEOUT });

    expect(outcome.restarted).toBe(true);
    expect(outcome.reason).toBe("set-changed");
    expect(outcome.rowCount).toBe(rowsBefore + 1);
    // Back to one chunk's worth: the job began again rather than carrying its old state
    // onto different data.
    expect(outcome.iterationsDone).toBe(DEFAULT_SPEC.chunkIterations);
  });

  it("finishes on the new set after a restart, not the old one", async () => {
    await putEvents(corpus(8));
    await refreshDataset(OPTIONS);
    await runTrainingChunk({ timeoutSeconds: TIMEOUT });

    const template = (await allLabels())[0]!;
    const templateRow = (await allFeatureRows())[0]!;
    const backdatedAt = new Date(Date.parse(template.windowEnd) - HOUR).toISOString();
    await putLabels([{ ...template, subject: "news", windowEnd: backdatedAt }]);
    await putFeatureRows([{ ...templateRow, subject: "news", windowEnd: backdatedAt }]);

    let outcome = await runTrainingChunk({ timeoutSeconds: TIMEOUT });
    expect(outcome.restarted).toBe(true);
    while (outcome.state === "training") {
      outcome = await runTrainingChunk({ timeoutSeconds: TIMEOUT });
    }

    // The reference is recomputed from what is in the stores *now*, so agreeing with it
    // is the assertion that the restart adopted the new set rather than the old.
    expect((await readModel())?.state.weights).toEqual((await referenceModel()).weights);
  });

  it("drops a label with no feature row rather than training on a gap", async () => {
    await putEvents(corpus(4));
    await refreshDataset(OPTIONS);
    const orphan = (await allLabels())[0]!;
    await putLabels([{ ...orphan, subject: "orphan" }]);

    const joined = joinStored(await allFeatureRows(), await allLabels());
    expect(joined.unmatched).toBe(1);
    expect(joined.rows).toHaveLength(joined.outcomes.length);
  });

  it("can be cancelled without touching a model that already exists", async () => {
    await putEvents(corpus(6));
    await refreshDataset(OPTIONS);
    let outcome = await runTrainingChunk({ timeoutSeconds: TIMEOUT });
    while (outcome.state === "training") {
      outcome = await runTrainingChunk({ timeoutSeconds: TIMEOUT });
    }
    const trained = await readModel();

    await runTrainingChunk({ timeoutSeconds: TIMEOUT });
    await cancelTraining();
    expect(await readJob()).toBeUndefined();
    expect(await readModel()).toEqual(trained);
  });
});

describe("what training leaves behind", () => {
  it("keeps rows, labels and the model when raw events expire", async () => {
    // D11 in its strongest form: the person keeps what was learned from their browsing
    // without keeping a record of the browsing itself.
    await putEvents(corpus(10));
    await refreshDataset(OPTIONS);
    let outcome = await runTrainingChunk({ timeoutSeconds: TIMEOUT });
    while (outcome.state === "training") {
      outcome = await runTrainingChunk({ timeoutSeconds: TIMEOUT });
    }

    const rowsBefore = await countFeatureRows();
    const labelsBefore = await countLabels();
    const trained = await readModel();

    const wellAfter = START + 400 * 24 * HOUR;
    const deleted = await enforceRetention({ ...DEFAULT_SETTINGS, rawRetentionDays: 30 }, wellAfter);

    expect(deleted.deleted).toBeGreaterThan(0);
    expect(await countFeatureRows()).toBe(rowsBefore);
    expect(await countLabels()).toBe(labelsBefore);
    expect(await readModel()).toEqual(trained);
  });

  it("is removed entirely by delete-all", async () => {
    // Retention is a promise about how long raw browsing is kept. Deletion is a promise
    // about everything, and a trained model is something learned from a person.
    await putEvents(corpus(6));
    await refreshDataset(OPTIONS);
    let outcome = await runTrainingChunk({ timeoutSeconds: TIMEOUT });
    while (outcome.state === "training") {
      outcome = await runTrainingChunk({ timeoutSeconds: TIMEOUT });
    }
    expect(await readModel()).toBeDefined();

    const removed = await deleteEverything();
    expect(removed.labelsDeleted).toBeGreaterThan(0);
    expect(removed.featureRowsDeleted).toBeGreaterThan(0);
    expect(await readModel()).toBeUndefined();
    expect(await isEmpty()).toBe(true);
  });
});
