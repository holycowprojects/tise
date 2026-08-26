/**
 * The person's own history of returning — the feature that has to be built carefully.
 *
 * PARITY-CRITICAL: `research/tise_research/features/priors.py` is the mirror.
 *
 * `priorReturnRate` is how often this category has *already* been returned to within the
 * horizon. It is the strongest feature in the set, because the bar it has to help clear
 * is `category_base_rate` (D28) and this is that baseline expressed as a number the model
 * can weigh against everything else.
 *
 * **It is also the one that leaks if you write it the obvious way.** Deciding whether a
 * past session was returned to means looking at the 24 hours after it — and for a recent
 * session, some of those hours are still in the future at `windowEnd`. Counting it either
 * way is wrong: as a miss it says "no return" when the return may be an hour away, and as
 * a hit it is reading the future outright.
 *
 * So a past session counts only when its entire horizon has already elapsed:
 *
 *     sessionEnd + horizon <= windowEnd
 *
 * Sessions whose outcome is not yet knowable are excluded from both numerator and
 * denominator, and `priorSessionCount` reports how many were counted — so a rate from two
 * sessions is visibly different from one built on forty.
 */
import type { TiseEvent } from "../types";
import { sessionise } from "./sessions";

const MS_PER_HOUR = 3_600_000;

export interface ResolvedPrior {
  readonly sessionEnd: number;
  readonly returned: boolean;
}

/** Index of the first element strictly greater than `target`. Python's `bisect_right`. */
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
 * Every prior session whose horizon has fully elapsed, with whether it was returned to.
 *
 * Both the sessions and the returns are derived from events strictly before `windowEnd`,
 * so nothing here can see past the boundary even indirectly.
 */
export function resolvedPriorSessions(
  events: readonly TiseEvent[],
  category: string,
  windowEnd: number,
  timeoutSeconds: number,
  horizonHours: number,
): ResolvedPrior[] {
  const horizon = horizonHours * MS_PER_HOUR;
  const past = events.filter((event) => Date.parse(event.occurredAt) < windowEnd);
  if (past.length === 0) return [];

  const times = past
    .filter((event) => event.category === category)
    .map((event) => Date.parse(event.occurredAt))
    .sort((a, b) => a - b);

  const resolved: ResolvedPrior[] = [];
  for (const session of sessionise(past, timeoutSeconds)) {
    if (!session.categories.includes(category)) continue;

    const sessionEnd = Date.parse(session.endedAt);
    if (sessionEnd + horizon > windowEnd) continue; // outcome not yet knowable

    const index = firstAfter(times, sessionEnd);
    const returned = index < times.length && (times[index] as number) <= sessionEnd + horizon;
    resolved.push({ sessionEnd, returned });
  }
  return resolved;
}

export function priorSessionCount(
  events: readonly TiseEvent[],
  category: string,
  windowEnd: number,
  timeoutSeconds: number,
  horizonHours: number,
): number {
  return resolvedPriorSessions(events, category, windowEnd, timeoutSeconds, horizonHours)
    .length;
}

/**
 * Share of resolved prior sessions that were returned to inside the horizon.
 *
 * `null` when nothing has resolved yet. A default of 0.5 would be a prior invented here
 * and then fitted downstream as though it had been measured.
 */
export function priorReturnRate(
  events: readonly TiseEvent[],
  category: string,
  windowEnd: number,
  timeoutSeconds: number,
  horizonHours: number,
): number | null {
  const resolved = resolvedPriorSessions(
    events,
    category,
    windowEnd,
    timeoutSeconds,
    horizonHours,
  );
  if (resolved.length === 0) return null;
  return resolved.filter((prior) => prior.returned).length / resolved.length;
}
