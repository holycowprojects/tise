/**
 * The history import.
 *
 * The fake API below returns exactly the fields T5 observed on a real `VisitItem` —
 * `visitId`, `visitTime`, `transition`, `referringVisitId` — and deliberately no
 * duration field, because there isn't one. A fake that is more generous than the real
 * API is how you end up shipping code that depends on something Chrome never sends.
 */
import "fake-indexeddb/auto";
import { IDBFactory } from "fake-indexeddb";
import { beforeEach, describe, expect, it } from "vitest";
import {
  isLikelyRedirect,
  prepareEvents,
  REDIRECT_GAP_MS,
  runImport,
  type HistoryApi,
  type HistoryVisit,
} from "../src/collect/import";
import { collect } from "../src/collect/collector";
import { readMeta, closeTiseDb } from "../src/storage/db";
import { allEvents, countEvents } from "../src/storage/events";
import { saveSettings } from "../src/storage/settings";
import { EVENT_FIELDS } from "../src/types";

const NOW = Date.parse("2026-08-26T12:00:00.000Z");
const DAY = 24 * 60 * 60 * 1000;
const TIMEOUT = 1800;

interface FakePage {
  url: string;
  visits: HistoryVisit[];
}

function fakeApi(pages: FakePage[]): HistoryApi & { searchCalls: unknown[] } {
  const searchCalls: unknown[] = [];
  return {
    searchCalls,
    async search(query) {
      searchCalls.push(query);
      return pages.map((page) => ({ url: page.url }));
    },
    async getVisits({ url }) {
      return pages.find((page) => page.url === url)?.visits ?? [];
    },
  };
}

function visit(overrides: Partial<HistoryVisit> & { visitId: string }): HistoryVisit {
  return {
    visitTime: NOW - DAY,
    transition: "link",
    referringVisitId: "0",
    ...overrides,
  };
}

const CORPUS: FakePage[] = [
  {
    url: "https://www.youtube.com/watch?v=abc",
    visits: [
      visit({ visitId: "1", visitTime: NOW - 2 * DAY }),
      visit({ visitId: "2", visitTime: NOW - 2 * DAY + 60_000 }),
    ],
  },
  {
    url: "https://www.google.com/search?q=private+question",
    visits: [visit({ visitId: "3", visitTime: NOW - 2 * DAY + 120_000, transition: "typed" })],
  },
  {
    url: "https://news.ycombinator.com/item?id=1",
    visits: [visit({ visitId: "4", visitTime: NOW - DAY })],
  },
];

beforeEach(async () => {
  await closeTiseDb();
  globalThis.indexedDB = new IDBFactory();
});

describe("bounds are always explicit", () => {
  it("never lets Chrome's 24-hour, 100-row default apply", async () => {
    const api = fakeApi(CORPUS);
    await runImport({ api, now: NOW, sessionTimeoutSeconds: TIMEOUT });

    expect(api.searchCalls).toHaveLength(1);
    const query = api.searchCalls[0] as Record<string, number | string>;
    expect(query["startTime"]).toBe(NOW - 90 * DAY);
    expect(query["endTime"]).toBe(NOW);
    expect(query["maxResults"]).toBeGreaterThanOrEqual(50_000);
    expect(query["text"]).toBe("");
  });

  it("drops visits that fall outside the window", () => {
    const { events, skipped } = prepareEvents(
      [
        { url: "https://example.com/", visit: visit({ visitId: "old", visitTime: NOW - 400 * DAY }) },
        { url: "https://example.com/", visit: visit({ visitId: "new", visitTime: NOW - DAY }) },
      ],
      { startTime: NOW - 90 * DAY, endTime: NOW, sessionTimeoutSeconds: TIMEOUT },
    );
    expect(events).toHaveLength(1);
    expect(skipped["out-of-window"]).toBe(1);
  });
});

describe("imported events are indistinguishable from live ones in shape", () => {
  beforeEach(async () => {
    await runImport({ api: fakeApi(CORPUS), now: NOW, sessionTimeoutSeconds: TIMEOUT });
  });

  it("wrote one event per visit", async () => {
    expect(await countEvents()).toBe(4);
  });

  it("marks them as imported", async () => {
    for (const event of await allEvents()) expect(event.source).toBe("import");
  });

  it("never invents a dwell time (D35)", async () => {
    for (const event of await allEvents()) expect(event.dwellSeconds).toBeNull();
  });

  it("has exactly the declared fields and no URL", async () => {
    const dump = JSON.stringify(await allEvents());
    for (const event of await allEvents()) {
      expect(Object.keys(event).sort()).toEqual([...EVENT_FIELDS].sort());
    }
    expect(dump).not.toContain("private+question");
    expect(dump).not.toContain("?");
    expect(dump).not.toMatch(/https?:/);
  });

  it("resolved categories the same way live collection does", async () => {
    const byDomain = new Map((await allEvents()).map((e) => [e.domain, e.category]));
    expect(byDomain.get("youtube.com")).toBe("video");
    expect(byDomain.get("google.com")).toBe("search");
  });
});

