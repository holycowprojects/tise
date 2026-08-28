"""The tournament (D84), tested on the claims it makes rather than on its arithmetic.

Three things could make `tournament.md` fictional without making anything fail:

1. **The folds silently stop being identical.** The whole comparison rests on every model
   scoring the same rows. If a challenger ever scored a different set, the table would
   still render and every number in it would still be a real Brier score.
2. **The failure case stops being the worst row.** It is published as "chosen by `max`,
   not by looking for an interesting one". That sentence is only true if it is.
3. **The adoption rule fires the wrong way.** D84 requires an interval excluding zero *in
   the challenger's favour*. An interval that excludes zero because the challenger is
   clearly **worse** must not fire it — and `excludes_zero` alone cannot tell them apart.

The scores themselves come from real browsing in `data/` and are not asserted here.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import pytest
from tise_research.eval.intervals import Interval
from tise_research.eval.tournament import (
    BAR_MODEL,
    PREVIOUS_FEATURE_SET,
    CorpusTournament,
    _pooled_labels,
    run_tournament,
)
from tise_research.features.events import Event
from tise_research.features.labels import return_24h_labels
from tise_research.models.challengers import (
    XGB_DEFAULT,
    XGB_SMALL,
    design_vector,
    fit_challenger,
)
from tise_research.models.return_model import (
    MODEL_NAME,
    FeatureIndex,
    model_name,
)

TIMEOUT = 1800.0
HORIZON = 24.0
N_FOLDS = 3
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
    """Synthetic — a unit test, never a benchmark (SPEC.md invariant 3)."""
    events: list[Event] = []
    for day in range(30):
        events.append(event("video", day * 24, f"v{day}"))
        events.append(event("video", day * 24 + 0.25, f"v{day}b"))
        if day % 3 == 0:
            events.append(event("dev", day * 24 + 3, f"d{day}"))
            events.append(event("dev", day * 24 + 3.25, f"d{day}b"))
        if day % 11 == 0:
            events.append(event("travel", day * 24 + 6, f"t{day}"))
    return events


@pytest.fixture(scope="module")
def events() -> list[Event]:
    return corpus()


@pytest.fixture(scope="module")
def labels(events: list[Event]):
    return return_24h_labels(events, timeout_seconds=TIMEOUT, horizon_hours=HORIZON)


@pytest.fixture(scope="module")
def index(events: list[Event]) -> FeatureIndex:
    return FeatureIndex(
        events=events, timeout_seconds=TIMEOUT, horizon_hours=HORIZON
    )


@pytest.fixture(scope="module")
def tournament(labels, index: FeatureIndex) -> CorpusTournament:
    return run_tournament("history-test", labels, index, n_folds=N_FOLDS)


class TestTheFoldsAreIdentical:
    def test_every_model_scored_the_same_number_of_rows(
        self, tournament: CorpusTournament
    ) -> None:
        # The claim the whole page rests on. One `run_backtest` call is what makes it
        # true; this is what would notice if that ever stopped being the case.
        counts = {
            name: len(probabilities)
            for name, probabilities in tournament.result.pooled_probabilities.items()
        }
        assert len(set(counts.values())) == 1, counts
        assert counts[MODEL_NAME] == len(tournament.result.pooled_outcomes)

    def test_the_challengers_and_the_previous_set_are_all_present(
        self, tournament: CorpusTournament
    ) -> None:
        for name in (
            MODEL_NAME,
            XGB_SMALL.name,
            XGB_DEFAULT.name,
            BAR_MODEL,
            model_name(PREVIOUS_FEATURE_SET),
        ):
            assert name in tournament.result.models

    def test_pooled_labels_line_up_with_the_pooled_outcomes(
        self, labels, tournament: CorpusTournament
    ) -> None:
        # `_failure_case` names a row from this reconstruction. If it drifts, the report
        # would attribute a probability to the wrong category.
        pooled = _pooled_labels(labels, n_folds=N_FOLDS)
        assert [label.outcome for label in pooled] == list(
            tournament.result.pooled_outcomes
        )
        assert [label.subject for label in pooled] == list(
            tournament.result.pooled_subjects
        )


class TestTheFailureCaseIsTheWorstRow:
    def test_it_is_the_maximum_squared_error(
        self, labels, tournament: CorpusTournament
    ) -> None:
        failure = tournament.failure
        assert failure is not None

        probabilities = tournament.result.pooled_probabilities[MODEL_NAME]
        worst = max(
            (probability - (1.0 if outcome else 0.0)) ** 2
            for probability, outcome in zip(
                probabilities, tournament.result.pooled_outcomes, strict=True
            )
        )
        assert failure.squared_error == pytest.approx(worst)

    def test_it_reports_the_row_it_scored(self, tournament: CorpusTournament) -> None:
        failure = tournament.failure
        assert failure is not None
        expected = (failure.probability - (1.0 if failure.outcome else 0.0)) ** 2
        assert failure.squared_error == pytest.approx(expected)

    def test_it_carries_the_feature_vector_that_produced_it(
        self, tournament: CorpusTournament
    ) -> None:
        failure = tournament.failure
        assert failure is not None
        assert failure.values, "a failure case with no features documents nothing"


class TestTheAdoptionRule:
    def _tournament_with(self, tournament: CorpusTournament, interval: Interval):
        return CorpusTournament(
            name=tournament.name,
            result=tournament.result,
            subject_intervals={XGB_SMALL.name: interval},
            row_intervals=tournament.row_intervals,
            failure=tournament.failure,
            width_ladder=tournament.width_ladder,
            null_shares=tournament.null_shares,
        )

    def _interval(self, point: float, low: float, high: float) -> Interval:
        return Interval(
            point=point,
            low=low,
            high=high,
            level=0.95,
            resamples=10,
            unit="subject",
            units=4,
        )

    def test_fires_when_the_challenger_is_clearly_better(
        self, tournament: CorpusTournament
    ) -> None:
        fake = self._tournament_with(
            tournament, self._interval(0.05, 0.01, 0.09)
        )
        assert fake.fires_adoption_rule(XGB_SMALL.name)

    def test_does_not_fire_when_the_challenger_is_clearly_worse(
        self, tournament: CorpusTournament
    ) -> None:
        # The one that matters. This interval *excludes zero*, so a rule written as
        # `excludes_zero` alone would fire it — and would announce a gap in favour of a
        # challenger that lost.
        fake = self._tournament_with(
            tournament, self._interval(-0.05, -0.09, -0.01)
        )
        assert not fake.fires_adoption_rule(XGB_SMALL.name)

    def test_does_not_fire_on_an_interval_containing_zero(
        self, tournament: CorpusTournament
    ) -> None:
        fake = self._tournament_with(
            tournament, self._interval(0.05, -0.01, 0.11)
        )
        assert not fake.fires_adoption_rule(XGB_SMALL.name)

    def test_does_not_fire_without_an_interval(
        self, tournament: CorpusTournament
    ) -> None:
        fake = CorpusTournament(
            name=tournament.name,
            result=tournament.result,
            subject_intervals={XGB_SMALL.name: None},
            row_intervals=tournament.row_intervals,
            failure=tournament.failure,
            width_ladder=tournament.width_ladder,
            null_shares=tournament.null_shares,
        )
        assert not fake.fires_adoption_rule(XGB_SMALL.name)


class TestTheChallenger:
    def test_sees_nulls_as_nan_rather_than_a_fill(self, index: FeatureIndex) -> None:
        # The asymmetry D84 registered. If this ever became a filled number, the
        # challenger would silently lose its native missing handling and the reported gap
        # would change meaning without any test noticing.
        from tise_research.features.vector import FeatureRow, compute_features

        row = compute_features(
            [], "video", window_end=START, timeout_seconds=TIMEOUT,
            horizon_hours=HORIZON,
        )
        assert isinstance(row, FeatureRow)
        nulls = [name for name, value in row.values.items() if value is None]
        assert nulls, "fixture no longer produces a null, so it tests nothing"

        vector = design_vector(row)
        assert any(math.isnan(value) for value in vector)

    def test_never_reads_the_outcome_of_the_row_it_predicts(
        self, labels, index: FeatureIndex
    ) -> None:
        # The `Baseline` contract. A model that reads `outcome` scores perfectly and is
        # worthless, and nothing else in the pipeline would catch it.
        from dataclasses import replace

        train = list(labels[:-1])
        target = labels[-1]
        model = fit_challenger(train, spec=XGB_SMALL, index=index)
        before = model.predict(target)
        after = model.predict(replace(target, outcome=not target.outcome))
        assert before == after

    def test_is_deterministic_across_fits(self, labels, index: FeatureIndex) -> None:
        # SPEC.md invariant 3 wants a committed script behind every number, and a number
        # that moves between runs of that script does not satisfy it.
        train = list(labels[:-1])
        target = labels[-1]
        first = fit_challenger(train, spec=XGB_SMALL, index=index)
        second = fit_challenger(train, spec=XGB_SMALL, index=index)
        assert first.predict(target) == second.predict(target)

    def test_a_single_class_window_gets_a_constant_not_a_crash(
        self, labels, index: FeatureIndex
    ) -> None:
        positives = [label for label in labels if label.outcome][:8]
        assert positives, "fixture has no positive labels"
        model = fit_challenger(positives, spec=XGB_SMALL, index=index)
        assert model.predict(labels[-1]) == 1.0

    def test_an_empty_window_predicts_no_information(
        self, labels, index: FeatureIndex
    ) -> None:
        model = fit_challenger([], spec=XGB_SMALL, index=index)
        assert model.predict(labels[-1]) == 0.5


class TestTheWidthLadder:
    def test_compares_three_things_against_the_shipped_model(
        self, tournament: CorpusTournament
    ) -> None:
        against = [rung.against for rung in tournament.width_ladder]
        assert against == [
            model_name(PREVIOUS_FEATURE_SET),
            XGB_SMALL.name,
            BAR_MODEL,
        ]

    def test_every_width_is_positive(self, tournament: CorpusTournament) -> None:
        for rung in tournament.width_ladder:
            assert rung.width > 0.0
