/**
 * Everything the dashboard shows, as pure functions over stored data.
 *
 * **The DOM lives in `ui/dashboard/`; the arithmetic lives here.** Not for tidiness — the
 * test suite runs in Node with no DOM, so anything computed inside a render function is
 * untestable by construction, and a dashboard is exactly where a wrong number is least
 * likely to be noticed and most likely to be believed.
 *
 * **Every number here traces to something stored.** Nothing is estimated, projected or
 * annualised. Where a number cannot be computed the answer is `null` and the page says so
 * (D51: absence is never a zero wearing a measurement's clothes).
 */
import type { CategoryTransition } from "../features/transitions";
import type { Prediction } from "./prediction";
import type { TiseEvent } from "../types";
import {
  MIN_CONDITIONAL_CHANGES,
  UNPRESENTABLE_ANSWER,
  nextCategoryCard,
  type Answers,
  type CardOptions,
} from "./nextCategory";

export interface TopicBoardEntry {
  readonly fromCategory: string;
  readonly card: Answers;
}

/**
 * "After X you usually go to…" for every topic with enough history to answer for itself.
 *
 * **Only the conditional cards.** A topic that falls back to the overall rates would print
 * the same row as every other topic that fell back, and a board of identical rows reads as
 * a finding when it is the absence of one. The popup's single card keeps the fallback,
 * because there it is the difference between showing something and showing nothing.
 *
 * Ordered by how much is behind each one, so the best-evidenced topic leads. The
 * denominator is on every row regardless, so the order is a convenience and not a claim.
 */
export function topicBoard(
  transitions: readonly CategoryTransition[],
  options: CardOptions = {},
): TopicBoardEntry[] {
  const sources = new Set(
    transitions
      .filter((item) => item.toCategory !== UNPRESENTABLE_ANSWER)
      .map((item) => item.fromCategory),
  );

  const entries: TopicBoardEntry[] = [];
  for (const fromCategory of [...sources].sort()) {
    const card = nextCategoryCard(transitions, fromCategory, options);
    if (card.kind !== "answers" || card.basis !== "conditional") continue;
    entries.push({ fromCategory, card });
  }
  return entries.sort(
    (a, b) =>
      b.card.denominator - a.card.denominator ||
      (a.fromCategory < b.fromCategory ? -1 : 1),
  );
}

export interface Hub {
  readonly category: string;
  /** How many topics lead there most often. */
  readonly leadsFrom: number;
  /** Out of how many topics on the board. */
  readonly topics: number;
}

/**
 * The topic most other topics lead back to — if a majority of them do.
 *
 * **Found on contact with a real profile, and it is the most useful line on the page.**
 * On 640 category changes, eight of ten topics led most often to `search`; two of them at
 * 100%. A board of ten cards that mostly say the same word reads as a broken page, and it
 * is not broken — it is the hub-and-spoke shape of real browsing, where a search engine
 * sits between everything else. Naming it turns ten repetitive rows into one fact plus the
 * rows that actually differ.
 *
 * **A majority is the rule, declared here rather than tuned.** Below half, there is no hub
 * and the board is already telling the story by itself; there is nothing to say and the
 * page says nothing. This never hides a card — every topic is still listed with its own
 * counts — it only adds a sentence.
 *
 * It also explains a published result. D102 found that `constrained_mode`, which ignores
 * what you just left, beat the fitted transition table on every corpus. A hub is exactly
 * the shape that makes that happen: when the answer is the same regardless of the question,
 * conditioning on the question buys nothing.
 */
export function hubTopic(board: readonly TopicBoardEntry[]): Hub | null {
  if (board.length === 0) return null;

  const leads = new Map<string, number>();
  for (const entry of board) {
    const top = entry.card.answers[0];
    if (top === undefined) continue;
    leads.set(top.category, (leads.get(top.category) ?? 0) + 1);
  }

  let best: Hub | null = null;
  for (const [category, leadsFrom] of leads) {
    if (best === null || leadsFrom > best.leadsFrom) {
      best = { category, leadsFrom, topics: board.length };
    }
  }
  if (best === null || best.leadsFrom * 2 <= board.length) return null;
  return best;
}

