"""`block_volume` labels and `bs_1` features (D91, T21).

The module claims leakage is *structural* — labels and features for a block are emitted
before that block joins any state, so no expression in it could read the answer. That claim
is worth exactly as much as a test that would fail if it stopped being true, which is what
this file is. "Cannot by construction" is a statement about code, and code changes.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from tise_research.features.block_labels import (
    BLOCK_FEATURE_SET,
    BLOCK_TARGET,
    BlockIndex,
    block_volume_examples,
)
from tise_research.features.blocks import blocks_from_events
from tise_research.features.events import Event
from tise_research.features.vector import FEATURE_SETS
from tise_research.models.prep import design_columns, fit_preprocessor

START = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def event(day: int, category: str = "video", index: int = 0) -> Event:
    at = START + timedelta(days=day, minutes=index * 7)
    return Event(
        event_id=f"{category}-{day}-{index}",
        occurred_at=at,
        domain="example.com",
        category=category,
        transition="link",
        dwell_seconds=None,
        source="import",
    )


def corpus(counts: list[int], category: str = "video") -> list[Event]:
    """One event list where `counts[day]` events fall on day `day`."""
    return [
        event(day, category, index)
        for day, count in enumerate(counts)
        for index in range(count)
    ]


def examples_for(counts: list[int], **kwargs: int):
    blocks = blocks_from_events(corpus(counts), tz=UTC, granularity="day")
    return block_volume_examples(blocks, kind="day", **kwargs)


class TestLeakage:
    def test_the_block_being_predicted_is_not_in_its_own_median(self) -> None:
        # Nine flat days then a spike. If the spike were inside its own trailing median
        # the median would rise with it and the label could go either way. It cannot.
        counts = [2] * 9 + [50]
        examples = examples_for(counts, min_prior=6, trailing=10)
        assert examples
        assert examples[-1].label.outcome is True
        # Every flat day ties its median of 2 and loses under strict `>`.
        assert sum(1 for e in examples if e.label.outcome) == 1

    def test_appending_a_later_block_changes_no_earlier_label(self) -> None:
        # The leakage test in the shape it takes everywhere else in this repository.
        short = examples_for([3] * 12)
        long = examples_for([3] * 12 + [99, 99])
        assert len(long) > len(short)
        for before, after in zip(short, long, strict=False):
            assert before.label == after.label
            assert before.row.values == after.row.values

    def test_prev_above_describes_the_previous_block_not_this_one(self) -> None:
        # A spike then a collapse. On the collapse day prevAbove must be 1 (yesterday was
        # high) while the label is False (today is not). If they ever agree, the feature
        # is reading the block it is predicting.
        # The trailing 1 matters: a zero day at the very end of the corpus is *outside*
        # the observed span and so is not a block at all. It has to be bracketed by
        # activity to exist as a measured zero.
        counts = [2] * 8 + [50, 0, 1]
        examples = examples_for(counts, min_prior=6, trailing=10)
        collapse = next(
            example
            for example in examples
            if example.label.window_end.date() == (START + timedelta(days=10)).date()
        )
        assert collapse.row.values["prevAbove"] == 1.0
        assert collapse.label.outcome is False


class TestLabels:
    def test_nothing_is_emitted_before_the_minimum_history(self) -> None:
        examples = examples_for([3] * 10, min_prior=6, trailing=10)
        # Days 0-5 build history; labels start once six prior blocks exist.
        assert len(examples) == 4

    def test_a_sparse_topic_is_not_labelled(self) -> None:
        events = corpus([3] * 12) + [event(0, "travel"), event(6, "travel")]
        blocks = blocks_from_events(events, tz=UTC, granularity="day")
        examples = block_volume_examples(blocks, kind="day")
        assert {example.label.subject for example in examples} == {"video"}

    def test_labels_carry_the_target_and_a_block_identity(self) -> None:
        example = examples_for([3] * 12)[0]
        assert example.label.target == BLOCK_TARGET
        assert example.label.session_id.endswith("-day")

    def test_strict_comparison_makes_a_tie_negative(self) -> None:
        # D91 fixed `>` over `>=` because "more than usual" is not "at least usual".
        # A perfectly flat series ties every block and must score zero positives.
        examples = examples_for([4] * 12)
        assert examples
        assert not any(example.label.outcome for example in examples)


class TestFeatures:
    def test_every_row_carries_the_declared_set(self) -> None:
        for example in examples_for([3] * 12):
            assert example.row.feature_set == BLOCK_FEATURE_SET
            assert set(example.row.values) == set(FEATURE_SETS[BLOCK_FEATURE_SET])

    def test_only_days_since_above_may_be_null(self) -> None:
        # prep.py declares exactly one nullable feature for bs_1. Any other null is a bug
        # and `raw_row` raises rather than imputing it, so this pins the contract.
        for example in examples_for([3] * 12):
            for name, value in example.row.values.items():
                if name != "daysSinceAbove":
                    assert value is not None, name

    def test_day_of_week_is_cyclic(self) -> None:
        # D86 measured the day-of-week pattern as non-monotone, so a plain integer cannot
        # represent it. sin/cos must put Sunday next to Monday rather than six apart.
        examples = examples_for([3] * 20)
        by_weekday = {
            example.label.window_end.weekday(): (
                example.row.values["dayOfWeekSin"],
                example.row.values["dayOfWeekCos"],
            )
            for example in examples
        }
        assert len(by_weekday) >= 7
        for sin, cos in by_weekday.values():
            assert sin is not None and cos is not None
            assert sin * sin + cos * cos == pytest.approx(1.0)

    def test_the_rows_fit_the_declared_design_matrix(self) -> None:
        rows = [example.row for example in examples_for([3] * 14)]
        preprocessor = fit_preprocessor(rows)
        assert preprocessor.feature_set == BLOCK_FEATURE_SET
        assert len(preprocessor.transform(rows[0])) == len(
            design_columns(BLOCK_FEATURE_SET)
        )


class TestIndex:
    def test_it_returns_the_row_that_was_produced_with_the_label(self) -> None:
        examples = examples_for([3] * 12)
        index = BlockIndex.from_examples(examples)
        for example in examples:
            assert index.row_for(example.label) is example.row

    def test_a_missing_row_is_loud_rather_than_recomputed(self) -> None:
        # Recomputing from a label alone is exactly what would reintroduce the leakage
        # this design removes, so the lookup refuses instead of falling back.
        examples = examples_for([3] * 12)
        index = BlockIndex.from_examples(examples[:1])
        with pytest.raises(KeyError, match="one pass"):
            index.row_for(examples[-1].label)
