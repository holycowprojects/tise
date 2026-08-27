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

from tise_research.features.vector import FEATURE_NAMES, FeatureRow

__all__ = [
    "DESIGN_COLUMNS",
    "MISSING_SUFFIX",
    "NULLABLE_FEATURES",
    "Preprocessor",
    "design_columns",
    "fit_preprocessor",
    "raw_row",
]

#: The features that `compute_features` can legitimately return `None` for. Anything not
#: listed here is `None` only if something is wrong, and `raw_row` raises rather than
#: silently imputing it.
NULLABLE_FEATURES: tuple[str, ...] = (
    "hoursSinceLastSeen",
    "hoursSinceFirstSeen",
    "categoryShare30d",
    "priorReturnRate",
)

MISSING_SUFFIX = "__missing"


def design_columns() -> tuple[str, ...]:
    """Column order of the design matrix. The order is the contract, as in `vector.py`.

    Features first in `FEATURE_NAMES` order, then one indicator per nullable feature in
    `NULLABLE_FEATURES` order. A silent reordering here would swap two coefficients and
    nothing else would notice.
    """
    return FEATURE_NAMES + tuple(name + MISSING_SUFFIX for name in NULLABLE_FEATURES)


DESIGN_COLUMNS: tuple[str, ...] = design_columns()

#: Used when a column is entirely absent in the training window. There is no mean to fall
#: back on, so the fill is declared rather than derived — and the indicator column makes
#: it visible that every value in that column was filled.
NO_OBSERVATIONS_FILL = 0.0


def raw_row(row: FeatureRow) -> tuple[list[float | None], list[float]]:
    """One feature row split into (possibly-null values, missingness indicators).

    Imputation is not applied here: this is the shape before a training window exists.
    """
    missing = set(FEATURE_NAMES) - set(row.values)
    if missing:
        raise ValueError(f"feature row is missing {sorted(missing)}")

    values: list[float | None] = []
    for name in FEATURE_NAMES:
        value = row.values[name]
        if value is None and name not in NULLABLE_FEATURES:
            raise ValueError(
                f"{name} is None, and it is not declared nullable. Either the feature "
                "changed meaning or a bug produced it; imputing it would hide both."
            )
        values.append(None if value is None else float(value))

    indicators = [
        1.0 if row.values[name] is None else 0.0 for name in NULLABLE_FEATURES
    ]
    return values, indicators


@dataclass(frozen=True, slots=True)
class Preprocessor:
    """Fitted imputation and standardisation. Part of the model, not a pre-step.

    `fills` are the training means of the observed values, in `FEATURE_NAMES` order.
    `means` and `scales` cover all eighteen design columns.
    """

    columns: tuple[str, ...]
    fills: tuple[float, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]

    def transform(self, row: FeatureRow) -> list[float]:
        """One row, imputed and standardised, ready to be multiplied by a weight vector."""
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
    columns = design_columns()
    if not rows:
        zeros = tuple(0.0 for _ in columns)
        ones = tuple(1.0 for _ in columns)
        return Preprocessor(
            columns=columns,
            fills=tuple(0.0 for _ in FEATURE_NAMES),
            means=zeros,
            scales=ones,
        )

    split = [raw_row(row) for row in rows]

    fills: list[float] = []
    for index, _name in enumerate(FEATURE_NAMES):
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
    )
