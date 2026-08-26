/**
 * Deletion, of two different sizes.
 *
 * `clearEvents` removes the record. `deleteEverything` removes the record *and* the fact
 * that Tise was ever allowed to make one — settings, consent, the session cursor, the
 * import progress, the rejection counters. Every store, zero rows.
 *
 * Wiping consent is deliberate, and it is the part people find surprising. "Delete
 * everything" that quietly left behind permission to start again would not be deleting
 * everything; it would be deleting the visible half. After this runs, Tise is in exactly
 * the state it installs in: unable to store anything until asked again.
 */
import { openTiseDb } from "./db";

export interface DeletionOutcome {
  readonly eventsDeleted: number;
  readonly metaKeysDeleted: number;
  readonly featureRowsDeleted: number;
}

export async function deleteEverything(): Promise<DeletionOutcome> {
  const db = await openTiseDb();

  const eventsDeleted = await db.count("events");
  const metaKeysDeleted = await db.count("meta");
  const featureRowsDeleted = await db.count("features");

  // Features survive *retention* (D11) and not deletion. Retention is a promise about
  // how long raw browsing is kept; "delete everything" is a promise about everything.
  const tx = db.transaction(["events", "meta", "features"], "readwrite");
  await Promise.all([
    tx.objectStore("events").clear(),
    tx.objectStore("meta").clear(),
    tx.objectStore("features").clear(),
    tx.done,
  ]);

  return { eventsDeleted, metaKeysDeleted, featureRowsDeleted };
}

/** Every store holds nothing. The assertion behind the delete-all claim. */
export async function isEmpty(): Promise<boolean> {
  const db = await openTiseDb();
  return (
    (await db.count("events")) === 0 &&
    (await db.count("meta")) === 0 &&
    (await db.count("features")) === 0
  );
}
