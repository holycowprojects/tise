/**
 * Measuring attention: how long a navigation actually held the person, not the tab.
 *
 * D35 recorded the duration trap as permanent — the history *file* has `visit_duration`,
 * the `chrome.history` API does not — so `dwellSeconds` has been `null` for every event
 * since T1. `chrome.tabs` and `chrome.idle` lift it, and they measure something **better**
 * than `visit_duration` rather than the same thing: a tab left open overnight records a
 * long duration and no attention whatsoever. D93 named that as the caveat capable of
 * accounting for its entire measured effect.
 *
 * **The rule that governs everything here: never invent a span.** If Tise cannot attribute
 * a period of attention to a specific navigation, it records nothing. A span with a
 * guessed `eventId` is indistinguishable from a measured one the moment it is written,
 * which is D51's principle applied to time instead of to features.
 *
 * **State lives in IndexedDB, not in this module.** MV3 terminates the service worker
 * constantly, so a variable holding the open span would be lost several times an hour and
 * every span would be silently truncated. It is not in `chrome.storage.session` either:
 * that needs the `storage` permission, and `db.ts` keeps every cursor in IndexedDB
 * precisely so the manifest stays at the permissions D31 justified and not one more.
 *
 * The pure functions below are separated from the listeners for the same reason
 * `normalise.ts` is — so the lifecycle can be tested without a browser.
 */
import { openTiseDb, readMeta, writeMeta, deleteMeta } from "../storage/db";
import { isCollecting, loadSettings } from "../storage/settings";
import { assertStorableSpan, type AttentionEndReason, type AttentionSpan } from "../types";

/** The open span, and the tab→event map needed to reopen one after an idle period. */
const OPEN_KEY = "attention:open";
const TABS_KEY = "attention:tabs";

/**
 * Idle threshold in seconds. Chrome's minimum is 15; 60 is chosen because a shorter one
 * ends a span every time somebody reads a long paragraph without touching the mouse,
 * which would measure typing rather than attention. Declared, not tuned.
 */
export const IDLE_THRESHOLD_SECONDS = 60;

/**
 * Longest span Tise will record from a single open period, in seconds.
 *
 * Not a timeout — a **cap**, and the difference matters. If the worker dies while a span
 * is open, the reopening code cannot tell an hour of reading from an hour of the laptop
 * being shut. Capping keeps an unobserved gap from entering the data as measured
 * attention; the alternative is a single 14-hour span that outweighs a month of real ones.
 */
export const MAX_SPAN_SECONDS = 30 * 60;

export interface OpenSpan {
  readonly eventId: string;
  readonly tabId: number;
  readonly startedAt: string;
}

/** `tabId` → the most recent navigation in that tab. Bounded by `MAX_TRACKED_TABS`. */
export type TabEventMap = Record<string, string>;

/** Someone with 400 tabs open should not grow this without limit. Oldest entries drop. */
export const MAX_TRACKED_TABS = 200;

/**
 * Close an open span, returning the record to store — or `null` when there is nothing
 * worth storing.
 *
 * Returns `null` rather than a zero-length span for a reason: a span of zero seconds is
 * not a measurement of no attention, it is the absence of a measurement, and storing it
 * would drag every average toward zero for rows that were never observed.
 */
export function closeSpan(
  open: OpenSpan,
  endedAt: number,
  endReason: AttentionEndReason,
  maxSeconds: number = MAX_SPAN_SECONDS,
): AttentionSpan | null {
  const started = Date.parse(open.startedAt);
  if (!Number.isFinite(started)) return null;

  const elapsed = (endedAt - started) / 1000;
  if (!(elapsed > 0)) return null;

  const capped = Math.min(elapsed, maxSeconds);
  return {
    spanId: `${open.eventId}:${open.startedAt}`,
    eventId: open.eventId,
    startedAt: open.startedAt,
    endedAt: new Date(started + capped * 1000).toISOString(),
    activeSeconds: capped,
    endReason,
  };
}

/** Remember which navigation is showing in a tab, dropping the oldest when full. */
export function rememberTab(
  map: TabEventMap,
  tabId: number,
  eventId: string,
): TabEventMap {
  const next: TabEventMap = { ...map, [String(tabId)]: eventId };
  const keys = Object.keys(next);
  if (keys.length <= MAX_TRACKED_TABS) return next;
  for (const key of keys.slice(0, keys.length - MAX_TRACKED_TABS)) {
    delete next[key];
  }
  return next;
}

