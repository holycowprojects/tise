/**
 * Where the label sits: the session that produced it, and when.
 *
 * PARITY-CRITICAL: `research/tise_research/features/context.py` is the mirror.
 *
 * **These are the features that leak most easily**, and the reason is worth stating. A
 * label's `windowEnd` is the end of its own session, so the session is fully observed at
 * that instant and including its events is correct. But re-deriving that session from the
 * whole corpus is not: an event twenty minutes *after* `windowEnd` is inside the timeout
 * and would merge into the same session, changing its event count retroactively.
 *
 * So every function here sessionises events with `occurredAt <= windowEnd` and takes the
 * last session. A later event cannot join a session it is not in the input for.
 *
 * Hour and day are **UTC**, for the same reason as `frequency.ts`. It costs real signal —
 * 9pm behaviour is not 9pm UTC behaviour — and that cost is recorded, not hidden.
 */
import type { TiseEvent } from "../types";
import { sessionise, type FeatureSession } from "./sessions";

/** The session that closes at `windowEnd`, derived only from events up to it. */
export function sessionAt(
  events: readonly TiseEvent[],
  windowEnd: number,
  timeoutSeconds: number,
): FeatureSession | null {
  const upto = events.filter((event) => Date.parse(event.occurredAt) <= windowEnd);
  const sessions = sessionise(upto, timeoutSeconds);
  return sessions.length === 0 ? null : (sessions[sessions.length - 1] as FeatureSession);
}

export function sessionEventCount(
  events: readonly TiseEvent[],
  windowEnd: number,
  timeoutSeconds: number,
): number {
  return sessionAt(events, windowEnd, timeoutSeconds)?.events.length ?? 0;
}

/** How many distinct categories this session touched. A proxy for browsing breadth. */
export function sessionCategoryCount(
  events: readonly TiseEvent[],
  windowEnd: number,
  timeoutSeconds: number,
): number {
  return sessionAt(events, windowEnd, timeoutSeconds)?.categories.length ?? 0;
}

export function categoryEventsInSession(
  events: readonly TiseEvent[],
  category: string,
  windowEnd: number,
  timeoutSeconds: number,
): number {
  const session = sessionAt(events, windowEnd, timeoutSeconds);
  if (session === null) return 0;
  return session.events.filter((event) => event.category === category).length;
}

/** UTC hour, 0–23. See the module comment for what UTC costs here. */
export function hourOfDay(windowEnd: number): number {
  return new Date(windowEnd).getUTCHours();
}

/**
 * UTC weekday, **Monday = 0** through Sunday = 6, matching Python's `datetime.weekday()`.
 *
 * JavaScript's `getUTCDay()` is Sunday = 0, so it is converted here. That off-by-one is
 * exactly the kind of silent disagreement the parity fixture exists to catch, and it
 * would have shifted every day-of-week coefficient by one without failing anything else.
 */
export function dayOfWeek(windowEnd: number): number {
  return (new Date(windowEnd).getUTCDay() + 6) % 7;
}
