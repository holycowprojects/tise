/**
 * The transition table: what tends to follow what.
 *
 * PARITY-CRITICAL: `research/tise_research/models/transition.py` is the mirror.
 *
 * This is the model behind `next_session_category`, which is a **UI-only** target — it is
 * displayed and it is not the number this project claims skill on. `return_24h` is the
 * evaluated target, and nothing here feeds it.
 *
 * **A session gets one category, and choosing it is a declared simplification.** Real
 * sessions contain several, so "the next session's category" needs a rule before it means
 * anything. The rule is: the category with the most events in the session, ties broken by
 * name so the answer never depends on iteration order. A session that is half video and
 * half news is recorded as whichever wins, and that loses information — the honest
 * alternative, a multi-label table of P(c appears next | b appeared now), does not produce
 * a distribution over categories, which is what a "what's next" surface needs. The
 * simplification is recorded rather than hidden, and it is the reason this target is
 * displayed rather than scored.
 *
 * **Smoothing is mandatory, for the reason D26 found.** A category seen twice, both times
 * followed by the same thing, would otherwise claim 100%. Every row is pulled toward the
 * marginal distribution of what follows anything, by a declared number of pseudo-counts.
 */
import type { FeatureSession } from "../features/sessions";

/**
 * Pseudo-observations pulled from the marginal. One is enough to stop a two-observation
 * row claiming certainty, and small enough that a well-populated row keeps its shape.
 */
export const DEFAULT_SMOOTHING = 1;

export interface TransitionTable {
  /**
   * Sorted, and it is the column order of every distribution this table produces — the
   * same contract `FEATURE_NAMES` carries for the feature vector.
   */
  readonly vocabulary: readonly string[];
  /** from-category -> to-category -> raw count. Sparse: absent means zero. */
  readonly counts: Readonly<Record<string, Readonly<Record<string, number>>>>;
  /** to-category -> raw count, over every transition. The fallback distribution. */
  readonly marginal: Readonly<Record<string, number>>;
  readonly smoothing: number;
}

/**
 * The category with the most events in the session; ties broken by name.
 *
 * The tie-break is alphabetical rather than "first seen" on purpose: first-seen depends
 * on within-session ordering, which two implementations could resolve differently for
 * events sharing a timestamp.
 */
export function primaryCategory(session: FeatureSession): string {
  const counts = new Map<string, number>();
  for (const event of session.events) {
    counts.set(event.category, (counts.get(event.category) ?? 0) + 1);
  }
  let best: string | null = null;
  let bestCount = 0;
  for (const [category, count] of counts) {
    if (best === null || count > bestCount || (count === bestCount && category < best)) {
      best = category;
      bestCount = count;
    }
  }
  if (best === null) throw new Error("a session with no events has no primary category");
  return best;
}

export function transitionCount(table: TransitionTable): number {
  let total = 0;
  for (const category of Object.keys(table.marginal)) {
    total += table.marginal[category] as number;
  }
  return total;
}

/** What follows anything. Used when the current category was never seen. */
export function marginalDistribution(table: TransitionTable): Record<string, number> {
  const total = transitionCount(table);
  const distribution: Record<string, number> = {};
  if (total === 0 || table.vocabulary.length === 0) {
    const uniform = table.vocabulary.length > 0 ? 1 / table.vocabulary.length : 0;
    for (const category of table.vocabulary) distribution[category] = uniform;
    return distribution;
  }
  for (const category of table.vocabulary) {
    distribution[category] = (table.marginal[category] ?? 0) / total;
  }
  return distribution;
}

/** P(next session's primary category | this one), smoothed toward the marginal. */
export function distribution(
  table: TransitionTable,
  fromCategory: string,
): Record<string, number> {
  const marginal = marginalDistribution(table);
  const row = table.counts[fromCategory];
  if (row === undefined) return marginal;

  let total = 0;
  for (const category of Object.keys(row)) total += row[category] as number;
  const denominator = total + table.smoothing;
  if (denominator === 0) return marginal;

  const result: Record<string, number> = {};
  for (const category of table.vocabulary) {
    result[category] =
      ((row[category] ?? 0) + table.smoothing * (marginal[category] ?? 0)) / denominator;
  }
  return result;
}

/** The top category and its probability, ties broken by name. `null` if unfitted. */
export function mostLikely(
  table: TransitionTable,
  fromCategory: string,
): { category: string; probability: number } | null {
  const result = distribution(table, fromCategory);
  const categories = Object.keys(result);
  if (categories.length === 0) return null;

  let best = categories[0] as string;
  for (const category of categories) {
    const candidate = result[category] as number;
    const incumbent = result[best] as number;
    if (candidate > incumbent || (candidate === incumbent && category < best)) {
      best = category;
    }
  }
  return { category: best, probability: result[best] as number };
}

/**
 * Count consecutive session pairs. Sessions must already be in chronological order.
 *
 * `sessionise` returns them that way, and re-sorting here would hide a caller that handed
 * over something out of order.
 */
export function fitTransitionTable(
  sessions: readonly FeatureSession[],
  smoothing: number = DEFAULT_SMOOTHING,
): TransitionTable {
  const primaries = sessions
    .filter((session) => session.events.length > 0)
    .map(primaryCategory);

  const counts: Record<string, Record<string, number>> = {};
  const marginal: Record<string, number> = {};
  for (let index = 0; index + 1 < primaries.length; index += 1) {
    const from = primaries[index] as string;
    const to = primaries[index + 1] as string;
    const row = (counts[from] ??= {});
    row[to] = (row[to] ?? 0) + 1;
    marginal[to] = (marginal[to] ?? 0) + 1;
  }

  return {
    vocabulary: [...new Set(primaries)].sort(),
    counts,
    marginal,
    smoothing,
  };
}
