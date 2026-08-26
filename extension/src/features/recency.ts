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

/** Bumped by T10 when the feature set changes. Travels with every feature row. */
export const FEATURE_SET = "fs_1";

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
