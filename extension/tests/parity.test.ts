/**
 * The parity suite. The most important test in the project.
 *
 * Features are implemented twice — TypeScript in the product, Python in the research
 * tier. If they drift, every published benchmark describes a model that was never
 * shipped, and nothing else in either suite would notice. So both run over
 * `research/fixtures/parity_events.json` and are measured against the same oracle,
 * `parity_expected.json`, which Python generates and neither language may quietly
 * regenerate to make a failure go away.
 *
 * **What is compared and what is not.** Instants are compared as epoch milliseconds, not
 * as strings. Session *ids* are not compared at all: they are locally assigned and opaque
 * (D36), and pinning Python's `isoformat` against JavaScript's `toISOString` across
 * microsecond precision would buy nothing and break quietly. What must agree is the
 * grouping and the numbers, and that is what these assertions cover.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { advanceSession, type SessionCursor } from "../src/collect/session";
import { resolve } from "../src/collect/resolver";
import { FEATURE_SET, hoursSinceLastSeen } from "../src/features/recency";
import { sessionise } from "../src/features/sessions";
import type { TiseEvent } from "../src/types";

const TOLERANCE = 1e-9;

interface FixtureInput {
  categoryMapVersion: number;
  timeoutSeconds: number;
  horizonHours: number;
  overrides: Record<string, string>;
  events: Array<{
    eventId: string;
    occurredAt: string;
    domain: string;
    transition: string;
    dwellSeconds: number | null;
    source: "live" | "import";
  }>;
}

interface FixtureExpected {
  categoryMapVersion: number;
  timeoutSeconds: number;
  featureSet: string;
  resolutions: Array<{ domain: string; category: string; source: string }>;
  sessions: Array<{
    sessionId: string;
    startedAt: string;
    endedAt: string;
    durationSeconds: number;
    eventIds: string[];
    categories: string[];
  }>;
  labels: unknown[];
  features: Array<{
    subject: string;
    windowEnd: string;
    values: Record<string, number | null>;
  }>;
  summary: Record<string, number>;
}

function fixture<T>(name: string): T {
  return JSON.parse(
    readFileSync(fileURLToPath(new URL(`../../research/fixtures/${name}`, import.meta.url)), "utf8"),
  ) as T;
}

const INPUT = fixture<FixtureInput>("parity_events.json");
const EXPECTED = fixture<FixtureExpected>("parity_expected.json");

/** Resolve the input into events, exactly as the Python generator does. */
const EVENTS: TiseEvent[] = INPUT.events.map((row) => ({
  eventId: row.eventId,
  occurredAt: row.occurredAt,
  source: row.source,
  domain: row.domain,
  category: resolve(row.domain, INPUT.overrides).category,
  transition: row.transition,
  dwellSeconds: row.dwellSeconds,
  sessionId: "",
}));

function closeEnough(actual: number | null, expected: number | null, what: string): void {
  if (expected === null || actual === null) {
    expect(actual, `${what}: null-ness must match, never be substituted`).toBe(expected);
    return;
  }
  expect(Math.abs(actual - expected), `${what}: ${actual} vs ${expected}`).toBeLessThanOrEqual(
    TOLERANCE,
  );
}

describe("the fixture itself", () => {
  it("is the version this build expects", () => {
    expect(EXPECTED.categoryMapVersion).toBe(INPUT.categoryMapVersion);
    expect(EXPECTED.featureSet).toBe(FEATURE_SET);
    expect(INPUT.timeoutSeconds).toBe(EXPECTED.timeoutSeconds);
  });

  it("has no section TypeScript silently ignores", () => {
    // If Python adds a section to the oracle, this fails and forces a decision rather
    // than letting an unchecked section look verified. `labels` is checked at T10.
    expect(Object.keys(EXPECTED).sort()).toEqual([
      "categoryMapVersion",
      "featureSet",
      "features",
      "horizonHours",
      "labels",
      "note",
      "resolutions",
      "sessions",
      "summary",
      "timeoutSeconds",
    ]);
  });

  it("hands TypeScript no categories — resolving is part of what is compared", () => {
    for (const row of INPUT.events) {
      expect(row).not.toHaveProperty("category");
    }
  });
});

describe("resolver parity", () => {
  it("agrees on every domain, and on which layer answered", () => {
    for (const expected of EXPECTED.resolutions) {
      const actual = resolve(expected.domain, INPUT.overrides);
      expect(actual.category, expected.domain).toBe(expected.category);
      expect(actual.source, expected.domain).toBe(expected.source);
    }
  });

  it("covers all four layers, so no layer is parity-tested by accident", () => {
    const sources = new Set(EXPECTED.resolutions.map((r) => r.source));
    expect([...sources].sort()).toEqual(["fallback", "map", "override", "rule"]);
  });
});

