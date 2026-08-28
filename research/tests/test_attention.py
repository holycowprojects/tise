"""Attention (dwell) labels, and the two properties the measurement rests on.

**Leakage.** Same structural guarantee as `block_labels.py`: a visit's label and features are
emitted before that visit joins any state. Asserted rather than trusted.

**Balance.** The label is a median split against the category's own recent dwell, which
should give a base rate near 50% for any person and any category. D88 claimed that property
for `block_volume` and D90 measured it false at daily granularity, so it is checked here
rather than assumed — this is the first target in the project where it actually holds.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from tise_research.features.attention import (
    ATTENTION_FEATURE_SET,
    ATTENTION_TARGET,
    attention_examples,
)
from tise_research.features.events import Event
from tise_research.features.vector import FEATURE_SETS
from tise_research.models.prep import design_columns, fit_preprocessor

START = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)
TIMEOUT = 1800.0


def event(
    index: int,
    dwell: float | None,
    *,
    category: str = "video",
    transition: str = "link",
    minutes: float | None = None,
) -> Event:
    at = START + timedelta(minutes=minutes if minutes is not None else index * 5)
    return Event(
        event_id=f"e{index}",
        occurred_at=at,
        domain="example.com",
        category=category,
        transition=transition,
        dwell_seconds=dwell,
        source="import",
    )


def examples_for(dwells: list[float | None], **kwargs):
    events = [event(i, d) for i, d in enumerate(dwells)]
    return attention_examples(events, timeout_seconds=TIMEOUT, **kwargs)


class TestLeakage:
    def test_a_visit_is_not_in_its_own_median(self) -> None:
        # Ten visits at 10s, then one at 500s. If the spike were inside its own median the
        # comparison would be against a raised threshold; it must be against the flat ten.
        examples = examples_for([10.0] * 10 + [500.0], min_prior=10, trailing=20)
        assert len(examples) == 1
        assert examples[0].label.outcome is True

    def test_appending_later_visits_changes_no_earlier_example(self) -> None:
        short = examples_for([10.0] * 15, min_prior=10)
        long = examples_for([10.0] * 15 + [900.0, 900.0], min_prior=10)
        assert len(long) > len(short)
        for before, after in zip(short, long, strict=False):
            assert before.label == after.label
            assert before.row.values == after.row.values


class TestLabels:
    def test_nothing_is_emitted_before_the_minimum_history(self) -> None:
        assert examples_for([10.0] * 9, min_prior=10) == []

    def test_a_visit_without_dwell_is_skipped_not_imputed(self) -> None:
        # A missing duration is not a short one. D51: never invent a value.
        with_gap = examples_for([10.0] * 10 + [None, 20.0], min_prior=10)
        assert len(with_gap) == 1
        assert with_gap[0].label.outcome is True

    def test_a_flat_series_ties_and_strict_comparison_makes_it_negative(self) -> None:
        examples = examples_for([10.0] * 20, min_prior=10)
        assert examples
        assert not any(example.label.outcome for example in examples)

    def test_the_split_is_balanced_on_an_alternating_series(self) -> None:
        # The property the whole target rests on: a median split is ~50% by construction.
        # block_volume claimed this and measured 36-47% (D90); here it should hold.
        dwells: list[float | None] = [5.0, 50.0] * 30
        examples = examples_for(dwells, min_prior=10)
        assert len(examples) > 20
        positives = sum(1 for example in examples if example.label.outcome)
        assert 0.4 <= positives / len(examples) <= 0.6

    def test_each_category_gets_its_own_median(self) -> None:
        # A category that is always slow must not be judged against a fast one's median.
        events = []
        for index in range(30):
            events.append(event(index, 5.0, category="news", minutes=index * 5))
            events.append(event(1000 + index, 300.0, category="video", minutes=index * 5 + 1))
        examples = attention_examples(events, timeout_seconds=TIMEOUT, min_prior=10)
        by_subject = {example.label.subject for example in examples}
        assert by_subject == {"news", "video"}
        # Both are flat within themselves, so neither should ever exceed its own median.
        assert not any(example.label.outcome for example in examples)


class TestFeatures:
    def test_rows_carry_the_declared_set_and_no_nulls(self) -> None:
        for example in examples_for([10.0, 40.0] * 15, min_prior=10):
            assert example.row.feature_set == ATTENTION_FEATURE_SET
            assert set(example.row.values) == set(FEATURE_SETS[ATTENTION_FEATURE_SET])
            assert all(value is not None for value in example.row.values.values())

    def test_it_is_declared_full_compat_because_it_needs_dwell(self) -> None:
        # The duration trap. Marking this `history` would claim the extension can compute
        # it today, which it cannot without the tabs permission.
        example = examples_for([10.0, 40.0] * 15, min_prior=10)[0]
        assert example.row.compat == "full"
        assert example.label.target == ATTENTION_TARGET

    def test_transition_reaches_the_features(self) -> None:
        # `transition` has been collected since T1 and read by no feature until now.
        events = [
            event(index, 10.0, transition="typed" if index % 2 else "link")
            for index in range(30)
        ]
        examples = attention_examples(events, timeout_seconds=TIMEOUT, min_prior=10)
        flags = {example.row.values["arrivedTyped"] for example in examples}
        assert flags == {0.0, 1.0}

    def test_hour_is_cyclic(self) -> None:
        examples = examples_for([10.0, 40.0] * 15, min_prior=10)
        for example in examples:
            sin = example.row.values["hourSin"]
            cos = example.row.values["hourCos"]
            assert sin is not None and cos is not None
            assert sin * sin + cos * cos == pytest.approx(1.0)

    def test_rows_fit_the_declared_design_matrix(self) -> None:
        rows = [example.row for example in examples_for([10.0, 40.0] * 15, min_prior=10)]
        preprocessor = fit_preprocessor(rows)
        assert preprocessor.feature_set == ATTENTION_FEATURE_SET
        assert len(preprocessor.transform(rows[0])) == len(
            design_columns(ATTENTION_FEATURE_SET)
        )
