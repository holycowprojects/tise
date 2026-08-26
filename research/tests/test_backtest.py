"""Rolling-origin backtesting.

The properties asserted here are the ones that make every published number meaningful.
If the fold structure leaks, nothing downstream can be trusted, and the failure is
invisible — leaked results look *better*, not broken.

Three things are checked directly:

* folds are strictly chronological, and training always precedes testing
* the training window expands and never loses history
* results do not depend on the order rows arrive in, because everything is sorted by
  `window_end` first
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from tise_research.eval.backtest import (
    BacktestResult,
    rolling_origin_folds,
    run_backtest,
)
from tise_research.features.labels import Label

SUBJECTS = ["video", "search", "news", "work"]


def make_labels(count: int = 200) -> list[Label]:
    start = datetime(2026, 3, 1, 9, tzinfo=UTC)
    labels = []
    for index in range(count):
        subject = SUBJECTS[index % len(SUBJECTS)]
        labels.append(
            Label(
                target="return_24h",
                subject=subject,
                window_end=start + timedelta(hours=7 * index),
                # Deterministic, learnable, and not uniform: video mostly returns,
                # work mostly does not.
                outcome=(index % 10 != 0) if subject == "video" else (index % 3 == 0),
                horizon_hours=24.0,
                session_id=f"s{index}",
            )
        )
    return labels


LABELS = make_labels()


class TestFolds:
    def test_requested_number_of_folds(self):
        assert len(rolling_origin_folds(LABELS, n_folds=5)) == 5

    def test_training_strictly_precedes_testing(self):
        """The single property everything else rests on."""
        for fold in rolling_origin_folds(LABELS, n_folds=5):
            latest_train = max(label.window_end for label in fold.train)
            earliest_test = min(label.window_end for label in fold.test)
            assert latest_train < earliest_test

    def test_no_label_is_in_both_train_and_test(self):
        for fold in rolling_origin_folds(LABELS, n_folds=5):
            train_ids = {label.session_id + label.subject for label in fold.train}
            test_ids = {label.session_id + label.subject for label in fold.test}
            assert not (train_ids & test_ids)

    def test_training_window_expands(self):
        folds = rolling_origin_folds(LABELS, n_folds=5)
        sizes = [len(fold.train) for fold in folds]
        assert sizes == sorted(sizes)
        assert sizes[0] < sizes[-1]

    def test_earlier_training_data_is_never_dropped(self):
        folds = rolling_origin_folds(LABELS, n_folds=5)
        for earlier, later in zip(folds, folds[1:], strict=False):
            assert set(earlier.train).issubset(set(later.train))

    def test_test_windows_do_not_overlap(self):
        folds = rolling_origin_folds(LABELS, n_folds=5)
        for earlier, later in zip(folds, folds[1:], strict=False):
            assert max(x.window_end for x in earlier.test) < min(
                x.window_end for x in later.test
            )

    def test_every_test_label_is_used_exactly_once(self):
        folds = rolling_origin_folds(LABELS, n_folds=5)
        tested = [label for fold in folds for label in fold.test]
        assert len(tested) == len(set(tested))

    def test_input_order_does_not_matter(self):
        """Sorted by window_end internally. A caller handing rows in a different order
        must not change a single number."""
        forward = rolling_origin_folds(LABELS, n_folds=4)
        backward = rolling_origin_folds(list(reversed(LABELS)), n_folds=4)
        assert [len(f.train) for f in forward] == [len(f.train) for f in backward]
        assert [f.train_end for f in forward] == [f.train_end for f in backward]

    def test_too_few_labels_raises_rather_than_producing_junk(self):
        with pytest.raises(ValueError):
            rolling_origin_folds(LABELS[:3], n_folds=5)


class TestRunBacktest:
    def test_scores_every_baseline(self):
        result = run_backtest(LABELS, n_folds=4)
        assert isinstance(result, BacktestResult)
        assert "majority_class" in result.models
        assert "category_base_rate" in result.models

    def test_is_deterministic(self):
        """No seed, because there is no randomness anywhere. Two runs are identical."""
        first = run_backtest(LABELS, n_folds=4)
        second = run_backtest(LABELS, n_folds=4)
        assert first == second

    def test_reports_a_base_rate_per_fold(self):
        result = run_backtest(LABELS, n_folds=4)
        for fold in result.folds:
            assert fold.base_rate is not None
            assert 0.0 <= fold.base_rate <= 1.0

    def test_category_base_rate_beats_the_global_one_on_learnable_data(self):
        """A sanity check on the harness, not a claim about real browsing: the synthetic
        data has genuine per-category signal, so if the harness cannot find it the
        harness is broken."""
        result = run_backtest(LABELS, n_folds=4)
        assert (
            result.models["category_base_rate"].brier
            < result.models["global_base_rate"].brier
        )

    def test_majority_class_is_always_reported(self):
        """D24. Omitting it is how a 70% base rate gets sold as 70% accuracy."""
        assert "majority_class" in run_backtest(LABELS, n_folds=4).models

    def test_per_category_results_respect_the_label_floor(self):
        """D26: a category with three labels gets no number, only a count."""
        result = run_backtest(LABELS, n_folds=4, min_category_labels=1000)
        assert result.per_category == {} or all(
            entry.reported is False for entry in result.per_category.values()
        )

    def test_unknown_is_kept_out_of_the_headline(self):
        """D27: `unknown` is the user's own frequent sites, highly predictable and
        unpresentable. Folding it in inflates the headline."""
        labels = [
            *LABELS,
            *[
                Label(
                    target="return_24h",
                    subject="unknown",
                    window_end=datetime(2026, 3, 1, 9, tzinfo=UTC)
                    + timedelta(hours=7 * i + 3),
                    outcome=True,
                    horizon_hours=24.0,
                    session_id=f"u{i}",
                )
                for i in range(60)
            ],
        ]
        result = run_backtest(labels, n_folds=4)
        assert result.headline_excludes_unknown is True
        assert result.unknown_label_count == 60
