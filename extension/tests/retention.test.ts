/**
 * Retention and deletion. The two operations a privacy claim actually rests on.
 */
import "fake-indexeddb/auto";
import { IDBFactory } from "fake-indexeddb";
import { beforeEach, describe, expect, it } from "vitest";
import { closeTiseDb, readMeta, writeMeta } from "../src/storage/db";
import { deleteEverything, isEmpty } from "../src/storage/delete";
import { allEvents, countEvents, putEvents } from "../src/storage/events";
import { enforceRetention, RETENTION_PERIOD_MINUTES } from "../src/storage/retention";
import {
  DEFAULT_SETTINGS,
  loadSettings,
  saveSettings,
  type Settings,
} from "../src/storage/settings";
import { allFeatureRows, countFeatureRows, putFeatureRows } from "../src/storage/features";
import { FEATURE_SET, type FeatureRow } from "../src/features/vector";
import type { TiseEvent } from "../src/types";

const NOW = Date.parse("2026-08-26T12:00:00.000Z");
const DAY = 24 * 60 * 60 * 1000;

function eventAt(daysAgo: number): TiseEvent {
  const at = new Date(NOW - daysAgo * DAY).toISOString();
  return {
    eventId: `e${daysAgo}`,
    occurredAt: at,
    source: "import",
    domain: "example.com",
    category: "unknown",
    transition: "link",
    dwellSeconds: null,
    sessionId: at,
  };
}

function settings(overrides: Partial<Settings> = {}): Settings {
  return { ...DEFAULT_SETTINGS, ...overrides };
}

beforeEach(async () => {
  await closeTiseDb();
  globalThis.indexedDB = new IDBFactory();
  await putEvents([eventAt(0), eventAt(10), eventAt(29), eventAt(31), eventAt(400)]);
});

describe("retention", () => {
  it("deletes raw events past the window and keeps the rest", async () => {
    const outcome = await enforceRetention(settings({ rawRetentionDays: 30 }), NOW);

    expect(outcome.deleted).toBe(2);
    expect(await countEvents()).toBe(3);
    expect((await allEvents()).map((e) => e.eventId)).toEqual(["e29", "e10", "e0"]);
  });

  it("treats 0 as keep forever, not as delete everything", async () => {
    const outcome = await enforceRetention(settings({ rawRetentionDays: 0 }), NOW);

    expect(outcome).toEqual({ deleted: 0, cutoff: null });
    expect(await countEvents()).toBe(5);
  });

  it("defaults to 30 days", () => {
    expect(DEFAULT_SETTINGS.rawRetentionDays).toBe(30);
  });

  it("keeps an event exactly on the boundary", async () => {
    await closeTiseDb();
    globalThis.indexedDB = new IDBFactory();
    await putEvents([eventAt(30)]);

    await enforceRetention(settings({ rawRetentionDays: 30 }), NOW);
    expect(await countEvents()).toBe(1);
  });

  it("is idempotent — a second pass deletes nothing more", async () => {
    await enforceRetention(settings({ rawRetentionDays: 30 }), NOW);
    const second = await enforceRetention(settings({ rawRetentionDays: 30 }), NOW);

    expect(second.deleted).toBe(0);
    expect(await countEvents()).toBe(3);
  });

  it("never touches the meta store, where settings and cursors live", async () => {
    await writeMeta("sessionCursor", { sessionId: "s", lastEventAt: "x" });
    await enforceRetention(settings({ rawRetentionDays: 30 }), NOW);

    expect(await readMeta("sessionCursor")).toEqual({ sessionId: "s", lastEventAt: "x" });
  });

  it("runs often enough to matter and rarely enough to ignore", () => {
    expect(RETENTION_PERIOD_MINUTES).toBe(360);
  });
});

describe("delete everything", () => {
  it("leaves zero rows in every store", async () => {
    await saveSettings({ consentGrantedAt: new Date(NOW).toISOString() });
    await writeMeta("rejections", { redirect: 4 });

    const outcome = await deleteEverything();

    expect(outcome.eventsDeleted).toBe(5);
    expect(outcome.metaKeysDeleted).toBeGreaterThan(0);
    expect(await isEmpty()).toBe(true);
  });

  it("takes consent with it, returning Tise to the state it installs in", async () => {
    await saveSettings({ consentGrantedAt: new Date(NOW).toISOString(), paused: true });
    await deleteEverything();

    const after = await loadSettings();
    expect(after.consentGrantedAt).toBeNull();
    expect(after.paused).toBe(false);
    expect(after).toEqual(DEFAULT_SETTINGS);
  });

  it("forgets the import too, so nothing claims a history that is gone", async () => {
    await writeMeta("importProgress", { state: "done", eventsWritten: 900 });
    await deleteEverything();

    expect(await readMeta("importProgress")).toBeUndefined();
  });
});

describe("feature rows outlive raw events (D11)", () => {
  const row = {
    subject: "video",
    windowEnd: new Date(NOW - 400 * DAY).toISOString(),
    featureSet: FEATURE_SET,
    compat: "history" as const,
    values: { hoursSinceLastSeen: 1.5 },
  } as unknown as FeatureRow;

  it("retention deletes raw events and leaves the derived rows alone", async () => {
    await putFeatureRows([row]);
    expect(await countFeatureRows()).toBe(1);

    const outcome = await enforceRetention(settings({ rawRetentionDays: 30 }), NOW);

    expect(outcome.deleted).toBe(2);
    // The row's own window is 400 days old — far outside retention — and it survives.
    // That is the whole privacy design: keep what was learned, not the browsing.
    expect(await countFeatureRows()).toBe(1);
  });

  it("but delete-all takes them too", async () => {
    await putFeatureRows([row]);
    const outcome = await deleteEverything();

    expect(outcome.featureRowsDeleted).toBe(1);
    expect(await countFeatureRows()).toBe(0);
    expect(await isEmpty()).toBe(true);
  });

  it("recomputing a window replaces the row rather than duplicating it", async () => {
    await putFeatureRows([row]);
    await putFeatureRows([
      { ...row, values: { ...row.values, hoursSinceLastSeen: 99 } } as FeatureRow,
    ]);

    expect(await countFeatureRows()).toBe(1);
    expect((await allFeatureRows())[0]?.values["hoursSinceLastSeen"]).toBe(99);
  });
});