describe("importing twice creates no duplicates", () => {
  it("leaves the row count unchanged", async () => {
    await runImport({ api: fakeApi(CORPUS), now: NOW, sessionTimeoutSeconds: TIMEOUT });
    const first = await countEvents();

    await runImport({ api: fakeApi(CORPUS), now: NOW, sessionTimeoutSeconds: TIMEOUT });
    expect(await countEvents()).toBe(first);
  });

  it("derives the event id from the visit id, not from a clock or a counter", () => {
    const { events } = prepareEvents(
      [{ url: "https://example.com/", visit: visit({ visitId: "77" }) }],
      { startTime: NOW - 90 * DAY, endTime: NOW, sessionTimeoutSeconds: TIMEOUT },
    );
    expect(events[0]?.eventId).toBe("imp_77");
  });
});

describe("the import stops where live collection starts (D43)", () => {
  /**
   * The defect this covers was found by looking at a real popup, not by a test: a visit
   * that both routes saw is stored twice, once with a uuid and once as `imp_<visitId>`,
   * and no id check can catch it because the two ids are legitimately different.
   */
  async function browse(url: string, at: number): Promise<void> {
    await saveSettings({ consentGrantedAt: new Date(at).toISOString(), paused: false });
    await collect({
      url,
      frameId: 0,
      timeStamp: at,
      transitionType: "link",
      transitionQualifiers: [],
    });
  }

  it("does not re-import a visit the collector already saw", async () => {
    const watched = NOW - 60_000;
    await browse("https://www.youtube.com/watch?v=abc", watched);
    expect(await countEvents()).toBe(1);

    // The same visit, as the history API would report it.
    const api = fakeApi([
      {
        url: "https://www.youtube.com/watch?v=abc",
        visits: [visit({ visitId: "dup", visitTime: watched })],
      },
    ]);
    await runImport({ api, now: NOW, sessionTimeoutSeconds: TIMEOUT });

    const events = await allEvents();
    expect(events).toHaveLength(1);
    expect(events[0]?.source).toBe("live");
  });

  it("still imports everything from before collection began", async () => {
    const watched = NOW - 60_000;
    await browse("https://www.youtube.com/watch?v=abc", watched);

    const api = fakeApi([
      {
        url: "https://news.ycombinator.com/",
        visits: [visit({ visitId: "old", visitTime: NOW - 10 * DAY })],
      },
      {
        url: "https://www.youtube.com/watch?v=abc",
        visits: [visit({ visitId: "dup", visitTime: watched })],
      },
    ]);
    const progress = await runImport({ api, now: NOW, sessionTimeoutSeconds: TIMEOUT });

    expect(progress.eventsWritten).toBe(1);
    expect((await allEvents()).map((e) => e.source)).toEqual(["import", "live"]);
  });

  it("records where it stopped, so the UI can say so rather than look truncated", async () => {
    const watched = NOW - 60_000;
    await browse("https://www.youtube.com/watch?v=abc", watched);

    const progress = await runImport({
      api: fakeApi([]),
      now: NOW,
      sessionTimeoutSeconds: TIMEOUT,
    });
    expect(progress.stoppedAt).toBe(new Date(watched).toISOString());
  });

  it("runs to the present when nothing has been collected live", async () => {
    const progress = await runImport({
      api: fakeApi(CORPUS),
      now: NOW,
      sessionTimeoutSeconds: TIMEOUT,
    });
    expect(progress.stoppedAt).toBeNull();
    expect(progress.eventsWritten).toBe(4);
  });
});

describe("redirect hops, without the transition qualifiers Chrome does not expose", () => {
  const referrers = new Map([["100", NOW - DAY]]);

  it("flags a hop that follows its referrer faster than a person can click", () => {
    const hop = visit({ visitId: "101", visitTime: NOW - DAY + 20, referringVisitId: "100" });
    expect(isLikelyRedirect(hop, referrers)).toBe(true);
  });

  it("keeps a navigation that took longer than the threshold", () => {
    const click = visit({
      visitId: "102",
      visitTime: NOW - DAY + REDIRECT_GAP_MS + 1,
      referringVisitId: "100",
    });
    expect(isLikelyRedirect(click, referrers)).toBe(false);
  });

  it("keeps a visit whose referrer was never fetched — it cannot be judged", () => {
    const orphan = visit({ visitId: "103", visitTime: NOW, referringVisitId: "999" });
    expect(isLikelyRedirect(orphan, referrers)).toBe(false);
  });

  it("keeps a visit with no referrer at all", () => {
    expect(isLikelyRedirect(visit({ visitId: "104" }), referrers)).toBe(false);
  });

  it("drops the hop but keeps the page the person actually asked for", () => {
    const { events, skipped } = prepareEvents(
      [
        {
          url: "https://example.com/",
          visit: visit({ visitId: "200", visitTime: NOW - DAY }),
        },
        {
          url: "https://tracker.example.org/r",
          visit: visit({ visitId: "201", visitTime: NOW - DAY + 10, referringVisitId: "200" }),
        },
      ],
      { startTime: NOW - 90 * DAY, endTime: NOW, sessionTimeoutSeconds: TIMEOUT },
    );
    expect(events.map((e) => e.domain)).toEqual(["example.com"]);
    expect(skipped["redirect"]).toBe(1);
  });
});

