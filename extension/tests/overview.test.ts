/**
 * What the dashboard shows, tested where it is computed rather than where it is drawn.
 *
 * A dashboard is the place a wrong number is least likely to be noticed and most likely to
 * be believed, so the arithmetic lives in `src/model/overview.ts` and is asserted here. The
 * render functions in `ui/dashboard/` do DOM and nothing else, which is what makes that
 * possible: the suite runs in Node with no DOM at all.
 *
 * The properties that matter are the ones about *absence*. A scorecard reading 0% because
 * nothing has resolved yet, or a topic board padded out with a fallback that looks like a
 * finding, would both be wrong in a way no test of the happy path would catch.
 */
import { describe, expect, it } from "vitest";
import type { CategoryTransition } from "../src/features/transitions";
import type { Prediction } from "../src/model/prediction";
import type { TiseEvent } from "../src/types";
import { MIN_CONDITIONAL_CHANGES } from "../src/model/nextCategory";
import {
  boardReadiness,
  browsingSummary,
  hubTopic,
  scorecard,
  topicBoard,
} from "../src/model/overview";

let counter = 0;

function change(from: string, to: string): CategoryTransition {
  counter += 1;
  return {
    transitionId: `t${counter}`,
    at: new Date(Date.UTC(2026, 5, 1, 9, counter)).toISOString(),
    fromCategory: from,
    toCategory: to,
    sessionId: "s1",
    withinSession: true,
    previousCategory: null,
    fromRunEvents: 1,
  };
}

function many(from: string, to: string, times: number): CategoryTransition[] {
  return Array.from({ length: times }, () => change(from, to));
}

function event(category: string, day: number, source: "live" | "import"): TiseEvent {
  counter += 1;
  return {
    eventId: `e${counter}`,
    occurredAt: new Date(Date.UTC(2026, 5, day, 9, 0, counter)).toISOString(),
    source,
    domain: `${category}.example`,
    category,
    transition: "link",
    dwellSeconds: null,
    sessionId: "s1",
  };
}

function prediction(outcome: string, abstained = false): Prediction {
  counter += 1;
  return {
    predictionId: `p${counter}`,
    createdAt: "2026-06-01T09:00:00.000Z",
    target: "return_24h",
    subject: "video",
    probability: 0.7,
    windowStart: "2026-06-01T09:00:00.000Z",
    windowEnd: "2026-06-02T09:00:00.000Z",
    abstained,
    modelName: "logreg_fs3",
    modelVersion: "cal_1@2026-06-01T09:00:00.000Z",
    featureSet: "fs_3",
    dataCutoff: "2026-06-01T09:00:00.000Z",
    evidence: [],
    outcome: outcome as Prediction["outcome"],
    resolvedAt: outcome === "pending" ? null : "2026-06-02T09:00:00.000Z",
  };
}

describe("the topic board", () => {
  it("lists only topics with enough history to answer for themselves", () => {
    // A topic that fell back to the overall rates would print the same row as every other
    // topic that fell back, and a board of identical rows reads as a finding.
    const board = topicBoard([
      ...many("news", "video", MIN_CONDITIONAL_CHANGES),
      ...many("work", "search", MIN_CONDITIONAL_CHANGES),
      ...many("apps", "video", 2),
    ]);
    expect(board.map((entry) => entry.fromCategory).sort()).toEqual(["news", "work"]);
    expect(board.every((entry) => entry.card.basis === "conditional")).toBe(true);
  });

  it("puts the best-evidenced topic first", () => {
    const board = topicBoard([
      ...many("news", "video", MIN_CONDITIONAL_CHANGES),
      ...many("work", "search", MIN_CONDITIONAL_CHANGES + 5),
    ]);
    expect(board[0]?.fromCategory).toBe("work");
  });

  it("breaks ties by name, so the board does not reshuffle itself", () => {
    const board = topicBoard([
      ...many("work", "search", MIN_CONDITIONAL_CHANGES),
      ...many("news", "video", MIN_CONDITIONAL_CHANGES),
    ]);
    expect(board.map((entry) => entry.fromCategory)).toEqual(["news", "work"]);
  });

  it("is empty rather than padded when nothing qualifies", () => {
    expect(topicBoard(many("news", "video", 3))).toEqual([]);
  });

  it("never offers `unknown` as an answer on any row", () => {
    const board = topicBoard([
      ...many("news", "video", MIN_CONDITIONAL_CHANGES),
      ...many("news", "unknown", 40),
    ]);
    for (const entry of board) {
      expect(entry.card.answers.map((a) => a.category)).not.toContain("unknown");
    }
  });
});

describe("board readiness", () => {
  it("reports how close the closest topic is, so waiting has an end in sight", () => {
    const readiness = boardReadiness(many("news", "video", 6));
    expect(readiness.ready).toBe(0);
    expect(readiness.closest).toBe(6);
  });

  it("counts the topics that already qualify", () => {
    const readiness = boardReadiness([
      ...many("news", "video", MIN_CONDITIONAL_CHANGES),
      ...many("work", "search", MIN_CONDITIONAL_CHANGES),
      ...many("apps", "video", 1),
    ]);
    expect(readiness.ready).toBe(2);
  });

  it("does not count changes into `unknown` toward readiness", () => {
    expect(boardReadiness(many("news", "unknown", 50)).closest).toBe(0);
  });

  it("is zero on an empty history rather than throwing", () => {
    expect(boardReadiness([])).toEqual({ ready: 0, closest: 0 });
  });
});

