/**
 * The "what comes next" card. **Descriptive, and deliberately not a model.**
 *
 * D88 retired abstention and replaced it with one rule: *show everything, always with its
 * denominator* — "71% — 11 of your last 15 weekends". This is that rule applied to the one
 * question this project can answer today without any training data at all.
 *
 * **Why counts and not the fitted table.** `transition.ts` produces a smoothed conditional
 * distribution, and D102 benchmarked it for the first time. On Edge it cleared its
 * pre-registered bar — and `constrained_mode`, a rule that knows only that the answer can
 * never be the category you just left, **scored higher**. Across all three corpora the
 * table's point estimate lost to that rule and its interval excluded zero against it
 * nowhere. So a card that showed the table's probability would be presenting a number whose
 * skill is not established.
 *
 * What *is* established is what the person actually did, and that needs no model. This card
 * shows observed frequencies with the counts behind them. A displayed frequency with its
 * denominator is a description, not a claim of skill: "9 of the last 22 times you left
 * news, you went to video" is either true of their data or it is not.
 *
 * **Smoothing is therefore deliberately absent.** The shipped table smooths toward the
 * marginal, which is right for a model and wrong here: the percentage shown must equal the
 * fraction shown, or the denominator stops being evidence and becomes decoration.
 *
 * **Two floors, both declared, both the only gate.** D88 permits exactly one kind: a
 * minimum number of prior observations. `MIN_CONDITIONAL_CHANGES` is when the conditional
 * counts are too thin to lead with, and the card falls back to the overall rates and says
 * so. `MIN_TOTAL_CHANGES` is when there is not enough history to show anything, and the
 * card says how much more is needed rather than showing a confident-looking 2 of 3.
 *
 * **`unknown` can be a question and never an answer** (D27). Roughly a fifth of visits land
 * there by design — the public map excludes employer, school, council and neighbourhood
 * domains, because a domain list is a profile — so "next you will visit *unknown*" is both
 * unpresentable and, being a large bucket, unusually easy to be right about.
 */
import type { CategoryTransition } from "../features/transitions";

/** D27. Excluded as an answer, kept as a source. */
export const UNPRESENTABLE_ANSWER = "unknown";

/**
 * Below this many changes *from the current category*, the conditional counts are not shown
 * as the headline and the overall rates are used instead.
 *
 * **Declared, not fitted** — the same status as the 30-minute session timeout (D17). Ten is
 * the smallest denominator at which a displayed percentage moves by less than ten points
 * per observation, which is the point at which a number stops jumping every time the person
 * opens a tab.
 */
export const MIN_CONDITIONAL_CHANGES = 10;

/**
 * Below this many changes in total, the card shows nothing and says how many are needed.
 *
 * Also declared. It is the one floor D88 allows, and it is a floor on **evidence**, not on
 * confidence — which is the whole difference from the abstention rule it replaced.
 */
export const MIN_TOTAL_CHANGES = 20;

export interface CategoryShare {
  readonly category: string;
  /** Times this category followed, within the denominator below. */
  readonly count: number;
  /** What `count` is out of. Shown beside every share, never omitted. */
  readonly denominator: number;
  /** `count / denominator`. Exact; the UI rounds to a whole percent (D88). */
  readonly share: number;
}

export interface NotEnoughHistory {
  readonly kind: "not-enough-history";
  readonly changes: number;
  readonly needed: number;
}

export interface Answers {
  readonly kind: "answers";
  /** The category the person is on now — the question, not the answer. */
  readonly fromCategory: string;
  /**
   * `conditional` counts only the changes out of `fromCategory`; `overall` counts every
   * change, minus those answering `fromCategory`, which cannot happen by construction.
   * Which one was used is shown to the reader, because they mean different things.
   */
  readonly basis: "conditional" | "overall";
  readonly denominator: number;
  /** Every answer, most common first, ties broken by name. Never truncated here. */
  readonly answers: readonly CategoryShare[];
  /** Total presentable changes on record, whichever basis was used. */
  readonly totalChanges: number;
}

export type NextCategoryCard = NotEnoughHistory | Answers;

export interface CardOptions {
  readonly minConditional?: number;
  readonly minTotal?: number;
}

function tally(categories: readonly string[]): CategoryShare[] {
  const counts = new Map<string, number>();
  for (const category of categories) {
    counts.set(category, (counts.get(category) ?? 0) + 1);
  }
  const denominator = categories.length;
  return [...counts.entries()]
    .map(([category, count]) => ({
      category,
      count,
      denominator,
      share: denominator > 0 ? count / denominator : 0,
    }))
    .sort((a, b) => (b.count - a.count) || (a.category < b.category ? -1 : 1));
}

/**
 * The category of the most recent run — what the person is on now.
 *
 * `null` for an empty stream. Transitions alone cannot answer this: the newest run has not
 * been left yet, so it appears as no transition's source.
 */
export function currentCategory(
  transitions: readonly CategoryTransition[],
): string | null {
  const last = transitions[transitions.length - 1];
  return last === undefined ? null : last.toCategory;
}

/**
 * What usually follows the category you are on, with the counts behind it.
 *
 * Every transition is used; there is no training window and no fold, because nothing is
 * fitted. That is the point — this ships before any target is adopted and does not wait on
 * one.
 */
export function nextCategoryCard(
  transitions: readonly CategoryTransition[],
  fromCategory: string,
  options: CardOptions = {},
): NextCategoryCard {
  const minConditional = options.minConditional ?? MIN_CONDITIONAL_CHANGES;
  const minTotal = options.minTotal ?? MIN_TOTAL_CHANGES;

  const presentable = transitions.filter(
    (item) => item.toCategory !== UNPRESENTABLE_ANSWER,
  );
  if (presentable.length < minTotal) {
    return {
      kind: "not-enough-history",
      changes: presentable.length,
      needed: minTotal - presentable.length,
    };
  }

  const conditional = presentable
    .filter((item) => item.fromCategory === fromCategory)
    .map((item) => item.toCategory);

  if (conditional.length >= minConditional) {
    return {
      kind: "answers",
      fromCategory,
      basis: "conditional",
      denominator: conditional.length,
      answers: tally(conditional),
      totalChanges: presentable.length,
    };
  }

  // The overall rates, minus the answers that cannot occur. A change out of `fromCategory`
  // never lands back on it, so leaving those in would put a category on the card that is
  // impossible right now — the exact defect D102 found in `global_mode`, which spent 31.9%
  // of its Edge predictions on the source category.
  const overall = presentable
    .filter((item) => item.toCategory !== fromCategory)
    .map((item) => item.toCategory);

  return {
    kind: "answers",
    fromCategory,
    basis: "overall",
    denominator: overall.length,
    answers: tally(overall),
    totalChanges: presentable.length,
  };
}
