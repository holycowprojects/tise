/**
 * Category changes: the run of visits you just finished ended, and something else started.
 *
 * PARITY-CRITICAL: `research/tise_research/features/transitions.py` is the mirror, and
 * `research/fixtures/parity_expected.json` is the oracle both sides assert against.
 *
 * **A label is a change, so consecutive same-category visits are one run.** The event
 * stream collapses into maximal runs of the same category and each adjacent pair is one
 * transition, so `fromCategory !== toCategory` holds by construction. D94 fixed that
 * wording and D102 measured what it costs: "you will keep doing what you are doing" is the
 * easy, high-volume, highly predictable mass, and run-collapsing removes all of it.
 *
 * **A session boundary with no category change produces nothing.** If a session ends on
 * `video` and the next begins on `video`, the run continues across the gap. That differs
 * from the between-session transitions `transition.ts` counts, which take one primary
 * category per session and permit a self-transition.
 *
 * **The clock on a transition is when the *next* run starts**, because that is the instant
 * the answer became known.
 *
 * **The session recorded is the one the question was asked in** — the session holding the
 * source run's last event, not the one that answered it.
 */
import type { TiseEvent } from "../types";
import type { FeatureSession } from "./sessions";

export interface CategoryTransition {
  /** The first event of the run being predicted. Each event starts at most one run. */
  readonly transitionId: string;
  /** When the next run's first event occurred: the moment the answer became known. */
  readonly at: string;
  /** The category just finished. */
  readonly fromCategory: string;
  /** The category that followed. */
  readonly toCategory: string;
  /** The session the source run ended in — the sitting the question was asked in. */
  readonly sessionId: string;
  /** False when the two runs are separated by a session boundary. */
  readonly withinSession: boolean;
  /**
   * The category of the run *before* the source run, or null at the start of the stream.
   * Strictly earlier than `at`, so it leaks nothing. Kept because D102 scored a rival that
   * reads it and found it beats the fitted table on one corpus.
   */
  readonly previousCategory: string | null;
  /** How many events the source run held. Reported, never a feature. */
  readonly fromRunEvents: number;
}

interface Placed {
  readonly event: TiseEvent;
  readonly sessionId: string;
}

/**
 * Every event with the session it belongs to, in chronological order.
 *
 * Re-sorted rather than trusted: an out-of-order stream would merge two runs that never
 * touched, and the result looks entirely normal afterwards.
 */
function flatten(sessions: readonly FeatureSession[]): Placed[] {
  const flat: Placed[] = [];
  for (const session of sessions) {
    for (const event of session.events) flat.push({ event, sessionId: session.sessionId });
  }
  flat.sort((a, b) => {
    if (a.event.occurredAt !== b.event.occurredAt) {
      return a.event.occurredAt < b.event.occurredAt ? -1 : 1;
    }
    if (a.event.eventId === b.event.eventId) return 0;
    return a.event.eventId < b.event.eventId ? -1 : 1;
  });
  return flat;
}

/** Collapse a chronological stream into maximal same-category runs. */
function runs(placed: readonly Placed[]): Placed[][] {
  const grouped: Placed[][] = [];
  for (const item of placed) {
    const current = grouped[grouped.length - 1];
    if (current !== undefined && current[current.length - 1]?.event.category === item.event.category) {
      current.push(item);
    } else {
      grouped.push([item]);
    }
  }
  return grouped;
}

/**
 * Every category change in the stream, within sessions and across their boundaries.
 *
 * Throws on a duplicate event id rather than emitting two transitions with the same
 * `transitionId`. Two rows sharing an id would silently double-count one change wherever
 * they were tallied, and nothing downstream could see it.
 */
export function categoryTransitions(
  sessions: readonly FeatureSession[],
): CategoryTransition[] {
  const flat = flatten(sessions);
  const seen = new Set<string>();
  for (const { event } of flat) {
    if (seen.has(event.eventId)) {
      throw new Error(`duplicate event id ${event.eventId}: transition ids would collide`);
    }
    seen.add(event.eventId);
  }

  const grouped = runs(flat);
  const transitions: CategoryTransition[] = [];
  for (let index = 0; index + 1 < grouped.length; index += 1) {
    const source = grouped[index] as Placed[];
    const target = grouped[index + 1] as Placed[];
    const last = source[source.length - 1] as Placed;
    const first = target[0] as Placed;
    const previous = index > 0 ? (grouped[index - 1]?.[0] as Placed) : undefined;
    transitions.push({
      transitionId: first.event.eventId,
      at: first.event.occurredAt,
      fromCategory: last.event.category,
      toCategory: first.event.category,
      sessionId: last.sessionId,
      withinSession: last.sessionId === first.sessionId,
      previousCategory: previous === undefined ? null : previous.event.category,
      fromRunEvents: source.length,
    });
  }
  return transitions;
}

/**
 * How many session boundaries the run-collapse absorbed because nothing changed.
 *
 * The declared cost of "a transition is a change", reported rather than assumed small.
 */
export function sessionBoundariesWithoutChange(
  sessions: readonly FeatureSession[],
): number {
  let lost = 0;
  for (let index = 0; index + 1 < sessions.length; index += 1) {
    const previous = sessions[index] as FeatureSession;
    const following = sessions[index + 1] as FeatureSession;
    const end = previous.events[previous.events.length - 1];
    const start = following.events[0];
    if (end === undefined || start === undefined) continue;
    if (end.category === start.category) lost += 1;
  }
  return lost;
}
