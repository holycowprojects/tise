/**
 * Assemble one feature row. The single place that decides what the model sees.
 *
 * PARITY-CRITICAL: `research/tise_research/features/vector.py` is the mirror, and the two
 * must produce identical maps — same keys, same values within 1e-9.
 *
 * **Compat classes.** Every feature declares whether it belongs to the `history` class
 * (computable from what `chrome.history` and `webNavigation` provide) or the `full` class
 * (needs dwell time, which only the history *database* has). In V1 **every feature is
 * `history`** and the `full` class is empty — a direct consequence of D35, which stopped
 * Tise measuring dwell in either direction. The mechanism stays because the distinction
 * is real, and the day it stops being empty must not be the day it gets invented.
 *
 * **`FEATURE_SET` is part of the contract.** A benchmark is only reproducible if you know
 * which features produced it, so the version travels on every row and is bumped whenever
 * this map's keys or semantics change.
 */
import type { TiseEvent } from "../types";
import {
  categoryEventsInSession,
  dayOfWeek,
  hourOfDay,
  sessionCategoryCount,
  sessionEventCount,
} from "./context";
import { categoryShare, daysSeen, eventCount, sessionCount } from "./frequency";
import { priorReturnRate, priorSessionCount } from "./priors";
import { hoursSinceFirstSeen, hoursSinceLastSeen } from "./recency";

/**
 * fs_1 was one feature; fs_2 was the full V1 set; **fs_3 replaces the two features that
 * grew with the calendar** (D81, adopted in D82).
 *
 * `hoursSinceFirstSeen` and `priorSessionCount` described when observation started rather
 * than how the person behaves — two people with identical habits and different install
 * dates got different values, so a coefficient fitted on one transferred to nobody.
 */
export const FEATURE_SET = "fs_3";

/**
 * Hours at which `firstSeenSaturation` reaches 0.5 — seven days, matching the 7-day
 * windows already in the set. Declared, not fitted (D81).
 */
export const FIRST_SEEN_SCALE_HOURS = 168;

/** Sessions per day at which `priorSessionRate` reaches 0.5. One a day is a daily habit. */
export const PRIOR_SESSION_RATE_SCALE = 1;

/**
 * Map [0, inf) onto [0, 1), reaching 0.5 at `scale`.
 *
 * The bound is the point, not the shape: a feature that only grows lets a value land
 * arbitrarily far outside the range its coefficient was fitted on, and one in [0, 1)
 * cannot. Mirrors `saturate` in `research/tise_research/features/vector.py`.
 */
export function saturate(value: number, scale: number): number {
  if (value < 0) throw new Error(`refusing to saturate a negative value: ${value}`);
  return value / (value + scale);
}

export type CompatClass = "history" | "full";

/**
 * Ordered, and the order is part of the contract: it is the column order of any matrix
 * built from these rows, and a silent reordering would swap two coefficients.
 */
export const FEATURE_NAMES = [
  "hoursSinceLastSeen",
  "firstSeenSaturation",
  "eventCount7d",
  "eventCount30d",
  "daysSeen7d",
  "sessionCount7d",
  "categoryShare30d",
  "priorReturnRate",
  "priorSessionRate",
  "sessionEventCount",
  "sessionCategoryCount",
  "categoryEventsInSession",
  "hourOfDay",
  "dayOfWeek",
] as const;

export type FeatureName = (typeof FEATURE_NAMES)[number];

export interface FeatureRow {
  readonly subject: string;
  readonly windowEnd: string;
  readonly featureSet: string;
  readonly compat: CompatClass;
  readonly values: Readonly<Record<FeatureName, number | null>>;
}

/**
 * Inverse of `saturate`. Exact, not approximate: `x = scale * s / (1 - s)`.
 *
 * It exists because the saturating transform is what a *model* wants and the underlying
 * quantity is what a *person* wants — "opened about forty times" is evidence a reader can
 * check, and 0.83 is not. Nothing is reconstructed that was not there: the value is
 * algebraically identical to what `fs_2` stored.
 *
 * Returns Infinity at s = 1, which `saturate` never produces for a finite input.
 */