describe("the browsing summary", () => {
  const EVENTS = [
    event("news", 1, "import"),
    event("news", 1, "import"),
    event("video", 3, "live"),
  ];

  it("counts a single day as one day, not zero", () => {
    const summary = browsingSummary([event("news", 1, "live")], 1, []);
    expect(summary.days).toBe(1);
  });

  it("spans the days between first and last inclusively", () => {
    expect(browsingSummary(EVENTS, 2, []).days).toBe(3);
  });

  it("separates what Tise saw from what it was handed", () => {
    // The distinction D88 makes load-bearing: an import may set a yardstick, only live
    // collection may score. A page that merged them would hide which is which.
    const summary = browsingSummary(EVENTS, 2, []);
    expect(summary.liveEvents).toBe(1);
    expect(summary.importedEvents).toBe(2);
  });

  it("ranks topics by volume, ties by name", () => {
    const summary = browsingSummary(EVENTS, 2, []);
    expect(summary.byTopic.map((topic) => topic.category)).toEqual(["news", "video"]);
    expect(summary.byTopic[0]?.share).toBeCloseTo(2 / 3, 10);
  });

  it("counts the changes it cannot show, so the two totals reconcile", () => {
    const summary = browsingSummary(EVENTS, 2, [
      ...many("news", "video", 4),
      ...many("news", "unknown", 3),
    ]);
    expect(summary.changes).toBe(7);
    expect(summary.unshowableChanges).toBe(3);
  });

  it("has no dates at all on an empty store, rather than an epoch", () => {
    const summary = browsingSummary([], 0, []);
    expect(summary.firstAt).toBeNull();
    expect(summary.lastAt).toBeNull();
    expect(summary.days).toBeNull();
    expect(summary.byTopic).toEqual([]);
  });
});

describe("the scorecard", () => {
  it("has no accuracy until something has actually resolved", () => {
    // 0% would be a lie in the shape of a measurement, and it is the number a reader
    // would most readily believe.
    const card = scorecard([prediction("pending"), prediction("pending")]);
    expect(card.accuracy).toBeNull();
    expect(card.scored).toBe(0);
  });

  it("scores hits against hits plus misses only", () => {
    const card = scorecard([
      prediction("hit"),
      prediction("hit"),
      prediction("hit"),
      prediction("miss"),
      prediction("pending"),
      prediction("expired"),
    ]);
    expect(card.scored).toBe(4);
    expect(card.accuracy).toBe(0.75);
  });

  it("never counts an expired window as a miss (D72)", () => {
    // A window Tise was not watching is scored by nobody. Folding it in would invent
    // failures that never happened.
    const card = scorecard([prediction("hit"), ...Array.from({ length: 9 }, () => prediction("expired"))]);
    expect(card.expired).toBe(9);
    expect(card.miss).toBe(0);
    expect(card.accuracy).toBe(1);
  });

  it("counts rows written by the retired confidence rule separately", () => {
    const card = scorecard([prediction("hit", true), prediction("hit", false)]);
    expect(card.withheldByRetiredRule).toBe(1);
  });

  it("is all zeroes and no accuracy when nothing has been predicted", () => {
    const card = scorecard([]);
    expect(card.total).toBe(0);
    expect(card.accuracy).toBeNull();
  });
});

describe("the hub", () => {
  const board = (transitions: CategoryTransition[]) => topicBoard(transitions);

  it("names the topic a majority of topics lead back to", () => {
    // The shape found on a real profile: eight of ten topics led most often to search,
    // two of them at 100%. Ten cards mostly saying one word is not a broken page.
    const hub = hubTopic(
      board([
        ...many("news", "search", MIN_CONDITIONAL_CHANGES),
        ...many("work", "search", MIN_CONDITIONAL_CHANGES),
        ...many("video", "search", MIN_CONDITIONAL_CHANGES),
        ...many("search", "travel", MIN_CONDITIONAL_CHANGES),
      ]),
    );
    expect(hub?.category).toBe("search");
    expect(hub?.leadsFrom).toBe(3);
    expect(hub?.topics).toBe(4);
  });

  it("says nothing when no topic holds a majority", () => {
    // Below half there is no hub, the board already tells the story, and a sentence
    // would be inventing a pattern out of the largest of several small numbers.
    const hub = hubTopic(
      board([
        ...many("news", "video", MIN_CONDITIONAL_CHANGES),
        ...many("work", "search", MIN_CONDITIONAL_CHANGES),
      ]),
    );
    expect(hub).toBeNull();
  });

  it("needs strictly more than half, not exactly half", () => {
    const hub = hubTopic(
      board([
        ...many("news", "search", MIN_CONDITIONAL_CHANGES),
        ...many("work", "search", MIN_CONDITIONAL_CHANGES),
        ...many("video", "dev", MIN_CONDITIONAL_CHANGES),
        ...many("apps", "travel", MIN_CONDITIONAL_CHANGES),
      ]),
    );
    expect(hub).toBeNull();
  });

  it("is null on an empty board rather than throwing", () => {
    expect(hubTopic([])).toBeNull();
  });

  it("never hides a card — it only adds a sentence", () => {
    const transitions = [
      ...many("news", "search", MIN_CONDITIONAL_CHANGES),
      ...many("work", "search", MIN_CONDITIONAL_CHANGES),
      ...many("search", "travel", MIN_CONDITIONAL_CHANGES),
    ];
    expect(hubTopic(board(transitions))).not.toBeNull();
    expect(board(transitions)).toHaveLength(3);
  });
});
