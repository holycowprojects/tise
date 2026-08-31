/**
 * The prediction registry, and the resolution loop with no human in it.
 *
 * Two properties carry T13. **Resolution is idempotent** — running it twice, or after a
 * restart, or after the worker was killed mid-pass, reaches the same answer — which here
 * is a consequence of `resolveOutcome` being pure rather than something arranged with
 * cursors. And **`expired` is not a miss**: a window Tise did not watch produces no
 * measurement, and the tests below try hard to make it produce a fabricated negative.
 */
import "fake-indexeddb/auto";
import { IDBFactory } from "fake-indexeddb";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { beforeEach, describe, expect, it } from "vitest";
import { closeTiseDb } from "../src/storage/db";
import { deleteEverything, isEmpty } from "../src/storage/delete";
import { putEvents } from "../src/storage/events";
import {
  allPredictions,
  countPredictions,
  predictionCounts,
  putPredictions,
} from "../src/storage/predictions";
import {
  coverageGaps,
  isFullyCovered,
  recordCollectionStarted,
  recordCollectionStopped,
  type CoverageGap,
} from "../src/storage/coverage";
import { saveSettings } from "../src/storage/settings";
import {
  assertStorablePrediction,
  evidenceFor,
  PREDICTION_FIELDS,
  priorSessionsFrom,
} from "../src/model/prediction";
import type { Prediction } from "../src/model/prediction";
import { resolveAll, resolveOutcome, type ResolutionContext } from "../src/model/resolve";
import { migrateResolutionRule, updateRegistry } from "../src/model/registry";
import {
  MODEL_NAME,
  modelName,
  refreshDataset,
  runTrainingChunk,
} from "../src/model/train";
import type { FeatureRow } from "../src/features/vector";
import {
  FEATURE_NAMES,
  FEATURE_SET,
  firstSeenSaturation,
  priorSessionRate,
} from "../src/features/vector";
import type { TiseEvent } from "../src/types";

const HOUR = 3_600_000;
const START = Date.parse("2026-06-01T09:00:00.000Z");
const CONSENT = "2026-05-01T00:00:00.000Z";

function event(category: string, hours: number, eventId: string): TiseEvent {
  const at = new Date(START + hours * HOUR).toISOString();
  return {
    eventId,
    occurredAt: at,
    source: "live",
    domain: "example.com",
    category,
    transition: "link",
    dwellSeconds: null,
    sessionId: at,
  };
}

function prediction(overrides: Partial<Prediction> = {}): Prediction {
  const windowStart = new Date(START).toISOString();
  return {
    predictionId: "return_24h:video:base",
    createdAt: windowStart,
    target: "return_24h",
    subject: "video",
    probability: 0.8,
    windowStart,
    windowEnd: new Date(START + 24 * HOUR).toISOString(),
    abstained: false,
    modelName: "logreg_fs3",
    modelVersion: "cal_1@2026-06-01T00:00:00.000Z",
    featureSet: FEATURE_SET,
    dataCutoff: windowStart,
    evidence: ["seen on 3 days in the last week"],
    outcome: "pending",
    resolvedAt: null,
    ...overrides,
  };
}

function context(overrides: Partial<ResolutionContext> = {}): ResolutionContext {
  return {
    events: [],
    gaps: [],
    consentGrantedAt: CONSENT,
    now: START + 48 * HOUR,
    earliestRetained: new Date(START - 30 * 24 * HOUR).toISOString(),
    ...overrides,
  };
}

beforeEach(async () => {
  await closeTiseDb();
  globalThis.indexedDB = new IDBFactory();
});

