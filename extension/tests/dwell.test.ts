/**
 * The span→event join, and the two decisions inside it that no score would reveal.
 *
 * `research/fixtures/export_v3.json` is read directly, so this is a genuine cross-language
 * check rather than a restatement: Python's `dwell_by_event` and `events_with_dwell` read
 * the same file, and `test_export_load.py` asserts the same properties from the other side.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { attachDwell, dwellByEvent, measuredCount } from "../src/features/dwell";
import type { AttentionSpan, TiseEvent } from "../src/types";

interface ExportV3 {
  schema: string;
  events: TiseEvent[];
  attention: AttentionSpan[];
}

const FIXTURE: ExportV3 = JSON.parse(
  readFileSync(
    fileURLToPath(new URL("../../research/fixtures/export_v3.json", import.meta.url)),
    "utf8",
  ),
);

function span(eventId: string, startedAt: string, activeSeconds: number): AttentionSpan {
  return {
    spanId: `${eventId}:${startedAt}`,
    eventId,
    startedAt,
    endedAt: startedAt,
    activeSeconds,
    endReason: "navigated",
  };
}

function event(eventId: string): TiseEvent {
  return {
    eventId,
    occurredAt: "2026-08-01T09:00:00.000Z",
    source: "live",
    domain: "example.com",
    category: "unknown",
    transition: "link",
    dwellSeconds: null,
    sessionId: "s1",
  };
}

describe("summing attention", () => {
  it("adds every span for an event rather than keeping the last", () => {
    // A revisited page produces several spans. Keeping one would halve its dwell, and a
    // revisited page is exactly the kind `visit_engaged` is about.
    const totals = dwellByEvent([
      span("e1", "2026-08-01T09:00:00.000Z", 30),
      span("e1", "2026-08-01T09:05:00.000Z", 12),
      span("e2", "2026-08-01T09:10:00.000Z", 7),
    ]);
    expect(totals.get("e1")).toBe(42);
    expect(totals.get("e2")).toBe(7);
  });

  it("leaves an unmeasured event out of the map entirely", () => {
    // Absent, not zero. A caller cannot then read a missing measurement as a short visit.
    const totals = dwellByEvent([span("e1", "2026-08-01T09:00:00.000Z", 30)]);
    expect(totals.has("e2")).toBe(false);
    expect(totals.get("e2")).toBeUndefined();
  });

  it("is empty for no spans, rather than throwing", () => {
    expect(dwellByEvent([]).size).toBe(0);
  });
});

describe("attaching dwell to events", () => {
  it("gives an event with no span null, never zero", () => {
    // The damage from a zero is not local: it enters the category's trailing median as a
    // genuinely short visit and shifts the threshold for every *other* visit in it.
    const [measured, unmeasured] = attachDwell(
      [event("e1"), event("e2")],
      [span("e1", "2026-08-01T09:00:00.000Z", 30)],
    );
    expect(measured?.dwellSeconds).toBe(30);
    expect(unmeasured?.dwellSeconds).toBeNull();
  });

  it("does not mutate the events it was given", () => {
    // The same array is read by `fs_3` code that must keep seeing null, and by
    // `assertStorable`, which throws if dwell ever reaches a stored row.
    const events = [event("e1")];
    attachDwell(events, [span("e1", "2026-08-01T09:00:00.000Z", 30)]);
    expect(events[0]?.dwellSeconds).toBeNull();
  });

  it("preserves every other field untouched", () => {
    const original = event("e1");
    const [joined] = attachDwell([original], [span("e1", "2026-08-01T09:00:00.000Z", 5)]);
    expect({ ...joined, dwellSeconds: null }).toEqual(original);
  });

  it("keeps the order it was given", () => {
    const events = [event("a"), event("b"), event("c")];
    expect(attachDwell(events, []).map((e) => e.eventId)).toEqual(["a", "b", "c"]);
  });
});

describe("agreeing with Python on the shared fixture", () => {
  it("reads the same spans Python reads", () => {
    expect(FIXTURE.schema).toBe("tise.export.v3");
    expect(FIXTURE.attention.length).toBeGreaterThan(0);
  });

  it("sums the repeated event the same way `dwell_by_event` does", () => {
    // The fixture deliberately carries two spans on one event. `test_export_load.py`
    // asserts the same total from the Python side against the same file.
    const totals = dwellByEvent(FIXTURE.attention);
    const counts = new Map<string, number>();
    for (const s of FIXTURE.attention) {
      counts.set(s.eventId, (counts.get(s.eventId) ?? 0) + 1);
    }
    const repeated = [...counts.entries()].filter(([, n]) => n > 1).map(([id]) => id);
    expect(repeated.length, "fixture must contain an event with two spans").toBeGreaterThan(0);

    for (const eventId of repeated) {
      const parts = FIXTURE.attention
        .filter((s) => s.eventId === eventId)
        .map((s) => s.activeSeconds);
      expect(totals.get(eventId)).toBe(parts.reduce((a, b) => a + b, 0));
      expect(totals.get(eventId)).toBeGreaterThan(Math.max(...parts));
    }
  });

  it("counts exactly the events Python finds measured", () => {
    const measured = measuredCount(FIXTURE.events, FIXTURE.attention);
    const distinct = new Set(FIXTURE.attention.map((s) => s.eventId));
    expect(measured).toBe(distinct.size);
    expect(measured).toBeLessThan(FIXTURE.events.length);
  });

  it("leaves the fixture's own events dwell-free (D35)", () => {
    for (const e of FIXTURE.events) expect(e.dwellSeconds).toBeNull();
  });
});
