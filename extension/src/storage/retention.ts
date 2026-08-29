/**
 * Raw events expire. Derived features do not (D11).
 *
 * That asymmetry is the whole design: a person keeps the model that was learned from
 * their browsing without keeping a record of the browsing itself. `features` and `labels`
 * must survive retention, and the safest guarantee is that the code which deletes knows
 * about exactly the stores that expire.
 *
 * **`attention` expires too, and did not until now.** D96 said spans expire with raw
 * events and then shipped without touching this file, so they accumulated without bound.
 * A span is raw browsing data — when attention began, how long it lasted, which
 * navigation it belongs to — and the README promises raw data is deleted after 30 days.
 * That made it a broken privacy promise rather than a stale comment.
 *
 * `rawRetentionDays: 0` means keep everything. Zero is the natural way to write "no
 * limit" in a settings field, and the alternative — a magic `null` or `-1` — is the kind
 * of thing that gets mishandled once and silently deletes a corpus.
 */
import { openTiseDb } from "./db";
import { deleteSpansBefore } from "./spans";
import type { Settings } from "./settings";

export const RETENTION_ALARM = "tise:retention";

/** Six hours. Frequent enough that a day's expiry is never far off, cheap enough to ignore. */
export const RETENTION_PERIOD_MINUTES = 6 * 60;

export interface RetentionOutcome {
  /** Raw events deleted. Kept as the headline number every caller already reads. */
  readonly deleted: number;
  /** Attention spans deleted, counted separately so a silent zero is visible. */
  readonly spansDeleted: number;
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
  if (settings.rawRetentionDays <= 0) return { deleted: 0, spansDeleted: 0, cutoff: null };

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

  // Separate transaction, deliberately: a failure deleting spans must not roll back the
  // event deletion and leave retention silently doing nothing on every future run.
  const spansDeleted = await deleteSpansBefore(cutoff);

  return { deleted, spansDeleted, cutoff };
}
