/**
 * One-time backfill from `chrome.history`.
 *
 * A new user with no history has nothing to predict from, so the first run offers to
 * read what the browser already knows (D10). The `history` permission is **optional** and
 * requested from a click (D33); declining costs the import and nothing else, and the
 * extension has to keep working while doing nothing.
 *
 * Three things about this API, all observed at T5 rather than read:
 *
 * 1. **No dwell time.** `VisitItem` is `id, isLocal, referringVisitId, transition,
 *    visitId, visitTime` and nothing else. The duration trap, proven.
 * 2. **No transition qualifiers.** `transition` is the core type only, so an import
 *    cannot drop redirect hops the way `webNavigation` does. See `isLikelyRedirect`.
 * 3. **`search` truncates by default** to 24 hours and 100 rows — documented, and *not*
 *    observed, because the throwaway profile had nothing to truncate. The mitigation is
 *    unconditional: `startTime`, `endTime` and `maxResults` are always passed explicitly,
 *    so the default never applies and never needs to be confirmed.
 */
import { earliestLiveEventAt, putEvents } from "../storage/events";
import { readMeta, writeMeta } from "../storage/db";
import type { TiseEvent } from "../types";
import { registrableDomain } from "./domain";
import { resolve } from "./resolver";
import { advanceSession, type SessionCursor } from "./session";

/** Chrome's `HistoryItem`, narrowed to what the import reads. */
export interface HistoryPage {
  readonly url?: string | undefined;
}

/** Chrome's `VisitItem`, narrowed to what the import reads. */
export interface HistoryVisit {
  readonly visitId?: string | undefined;
  readonly visitTime?: number | undefined;
  readonly transition?: string | undefined;
  readonly referringVisitId?: string | undefined;
}

export interface HistoryApi {
  search(query: {
    text: string;
    startTime: number;
    endTime: number;
    maxResults: number;
  }): Promise<HistoryPage[]>;
  getVisits(details: { url: string }): Promise<HistoryVisit[]>;
}

/**
 * Below human reaction time.
 *
 * A person cannot follow a link 50 ms after the page they are on commits, so a
 * navigation that close to its referrer was not a decision. This threshold is argued
 * from that, not fitted: `analysis/redirect_heuristic.py` scored it against the real
 * transition bits afterwards and it holds at precision 0.93–0.95 on both corpora, but
 * the reasoning came first and would stand without the table. See D40.
 */
export const REDIRECT_GAP_MS = 50;

/** Subframe transitions. An iframe is not a navigation the person chose to make. */
const SUBFRAME_TRANSITIONS: ReadonlySet<string> = new Set([
  "auto_subframe",
  "manual_subframe",
]);

/**
 * Explicit, and larger than any plausible personal corpus. T1 measured 5,706 visits
 * across 90 days on the largest profile here; this is an order of magnitude above that,
 * and it exists so that Chrome's 100-row default can never silently apply.
 */
export const MAX_PAGES = 50_000;

export const DEFAULT_IMPORT_DAYS = 90;

const PROGRESS_KEY = "importProgress";
const CURSOR_KEY = "sessionCursor";

export type ImportState = "running" | "done" | "failed";

export interface ImportProgress {
  readonly state: ImportState;
  readonly pagesTotal: number;
  readonly pagesDone: number;
  readonly eventsWritten: number;
  readonly skipped: Readonly<Record<string, number>>;
  readonly windowDays: number;
  readonly startedAt: string;
  readonly finishedAt: string | null;
  /**
   * Where the window was cut short because live collection takes over there (D43), or
   * `null` when the import ran to the present.
   */
  readonly stoppedAt: string | null;
  readonly error?: string;
}

export async function importProgress(): Promise<ImportProgress | undefined> {
  return readMeta<ImportProgress>(PROGRESS_KEY);
}

/**
 * Whether this visit looks like a redirect hop rather than a chosen navigation.
 *
 * `referrerTimes` maps visit id to visit time across everything fetched, because the
 * referrer of a hop is usually a different page. A visit whose referrer was never
 * fetched cannot be judged, and the honest default there is to keep it: a false positive
 * deletes a real navigation, a false negative leaves one redirect hop in.
 */
