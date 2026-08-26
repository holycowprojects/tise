/**
 * The export, checked against the same file the Python loader is checked against:
 * `research/fixtures/export_v1.json`.
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
  new URL("../../research/fixtures/export_v1.json", import.meta.url),
);
const FIXTURE: TiseExport = JSON.parse(readFileSync(FIXTURE_PATH, "utf8"));

const NOW = Date.parse(FIXTURE.exportedAt);

beforeEach(async () => {
  await closeTiseDb();
  globalThis.indexedDB = new IDBFactory();
  await putEvents(FIXTURE.events as TiseEvent[]);
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
      "categoryMapVersion",
      "events",
      "exportedAt",
      "extensionVersion",
      "overrides",
      "rawRetentionDays",
      "schema",
      "sessionTimeoutSeconds",
      "suffixListVersion",
    ]);
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
