/**
 * Group events into sessions. The batch form.
 *
 * PARITY-CRITICAL: `research/tise_research/features/sessions.py` is the mirror, and
 * `research/fixtures/parity_expected.json` is the oracle both are measured against.
 *
 * A session is a run of events with no gap **strictly greater** than the timeout. The
 * strictness is the contract, not an implementation detail: a `>` versus `>=`
 * disagreement between the two languages shifts every session-derived feature by one
 * event, and nothing else in either suite would notice.
 *
 * There are deliberately two implementations of this rule in the extension. This one
 * sees a whole corpus at once and is what the import and the trainer use;
 * `collect/session.ts` assigns sessions one event at a time as browsing happens, because
 * live collection cannot see the future. `tests/parity.test.ts` asserts they agree.
 */
import type { TiseEvent } from "../types";

export interface FeatureSession {
  /** Locally assigned and opaque — see D36. Never compared across languages. */
  readonly sessionId: string;
  readonly startedAt: string;
  readonly endedAt: string;
  readonly durationSeconds: number;
  readonly eventIds: readonly string[];
  /** Sorted, so the comparison is order-independent on both sides. */
  readonly categories: readonly string[];
  /** The members themselves. `context.ts` needs them; the parity fixture ignores them. */
  readonly events: readonly TiseEvent[];
}

/**
 * Group timestamps into runs. The primitive everything else is built on.
 *
 * Input is sorted first. A browser's visit table is ordered in practice but not by
 * contract, and one out-of-order row produces a negative gap that silently merges two
 * sessions.
 */
export function sessionBoundaries(
  times: readonly number[],
  timeoutSeconds: number,
): number[][] {
  const ordered = [...times].sort((a, b) => a - b);
  if (ordered.length === 0) return [];

  const groups: number[][] = [[ordered[0] as number]];
  for (let i = 1; i < ordered.length; i += 1) {
    const previous = ordered[i - 1] as number;
    const current = ordered[i] as number;
    if ((current - previous) / 1000 > timeoutSeconds) {
      groups.push([current]);
    } else {
      (groups[groups.length - 1] as number[]).push(current);
    }
  }
  return groups;
}

/** Group events into sessions, in chronological order. */
export function sessionise(
  events: readonly TiseEvent[],
  timeoutSeconds: number,
): FeatureSession[] {
  // Ties broken by eventId, matching Python's `sorted(key=(occurred_at, event_id))`.
  // Without the tiebreak two events at the same instant could land in a different order
  // in each language, and every eventId list would drift.
  const ordered = [...events].sort((a, b) => {
    const byTime = Date.parse(a.occurredAt) - Date.parse(b.occurredAt);
    return byTime !== 0 ? byTime : a.eventId.localeCompare(b.eventId);
  });
  if (ordered.length === 0) return [];

  const groups = sessionBoundaries(
    ordered.map((event) => Date.parse(event.occurredAt)),
    timeoutSeconds,
  );

  const sessions: FeatureSession[] = [];
  let position = 0;
  for (const group of groups) {
    const members = ordered.slice(position, position + group.length);
    position += group.length;

    const first = members[0] as TiseEvent;
    const last = members[members.length - 1] as TiseEvent;

    sessions.push({
      sessionId: first.occurredAt,
      startedAt: first.occurredAt,
      endedAt: last.occurredAt,
      // Zero for a single-event session. A real measurement, not an absence.
      durationSeconds: (Date.parse(last.occurredAt) - Date.parse(first.occurredAt)) / 1000,
      eventIds: members.map((event) => event.eventId),
      categories: [...new Set(members.map((event) => event.category))].sort(),
      events: members,
    });
  }
  return sessions;
}
