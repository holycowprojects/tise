"""The `return_24h` model end to end: events in, a probability out.

The number that decides whether T11 succeeded comes from a backtest on real browsing, not
from here. What these tests protect is that the pipeline cannot leak and cannot memoise
its way into a wrong answer — the two failures that would make that number fictional
without making anything fail.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from tise_research.eval.metrics import brier_score
from tise_research.features.events import Event
from tise_research.features.labels import return_24h_labels
from tise_research.features.vector import DEFAULT_FEATURE_SET
from tise_research.models.baselines import fit_category_base_rate
from tise_research.models.prep import design_columns
from tise_research.models.return_model import (
    FeatureIndex,
    fit_return_model,
    make_return_model_fitter,
    model_name,
)

TIMEOUT = 1800.0
HORIZON = 24.0
START = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)


def event(category: str, hours: float, event_id: str) -> Event:
    return Event(
        event_id=event_id,
        occurred_at=START + timedelta(hours=hours),
        domain="example.com",
        category=category,
        transition="link",
        dwell_seconds=None,
        source="import",
    )


def corpus() -> list[Event]:
    """`video` recurs daily, `travel` twice a fortnight. A signal a model should find.

    Synthetic, and used as a unit test rather than a benchmark. SPEC.md permits the
    first and forbids the second, and the distinction is the whole reason the real
    numbers come from `data/`.
    """
    events: list[Event] = []
    for day in range(30):
        events.append(event("video", day * 24, f"v{day}"))
        events.append(event("video", day * 24 + 0.25, f"v{day}b"))
        if day % 11 == 0:
            events.append(event("travel", day * 24 + 3, f"t{day}"))
    return events


def index_for(events):
    return FeatureIndex(
        events=events, timeout_seconds=TIMEOUT, horizon_hours=HORIZON
    )


def labels_for(events):
    return return_24h_labels(events, timeout_seconds=TIMEOUT, horizon_hours=HORIZON)


class TestFitting:
    def test_the_matrix_has_one_column_per_design_column(self) -> None:
        events = corpus()
        model = fit_return_model(labels_for(events), index=index_for(events))
        assert len(model.state.weights) == len(design_columns())

    def test_it_converges_rather_than_running_out_of_iterations(self) -> None:
        events = corpus()
        model = fit_return_model(labels_for(events), index=index_for(events))
        assert model.state.gradient_norm < 1e-6

    def test_it_separates_a_daily_habit_from_a_fortnightly_one(self) -> None:
        events = corpus()
        labels = labels_for(events)
        model = fit_return_model(labels, index=index_for(events))

        video = [model.predict(row) for row in labels if row.subject == "video"]
        travel = [model.predict(row) for row in labels if row.subject == "travel"]
        assert min(video) > max(travel)

    def test_it_beats_the_baseline_it_has_to_beat_on_data_that_has_a_signal(self) -> None:
        """Not a benchmark — a check that the optimiser can find a signal at all.

        If this fails, a poor score on real browsing means nothing, because the pipeline
        could not have found a signal that was put there deliberately.
        """
        events = corpus()
        labels = labels_for(events)
        outcomes = [label.outcome for label in labels]

        model = fit_return_model(labels, index=index_for(events))
        baseline = fit_category_base_rate(labels)

        model_score = brier_score(outcomes, [model.predict(row) for row in labels])
        baseline_score = brier_score(outcomes, [baseline.predict(row) for row in labels])
        assert model_score is not None and baseline_score is not None
        assert model_score <= baseline_score

    def test_an_empty_training_window_predicts_one_half(self) -> None:
        events = corpus()
        model = fit_return_model([], index=index_for(events))
        assert model.predict(labels_for(events)[0]) == 0.5


class TestLeakage:
    def test_a_prediction_never_moves_when_the_future_changes(self) -> None:
        events = corpus()
        labels = labels_for(events)
        train = labels[:20]
        subject = labels[20]

        model = fit_return_model(train, index=index_for(events))
        before = model.predict(subject)

        # Something happens long after the label became decidable. If a feature reads
        # past its own `window_end`, this moves — and nothing else would notice.
        later = [*events, event("video", 24 * 60, "future")]
        after = fit_return_model(train, index=index_for(later)).predict(subject)
        assert after == pytest.approx(before, abs=1e-12)

    def test_the_model_never_reads_the_outcome_of_the_row_it_is_predicting(self) -> None:
        """The same assertion `test_baselines.py` makes, for the same reason."""
        events = corpus()
        labels = labels_for(events)
        model = fit_return_model(labels[:20], index=index_for(events))

        subject = labels[20]
        flipped = type(subject)(
            target=subject.target,
            subject=subject.subject,
            window_end=subject.window_end,
            outcome=not subject.outcome,
            horizon_hours=subject.horizon_hours,
            session_id=subject.session_id,
        )
        assert model.predict(flipped) == model.predict(subject)


class TestFeatureIndex:
    def test_the_cache_returns_the_same_row_it_would_have_computed(self) -> None:
        """Memoisation of a pure function. If it is not, every fold after the first is
        scored against rows that were computed under different conditions."""
        events = corpus()
        labels = labels_for(events)
        warm = index_for(events)
        cold = index_for(events)

        for label in labels[:10]:
            warm.row_for(label)
        for label in labels[:10]:
            assert warm.row_for(label).values == cold.row_for(label).values

    def test_the_fitter_matches_the_baseline_signature(self) -> None:
        events = corpus()
        fit = make_return_model_fitter(index_for(events))
        model = fit(labels_for(events))
        assert callable(model.predict)
        # The name follows the feature set, so a table can never show two sets under one
        # label — which is exactly what a tournament comparing them would otherwise do.
        assert model.name == model_name(DEFAULT_FEATURE_SET)
        assert model.name == "logreg_fs3"
