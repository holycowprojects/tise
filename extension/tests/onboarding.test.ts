/**
 * T15 — the install state is genuinely empty, and consent is the only thing that ends it.
 *
 * The task's own verification is *"fresh profile install; confirm zero writes pre-consent"*.
 * That needs a browser and Akash, and it should. This file is the half that can be
 * automated: it drives the real storage layer through the real gate and asserts that the
 * database a person has not consented to is **empty**, not merely unused.
 *
 * "Nothing is stored before consent" has been a claim since D37. Until now the assertions
 * behind it were about the collector refusing an event. This asserts the stronger and more
 * useful thing: after everything onboarding does short of consenting, the store holds
 * nothing at all — no settings row, no flag, no "has seen the welcome page" marker.
 *
 * **That last one is a real temptation and it is the reason this file exists.** The obvious
 * way to open a welcome page once is to write down that you have opened it. A flag like
 * that is a stored fact about a person who has not agreed to Tise storing facts about them,
 * and it would be indistinguishable from consent to anyone reading the database.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { beforeEach, describe, expect, it } from "vitest";
import "fake-indexeddb/auto";
import { IDBFactory } from "fake-indexeddb";
import { countEvents } from "../src/storage/events";
import { closeTiseDb, readMeta } from "../src/storage/db";
import {
  DEFAULT_SETTINGS,
  RETENTION_MAX_DAYS,
  TIMEOUT_MAX_SECONDS,
  TIMEOUT_MIN_SECONDS,
  isCollecting,
  loadSettings,
  saveSettings,
  settingsError,
} from "../src/storage/settings";
import { collect } from "../src/collect/collector";

beforeEach(async () => {
  // `db.ts` caches the open handle, so replacing the factory alone leaves the previous
  // test's database attached. Closing first is what actually makes each test a fresh
  // install — the state this whole file is about.
  await closeTiseDb();
  globalThis.indexedDB = new IDBFactory();

  // A fresh install holds **no optional permission**, so `contains` is false for all of
  // them. Stubbed rather than avoided by omitting `tabId`: the navigation a real browser
  // delivers carries one, and the branch it reaches is the one that asks whether attention
  // may be measured. Answering honestly is what makes this a fresh-install test.
  (globalThis as { chrome?: unknown }).chrome = {
    permissions: { contains: () => Promise.resolve(false) },
  };
});

/** A navigation the collector would accept, if it were allowed to. */
const NAVIGATION = {
  url: "https://example.com/some/path?q=secret",
  transitionType: "link",
  timeStamp: Date.UTC(2026, 5, 1, 9, 0),
  frameId: 0,
  tabId: 1,
} as const;

describe("the install state", () => {
  it("has no settings row at all, not a settings row saying no", () => {
    // Read through the raw meta store rather than `loadSettings`, which would helpfully
    // return the defaults and hide whether anything was ever written.
    return readMeta("settings").then((stored) => expect(stored).toBeUndefined());
  });

  it("reports not-consented and not-collecting from defaults alone", async () => {
    const settings = await loadSettings();
    expect(settings.consentGrantedAt).toBeNull();
    expect(isCollecting(settings)).toBe(false);
    expect(settings).toEqual(DEFAULT_SETTINGS);
  });

  it("stores nothing when a navigation happens before consent", async () => {
    const outcome = await collect(NAVIGATION);
    expect(outcome).toEqual({ stored: false, reason: "not-collecting" });
    expect(await countEvents()).toBe(0);
    // And still no settings row: a refused navigation must not create one as a side effect.
    expect(await readMeta("settings")).toBeUndefined();
  });

  it("writes exactly one thing when consent is given, and it is the consent", async () => {
    const before = await countEvents();
    const settings = await saveSettings({
      consentGrantedAt: new Date().toISOString(),
      paused: false,
    });

    expect(isCollecting(settings)).toBe(true);
    expect(settings.consentGrantedAt).not.toBeNull();
    // Consent does not manufacture history.
    expect(await countEvents()).toBe(before);
  });

  it("collects only after consent, on the same navigation it refused before", async () => {
    await collect(NAVIGATION);
    expect(await countEvents()).toBe(0);

    await saveSettings({ consentGrantedAt: new Date().toISOString(), paused: false });
    const after = await collect(NAVIGATION);
    expect(after.stored).toBe(true);
    expect(await countEvents()).toBe(1);
  });
});

