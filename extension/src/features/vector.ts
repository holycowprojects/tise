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

/** fs_1 was one feature; fs_2 is the full V1 set. */
export const FEATURE_SET = "fs_2";

export type CompatClass = "history" | "full";

/**
 * Ordered, and the order is part of the contract: it is the column order of any matrix
 * built from these rows, and a silent reordering would swap two coefficients.
 */
export const FEATURE_NAMES = [
  "hoursSinceLastSeen",
  "hoursSinceFirstSeen",
  "eventCount7d",
  "eventCount30d",
  "daysSeen7d",
  "sessionCount7d",
  "categoryShare30d",
  "priorReturnRate",
  "priorSessionCount",
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

  const values: Record<FeatureName, number | null> = {
    hoursSinceLastSeen: hoursSinceLastSeen(events, category, windowEnd),
    hoursSinceFirstSeen: hoursSinceFirstSeen(events, category, windowEnd),
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
    priorSessionCount: priorSessionCount(
      events,
      category,
      windowEnd,
      timeoutSeconds,
      horizonHours,
    ),
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