describe("what a prediction is allowed to be", () => {
  it("accepts exactly the fields SPEC.md declares", () => {
    expect(Object.keys(prediction()).sort()).toEqual([...PREDICTION_FIELDS].sort());
  });

  it("refuses a field nobody declared", () => {
    const rogue = { ...prediction(), url: "https://example.com/secret" };
    expect(() => assertStorablePrediction(rogue as Prediction)).toThrow(/unexpected/);
  });

  it("refuses evidence that looks like a URL", () => {
    // Evidence is free text assembled from features, and free text is where a path would
    // end up if anyone ever built one there.
    expect(() =>
      assertStorablePrediction(prediction({ evidence: ["seen at /watch?v=abc"] })),
    ).toThrow(/URL/);
    expect(() =>
      assertStorablePrediction(prediction({ evidence: ["https://example.com"] })),
    ).toThrow(/URL/);
  });

  it("refuses a prediction that used data from inside its own window", () => {
    // dataCutoff drifting past windowStart is the leak this schema exists to prevent, and
    // it would be invisible in every score.
    expect(() =>
      assertStorablePrediction(
        prediction({ dataCutoff: new Date(START + HOUR).toISOString() }),
      ),
    ).toThrow(/dataCutoff/);
  });

  it("refuses a window that ends before it starts", () => {
    expect(() =>
      assertStorablePrediction(prediction({ windowEnd: prediction().windowStart })),
    ).toThrow(/end after it starts/);
  });

  it("refuses an outcome and a resolution instant that disagree", () => {
    expect(() => assertStorablePrediction(prediction({ outcome: "hit" }))).toThrow(
      /disagree/,
    );
    expect(() =>
      assertStorablePrediction(prediction({ resolvedAt: "2026-06-02T00:00:00.000Z" })),
    ).toThrow(/disagree/);
  });

  it("refuses a probability outside [0, 1]", () => {
    expect(() => assertStorablePrediction(prediction({ probability: 1.2 }))).toThrow();
  });

  it("validates every row before opening the transaction", async () => {
    // One bad row writes none of the batch rather than half of it.
    const bad = { ...prediction({ subject: "dev" }), url: "x" } as Prediction;
    await expect(putPredictions([prediction(), bad])).rejects.toThrow();
    expect(await countPredictions()).toBe(0);
  });
});

describe("resolution, with nobody asked", () => {
  it("calls it a hit when the subject recurs inside the window", () => {
    const events = [event("video", 5, "a")];
    expect(resolveOutcome(prediction(), context({ events }))).toBe("hit");
  });

  it("ignores a recurrence in a different category", () => {
    const events = [event("dev", 5, "a")];
    expect(resolveOutcome(prediction(), context({ events }))).toBe("miss");
  });

  it("never lets the session that produced it satisfy it", () => {
    // An event exactly at windowStart is inside the session being predicted from. If it
    // counted, almost every prediction would be a hit and it would look like a triumph.
    const events = [event("video", 0, "a")];
    expect(resolveOutcome(prediction(), context({ events }))).toBe("miss");
  });

  it("counts a recurrence exactly on the closing edge", () => {
    // Half-open at the start, closed at the end — the same convention labels.ts uses.
    const events = [event("video", 24, "a")];
    expect(resolveOutcome(prediction(), context({ events }))).toBe("hit");
  });

  it("does not count a recurrence a moment past the window", () => {
    const events = [event("video", 24.001, "a")];
    expect(resolveOutcome(prediction(), context({ events }))).toBe("miss");
  });

  it("stays pending while the window is still open", () => {
    expect(resolveOutcome(prediction(), context({ now: START + 5 * HOUR }))).toBe(
      "pending",
    );
  });

  it("declares a hit the moment it happens, without waiting for the window", () => {
    const events = [event("video", 2, "a")];
    expect(
      resolveOutcome(prediction(), context({ events, now: START + 3 * HOUR })),
    ).toBe("hit");
  });

  it("never revisits an outcome it already reached", () => {
    const settled = prediction({ outcome: "miss", resolvedAt: "2026-06-02T09:00:00.000Z" });
    const events = [event("video", 5, "a")];
    expect(resolveOutcome(settled, context({ events }))).toBe("miss");
  });
});