export function isLikelyRedirect(
  visit: HistoryVisit,
  referrerTimes: ReadonlyMap<string, number>,
): boolean {
  const referrerId = visit.referringVisitId;
  if (!referrerId || referrerId === "0") return false;

  const referrerTime = referrerTimes.get(referrerId);
  if (referrerTime === undefined || visit.visitTime === undefined) return false;

  const gap = visit.visitTime - referrerTime;
  return gap >= 0 && gap <= REDIRECT_GAP_MS;
}

export type SkipReason = "not-web" | "subframe" | "redirect" | "out-of-window" | "malformed";

interface Prepared {
  readonly events: TiseEvent[];
  readonly skipped: Record<string, number>;
}

/**
 * Turn fetched visits into events. Pure — no clock, no storage, no `chrome`.
 *
 * Sessions are assigned by walking the whole batch in time order with the same rule the
 * live collector uses. An import can do this properly because it sees the past all at
 * once, which live collection never can.
 */
export function prepareEvents(
  visits: ReadonlyArray<{ url: string; visit: HistoryVisit }>,
  options: {
    readonly startTime: number;
    readonly endTime: number;
    readonly sessionTimeoutSeconds: number;
    readonly overrides?: Readonly<Record<string, string>>;
  },
): Prepared {
  const skipped: Record<string, number> = {};
  const bump = (reason: SkipReason) => {
    skipped[reason] = (skipped[reason] ?? 0) + 1;
  };

  const referrerTimes = new Map<string, number>();
  for (const { visit } of visits) {
    if (visit.visitId !== undefined && visit.visitTime !== undefined) {
      referrerTimes.set(visit.visitId, visit.visitTime);
    }
  }

  const kept: Array<{ visit: HistoryVisit; domain: string }> = [];
  for (const { url, visit } of visits) {
    if (visit.visitId === undefined || visit.visitTime === undefined) {
      bump("malformed");
      continue;
    }
    if (visit.visitTime < options.startTime || visit.visitTime > options.endTime) {
      bump("out-of-window");
      continue;
    }
    if (visit.transition !== undefined && SUBFRAME_TRANSITIONS.has(visit.transition)) {
      bump("subframe");
      continue;
    }
    if (isLikelyRedirect(visit, referrerTimes)) {
      bump("redirect");
      continue;
    }
    const domain = registrableDomain(url);
    if (domain === null) {
      bump("not-web");
      continue;
    }
    kept.push({ visit, domain });
  }

  kept.sort((a, b) => (a.visit.visitTime ?? 0) - (b.visit.visitTime ?? 0));

  const events: TiseEvent[] = [];
  let cursor: SessionCursor | null = null;
  for (const { visit, domain } of kept) {
    const occurredAt = new Date(visit.visitTime as number).toISOString();
    cursor = advanceSession(cursor, occurredAt, options.sessionTimeoutSeconds);
    events.push({
      // Deterministic, so importing twice writes the same rows rather than duplicates.
      eventId: `imp_${visit.visitId}`,
      occurredAt,
      source: "import",
      domain,
      category: resolve(domain, options.overrides).category,
      transition: visit.transition ?? "link",
      dwellSeconds: null, // D35 — the API could not supply it and we would not use it
      sessionId: cursor.sessionId,
    });
  }

  return { events, skipped };
}

export interface ImportOptions {
  readonly api: HistoryApi;
  readonly now: number;
  readonly days?: number;
  readonly sessionTimeoutSeconds: number;
  readonly overrides?: Readonly<Record<string, string>>;
  readonly onProgress?: (progress: ImportProgress) => void;
}

const BATCH_SIZE = 500;

