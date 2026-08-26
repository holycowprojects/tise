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
import { hoursSinceLastSeen } from "../src/features/recency";
import { sessionise } from "../src/features/sessions";
import { dayOfWeek } from "../src/features/context";
import {
  computeFeatures,
  FEATURE_NAMES,
  FEATURE_SET,
  type FeatureName,
} from "../src/features/vector";
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
  featureNames: string[];
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
    compat: string;
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
      "featureNames",
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
  const OPTIONS = {
    timeoutSeconds: INPUT.timeoutSeconds,
    horizonHours: INPUT.horizonHours,
  };

  it("agrees on the feature set and the column order", () => {
    expect(EXPECTED.featureSet).toBe(FEATURE_SET);
    expect([...FEATURE_NAMES]).toEqual(EXPECTED.featureNames);
  });

  it("computes every value of every row to within 1e-9", () => {
    expect(EXPECTED.features.length).toBeGreaterThan(0);

    EXPECTED.features.forEach((expected, index) => {
      const windowEnd = Date.parse(expected.windowEnd);
      const actual = computeFeatures(EVENTS, expected.subject, windowEnd, OPTIONS);

      expect(actual.compat, `row ${index} compat`).toBe(expected.compat);
      expect(Object.keys(actual.values).sort()).toEqual(Object.keys(expected.values).sort());

      for (const name of FEATURE_NAMES) {
        closeEnough(
          actual.values[name],
          expected.values[name] ?? null,
          `row ${index} (${expected.subject} @ ${expected.windowEnd}) ${name}`,
        );
      }
    });
  });

  it("tags every feature `history`, because D35 left the `full` class empty", () => {
    for (const row of EXPECTED.features) expect(row.compat).toBe("history");
  });

  it("reproduces null rather than substituting a sentinel", () => {
    const nulled = new Set<string>();
    for (const row of EXPECTED.features) {
      for (const name of FEATURE_NAMES) {
        if (row.values[name] === null) {
          nulled.add(name);
          const actual = computeFeatures(
            EVENTS,
            row.subject,
            Date.parse(row.windowEnd),
            OPTIONS,
          );
          expect(actual.values[name], `${name} must be null, not a stand-in`).toBeNull();
        }
      }
    }
    expect(nulled.size, "the fixture must exercise absence").toBeGreaterThan(0);
  });

  it("exercises priorReturnRate with real variety, not just null and zero", () => {
    // The strongest feature and the one that leaks if written the obvious way, so a
    // fixture where it is null everywhere would be worth very little.
    const rates = EXPECTED.features
      .map((row) => row.values["priorReturnRate"])
      .filter((value): value is number => value !== null && value !== undefined);

    expect(rates.length).toBeGreaterThanOrEqual(4);
    expect(new Set(rates).size).toBeGreaterThanOrEqual(3);
    expect(rates.some((rate) => rate > 0 && rate < 1)).toBe(true);
  });

  it("reproduces repeating decimals, where a float bug would show", () => {
    // Carry the subject along. Two rows share a windowEnd — `search` and `video` both
    // close at 09:50 on day one — so looking the subject up by window afterwards finds
    // the wrong row. That mistake made this test fail against correct code once.
    const repeating: Array<{ subject: string; windowEnd: string; name: FeatureName; value: number }> =
      [];
    for (const row of EXPECTED.features) {
      for (const name of FEATURE_NAMES) {
        const value = row.values[name];
        if (typeof value === "number" && String(value).length > 12) {
          repeating.push({ subject: row.subject, windowEnd: row.windowEnd, name, value });
        }
      }
    }
    expect(repeating.length, "a fixture of round numbers proves little").toBeGreaterThan(0);

    // Recompute them, rather than only asserting the fixture contains them.
    for (const { subject, windowEnd, name, value } of repeating) {
      const actual = computeFeatures(EVENTS, subject, Date.parse(windowEnd), OPTIONS);
      closeEnough(actual.values[name], value, `${subject} ${name} @ ${windowEnd}`);
    }
  });

  it("gets Monday=0 right — JavaScript counts weekdays from Sunday", () => {
    // 2026-06-01 is a Monday. Python's weekday() says 0; getUTCDay() says 1. Without the
    // conversion in context.ts every day-of-week coefficient would be shifted by one.
    //
    // This asserts against the *implementation*. An earlier version of this test read
    // the value out of the fixture instead, which meant it could never fail from a
    // TypeScript bug — it was checking that Python had written what Python wrote.
    expect(dayOfWeek(Date.parse("2026-06-01T09:50:00+00:00"))).toBe(0);
    expect(dayOfWeek(Date.parse("2026-06-07T09:00:00+00:00"))).toBe(6); // Sunday

    const monday = EXPECTED.features.find((row) => row.windowEnd.startsWith("2026-06-01"));
    expect(monday?.values["dayOfWeek"]).toBe(0);
  });

  it("filters strictly before windowEnd — the leakage guard, on the whole vector", () => {
    const future: TiseEvent = {
      eventId: "leak",
      occurredAt: "2026-07-01T00:00:00+00:00",
      source: "import",
      domain: "youtube.com",
      category: "video",
      transition: "link",
      dwellSeconds: null,
      sessionId: "",
    };

    for (const row of EXPECTED.features) {
      const windowEnd = Date.parse(row.windowEnd);
      const before = computeFeatures(EVENTS, row.subject, windowEnd, OPTIONS);
      const after = computeFeatures([...EVENTS, future], row.subject, windowEnd, OPTIONS);
      expect(after.values, `${row.subject} @ ${row.windowEnd} moved`).toEqual(before.values);
    }
  });

  it("does not let a near-future event extend the session it describes", () => {
    // The subtlest leak in the set. An event inside the timeout after windowEnd would
    // merge into the label's own session if context.ts re-derived it from the whole
    // corpus, and sessionEventCount would change retroactively.
    const row = EXPECTED.features[0] as (typeof EXPECTED.features)[number];
    const windowEnd = Date.parse(row.windowEnd);

    const soon: TiseEvent = {
      eventId: "soon",
      occurredAt: new Date(windowEnd + 10 * 60_000).toISOString(),
      source: "import",
      domain: "github.com",
      category: "dev",
      transition: "link",
      dwellSeconds: null,
      sessionId: "",
    };

    const before = computeFeatures(EVENTS, row.subject, windowEnd, OPTIONS);
    const after = computeFeatures([...EVENTS, soon], row.subject, windowEnd, OPTIONS);
    expect(after.values["sessionEventCount"]).toBe(before.values["sessionEventCount"]);
    expect(after.values).toEqual(before.values);
  });

  it("still agrees on the single feature T9 pinned", () => {
    for (const row of EXPECTED.features) {
      closeEnough(
        hoursSinceLastSeen(EVENTS, row.subject, Date.parse(row.windowEnd)),
        row.values["hoursSinceLastSeen"] ?? null,
        `${row.subject} hoursSinceLastSeen`,
      );
    }
  });
});