describe("expired is not a miss", () => {
  it("expires a window Tise was paused for", () => {
    const gaps: CoverageGap[] = [
      { from: new Date(START + 2 * HOUR).toISOString(), to: new Date(START + 6 * HOUR).toISOString() },
    ];
    expect(resolveOutcome(prediction(), context({ gaps }))).toBe("expired");
  });

  it("expires a window that opened before consent was ever given", () => {
    expect(
      resolveOutcome(
        prediction(),
        context({ consentGrantedAt: new Date(START + HOUR).toISOString() }),
      ),
    ).toBe("expired");
  });

  it("expires a window whose events retention already deleted", () => {
    // "No return was seen" would mean "no return survived", which is a different sentence.
    expect(
      resolveOutcome(
        prediction(),
        context({ earliestRetained: new Date(START + HOUR).toISOString() }),
      ),
    ).toBe("expired");
  });

  it("expires when nothing is stored at all", () => {
    expect(resolveOutcome(prediction(), context({ earliestRetained: null }))).toBe(
      "expired",
    );
  });

  it("does not call a hit a hit through a gap — reversed, and here is what it cost", () => {
    // **This test asserted the opposite until D107, and its old argument was not silly:**
    // "a return that *was* observed is evidence regardless of what was missed around it;
    // only the negative needs full coverage to be trustworthy."
    //
    // That reasoning holds for one row and fails for any *rate* computed over rows. If a
    // hit scores under partial coverage and a miss does not, the scored set is biased
    // toward positives by construction, and the scorecard's accuracy stops meaning
    // anything. On a real profile it produced 192 hits against 1 miss — 99.5% — where the
    // same target measured 73.2% on the same browsing.
    //
    // It also conflated two cases. Under a partial gap, a return seen in a covered stretch
    // really was observed. But a window lying entirely *before consent* observed nothing at
    // all: its "return" is read out of imported history, and D88 is explicit that an import
    // may set the yardstick and only live collection may score. Every one of those 192 was
    // the second case.
    //
    // What is given up is real: a genuinely observed return inside a partially covered
    // window is now discarded rather than scored. That is the price of a scored set whose
    // rate can be read, and it is paid knowingly.
    const gaps: CoverageGap[] = [
      { from: new Date(START + 2 * HOUR).toISOString(), to: new Date(START + 6 * HOUR).toISOString() },
    ];
    const events = [event("video", 1, "a")];
    expect(resolveOutcome(prediction(), context({ gaps, events }))).toBe("expired");
  });

  it("scores neither outcome for a window that opened before consent", () => {
    // The case that actually happened. An imported history predates consent entirely, so
    // nothing in it was ever observed by Tise — and a recurrence found there must not
    // score, in either direction.
    const before = context({
      consentGrantedAt: new Date(START + 48 * HOUR).toISOString(),
      events: [event("video", 5, "a")],
    });
    expect(resolveOutcome(prediction(), before)).toBe("expired");
    expect(resolveOutcome(prediction(), { ...before, events: [] })).toBe("expired");
  });

  it("scores both outcomes for a window it did watch", () => {
    // The symmetry the fix is for: with full coverage, the same context resolves to a hit
    // or a miss according to the events alone.
    const covered = context({ gaps: [] });
    expect(resolveOutcome(prediction(), { ...covered, events: [event("video", 5, "a")] })).toBe(
      "hit",
    );
    expect(resolveOutcome(prediction(), { ...covered, events: [] })).toBe("miss");
  });

  it("treats a gap that is still open as covering everything after it", () => {
    const gaps: CoverageGap[] = [
      { from: new Date(START + 2 * HOUR).toISOString(), to: null },
    ];
    expect(resolveOutcome(prediction(), context({ gaps }))).toBe("expired");
  });

  it("leaves a window that ends before the gap starts alone", () => {
    const gaps: CoverageGap[] = [
      { from: new Date(START + 48 * HOUR).toISOString(), to: null },
    ];
    expect(resolveOutcome(prediction(), context({ gaps }))).toBe("miss");
  });
});

