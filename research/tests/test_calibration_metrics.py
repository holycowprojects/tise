"""Reliability curves and calibration error.

The thing being defended here is that these numbers stay *honest about their own
weakness*: ECE depends on the bin count, bins can hold three points, and both facts have
to survive into anything that reports them.
"""

from __future__ import annotations

import pytest
from tise_research.eval.calibration import (
    DEFAULT_BINS,
    expected_calibration_error,
    maximum_calibration_error,
    reliability_curve,
)


def perfectly_calibrated() -> tuple[list[bool], list[float]]:
    """Ten predictions at each decile, each right that share of the time."""
    outcomes: list[bool] = []
    probabilities: list[float] = []
    for decile in range(10):
        probability = decile / 10 + 0.05
        for index in range(100):
            probabilities.append(probability)
            outcomes.append(index < probability * 100)
    return outcomes, probabilities


class TestBinning:
    def test_bins_are_half_open_except_the_top(self) -> None:
        """Exactly 0.3 lands in [0.3, 0.4) and 1.0 lands in the last bin, not past it."""
        curve = reliability_curve([True, True], [0.3, 1.0], bins=10)
        assert curve[3].count == 1
        assert curve[9].count == 1
        assert sum(entry.count for entry in curve) == 2

    def test_empty_bins_are_kept_not_dropped(self) -> None:
        """A gap says the model never predicted in that range. Closing it draws a line
        through territory nothing was measured in."""
        curve = reliability_curve([True, False], [0.95, 0.92], bins=10)
        assert len(curve) == 10
        assert curve[0].count == 0
        assert curve[0].mean_predicted is None
        assert curve[0].observed_rate is None
        assert curve[0].gap is None

    def test_every_prediction_lands_in_exactly_one_bin(self) -> None:
        probabilities = [index / 97 for index in range(98)]
        curve = reliability_curve([True] * 98, probabilities, bins=7)
        assert sum(entry.count for entry in curve) == 98

    def test_a_single_bin_is_the_whole_population(self) -> None:
        outcomes, probabilities = perfectly_calibrated()
        curve = reliability_curve(outcomes, probabilities, bins=1)
        assert len(curve) == 1
        assert curve[0].count == len(outcomes)

    def test_zero_bins_is_refused(self) -> None:
        with pytest.raises(ValueError, match="at least one bin"):
            reliability_curve([True], [0.5], bins=0)

    def test_misaligned_input_raises(self) -> None:
        with pytest.raises(ValueError, match="outcomes"):
            reliability_curve([True, False], [0.5])


class TestGap:
    def test_a_positive_gap_means_overconfident(self) -> None:
        """Predicted 0.9, happened half the time: the gap is positive."""
        curve = reliability_curve([True, False], [0.9, 0.9], bins=10)
        entry = next(item for item in curve if item.count)
        assert entry.gap is not None and entry.gap == pytest.approx(0.4)

    def test_a_negative_gap_means_underconfident(self) -> None:
        curve = reliability_curve([True, True, True, False], [0.5] * 4, bins=10)
        entry = next(item for item in curve if item.count)
        assert entry.gap is not None and entry.gap < 0


class TestError:
    def test_perfect_calibration_scores_zero(self) -> None:
        outcomes, probabilities = perfectly_calibrated()
        error = expected_calibration_error(outcomes, probabilities)
        assert error is not None and error < 0.01

    def test_a_confidently_wrong_model_scores_close_to_one(self) -> None:
        error = expected_calibration_error([False] * 50, [0.99] * 50)
        assert error is not None and error > 0.95

    def test_empty_input_is_none_not_zero(self) -> None:
        """Zero is a perfect score. No data is not a score."""
        assert expected_calibration_error([], []) is None
        assert maximum_calibration_error([], []) is None

    def test_the_answer_depends_on_the_bin_count(self) -> None:
        """Which is exactly why the bin count is declared and travels with the number.

        ECE is not a property of the predictions alone, and a report that quotes one
        without saying how it was binned is quoting an incomparable figure.
        """
        outcomes = [index % 3 == 0 for index in range(300)]
        probabilities = [0.2 + 0.6 * (index / 300) for index in range(300)]
        coarse = expected_calibration_error(outcomes, probabilities, bins=2)
        fine = expected_calibration_error(outcomes, probabilities, bins=50)
        assert coarse is not None and fine is not None
        assert coarse != fine

    def test_maximum_error_finds_the_worst_bin_that_average_hides(self) -> None:
        """A fine ECE can sit next to one range where the model is badly wrong."""
        outcomes = [True] * 99 + [True]
        probabilities = [0.99] * 99 + [0.05]
        ece = expected_calibration_error(outcomes, probabilities)
        mce = maximum_calibration_error(outcomes, probabilities)
        assert ece is not None and mce is not None
        assert ece < 0.02
        assert mce > 0.9

    def test_maximum_error_can_ignore_bins_too_small_to_mean_anything(self) -> None:
        """Otherwise the answer is decided by a bin holding two points."""
        outcomes = [True] * 99 + [True]
        probabilities = [0.99] * 99 + [0.05]
        assert maximum_calibration_error(outcomes, probabilities, min_count=5) is not None
        strict = maximum_calibration_error(outcomes, probabilities, min_count=5)
        assert strict is not None and strict < 0.02

    def test_the_default_bin_count_is_the_declared_one(self) -> None:
        outcomes, probabilities = perfectly_calibrated()
        assert expected_calibration_error(
            outcomes, probabilities
        ) == expected_calibration_error(outcomes, probabilities, bins=DEFAULT_BINS)
