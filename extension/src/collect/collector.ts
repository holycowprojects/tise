/**
 * One navigation in, at most one stored event out.
 *
 * All of the decision-making lives here rather than in `background.ts`, which is a thin
 * shell around `chrome.webNavigation`. The split is what makes the collector testable
 * without a browser — and T5 was a reminder that anything only testable in a browser
 * tends to be believed rather than checked.
 *
 * Calls are serialised. Navigation events can arrive faster than a read-modify-write of
 * the session cursor completes, and two interleaved writes would hand the same session
 * id to events an hour apart.
 */
import type { TiseEvent } from "../types";
import { deleteMeta, readMeta, writeMeta } from "../storage/db";
import { putEvent } from "../storage/events";
import { isCollecting, loadSettings } from "../storage/settings";
import { normaliseNavigation, type NavigationDetails, type RejectionReason } from "./normalise";
import { advanceSession, type SessionCursor } from "./session";
import { attentionEnabled, beginSpan } from "./attention";

const CURSOR_KEY = "sessionCursor";
const REJECTIONS_KEY = "rejections";

export type SkipReason = RejectionReason | "not-collecting";

export type CollectOutcome =
  | { readonly stored: true; readonly event: TiseEvent }
  | { readonly stored: false; readonly reason: SkipReason };

let queue: Promise<unknown> = Promise.resolve();

/** Run `task` after every previously queued task, whether those succeeded or not. */
function serialised<T>(task: () => Promise<T>): Promise<T> {
  const next = queue.then(task, task);
  queue = next.then(
    () => undefined,
    () => undefined,
  );
  return next;
}

async function recordRejection(reason: RejectionReason): Promise<void> {
  const counts = (await readMeta<Record<string, number>>(REJECTIONS_KEY)) ?? {};
  counts[reason] = (counts[reason] ?? 0) + 1;
  await writeMeta(REJECTIONS_KEY, counts);
}

/** Aggregate counts of what was filtered out. Counts only — never a rejected URL. */
export async function rejectionCounts(): Promise<Record<string, number>> {
  return (await readMeta<Record<string, number>>(REJECTIONS_KEY)) ?? {};
}

export function collect(details: NavigationDetails): Promise<CollectOutcome> {
  return serialised(async () => {
    const settings = await loadSettings();

    // Checked before anything is parsed. Not collecting means not looking, and the
    // early return is what makes "installed but inert" a state rather than a promise.
    if (!isCollecting(settings)) {
      return { stored: false, reason: "not-collecting" } as const;
    }

    const result = normaliseNavigation(details, { overrides: settings.overrides });
    if (!result.ok) {
      await recordRejection(result.reason);
      return { stored: false, reason: result.reason } as const;
    }

    const cursor = await readMeta<SessionCursor>(CURSOR_KEY);
    const next = advanceSession(
      cursor ?? null,
      result.event.occurredAt,
      settings.sessionTimeoutSeconds,
    );

    const event: TiseEvent = { ...result.event, sessionId: next.sessionId };
    await putEvent(event);
    await writeMeta(CURSOR_KEY, next);

    // A navigation ends the previous span in that tab and begins a new one. Done after
    // the event is stored so a span can never reference an event that failed to write.
    // `tabId` is used here and **never stored** — it identifies which tab the attention
    // belongs to and is discarded with this call.
    if (typeof details.tabId === "number" && (await attentionEnabled())) {
      await beginSpan(event.eventId, details.tabId);
    }

    return { stored: true, event } as const;
  });
}

/** Exposed so tests can start from a known cursor instead of a shared one. */
export async function resetSessionCursor(): Promise<void> {
  await deleteMeta(CURSOR_KEY);
}
