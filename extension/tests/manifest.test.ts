/**
 * The manifest is a decision (D31), not a config file. It was arrived at by running five
 * variants in a real browser at T5, and one belief the design had held — that
 * `webNavigation` needs host permissions — turned out to be false (D32).
 *
 * These assertions exist so that permission creep has to be deliberate. Adding a
 * permission is on the "ask first" list; this test makes doing it by accident fail.
 */
import { readFileSync, readdirSync } from "node:fs";
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

  it("can actually ask for every optional permission it declares", () => {
    // The bug this exists for: D96 declared `tabs` and `idle`, gated attention collection
    // on `permissions.contains([...])`, and built nothing that could ever *request* them.
    // Optional permissions are not granted at install, so the gate could never open. The
    // span store stayed empty and the only symptom was a number that never moved — no
    // test failed, nothing threw, and it surfaced only because a screenshot was sent.
    //
    // **It is not enough to find the permission's name in the source.** The first version
    // of this test did exactly that and passed with the bug reintroduced, because `tabs`
    // and `idle` appear in the `contains` call that reads the gate. Only the arguments of
    // `permissions.request` count, which is the one call that can actually open it.
    const source = readFileSync(
      fileURLToPath(new URL("../ui/popup/popup.ts", import.meta.url)),
      "utf8",
    );

    const requested = new Set<string>();
    for (const match of source.matchAll(/permissions\.request\(([^)]*)\)/g)) {
      for (const name of (match[1] ?? "").matchAll(/"([a-zA-Z]+)"/g)) {
        if (name[1] && name[1] !== "permissions") requested.add(name[1]);
      }
    }

    expect(requested.size, "no permission is requested anywhere").toBeGreaterThan(0);
    for (const permission of manifest["optional_permissions"] as string[]) {
      expect(
        requested.has(permission),
        `${permission} is declared optional but never passed to permissions.request, ` +
          "so a user has no way to grant it and the feature behind it can never run",
      ).toBe(true);
    }
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

/**
 * Icons, checked in both directions, because either direction failing ships something
 * broken and neither would fail anything else.
 *
 * A file the manifest names and the build forgets is a missing icon in the store listing.
 * A file on disk the manifest never names is dead weight in the package and, more to the
 * point, the sign that a size was added and half-wired. Same shape as `disclosure.test.ts`
 * against the permission list.
 */
describe("icons", () => {
  const REQUIRED = [16, 32, 48, 128];
  const icons = manifest["icons"] as Record<string, string>;
  const action = manifest["action"] as Record<string, unknown>;

  function read(relative: string): Buffer {
    return readFileSync(fileURLToPath(new URL(`../${relative}`, import.meta.url)));
  }

  it("declares the four sizes Chrome and the Web Store ask for", () => {
    expect(Object.keys(icons).map(Number).sort((a, b) => a - b)).toEqual(REQUIRED);
  });

  it("gives the toolbar button an icon, so it is not a generated letter", () => {
    // What Chrome falls back to without one, and what Tise showed until T18: a grey tile
    // with the first letter of the name.
    expect(action["default_icon"]).toEqual({
      "16": "icons/icon16.png",
      "32": "icons/icon32.png",
    });
  });

  it("names files that exist and are PNGs of the size claimed", () => {
    for (const [size, path] of Object.entries(icons)) {
      const bytes = read(path);
      expect(bytes.subarray(0, 8)).toEqual(
        Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
      );
      // IHDR width and height, big-endian, at a fixed offset in every PNG.
      expect(bytes.readUInt32BE(16)).toBe(Number(size));
      expect(bytes.readUInt32BE(20)).toBe(Number(size));
    }
  });

  it("has no icon on disk that the manifest does not name", () => {
    const named = new Set(Object.values(icons).map((path) => path.split("/").pop()));
    const onDisk = readdirSync(
      fileURLToPath(new URL("../icons", import.meta.url)),
    ).filter((name) => name.endsWith(".png"));

    expect(onDisk.length).toBeGreaterThan(0);
    for (const name of onDisk) expect(named).toContain(name);
  });

  it("is copied by the build, not left behind in source", () => {
    // The manifest can name a path that only exists in the repository. Chrome loads
    // `dist/`, so an icon the build does not copy is missing where it matters.
    const config = readFileSync(
      fileURLToPath(new URL("../vite.config.ts", import.meta.url)),
      "utf8",
    );
    for (const path of Object.values(icons)) expect(config).toContain(path);
  });
});
