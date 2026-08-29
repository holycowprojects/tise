/**
 * Turn feature rows into a numeric matrix, without inventing anything.
 *
 * PARITY-CRITICAL: `research/tise_research/models/prep.py` is the mirror. Both must
 * produce identical matrices from identical rows, and the parity suite asserts it.
 *
 * Two problems stand between a `FeatureRow` and a logistic regression, and the
 * interesting part of this module is that neither has a neutral answer.
 *
 * **Nulls.** D51 said absence is `null` and never a sentinel, precisely so nothing
 * downstream fits a coefficient to a number that was never measured. A linear model
 * cannot consume `null`, so something must be put there — and whatever is put there is
 * exactly the invented number D51 forbade. The resolution is to fill with the training
 * mean *and* add a column recording that the fill happened, so the model can learn what
 * absence is worth instead of being told it is worth the average. Four of the fourteen
 * features are nullable, so the design matrix has eighteen columns.
 *
 * `priorReturnRate__missing` is very nearly `priorSessionCount === 0` restated, so two of
 * those eighteen columns are close to collinear. That is a real redundancy; L2 absorbs it
 * and it is recorded here rather than tidied away, because the alternative — dropping the
 * indicator on the grounds that another column implies it — would be reasoning about the
 * data rather than measuring it.
 *
 * **Scale.** `hoursSinceFirstSeen` runs into the hundreds while `dayOfWeek` runs 0 to 6.
 * Gradient descent on unscaled columns takes a step that is far too large for one and far
 * too small for the other, so every column is standardised. The means and deviations are
 * **part of the fitted model**: computed on the training window only, frozen, and
 * reapplied unchanged at prediction time. Recomputing them over train and test together
 * is the textbook leak, and it does not look like one — it looks like a slightly better
 * score.
 */
import {
  FEATURE_NAMES,
  FEATURE_SET,
  featureNames,
  type FeatureName,
  type FeatureRow,
} from "../features/vector";

/**
 * The features `computeFeatures` can legitimately return `null` for. Anything not listed
 * here is `null` only if something is wrong, and `rawRow` throws rather than silently
 * imputing it.
 */
export const NULLABLE_FEATURES = [
  "hoursSinceLastSeen",
  "firstSeenSaturation",
  "categoryShare30d",
  "priorReturnRate",
] as const satisfies readonly FeatureName[];

/**
 * Per feature set, mirroring Python's `NULLABLE_BY_SET`.
 *
 * `as_2` has exactly two legitimate absences, and both are absences of a *different*
 * history than the minimum-prior rule guarantees. That rule is about the category; these
 * are about the domain and about the preceding visit.
 *
 * * `domainDwellLevel` — this domain has been visited before but never with a recorded
 *   duration, so there is no median to take. Filling it with zero would say the person
 *   leaves this domain instantly, which is the opposite of unknown.
 * * `prevDwellRatio` — the immediately preceding visit has no recorded duration. The
 *   previous visit is *not* skipped over to find one that does: "the visit before this one"
 *   is the feature, and substituting an earlier visit would quietly change its meaning
 *   while keeping its name.
 *
 * The other sixteen are measured zeros. A domain seen zero times has been seen zero times,
 * and an indicator column would claim the count was never taken.
 */
export const NULLABLE_BY_SET: Readonly<Record<string, readonly string[]>> = {
  fs_3: NULLABLE_FEATURES,
  as_2: ["domainDwellLevel", "prevDwellRatio"],
};

export function nullableFeatures(featureSet: string): readonly string[] {
  const names = NULLABLE_BY_SET[featureSet];
  if (!names) {
    throw new Error(`no nullable list declared for ${featureSet}`);
  }
  return names;
}

export const MISSING_SUFFIX = "__missing";

/**
 * Column order of the design matrix for any feature set. Features in set order, then one
 * indicator per nullable feature. Mirrors Python's `design_columns`.
 */
export function designColumns(featureSet: string): readonly string[] {
  return [
    ...featureNames(featureSet),
    ...nullableFeatures(featureSet).map((name) => name + MISSING_SUFFIX),
  ];
}

/**
 * Column order of the design matrix. The order is the contract, as in `vector.ts`.
 * Features first in `FEATURE_NAMES` order, then one indicator per nullable feature in
 * `NULLABLE_FEATURES` order. A silent reordering here would swap two coefficients and
 * nothing else would notice.
 */
export const DESIGN_COLUMNS: readonly string[] = [
  ...FEATURE_NAMES,
  ...NULLABLE_FEATURES.map((name) => name + MISSING_SUFFIX),
];

/**
 * Used when a column is entirely absent in the training window. There is no mean to fall
 * back on, so the fill is declared rather than derived — and the indicator column makes
 * it visible that every value in that column was filled.
 */
const NO_OBSERVATIONS_FILL = 0;

export interface Preprocessor {
  /** Which feature set these fills and scales were fitted on. Part of the model. */
  readonly featureSet: string;
  readonly columns: readonly string[];
  /** Training means of the observed values, in `FEATURE_NAMES` order. */
  readonly fills: readonly number[];
  /** Over all eighteen design columns. */
  readonly means: readonly number[];
  readonly scales: readonly number[];
}

export interface SplitRow {
  readonly values: readonly (number | null)[];
  readonly indicators: readonly number[];
}

/**
 * One feature row split into (possibly-null values, missingness indicators).
 * Imputation is not applied here: this is the shape before a training window exists.
 */