/**
 * Read the browser's history and write it as events.
 *
 * T5 measured `getVisits` at 0.7 ms per page, so a 5,000-page corpus is about three and
 * a half seconds in one pass. There is no chunking across alarms here because there is
 * nothing to chunk — but progress is written to storage as it goes, so the popup can
 * close mid-import and still show where it got to.
 *
 * The window ends where live collection begins (D43). Importing a period the collector
 * already watched would store every visit in it twice, and deduplicating by id cannot
 * help: a live event's id is a uuid and an imported one is `imp_<visitId>`, so the two
 * rows for one visit are legitimately distinct. Not overlapping is the only fix that
 * works without inventing a fuzzy match on domain and timestamp.
 */
export async function runImport(options: ImportOptions): Promise<ImportProgress> {
  const windowDays = options.days ?? DEFAULT_IMPORT_DAYS;
  const startTime = options.now - windowDays * 24 * 60 * 60 * 1000;

  // D43: the import stops where live collection starts. A visit that both routes saw
  // would otherwise be stored twice — once with a random id, once as `imp_<visitId>` —
  // and no id-based check can catch that, because the two ids are legitimately different.
  const firstLive = await earliestLiveEventAt();
  const stoppedAt = firstLive === null ? null : firstLive;
  const endTime = firstLive === null ? options.now : Math.min(options.now, Date.parse(firstLive) - 1);

  let progress: ImportProgress = {
    state: "running",
    pagesTotal: 0,
    pagesDone: 0,
    eventsWritten: 0,
    skipped: {},
    windowDays,
    startedAt: new Date(options.now).toISOString(),
    finishedAt: null,
    stoppedAt,
  };

  const publish = async (next: ImportProgress): Promise<void> => {
    progress = next;
    await writeMeta(PROGRESS_KEY, next);
    options.onProgress?.(next);
  };

  await publish(progress);

  try {
    // Every bound is explicit. Chrome's defaults are never allowed to apply.
    const pages = await options.api.search({
      text: "",
      startTime,
      endTime,
      maxResults: MAX_PAGES,
    });

    const urls = pages.map((page) => page.url).filter((url): url is string => !!url);
    await publish({ ...progress, pagesTotal: urls.length });

    const fetched: Array<{ url: string; visit: HistoryVisit }> = [];
    for (const [index, url] of urls.entries()) {
      for (const visit of await options.api.getVisits({ url })) {
        fetched.push({ url, visit });
      }
      if ((index + 1) % 100 === 0 || index + 1 === urls.length) {
        await publish({ ...progress, pagesDone: index + 1 });
      }
    }

    const { events, skipped } = prepareEvents(fetched, {
      startTime,
      endTime,
      sessionTimeoutSeconds: options.sessionTimeoutSeconds,
      ...(options.overrides !== undefined ? { overrides: options.overrides } : {}),
    });

    for (let i = 0; i < events.length; i += BATCH_SIZE) {
      await putEvents(events.slice(i, i + BATCH_SIZE));
      await publish({ ...progress, eventsWritten: Math.min(i + BATCH_SIZE, events.length) });
    }

    // Live collection continues the last imported session rather than opening a new one
    // a second later. Session ids are local and opaque (D36); this only affects grouping.
    const last = events[events.length - 1];
    if (last !== undefined) {
      const existing = await readMeta<SessionCursor>(CURSOR_KEY);
      if (existing === undefined || Date.parse(existing.lastEventAt) < Date.parse(last.occurredAt)) {
        await writeMeta(CURSOR_KEY, {
          sessionId: last.sessionId,
          lastEventAt: last.occurredAt,
        } satisfies SessionCursor);
      }
    }

    await publish({
      ...progress,
      state: "done",
      eventsWritten: events.length,
      skipped,
      finishedAt: new Date().toISOString(),
    });
  } catch (error) {
    await publish({
      ...progress,
      state: "failed",
      finishedAt: new Date().toISOString(),
      // The message, never the cause object: a rejected history call can carry a URL.
      error: error instanceof Error ? error.message : "unknown error",
    });
  }

  return progress;
}

/** Adapter over the real API. Nothing else in this file mentions `chrome`. */
export function chromeHistoryApi(): HistoryApi {
  return {
    search: (query) => chrome.history.search(query),
    getVisits: (details) => chrome.history.getVisits(details),
  };
}
