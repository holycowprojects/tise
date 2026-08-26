/**
 * Resolve a registrable domain to a category. Four layers, first match wins:
 *
 * 1. **User override** — the user is always right about their own browsing.
 * 2. **Shipped map** — explicit `domain -> category` entries.
 * 3. **Keyword rules** — ordered patterns catching classes of site the map cannot
 *    enumerate: every local government portal, every school, every regional bank.
 * 4. **`unknown`** — a valid answer, not a failure.
 *
 * Layer 3 does real privacy work as well as coverage work. A rule categorises someone's
 * council website or their child's school without either ever appearing in a public file.
 *
 * The resolver reports **which layer answered**, which is what makes the unknown rate
 * measurable instead of hidden.
 *
 * PARITY-CRITICAL: `research/tise_research/features/resolver.py` must match exactly.
 */
import { lookup, RULES, ruleMatches } from "../categories/map";

export type ResolutionSource = "override" | "map" | "rule" | "fallback";

export interface Resolution {
  readonly category: string;
  readonly source: ResolutionSource;
}

export const UNKNOWN = "unknown";

/** Pure: same inputs, same output, no clock, no I/O. */
export function resolve(
  domain: string,
  overrides?: Readonly<Record<string, string>>,
): Resolution {
  const normalised = domain.trim().toLowerCase();
  if (!normalised) return { category: UNKNOWN, source: "fallback" };

  const override = overrides?.[normalised];
  if (override) return { category: override, source: "override" };

  const mapped = lookup(normalised);
  if (mapped !== null) return { category: mapped, source: "map" };

  for (const rule of RULES) {
    if (ruleMatches(rule, normalised)) {
      return { category: rule.category, source: "rule" };
    }
  }

  return { category: UNKNOWN, source: "fallback" };
}
