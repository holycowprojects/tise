/**
 * The gate that decides when `visit_engaged` may switch on.
 *
 * The assertion that matters most here is not arithmetic. It is that **the three thresholds
 * are still D99's**. They were declared before the D100 replication ran, on 2,148 strangers,
 * to decide whether one person had enough data to fit this model — and 822 of those people
 * were excluded by them. The entire argument for using them is that nobody could have chosen
 * them after seeing this profile's numbers. A copy of three integers that can drift is a copy
 * that will, and the drift would be silent and would look like a smaller, kinder gate.
 *
 * So this reads `analysis/engagement_gate.py` and checks. Reading Python from a TypeScript
 * test is the same move `disclosure.test.ts` makes against `manifest.json`: the fact lives in
 * one place and every other place is checked against it rather than trusted.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  MIN_LABELS,
  MIN_SESSIONS,
  MIN_VISITS,
  engagementGate,
  gateSentence,
} from "../src/model/engagement";
import type { AttentionSpan, TiseEvent } from "../src/types";

const TIMEOUT = 1800;
const START = Date.UTC(2026, 8, 1, 9, 0);

function event(index: number, options: { category?: string; minutes?: number } = {}): TiseEvent {
  const minutes = options.minutes ?? index * 5;
  return {
    eventId: `e${index}`,
    occurredAt: new Date(START + minutes * 60_000).toISOString(),
    source: "live",
    domain: "a.example",
    category: options.category ?? "news",
    transition: "link",
    dwellSeconds: null,
    sessionId: "ignored — sessionise recomputes it",
  };
}

function span(index: number, seconds = 40): AttentionSpan {
  return {
    spanId: `sp${index}`,
    eventId: `e${index}`,
    startedAt: new Date(START).toISOString(),
    endedAt: new Date(START + seconds * 1000).toISOString(),
    activeSeconds: seconds,
    endReason: "navigated",
  };
}

function pythonConstant(name: string): number {
  const source = readFileSync(
    fileURLToPath(new URL("../../analysis/engagement_gate.py", import.meta.url)),
    "utf8",
  );
  const found = new RegExp(`^${name} = ([0-9_]+)$`, "m").exec(source);
  if (found === null) throw new Error(`${name} is not declared in engagement_gate.py`);
  return Number((found[1] as string).replaceAll("_", ""));
}

describe("the thresholds are D99's, and nobody has quietly lowered them", () => {
  it("matches the Python mirror on all three", () => {
    expect(MIN_VISITS).toBe(pythonConstant("MIN_VISITS"));
    expect(MIN_SESSIONS).toBe(pythonConstant("MIN_SESSIONS"));
    expect(MIN_LABELS).toBe(pythonConstant("MIN_LABELS"));
  });

  it("still reads the values D99 actually declared", () => {
    // Belt and braces: the check above would pass if both sides moved together.
    expect(MIN_VISITS).toBe(1000);
    expect(MIN_SESSIONS).toBe(20);
    expect(MIN_LABELS).toBe(200);
  });
});

describe("what counts, and what only looks like it counts", () => {
  it("counts visits with attention, not visits", () => {
    // Imported history can never carry dwell (D35), so counting every event would clear a
    // 1,000-visit bar on data that cannot answer the question.
    const events = Array.from({ length: 20 }, (_, i) => event(i));
    const gate = engagementGate(events, [span(0), span(1), span(2), span(3)], TIMEOUT);

    expect(events).toHaveLength(20);
    expect(gate.dwelledVisits).toBe(4);
  });

  it("counts sittings that hold a label, not sittings", () => {
    const dwelled = Array.from({ length: 14 }, (_, i) => event(i));
    const quiet = Array.from({ length: 5 }, (_, i) =>
      event(100 + i, { minutes: 600 + i * 5 }),
    );
    const spans = Array.from({ length: 14 }, (_, i) => span(i));
    const gate = engagementGate([...dwelled, ...quiet], spans, TIMEOUT);

    expect(gate.sessionsWithLabels).toBe(1);
  });

  it("gives a category no labels until its eleventh dwelled visit", () => {
    const events = Array.from({ length: 14 }, (_, i) => event(i));
    const gate = engagementGate(events, events.map((_, i) => span(i)), TIMEOUT);

    expect(gate.dwelledVisits).toBe(14);
    expect(gate.labels).toBe(4);
  });

  it("sums several spans on one visit rather than keeping the last", () => {
    const events = Array.from({ length: 12 }, (_, i) => event(i));
    const spans = events.flatMap((_, i) => [span(i, 10), { ...span(i, 30), spanId: `sp${i}b` }]);
    const gate = engagementGate(events, spans, TIMEOUT);

    // 24 spans, 12 visits. A revisited page is what this target is about.
    expect(spans).toHaveLength(24);
    expect(gate.dwelledVisits).toBe(12);
  });

  it("holds an empty store at zero rather than throwing", () => {
    const gate = engagementGate([], [], TIMEOUT);
    expect(gate.met).toBe(false);
    expect(gate.labels).toBe(0);
    expect(gate.dwelledVisits).toBe(0);
  });
});

describe("the sentence a person reads", () => {
  it("names the criterion furthest away, not the first one", () => {
    // 14 visits: labels are at 4/200 (2%) and visits at 14/1000 (1.4%), so visits is the
    // honest thing to report. Reporting whichever came first in the list would drift.
    const events = Array.from({ length: 14 }, (_, i) => event(i));
    const gate = engagementGate(events, events.map((_, i) => span(i)), TIMEOUT);

    expect(gate.met).toBe(false);
    expect(gateSentence(gate)).toContain("visits with measured attention");
    expect(gateSentence(gate)).toContain("986 to go");
  });

  it("does not repeat the claim it replaced", () => {
    // D101 shipped "Predictions need roughly ten measured visits per topic before they
    // begin". Ten per topic is when a *label* becomes possible; it says nothing about when
    // a model may be trusted, and it was wrong by more than an order of magnitude.
    //
    // Comments are stripped first, exactly as `privacy.test.ts` does: the scan is about
    // what the code *displays*, and the comment above the replacement quotes the old
    // sentence in order to explain it. The first version of this test failed on its own
    // documentation.
    const popup = readFileSync(
      fileURLToPath(new URL("../ui/popup/popup.ts", import.meta.url)),
      "utf8",
    )
      .replace(/\/\*[\s\S]*?\*\//g, " ")
      .replace(/(^|[^:])\/\/.*$/gm, "$1");
    expect(popup).not.toContain("roughly ten measured visits per topic");
  });

  it("says ready only when all three are met", () => {
    const events: TiseEvent[] = [];
    const spans: AttentionSpan[] = [];
    let index = 0;
    for (let sitting = 0; sitting < MIN_SESSIONS + 2; sitting += 1) {
      for (let step = 0; step < 60; step += 1) {
        events.push(event(index, { minutes: sitting * 24 * 60 + step }));
        spans.push(span(index));
        index += 1;
      }
    }
    const gate = engagementGate(events, spans, TIMEOUT);

    expect(gate.dwelledVisits).toBeGreaterThanOrEqual(MIN_VISITS);
    expect(gate.sessionsWithLabels).toBeGreaterThanOrEqual(MIN_SESSIONS);
    expect(gate.labels).toBeGreaterThanOrEqual(MIN_LABELS);
    expect(gate.met).toBe(true);
    expect(gateSentence(gate)).toContain("Ready");
  });
});
