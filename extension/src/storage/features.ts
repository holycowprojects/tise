/**
 * Derived feature rows. The half of storage that **outlives raw events**.
 *
 * D11: raw events expire after the retention window, feature rows do not. That asymmetry
 * is the whole privacy design — a person keeps the model that was learned from their
 * browsing without keeping a record of the browsing itself. `retention.ts` therefore
 * touches the `events` store and nothing else, and a test asserts it.
 *
 * Deletion is different from retention. "Delete everything" clears this store too:
 * retention is a promise about how long raw browsing is kept, deletion is a promise about
 * everything.
 */
import type { FeatureRow } from "../features/vector";
import { openTiseDb } from "./db";

/**
 * Write rows, replacing any with the same (featureSet, subject, windowEnd).
 *
 * Recomputation is therefore idempotent, which matters because training is chunked and
 * resumable (T11) and will recompute a window it has already seen after an interruption.
 */
export async function putFeatureRows(rows: readonly FeatureRow[]): Promise<void> {
  if (rows.length === 0) return;
  const db = await openTiseDb();
  const tx = db.transaction("features", "readwrite");
  await Promise.all([...rows.map((row) => tx.store.put(row)), tx.done]);
}

export async function countFeatureRows(): Promise<number> {
  const db = await openTiseDb();
  return db.count("features");
}

/** Every row, oldest window first. */
export async function allFeatureRows(): Promise<FeatureRow[]> {
  const db = await openTiseDb();
  return db.getAllFromIndex("features", "windowEnd");
}

/** Rows for one subject, oldest first. What the trainer reads per category. */
export async function featureRowsFor(subject: string): Promise<FeatureRow[]> {
  const db = await openTiseDb();
  const rows = await db.getAllFromIndex("features", "subject", subject);
  return rows.sort((a, b) => Date.parse(a.windowEnd) - Date.parse(b.windowEnd));
}
