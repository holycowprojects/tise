"""Baselines — the numbers any real model has to beat before it is interesting.

Five of them, and the majority-class one is mandatory (D24). With `video` at 90%
positive and an overall base rate near 70%, a model that beats coin-flipping has
demonstrated nothing; the question is always whether it beat *reporting the base rate*.

Every baseline is fitted on the training window and then **frozen**. Nothing updates
during the test window. That is a weaker "same as last time" than an online version would
be, and it is stated in the report rather than quietly improved.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from tise_research.features.labels import Label
from tise_research.models.baselines import (
    ALL_BASELINES,
    fit_category_base_rate,
    fit_global_base_rate,
    fit_majority_class,
    fit_same_as_last,
    fit_time_of_day,
)


def label(
    day: int, hour: int = 10, subject: str = "video", outcome: bool = True
) -> Label:
    return Label(
        target="return_24h",
        subject=subject,
        window_end=datetime(2026, 6, day, hour, tzinfo=UTC),
        outcome=outcome,
        horizon_hours=24.0,
        session_id=f"s-{day}-{hour}",
    )


TRAIN = [
    label(1, subject="video", outcome=True),
    label(2, subject="video", outcome=True),
    label(3, subject="video", outcome=True),
    label(4, subject="news", outcome=False),
    label(5, subject="news", outcome=False),
]  # global base rate 3/5 = 0.6


class TestMajorityClass:
    def test_predicts_one_when_positives_dominate(self):
        model = fit_majority_class(TRAIN)
        assert model.predict(label(9, subject="video")) == 1.0

    def test_predicts_zero_when_negatives_dominate(self):
        model = fit_majority_class([label(1, outcome=False), label(2, outcome=False)])
        assert model.predict(label(9)) == 0.0

    def test_is_a_hard_classifier(self):
        """Hard 0/1 output is the point: it shows what the log-loss clamp is hiding."""
        model = fit_majority_class(TRAIN)
        assert model.predict(label(9)) in {0.0, 1.0}


class TestGlobalBaseRate:
    def test_predicts_the_training_base_rate(self):
        model = fit_global_base_rate(TRAIN)
        assert model.predict(label(9, subject="anything")) == pytest.approx(0.6)

    def test_ignores_the_category(self):
        model = fit_global_base_rate(TRAIN)
        assert model.predict(label(9, subject="video")) == model.predict(
            label(9, subject="finance")
        )


class TestCategoryBaseRate:
    def test_uses_the_category_specific_rate(self):
        model = fit_category_base_rate(TRAIN, smoothing=0.0)
        assert model.predict(label(9, subject="video")) == pytest.approx(1.0)
        assert model.predict(label(9, subject="news")) == pytest.approx(0.0)

    def test_unseen_category_falls_back_to_the_global_rate(self):
        """Cold start is the normal case for a new user, not an edge case."""
        model = fit_category_base_rate(TRAIN, smoothing=0.0)
        assert model.predict(label(9, subject="travel")) == pytest.approx(0.6)

    def test_smoothing_pulls_sparse_categories_toward_the_global_rate(self):
        """D26: nine of fifteen categories have fewer than ten labels. Unsmoothed, a
        category with two positives claims 100% and is confidently wrong."""
        unsmoothed = fit_category_base_rate(TRAIN, smoothing=0.0)
        smoothed = fit_category_base_rate(TRAIN, smoothing=5.0)
        assert smoothed.predict(label(9, subject="video")) < unsmoothed.predict(
            label(9, subject="video")
        )
        assert smoothed.predict(label(9, subject="video")) > 0.6


class TestSameAsLast:
    def test_repeats_the_last_training_outcome_for_that_category(self):
        model = fit_same_as_last(TRAIN, alpha=0.05)
        assert model.predict(label(9, subject="video")) == pytest.approx(0.95)
        assert model.predict(label(9, subject="news")) == pytest.approx(0.05)

    def test_alpha_keeps_log_loss_finite(self):
        """A hard repeat has infinite log loss the first time it is wrong. Smoothing is
        declared rather than hidden inside the metric."""
        model = fit_same_as_last(TRAIN, alpha=0.05)
        assert 0.0 < model.predict(label(9, subject="video")) < 1.0

    def test_unseen_category_falls_back_to_the_global_rate(self):
        model = fit_same_as_last(TRAIN, alpha=0.05)
        assert model.predict(label(9, subject="travel")) == pytest.approx(0.6)


class TestTimeOfDay:
    def test_uses_the_hour_bucket_of_window_end(self):
        train = [
            label(1, hour=9, outcome=True),
            label(2, hour=9, outcome=True),
            label(3, hour=22, outcome=False),
            label(4, hour=22, outcome=False),
        ]
        model = fit_time_of_day(train, bucket_hours=6, smoothing=0.0)
        assert model.predict(label(9, hour=9)) == pytest.approx(1.0)
        assert model.predict(label(9, hour=22)) == pytest.approx(0.0)

    def test_unseen_bucket_falls_back_to_the_global_rate(self):
        model = fit_time_of_day(TRAIN, bucket_hours=6, smoothing=0.0)
        assert model.predict(label(9, hour=3)) == pytest.approx(0.6)


class TestEveryBaseline:
    @pytest.mark.parametrize("fit", ALL_BASELINES.values(), ids=ALL_BASELINES.keys())
    def test_returns_a_probability(self, fit):
        model = fit(TRAIN)
        assert 0.0 <= model.predict(label(9)) <= 1.0

    @pytest.mark.parametrize("fit", ALL_BASELINES.values(), ids=ALL_BASELINES.keys())
    def test_no_training_data_predicts_one_half(self, fit):
        """An empty training window is the first fold's reality, not a bug."""
        assert fit([]).predict(label(9)) == pytest.approx(0.5)

    @pytest.mark.parametrize("fit", ALL_BASELINES.values(), ids=ALL_BASELINES.keys())
    def test_prediction_does_not_depend_on_the_label_being_predicted(self, fit):
        """The leakage test. If flipping the outcome of the very row being predicted
        changes its prediction, the model is reading the answer."""
        model = fit(TRAIN)
        target = label(9, subject="video", outcome=True)
        flipped = replace(target, outcome=False)
        assert model.predict(target) == model.predict(flipped)

    @pytest.mark.parametrize("fit", ALL_BASELINES.values(), ids=ALL_BASELINES.keys())
    def test_is_deterministic(self, fit):
        first = fit(TRAIN).predict(label(9))
        second = fit(TRAIN).predict(label(9))
        assert first == second

    @pytest.mark.parametrize("fit", ALL_BASELINES.values(), ids=ALL_BASELINES.keys())
    def test_has_a_name(self, fit):
        assert fit(TRAIN).name