describe("coverage bookkeeping", () => {
  it("opens one gap however many times stopping is recorded", async () => {
    await recordCollectionStopped(START);
    await recordCollectionStopped(START + HOUR);
    expect(await coverageGaps()).toHaveLength(1);
  });

  it("closes the open gap and leaves it closed", async () => {
    await recordCollectionStopped(START);
    await recordCollectionStarted(START + HOUR);
    await recordCollectionStarted(START + 2 * HOUR);
    const gaps = await coverageGaps();
    expect(gaps).toHaveLength(1);
    expect(gaps[0]?.to).toBe(new Date(START + HOUR).toISOString());
  });

  it("records a gap when the settings say collection stopped", async () => {
    // Hooked into saveSettings rather than the popup, so every route in is covered —
    // including consent withdrawal and delete-all.
    await saveSettings({ consentGrantedAt: CONSENT, paused: false });
    expect(await coverageGaps()).toHaveLength(0);
    await saveSettings({ paused: true });
    expect(await coverageGaps()).toHaveLength(1);
    await saveSettings({ paused: false });
    expect((await coverageGaps())[0]?.to).not.toBeNull();
  });

  it("records a gap when consent is withdrawn, not only when paused", async () => {
    await saveSettings({ consentGrantedAt: CONSENT });
    await saveSettings({ consentGrantedAt: null });
    expect(await coverageGaps()).toHaveLength(1);
  });

  it("treats any overlap at all as a hole", () => {
    // "Mostly watched" would need a threshold nobody measured.
    const gaps: CoverageGap[] = [
      { from: new Date(START + 23 * HOUR).toISOString(), to: new Date(START + 23.5 * HOUR).toISOString() },
    ];
    expect(isFullyCovered(START, START + 24 * HOUR, gaps, CONSENT, START + 48 * HOUR)).toBe(
      false,
    );
  });
});

describe("the registry pass", () => {
  async function seed(): Promise<void> {
    await saveSettings({ consentGrantedAt: CONSENT });
    await putEvents([event("video", 0, "a"), event("video", 5, "b")]);
  }

  it("does nothing before consent", async () => {
    const outcome = await updateRegistry({ now: START + 48 * HOUR });
    expect(outcome.reason).toBe("not-consented");
    expect(await countPredictions()).toBe(0);
  });

  it("does nothing before a model exists", async () => {
    // A 0.5 from an untrained model is a made-up number wearing the schema of a measured
    // one, so no rows at all is the honest output.
    await seed();
    const outcome = await updateRegistry({ now: START + 48 * HOUR });
    expect(outcome.reason).toBe("no-model");
    expect(await countPredictions()).toBe(0);
  });

  it("resolves stored predictions and is idempotent", async () => {
    await seed();
    await putPredictions([prediction()]);

    const events = [event("video", 0, "a"), event("video", 5, "b")];
    const first = resolveAll([prediction()], context({ events }));
    expect(first.resolved).toHaveLength(1);
    expect(first.resolved[0]?.outcome).toBe("hit");

    // Feeding the already-resolved row back through changes nothing at all.
    const second = resolveAll(first.resolved, context({ events }));
    expect(second.resolved).toHaveLength(0);
  });

  it("survives being run again after a restart", async () => {
    await seed();
    await putPredictions([prediction()]);
    await closeTiseDb();

    const stored = await allPredictions();
    const events = [event("video", 5, "b")];
    const once = resolveAll(stored, context({ events }));
    await putPredictions(once.resolved);
    await closeTiseDb();

    const again = resolveAll(await allPredictions(), context({ events }));
    expect(again.resolved).toHaveLength(0);
    expect((await allPredictions())[0]?.outcome).toBe("hit");
  });

  it("counts outcomes for the surface that displays them", async () => {
    await putPredictions([
      prediction({ subject: "video", outcome: "hit", resolvedAt: "2026-06-02T09:00:00.000Z" }),
      prediction({ subject: "dev", outcome: "miss", resolvedAt: "2026-06-02T09:00:00.000Z" }),
      prediction({ subject: "news" }),
    ]);
    expect(await predictionCounts()).toEqual({ hit: 1, miss: 1, pending: 1 });
  });
});

