"""Multiclass scoring, and the interval T-C's adoption rule is read off.

The most important test in this file is `test_folds_match_the_binary_backtest`. Two
implementations of "where do the folds go" is how two benchmark tables quietly stop being
comparable, and the drift would be a single index — invisible in every number either one
prints.

The second most important is the sign convention. `accuracy_difference` is
`challenger - reference`, the **opposite** arithmetic to `brier_difference`, because Brier
is an error and accuracy is a score. Both are positive when the challenger wins. Getting it
backwards inverts a verdict and nothing else in the pipeline would notice, so it is asserted
directly rather than trusted to the docstring.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from tise_research.eval.backtest import expanding_windows, rolling_origin_folds
from tise_research.eval.multiclass import (
    accuracy,
    accuracy_difference,
    accuracy_difference_interval,
    multiclass_folds,
    run_multiclass_backtest,
    top_k_accuracy,
)
from tise_research.features.labels import Label
from tise_research.features.transitions import CategoryTransition
from tise_research.models.next_category import (
    BAR_MODEL,
    BOUNCE_BACK_MODEL,
    CHALLENGER_MODEL,
    fit_bounce_back,
    fit_global_mode,
    fit_transition_ranker,
)

START = datetime(2026, 3, 1, 9, tzinfo=UTC)
CATEGORIES = ["news", "video", "work", "search"]


def make_transitions(count: int = 200) -> list[CategoryTransition]:
    """A learnable stream: news is followed by video far more often than by anything else."""
    items: list[CategoryTransition] = []
    previous: str | None = None
    source = "news"
    for index in range(count):
        target = "video" if source == "news" and index % 4 != 0 else CATEGORIES[index % 4]
        if target == source:
            target = CATEGORIES[(index + 1) % 4]
        items.append(
            CategoryTransition(
                transition_id=f"t{index}",
                at=START + timedelta(hours=index),
                from_category=source,
                to_category=target,
                session_id=f"s{index // 4}",
                within_session=index % 4 != 0,
                previous_category=previous,
                from_run_events=1 + index % 3,
            )
        )
        previous, source = source, target
    return items


TRANSITIONS = make_transitions()


class TestFolds:
    def test_folds_match_the_binary_backtest(self):
        # The reason `expanding_windows` was extracted. If these ever disagree, one of the
        # two targets is scored on a different split from the other and the two benchmark
        # pages stop being comparable.
        labels = [
            Label(
                target="return_24h",
                subject="video",
                window_end=START + timedelta(hours=index),
                outcome=index % 3 == 0,
                horizon_hours=24.0,
                session_id=f"s{index}",
            )
            for index in range(len(TRANSITIONS))
        ]
        def bounds(folds):
            return [(len(f.train), len(f.train) + len(f.test)) for f in folds]

        binary = bounds(rolling_origin_folds(labels))
        multi = bounds(multiclass_folds(TRANSITIONS))
        assert binary == multi
        assert multi == expanding_windows(len(TRANSITIONS))

    def test_training_precedes_testing(self):
        for fold in multiclass_folds(TRANSITIONS):
            assert max(item.at for item in fold.train) <= min(item.at for item in fold.test)

    def test_the_training_window_only_grows(self):
        sizes = [len(fold.train) for fold in multiclass_folds(TRANSITIONS)]
        assert sizes == sorted(sizes)
        assert len(set(sizes)) == len(sizes)

    def test_no_label_is_dropped(self):
        folds = multiclass_folds(TRANSITIONS)
        assert sum(len(fold.test) for fold in folds) + len(folds[0].train) == len(TRANSITIONS)

    def test_input_order_does_not_matter(self):
        forward = multiclass_folds(TRANSITIONS)
        backward = multiclass_folds(list(reversed(TRANSITIONS)))
        assert [[i.transition_id for i in f.test] for f in forward] == [
            [i.transition_id for i in f.test] for f in backward
        ]

    def test_too_few_labels_raises_rather_than_producing_thin_folds(self):
        with pytest.raises(ValueError, match="cannot support"):
            multiclass_folds(TRANSITIONS[:5], n_folds=5)


class TestAccuracy:
    def test_counts_exact_matches(self):
        assert accuracy(["a", "b", "c"], ["a", "x", "c"]) == pytest.approx(2 / 3)

    def test_empty_is_none_not_zero(self):
        # Zero accuracy is a measurement; no rows is not.
        assert accuracy([], []) is None

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="length mismatch"):
            accuracy(["a", "b"], ["a"])


class TestTopK:
    def test_k_of_one_is_plain_accuracy(self):
        outcomes = ["a", "b", "c", "d"]
        rankings = [("a", "b"), ("c", "b"), ("c", "a"), ("a", "d")]
        assert top_k_accuracy(outcomes, rankings, 1) == accuracy(
            outcomes, [r[0] for r in rankings]
        )

    def test_a_full_ranking_is_always_right(self):
        assert top_k_accuracy(["a", "b"], [("b", "a"), ("a", "b")], 2) == 1.0

    def test_k_below_one_raises(self):
        with pytest.raises(ValueError, match="at least 1"):
            top_k_accuracy(["a"], [("a",)], 0)


class TestSignConvention:
    def test_a_better_challenger_is_positive(self):
        # `challenger - reference`. The inverse of `brier_difference`, deliberately.
        assert accuracy_difference(["a", "a"], ["a", "a"], ["b", "b"]) == 1.0

    def test_a_worse_challenger_is_negative(self):
        assert accuracy_difference(["a", "a"], ["b", "b"], ["a", "a"]) == -1.0

    def test_agreement_is_exactly_zero(self):
        assert accuracy_difference(["a", "b"], ["a", "x"], ["a", "x"]) == 0.0

    def test_the_interval_carries_the_same_sign(self):
        interval = accuracy_difference_interval(
            ["a"] * 40, ["a"] * 40, ["b"] * 40,
            subjects=[f"s{i}" for i in range(40)], resamples=200,
        )
        assert interval is not None
        assert interval.point == 1.0
        assert interval.low > 0.0
        assert interval.excludes_zero


class TestInterval:
    def test_identical_models_do_not_produce_a_finding(self):
        predictions = ["a", "b", "c"] * 20
        interval = accuracy_difference_interval(
            predictions, predictions, predictions,
            subjects=[f"s{i // 3}" for i in range(60)], resamples=200,
        )
        assert interval is not None
        assert interval.point == 0.0
        assert not interval.excludes_zero

    def test_empty_input_is_none_rather_than_a_confident_zero(self):
        assert accuracy_difference_interval([], [], []) is None

    def test_clustering_names_the_unit_it_resampled(self):
        outcomes = ["a", "b"] * 30
        interval = accuracy_difference_interval(
            outcomes, outcomes, ["a"] * 60,
            subjects=[f"s{i // 6}" for i in range(60)], unit="session", resamples=200,
        )
        assert interval is not None
        assert interval.unit == "session"
        assert interval.units == 10

    def test_rows_are_the_default_when_no_clusters_are_given(self):
        outcomes = ["a", "b"] * 30
        interval = accuracy_difference_interval(
            outcomes, outcomes, ["a"] * 60, unit="session", resamples=200
        )
        assert interval is not None
        # `unit` only labels; passing it without `subjects` must not claim a clustering
        # that did not happen.
        assert interval.unit == "row"
        assert interval.units == 60

    def test_clustered_is_wider_than_rows_on_correlated_data(self):
        # The whole reason D94 changed the unit. Rows inside a session share whatever
        # makes that session predictable, and treating them as independent understates
        # the width.
        outcomes = [c for c in CATEGORIES for _ in range(15)]
        challenger = [c if i % 30 < 25 else "x" for i, c in enumerate(outcomes)]
        subjects = [f"s{i // 15}" for i in range(60)]
        rows = accuracy_difference_interval(
            outcomes, challenger, ["news"] * 60, resamples=2000
        )
        clustered = accuracy_difference_interval(
            outcomes, challenger, ["news"] * 60, subjects=subjects, resamples=2000
        )
        assert rows is not None and clustered is not None
        assert (clustered.high - clustered.low) > (rows.high - rows.low)

    def test_subject_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="length mismatch"):
            accuracy_difference_interval(["a"] * 4, ["a"] * 4, ["b"] * 4, subjects=["s1"])

    def test_reproducible_across_runs(self):
        args = (["a", "b"] * 30, ["a", "b"] * 30, ["a"] * 60)
        kwargs = {"subjects": [f"s{i // 6}" for i in range(60)], "resamples": 500}
        assert accuracy_difference_interval(*args, **kwargs) == accuracy_difference_interval(
            *args, **kwargs
        )


MODELS = {
    BAR_MODEL: fit_global_mode,
    CHALLENGER_MODEL: fit_transition_ranker,
    BOUNCE_BACK_MODEL: fit_bounce_back,
}


class TestBacktest:
    def test_every_model_is_scored_on_the_same_rows(self):
        result = run_multiclass_backtest(TRANSITIONS, MODELS)
        lengths = {len(values) for values in result.pooled_predictions.values()}
        assert lengths == {len(result.pooled_outcomes)}
        assert len(result.pooled_sessions) == len(result.pooled_outcomes)
        assert len(result.pooled_sources) == len(result.pooled_outcomes)

    def test_top3_is_never_below_top1(self):
        result = run_multiclass_backtest(TRANSITIONS, MODELS)
        for model in result.models.values():
            assert model.top3 >= model.top1

    def test_the_table_learns_something_the_floor_does_not(self):
        # A sanity check on the machinery, not a finding: this stream was constructed so
        # that news is usually followed by video. If the table cannot beat the mode here,
        # the plumbing is broken rather than the corpus uninformative.
        result = run_multiclass_backtest(TRANSITIONS, MODELS)
        assert result.models[CHALLENGER_MODEL].top1 > result.models[BAR_MODEL].top1

    def test_a_source_below_the_floor_is_counted_and_not_scored(self):
        result = run_multiclass_backtest(TRANSITIONS, MODELS, min_source_labels=10_000)
        assert result.per_source
        assert all(not source.reported for source in result.per_source.values())
        assert all(source.top1 is None for source in result.per_source.values())

    def test_no_models_raises(self):
        # The bar is a model too. Scoring a challenger with nothing to compare it against
        # is how a number gets published with nothing underneath it (D24).
        with pytest.raises(ValueError, match="no models"):
            run_multiclass_backtest(TRANSITIONS, {})

    def test_deterministic(self):
        first = run_multiclass_backtest(TRANSITIONS, MODELS)
        second = run_multiclass_backtest(TRANSITIONS, MODELS)
        assert first == second
