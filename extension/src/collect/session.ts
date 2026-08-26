/**
 * Assign live events to sessions as they arrive.
 *
 * A session is a run of events with no gap **strictly greater** than the timeout. That
 * strictness is part of the contract, not an implementation detail: a `>` versus `>=`
 * disagreement with `research/tise_research/features/sessions.py` shifts every
 * session-derived feature by one event, and it is invisible until the parity suite
 * catches it.
 *
 * **Session ids are locally assigned and opaque.** The research tier re-derives sessions
 * from timestamps with `sessionise` and never compares its ids to these — the two
 * languages agree on the *grouping*, which is what features depend on, and not on the
 * exact string. Requiring the strings to match would mean pinning Python's `isoformat`
 * against JavaScript's `toISOString` across microsecond precision, which buys nothing
 * and breaks quietly.
 */
export interface SessionCursor {
  readonly sessionId: string;
  /** The latest event instant seen so far, ISO 8601 UTC. */
  readonly lastEventAt: string;
}

/**
 * The cursor after observing an event at `occurredAt`. Pure — no clock, no I/O.
 *
 * Out-of-order arrivals keep the later timestamp as the cursor. Live navigation is
 * ordered in practice but not by contract, and a cursor that walked backwards would
 * split the next session on a gap that never happened.
 */
export function advanceSession(
  cursor: SessionCursor | null,
  occurredAt: string,
  timeoutSeconds: number,
): SessionCursor {
  const now = Date.parse(occurredAt);
  if (cursor === null) {
    return { sessionId: occurredAt, lastEventAt: occurredAt };
  }

  const previous = Date.parse(cursor.lastEventAt);
  const gapSeconds = (now - previous) / 1000;

  if (gapSeconds > timeoutSeconds) {
    return { sessionId: occurredAt, lastEventAt: occurredAt };
  }

  return {
    sessionId: cursor.sessionId,
    lastEventAt: now > previous ? occurredAt : cursor.lastEventAt,
  };
}