export interface TopicCount {
  readonly category: string;
  readonly count: number;
  readonly share: number;
}

export interface BrowsingSummary {
  readonly events: number;
  /** Null on an empty store rather than an epoch date. */
  readonly firstAt: string | null;
  readonly lastAt: string | null;
  /** Calendar days spanned, inclusive. Null when there is nothing to span. */
  readonly days: number | null;
  readonly sessions: number;
  readonly topics: number;
  readonly changes: number;
  /** Changes whose answer is `unknown`, and therefore cannot be shown (D27). */
  readonly unshowableChanges: number;
  readonly liveEvents: number;
  readonly importedEvents: number;
  /** Every topic by volume, largest first, ties by name. */
  readonly byTopic: readonly TopicCount[];
}

export function browsingSummary(
  events: readonly TiseEvent[],
  sessionCount: number,
  transitions: readonly CategoryTransition[],
): BrowsingSummary {
  const times = events.map((event) => event.occurredAt).sort();
  const first = times[0] ?? null;
  const last = times[times.length - 1] ?? null;

  const counts = new Map<string, number>();
  let live = 0;
  for (const event of events) {
    counts.set(event.category, (counts.get(event.category) ?? 0) + 1);
    if (event.source === "live") live += 1;
  }

  const byTopic = [...counts.entries()]
    .map(([category, count]) => ({
      category,
      count,
      share: events.length > 0 ? count / events.length : 0,
    }))
    .sort((a, b) => b.count - a.count || (a.category < b.category ? -1 : 1));

  return {
    events: events.length,
    firstAt: first,
    lastAt: last,
    // Inclusive: browsing on one day is one day, not zero.
    days:
      first !== null && last !== null
        ? Math.floor((Date.parse(last) - Date.parse(first)) / 86_400_000) + 1
        : null,
    sessions: sessionCount,
    topics: counts.size,
    changes: transitions.length,
    unshowableChanges: transitions.filter(
      (item) => item.toCategory === UNPRESENTABLE_ANSWER,
    ).length,
    liveEvents: live,
    importedEvents: events.length - live,
    byTopic,
  };
}

export interface Scorecard {
  readonly total: number;
  readonly hit: number;
  readonly miss: number;
  readonly pending: number;
  /** D72: a window Tise was not watching. **Not a miss** — scored by nobody. */
  readonly expired: number;
  /** Rows written under the retired confidence rule. Counts down, never up (D103). */
  readonly withheldByRetiredRule: number;
  readonly scored: number;
  /**
   * `hit / (hit + miss)`. **Null until something has actually resolved** — a scorecard
   * reading 0% because nothing has been scored yet is a lie in the shape of a measurement.
   */
  readonly accuracy: number | null;
}

export function scorecard(predictions: readonly Prediction[]): Scorecard {
  const by = (outcome: string): number =>
    predictions.filter((prediction) => prediction.outcome === outcome).length;

  const hit = by("hit");
  const miss = by("miss");
  const scored = hit + miss;
  return {
    total: predictions.length,
    hit,
    miss,
    pending: by("pending"),
    expired: by("expired"),
    withheldByRetiredRule: predictions.filter((prediction) => prediction.abstained).length,
    scored,
    accuracy: scored > 0 ? hit / scored : null,
  };
}

/**
 * Whether the topic board has anything to say yet, and what is missing if not.
 *
 * The dashboard needs this before rendering, because "no topic has enough history" and
 * "you have not browsed enough at all" are different things to a person and the fix
 * differs: the first resolves itself, the second needs more browsing.
 */
export function boardReadiness(
  transitions: readonly CategoryTransition[],
  minConditional: number = MIN_CONDITIONAL_CHANGES,
): { readonly ready: number; readonly closest: number } {
  const counts = new Map<string, number>();
  for (const item of transitions) {
    if (item.toCategory === UNPRESENTABLE_ANSWER) continue;
    counts.set(item.fromCategory, (counts.get(item.fromCategory) ?? 0) + 1);
  }
  const sizes = [...counts.values()];
  return {
    ready: sizes.filter((size) => size >= minConditional).length,
    closest: sizes.length > 0 ? Math.max(...sizes) : 0,
  };
}
