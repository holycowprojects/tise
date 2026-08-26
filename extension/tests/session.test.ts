import { describe, expect, it } from "vitest";
import { advanceSession, type SessionCursor } from "../src/collect/session";

const TIMEOUT = 1800; // D17, thirty minutes — a declared hyperparameter

function at(iso: string): string {
  return new Date(iso).toISOString();
}

describe("advanceSession", () => {
  it("opens a session on the first event", () => {
    const cursor = advanceSession(null, at("2026-08-26T09:00:00Z"), TIMEOUT);
    expect(cursor).toEqual({
      sessionId: "2026-08-26T09:00:00.000Z",
      lastEventAt: "2026-08-26T09:00:00.000Z",
    });
  });

  it("keeps the session while the gap stays within the timeout", () => {
    const first = advanceSession(null, at("2026-08-26T09:00:00Z"), TIMEOUT);
    const second = advanceSession(first, at("2026-08-26T09:20:00Z"), TIMEOUT);
    expect(second.sessionId).toBe(first.sessionId);
    expect(second.lastEventAt).toBe("2026-08-26T09:20:00.000Z");
  });

  it("opens a new session once the gap exceeds the timeout", () => {
    const first = advanceSession(null, at("2026-08-26T09:00:00Z"), TIMEOUT);
    const second = advanceSession(first, at("2026-08-26T09:40:00Z"), TIMEOUT);
    expect(second.sessionId).toBe("2026-08-26T09:40:00.000Z");
  });

  it("treats a gap of exactly the timeout as the same session", () => {
    // Strictly greater, matching features/sessions.py. A `>` versus `>=` disagreement
    // shifts every session-derived feature by one event and is invisible until the
    // parity suite catches it.
    const first = advanceSession(null, at("2026-08-26T09:00:00Z"), TIMEOUT);
    const boundary = advanceSession(first, at("2026-08-26T09:30:00Z"), TIMEOUT);
    expect(boundary.sessionId).toBe(first.sessionId);

    const justOver = advanceSession(first, at("2026-08-26T09:30:00.001Z"), TIMEOUT);
    expect(justOver.sessionId).not.toBe(first.sessionId);
  });

  it("does not let an out-of-order arrival walk the cursor backwards", () => {
    const first = advanceSession(null, at("2026-08-26T09:00:00Z"), TIMEOUT);
    const ahead = advanceSession(first, at("2026-08-26T09:25:00Z"), TIMEOUT);
    const late = advanceSession(ahead, at("2026-08-26T09:10:00Z"), TIMEOUT);

    expect(late.sessionId).toBe(first.sessionId);
    expect(late.lastEventAt).toBe("2026-08-26T09:25:00.000Z");
  });

  it("groups a realistic run the same way the Python sessioniser would", () => {
    const times = [
      "2026-08-26T09:00:00Z",
      "2026-08-26T09:05:00Z",
      "2026-08-26T09:29:00Z",
      "2026-08-26T11:00:00Z", // long gap — new session
      "2026-08-26T11:02:00Z",
    ];
    let cursor: SessionCursor | null = null;
    const ids = times.map((t) => {
      cursor = advanceSession(cursor, at(t), TIMEOUT);
      return cursor.sessionId;
    });

    expect(new Set(ids).size).toBe(2);
    expect(ids[0]).toBe(ids[2]);
    expect(ids[3]).toBe(ids[4]);
    expect(ids[3]).not.toBe(ids[0]);
  });
});
