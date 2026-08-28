/**
 * Attention spans: the first thing in Tise that measures *time a person spent*.
 *
 * D35 recorded the duration trap as permanent, and `dwellSeconds` has been `null` since
 * T1 because of it. These spans lift it — and measure something better than
 * `visit_duration`, which counts how long a tab held a URL and so records a tab left open
 * overnight as deep engagement. D93 named that as capable of accounting for its entire
 * effect.
 *
 * Three rules carry the honesty of the whole mechanism, and each has a test here:
 *
 * 1. **Never invent a span.** No attributable navigation means no record, not a guess.
 * 2. **A zero-length span is the absence of a measurement**, not a measurement of zero.
 *    Storing one would drag every average toward zero for rows never observed.
 * 3. **An unbounded span is a laptop lid, not a person.** Capping is what stops an
 *    unobserved gap entering the data as measured attention.
 */
import "fake-indexeddb/auto";
import { IDBFactory } from "fake-indexeddb";
import { beforeEach, describe, expect, it } from "vitest";
import {
  beginSpan,
  closeSpan,
  endOpenSpan,
  forgetTab,
  MAX_SPAN_SECONDS,
  MAX_TRACKED_TABS,
  rememberTab,
  switchToTab,
  type OpenSpan,
} from "../src/collect/attention";
import { closeTiseDb, openTiseDb } from "../src/storage/db";
import { assertStorableSpan, type AttentionSpan } from "../src/types";

const START = Date.parse("2026-06-01T09:00:00.000Z");

function open(overrides: Partial<OpenSpan> = {}): OpenSpan {
  return {
    eventId: "e1",
    tabId: 7,
    startedAt: new Date(START).toISOString(),
    ...overrides,
  };
}

async function storedSpans(): Promise<AttentionSpan[]> {
  const db = await openTiseDb();
  return db.getAll("attention");
}

beforeEach(async () => {
  await closeTiseDb();
  globalThis.indexedDB = new IDBFactory();
});

describe("closing a span", () => {
  it("measures the elapsed time", () => {
    const span = closeSpan(open(), START + 90_000, "tab-switch");
    expect(span?.activeSeconds).toBe(90);
    expect(span?.endReason).toBe("tab-switch");
    expect(span?.eventId).toBe("e1");
  });

  it("refuses a zero-length span rather than storing a zero", () => {
    // Rule 2. A span of zero seconds is not "no attention" — it is no observation, and
    // storing it would pull every average down for rows that were never measured.
    expect(closeSpan(open(), START, "blur")).toBeNull();
  });

  it("refuses a span that would end before it started", () => {
    expect(closeSpan(open(), START - 1000, "blur")).toBeNull();
  });

  it("caps an implausibly long span instead of trusting it", () => {
    // Rule 3. Fourteen hours is a closed laptop, not a person reading. Capping keeps an
    // unobserved gap from outweighing a month of real spans.
    const span = closeSpan(open(), START + 14 * 3600 * 1000, "shutdown");
    expect(span?.activeSeconds).toBe(MAX_SPAN_SECONDS);
    expect(Date.parse(span!.endedAt)).toBe(START + MAX_SPAN_SECONDS * 1000);
  });

  it("gives a span a stable id, so re-recording replaces rather than duplicates", () => {
    const first = closeSpan(open(), START + 1000, "blur");
    const second = closeSpan(open(), START + 5000, "idle");
    expect(first?.spanId).toBe(second?.spanId);
  });
});

describe("the tab map", () => {
  it("remembers which navigation a tab is showing", () => {
    expect(rememberTab({}, 3, "e9")["3"]).toBe("e9");
  });

  it("is bounded, so many tabs cannot grow it without limit", () => {
    let map = {};
    for (let index = 0; index < MAX_TRACKED_TABS + 50; index += 1) {
      map = rememberTab(map, index, `e${index}`);
    }
    expect(Object.keys(map)).toHaveLength(MAX_TRACKED_TABS);
    // The most recent survive; the oldest are dropped.
    expect(map).toHaveProperty(String(MAX_TRACKED_TABS + 49));
  });
});