describe("the whole loop, with a real trained model", () => {
  /**
   * Everything above tests `updateRegistry`'s refusals and `resolveAll` directly, which
   * left the path between them untested — and a deliberate break proved it: removing the
   * filter that stops the pass rewriting existing predictions failed **nothing**. That
   * break resets a resolved outcome back to `pending`, silently erasing a measurement, so
   * it is exactly the kind of thing this suite exists to catch.
   *
   * The same shape of hole as T10's oracle-reading assertions and T12's untouched logit
   * clamp: a real code path with no test through it.
   */
  async function trainedProfile(): Promise<void> {
    await saveSettings({ consentGrantedAt: CONSENT });
    const events: TiseEvent[] = [];
    for (let day = 0; day < 12; day += 1) {
      events.push(event("video", day * 24, `v${day}`));
      events.push(event("video", day * 24 + 0.25, `v${day}b`));
      if (day % 4 === 0) events.push(event("dev", day * 24 + 3, `d${day}`));
    }
    await putEvents(events);
    await refreshDataset({ timeoutSeconds: 1800, horizonHours: 24 });
    let outcome = await runTrainingChunk({ timeoutSeconds: 1800 });
    while (outcome.state === "training") {
      outcome = await runTrainingChunk({ timeoutSeconds: 1800 });
    }
    expect(outcome.state).toBe("done");
  }

  const NOW = START + 20 * 24 * HOUR;

  it("creates predictions for closed sessions and resolves them", async () => {
    await trainedProfile();
    const first = await updateRegistry({ now: NOW });

    expect(first.reason).toBeUndefined();
    expect(first.created).toBeGreaterThan(0);
    expect(await countPredictions()).toBe(first.created);

    const stored = await allPredictions();
    expect(stored.every((p) => p.outcome !== "pending")).toBe(true);
    expect(stored.some((p) => p.outcome === "hit")).toBe(true);
  });

  it("creates nothing on a second pass and never resets a resolved outcome", async () => {
    await trainedProfile();
    await updateRegistry({ now: NOW });
    const before = await allPredictions();

    const second = await updateRegistry({ now: NOW });
    expect(second.created).toBe(0);
    expect(second.resolved).toBe(0);

    const after = await allPredictions();
    expect(after).toEqual(before);
    expect(after.every((p) => p.outcome !== "pending")).toBe(true);
  });

  it("survives the worker dying between passes", async () => {
    await trainedProfile();
    await updateRegistry({ now: NOW });
    const before = await allPredictions();

    await closeTiseDb();
    await updateRegistry({ now: NOW });
    expect(await allPredictions()).toEqual(before);
  });

  it("does not predict from a session that is still open", async () => {
    // `now` sits inside the last session's timeout, so that session is still growing and
    // any prediction from it would change as more events arrive.
    await trainedProfile();
    const lastEventAt = START + 11 * 24 * HOUR + 0.25 * HOUR;
    await updateRegistry({ now: lastEventAt + 60_000 });

    const windows = (await allPredictions()).map((p) => Date.parse(p.windowStart));
    expect(Math.max(...windows)).toBeLessThan(lastEventAt);
  });

  it("records the model that produced each prediction", async () => {
    await trainedProfile();
    await updateRegistry({ now: NOW });
    for (const stored of await allPredictions()) {
      expect(stored.modelName).toBe(MODEL_NAME);
      expect(stored.modelVersion).toMatch(/^cal_1@/);
      expect(stored.featureSet).toBe(FEATURE_SET);
      expect(stored.dataCutoff).toBe(stored.windowStart);
      // The pairing, not either half. This assertion is the one that was missing: the
      // literal above used to read `logreg_fs2` while the line under it derived `fs_3`,
      // so the test passed while pinning the contradiction in place.
      expect(stored.modelName).toBe(modelName(stored.featureSet));
    }
  });

  it("withholds nothing on confidence any more (D88)", async () => {
    // This test used to assert the opposite, and asserting the opposite was correct at the
    // time: D70 found no threshold that certified the 90% target on any fold, so every
    // prediction was abstained and a registry keeping only the displayed ones would have
    // been empty. D88 retired that rule — show everything, always with its denominator —
    // and this half of the replacement was owed until now. The floor that remains is on
    // evidence, and it lives in `model/nextCategory.ts`, not on a probability.
    await trainedProfile();
    await updateRegistry({ now: NOW });
    const stored = await allPredictions();
    expect(stored.length).toBeGreaterThan(0);
    expect(stored.every((p) => !p.abstained)).toBe(true);
  });

  it("still stores every category in a closed session", async () => {
    // The reason the registry exists is unchanged by D88: a scorecard that kept only the
    // rows someone chose to look at could never say whether the choosing was right.
    await trainedProfile();
    await updateRegistry({ now: NOW });
    const stored = await allPredictions();
    expect(new Set(stored.map((p) => p.subject)).size).toBeGreaterThan(1);
  });
});

