/**
 * Recency features — how long since this category was last seen.
 *
 * PARITY-CRITICAL: `research/tise_research/features/recency.py` is the mirror.
 *
 * **Every function here takes `windowEnd` and filters strictly before it.** That is the
 * structural defence against leakage: it is not possible to write a leaking feature
 * without deleting that line.
 *
 * `null` for "never seen", never a sentinel. A stand-in like 9999 hours is a number the
 * model will happily fit a coefficient to, and it means something categorically
 * different from a measurement. This layer refuses to invent an encoding for absence;
 * the consumer decides.
 */
import type { TiseEvent } from "../types";

/* FEATURE_SET moved to vector.ts at T10: it describes the set, not this module. */


const MS_PER_HOUR = 3_600_000;

/**
 * Hours since the most recent event in `category` strictly before `windowEnd`.
 *
 * A category can be absent here even though it produced the label being computed: a
 * label closes at the end of its session, and an event *at* that instant is not strictly
 * before it. That case is in the parity fixture on purpose.
 */
export function hoursSinceLastSeen(
  events: readonly TiseEvent[],
  category: string,
  windowEnd: number,
): number | null {
  let latest: number | null = null;
  for (const event of events) {
    const at = Date.parse(event.occurredAt);
    if (at >= windowEnd) continue; // leakage guard
    if (event.category !== category) continue;
    if (latest === null || at > latest) latest = at;
  }
  return latest === null ? null : (windowEnd - latest) / MS_PER_HOUR;
}

/**
 * Hours since the category was **first** seen, strictly before `windowEnd`.
 *
 * How long this has been a thing the person does, as against how recently they did it. A
 * category first seen an hour ago and one first seen a year ago behave differently even
 * when `hoursSinceLastSeen` is identical.
 */
export function hoursSinceFirstSeen(
  events: readonly TiseEvent[],
  category: string,
  windowEnd: number,
): number | null {
  let earliest: number | null = null;
  for (const event of events) {
    const at = Date.parse(event.occurredAt);
    if (at >= windowEnd) continue; // leakage guard
    if (event.category !== category) continue;
    if (earliest === null || at < earliest) earliest = at;
  }
  return earliest === null ? null : (windowEnd - earliest) / MS_PER_HOUR;
}
