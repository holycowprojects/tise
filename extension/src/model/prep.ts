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
import { FEATURE_NAMES, type FeatureName, type FeatureRow } from "../features/vector";

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

export const MISSING_SUFFIX = "__missing";

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
export function rawRow(row: FeatureRow): SplitRow {
  const values: (number | null)[] = [];
  for (const name of FEATURE_NAMES) {
    if (!(name in row.values)) {
      throw new Error(`feature row is missing ${name}`);
    }
    const value = row.values[name];
    if (value === null && !(NULLABLE_FEATURES as readonly string[]).includes(name)) {
      throw new Error(
        `${name} is null, and it is not declared nullable. Either the feature changed ` +
          "meaning or a bug produced it; imputing it would hide both.",
      );
    }
    values.push(value);
  }
  const indicators = NULLABLE_FEATURES.map((name) => (row.values[name] === null ? 1 : 0));
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
      columns: DESIGN_COLUMNS,
      fills: FEATURE_NAMES.map(() => 0),
      means: DESIGN_COLUMNS.map(() => 0),
      scales: DESIGN_COLUMNS.map(() => 1),
    };
  }

  const split = rows.map(rawRow);

  const fills: number[] = [];
  for (let index = 0; index < FEATURE_NAMES.length; index += 1) {
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
  for (let index = 0; index < DESIGN_COLUMNS.length; index += 1) {
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

  return { columns: DESIGN_COLUMNS, fills, means, scales };
}

/** One row, imputed and standardised, ready to be multiplied by a weight vector. */
export function transform(preprocessor: Preprocessor, row: FeatureRow): number[] {
  const { values, indicators } = rawRow(row);
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
