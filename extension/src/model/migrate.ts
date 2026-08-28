/**
 * Carry stored feature rows forward when the feature set changes.
 *
 * **Why this has to exist.** D11 is the promise that derived rows outlive raw events: a
 * person keeps the model learned from their browsing without keeping the browsing.
 * `refreshDataset` can only recompute rows for events that still exist, so on a feature-set
 * change every row older than the retention window would be stranded in the old set and
 * silently dropped from training. The model would restart from the last thirty days, and
 * nothing would report that it had.
 *
 * **Why it can exist.** `fs_3`'s two new features are pure arithmetic transforms of values
 * `fs_2` already stored (D81/D82):
 *
 *     firstSeenSaturation = h / (h + 168)          from hoursSinceFirstSeen
 *     priorSessionRate    = r / (r + 1),           from priorSessionCount and
 *                           r = count / max(h/24, 1)     hoursSinceFirstSeen
 *
 * So the migration needs no events at all, and produces rows identical to what
 * `computeFeatures` would have written at the time. That was a design choice made for
 * simplicity in D81 and it is what makes this lossless.
 *
 * **This is not a general mechanism.** It works because these particular features are
 * derivable from stored ones. A future feature set that needs anything not already in the
 * row cannot be migrated this way, and the honest options there are to recompute what is
 * recoverable and say plainly what was lost. See D83.
 */
import {
  FEATURE_SET,
  FIRST_SEEN_SCALE_HOURS,
  PRIOR_SESSION_RATE_SCALE,
  firstSeenSaturation,
  priorSessionRate,
  type FeatureRow,
} from "../features/vector";
import { allFeatureRows, putFeatureRows } from "../storage/features";

/** The set this migration reads from. Rows in any other old set are left alone. */
export const MIGRATES_FROM = "fs_2";

export interface MigrationResult {
  /** Rows found in the old set. */
  readonly found: number;
  /** Rows written in the new set. */
  readonly migrated: number;
  /**
   * Rows that could not be carried forward. Reported rather than swallowed: a silent
   * partial migration is a model quietly trained on less than it says.
   */
  readonly skipped: number;
}

/**
 * Convert one `fs_2` row to `fs_3`, or null if it cannot be converted.
 *
 * Pure — no storage, no clock. The `windowEnd` and `subject` are carried unchanged, so the
 * migrated row lands on the same key it would have had if it were computed today.
 */
export function migrateRow(row: FeatureRow): FeatureRow | null {
  const values = row.values as Readonly<Record<string, number | null>>;
  const hoursFirst = values.hoursSinceFirstSeen;
  const priorSessions = values.priorSessionCount;

  // `hoursSinceFirstSeen` is nullable and `priorSessionCount` is not, so a null count is a
  // row that was not written by any version of `computeFeatures`. Refuse it rather than
  // invent a zero: a fabricated feature is worse than a dropped row, because it is
  // indistinguishable from a measured one afterwards.
  if (priorSessions === null || priorSessions === undefined) return null;
  if (hoursFirst === undefined) return null;

  const carried: Record<string, number | null> = {};
  for (const [name, value] of Object.entries(values)) {
    if (name === "hoursSinceFirstSeen" || name === "priorSessionCount") continue;
    carried[name] = value;
  }
  carried.firstSeenSaturation = firstSeenSaturation(hoursFirst);
  carried.priorSessionRate = priorSessionRate(priorSessions, hoursFirst);

  return {
    subject: row.subject,
    windowEnd: row.windowEnd,
    featureSet: FEATURE_SET,
    compat: row.compat,
    values: carried as FeatureRow["values"],
  };
}

/**
 * Migrate every stored `fs_2` row to the current set.
 *
 * Idempotent: the store replaces on `(featureSet, subject, windowEnd)`, and a second run
 * finds the same old rows and rewrites the same new ones. The old rows are **left in
 * place** — they are the only record of what the previous model was trained on, they cost
 * little, and deleting them would make this migration irreversible for no gain.
 */
export async function migrateFeatureRows(): Promise<MigrationResult> {
  const rows = await allFeatureRows();
  const old = rows.filter((row) => row.featureSet === MIGRATES_FROM);
  if (old.length === 0) return { found: 0, migrated: 0, skipped: 0 };

  const existing = new Set(
    rows
      .filter((row) => row.featureSet === FEATURE_SET)
      .map((row) => `${row.subject} ${row.windowEnd}`),
  );

  const migrated: FeatureRow[] = [];
  let skipped = 0;
  for (const row of old) {
    if (existing.has(`${row.subject} ${row.windowEnd}`)) continue;
    const next = migrateRow(row);
    if (next === null) {
      skipped += 1;
      continue;
    }
    migrated.push(next);
  }

  await putFeatureRows(migrated);
  return { found: old.length, migrated: migrated.length, skipped };
}

// Re-exported so a caller checking the arithmetic does not have to import two modules.
export { FIRST_SEEN_SCALE_HOURS, PRIOR_SESSION_RATE_SCALE };
