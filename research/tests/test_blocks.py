"""Blocks, and the two things about them that would silently corrupt every label.

**The boundary is local.** Friday 23:00 in Kolkata is Friday 17:30 UTC, and Saturday 02:00
in Kolkata is Friday 20:30 UTC. Bucketing on UTC weekday puts one of those in the wrong
block, and the error is invisible in aggregate — it just makes the weekend look busier or
quieter than it was, for everyone far enough from Greenwich.

**An empty block is a zero, not a gap.** A weekend nobody browsed is a real observation.
Dropping it removes a true zero from the median, pushing every subsequent median up, and
deletes a label a person would have found informative. This cost 6 labels on Edge before it
was fixed, and it was found by the label yield being implausibly low rather than by a test —
so the tests are here now.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from tise_research.eval.candidates import block_volume_stats
from tise_research.features.blocks import (
    Block,
    BlockKey,
    block_key_for,
    blocks_from_events,
    category_counts,
    complete_blocks,
)
from tise_research.features.events import Event

KOLKATA = timezone(timedelta(hours=5, minutes=30))
#: 2026-06-01 is a Monday.
MONDAY = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def event(at: datetime, category: str = "video", domain: str = "example.com") -> Event:
    return Event(
        event_id=f"{category}-{at.isoformat()}",
        occurred_at=at,
        domain=domain,
        category=category,
        transition="link",
        dwell_seconds=None,
        source="import",
    )


class TestBoundaries:
    def test_monday_to_friday_is_the_weekday_block(self) -> None:
        for offset in range(5):
            key = block_key_for(MONDAY + timedelta(days=offset), UTC)
            assert key.kind == "weekday", offset

    def test_saturday_and_sunday_are_the_weekend_block(self) -> None:
        for offset in (5, 6):
            key = block_key_for(MONDAY + timedelta(days=offset), UTC)
            assert key.kind == "weekend", offset

    def test_the_weekend_shares_its_week_with_the_weekday_block(self) -> None:
        # ISO weeks start Monday, so Mon-Fri and the Sat/Sun after it are one week. If
        # they were not, Friday night would predict the *previous* weekend.
        weekday = block_key_for(MONDAY, UTC)
        weekend = block_key_for(MONDAY + timedelta(days=5), UTC)
        assert (weekday.iso_year, weekday.iso_week) == (
            weekend.iso_year,
            weekend.iso_week,
        )

    def test_the_boundary_moves_with_the_timezone(self) -> None:
        # Friday 20:30 UTC is Saturday 02:00 in Kolkata. The same instant belongs to
        # different blocks for different people, which is the whole reason tz is required.
        instant = datetime(2026, 6, 5, 20, 30, tzinfo=UTC)
        assert block_key_for(instant, UTC).kind == "weekday"
        assert block_key_for(instant, KOLKATA).kind == "weekend"

    def test_a_naive_datetime_is_refused_rather_than_assumed_utc(self) -> None:
        with pytest.raises(ValueError, match="naive"):
            block_key_for(datetime(2026, 6, 1, 12, 0), UTC)

    def test_keys_sort_into_calendar_order_with_weekday_first(self) -> None:
        weekday = BlockKey(2026, 23, "weekday")
        weekend = BlockKey(2026, 23, "weekend")
        assert sorted([weekend, weekday]) == [weekday, weekend]


class TestGapFilling:
    def test_a_silent_week_becomes_a_zero_block(self) -> None:
        events = [
            event(MONDAY),
            event(MONDAY + timedelta(days=21)),  # three weeks later
        ]
        blocks = blocks_from_events(events, tz=UTC)
        weekday = [block for block in blocks if block.kind == "weekday"]
        assert len(weekday) == 4
        assert [len(block.events) for block in weekday] == [1, 0, 0, 1]

    def test_gaps_can_be_turned_off(self) -> None:
        events = [event(MONDAY), event(MONDAY + timedelta(days=21))]
        blocks = blocks_from_events(events, tz=UTC, fill_gaps=False)
        assert len([b for b in blocks if b.kind == "weekday"]) == 2

    def test_nothing_is_invented_outside_the_observed_span(self) -> None:
        # "Nothing happened" and "nobody was looking" are different, and only the first
        # is a zero. Blocks before the first event or after the last are the second.
        events = [event(MONDAY), event(MONDAY + timedelta(days=7))]
        blocks = blocks_from_events(events, tz=UTC)
        assert len(blocks) == 2

    def test_an_empty_block_still_has_a_position_in_time(self) -> None:
        events = [event(MONDAY), event(MONDAY + timedelta(days=14))]
        blocks = blocks_from_events(events, tz=UTC)
        middle = [b for b in blocks if b.kind == "weekday"][1]
        assert not middle.events
        assert middle.first_at < blocks[-1].first_at


class TestCompleteBlocks:
    def test_the_first_and_last_of_each_type_are_dropped(self) -> None:
        # A corpus starts and ends mid-week, so those two are partial. A half-length
        # block has a systematically lower count, and left in the median it looks
        # exactly like a behaviour change.
        events = [event(MONDAY + timedelta(days=7 * week)) for week in range(5)]
        blocks = blocks_from_events(events, tz=UTC)
        trimmed = complete_blocks(blocks, tz=UTC)
        assert len(blocks) == 5
        assert len(trimmed) == 3

    def test_too_few_blocks_yields_none_rather_than_something_arbitrary(self) -> None:
        events = [event(MONDAY), event(MONDAY + timedelta(days=7))]
        assert complete_blocks(blocks_from_events(events, tz=UTC), tz=UTC) == []

    def test_a_quiet_middle_block_is_kept(self) -> None:
        # Dropping quiet blocks would bias the median upward, which is the same mistake
        # as keeping partial ones, in the other direction.
        events = [event(MONDAY + timedelta(days=7 * week)) for week in (0, 1, 3, 4)]
        trimmed = complete_blocks(blocks_from_events(events, tz=UTC), tz=UTC)
        assert any(not block.events for block in trimmed)


class TestCounts:
    def test_counts_events_per_category(self) -> None:
        block = Block(
            key=BlockKey(2026, 23, "weekday"),
            events=(event(MONDAY), event(MONDAY, "dev"), event(MONDAY)),
            first_at=MONDAY,
            last_at=MONDAY,
        )
        assert category_counts(block) == {"video": 2, "dev": 1}


class TestNoLeakage:
    def test_a_block_is_never_in_its_own_median(self) -> None:
        """The rule everything rests on, asserted directly.

        A topic is quiet for eight blocks and then explodes. If the final block were in
        its own trailing median, the median would rise with it and the label would be
        wrong. With the guard, the spike is unambiguously above a median of quiet blocks.
        """
        events: list[Event] = []
        for week in range(10):
            count = 50 if week == 9 else 2
            for index in range(count):
                events.append(
                    event(MONDAY + timedelta(days=7 * week, minutes=index * 90))
                )
        blocks = blocks_from_events(events, tz=UTC)
        stats = block_volume_stats(blocks, kind="weekday", min_prior=2, trailing=10)

        assert stats.labels > 0
        # Every quiet block ties its median of 2 and loses under `>`; only the spike wins.
        assert stats.base_rate_strict is not None
        assert stats.base_rate_strict == pytest.approx(1 / stats.labels)

    def test_ties_are_counted_and_split_the_two_rules(self) -> None:
        # The measurement D88's 50/50 claim depends on. A flat series ties every block,
        # so `>` scores 0% and `>=` scores 100% — the two rules bracket the truth.
        events = [
            event(MONDAY + timedelta(days=7 * week, minutes=index * 90))
            for week in range(8)
            for index in range(3)
        ]
        blocks = blocks_from_events(events, tz=UTC)
        stats = block_volume_stats(blocks, kind="weekday", min_prior=2, trailing=10)

        assert stats.labels > 0
        assert stats.tie_rate == 1.0
        assert stats.base_rate_strict == 0.0
        assert stats.base_rate_inclusive == 1.0

    def test_a_sparse_topic_is_rejected_rather_than_predicted_against_zero(self) -> None:
        # D88's known flaw: with a median of 0, "above the median" is "did it appear",
        # and the 50/50 property is gone. The qualifying rule is what keeps that out.
        events = [
            event(MONDAY + timedelta(days=7 * week, minutes=index * 90))
            for week in range(10)
            for index in range(3)
        ]
        # Sparse but present from the start, so it accumulates enough history to be
        # *evaluated* and then rejected. Appearing only at the end would mean it never
        # reached the minimum and was never considered, which tests nothing.
        events.append(event(MONDAY, "travel"))
        events.append(event(MONDAY + timedelta(days=35), "travel"))
        blocks = blocks_from_events(events, tz=UTC)
        # min_prior=6, because "at least half" of a two-block window is satisfied by a
        # single appearance. The rule only distinguishes sparse from regular once the
        # window is long enough to have a shape.
        stats = block_volume_stats(blocks, kind="weekday", min_prior=6, trailing=10)

        assert stats.rejected_sparse >= 1
        assert stats.qualifying_topics == 1
        assert stats.zero_median_rate == 0.0
