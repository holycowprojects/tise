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
  it("declares exactly the permissions D31 justified, minus the one D63 retired", () => {
    expect(manifest["permissions"]).toEqual(["webNavigation", "alarms"]);
  });

  it("does not ask for `offscreen`, which nothing uses", () => {
    // D31 justified it for training. D57 made training chunked, so no single call is long
    // enough to need a document that outlives the worker, and D63 removed it. This is a
    // separate assertion from the one above because it is a separate claim: not "the set
    // is what we expect" but "this specific capability is not requested".
    expect(manifest["permissions"]).not.toContain("offscreen");
    expect(JSON.stringify(manifest)).not.toContain("offscreen");
  });

  it("keeps every reading capability optional, so install grants none of them", () => {
    // `tabs` and `idle` were added for attention spans, authorised 2026-08-28. Both are
    // optional and consent-gated exactly as `history` is: installing Tise still grants
    // the ability to read nothing at all, which is the property this asserts.
    expect(manifest["optional_permissions"]).toEqual(["history", "tabs", "idle"]);
  });

  it("asks for none of the permissions that would read page content or requests", () => {
    // A separate claim from the one above, and the one that matters most: `tabs` gives
    // tab lifecycle and URLs, but `cookies` would give credentials, `webRequest` every
    // request, and `scripting`/`declarativeNetRequest` reach into pages. None is
    // requested, in either list, and D95 recorded why `cookies` in particular is the
    // wrong trade — its values *are* credentials and it needs host permissions.
    const requested = JSON.stringify([
      manifest["permissions"],
      manifest["optional_permissions"],
    ]);
    for (const forbidden of [
      "cookies",
      "webRequest",
      "scripting",
      "declarativeNetRequest",
      "browsingData",
      "management",
      "downloads",
      "bookmarks",
      "topSites",
      "storage",
    ]) {
      expect(requested).not.toContain(forbidden);
    }
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
