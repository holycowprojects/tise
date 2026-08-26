/**
 * The manifest is a decision (D31), not a config file. It was arrived at by running five
 * variants in a real browser at T5, and one belief the design had held — that
 * `webNavigation` needs host permissions — turned out to be false (D32).
 *
 * These assertions exist so that permission creep has to be deliberate. Adding a
 * permission is on the "ask first" list; this test makes doing it by accident fail.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const manifest = JSON.parse(
  readFileSync(fileURLToPath(new URL("../manifest.json", import.meta.url)), "utf8"),
) as Record<string, unknown>;

describe("manifest", () => {
  it("declares exactly the permissions D31 justified", () => {
    expect(manifest["permissions"]).toEqual(["webNavigation", "alarms", "offscreen"]);
  });

  it("keeps history optional, so install grants no ability to read anything", () => {
    expect(manifest["optional_permissions"]).toEqual(["history"]);
  });

  it("requests no host permissions — observed unnecessary, and the widest warning", () => {
    expect(manifest["host_permissions"]).toBeUndefined();
    expect(manifest["optional_host_permissions"]).toBeUndefined();
    expect(manifest["content_scripts"]).toBeUndefined();
  });

  it("is Manifest V3 with a module service worker", () => {
    expect(manifest["manifest_version"]).toBe(3);
    expect(manifest["background"]).toEqual({
      service_worker: "background.js",
      type: "module",
    });
  });

  it("has a description short enough for the Web Store listing", () => {
    expect(String(manifest["description"]).length).toBeLessThanOrEqual(132);
  });
});
