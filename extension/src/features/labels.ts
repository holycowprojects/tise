/**
 * Generate `return_24h` labels.
 *
 * PARITY-CRITICAL: `research/tise_research/features/labels.py` is the mirror. Until now
 * the oracle's `labels` section was the one part TypeScript did not check — the fixture
 * key-set guard existed precisely so that gap could not hide. This closes it.
 *
 * One label per (category, session), per D16. The window closes at the **end of the
 * session**; the label is positive if that category is seen again strictly after the
 * close and within the horizon.
 *
 * Two properties matter more than the arithmetic:
 *
 * * **Every label carries an explicit `windowEnd`.** Nothing downstream has to infer when
 *   a label became knowable.
 * * **A label is decided only by events strictly after its `windowEnd`.** Activity inside
 *   the session that produced it can never make it positive. That is the leakage guard in
 *   its simplest form.
 */
import type { TiseEvent } from "../types";
import { sessionise } from "./sessions";

export const DEFAULT_HORIZON_HOURS = 24;

export const TARGET = "return_24h";

/**
 * One training example.
 *
 * `windowEnd` is the instant the label became decidable. A feature vector for this label
 * may look at everything strictly before it and nothing at or after it.
 */
export interface Label {
  readonly target: string;
  readonly subject: string;
  readonly windowEnd: string;
  readonly outcome: boolean;
  readonly horizonHours: number;
  readonly sessionId: string;
}

/**
 * Index of the first element strictly greater than `target`.
 *
 * Mirrors Python's `bisect_right`, which is what makes the horizon boundary strictly
 * after `windowEnd` even when an event lands exactly on it.
 */
function firstAfter(sorted: readonly number[], target: number): number {
  let low = 0;
  let high = sorted.length;
  while (low < high) {
    const mid = (low + high) >> 1;
    if ((sorted[mid] as number) <= target) low = mid + 1;
    else high = mid;
  }
  return low;
}

/**
 * (windowEnd, category, sessionId) for every (category, session) combination.
 *
 * Separated from outcome resolution so the two can be tested apart, and so a future target
 * with the same subjects but a different horizon reuses this unchanged.
 */
export function sessionLabelPairs(
  events: readonly TiseEvent[],
  timeoutSeconds: number,
): Array<{ windowEnd: string; category: string; sessionId: string }> {
  const pairs: Array<{ windowEnd: string; category: string; sessionId: string }> = [];
  for (const session of sessionise(events, timeoutSeconds)) {
    for (const category of [...session.categories].sort()) {
      pairs.push({ windowEnd: session.endedAt, category, sessionId: session.sessionId });
    }
  }
  return pairs;
}

/** Emit one `return_24h` label per (category, session), in window-end order. */
export function return24hLabels(
  events: readonly TiseEvent[],
  timeoutSeconds: number,
  horizonHours: number = DEFAULT_HORIZON_HOURS,
): Label[] {
  if (events.length === 0) return [];

  const byCategory = new Map<string, number[]>();
  for (const event of events) {
    const moments = byCategory.get(event.category);
    const at = Date.parse(event.occurredAt);
    if (moments === undefined) byCategory.set(event.category, [at]);
    else moments.push(at);
  }
  for (const moments of byCategory.values()) moments.sort((a, b) => a - b);

  const horizonMs = horizonHours * 3_600_000;
  const labels: Label[] = [];

  for (const pair of sessionLabelPairs(events, timeoutSeconds)) {
    const moments = byCategory.get(pair.category) ?? [];
    const windowEnd = Date.parse(pair.windowEnd);
    const index = firstAfter(moments, windowEnd);
    const outcome =
      index < moments.length && (moments[index] as number) <= windowEnd + horizonMs;
    labels.push({
      target: TARGET,
      subject: pair.category,
      windowEnd: pair.windowEnd,
      outcome,
      horizonHours,
      sessionId: pair.sessionId,
    });
  }

  // Sorted by (windowEnd, subject), matching Python's `sort(key=...)`. The order is the
  // row order of any matrix built from these labels, so it is part of the contract.
  //
  // Compared by code point rather than with `localeCompare`, which is locale-dependent:
  // Python sorts strings by code point, and a machine with a different collation would
  // otherwise order two categories differently and shuffle the matrix rows.
  labels.sort((a, b) => {
    const byTime = Date.parse(a.windowEnd) - Date.parse(b.windowEnd);
    if (byTime !== 0) return byTime;
    return a.subject < b.subject ? -1 : a.subject > b.subject ? 1 : 0;
  });
  return labels;
}
