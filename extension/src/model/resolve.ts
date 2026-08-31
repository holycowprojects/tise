/**
 * Resolving predictions against what actually happened. No user involvement anywhere.
 *
 * D6: there is no confirmation button in this loop. A person asked "did you mean to do
 * that?" answers to be agreeable, and a reliability curve built on agreeable answers
 * measures politeness. The outcome is read off the event stream or it is not read at all.
 *
 * **The three-way outcome is the whole design.** `hit` and `miss` are measurements.
 * `expired` is the absence of one, and keeping it separate is D52's rule applied to a new
 * place: there, prior sessions whose horizon had not elapsed were excluded from both sides
 * of the ratio rather than counted as misses. Here, a window Tise did not watch is
 * excluded from scoring rather than counted as a miss. In both cases "count it as a miss"
 * is the tempting shortcut, looks conservative, and manufactures a negative.
 *
 * **Resolution is a pure function**, so it is idempotent by construction rather than by
 * care. Running it twice, or after a browser restart, or after the worker was killed
 * mid-pass, reaches the same answer from the same stored state — there is no cursor to
 * lose and no partial progress to reconcile.
 */
import type { TiseEvent } from "../types";
import type { CoverageGap } from "../storage/coverage";
import { isFullyCovered } from "../storage/coverage";
import type { Prediction, PredictionOutcome } from "./prediction";

export interface ResolutionContext {
  readonly events: readonly TiseEvent[];
  readonly gaps: readonly CoverageGap[];
  readonly consentGrantedAt: string | null;
  readonly now: number;
  /**
   * Oldest event Tise still holds, or `null` when it holds none. A window that opened
   * before this cannot be checked: retention deleted the evidence, and "no return was
   * seen" would mean "no return survived", which is a different sentence.
   */
  readonly earliestRetained: string | null;
}

/**
 * What one prediction should say now. Pure, and the only place the rules live.
 *
 * A recurrence counts when it falls **strictly after** `windowStart` and at or before
 * `windowEnd` — the same half-open convention `labels.ts` uses, for the same reason:
 * activity inside the session that produced the prediction must never be able to satisfy
 * it. Getting this wrong would make almost every prediction a hit and look like a triumph.
 */
export function resolveOutcome(
  prediction: Prediction,
  context: ResolutionContext,
): PredictionOutcome {
  if (prediction.outcome !== "pending") return prediction.outcome;

  const start = Date.parse(prediction.windowStart);
  const end = Date.parse(prediction.windowEnd);

  // **Coverage is decided before any outcome, and the order is the whole correctness
  // argument.** This function used to scan for a recurrence first and check coverage
  // afterwards, so a `hit` was declared from evidence a `miss` was not allowed to use.
  // Every window that opened before Tise was collecting — which is all of an imported
  // history — could therefore resolve `hit` or `expired` and never `miss`. On a real
  // profile that produced 192 hits against 1 miss, a scorecard reading 99.5% where the
  // measured base rate of the same target on the same data is 73.2%.
  //
  // The docstring above already names the mirror image of this mistake: counting an
  // unwatched window as a miss "looks conservative and manufactures a negative". Scanning
  // for hits first manufactures a positive, which is the same error pointing the other
  // way and the one that flatters the project.
  //
  // It is also D88's rule — **an import may set the yardstick, only live collection may
  // score** — which this violated in the direction nobody would question.
  //
  // The elapsed part of the window is what is checked, not the whole of it: a gap that
  // has already happened can never be filled, so an open window with a hole in it is
  // unscoreable now rather than at its close.
  const elapsed = Math.min(end, context.now);
  if (
    !isFullyCovered(start, elapsed, context.gaps, context.consentGrantedAt, context.now)
  ) {
    return "expired";
  }
  if (context.earliestRetained === null) {
    // Nothing is stored at all, so there is nothing to have found. Cannot be a miss.
    return "expired";
  }
  if (Date.parse(context.earliestRetained) > start) {
    // Retention removed the window's events before anyone looked. Rare with a 30-day
    // window and a 24-hour horizon, and it is a real hole rather than an impossible one.
    return "expired";
  }

  for (const event of context.events) {
    if (event.category !== prediction.subject) continue;
    const at = Date.parse(event.occurredAt);
    if (at > start && at <= end) return "hit";
  }

  // A hit can still be declared the instant it happens — the scan above runs before this
  // — but only for a window Tise actually watched.
  if (context.now <= end) return "pending";
  return "miss";
}

export interface ResolutionOutcome {
  readonly resolved: Prediction[];
  readonly counts: Record<PredictionOutcome, number>;
}

/**
 * Apply `resolveOutcome` to a batch, returning only the ones that changed.
 *
 * Returning only changes keeps the write small and makes idempotence visible: a second
 * pass over the same state returns an empty list, which a test can assert directly rather
 * than inferring from row counts.
 */
export function resolveAll(
  predictions: readonly Prediction[],
  context: ResolutionContext,
): ResolutionOutcome {
  const resolved: Prediction[] = [];
  const counts: Record<PredictionOutcome, number> = {
    pending: 0,
    hit: 0,
    miss: 0,
    expired: 0,
  };

  for (const prediction of predictions) {
    const outcome = resolveOutcome(prediction, context);
    counts[outcome] += 1;
    if (outcome === prediction.outcome) continue;
    resolved.push({
      ...prediction,
      outcome,
      resolvedAt: outcome === "pending" ? null : new Date(context.now).toISOString(),
    });
  }
  return { resolved, counts };
}
