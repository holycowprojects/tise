/**
 * Raw events expire. Derived features do not (D11).
 *
 * That asymmetry is the whole design: a person keeps the model that was learned from
 * their browsing without keeping a record of the browsing itself. It is also why this
 * file touches the `events` store and nothing else — when the `features` store arrives at
 * T10 it must survive retention, and the safest way to guarantee that is for the code
 * that deletes to know about exactly one store.
 *
 * `rawRetentionDays: 0` means keep everything. Zero is the natural way to write "no
 * limit" in a settings field, and the alternative — a magic `null` or `-1` — is the kind
 * of thing that gets mishandled once and silently deletes a corpus.
 */
import { openTiseDb } from "./db";
import type { Settings } from "./settings";

export const RETENTION_ALARM = "tise:retention";

/** Six hours. Frequent enough that a day's expiry is never far off, cheap enough to ignore. */
export const RETENTION_PERIOD_MINUTES = 6 * 60;

export interface RetentionOutcome {
  readonly deleted: number;
  /** The boundary applied, or `null` when retention is off. */
  readonly cutoff: string | null;
}

/**
 * Delete raw events older than the retention window.
 *
 * Walks the `occurredAt` index over a bounded range rather than scanning, so the cost is
 * proportional to what is being deleted and not to what is being kept.
 */
export async function enforceRetention(
  settings: Settings,
  now: number,
): Promise<RetentionOutcome> {
  if (settings.rawRetentionDays <= 0) return { deleted: 0, cutoff: null };

  const cutoff = new Date(now - settings.rawRetentionDays * 24 * 60 * 60 * 1000).toISOString();

  const db = await openTiseDb();
  const tx = db.transaction("events", "readwrite");
  const index = tx.store.index("occurredAt");

  let deleted = 0;
  let cursor = await index.openCursor(IDBKeyRange.upperBound(cutoff, true));
  while (cursor) {
    await cursor.delete();
    deleted += 1;
    cursor = await cursor.continue();
  }
  await tx.done;

  return { deleted, cutoff };
}