describe("the welcome page writes no marker of its own", () => {
  it("does not record that it has been shown", () => {
    // Asserted against the source, because the failure would be a *new* meta key and no
    // existing test enumerates them. The install-once behaviour comes from Chrome's
    // `onInstalled` reason, which costs nothing and stores nothing.
    const source = readSource("../ui/welcome/welcome.ts") + readSource("../src/background.ts");
    for (const tempting of ["writeMeta", "welcomeShown", "onboarded", "hasSeen", "firstRun"]) {
      expect(
        source.includes(tempting),
        `onboarding writes "${tempting}" — a stored fact about someone who has not consented`,
      ).toBe(false);
    }
  });

  it("opens only on a genuine first install, never on an update", () => {
    // Reopening a consent page every release trains a person to dismiss it, which is the
    // opposite of informed consent. `onInstalled` fires for "update" and "chrome_update"
    // as well, so the guard has to be explicit.
    const source = readSource("../src/background.ts");
    expect(source).toMatch(/details\.reason !== "install"/);
    expect(source).toContain("welcome.html");
  });
});

describe("settings a person can edit cannot be set to nonsense", () => {
  it("accepts the defaults it ships with", () => {
    expect(settingsError(DEFAULT_SETTINGS)).toBeNull();
  });

  it("accepts zero retention, which means keep everything (D11)", () => {
    expect(settingsError({ rawRetentionDays: 0 })).toBeNull();
  });

  it("refuses a negative or fractional retention", () => {
    expect(settingsError({ rawRetentionDays: -1 })).toMatch(/whole number/);
    expect(settingsError({ rawRetentionDays: 2.5 })).toMatch(/whole number/);
  });

  it("refuses an absurd retention rather than accepting a second way to say forever", () => {
    expect(settingsError({ rawRetentionDays: RETENTION_MAX_DAYS + 1 })).toMatch(/use 0/);
  });

  it("refuses a session gap that would make every visit its own session", () => {
    // Every session-derived feature in the project rests on this number (D17), and D97
    // made it load-bearing again by clustering intervals on sessions.
    expect(settingsError({ sessionTimeoutSeconds: 1 })).toMatch(/between/);
    expect(settingsError({ sessionTimeoutSeconds: TIMEOUT_MIN_SECONDS - 1 })).toMatch(/between/);
    expect(settingsError({ sessionTimeoutSeconds: TIMEOUT_MAX_SECONDS + 1 })).toMatch(/between/);
    expect(settingsError({ sessionTimeoutSeconds: TIMEOUT_MIN_SECONDS })).toBeNull();
    expect(settingsError({ sessionTimeoutSeconds: TIMEOUT_MAX_SECONDS })).toBeNull();
  });

  it("refuses a URL in a site override, because settings travel in the export", () => {
    // D45 puts overrides in the export. Invariant 2 has no exception for a path a person
    // typed themselves.
    expect(settingsError({ overrides: { "https://example.com": "news" } })).toMatch(/bare site/);
    expect(settingsError({ overrides: { "example.com/inbox": "news" } })).toMatch(/bare site/);
    expect(settingsError({ overrides: { "example.com?q=1": "news" } })).toMatch(/bare site/);
    expect(settingsError({ overrides: { "example.com": "news" } })).toBeNull();
  });

  it("refuses a half-filled override", () => {
    expect(settingsError({ overrides: { "": "news" } })).toMatch(/needs both/);
    expect(settingsError({ overrides: { "example.com": " " } })).toMatch(/needs both/);
  });

  it("is enforced at the choke point, not only in the UI", async () => {
    // A page that forgot to validate would otherwise write a one-second session timeout
    // into the store and every feature in the project would start describing something
    // else, silently.
    await expect(saveSettings({ sessionTimeoutSeconds: 1 })).rejects.toThrow(/between/);
    expect(await readMeta("settings")).toBeUndefined();
  });
});

function readSource(relative: string): string {
  return readFileSync(fileURLToPath(new URL(relative, import.meta.url)), "utf8");
}