async function readOpen(): Promise<OpenSpan | undefined> {
  return readMeta<OpenSpan>(OPEN_KEY);
}

async function readTabs(): Promise<TabEventMap> {
  return (await readMeta<TabEventMap>(TABS_KEY)) ?? {};
}

/** Write a span, refusing anything that carries a field it should not. */
async function storeSpan(span: AttentionSpan): Promise<void> {
  assertStorableSpan(span);
  const db = await openTiseDb();
  await db.put("attention", span);
}

/**
 * End whatever span is open. Idempotent: with nothing open it does nothing, which is what
 * makes it safe to call from every listener without coordinating them.
 */
export async function endOpenSpan(
  endReason: AttentionEndReason,
  now: number = Date.now(),
): Promise<AttentionSpan | null> {
  const open = await readOpen();
  if (open === undefined) return null;
  await deleteMeta(OPEN_KEY);

  const span = closeSpan(open, now, endReason);
  if (span === null) return null;
  await storeSpan(span);
  return span;
}

/**
 * Begin a span for a navigation. Closes any span already open first — two open at once
 * would double-count a single person's attention.
 */
export async function beginSpan(
  eventId: string,
  tabId: number,
  now: number = Date.now(),
): Promise<void> {
  await endOpenSpan("navigated", now);
  await writeMeta(TABS_KEY, rememberTab(await readTabs(), tabId, eventId));
  await writeMeta(OPEN_KEY, {
    eventId,
    tabId,
    startedAt: new Date(now).toISOString(),
  } satisfies OpenSpan);
}

/**
 * The person moved to another tab. Closes the current span and opens one for the new tab
 * **only if** Tise knows which navigation that tab is showing — otherwise it records
 * nothing rather than attributing attention to a guess.
 */
export async function switchToTab(
  tabId: number,
  now: number = Date.now(),
): Promise<void> {
  await endOpenSpan("tab-switch", now);
  const eventId = (await readTabs())[String(tabId)];
  if (eventId === undefined) return;
  await writeMeta(OPEN_KEY, {
    eventId,
    tabId,
    startedAt: new Date(now).toISOString(),
  } satisfies OpenSpan);
}

/** A tab closed. Ends its span and forgets it. */
export async function forgetTab(
  tabId: number,
  now: number = Date.now(),
): Promise<void> {
  const open = await readOpen();
  if (open?.tabId === tabId) await endOpenSpan("tab-closed", now);
  const tabs = await readTabs();
  if (String(tabId) in tabs) {
    const next = { ...tabs };
    delete next[String(tabId)];
    await writeMeta(TABS_KEY, next);
  }
}

/**
 * Whether collection may run at all. Checked in every listener before anything is read or
 * written — consent is not assumed from the permission being granted, because a person can
 * grant `tabs` and still not have consented to Tise storing anything.
 */
export async function attentionEnabled(): Promise<boolean> {
  const settings = await loadSettings();
  if (settings.consentGrantedAt === null) return false;
  if (!isCollecting(settings)) return false;
  return chrome.permissions.contains({ permissions: ["tabs", "idle"] });
}

/**
 * Register the listeners. Called from the service worker's top level, because MV3 reads
 * the registration to decide which events wake the worker — a listener added later inside
 * a callback would never fire after the first termination.
 */
export function registerAttentionListeners(): void {
  chrome.tabs?.onActivated.addListener((info) => {
    void (async () => {
      if (await attentionEnabled()) await switchToTab(info.tabId);
    })();
  });

  chrome.tabs?.onRemoved.addListener((tabId) => {
    void (async () => {
      if (await attentionEnabled()) await forgetTab(tabId);
    })();
  });

  chrome.idle?.onStateChanged.addListener((state) => {
    void (async () => {
      if (!(await attentionEnabled())) return;
      // Only the leaving edge is handled. Returning from idle does not reopen a span:
      // Chrome reports `active` on the first input, which may be in another application
      // entirely, and attributing that to whatever tab was last open would be a guess.
      if (state !== "active") await endOpenSpan("idle");
    })();
  });

  chrome.windows?.onFocusChanged.addListener((windowId) => {
    void (async () => {
      if (!(await attentionEnabled())) return;
      if (windowId === chrome.windows.WINDOW_ID_NONE) await endOpenSpan("blur");
    })();
  });

  chrome.idle?.setDetectionInterval?.(IDLE_THRESHOLD_SECONDS);
}
