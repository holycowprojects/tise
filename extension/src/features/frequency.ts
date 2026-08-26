/**
 * Frequency features — how much, how often, how spread out.
 *
 * PARITY-CRITICAL: `research/tise_research/features/frequency.py` is the mirror.
 *
 * Every window is **half-open**: `[windowEnd - span, windowEnd)`. An event exactly at
 * `windowEnd` is excluded, the same rule `recency.ts` uses, because a feature that
 * includes the instant its label became decidable is reading the boundary from the wrong
 * side.
 *
 * Calendar days are **UTC**. Local days would be the more behavioural unit — people have
 * mornings, not 00:00 UTC — but the browser's local timezone and the research machine's
 * are not the same thing, and a feature that depends on which computer ran it cannot be
 * in a parity suite. A known limitation, recorded rather than smoothed over.
 */
import type { TiseEvent } from "../types";
import { sessionise } from "./sessions";

const MS_PER_DAY = 86_400_000;

function inWindow(
  events: readonly TiseEvent[],
  windowEnd: number,
  days: number,
): TiseEvent[] {
  const start = windowEnd - days * MS_PER_DAY;
  return events.filter((event) => {
    const at = Date.parse(event.occurredAt);
    return at >= start && at < windowEnd;
  });
}

/** How many events in this category fell inside the window. Zero is a measurement. */
export function eventCount(
  events: readonly TiseEvent[],
  category: string,
  windowEnd: number,
  days: number,
): number {
  return inWindow(events, windowEnd, days).filter((event) => event.category === category)
    .length;
}

/**
 * Distinct UTC calendar days on which the category appeared.
 *
 * Separates a habit from a binge: thirty events on one afternoon and thirty spread over a
 * fortnight have the same `eventCount` and mean very different things.
 */
export function daysSeen(
  events: readonly TiseEvent[],
  category: string,
  windowEnd: number,
  days: number,
): number {
  const dates = new Set<string>();
  for (const event of inWindow(events, windowEnd, days)) {
    if (event.category !== category) continue;
    dates.add(new Date(Date.parse(event.occurredAt)).toISOString().slice(0, 10));
  }
  return dates.size;
}

/**
 * Distinct sessions inside the window that contained this category.
 *
 * Sessions are derived from the windowed events only. Sessionising the whole corpus and
 * then filtering would let an event after `windowEnd` merge two earlier sessions into
 * one, and the count would move — which is exactly what the leakage test checks for.
 */
export function sessionCount(
  events: readonly TiseEvent[],
  category: string,
  windowEnd: number,
  days: number,
  timeoutSeconds: number,
): number {
  return sessionise(inWindow(events, windowEnd, days), timeoutSeconds).filter((session) =>
    session.categories.includes(category),
  ).length;
}

/**
 * This category's share of all events in the window.
 *
 * `null` when the window holds nothing at all. Zero would claim "you never do this",
 * which is a different statement from "there is nothing to divide by".
 */
export function categoryShare(
  events: readonly TiseEvent[],
  category: string,
  windowEnd: number,
  days: number,
): number | null {
  const windowed = inWindow(events, windowEnd, days);
  if (windowed.length === 0) return null;
  const matching = windowed.filter((event) => event.category === category).length;
  return matching / windowed.length;
}