export function rawRow(row: FeatureRow, featureSet: string = FEATURE_SET): SplitRow {
  const names = featureNames(featureSet);
  const nullable = nullableFeatures(featureSet);

  // The check the type used to make, now made at runtime and made stronger. An *extra*
  // key means the row was built for a different feature set: its values would line up
  // against the wrong column names, every coefficient after the first difference would be
  // applied to the wrong feature, and no score would reveal it. The old signature could
  // not catch this at all, because the widths of two sets can coincide.
  for (const key of Object.keys(row.values)) {
    if (!names.includes(key)) {
      throw new Error(
        `feature row carries ${key}, which is not in ${featureSet}. The row was built ` +
          "for a different feature set and its columns would not line up.",
      );
    }
  }

  const values: (number | null)[] = [];
  for (const name of names) {
    const value = row.values[name];
    if (value === undefined) {
      throw new Error(`feature row is missing ${name}`);
    }
    if (value === null && !nullable.includes(name)) {
      throw new Error(
        `${name} is null, and it is not declared nullable. Either the feature changed ` +
          "meaning or a bug produced it; imputing it would hide both.",
      );
    }
    values.push(value);
  }
  const indicators = nullable.map((name) => (row.values[name] === null ? 1 : 0));
  return { values, indicators };
}

function mean(values: readonly number[]): number {
  if (values.length === 0) return NO_OBSERVATIONS_FILL;
  let total = 0;
  for (const value of values) total += value;
  return total / values.length;
}

/**
 * Fit fills and scales on a training window. Nothing after it may be passed in.
 *
 * A column with no variation gets a scale of 1, which turns it into a column of zeros
 * rather than a division by zero. That is the honest outcome: a column that never varies
 * in training carries no information, and the model should not be able to fit a
 * coefficient to it.
 */
export function fitPreprocessor(rows: readonly FeatureRow[]): Preprocessor {
  if (rows.length === 0) {
    return {
      featureSet: FEATURE_SET,
      columns: DESIGN_COLUMNS,
      fills: FEATURE_NAMES.map(() => 0),
      means: DESIGN_COLUMNS.map(() => 0),
      scales: DESIGN_COLUMNS.map(() => 1),
    };
  }

  // Taken from the rows, never from a module constant: fitting `as_2` rows against `fs_3`
  // columns would build a matrix of the wrong width, and the failure would surface as a
  // coefficient meaning something other than its label. Mirrors Python's `fit_preprocessor`.
  const featureSet = rows[0]?.featureSet ?? FEATURE_SET;
  const mixed = new Set(rows.map((row) => row.featureSet));
  if (mixed.size > 1) {
    throw new Error(
      `refusing to fit across mixed feature sets: ${[...mixed].sort().join(", ")}`,
    );
  }
  const names = featureNames(featureSet);
  const columns = designColumns(featureSet);

  // Not `rows.map(rawRow)`: map passes the array index as the second argument, which would
  // arrive as the feature set. TypeScript caught it the moment the parameter was added.
  const split = rows.map((row) => rawRow(row, featureSet));

  const fills: number[] = [];
  for (let index = 0; index < names.length; index += 1) {
    const observed: number[] = [];
    for (const row of split) {
      const value = row.values[index];
      if (value !== null && value !== undefined) observed.push(value);
    }
    fills.push(mean(observed));
  }

  const filled = split.map((row) => [
    ...row.values.map((value, index) => (value === null ? (fills[index] as number) : value)),
    ...row.indicators,
  ]);

  const means: number[] = [];
  const scales: number[] = [];
  for (let index = 0; index < columns.length; index += 1) {
    let total = 0;
    for (const row of filled) total += row[index] as number;
    const columnMean = total / filled.length;

    // Population deviation, divided by n. Declared rather than defaulted: n and n-1
    // differ, and the mirror has to make the same choice.
    let squared = 0;
    for (const row of filled) squared += ((row[index] as number) - columnMean) ** 2;
    const deviation = Math.sqrt(squared / filled.length);

    means.push(columnMean);
    scales.push(deviation > 0 ? deviation : 1);
  }

  return { featureSet, columns, fills, means, scales };
}

/** One row, imputed and standardised, ready to be multiplied by a weight vector. */
export function transform(preprocessor: Preprocessor, row: FeatureRow): number[] {
  // The widths of two sets can coincide, so a length check would not catch this. Without
  // the name, an `fs_3` row transforms cleanly through an `as_2` preprocessor and every
  // coefficient after the first differing column is applied to the wrong feature, silently.
  if (row.featureSet !== preprocessor.featureSet) {
    throw new Error(
      `row is ${row.featureSet} and this preprocessor was fitted on ` +
        `${preprocessor.featureSet}; nothing downstream would notice.`,
    );
  }
  const { values, indicators } = rawRow(row, preprocessor.featureSet);
  const full = [
    ...values.map((value, index) =>
      value === null ? (preprocessor.fills[index] as number) : value,
    ),
    ...indicators,
  ];
  return full.map(
    (value, index) =>
      (value - (preprocessor.means[index] as number)) /
      (preprocessor.scales[index] as number),
  );
}

export function buildMatrix(
  preprocessor: Preprocessor,
  rows: readonly FeatureRow[],
): number[][] {
  return rows.map((row) => transform(preprocessor, row));
}
