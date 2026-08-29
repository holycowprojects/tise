"""Turn feature rows into a numeric matrix, without inventing anything.

`extension/src/model/prep.ts` is the mirror. Both must produce identical matrices from
identical rows, and the parity suite asserts it.

Two problems stand between a `FeatureRow` and a logistic regression, and the interesting
part of this module is that neither has a neutral answer.

**Nulls.** D51 said absence is `null` and never a sentinel, precisely so nothing
downstream fits a coefficient to a number that was never measured. A linear model cannot
consume `null`, so something must be put there — and whatever is put there is exactly the
invented number D51 forbade. The resolution is to fill with the training mean *and* add a
column recording that the fill happened, so the model can learn what absence is worth
instead of being told it is worth the average. Four of the fourteen features are
nullable, so the design matrix has eighteen columns.

`priorReturnRate__missing` is very nearly `priorSessionCount == 0` restated, so two of
those eighteen columns are close to collinear. That is a real redundancy; L2 absorbs it
and it is recorded here rather than tidied away, because the alternative — dropping the
indicator on the grounds that another column implies it — would be reasoning about the
data rather than measuring it.

**Scale.** `hoursSinceFirstSeen` runs into the hundreds while `dayOfWeek` runs 0 to 6.
Gradient descent on unscaled columns takes a step that is far too large for one and far
too small for the other, so every column is standardised. The means and deviations are
**part of the fitted model**: computed on the training window only, frozen, and reapplied
unchanged at prediction time. Recomputing them over train and test together is the
textbook leak, and it does not look like one — it looks like a slightly better score.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from tise_research.features.vector import (
    DEFAULT_FEATURE_SET,
    FeatureRow,
    feature_names,
)

__all__ = [
    "DESIGN_COLUMNS",
    "MISSING_SUFFIX",
    "NULLABLE_BY_SET",
    "NULLABLE_FEATURES",
    "nullable_features",
    "Preprocessor",
    "design_columns",
    "fit_preprocessor",
    "raw_row",
]

#: The features that `compute_features` can legitimately return `None` for. Anything not
#: listed here is `None` only if something is wrong, and `raw_row` raises rather than
#: silently imputing it.
#: Per feature set, because `fs_3` replaced one nullable feature and one non-nullable one.
#: `priorSessionRate` is deliberately **not** nullable: with no prior sessions the rate is a
#: measured zero, not an absence, and giving it an indicator column would say otherwise.
NULLABLE_BY_SET: dict[str, tuple[str, ...]] = {
    "fs_2": (
        "hoursSinceLastSeen",
        "hoursSinceFirstSeen",
        "categoryShare30d",
        "priorReturnRate",
    ),
    "fs_3": (
        "hoursSinceLastSeen",
        "firstSeenSaturation",
        "categoryShare30d",
        "priorReturnRate",
    ),
    # `bs_1` has exactly one legitimate absence: a topic that has never been above its own
    # median has no "blocks since it last was". Everything else is computed from a window
    # that is guaranteed non-empty by the minimum-history rule, so a null anywhere else is
    # a bug and `raw_row` raises rather than quietly imputing it.
    "bs_1": ("daysSinceAbove",),
    # `as_1` has no legitimate absence: a visit is only labelled once its category has
    # enough dwell history, so every window is non-empty by construction.
    "as_1": (),
    # `as_2` adds exactly two legitimate absences, and both are absences of a *different*
    # history than the one the minimum-prior rule guarantees. The rule is about the
    # category; these are about the domain and about the preceding visit.
    #
    # * `domainDwellLevel` — this domain has been visited before but never with a recorded
    #   duration, so there is no median to take. Filling it with zero would say the person
    #   leaves this domain instantly, which is the opposite of unknown.
    # * `prevDwellRatio` — the immediately preceding visit has no recorded duration. The
    #   previous visit is not skipped over to find one that does: "the visit before this
    #   one" is the feature, and substituting an earlier visit would quietly change its
    #   meaning while keeping its name.
    #
    # The other four are measured zeros. A domain seen zero times has been seen zero
    # times; an indicator column would claim the count was never taken.
    "as_2": ("domainDwellLevel", "prevDwellRatio"),
    # `as_1n` / `as_2n` drop the arrival flags for a corpus with no transition column (D99).
    # The flags were never nullable, so the nullable lists are unchanged from their parents —
    # written out rather than aliased, because a set that silently shares another set's list
    # is one rename away from being wrong.
    "as_1n": (),
    "as_2n": ("domainDwellLevel", "prevDwellRatio"),
}

NULLABLE_FEATURES: tuple[str, ...] = NULLABLE_BY_SET[DEFAULT_FEATURE_SET]


def nullable_features(feature_set: str) -> tuple[str, ...]:
    try:
        return NULLABLE_BY_SET[feature_set]
    except KeyError:
        raise ValueError(f"no nullable list declared for {feature_set!r}") from None

MISSING_SUFFIX = "__missing"


def design_columns(feature_set: str = DEFAULT_FEATURE_SET) -> tuple[str, ...]:
    """Column order of the design matrix. The order is the contract, as in `vector.py`.

    Features first in feature-set order, then one indicator per nullable feature. A silent
    reordering here would swap two coefficients and nothing else would notice.
    """
    return feature_names(feature_set) + tuple(
        name + MISSING_SUFFIX for name in nullable_features(feature_set)
    )


DESIGN_COLUMNS: tuple[str, ...] = design_columns()

#: Used when a column is entirely absent in the training window. There is no mean to fall
#: back on, so the fill is declared rather than derived — and the indicator column makes
#: it visible that every value in that column was filled.
NO_OBSERVATIONS_FILL = 0.0


def raw_row(row: FeatureRow) -> tuple[list[float | None], list[float]]:
    """One feature row split into (possibly-null values, missingness indicators).

    Imputation is not applied here: this is the shape before a training window exists.
    """
    names = feature_names(row.feature_set)
    nullable = nullable_features(row.feature_set)
    missing = set(names) - set(row.values)
    if missing:
        raise ValueError(f"feature row is missing {sorted(missing)}")

    values: list[float | None] = []
    for name in names:
        value = row.values[name]
        if value is None and name not in nullable:
            raise ValueError(
                f"{name} is None, and it is not declared nullable. Either the feature "
                "changed meaning or a bug produced it; imputing it would hide both."
            )
        values.append(None if value is None else float(value))

    indicators = [1.0 if row.values[name] is None else 0.0 for name in nullable]
    return values, indicators


@dataclass(frozen=True, slots=True)
class Preprocessor:
    """Fitted imputation and standardisation. Part of the model, not a pre-step.

    `fills` are the training means of the observed values, in feature-set order.
    `means` and `scales` cover all eighteen design columns.

    `feature_set` is carried because **the widths do not distinguish the sets**: `fs_2` and
    `fs_3` both produce eighteen columns, so `zip(strict=True)` cannot catch a row from the
    wrong set. Without this check an `fs_2` row transforms cleanly through an `fs_3`
    preprocessor and every coefficient after the first differing column is applied to the
    wrong feature, silently. Found by a test written for D82.
    """

    columns: tuple[str, ...]
    fills: tuple[float, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]
    feature_set: str = DEFAULT_FEATURE_SET

    def transform(self, row: FeatureRow) -> list[float]:
        """One row, imputed and standardised, ready to be multiplied by a weight vector."""
        if row.feature_set != self.feature_set:
            raise ValueError(
                f"row is {row.feature_set} and this preprocessor was fitted on "
                f"{self.feature_set}; the column counts match, so nothing downstream "
                "would notice."
            )
        values, indicators = raw_row(row)
        filled = [
            fill if value is None else value
            for value, fill in zip(values, self.fills, strict=True)
        ]
        full = filled + indicators
        return [
            (value - mean) / scale
            for value, mean, scale in zip(full, self.means, self.scales, strict=True)
        ]

    def matrix(self, rows: Sequence[FeatureRow]) -> list[list[float]]:
        return [self.transform(row) for row in rows]


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else NO_OBSERVATIONS_FILL


def fit_preprocessor(rows: Sequence[FeatureRow]) -> Preprocessor:
    """Fit fills and scales on a training window. Nothing after it may be passed in.

    A column with no variation gets a scale of 1, which turns it into a column of zeros
    rather than a division by zero. That is the honest outcome: a column that never
    varies in training carries no information, and the model should not be able to fit a
    coefficient to it.
    """
    # The feature set comes off the rows, never from a module constant: fitting on `fs_3`
    # rows against `fs_2` columns would build a matrix of the wrong width, and the failure
    # would surface as a coefficient meaning something other than its label.
    feature_set = rows[0].feature_set if rows else DEFAULT_FEATURE_SET
    mixed = {row.feature_set for row in rows}
    if len(mixed) > 1:
        raise ValueError(f"refusing to fit across mixed feature sets: {sorted(mixed)}")

    columns = design_columns(feature_set)
    names = feature_names(feature_set)
    if not rows:
        zeros = tuple(0.0 for _ in columns)
        ones = tuple(1.0 for _ in columns)
        return Preprocessor(
            columns=columns,
            fills=tuple(0.0 for _ in names),
            means=zeros,
            scales=ones,
            feature_set=feature_set,
        )

    split = [raw_row(row) for row in rows]

    fills: list[float] = []
    for index, _name in enumerate(names):
        observed = [values[index] for values, _ in split if values[index] is not None]
        fills.append(_mean(observed))

    filled_matrix: list[list[float]] = []
    for values, indicators in split:
        filled = [
            fill if value is None else value
            for value, fill in zip(values, fills, strict=True)
        ]
        filled_matrix.append(filled + indicators)

    means: list[float] = []
    scales: list[float] = []
    for index in range(len(columns)):
        column = [row[index] for row in filled_matrix]
        mean = sum(column) / len(column)
        # Population deviation, divided by n. Declared rather than defaulted: n and n-1
        # differ, and the mirror has to make the same choice.
        variance = sum((value - mean) ** 2 for value in column) / len(column)
        deviation = math.sqrt(variance)
        means.append(mean)
        scales.append(deviation if deviation > 0.0 else 1.0)

    return Preprocessor(
        columns=columns,
        fills=tuple(fills),
        means=tuple(means),
        scales=tuple(scales),
        feature_set=feature_set,
    )
