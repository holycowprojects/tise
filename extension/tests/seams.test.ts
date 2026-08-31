/**
 * The seam between a build and the state a previous build left behind.
 *
 * **Five defects were found in one day, and every one of them lived here.** D105 a stale
 * preprocessor, D106 two code paths assumed equivalent, D107 an ordering inside one
 * function, D108 a label on a number, D109 a number without its baseline. Not one was
 * caught by the 460 tests already in this suite, because **every one of those tests writes
 * its own state with the current build and then reads it back with the current build**.
 * They test one build against itself. The seam is invisible from inside.
 *
 * This file is the deliberate pass over that class, and its rule is simple: **write the
 * old shape, then use the current code.** Nothing here constructs state through the normal
 * API — that would defeat the entire point.
 *
 * D105's rule, which this file exists to enforce going forward: a stored shape that
 * acquires a version needs a migration **and** a test that writes the old shape, in the
 * same commit.
 *
 * Everything Tise persists is enumerated below, so a reader can see what is covered and
 * what is not, rather than inferring it from which tests happen to exist.
 */
import "fake-indexeddb/auto";
import { IDBFactory } from "fake-indexeddb";
import { openDB } from "idb";
import { beforeEach, describe, expect, it } from "vitest";
import { closeTiseDb, openTiseDb, readMeta, writeMeta } from "../src/storage/db";
import { allEvents, countEvents, putEvents } from "../src/storage/events";
import { allSpans, countSpans } from "../src/storage/spans";
import { coverageGaps, isFullyCovered } from "../src/storage/coverage";
import { DEFAULT_SETTINGS, loadSettings, saveSettings } from "../src/storage/settings";
import { importProgress } from "../src/collect/import";
import { rejectionCounts } from "../src/collect/collector";
import { readJob, readModel } from "../src/model/train";
import { buildExport } from "../src/storage/export";
import { enforceRetention } from "../src/storage/retention";
import type { TiseEvent } from "../src/types";

const START = Date.parse("2026-06-01T09:00:00.000Z");
const CONSENT = "2026-05-01T00:00:00.000Z";

function event(index: number, overrides: Partial<TiseEvent> = {}): TiseEvent {
  return {
    eventId: `e${index}`,
    occurredAt: new Date(START + index * 60_000).toISOString(),
    source: "live",
    domain: "example.com",
    category: "video",
    transition: "link",
    dwellSeconds: null,
    sessionId: "s1",
    ...overrides,
  };
}


/**
 * A row with one field removed — the shape an older build wrote.
 *
 * A helper rather than destructuring-with-rest, because the discarded binding is unused by
 * definition and the linter is right to say so. Typed loosely on purpose: the whole point
 * is to produce something the current type says cannot exist.
 */
function without(row: TiseEvent, field: keyof TiseEvent): TiseEvent {
  const copy: Record<string, unknown> = { ...row };
  delete copy[field];
  return copy as unknown as TiseEvent;
}

beforeEach(async () => {
  await closeTiseDb();
  globalThis.indexedDB = new IDBFactory();
});

/**
 * The database itself. `openTiseDb` creates any store it does not find, so it upgrades
 * from any earlier version — but nothing had ever opened a database that was actually at
 * an earlier version, so "it upgrades" was a reading of the code rather than a result.
 */
