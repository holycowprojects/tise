"""Bootstrap intervals on a paired score difference.

The sign convention is the thing most worth guarding: `reference - challenger`, positive
means the challenger is better. Getting it backwards inverts every published conclusion
and no other test in this project would notice.
"""

from __future__ import annotations

import pytest
from tise_research.eval.intervals import (
    BOOTSTRAP_SEED,
    brier_difference,
    brier_difference_interval,
    fold_win_probability,
    rows_to_exclude_zero,
)

# A challenger that is better on average but **not uniformly**, against a flat 0.5.
#
# The unevenness is the point. An earlier version of this fixture used 0.9/0.1 throughout,
# which makes every row's paired difference exactly 0.24 — zero variance, so the bootstrap
# correctly returned a zero-width interval and two tests here failed. A fixture with no
# spread cannot exercise anything that estimates spread.
OUTCOMES = [True, False, True, False, True, False, True, False]
GOOD = [0.90, 0.20, 0.70, 0.10, 0.95, 0.40, 0.60, 0.05]
FLAT = [0.5] * 8
BAD = [0.10, 0.80, 0.30, 0.90, 0.05, 0.60, 0.40, 0.95]

#: Barely better than flat — the shape every real result in this project has so far.
MARGINAL = [0.55, 0.48, 0.52, 0.60, 0.51, 0.44, 0.58, 0.53]


class TestSignConvention:
    def test_a_better_challenger_gives_a_positive_difference(self):
        difference = brier_difference(OUTCOMES, GOOD, FLAT)
        assert difference is not None and difference > 0

    def test_a_worse_challenger_gives_a_negative_difference(self):
        difference = brier_difference(OUTCOMES, BAD, FLAT)
        assert difference is not None and difference < 0

    def test_identical_models_give_exactly_zero(self):
        assert brier_difference(OUTCOMES, FLAT, FLAT) == 0.0

    def test_the_magnitude_is_the_difference_of_brier_scores(self):
        """Cross-checked against `metrics.brier_score`, not just asserted internally."""
        from tise_research.eval.metrics import brier_score

        expected = brier_score(OUTCOMES, FLAT) - brier_score(OUTCOMES, GOOD)
        assert brier_difference(OUTCOMES, GOOD, FLAT) == pytest.approx(expected)

    def test_empty_is_none_not_zero(self):
        """Zero would read as a confident finding of no difference."""
        assert brier_difference([], [], []) is None
        assert brier_difference_interval([], [], []) is None

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="length mismatch"):
            brier_difference(OUTCOMES, GOOD[:4], FLAT)


class TestInterval:
    def test_a_clear_difference_excludes_zero(self):
        interval = brier_difference_interval(
            OUTCOMES * 20, GOOD * 20, FLAT * 20, resamples=2_000
        )
        assert interval is not None
        assert interval.excludes_zero
        assert interval.low > 0

    def test_no_difference_includes_zero(self):
        interval = brier_difference_interval(
            OUTCOMES * 20, FLAT * 20, FLAT * 20, resamples=2_000
        )
        assert interval is not None
        assert not interval.excludes_zero

    def test_the_interval_brackets_the_point_estimate(self):
        interval = brier_difference_interval(
            OUTCOMES * 20, GOOD * 20, FLAT * 20, resamples=2_000
        )
        assert interval is not None
        assert interval.low <= interval.point <= interval.high

    def test_the_same_seed_reproduces_the_same_bounds(self):
        """A published interval has to be regenerable, not merely re-derivable."""
        first = brier_difference_interval(OUTCOMES * 5, GOOD * 5, FLAT * 5, resamples=500)
        second = brier_difference_interval(OUTCOMES * 5, GOOD * 5, FLAT * 5, resamples=500)
        assert first == second

    def test_the_seed_is_not_doing_real_work(self):
        """If another seed moves the bounds materially, the resample count is too low.

        This is what makes `BOOTSTRAP_SEED` an implementation detail rather than a choice
        that shapes a published number.
        """
        rows = (OUTCOMES * 20, GOOD * 20, FLAT * 20)
        base = brier_difference_interval(*rows, resamples=4_000)
        assert base is not None
        for offset in (1, 7, 999):
            other = brier_difference_interval(
                *rows, resamples=4_000, seed=BOOTSTRAP_SEED + offset
            )
            assert other is not None
            assert abs(other.low - base.low) < 0.01
            assert abs(other.high - base.high) < 0.01

    def test_a_wider_level_gives_a_wider_interval(self):
        rows = (OUTCOMES * 20, GOOD * 20, FLAT * 20)
        narrow = brier_difference_interval(*rows, level=0.80, resamples=2_000)
        wide = brier_difference_interval(*rows, level=0.99, resamples=2_000)
        assert narrow is not None and wide is not None
        assert wide.high - wide.low > narrow.high - narrow.low


