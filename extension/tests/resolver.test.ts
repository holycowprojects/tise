import { describe, expect, it } from "vitest";
import { CATEGORIES, CATEGORY_MAP_VERSION, RULES } from "../src/categories/map";
import { resolve, UNKNOWN } from "../src/collect/resolver";

describe("resolve", () => {
  it("answers from the shipped map", () => {
    expect(resolve("youtube.com")).toEqual({ category: "video", source: "map" });
  });

  it("falls through to the keyword rules when the map misses", () => {
    const result = resolve("mumbaipolice.gov.in");
    expect(result.source).toBe("rule");
    expect(result.category).toBe("government");
  });

  it("returns unknown rather than guessing", () => {
    expect(resolve("some-domain-nobody-has-mapped.example")).toEqual({
      category: UNKNOWN,
      source: "fallback",
    });
  });

  it("lets a user override beat everything", () => {
    expect(resolve("youtube.com", { "youtube.com": "learning" })).toEqual({
      category: "learning",
      source: "override",
    });
  });

  it("is case- and whitespace-insensitive", () => {
    expect(resolve("  YouTube.COM ").category).toBe("video");
  });

  it("treats an empty domain as unknown, not as an error", () => {
    expect(resolve("").source).toBe("fallback");
  });

  it("only ever emits a category the map defines", () => {
    const declared = new Set(Object.keys(CATEGORIES));
    for (const rule of RULES) {
      expect(declared.has(rule.category)).toBe(true);
    }
    expect(declared.has(UNKNOWN)).toBe(true);
  });

  it("pins the map version, because a benchmark is only reproducible with it", () => {
    expect(CATEGORY_MAP_VERSION).toBe(1);
  });
});
