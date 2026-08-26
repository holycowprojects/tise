"""Scoring rules.

Brier and log loss are both **proper** scoring rules: they are minimised by reporting
your true belief, so a model cannot improve its score by shading probabilities toward
the extremes. That is the whole reason this project reports them instead of accuracy.

Accuracy is deliberately absent as a headline. With a 70% base rate, always saying "yes"
scores 70% and has learned nothing.
"""

from __future__ import annotations

import math

import pytest
from tise_research.eval.metrics import (
    LOG_LOSS_EPSILON,
    base_rate,
    brier_score,
    log_loss,
    skill_score,
)


class TestBrierScore:
    def test_perfect_prediction_scores_zero(self):
        assert brier_score([True, False], [1.0, 0.0]) == 0.0

    def test_completely_wrong_prediction_scores_one(self):
        assert brier_score([True, False], [0.0, 1.0]) == 1.0

    def test_uninformative_half_scores_a_quarter(self):
        """0.5 everywhere gives 0.25 regardless of the labels — the reference point."""
        assert brier_score([True, False, True], [0.5, 0.5, 0.5]) == pytest.approx(0.25)

    def test_is_the_mean_squared_error_of_the_probability(self):
        assert brier_score([True, False], [0.8, 0.3]) == pytest.approx(
            ((1 - 0.8) ** 2 + (0 - 0.3) ** 2) / 2
        )

    def test_empty_input_is_none_not_zero(self):
        """Zero is a perfect score. An empty fold has no score at all."""
        assert brier_score([], []) is None

    def test_mismatched_lengths_raise(self):
        with pytest.raises(ValueError):
            brier_score([True], [0.5, 0.5])


class TestLogLoss:
    def test_uninformative_half_scores_ln_two(self):
        assert log_loss([True, False], [0.5, 0.5]) == pytest.approx(math.log(2))

    def test_confident_and_correct_scores_near_zero(self):
        assert log_loss([True], [1.0]) == pytest.approx(0.0, abs=1e-5)

    def test_confident_and_wrong_is_clamped_not_infinite(self):
        """A hard 0/1 predictor that is wrong has infinite log loss. The clamp keeps the
        number finite; the report has to say the clamp is doing the work, because
        otherwise the figure looks like a measurement rather than a floor."""
        score = log_loss([True], [0.0])
        assert math.isfinite(score)
        assert score == pytest.approx(-math.log(LOG_LOSS_EPSILON))

    def test_empty_input_is_none(self):
        assert log_loss([], []) is None


class TestBaseRate:
    def test_share_of_positives(self):
        assert base_rate([True, True, False, False]) == pytest.approx(0.5)

    def test_all_positive(self):
        assert base_rate([True, True]) == 1.0

    def test_empty_input_is_none(self):
        assert base_rate([]) is None


class TestSkillScore:
    """Skill is the only honest headline when the base rate is 70%: it asks whether the
    model beat simply reporting that base rate, not whether it beat coin-flipping."""

    def test_zero_when_the_model_equals_the_reference(self):
        assert skill_score(0.21, 0.21) == pytest.approx(0.0)

    def test_positive_when_the_model_is_better(self):
        assert skill_score(0.105, 0.21) == pytest.approx(0.5)

    def test_negative_when_the_model_is_worse(self):
        assert skill_score(0.42, 0.21) == pytest.approx(-1.0)

    def test_reference_of_zero_is_none_not_infinity(self):
        assert skill_score(0.1, 0.0) is None

    def test_none_inputs_propagate(self):
        assert skill_score(None, 0.21) is None
        assert skill_score(0.21, None) is None
