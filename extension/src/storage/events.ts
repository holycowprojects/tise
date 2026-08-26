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