describe("a database left at an older version", () => {
  /** Exactly the v4 schema: everything except `attention`, which D96 added at v5. */
  async function createV4WithData(): Promise<void> {
    const db = await openDB("tise", 4, {
      upgrade(database) {
        const events = database.createObjectStore("events", { keyPath: "eventId" });
        events.createIndex("occurredAt", "occurredAt");
        events.createIndex("category", "category");
        events.createIndex("sessionId", "sessionId");
        database.createObjectStore("meta");
        const features = database.createObjectStore("features", {
          keyPath: ["featureSet", "subject", "windowEnd"],
        });
        features.createIndex("windowEnd", "windowEnd");
        features.createIndex("subject", "subject");
        const labels = database.createObjectStore("labels", {
          keyPath: ["target", "subject", "windowEnd"],
        });
        labels.createIndex("windowEnd", "windowEnd");
        labels.createIndex("subject", "subject");
        const predictions = database.createObjectStore("predictions", {
          keyPath: ["target", "subject", "windowStart"],
        });
        predictions.createIndex("windowEnd", "windowEnd");
        predictions.createIndex("outcome", "outcome");
        predictions.createIndex("subject", "subject");
      },
    });
    await db.put("events", event(1));
    await db.put("events", event(2));
    await db.put("meta", { consentGrantedAt: CONSENT, paused: false }, "settings");
    db.close();
  }

  it("upgrades to v5 and gains the attention store", async () => {
    await createV4WithData();
    const db = await openTiseDb();
    expect(db.version).toBe(5);
    expect([...db.objectStoreNames].sort()).toContain("attention");
    expect(await countSpans()).toBe(0);
  });

  it("keeps every event the older version had written", async () => {
    // The failure that would matter: an upgrade that recreated a store would delete a
    // person's entire history, silently, on the update that introduced it.
    await createV4WithData();
    expect(await countEvents()).toBe(2);
    expect((await allEvents()).map((e) => e.eventId).sort()).toEqual(["e1", "e2"]);
  });

  it("keeps the settings the older version had written", async () => {
    await createV4WithData();
    const settings = await loadSettings();
    expect(settings.consentGrantedAt).toBe(CONSENT);
    // Fields the older build never wrote come from the defaults rather than undefined.
    expect(settings.sessionTimeoutSeconds).toBe(DEFAULT_SETTINGS.sessionTimeoutSeconds);
    expect(settings.rawRetentionDays).toBe(DEFAULT_SETTINGS.rawRetentionDays);
    expect(settings.overrides).toEqual({});
  });

  it("can still write after the upgrade", async () => {
    // An upgrade that leaves the database readable but not writable is a state no test
    // that only reads would notice.
    await createV4WithData();
    await putEvents([event(3)]);
    expect(await countEvents()).toBe(3);
  });
});

/**
 * `meta` holds nine unrelated shapes under nine keys, none of them versioned. Each is read
 * back by code that has changed since it was written, and a missing field reads as
 * `undefined` rather than throwing — which is the quiet failure mode this whole file is
 * about.
 */
describe("settings written by an older build", () => {
  it("fills in fields that did not exist yet", async () => {
    await writeMeta("settings", { consentGrantedAt: CONSENT, paused: true });
    const settings = await loadSettings();
    expect(settings.paused).toBe(true);
    expect(settings.overrides).toEqual({});
    expect(settings.rawRetentionDays).toBe(DEFAULT_SETTINGS.rawRetentionDays);
  });

  it("survives a stored object with nothing in it", async () => {
    await writeMeta("settings", {});
    expect(await loadSettings()).toEqual(DEFAULT_SETTINGS);
  });

  it("does not let an explicit undefined erase a default", async () => {
    // `{...defaults, ...stored}` copies an own property whose value is undefined, so a
    // build that wrote `overrides: undefined` would leave `overrides` undefined here and
    // every `settings.overrides[domain]` lookup downstream would throw.
    await writeMeta("settings", {
      consentGrantedAt: CONSENT,
      overrides: undefined,
      sessionTimeoutSeconds: undefined,
    });
    const settings = await loadSettings();
    expect(settings.overrides).toEqual({});
    expect(settings.sessionTimeoutSeconds).toBe(DEFAULT_SETTINGS.sessionTimeoutSeconds);
  });

  it("writes a complete object back, so the gap does not persist", async () => {
    await writeMeta("settings", { consentGrantedAt: CONSENT });
    await saveSettings({ paused: true });
    const stored = await readMeta<Record<string, unknown>>("settings");
    expect(Object.keys(stored ?? {}).sort()).toEqual(
      Object.keys(DEFAULT_SETTINGS).sort(),
    );
  });
});

describe("meta keys an older build wrote", () => {
  it("reads no coverage log as full coverage having never been recorded", async () => {
    // Absent, not empty. `coverageGaps` returning `[]` for "never written" is correct
    // only because consent is checked separately — asserted here so the pair stays true.
    expect(await coverageGaps()).toEqual([]);
    expect(isFullyCovered(START, START + 3_600_000, [], null, START)).toBe(false);
  });

  it("treats a gap with a missing end as still open", async () => {
    // An older build could have omitted `to` rather than writing null. Both must mean
    // "still open", because reading it as closed would score windows nobody watched.
    await writeMeta("coverage:gaps", [{ from: new Date(START).toISOString() }]);
    const gaps = await coverageGaps();
    expect(
      isFullyCovered(START + 60_000, START + 120_000, gaps, CONSENT, START + 600_000),
    ).toBe(false);
  });

  it("reports no import when the progress key was never written", async () => {
    expect(await importProgress()).toBeUndefined();
  });

  it("reports no rejections when the counter was never written", async () => {
    expect(await rejectionCounts()).toEqual({});
  });

  it("reports no training job and no model on an empty store", async () => {
    expect(await readJob()).toBeUndefined();
    expect(await readModel()).toBeUndefined();
  });
});

