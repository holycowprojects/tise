/**
 * Writing and reading events.
 *
 * Every write goes through `assertStorable`, so the privacy invariant is enforced at
 * runtime and not only in the test suite. A guard that exists only in tests protects the
 * tests; this one protects the user.
 */
import { assertStorable, type TiseEvent } from "../types";
import { openTiseDb } from "./db";

export async function putEvent(event: TiseEvent): Promise<void> {
  assertStorable(event);
  const db = await openTiseDb();
  await db.put("events", event);
}

/**
 * Write many events in one transaction. The import's path.
 *
 * Every event is validated *before* the transaction opens, so a bad row aborts the batch
 * instead of leaving half of it committed.
 */
export async function putEvents(events: readonly TiseEvent[]): Promise<void> {
  for (const event of events) assertStorable(event);
  if (events.length === 0) return;

  const db = await openTiseDb();
  const tx = db.transaction("events", "readwrite");
  await Promise.all([...events.map((event) => tx.store.put(event)), tx.done]);
}

export async function countEvents(): Promise<number> {
  const db = await openTiseDb();
  return db.count("events");
}

/** Every event, oldest first. Fine at V1 scale; T8's export is the streaming path. */
export async function allEvents(): Promise<TiseEvent[]> {
  const db = await openTiseDb();
  return db.getAllFromIndex("events", "occurredAt");
}

/** The most recent `limit` events, newest first. The popup's only read. */
export async function recentEvents(limit: number): Promise<TiseEvent[]> {
  const db = await openTiseDb();
  const out: TiseEvent[] = [];
  let cursor = await db
    .transaction("events")
    .store.index("occurredAt")
    .openCursor(null, "prev");
  while (cursor && out.length < limit) {
    out.push(cursor.value);
    cursor = await cursor.continue();
  }
  return out;
}

/**
 * When live collection first observed something, or `null` if it never has.
 *
 * The import uses this to stop where live collection starts. Walks the `occurredAt`
 * index in order and returns at the first live row, so it costs a scan of the imported
 * prefix once per import and nothing at all afterwards.
 */
/**
 * The oldest event still stored, of any source. `null` when nothing is stored.
 *
 * Distinct from `earliestLiveEventAt`, which answers a different question for the import.
 * This one answers "how far back does the evidence go" — which is what tells the resolver
 * whether retention removed a prediction window before anyone looked at it. Confusing the
 * two would let an import-only profile resolve everything to `expired`.
 */
export async function earliestEventAt(): Promise<string | null> {
  const db = await openTiseDb();
  const cursor = await db.transaction("events").store.index("occurredAt").openCursor();
  return cursor === null ? null : cursor.value.occurredAt;
}

export async function earliestLiveEventAt(): Promise<string | null> {
  const db = await openTiseDb();
  let cursor = await db.transaction("events").store.index("occurredAt").openCursor();
  while (cursor) {
    if (cursor.value.source === "live") return cursor.value.occurredAt;
    cursor = await cursor.continue();
  }
  return null;
}

/** Counts by category, for the popup. Aggregate only — no domains leave storage. */
export async function countsByCategory(): Promise<Map<string, number>> {
  const counts = new Map<string, number>();
  for (const event of await allEvents()) {
    counts.set(event.category, (counts.get(event.category) ?? 0) + 1);
  }
  return counts;
}

/** Delete every event. T8 makes this reachable from the UI and tests it properly. */
export async function clearEvents(): Promise<void> {
  const db = await openTiseDb();
  await db.clear("events");
}
