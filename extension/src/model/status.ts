/**
 * What Tise claims, what it does not, and where every target actually stands.
 *
 * **This exists because the same defect has already happened once.** Between D88 and D97
 * `reports.py` said the project predicted `block_volume`, which D92 had retired, and eight
 * generated reports told readers so. Right numbers, wrong frame, in the module written to
 * prevent exactly that. The lesson recorded there was that one constant was being asked to
 * mean two things — a goal and a shipped fact — and one of them was always wrong.
 *
 * A dashboard is where that defect becomes visible to a *person* rather than a reader of
 * benchmarks, so the states are separated here and the shipped one is pinned by a test
 * against `predict.ts` itself. `research/tise_research/reports.py` anchors to the same
 * file from the other language.
 *
 * **The states are not a ranking.** `retired` is not failure and `measured` is not
 * half-shipped; they are different facts. A target is retired when the question stopped
 * being worth asking, which is what happened to `return_24h` — it was measurable and
 * uninteresting, and finding that out cost thirteen tasks and is the reason the rest of
 * this list is honest.
 */

export type TargetState =
  /** Trained and predicted by the extension today. */
  | "shipped"
  /** Cleared a bar written before it was fitted, and is not wired in yet. */
  | "adopted"
  /**
   * Cleared its bar, and deliberately not shipped because a *data* gate fixed in advance
   * is not met and will not be (D124).
   *
   * Distinct from `adopted`, which describes a wait. This one is a decision: the model is
   * good and the person's data is insufficient, which is a real and common answer rather
   * than a stage on the way to shipping. Keeping them apart is the whole point of this
   * file — D88 to D97 had one constant meaning both a goal and a shipped fact, and one of
   * the two was always wrong.
   */
  | "withheld"
  /** Scored against a pre-registered bar; the result did not adopt it. */
  | "measured"
  /** Definition, bar and adoption rule fixed in advance. Nothing fitted. */
  | "registered"
  /** Registered and cannot be measured yet, for a stated reason. */
  | "blocked"
  /** The question stopped being worth asking. */
  | "retired";

export interface TargetStatus {
  readonly name: string;
  /** In the person's words, not the project's. */
  readonly question: string;
  readonly state: TargetState;
  /** What a reader would otherwise have to take on trust. Always says the awkward part. */
  readonly note: string;
}

/**
 * Every target this project has taken seriously, with the decision behind its state.
 *
 * Ordered by what a reader needs first: the thing on screen, then the thing that nearly
 * is, then the ones that are not.
 */
export const TARGET_STATUS: readonly TargetStatus[] = [
  {
    name: "next_category",
    question: "What topic comes next?",
    state: "measured",
    note:
      "The card on this page is counts, not this model. The fitted version cleared the " +
      "bar written before it was fitted, and a rule that knows only that you will not " +
      "resume what you just stopped scored higher on every browser tested (D102). So " +
      "Tise shows you what you did rather than what a model thinks you will do.",
  },
  {
    name: "visit_engaged",
    question: "Will this page hold your attention?",
    state: "withheld",
    note:
      "The one place machine learning has earned its place here, and it is switched off. " +
      "It cleared a bar set before it was fitted (D97) and held on 1,326 other people's " +
      "browsing (D100), beating a constant for 88.6% of them individually. Switching it " +
      "on needed 1,000 visits Tise actually watched — a rule fixed before any of your " +
      "attention was measured, and one that excluded 822 of those 1,326 people. Your " +
      "browsing does not reach it: Tise only keeps 30 days at a time, so the count " +
      "settles near 650 and stays there. Waiting does not fix that, so rather than " +
      "quietly lower the bar, Tise shows you what it measured instead (D123, D124).",
  },
  {
    name: "return_24h",
    question: "Will you come back to this topic within a day?",
    state: "retired",
    note:
      "Measurable and uninteresting (D88). A session is not a unit anyone cares about, " +
      "and a 65-72% base rate was most of the answer. The extension still trains it, " +
      "because nothing has replaced it yet — those predictions are kept and scored, and " +
      "they are not shown to you as advice.",
  },
  {
    name: "block_volume",
    question: "Will a topic be busier than usual tomorrow?",
    state: "retired",
    note:
      "The base-rate table beat the model, so the table would have shipped and the model " +
      "would not (D92). Retired rather than shipped half-way.",
  },
  {
    name: "browsing_next_hour",
    question: "Will you be browsing in the next hour?",
    state: "registered",
    note:
      "Bar and rule fixed in advance, nothing fitted. The bar is your own daily rhythm " +
      "rather than a flat rate, because beating a flat rate would be trivial — and the " +
      "pre-registered prediction is that this one fails.",
  },
  {
    name: "tab_return",
    question: "Will you come back to this tab?",
    state: "blocked",
    note:
      "Cannot be measured on any browser history, which records visits and not tabs. " +
      "Registered in advance anyway, so its definition is fixed before the first data " +
      "arrives rather than shaped by it.",
  },
];

/** Purchase intent, and why it is absent rather than labelled "not evaluated". */
export const PURCHASE_INTENT_NOTE =
  "Predicting what you are about to buy was this project's original headline. It is not " +
  "here, and not because it is hard: confirming it would mean reading checkout pages, " +
  "which the privacy design forbids outright. A demo of it would be a number nobody " +
  "measured, shown next to numbers that were.";

export function statusFor(name: string): TargetStatus | null {
  return TARGET_STATUS.find((entry) => entry.name === name) ?? null;
}

/** The target the extension actually trains. Pinned against `predict.ts` by a test. */
export const SHIPPED_TARGET = "return_24h";
