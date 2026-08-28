/**
 * Carrying stored feature rows across a feature-set change (D83).
 *
 * The thing that must not happen is a *silent* partial migration: training filters to the
 * current feature set, so any row left behind simply stops existing as far as the model is
 * concerned, and the model restarts from whatever the retention window still holds. D11
 * promises the opposite — derived rows outlive raw events — so this is the code that keeps
 * that promise across a version bump.
 *
 * The central test is not that the arithmetic runs. It is that a migrated row is
 * **identical** to the row `computeFeatures` would have written, because anything less
 * means the model is trained on two subtly different definitions of the same feature.
 */
import "fake-indexeddb/auto";
import { IDBFactory } from "fake-indexeddb";
import { beforeEach, describe, expect, it } from "vitest";
import { return24hLabels } from "../src/features/labels";
import { priorSessionCount } from "../src/features/priors";
import { hoursSinceFirstSeen } from "../src/features/recency";
import { computeFeatures, FEATURE_SET, type FeatureRow } from "../src/features/vector";
import { migrateFeatureRows, migrateRow, MIGRATES_FROM } from "../src/model/migrate";
import { refreshDataset } from "../src/model/train";
import { allFeatureRows, putFeatureRows } from "../src/storage/features";
import { closeTiseDb } from "../src/storage/db";
import type { TiseEvent } from "../src/types";

const TIMEOUT = 1800;
const HORIZON = 24;
const OPTIONS = { timeoutSeconds: TIMEOUT, horizonHours: HORIZON };
const START = Date.parse("2026-06-01T09:00:00.000Z");
const HOUR = 3_600_000;

function event(category: string, at: number, id: string): TiseEvent {
  return {
    eventId: id,
    occurredAt: new Date(at).toISOString(),
    source: "import",
    domain: "example.com",
    category,
    transition: "link",
    dwellSeconds: null,
    sessionId: `s-${id}`,
  };
}

/** Browsing spread over a fortnight, so the categories have real ages and priors. */
function corpus(): TiseEvent[] {
  const events: TiseEvent[] = [];
  for (let day = 0; day < 14; day += 1) {
    events.push(event("video", START + day * 24 * HOUR, `v${day}`));
    if (day % 2 === 0) {
      events.push(event("video", START + day * 24 * HOUR + 2 * HOUR, `w${day}`));
      events.push(event("dev", START + day * 24 * HOUR + 3 * HOUR, `d${day}`));
    }
  }
  return events;
}

/**
 * The `fs_2` row for a label, built from the same feature functions `fs_2` used.
 *
 * `hoursSinceFirstSeen` and `priorSessionCount` are still exported — they stopped being
 * *features*, not functions — so this is a genuine old row rather than a hand-written
 * approximation of one.
 */
function fs2Row(events: readonly TiseEvent[], subject: string, windowEnd: number): FeatureRow {
  const current = computeFeatures(events, subject, windowEnd, OPTIONS);
  const values: Record<string, number | null> = { ...current.values };
  delete values.firstSeenSaturation;
  delete values.priorSessionRate;
  values.hoursSinceFirstSeen = hoursSinceFirstSeen(events, subject, windowEnd);
  values.priorSessionCount = priorSessionCount(
    events,
    subject,
    windowEnd,
    TIMEOUT,
    HORIZON,
  );
  return {
    subject: current.subject,
    windowEnd: current.windowEnd,
    featureSet: MIGRATES_FROM,
    compat: "history",
    values: values as FeatureRow["values"],
  };
}

function oldRows(): FeatureRow[] {
  const events = corpus();
  return return24hLabels(events, TIMEOUT, HORIZON).map((label) =>
    fs2Row(events, label.subject, Date.parse(label.windowEnd)),
  );
}

beforeEach(async () => {
  await closeTiseDb();
  globalThis.indexedDB = new IDBFactory();
});

describe("migrating a row", () => {
  it("produces exactly what computeFeatures would have written", () => {
    const events = corpus();
    const labels = return24hLabels(events, TIMEOUT, HORIZON);
    expect(labels.length).toBeGreaterThan(5);

    for (const label of labels) {
      const windowEnd = Date.parse(label.windowEnd);
      const migrated = migrateRow(fs2Row(events, label.subject, windowEnd));
      const direct = computeFeatures(events, label.subject, windowEnd, OPTIONS);
      expect(migrated).not.toBeNull();
      expect(migrated?.values).toEqual(direct.values);
    }
  });

  it("keeps the key, so a migrated row lands where a recomputed one would", () => {
    const [first] = oldRows();
    const migrated = migrateRow(first as FeatureRow);
    expect(migrated?.subject).toBe(first?.subject);
    expect(migrated?.windowEnd).toBe(first?.windowEnd);
    expect(migrated?.featureSet).toBe(FEATURE_SET);
  });

  it("drops the replaced features rather than carrying them along", () => {
    const migrated = migrateRow(oldRows()[0] as FeatureRow);
    expect(migrated?.values).not.toHaveProperty("hoursSinceFirstSeen");
    expect(migrated?.values).not.toHaveProperty("priorSessionCount");
  });

  it("refuses a row it cannot convert instead of inventing a zero", () => {
    // A fabricated feature is worse than a dropped row: afterwards it is indistinguishable
    // from a measured one.
    const broken = oldRows()[0] as FeatureRow;
    const values = { ...broken.values } as Record<string, number | null>;
    values.priorSessionCount = null;
    expect(migrateRow({ ...broken, values: values as FeatureRow["values"] })).toBeNull();
  });

  it("carries a never-seen category through as still never seen", () => {
    const row = oldRows()[0] as FeatureRow;
    const values = { ...row.values } as Record<string, number | null>;
    values.hoursSinceFirstSeen = null;
    values.priorSessionCount = 0;
    const migrated = migrateRow({ ...row, values: values as FeatureRow["values"] });
    expect(migrated?.values.firstSeenSaturation).toBeNull();
    expect(migrated?.values.priorSessionRate).toBe(0);
  });
});

