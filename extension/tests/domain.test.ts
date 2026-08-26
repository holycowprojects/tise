/**
 * Domain reduction, checked against the same fixture the Python tier checks itself
 * against: `research/fixtures/domain_cases.json`.
 *
 * The full parity suite arrives at T9 for features. This starts it early for the one
 * function that is already implemented twice — and it is the one every feature is
 * computed on top of, so a disagreement here would move all of them at once.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { registrableDomain, SUFFIX_LIST_VERSION } from "../src/collect/domain";

interface DomainCase {
  url: string;
  domain: string | null;
}

const FIXTURE = fileURLToPath(
  new URL("../../research/fixtures/domain_cases.json", import.meta.url),
);

const cases: DomainCase[] = JSON.parse(readFileSync(FIXTURE, "utf8")).cases;

describe("registrableDomain", () => {
  it("has a fixture with both accepted and rejected URLs in it", () => {
    expect(cases.length).toBeGreaterThan(20);
    expect(cases.some((c) => c.domain !== null)).toBe(true);
    expect(cases.some((c) => c.domain === null)).toBe(true);
  });

  it.each(cases)("$url -> $domain", ({ url, domain }) => {
    expect(registrableDomain(url)).toBe(domain);
  });

  it("rejects a string that is not a URL at all", () => {
    expect(registrableDomain("not a url at all")).toBeNull();
  });

  it("pins the suffix list version alongside the map version", () => {
    expect(SUFFIX_LIST_VERSION).toBe(1);
  });
});
