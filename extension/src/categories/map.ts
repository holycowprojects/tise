/**
 * The shipped domain -> category map, read straight from `domains.json`.
 *
 * `research/tise_research/categories.py` reads the same file. There is exactly one map,
 * and no opportunity for the two languages to drift — the same reasoning as the parity
 * suite, applied to data instead of code.
 *
 * This module deliberately stops at a **lookup**. The four-layer resolver lives in
 * `collect/resolver.ts`, mirroring the Python split.
 */
import rawMap from "./domains.json";

export type RuleKind = "suffix" | "contains";

/**
 * One keyword rule, applied only when the domain map misses.
 *
 * Kept as data rather than code precisely so the two implementations cannot drift:
 * both languages read this list, neither owns it.
 */
export interface CategoryRule {
  readonly kind: RuleKind;
  readonly value: string;
  readonly category: string;
}

/** Bumped whenever the mapping changes in a way that could move a prediction. */
export const CATEGORY_MAP_VERSION: number = rawMap.version;

export const CATEGORIES: Readonly<Record<string, string>> = Object.freeze({
  ...rawMap.categories,
});

const DOMAINS: ReadonlyMap<string, string> = new Map(
  Object.entries(rawMap.domains).map(([domain, category]) => [
    domain.toLowerCase(),
    category as string,
  ]),
);

/** Ordered. First match wins, and the order is part of the contract. */
export const RULES: readonly CategoryRule[] = rawMap.rules.map((rule) => ({
  kind: rule.kind as RuleKind,
  value: rule.value.toLowerCase(),
  category: rule.category,
}));

export function ruleMatches(rule: CategoryRule, domain: string): boolean {
  switch (rule.kind) {
    case "suffix":
      return domain.endsWith(rule.value);
    case "contains":
      return domain.includes(rule.value);
    default: {
      const exhaustive: never = rule.kind;
      throw new Error(`unknown rule kind: ${String(exhaustive)}`);
    }
  }
}

/**
 * Category for a registrable domain, or `null` if the map has nothing.
 *
 * `null` is not `unknown`. `null` means "this layer had no answer"; `unknown` is a
 * decision the resolver makes after every layer has declined.
 */
export function lookup(domain: string): string | null {
  return DOMAINS.get(domain.trim().toLowerCase()) ?? null;
}

/** Exposed for the coverage test, which needs the map size, not its contents. */
export const DOMAIN_COUNT = DOMAINS.size;