describe("migrating the store", () => {
  it("carries every convertible row forward", async () => {
    const rows = oldRows();
    await putFeatureRows(rows);

    const result = await migrateFeatureRows();
    expect(result.found).toBe(rows.length);
    expect(result.migrated).toBe(rows.length);
    expect(result.skipped).toBe(0);

    const stored = await allFeatureRows();
    const migrated = stored.filter((row) => row.featureSet === FEATURE_SET);
    expect(migrated).toHaveLength(rows.length);
  });

  it("leaves the old rows in place", async () => {
    // They are the only record of what the previous model was trained on, and deleting
    // them would make the migration irreversible for no gain.
    const rows = oldRows();
    await putFeatureRows(rows);
    await migrateFeatureRows();

    const stored = await allFeatureRows();
    expect(stored.filter((row) => row.featureSet === MIGRATES_FROM)).toHaveLength(
      rows.length,
    );
  });

  it("is idempotent", async () => {
    await putFeatureRows(oldRows());
    await migrateFeatureRows();
    const afterFirst = await allFeatureRows();

    const second = await migrateFeatureRows();
    expect(second.migrated).toBe(0);
    expect(await allFeatureRows()).toEqual(afterFirst);
  });

  it("does not overwrite a row the current version already computed", async () => {
    // A recomputed row is authoritative: it was built from events, not from arithmetic on
    // an older row. Migration must never quietly replace one.
    const events = corpus();
    const label = return24hLabels(events, TIMEOUT, HORIZON)[0];
    const windowEnd = Date.parse((label as { windowEnd: string }).windowEnd);
    const subject = (label as { subject: string }).subject;

    const fresh = computeFeatures(events, subject, windowEnd, OPTIONS);
    const stale = fs2Row(events, subject, windowEnd);
    const staleValues = { ...stale.values } as Record<string, number | null>;
    staleValues.priorSessionCount = 999;

    await putFeatureRows([fresh, { ...stale, values: staleValues as FeatureRow["values"] }]);
    await migrateFeatureRows();

    const stored = await allFeatureRows();
    const current = stored.filter(
      (row) => row.featureSet === FEATURE_SET && row.windowEnd === fresh.windowEnd,
    );
    expect(current).toHaveLength(1);
    expect(current[0]?.values).toEqual(fresh.values);
  });

  it("runs from refreshDataset, which is the only path into the dataset", async () => {
    // Hooking the two callers instead would mean remembering at every future call site,
    // and the failure would be silent: training would quietly see only the rows young
    // enough to recompute. Removing the call failed zero tests before this one existed.
    await putFeatureRows(oldRows());
    const result = await refreshDataset(OPTIONS);
    expect(result.migrated).toBeGreaterThan(0);

    const stored = await allFeatureRows();
    expect(stored.some((row) => row.featureSet === FEATURE_SET)).toBe(true);
  });

  it("migrates even with no events left at all, which is the whole point", async () => {
    // D11: derived rows outlive raw events. If migration needed events it would only ever
    // carry forward the rows that did not need carrying.
    await putFeatureRows(oldRows());
    const result = await refreshDataset(OPTIONS);
    expect(result).toMatchObject({ rows: 0, labels: 0 });
    expect(result.migrated).toBe(oldRows().length);
  });

  it("does nothing when there is nothing to migrate", async () => {
    expect(await migrateFeatureRows()).toEqual({ found: 0, migrated: 0, skipped: 0 });
  });

  it("reports rows it could not convert rather than swallowing them", async () => {
    const rows = oldRows();
    const broken = rows[0] as FeatureRow;
    const values = { ...broken.values } as Record<string, number | null>;
    values.priorSessionCount = null;
    await putFeatureRows([{ ...broken, values: values as FeatureRow["values"] }]);

    const result = await migrateFeatureRows();
    expect(result.found).toBe(1);
    expect(result.migrated).toBe(0);
    expect(result.skipped).toBe(1);
  });
});