describe("sessioniser parity", () => {
  const actual = sessionise(EVENTS, INPUT.timeoutSeconds);

  it("finds the same number of sessions", () => {
    expect(actual).toHaveLength(EXPECTED.sessions.length);
    expect(actual).toHaveLength(EXPECTED.summary["sessionCount"] as number);
  });

  it("puts the same events in the same sessions", () => {
    EXPECTED.sessions.forEach((expected, index) => {
      expect(actual[index]?.eventIds, `session ${index}`).toEqual(expected.eventIds);
    });
  });

  it("agrees on start and end instants", () => {
    EXPECTED.sessions.forEach((expected, index) => {
      expect(Date.parse(actual[index]?.startedAt ?? "")).toBe(Date.parse(expected.startedAt));
      expect(Date.parse(actual[index]?.endedAt ?? "")).toBe(Date.parse(expected.endedAt));
    });
  });

  it("agrees on duration and categories", () => {
    EXPECTED.sessions.forEach((expected, index) => {
      closeEnough(
        actual[index]?.durationSeconds ?? null,
        expected.durationSeconds,
        `session ${index} duration`,
      );
      expect(actual[index]?.categories).toEqual(expected.categories);
    });
  });

  it("splits on a gap one second past the timeout and not on one exactly at it", () => {
    // The two cases the fixture exists for. Named here so a regression reads as itself
    // rather than as "session 2 has the wrong events".
    expect(actual[0]?.eventIds).toEqual(["evt-000", "evt-001", "evt-002"]);
    expect(actual[1]?.eventIds?.[0]).toBe("evt-003");
  });
});

describe("the two TypeScript sessionisers agree with each other", () => {
  it("live assignment reproduces the batch grouping", () => {
    // `collect/session.ts` assigns sessions one event at a time because live collection
    // cannot see the future; `features/sessions.ts` sees the whole corpus. Same rule,
    // two implementations, and a disagreement would put live and imported events in
    // different sessions for the same browsing.
    const ordered = [...EVENTS].sort((a, b) => Date.parse(a.occurredAt) - Date.parse(b.occurredAt));

    let cursor: SessionCursor | null = null;
    const liveGrouping: string[][] = [];
    for (const event of ordered) {
      const next = advanceSession(cursor, event.occurredAt, INPUT.timeoutSeconds);
      if (cursor === null || next.sessionId !== cursor.sessionId) liveGrouping.push([]);
      (liveGrouping[liveGrouping.length - 1] as string[]).push(event.eventId);
      cursor = next;
    }

    expect(liveGrouping).toEqual(
      sessionise(EVENTS, INPUT.timeoutSeconds).map((session) => [...session.eventIds]),
    );
  });
});

describe("feature parity", () => {
  it("computes every feature row to within 1e-9", () => {
    expect(EXPECTED.features.length).toBeGreaterThan(0);

    EXPECTED.features.forEach((expected, index) => {
      const windowEnd = Date.parse(expected.windowEnd);
      const actual = hoursSinceLastSeen(EVENTS, expected.subject, windowEnd);
      closeEnough(
        actual,
        expected.values["hoursSinceLastSeen"] ?? null,
        `row ${index} (${expected.subject} @ ${expected.windowEnd})`,
      );
    });
  });

  it("reproduces null rather than substituting a sentinel", () => {
    const nulls = EXPECTED.features.filter((f) => f.values["hoursSinceLastSeen"] === null);
    expect(nulls.length, "the fixture must contain a never-seen case").toBeGreaterThan(0);

    for (const row of nulls) {
      expect(hoursSinceLastSeen(EVENTS, row.subject, Date.parse(row.windowEnd))).toBeNull();
    }
  });

  it("reproduces a repeating decimal, where a float bug would show", () => {
    const repeating = EXPECTED.features.find(
      (f) => String(f.values["hoursSinceLastSeen"]).length > 8,
    );
    expect(repeating, "the fixture must contain a non-terminating value").toBeDefined();
    closeEnough(
      hoursSinceLastSeen(EVENTS, repeating!.subject, Date.parse(repeating!.windowEnd)),
      repeating!.values["hoursSinceLastSeen"] ?? null,
      "repeating decimal",
    );
  });

  it("filters strictly before windowEnd — the leakage guard", () => {
    const future: TiseEvent = {
      eventId: "leak",
      occurredAt: "2026-06-09T00:00:00+00:00",
      source: "import",
      domain: "youtube.com",
      category: "video",
      transition: "link",
      dwellSeconds: null,
      sessionId: "",
    };

    for (const row of EXPECTED.features) {
      const windowEnd = Date.parse(row.windowEnd);
      const before = hoursSinceLastSeen(EVENTS, row.subject, windowEnd);
      const after = hoursSinceLastSeen([...EVENTS, future], row.subject, windowEnd);
      expect(after, `${row.subject} moved when a future event was appended`).toBe(before);
    }
  });
});
