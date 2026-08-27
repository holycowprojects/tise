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
import { coverageGaps } from "../storage/coverage";
import {
  allPredictions,
  pendingPredictions,
  putPredictions,
} from "../storage/predictions";
import { loadSettings } from "../storage/settings";
import { buildPredictions } from "./predict";
import type { Prediction } from "./prediction";
import { resolveAll, type ResolutionContext } from "./resolve";
import { readModel } from "./train";

export interface RegistryOutcome {
  readonly created: number;
  readonly resolved: number;
  readonly pending: number;
  readonly counts: Record<string, number>;
  readonly reason?: "no-model" | "not-consented";
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
  };
}
