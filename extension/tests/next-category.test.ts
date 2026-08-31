/**
 * The "what comes next" card, and the three rules that keep it honest.
 *
 * This is the first surface Tise has that shows a number to a person, so the properties
 * asserted here are product claims rather than internal ones:
 *
 * * **the percentage equals the fraction shown.** No smoothing, no rounding inside the
 *   model. A denominator that does not divide into the number above it is decoration.
 * * **the only gate is evidence, never confidence.** D88 retired abstention; what replaced
 *   it is a minimum number of observations, and nothing else may withhold a row.
 * * **a category that cannot happen is never offered.** You just left `news`, so `news` is
 *   not what comes next — the defect D102 found in `global_mode`, which spent 31.9% of its
 *   Edge predictions on exactly that.
 */
import { describe, expect, it } from "vitest";
import type { CategoryTransition } from "../src/features/transitions";
import {
  MIN_CONDITIONAL_CHANGES,
  MIN_TOTAL_CHANGES,
  currentCategory,
  nextCategoryCard,
  type Answers,
} from "../src/model/nextCategory";

let counter = 0;

function change(from: string, to: string): CategoryTransition {
  counter += 1;
  return {
    transitionId: `t${counter}`,
    at: new Date(Date.UTC(2026, 5, 1, 9, counter)).toISOString(),
    fromCategory: from,
    toCategory: to,
    sessionId: `s${Math.floor(counter / 4)}`,
    withinSession: true,
    previousCategory: null,
    fromRunEvents: 1,
  };
}

function many(from: string, to: string, times: number): CategoryTransition[] {
  return Array.from({ length: times }, () => change(from, to));
}

/** Enough unrelated history to clear `MIN_TOTAL_CHANGES` without touching a subject. */
function filler(times: number = MIN_TOTAL_CHANGES): CategoryTransition[] {
  return many("work", "search", times);
}

function answers(card: ReturnType<typeof nextCategoryCard>): Answers {
  if (card.kind !== "answers") throw new Error(`expected answers, got ${card.kind}`);
  return card;
}

describe("the evidence floor", () => {
  it("shows nothing at all below the total floor, and says how much is missing", () => {
    const card = nextCategoryCard(many("news", "video", 5), "news");
    expect(card.kind).toBe("not-enough-history");
    if (card.kind !== "not-enough-history") return;
    expect(card.changes).toBe(5);
    expect(card.changes + card.needed).toBe(MIN_TOTAL_CHANGES);
  });

  it("is a floor on evidence, not on confidence", () => {
    // The whole difference from the abstention rule D88 retired. Twenty changes that all
    // went the same way are as certain as data gets, and would have been *withheld* by a
    // confidence threshold on a thin validation slice. Here they are shown.
    const card = answers(nextCategoryCard(many("news", "video", MIN_TOTAL_CHANGES), "news"));
    expect(card.answers[0]?.category).toBe("video");
    expect(card.answers[0]?.share).toBe(1);
  });

  it("falls back to overall rates when the conditional history is thin, and says so", () => {
    const card = answers(
      nextCategoryCard([...filler(), ...many("news", "video", 2)], "news"),
    );
    expect(card.basis).toBe("overall");
    expect(card.denominator).toBe(MIN_TOTAL_CHANGES + 2);
  });

  it("leads with the conditional counts once there are enough of them", () => {
    const card = answers(
      nextCategoryCard(
        [...filler(), ...many("news", "video", MIN_CONDITIONAL_CHANGES)],
        "news",
      ),
    );
    expect(card.basis).toBe("conditional");
    expect(card.denominator).toBe(MIN_CONDITIONAL_CHANGES);
  });
});