export function unsaturate(saturated: number, scale: number): number {
  if (saturated < 0 || saturated >= 1) {
    if (saturated === 1) return Number.POSITIVE_INFINITY;
    throw new Error(`not a saturated value in [0, 1): ${saturated}`);
  }
  return (scale * saturated) / (1 - saturated);
}

/**
 * `null` stays `null`: never having seen the category is an absence, not a saturation of
 * zero, and the missing-indicator column is what carries it.
 */
export function firstSeenSaturation(hoursFirst: number | null): number | null {
  return hoursFirst === null ? null : saturate(hoursFirst, FIRST_SEEN_SCALE_HOURS);
}

/**
 * Sessions per observed day, saturated. Never `null`: with no prior sessions the rate is a
 * measured zero, unlike never having been seen at all.
 *
 * The one-day floor on the denominator stops a category first seen an hour ago reporting a
 * rate per hour. At the default 24-hour horizon it cannot actually bind — a prior session
 * only counts once its horizon has elapsed, so a day has always passed by then — and it is
 * kept as a guard for shorter horizons.
 */
export function priorSessionRate(
  priorSessions: number,
  hoursFirst: number | null,
): number {
  const observedDays = hoursFirst === null ? 0 : hoursFirst / 24;
  return saturate(priorSessions / Math.max(observedDays, 1), PRIOR_SESSION_RATE_SCALE);
}

export interface FeatureOptions {
  readonly timeoutSeconds: number;
  readonly horizonHours: number;
}

/**
 * Every feature for one (category, windowEnd) pair.
 *
 * Nothing here reads an event at or after `windowEnd` except the session-context
 * functions, which take events up to *and including* it — that instant is the end of the
 * session being described, not the future. See `context.ts`.
 */
export function computeFeatures(
  events: readonly TiseEvent[],
  category: string,
  windowEnd: number,
  options: FeatureOptions,
): FeatureRow {
  const { timeoutSeconds, horizonHours } = options;

  // Both are computed first because `fs_3`'s two features are pure transforms of them.
  // That is also what makes an `fs_2` row migratable without its events — see
  // `model/migrate.ts`.
  const hoursFirst = hoursSinceFirstSeen(events, category, windowEnd);
  const priorSessions = priorSessionCount(
    events,
    category,
    windowEnd,
    timeoutSeconds,
    horizonHours,
  );

  const values: Record<FeatureName, number | null> = {
    hoursSinceLastSeen: hoursSinceLastSeen(events, category, windowEnd),
    firstSeenSaturation: firstSeenSaturation(hoursFirst),
    eventCount7d: eventCount(events, category, windowEnd, 7),
    eventCount30d: eventCount(events, category, windowEnd, 30),
    daysSeen7d: daysSeen(events, category, windowEnd, 7),
    sessionCount7d: sessionCount(events, category, windowEnd, 7, timeoutSeconds),
    categoryShare30d: categoryShare(events, category, windowEnd, 30),
    priorReturnRate: priorReturnRate(
      events,
      category,
      windowEnd,
      timeoutSeconds,
      horizonHours,
    ),
    priorSessionRate: priorSessionRate(priorSessions, hoursFirst),
    sessionEventCount: sessionEventCount(events, windowEnd, timeoutSeconds),
    sessionCategoryCount: sessionCategoryCount(events, windowEnd, timeoutSeconds),
    categoryEventsInSession: categoryEventsInSession(
      events,
      category,
      windowEnd,
      timeoutSeconds,
    ),
    hourOfDay: hourOfDay(windowEnd),
    dayOfWeek: dayOfWeek(windowEnd),
  };

  return {
    subject: category,
    windowEnd: new Date(windowEnd).toISOString(),
    featureSet: FEATURE_SET,
    compat: "history",
    values,
  };
}
