/**
 * Stored `return_24h` outcomes. The other half of what outlives raw events.
 *
 * D11 keeps derived data past the retention window so a person keeps the model learned
 * from their browsing without keeping the browsing. A feature row alone cannot retrain
 * anything — it has no answer attached — so labels persist on the same terms, in their
 * own store for the reason `db.ts` gives: a feature vector is final when it is computed,
 * an outcome is provisional until its horizon elapses.
 *
 * `retention.ts` touches `events` and nothing else, and `deleteEverything` clears this
 * store along with the rest. Retention is a promise about how long raw browsing is kept;
 * deletion is a promise about everything.
 */
import type { Label } from "../features/labels";
import { openTiseDb } from "./db";

/**
 * Write labels, replacing any with the same (target, subject, windowEnd).
 *
 * Replacement is the point rather than a convenience: a label written before its horizon
 * elapsed is provisional, and the pass that recomputes it later must overwrite the
 * earlier answer instead of accumulating two.
 */
export async function putLabels(labels: readonly Label[]): Promise<void> {
  if (labels.length === 0) return;
  const db = await openTiseDb();
  const tx = db.transaction("labels", "readwrite");
  await Promise.all([...labels.map((label) => tx.store.put(label)), tx.done]);
}

export async function countLabels(): Promise<number> {
  const db = await openTiseDb();
  return db.count("labels");
}

/** Every label, oldest window first. */
export async function allLabels(): Promise<Label[]> {
  const db = await openTiseDb();
  return db.getAllFromIndex("labels", "windowEnd");
}

export async function clearLabels(): Promise<number> {
  const db = await openTiseDb();
  const count = await db.count("labels");
  await db.clear("labels");
  return count;
}