/**
 * Events are the one shape with no version and no migration, because it has never changed.
 * That is worth an assertion rather than a memory: if a field is ever added, these fail and
 * the person adding it has to decide what old rows mean.
 */
describe("events written before a field existed", () => {
  it("survives a row with no source, and does not invent one", async () => {
    const db = await openTiseDb();
    await db.put("events", without(event(1), "source"));

    const [stored] = await allEvents();
    expect(stored?.eventId).toBe("e1");
    // Undefined rather than "live": guessing would move a row from the imported side of
    // D88's rule to the side that is allowed to score.
    expect(stored?.source).toBeUndefined();
  });

  it("counts a source-less row as imported rather than as live", async () => {
    // The consequence that matters. `browsingSummary` splits live from imported, and a
    // row with no source must not be counted as something Tise watched.
    const db = await openTiseDb();
    await db.put("events", without(event(1), "source"));
    const { browsingSummary } = await import("../src/model/overview");
    const summary = browsingSummary(await allEvents(), 1, []);
    expect(summary.liveEvents).toBe(0);
    expect(summary.importedEvents).toBe(1);
  });

  it("exports a row an older build wrote without dropping it", async () => {
    const db = await openTiseDb();
    await db.put("events", without(event(1), "dwellSeconds"));
    const exported = await buildExport({ now: START, extensionVersion: "0.1.0" });
    expect(exported.events).toHaveLength(1);
  });
});

/**
 * Retention deletes by timestamp, so it runs over rows every earlier build wrote. It is
 * the one job that is *destructive*, which makes it the worst place for a shape surprise.
 */
describe("retention over rows an older build wrote", () => {
  it("cannot see or delete a row with no timestamp — so the write guard must stop one", async () => {
    // **The finding, and it is a latent one rather than an active bug.** `occurredAt` is
    // the `events` index, and IndexedDB omits a row from an index it has no key for. So a
    // row written without it sits in the store, invisible to `allEvents`, absent from
    // every export, and unreachable by retention — which walks the same index. It would
    // survive "delete everything older than 30 days" forever and never appear anywhere.
    //
    // No build has ever written one. This asserts both halves: the store really does hide
    // such a row, and `assertStorable` now refuses to create one, which is where the
    // problem is actually solved.
    const db = await openTiseDb();
    await db.put("events", without(event(1), "occurredAt"));
    await db.put("events", event(2, { occurredAt: new Date(START).toISOString() }));

    expect(await countEvents()).toBe(2);
    // Invisible: in the store, absent from every reader.
    expect((await allEvents()).map((e) => e.eventId)).toEqual(["e2"]);

    await saveSettings({ consentGrantedAt: CONSENT, rawRetentionDays: 30 });
    await enforceRetention(await loadSettings(), START + 365 * 86_400_000);
    // Undeletable: retention expired the dated row and could not reach the undated one.
    expect(await countEvents()).toBe(1);
    expect(await allEvents()).toEqual([]);
  });

  it("refuses to write an event missing any declared field", async () => {
    // Where the hazard is actually closed. `assertStorable` checked for unexpected fields
    // and never for missing ones, which is the half that would have let one in.
    await expect(putEvents([without(event(1), "occurredAt")])).rejects.toThrow(
      /missing: occurredAt/,
    );
    await expect(putEvents([without(event(2), "source")])).rejects.toThrow(
      /missing: source/,
    );
    expect(await countEvents()).toBe(0);
  });

  it("leaves the attention store alone when it is empty", async () => {
    await saveSettings({ consentGrantedAt: CONSENT, rawRetentionDays: 30 });
    await enforceRetention(await loadSettings(), START + 365 * 86_400_000);
    expect(await allSpans()).toEqual([]);
  });
});