describe("the lifecycle", () => {
  it("stores a span when a navigation replaces the previous one", async () => {
    await beginSpan("e1", 7, START);
    await beginSpan("e2", 7, START + 30_000);

    const spans = await storedSpans();
    expect(spans).toHaveLength(1);
    expect(spans[0]).toMatchObject({
      eventId: "e1",
      activeSeconds: 30,
      endReason: "navigated",
    });
  });

  it("never has two spans open at once", async () => {
    // Two open spans would double-count one person's attention.
    await beginSpan("e1", 7, START);
    await beginSpan("e2", 8, START + 10_000);
    await endOpenSpan("blur", START + 20_000);

    const spans = await storedSpans();
    expect(spans.map((span) => span.eventId).sort()).toEqual(["e1", "e2"]);
    expect(spans.reduce((total, span) => total + span.activeSeconds, 0)).toBe(20);
  });

  it("is idempotent, so every listener can call it without coordinating", async () => {
    await beginSpan("e1", 7, START);
    await endOpenSpan("idle", START + 5000);
    expect(await endOpenSpan("idle", START + 9000)).toBeNull();
    expect(await storedSpans()).toHaveLength(1);
  });

  it("reopens on a tab switch when it knows what that tab is showing", async () => {
    await beginSpan("e1", 7, START);
    await beginSpan("e2", 8, START + 10_000);
    await switchToTab(7, START + 20_000);
    await endOpenSpan("blur", START + 25_000);

    const spans = await storedSpans();
    const reopened = spans.filter((span) => span.eventId === "e1");
    // e1 got its original 10s, then 5s more after switching back. Numeric comparator:
    // the default sort is lexicographic, which orders [10, 5] as [10, 5].
    expect(reopened.map((span) => span.activeSeconds).sort((a, b) => a - b)).toEqual([
      5, 10,
    ]);
  });

  it("records nothing when it cannot attribute the tab to a navigation", async () => {
    // Rule 1, and the most important test here. Switching to a tab Tise never saw a
    // navigation in must produce no span — attributing that time to a guessed event
    // would be indistinguishable from a measurement afterwards.
    await beginSpan("e1", 7, START);
    await switchToTab(999, START + 10_000);
    await endOpenSpan("blur", START + 60_000);

    const spans = await storedSpans();
    expect(spans).toHaveLength(1);
    expect(spans[0]?.eventId).toBe("e1");
    expect(spans[0]?.activeSeconds).toBe(10);
  });

  it("ends a span when its tab closes", async () => {
    await beginSpan("e1", 7, START);
    await forgetTab(7, START + 12_000);

    const spans = await storedSpans();
    expect(spans[0]).toMatchObject({ endReason: "tab-closed", activeSeconds: 12 });
  });

  it("forgets a closed tab, so switching back attributes nothing", async () => {
    await beginSpan("e1", 7, START);
    await forgetTab(7, START + 5000);
    await switchToTab(7, START + 10_000);
    await endOpenSpan("blur", START + 60_000);

    expect(await storedSpans()).toHaveLength(1);
  });
});

describe("the storage guard", () => {
  it("refuses a span attributed to nothing", () => {
    expect(() =>
      assertStorableSpan({
        spanId: "x",
        eventId: "",
        startedAt: new Date(START).toISOString(),
        endedAt: new Date(START + 1000).toISOString(),
        activeSeconds: 1,
        endReason: "blur",
      }),
    ).toThrow(/attributed to nothing/);
  });

  it("refuses a non-positive duration", () => {
    expect(() =>
      assertStorableSpan({
        spanId: "x",
        eventId: "e1",
        startedAt: new Date(START).toISOString(),
        endedAt: new Date(START).toISOString(),
        activeSeconds: 0,
        endReason: "blur",
      }),
    ).toThrow(/absence of a measurement/);
  });

  it("refuses an unexpected field", () => {
    expect(() =>
      assertStorableSpan({
        spanId: "x",
        eventId: "e1",
        startedAt: new Date(START).toISOString(),
        endedAt: new Date(START + 1000).toISOString(),
        activeSeconds: 1,
        endReason: "blur",
        url: "https://example.com/secret",
      } as unknown as AttentionSpan),
    ).toThrow(/unexpected fields/);
  });
});
