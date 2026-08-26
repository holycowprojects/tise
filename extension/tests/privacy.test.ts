/**
 * The invariants that make Tise publishable. If any of these fail, nothing else matters.
 *
 * SPEC.md states them as promises. This file states them as assertions, and the store
 * assertions in `storage.test.ts` state them against real rows rather than against
 * intentions.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { normaliseNavigation } from "../src/collect/normalise";
import { registrableDomain } from "../src/collect/domain";
import { assertStorable, EVENT_FIELDS, type TiseEvent } from "../src/types";

const EXTENSION_ROOT = fileURLToPath(new URL("..", import.meta.url));

function sourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...sourceFiles(full));
    else if (entry.endsWith(".ts")) out.push(full);
  }
  return out;
}

/**
 * Source with comments removed.
 *
 * The scan is about what the code *does*, not what it says about itself: this very file
 * names every forbidden API, and so does the ESLint config. Naive stripping is enough
 * here because nothing in `src/` or `ui/` puts a `//` inside a string literal.
 */
function codeOf(file: string): string {
  return readFileSync(file, "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

function validEvent(overrides: Partial<TiseEvent> = {}): TiseEvent {
  return {
    eventId: "e1",
    occurredAt: "2026-08-26T09:15:00.000Z",
    source: "live",
    domain: "youtube.com",
    category: "video",
    transition: "link",
    dwellSeconds: null,
    sessionId: "2026-08-26T09:15:00.000Z",
    ...overrides,
  };
}

describe("the event type cannot carry a URL", () => {
  it("accepts a well-formed event", () => {
    expect(() => assertStorable(validEvent())).not.toThrow();
  });

  it("refuses a domain that still looks like a URL", () => {
    for (const domain of [
      "youtube.com/watch",
      "youtube.com?q=1",
      "youtube.com#top",
      "https://youtube.com",
      "user@youtube.com",
      "youtube.com:443",
      "",
    ]) {
      expect(() => assertStorable(validEvent({ domain }))).toThrow();
    }
  });

  it("refuses fields the schema does not declare", () => {
    const smuggled = { ...validEvent(), url: "https://example.com/secret" } as TiseEvent;
    expect(() => assertStorable(smuggled)).toThrow(/unexpected fields/);
  });

  it("refuses a non-UTC timestamp", () => {
    expect(() => assertStorable(validEvent({ occurredAt: "2026-08-26T09:15:00+05:30" }))).toThrow();
  });

  it("refuses an invented dwell time (D35)", () => {
    expect(() => assertStorable(validEvent({ dwellSeconds: 42 }))).toThrow(/D35/);
  });
});

describe("normalisation discards everything but the domain", () => {
  const leaky = [
    "https://mail.google.com/mail/u/0/#inbox/FMfcgz?token=SECRET",
    "https://www.google.com/search?q=how+to+treat+SECRET",
    "https://bank.example.co.uk/accounts/12345678/statement.pdf?otp=SECRET",
    "https://github.com/someone/private-repo/blob/main/.env#L3",
  ];

  it("emits an object with exactly the declared fields", () => {
    for (const url of leaky) {
      const result = normaliseNavigation({
        url,
        frameId: 0,
        timeStamp: 1_756_200_000_000,
        transitionType: "link",
        transitionQualifiers: [],
      });
      expect(result.ok).toBe(true);
      if (!result.ok) continue;

      const keys = Object.keys(result.event).sort();
      const allowed = EVENT_FIELDS.filter((f) => f !== "sessionId").sort();
      expect(keys).toEqual([...allowed]);
    }
  });

  it("leaves no trace of the path, query or fragment anywhere in the event", () => {
    for (const url of leaky) {
      const result = normaliseNavigation({
        url,
        frameId: 0,
        timeStamp: 1_756_200_000_000,
        transitionType: "link",
        transitionQualifiers: [],
      });
      if (!result.ok) continue;
      const serialised = JSON.stringify(result.event);
      expect(serialised).not.toContain("SECRET");
      expect(serialised).not.toContain("/");
      expect(serialised).not.toContain("?");
      expect(serialised).not.toContain("private-repo");
    }
  });

  it("never returns a domain longer than the host it came from", () => {
    // A cheap property check: the reduction can only ever shorten.
    for (const url of leaky) {
      const domain = registrableDomain(url);
      expect(domain).not.toBeNull();
      expect(url).toContain(domain as string);
      expect((domain as string).length).toBeLessThan(url.length);
    }
  });
});

describe("the extension cannot talk to anything", () => {
  const files = [
    ...sourceFiles(join(EXTENSION_ROOT, "src")),
    ...sourceFiles(join(EXTENSION_ROOT, "ui")),
  ];

  it("finds source files to check", () => {
    expect(files.length).toBeGreaterThan(5);
  });

  it.each([
    ["fetch", /\bfetch\s*\(/],
    ["XMLHttpRequest", /\bXMLHttpRequest\b/],
    ["WebSocket", /\bWebSocket\b/],
    ["sendBeacon", /\bsendBeacon\b/],
    ["importScripts", /\bimportScripts\s*\(/],
    ["EventSource", /\bEventSource\b/],
  ])("contains no %s call", (_name, pattern) => {
    const offenders = files.filter((file) => pattern.test(codeOf(file)));
    expect(offenders).toEqual([]);
  });

  it("uses no chrome.storage, so the manifest needs no storage permission", () => {
    const offenders = files.filter((file) => /chrome\.storage\b/.test(codeOf(file)));
    expect(offenders).toEqual([]);
  });
});