describe("the denominator is real", () => {
  it("shows a share that is exactly the count over the denominator", () => {
    const card = answers(
      nextCategoryCard(
        [...many("news", "video", 9), ...many("news", "work", 3), ...filler()],
        "news",
      ),
    );
    for (const answer of card.answers) {
      expect(answer.share).toBe(answer.count / answer.denominator);
      expect(answer.denominator).toBe(card.denominator);
    }
  });

  it("does not smooth, unlike the fitted table", () => {
    // `transition.ts` pulls every row toward the marginal, which is right for a model and
    // wrong for a displayed count: a smoothed 9 of 12 is not 75% and the reader is owed
    // the number they can check.
    const card = answers(
      nextCategoryCard([...many("news", "video", 12), ...filler()], "news"),
    );
    expect(card.answers).toHaveLength(1);
    expect(card.answers[0]?.share).toBe(1);
  });

  it("counts sum to the denominator", () => {
    const card = answers(
      nextCategoryCard(
        [...many("news", "video", 7), ...many("news", "work", 4), ...filler()],
        "news",
      ),
    );
    const total = card.answers.reduce((sum, answer) => sum + answer.count, 0);
    expect(total).toBe(card.denominator);
  });
});

describe("what is never offered", () => {
  it("never answers with the category just left", () => {
    // Impossible by construction: a change out of `news` cannot land on `news`. The
    // overall basis has to remove it explicitly, which is where it could go wrong.
    const card = answers(
      nextCategoryCard(
        [...many("work", "news", 15), ...many("work", "video", 8), ...many("news", "work", 2)],
        "news",
      ),
    );
    expect(card.basis).toBe("overall");
    expect(card.answers.map((a) => a.category)).not.toContain("news");
  });

  it("never answers `unknown`, but still answers questions asked from it (D27)", () => {
    const card = answers(
      nextCategoryCard(
        [
          ...many("unknown", "video", MIN_CONDITIONAL_CHANGES),
          ...filler(),
          ...many("news", "unknown", 30),
        ],
        "unknown",
      ),
    );
    expect(card.answers.map((a) => a.category)).not.toContain("unknown");
    expect(card.answers[0]?.category).toBe("video");
  });

  it("does not let `unknown` clear the evidence floor either", () => {
    // Found by a failing test above. Thirty changes into `unknown` are thirty changes
    // nothing can display, so counting them toward the floor would unlock a card built
    // on ten real observations while telling the reader it rests on forty.
    const card = nextCategoryCard(
      [...many("news", "video", 5), ...many("news", "unknown", 40)],
      "news",
    );
    expect(card.kind).toBe("not-enough-history");
    if (card.kind !== "not-enough-history") return;
    expect(card.changes).toBe(5);
  });

  it("does not let `unknown` inflate the denominator", () => {
    const card = answers(
      nextCategoryCard(
        [...many("news", "video", 10), ...many("news", "unknown", 40), ...filler()],
        "news",
      ),
    );
    expect(card.denominator).toBe(10);
    expect(card.answers[0]?.count).toBe(10);
  });
});

describe("ordering", () => {
  it("puts the most common answer first", () => {
    const card = answers(
      nextCategoryCard(
        [...many("news", "work", 3), ...many("news", "video", 9), ...filler()],
        "news",
      ),
    );
    expect(card.answers.map((a) => a.category)).toEqual(["video", "work"]);
  });

  it("breaks ties by name rather than by insertion order", () => {
    // Otherwise the card reorders itself when nothing about the person changed.
    const forward = answers(
      nextCategoryCard(
        [...many("news", "video", 5), ...many("news", "apps", 5), ...filler()],
        "news",
      ),
    );
    const backward = answers(
      nextCategoryCard(
        [...many("news", "apps", 5), ...many("news", "video", 5), ...filler()],
        "news",
      ),
    );
    expect(forward.answers.map((a) => a.category)).toEqual(["apps", "video"]);
    expect(backward.answers.map((a) => a.category)).toEqual(["apps", "video"]);
  });

  it("returns every answer rather than a top slice", () => {
    // Truncation is the UI's decision, and it needs the total to say "and 4 others".
    const card = answers(
      nextCategoryCard(
        [
          ...many("news", "video", 6),
          ...many("news", "work", 3),
          ...many("news", "apps", 2),
          ...many("news", "shopping", 1),
          ...filler(),
        ],
        "news",
      ),
    );
    expect(card.answers).toHaveLength(4);
  });
});

describe("the current category", () => {
  it("is where the newest change landed", () => {
    // Not the newest transition's *source*: the run that has just started is the one the
    // person is in, and it has not been left yet.
    expect(currentCategory([change("news", "video"), change("video", "work")])).toBe("work");
  });

  it("is null with no history rather than a guess", () => {
    expect(currentCategory([])).toBeNull();
  });
});
