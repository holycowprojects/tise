/**
 * The collector and the store, end to end, against a real IndexedDB implementation.
 *
 * `fake-indexeddb` is a test-only dependency and never reaches `dist/`. It matters that
 * it is a real implementation rather than a mock of my own: these assertions are the
 * ones that claim "no URL is ever stored", and a mock would only prove that my mock
 * behaves the way I expected IndexedDB to. T5 was a reminder of how that goes.
 */
import "fake-indexeddb/auto";
import { IDBFactory } from "fake-indexeddb";
import { beforeEach, describe, expect, it } from "vitest";
import { collect, rejectionCounts } from "../src/collect/collector";
import type { NavigationDetails } from "../src/collect/normalise";
import { closeTiseDb } from "../src/storage/db";
import { allEvents, clearEvents, countEvents, putEvent } from "../src/storage/events";
import { loadSettings, saveSettings } from "../src/storage/settings";
import { EVENT_FIELDS, type TiseEvent } from "../src/types";

const MINUTE = 60_000;
const START = Date.parse("2026-08-26T09:00:00.000Z");

function nav(overrides: Partial<NavigationDetails> = {}): NavigationDetails {
  return {
    url: "https://www.youtube.com/watch?v=abc",
    frameId: 0,
    timeStamp: START,
    transitionType: "link",
    transitionQualifiers: [],
    ...overrides,
  };
}

async function consent(): Promise<void> {
  await saveSettings({ consentGrantedAt: new Date(START).toISOString(), paused: false });
}

beforeEach(async () => {
  await closeTiseDb();
  globalThis.indexedDB = new IDBFactory();
});

describe("consent gates everything", () => {
  it("stores nothing at all before the user agrees", async () => {
    const outcome = await collect(nav());
    expect(outcome).toEqual({ stored: false, reason: "not-collecting" });
    expect(await countEvents()).toBe(0);
  });

  it("defaults to not collecting on a fresh install", async () => {
    const settings = await loadSettings();
    expect(settings.consentGrantedAt).toBeNull();
  });

  it("collects once the user agrees", async () => {
    await consent();
    const outcome = await collect(nav());
    expect(outcome.stored).toBe(true);
    expect(await countEvents()).toBe(1);
  });
});

describe("pausing stops writes", () => {
  it("keeps what was collected and writes nothing more", async () => {
    await consent();
    await collect(nav());
    expect(await countEvents()).toBe(1);

    await saveSettings({ paused: true });
    const outcome = await collect(nav({ timeStamp: START + MINUTE }));

    expect(outcome).toEqual({ stored: false, reason: "not-collecting" });
    expect(await countEvents()).toBe(1);
  });

  it("resumes where it left off", async () => {
    await consent();
    await saveSettings({ paused: true });
    await collect(nav());
    await saveSettings({ paused: false });
    await collect(nav({ timeStamp: START + MINUTE }));

    expect(await countEvents()).toBe(1);
  });
});

describe("a populated store contains nothing but events", () => {
  const leaky = [
    "https://mail.google.com/mail/u/0/#inbox/FMfcgz?token=SECRET",
    "https://www.google.com/search?q=SECRET+symptoms",
    "https://bank.example.co.uk/accounts/12345678/statement.pdf?otp=SECRET",
    "https://github.com/someone/private-repo/blob/main/.env",
    "https://www.amazon.in/dp/B0SECRET/ref=nav",
  ];

  beforeEach(async () => {
    await consent();
    for (const [index, url] of leaky.entries()) {
      await collect(nav({ url, timeStamp: START + index * MINUTE }));
    }
  });

  it("stored one row per navigation", async () => {
    expect(await countEvents()).toBe(leaky.length);
  });

  it("gives every row exactly the declared fields", async () => {
    for (const event of await allEvents()) {
      expect(Object.keys(event).sort()).toEqual([...EVENT_FIELDS].sort());
    }
  });

  it("holds no path, query, fragment or secret anywhere in the database", async () => {
    const dump = JSON.stringify(await allEvents());
    expect(dump).not.toContain("SECRET");
    expect(dump).not.toContain("private-repo");
    expect(dump).not.toContain("statement.pdf");
    expect(dump).not.toContain("?");
    expect(dump).not.toContain("#");
    expect(dump).not.toMatch(/https?:/);
  });

  it("kept the registrable domains and nothing more", async () => {
    const domains = (await allEvents()).map((e) => e.domain);
    expect(domains).toEqual([
      "google.com",
      "google.com",
      "example.co.uk",
      "github.com",
      "amazon.in",
    ]);
  });

  it("empties completely when cleared", async () => {
    await clearEvents();
    expect(await countEvents()).toBe(0);
    expect(await allEvents()).toEqual([]);
  });
});

describe("sessions are assigned as browsing happens", () => {
  it("keeps one session while the gaps stay under the timeout", async () => {
    await consent();
    for (const minutes of [0, 5, 25]) {
      await collect(nav({ timeStamp: START + minutes * MINUTE }));
    }
    const ids = new Set((await allEvents()).map((e) => e.sessionId));
    expect(ids.size).toBe(1);
  });

  it("opens a new session after a gap longer than the timeout", async () => {
    await consent();
    for (const minutes of [0, 5, 90, 92]) {
      await collect(nav({ timeStamp: START + minutes * MINUTE }));
    }
    const events = await allEvents();
    const ids = events.map((e) => e.sessionId);
    expect(new Set(ids).size).toBe(2);
    expect(ids[0]).toBe(ids[1]);
    expect(ids[2]).toBe(ids[3]);
  });

  it("survives a service worker restart, because the cursor is in the database", async () => {
    await consent();
    await collect(nav());

    // Closing the handle is what a terminated service worker looks like from here.
    await closeTiseDb();

    await collect(nav({ timeStamp: START + 10 * MINUTE }));
    const ids = new Set((await allEvents()).map((e) => e.sessionId));
    expect(ids.size).toBe(1);
  });
});

describe("filtered navigations", () => {
  it("stores nothing and counts the reason", async () => {
    await consent();
    await collect(nav({ frameId: 7 }));
    await collect(nav({ transitionQualifiers: ["server_redirect"] }));
    await collect(nav({ url: "chrome://settings" }));

    expect(await countEvents()).toBe(0);
    expect(await rejectionCounts()).toEqual({ subframe: 1, redirect: 1, "not-web": 1 });
  });
});

describe("the store refuses a bad write even if one is attempted", () => {
  it("throws rather than persisting a URL-shaped domain", async () => {
    const smuggled: TiseEvent = {
      eventId: "e1",
      occurredAt: "2026-08-26T09:00:00.000Z",
      source: "live",
      domain: "example.com/secret-path",
      category: "unknown",
      transition: "link",
      dwellSeconds: null,
      sessionId: "s1",
    };
    await expect(putEvent(smuggled)).rejects.toThrow(/looks like a URL/);
    expect(await countEvents()).toBe(0);
  });

  it("is idempotent on eventId, so a replayed write creates no duplicate", async () => {
    const event: TiseEvent = {
      eventId: "e1",
      occurredAt: "2026-08-26T09:00:00.000Z",
      source: "import",
      domain: "example.com",
      category: "unknown",
      transition: "link",
      dwellSeconds: null,
      sessionId: "s1",
    };
    await putEvent(event);
    await putEvent(event);
    expect(await countEvents()).toBe(1);
  });
});