class TestClusterBootstrap:
    def test_subjects_are_the_resampling_unit(self):
        subjects = ["a", "a", "b", "b", "c", "c", "d", "d"]
        interval = brier_difference_interval(
            OUTCOMES, GOOD, FLAT, subjects=subjects, resamples=500
        )
        assert interval is not None
        assert interval.unit == "subject"
        assert interval.units == 4

    def test_the_point_estimate_is_unaffected_by_the_unit(self):
        """Clustering changes the interval, never the estimate it surrounds."""
        subjects = ["a", "a", "b", "b", "c", "c", "d", "d"]
        rows = brier_difference_interval(OUTCOMES, GOOD, FLAT, resamples=500)
        clustered = brier_difference_interval(
            OUTCOMES, GOOD, FLAT, subjects=subjects, resamples=500
        )
        assert rows is not None and clustered is not None
        assert rows.point == clustered.point

    def test_a_single_subject_cannot_be_resampled_and_says_so(self):
        """One cluster means every resample is the same data. The width is zero, and
        that is a statement about the corpus, not a confident finding."""
        subjects = ["a"] * 8
        interval = brier_difference_interval(
            OUTCOMES, GOOD, FLAT, subjects=subjects, resamples=100
        )
        assert interval is not None
        assert interval.units == 1
        assert interval.low == pytest.approx(interval.point)
        assert interval.high == pytest.approx(interval.point)

    def test_subject_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="length mismatch"):
            brier_difference_interval(OUTCOMES, GOOD, FLAT, subjects=["a", "b"])


class TestFoldWinProbability:
    @pytest.mark.parametrize(
        ("wins", "folds", "expected"),
        [
            (2, 5, 26 / 32),  # the D60 headline: 0.8125
            (3, 5, 16 / 32),
            (4, 5, 6 / 32),
            (5, 5, 1 / 32),
            (0, 5, 1.0),
        ],
    )
    def test_exact_binomial_tail(self, wins, folds, expected):
        assert fold_win_probability(wins, folds) == pytest.approx(expected)

    def test_five_folds_can_never_be_convincing(self):
        """Even a clean sweep is 0.031 — worth knowing before reading a fold count.

        This is why D60's "wins 2 of 5" was never evidence of anything either way.
        """
        assert fold_win_probability(5, 5) > 0.03

    def test_out_of_range_is_none(self):
        assert fold_win_probability(6, 5) is None
        assert fold_win_probability(-1, 5) is None
        assert fold_win_probability(0, 0) is None


class TestRowsToExcludeZero:
    def test_none_when_the_interval_already_excludes_zero(self):
        interval = brier_difference_interval(
            OUTCOMES * 20, GOOD * 20, FLAT * 20, resamples=2_000
        )
        assert interval is not None and interval.excludes_zero
        assert rows_to_exclude_zero(interval, 160) is None

    def test_a_borderline_difference_needs_more_rows_than_observed(self):
        interval = brier_difference_interval(OUTCOMES, MARGINAL, FLAT, resamples=2_000)
        assert interval is not None and not interval.excludes_zero
        needed = rows_to_exclude_zero(interval, len(OUTCOMES))
        assert needed is not None and needed > len(OUTCOMES)

    def test_the_projection_barely_moves_with_the_sample_it_is_read_from(self):
        """It should describe the effect size, not the corpus that happened to measure it.

        Tripling the rows shrinks the interval but leaves the point estimate alone, so the
        projection has to land in roughly the same place. If it did not, the one-over-root-n
        assumption underneath it would be wrong and the number would be decorative.
        """
        small = brier_difference_interval(OUTCOMES, MARGINAL, FLAT, resamples=4_000)
        large = brier_difference_interval(
            OUTCOMES * 3, MARGINAL * 3, FLAT * 3, resamples=4_000
        )
        assert small is not None and large is not None
        from_small = rows_to_exclude_zero(small, 8)
        from_large = rows_to_exclude_zero(large, 24)
        assert from_small is not None and from_large is not None
        assert 0.5 < from_small / from_large < 2.0

    def test_a_wider_interval_around_the_same_point_needs_more_rows(self):
        """The projection is driven by width relative to the estimate, nothing else."""
        narrow = brier_difference_interval(
            OUTCOMES, MARGINAL, FLAT, level=0.80, resamples=2_000
        )
        wide = brier_difference_interval(
            OUTCOMES, MARGINAL, FLAT, level=0.99, resamples=2_000
        )
        assert narrow is not None and wide is not None
        assert rows_to_exclude_zero(wide, 8) > rows_to_exclude_zero(narrow, 8)
