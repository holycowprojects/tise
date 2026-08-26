/**
 * The IndexedDB handle. Three stores: `events`, `meta` and `features`.
 *
 * IndexedDB needs **no** `storage` permission — observed at T5, in all five variants.
 * That matters more than convenience: every setting and every cursor Tise keeps lives
 * here rather than in `chrome.storage.local`, so the manifest stays at exactly the
 * permissions D31 justified and not one more.
 *
 * `meta` is a plain key/value store. Retention touches `events` only, which is why
 * settings, the session cursor and — from version 2 — the derived feature rows are kept
 * in stores it cannot reach. **Feature rows outlive raw events by design** (D11): a
 * person keeps what was learned from their browsing without keeping a record of the
 * browsing itself.
 */
import { openDB, type DBSchema, type IDBPDatabase } from "idb";
import type { FeatureRow } from "../features/vector";
import type { TiseEvent } from "../types";

export const DB_NAME = "tise";

/** 2 added the `features` store. Upgrades are additive; nothing is ever dropped here. */
export const DB_VERSION = 2;

export interface TiseDB extends DBSchema {
  events: {
    key: string;
    value: TiseEvent;
    indexes: {
      occurredAt: string;
      category: string;
      sessionId: string;
    };
  };
  meta: {
    key: string;
    value: unknown;
  };
  /**
   * Keyed on (featureSet, subject, windowEnd), so recomputing a row replaces it rather
   * than duplicating it, and rows from two feature-set versions can coexist while a
   * migration is in flight.
   */
  features: {
    key: [string, string, string];
    value: FeatureRow;
    indexes: { windowEnd: string; subject: string };
  };
}

let handle: Promise<IDBPDatabase<TiseDB>> | null = null;

export function openTiseDb(): Promise<IDBPDatabase<TiseDB>> {
  handle ??= openDB<TiseDB>(DB_NAME, DB_VERSION, {
    upgrade(db) {
      if (!db.objectStoreNames.contains("events")) {
        const events = db.createObjectStore("events", { keyPath: "eventId" });
        events.createIndex("occurredAt", "occurredAt");
        events.createIndex("category", "category");
        events.createIndex("sessionId", "sessionId");
      }
      if (!db.objectStoreNames.contains("meta")) {
        db.createObjectStore("meta");
      }
      if (!db.objectStoreNames.contains("features")) {
        const features = db.createObjectStore("features", {
          keyPath: ["featureSet", "subject", "windowEnd"],
        });
        features.createIndex("windowEnd", "windowEnd");
        features.createIndex("subject", "subject");
      }
    },
  });
  return handle;
}

/** Drop the cached handle. Used between tests; harmless in production. */
export async function closeTiseDb(): Promise<void> {
  if (handle === null) return;
  const db = await handle;
  handle = null;
  db.close();
}

export async function readMeta<T>(key: string): Promise<T | undefined> {
  const db = await openTiseDb();
  return (await db.get("meta", key)) as T | undefined;
}

export async function writeMeta(key: string, value: unknown): Promise<void> {
  const db = await openTiseDb();
  await db.put("meta", value, key);
}

export async function deleteMeta(key: string): Promise<void> {
  const db = await openTiseDb();
  await db.delete("meta", key);
}
