/**
 * The export, checked against the same file the Python loader is checked against:
 * `research/fixtures/export_v2.json`.
 *
 * `export_v1.json` is kept frozen next to it and is **not** updated: the Python loader
 * still reads it, which is how the backward-compatibility promise is tested rather than
 * asserted. Someone who exported their browsing before the registry existed should not
 * find the file unreadable because a later version added a key.
 *
 * This is the third shared-data contract in the project, after `domains.json` and
 * `domain_cases.json`. Neither language owns the fixture. If the exporter's shape drifts
 * from what `tise_research.data.load` reads, one of the two suites fails and says which.
 */
import "fake-indexeddb/auto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { IDBFactory } from "fake-indexeddb";
import { beforeEach, describe, expect, it } from "vitest";
import { closeTiseDb } from "../src/storage/db";
import { putEvents } from "../src/storage/events";
import { putSpans } from "../src/storage/spans";
import { putPredictions } from "../src/storage/predictions";
import { saveSettings } from "../src/storage/settings";
import {
  buildExport,
  EXPORT_SCHEMA,
  exportFilename,
  serialiseExport,
  type TiseExport,
} from "../src/storage/export";
import { EVENT_FIELDS, type TiseEvent } from "../src/types";

const FIXTURE_PATH = fileURLToPath(
  new URL("../../research/fixtures/export_v3.json", import.meta.url),
);
const FIXTURE: TiseExport = JSON.parse(readFileSync(FIXTURE_PATH, "utf8"));

/**
 * v1 and v2 are frozen next to v3 and are never regenerated (D76). They exist so that
 * "old exports still load" is tested rather than asserted — the Python loader reads all
 * three, and a file a person exported last year must not become unreadable because the
 * exporter moved on.
 */
const FROZEN: TiseExport[] = ["export_v1.json", "export_v2.json"].map((name) =>
  JSON.parse(
    readFileSync(fileURLToPath(new URL(`../../research/fixtures/${name}`, import.meta.url)), "utf8"),
  ),
);

const NOW = Date.parse(FIXTURE.exportedAt);

beforeEach(async () => {
  await closeTiseDb();
  globalThis.indexedDB = new IDBFactory();
  await putEvents(FIXTURE.events as TiseEvent[]);
  await putPredictions(FIXTURE.predictions);
  await putSpans(FIXTURE.attention);
  await saveSettings({
    sessionTimeoutSeconds: FIXTURE.sessionTimeoutSeconds,
    rawRetentionDays: FIXTURE.rawRetentionDays,
    overrides: FIXTURE.overrides,
  });
});

describe("the export contract", () => {
  it("reproduces the fixture exactly", async () => {
    const built = await buildExport({ now: NOW, extensionVersion: FIXTURE.extensionVersion });
    expect(built).toEqual(FIXTURE);
  });

  it("declares its schema, so the loader can refuse an unknown one", async () => {
    const built = await buildExport({ now: NOW, extensionVersion: "0.1.0" });
    expect(built.schema).toBe(EXPORT_SCHEMA);
  });

  it("carries the versions a benchmark needs to be reproducible", async () => {
    const built = await buildExport({ now: NOW, extensionVersion: "0.1.0" });
    expect(built.categoryMapVersion).toBe(1);
    expect(built.suffixListVersion).toBe(1);
    expect(built.sessionTimeoutSeconds).toBe(1800);
  });

  it("orders events oldest first", async () => {
    const built = await buildExport({ now: NOW, extensionVersion: "0.1.0" });
    const times = built.events.map((e) => Date.parse(e.occurredAt));
    expect(times).toEqual([...times].sort((a, b) => a - b));
  });

  it("includes the user's own overrides — an export is everything, or it is a half-truth", async () => {
    const built = await buildExport({ now: NOW, extensionVersion: "0.1.0" });
    expect(built.overrides).toEqual({ "youtube.com": "learning" });
  });
});

describe("the export contains nothing beyond the schema", () => {
  it("has exactly the declared top-level keys", async () => {
    const built = await buildExport({ now: NOW, extensionVersion: "0.1.0" });
    expect(Object.keys(built).sort()).toEqual([
      // v3. D96 shipped attention spans into their own store and left them out of the
      // export for as long as that stood, which made the file the visible half of the
      // truth and — worse — kept live dwell out of the research tier entirely.
      "attention",
      "categoryMapVersion",
      "events",
      "exportedAt",
      "extensionVersion",
      "overrides",
      "predictions",
      "rawRetentionDays",
      "schema",
      "sessionTimeoutSeconds",
      "suffixListVersion",
    ]);
  });

  it("carries every span, including two on one event", async () => {
    // The join sums attention across spans, so an exporter that kept only the last span
    // per event would quietly halve the dwell of every revisited page.
    const built = await buildExport({ now: NOW, extensionVersion: "0.1.0" });
    expect(built.attention.length).toBe(FIXTURE.attention.length);
    const perEvent = new Map<string, number>();
    for (const span of built.attention) {
      perEvent.set(span.eventId, (perEvent.get(span.eventId) ?? 0) + 1);
    }
    expect([...perEvent.values()].some((count) => count > 1)).toBe(true);
  });

  it("still keeps dwell off every exported event (D35)", async () => {
    // Spans are the measurement; the event stays final and dwell-free. If dwell ever
    // appears on an exported event, something wrote it to disk.
    const built = await buildExport({ now: NOW, extensionVersion: "0.1.0" });
    for (const event of built.events) {
      expect(event.dwellSeconds, `${event.eventId} must not carry dwell`).toBeNull();
    }
  });

  it("older exports stay readable, which is what freezing them is for", () => {
    for (const old of FROZEN) {
      expect(old.schema).not.toBe(EXPORT_SCHEMA);
      expect(Array.isArray(old.events)).toBe(true);
    }
  });

  it("gives every event exactly the declared fields", async () => {
    const built = await buildExport({ now: NOW, extensionVersion: "0.1.0" });
    for (const event of built.events) {
      expect(Object.keys(event).sort()).toEqual([...EVENT_FIELDS].sort());
    }
  });

  it("holds no URL anywhere in the serialised file", async () => {
    const text = serialiseExport(
      await buildExport({ now: NOW, extensionVersion: "0.1.0" }),
    );
    expect(text).not.toMatch(/https?:\/\//);
    expect(text).not.toContain("?");
    expect(text).not.toContain("#");
  });

  it("is readable rather than minified — an unreadable privacy claim is uncheckable", async () => {
    const text = serialiseExport(
      await buildExport({ now: NOW, extensionVersion: "0.1.0" }),
    );
    expect(text.split("\n").length).toBeGreaterThan(20);
  });

  it("names the file by date", () => {
    expect(exportFilename(NOW)).toBe("tise-export-2026-08-26.json");
  });
});
