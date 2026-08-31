/**
 * The pass that keeps the registry current: predict what is new, resolve what has closed.
 *
 * Runs on the same alarm as training. Both halves are idempotent, so it does not matter
 * how often it runs, whether it ran already today, or whether the worker was killed
 * halfway through — there is no cursor and no partial progress. That is the property that
 * makes "correct across browser restarts" a consequence of the design rather than
 * something to test for and hope.
 */
import { allEvents, earliestEventAt } from "../storage/events";
import { readMeta, writeMeta } from "../storage/db";
import { coverageGaps } from "../storage/coverage";
import {
  allPredictions,
  clearPredictions,
  pendingPredictions,
  putPredictions,
} from "../storage/predictions";
import { loadSettings } from "../storage/settings";
import { buildPredictions } from "./predict";
import type { Prediction } from "./prediction";
import { resolveAll, type ResolutionContext } from "./resolve";
import { readModel } from "./train";

/**
 * Which version of the resolution rule produced the stored outcomes.
 *
 * **Rule 2 (D107) fixed a resolution that could not produce a `miss`.** Version 1 scanned
 * for a recurrence before checking coverage, so a window Tise never watched — all of an
 * imported history — resolved `hit` from imported evidence or `expired` from its absence,
 * and never `miss`. On a real profile that read 192 hits against 1 miss, against a measured
 * base rate of 73.2% for the same target on the same browsing.
 *
 * Resolution never revisits a settled outcome, by design and for good reason, so those rows
 * would have stayed wrong forever. They are **discarded and rebuilt** rather than re-read:
 * a prediction is fully regenerable from the events and the coverage log, so nothing is
 * lost that was ever measured — only outcomes a rule now known to be wrong wrote down.
 *
 * This is D105's rule applied on the day it was written: a stored shape that acquires a
 * version needs a migration and a test that writes the old shape, in the same commit.
 */
export const RESOLUTION_RULE = 2;

const RULE_KEY = "resolution:rule";

/**
 * Drop outcomes written by a superseded resolution rule, once.
 *
 * Returns how many were discarded. Writes the marker **after** clearing, so an interrupted
 * run repeats the clear rather than skipping it — the pass is idempotent either way, and
 * clearing twice costs a rebuild while skipping it leaves wrong numbers on screen.
 */
export async function migrateResolutionRule(): Promise<number> {
  const stored = await readMeta<number>(RULE_KEY);
  if (stored === RESOLUTION_RULE) return 0;
  const dropped = await clearPredictions();
  await writeMeta(RULE_KEY, RESOLUTION_RULE);
  return dropped;
}

export interface RegistryOutcome {
  readonly created: number;
  readonly resolved: number;
  readonly pending: number;
  readonly counts: Record<string, number>;
  readonly reason?: "no-model" | "not-consented";
  /** Rows dropped because a superseded resolution rule wrote them. One-off; see below. */
  readonly discarded?: number;
}

/**
 * Create predictions for newly closed sessions, then resolve whatever has come due.
 *
 * Creation runs first so that a session which closed and was returned to inside the same
 * gap between alarms still gets a prediction *and* its resolution in one pass, rather than
 * waiting for the next one to notice it.
 *
 * Existing predictions are never overwritten by the creation step. `buildPredictions`
 * would happily rebuild a row for a session it has already covered, and doing so would
 * reset a resolved outcome back to `pending` — quietly erasing the measurement. So already
 * known windows are filtered out before the write.
 */
export async function updateRegistry(options: {
  readonly now: number;
}): Promise<RegistryOutcome> {
  const settings = await loadSettings();
  if (settings.consentGrantedAt === null) {
    return {
      created: 0,
      resolved: 0,
      pending: 0,
      counts: {},
      reason: "not-consented",
    };
  }

  // Before anything reads them: outcomes from a superseded rule are dropped and rebuilt.
  const discarded = await migrateResolutionRule();

  const model = await readModel();
  if (model === undefined) {
    // Nothing to predict with. A 0.5 from an untrained model is a made-up number wearing
    // the schema of a measured one.
    return { created: 0, resolved: 0, pending: 0, counts: {}, reason: "no-model" };
  }

  const events = await allEvents();
  const existing = await allPredictions();
  const known = new Set(
    existing.map((prediction) => `${prediction.target}:${prediction.subject}:${prediction.windowStart}`),
  );

  const fresh = buildPredictions(events, model, {
    timeoutSeconds: settings.sessionTimeoutSeconds,
    now: options.now,
  }).filter(
    (prediction) =>
      !known.has(`${prediction.target}:${prediction.subject}:${prediction.windowStart}`),
  );
  await putPredictions(fresh);

  const context: ResolutionContext = {
    events,
    gaps: await coverageGaps(),
    consentGrantedAt: settings.consentGrantedAt,
    now: options.now,
    earliestRetained: await earliestEventAt(),
  };
  const pending: Prediction[] = [...(await pendingPredictions()), ...fresh];
  const { resolved, counts } = resolveAll(pending, context);
  await putPredictions(resolved);

  return {
    created: fresh.length,
    resolved: resolved.length,
    pending: counts.pending,
    counts: { ...counts },
    ...(discarded > 0 ? { discarded } : {}),
  };
}
