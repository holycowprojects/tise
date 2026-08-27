"""Imputation and standardisation — the two places a leak can enter without a trace.

`extension/tests/model.test.ts` holds the mirrors. Parity proves the two agree; these
prove the Python side is right in the first place.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from tise_research.features.vector import FEATURE_NAMES, FeatureRow
from tise_research.models.prep import (
    MISSING_SUFFIX,
    NULLABLE_FEATURES,
    design_columns,
    fit_preprocessor,
    raw_row,
)

WINDOW_END = datetime(2026, 6, 1, tzinfo=UTC)


def row(**overrides: float | None) -> FeatureRow:
    """A feature row with every value at 1.0 unless named."""
    values: dict[str, float | None] = dict.fromkeys(FEATURE_NAMES, 1.0)
    values.update(overrides)
    return FeatureRow(
        subject="video",
        window_end=WINDOW_END,
        feature_set="fs_2",
        compat="history",
        values=values,
    )


class TestDesignColumns:
    def test_features_first_then_indicators_in_declared_order(self) -> None:
        columns = design_columns()
        assert columns[: len(FEATURE_NAMES)] == FEATURE_NAMES
        assert columns[len(FEATURE_NAMES) :] == tuple(
            name + MISSING_SUFFIX for name in NULLABLE_FEATURES
        )

    def test_one_indicator_per_nullable_feature_and_no_others(self) -> None:
        assert len(design_columns()) == len(FEATURE_NAMES) + len(NULLABLE_FEATURES)
        assert set(NULLABLE_FEATURES) <= set(FEATURE_NAMES)


class TestRawRow:
    def test_a_null_in_a_non_nullable_feature_raises_rather_than_being_filled(
        self,
    ) -> None:
        """Silently imputing it would hide either a bug or a changed feature."""
        with pytest.raises(ValueError, match="not declared nullable"):
            raw_row(row(eventCount7d=None))

    def test_indicators_record_which_values_were_absent(self) -> None:
        values, indicators = raw_row(row(priorReturnRate=None))
        assert values[FEATURE_NAMES.index("priorReturnRate")] is None
        expected = [
            1.0 if name == "priorReturnRate" else 0.0 for name in NULLABLE_FEATURES
        ]
        assert indicators == expected


class TestFitting:
    def test_fills_are_the_mean_of_observed_values_only(self) -> None:
        rows = [row(priorReturnRate=None), row(priorReturnRate=0.4), row(priorReturnRate=0.6)]
        fitted = fit_preprocessor(rows)
        assert fitted.fills[FEATURE_NAMES.index("priorReturnRate")] == pytest.approx(0.5)

    def test_a_column_with_no_variation_becomes_zeros_rather_than_dividing_by_zero(
        self,
    ) -> None:
        """It carries no information, and the model must not be able to fit it."""
        rows = [row(), row(), row()]
        fitted = fit_preprocessor(rows)
        assert all(scale == 1.0 for scale in fitted.scales)
        assert fitted.matrix(rows) == [[0.0] * len(design_columns())] * 3

    def test_a_column_that_is_null_everywhere_gets_a_declared_fill_not_a_guess(
        self,
    ) -> None:
        rows = [row(priorReturnRate=None), row(priorReturnRate=None)]
        fitted = fit_preprocessor(rows)
        assert fitted.fills[FEATURE_NAMES.index("priorReturnRate")] == 0.0
        # And the indicator records that every value in the column was filled.
        index = design_columns().index("priorReturnRate" + MISSING_SUFFIX)
        assert all(candidate[index] == 0.0 for candidate in fitted.matrix(rows))

    def test_standardisation_uses_the_population_deviation(self) -> None:
        """n, not n-1. Declared, because the mirror has to make the same choice."""
        rows = [row(eventCount7d=0.0), row(eventCount7d=2.0)]
        fitted = fit_preprocessor(rows)
        index = FEATURE_NAMES.index("eventCount7d")
        assert fitted.means[index] == pytest.approx(1.0)
        assert fitted.scales[index] == pytest.approx(1.0)  # n-1 would give sqrt(2)

    def test_an_empty_training_window_gives_the_identity_transform(self) -> None:
        """A new profile has no history. That is normal, not an error.

        Zero means and unit scales, so rows pass through unchanged. Numerically it does
        not matter — an untrained model has zero weights and predicts 0.5 whatever the
        columns hold — but it is a contract the mirror has to match, so it is asserted
        rather than left to whichever default each language happened to reach.
        """
        fitted = fit_preprocessor([])
        assert fitted.means == tuple(0.0 for _ in design_columns())
        assert fitted.scales == tuple(1.0 for _ in design_columns())
        assert fitted.transform(row()) == [1.0] * len(FEATURE_NAMES) + [0.0] * len(
            NULLABLE_FEATURES
        )


class TestLeakage:
    def test_scales_come_from_the_training_window_and_are_reapplied_unchanged(
        self,
    ) -> None:
        """Refitting over train and test together is the textbook leak, and it does not
        look like one — it looks like a slightly better score."""
        train = [row(eventCount7d=0.0), row(eventCount7d=2.0)]
        fitted = fit_preprocessor(train)
        index = FEATURE_NAMES.index("eventCount7d")

        # A test row far outside the training range must be scaled by the *training*
        # deviation, which puts it far from zero rather than pulling it back in.
        transformed = fitted.transform(row(eventCount7d=100.0))
        assert transformed[index] == pytest.approx(99.0)

    def test_transform_never_reads_another_row(self) -> None:
        rows = [row(eventCount7d=0.0), row(eventCount7d=2.0)]
        fitted = fit_preprocessor(rows)
        alone = fitted.transform(rows[0])
        together = fitted.matrix(rows)[0]
        assert alone == together