describe("what else is filtered", () => {
  it("drops subframes and non-web URLs", () => {
    const { events, skipped } = prepareEvents(
      [
        {
          url: "https://ads.example.com/frame",
          visit: visit({ visitId: "300", transition: "auto_subframe" }),
        },
        { url: "chrome://settings", visit: visit({ visitId: "301" }) },
        { url: "file:///C:/Users/a/notes.txt", visit: visit({ visitId: "302" }) },
        { url: "https://example.com/", visit: visit({ visitId: "303" }) },
      ],
      { startTime: NOW - 90 * DAY, endTime: NOW, sessionTimeoutSeconds: TIMEOUT },
    );
    expect(events).toHaveLength(1);
    expect(skipped["subframe"]).toBe(1);
    expect(skipped["not-web"]).toBe(2);
  });
});

describe("sessions across an import", () => {
  it("groups the whole batch at once, which live collection cannot do", () => {
    const { events } = prepareEvents(
      [
        { url: "https://a.example/", visit: visit({ visitId: "1", visitTime: NOW - 3 * DAY }) },
        {
          url: "https://b.example/",
          visit: visit({ visitId: "2", visitTime: NOW - 3 * DAY + 5 * 60_000 }),
        },
        { url: "https://c.example/", visit: visit({ visitId: "3", visitTime: NOW - 2 * DAY }) },
      ],
      { startTime: NOW - 90 * DAY, endTime: NOW, sessionTimeoutSeconds: TIMEOUT },
    );
    const ids = events.map((e) => e.sessionId);
    expect(new Set(ids).size).toBe(2);
    expect(ids[0]).toBe(ids[1]);
  });

  it("sorts by time even when the API returns visits out of order", () => {
    const { events } = prepareEvents(
      [
        { url: "https://b.example/", visit: visit({ visitId: "2", visitTime: NOW - DAY }) },
        { url: "https://a.example/", visit: visit({ visitId: "1", visitTime: NOW - 2 * DAY }) },
      ],
      { startTime: NOW - 90 * DAY, endTime: NOW, sessionTimeoutSeconds: TIMEOUT },
    );
    expect(events.map((e) => e.domain)).toEqual(["a.example", "b.example"]);
  });

  it("hands the live cursor the last imported session, so browsing continues it", async () => {
    await runImport({ api: fakeApi(CORPUS), now: NOW, sessionTimeoutSeconds: TIMEOUT });

    const cursor = await readMeta<{ sessionId: string; lastEventAt: string }>("sessionCursor");
    const last = (await allEvents()).at(-1);
    expect(cursor?.sessionId).toBe(last?.sessionId);
    expect(cursor?.lastEventAt).toBe(last?.occurredAt);
  });
});

describe("progress and failure", () => {
  it("reports what it did", async () => {
    const progress = await runImport({
      api: fakeApi(CORPUS),
      now: NOW,
      sessionTimeoutSeconds: TIMEOUT,
    });
    expect(progress.state).toBe("done");
    expect(progress.pagesTotal).toBe(3);
    expect(progress.pagesDone).toBe(3);
    expect(progress.eventsWritten).toBe(4);
    expect(progress.windowDays).toBe(90);
  });

  it("records a failure instead of throwing, and keeps no cause object", async () => {
    const broken: HistoryApi = {
      search: () => Promise.reject(new Error("history permission removed")),
      getVisits: () => Promise.resolve([]),
    };
    const progress = await runImport({
      api: broken,
      now: NOW,
      sessionTimeoutSeconds: TIMEOUT,
    });
    expect(progress.state).toBe("failed");
    expect(progress.error).toBe("history permission removed");
    expect(await countEvents()).toBe(0);
  });

  it("writes nothing when the browser has no history", async () => {
    const progress = await runImport({
      api: fakeApi([]),
      now: NOW,
      sessionTimeoutSeconds: TIMEOUT,
    });
    expect(progress.state).toBe("done");
    expect(progress.eventsWritten).toBe(0);
    expect(await countEvents()).toBe(0);
  });
});