describe("what the registry leaves behind", () => {
  it("is removed entirely by delete-all", async () => {
    await putPredictions([prediction()]);
    const removed = await deleteEverything();
    expect(removed.predictionsDeleted).toBe(1);
    expect(await isEmpty()).toBe(true);
  });
});

describe("evidence", () => {
  function row(values: Partial<Record<string, number | null>>): FeatureRow {
    const base = Object.fromEntries(FEATURE_NAMES.map((name) => [name, null]));
    return {
      subject: "video",
      windowEnd: new Date(START).toISOString(),
      featureSet: FEATURE_SET,
      compat: "history",
      values: { ...base, ...values } as FeatureRow["values"],
    };
  }

  it("describes features, never raw browsing", () => {
    const lines = evidenceFor(row({ daysSeen7d: 4, eventCount30d: 12 }));
    expect(lines).toContain("seen on 4 days in the last week");
    for (const line of lines) expect(line).not.toMatch(/https?:|\//);
  });

  it("skips absent features rather than describing them", () => {
    // "We have never seen this" is true and is not evidence *for* anything. A list padded
    // with absences reads as though the model knew more than it did.
    expect(evidenceFor(row({}))).toEqual([]);
  });

  it("says how much the return rate rests on", () => {
    // A rate built on two sessions must read differently from one built on forty (D52).
    //
    // `fs_3` stores a saturated rate, so the count is recovered by inverting both
    // transforms. Building the row through the same functions the extension uses makes
    // this a round-trip test as well: two sessions in, "2 sessions" out.
    const lines = evidenceFor(
      row({
        priorReturnRate: 0.5,
        firstSeenSaturation: firstSeenSaturation(7 * 24),
        priorSessionRate: priorSessionRate(2, 7 * 24),
      }),
    );
    expect(lines.some((line) => line.includes("2 sessions"))).toBe(true);
  });

  it("recovers the prior session count exactly, across a range of them", () => {
    // The inverse has to be exact rather than approximate, because the number it produces
    // is shown to a person as evidence. Checked at several ages and counts, since the two
    // transforms compose and an error in either would show up as an off-by-a-bit.
    for (const hours of [24, 168, 24 * 90]) {
      for (const count of [1, 2, 7, 40]) {
        const recovered = priorSessionsFrom(
          row({
            firstSeenSaturation: firstSeenSaturation(hours),
            priorSessionRate: priorSessionRate(count, hours),
          }),
        );
        expect(recovered).toBe(count);
      }
    }
  });

  it("has no session count to report when the category was never seen", () => {
    expect(priorSessionsFrom(row({ firstSeenSaturation: null }))).toBeNull();
  });

  it("gets singulars right, because evidence a person reads should read properly", () => {
    const lines = evidenceFor(row({ daysSeen7d: 1, eventCount30d: 1 }));
    expect(lines).toContain("seen on 1 day in the last week");
    expect(lines).toContain("1 visit in the last 30 days");
  });
});

/**
 * Both ways of training must end in the same state, not merely produce the same model.
 *
 * This is a source guard rather than a behavioural test, for the same reason
 * `manifest.test.ts` is one: the service worker registers its listeners against the real
 * `chrome` object at module load, so there is nothing here to call. What can be checked is
 * the wiring, and the wiring is exactly what was wrong.
 *
 * The alarm path trained and then called `updateRegistry`. The "Train now" button trained
 * and stopped, so pressing it produced a fresh model, no predictions, and a wait of up to
 * `TRAINING_PERIOD_MINUTES` — six hours — with nothing on screen explaining it. The
 * background module's own docstring claimed the two paths were equivalent because both go
 * through `runTrainingChunk`; they produced the same model, and only one of them used it.
 */
describe("both training paths reach the same state", () => {
  const SOURCE = readFileSync(
    fileURLToPath(new URL("../src/background.ts", import.meta.url)),
    "utf8",
  );

  /** The body of the `tise:train` message listener, from its type guard to end of file. */
  function trainListener(): string {
    const start = SOURCE.indexOf("isTrainMessage(message)");
    expect(start, "the train listener moved; this guard needs updating").toBeGreaterThan(0);
    return SOURCE.slice(start);
  }

  it("updates the registry after on-demand training", () => {
    expect(trainListener()).toContain("updateRegistry");
  });

  it("still updates the registry on the alarm path", () => {
    const alarms = SOURCE.slice(
      SOURCE.indexOf("chrome.alarms.onAlarm.addListener"),
      SOURCE.indexOf("interface ImportMessage"),
    );
    expect(alarms).toContain("updateRegistry");
  });

  it("calls it from both places rather than one", () => {
    // A single call site that happened to sit in the shared prefix would satisfy both
    // assertions above while leaving one path broken.
    const calls = SOURCE.split("updateRegistry(").length - 1;
    expect(calls).toBeGreaterThanOrEqual(2);
  });
});

/**
 * Dropping outcomes a superseded rule wrote.
 *
 * D105's rule, applied on the day it was written: a stored shape that acquires a version
 * needs a migration **and a test that writes the old shape**, in the same commit. Every
 * other test here creates its predictions through the current code, so none of them can
 * construct a store left behind by an earlier build — which is exactly how the stale
 * preprocessor and these outcomes both survived a full suite.
 */
describe("outcomes from a superseded resolution rule", () => {
  it("drops them, because resolution never revisits a settled outcome", async () => {
    // The rows written by rule 1: hits declared from imported evidence, before any
    // coverage check. Nothing would ever have looked at them again.
    await putPredictions([
      prediction({ predictionId: "a", outcome: "hit", resolvedAt: CONSENT }),
      prediction({ predictionId: "b", subject: "dev", outcome: "hit", resolvedAt: CONSENT }),
    ]);
    expect(await countPredictions()).toBe(2);

    expect(await migrateResolutionRule()).toBe(2);
    expect(await countPredictions()).toBe(0);
  });

  it("runs once, not on every pass", async () => {
    await putPredictions([prediction({ outcome: "hit", resolvedAt: CONSENT })]);
    expect(await migrateResolutionRule()).toBe(1);

    await putPredictions([prediction({ predictionId: "fresh" })]);
    // A migration that ran every time would delete rows the current rule just wrote.
    expect(await migrateResolutionRule()).toBe(0);
    expect(await countPredictions()).toBe(1);
  });

  it("repeats the clear if it was interrupted before the marker was written", async () => {
    // The marker is written after the clear, so a worker killed between the two repeats
    // the clear. Repeating costs a rebuild; skipping leaves wrong numbers on screen.
    await putPredictions([prediction({ outcome: "hit", resolvedAt: CONSENT })]);
    expect(await migrateResolutionRule()).toBe(1);
    expect(await migrateResolutionRule()).toBe(0);
  });

  it("is harmless on a store that never held a prediction", async () => {
    expect(await migrateResolutionRule()).toBe(0);
    expect(await countPredictions()).toBe(0);
  });
});
