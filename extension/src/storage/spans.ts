/**
 * Reading attention spans. D96 wrote them and gave nothing a way to read them back.
 *
 * That gap had two consequences, and neither was visible from the collection code:
 *
 * * **The export omitted them**, so live dwell could never reach the research tier — and
 *   the whole architecture is that Python only ever sees a file the person chose to hand
 *   over. `export.ts` says the file "contains everything Tise holds" and that omitting
 *   part of the store would be "the visible half of the truth". It was.
 * * **Retention never expired them**, though D96 said they expire with raw events. Spans
 *   are raw browsing data: when they began, how long attention lasted, which navigation
 *   they belong to. The README promises raw data is deleted after 30 days, so an
 *   unbounded span store is a broken privacy promise, not just a stale comment.
 *
 * Both are fixed here and in `retention.ts`. This module owns the *store*; the span
 * lifecycle — when one opens, extends and closes — stays in `collect/attention.ts`, which
 * is the only place that decides a span exists.
 */
import { openTiseDb } from "./db";
import type { AttentionSpan } from "../types";

/** Every span, ordered by when attention ended. The export's read. */
export async function allSpans(): Promise<AttentionSpan[]> {
  const db = await openTiseDb();
  return db.getAllFromIndex("attention", "endedAt");
}

/**
 * How many spans exist. Cheap, and the only honest answer to "is collection working?".
 *
 * Until this existed, nothing in the extension or the export could answer that question,
 * so the only way to check was to open DevTools and read the row count by hand.
 */
export async function countSpans(): Promise<number> {
  const db = await openTiseDb();
  return db.count("attention");
}

/**
 * Delete spans that ended before `cutoff`. Called by retention, never on its own.
 *
 * Keyed on `endedAt` rather than on the parent event's timestamp: a span is deleted when
 * *it* is old enough, which is the same rule raw events get. Joining back to the event to
 * ask when the navigation happened would delete a span for a reason the span does not
 * carry, and would silently keep spans whose event had already been expired.
 */
export async function deleteSpansBefore(cutoff: string): Promise<number> {
  const db = await openTiseDb();
  const tx = db.transaction("attention", "readwrite");
  const index = tx.store.index("endedAt");

  let deleted = 0;
  let cursor = await index.openCursor(IDBKeyRange.upperBound(cutoff, true));
  while (cursor) {
    await cursor.delete();
    deleted += 1;
    cursor = await cursor.continue();
  }
  await tx.done;
  return deleted;
}

/**
 * Write spans in bulk. Used by tests and by any future import; collection writes one at a
 * time through `collect/attention.ts`, which is where the decision to record one is made.
 *
 * `spanId` is the key and is derived from the event and the start instant, so re-writing a
 * span replaces it rather than duplicating it.
 */
export async function putSpans(spans: readonly AttentionSpan[]): Promise<void> {
  if (spans.length === 0) return;
  const db = await openTiseDb();
  const tx = db.transaction("attention", "readwrite");
  await Promise.all(spans.map((span) => tx.store.put(span)));
  await tx.done;
}
