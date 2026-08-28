"""Weekday and weekend blocks — the unit `block_volume` predicts over (D88).

A **block** is one person's Monday-to-Friday, or one Saturday-to-Sunday, in one calendar
week. Friday night predicts the weekend; Sunday night predicts the week. It replaces the
per-session unit, which produced 6-7 predictions a day that nobody wanted.

**Local time, not UTC.** A block boundary is a fact about someone's week, and "Saturday"
means Saturday where they are. Bucketing by UTC weekday would move the boundary by hours
and, for anyone far enough east or west, put Friday evening browsing in the weekend block.
The timezone is therefore an explicit argument with no default — passing one is a decision,
and defaulting it silently would be the kind of thing that is discovered much later.

**ISO weeks do the work.** ISO weeks start on Monday, so Monday-to-Friday and the Saturday
and Sunday that follow it share one `(iso_year, iso_week)`. Weekday block *n* and weekend
block *n* are the same week, in order, with no arithmetic to get wrong at year boundaries —
`date.isocalendar()` already handles the week that straddles New Year.

**Not yet mirrored in TypeScript.** The parity contract binds features the extension
computes; nothing here ships until T21, and it gains a TS twin and an oracle entry then.
Recorded so the omission is deliberate rather than forgotten.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo
from typing import Literal

from tise_research.features.events import Event

__all__ = [
    "BLOCK_TYPES",
    "BLOCK_TYPES_BY_GRANULARITY",
    "Block",
    "BlockKey",
    "BlockType",
    "Granularity",
    "block_key_for",
    "blocks_from_events",
    "category_counts",
    "complete_blocks",
]

BlockType = Literal["weekday", "weekend", "day"]
Granularity = Literal["week", "day"]

#: Which block types each granularity produces. Reports iterate these in order.
BLOCK_TYPES_BY_GRANULARITY: dict[Granularity, tuple[BlockType, ...]] = {
    "week": ("weekday", "weekend"),
    "day": ("day",),
}

#: The weekly pair, kept as a name because most callers still mean exactly these two.
BLOCK_TYPES: tuple[BlockType, ...] = BLOCK_TYPES_BY_GRANULARITY["week"]

#: Days in each block, used to decide whether a block was fully observed.
BLOCK_LENGTH_DAYS: dict[BlockType, int] = {"weekday": 5, "weekend": 2, "day": 1}


@dataclass(frozen=True, slots=True, order=True)
class BlockKey:
    """Identity of one block: the calendar day it starts on, and what kind it is.

    Keyed on the **start date** rather than an ISO week number, so one scheme covers a
    Monday-to-Friday block, a weekend, and a single day without special cases. Ordering by
    `(start, kind)` gives calendar order for free, and within a week the weekday block
    (starting Monday) sorts ahead of the weekend block (starting Saturday) — which is the
    order the prediction loop runs in.
    """

    start: date
    kind: BlockType

    def __str__(self) -> str:
        return f"{self.start.isoformat()}-{self.kind}"


@dataclass(frozen=True, slots=True)
class Block:
    """One block and the events that fell inside it."""

    key: BlockKey
    events: tuple[Event, ...]
    first_at: datetime
    last_at: datetime

    @property
    def kind(self) -> BlockType:
        return self.key.kind

    @property
    def active_days(self) -> int:
        """Distinct local dates with at least one event. Used to spot partial blocks."""
        return len({event.occurred_at.date() for event in self.events})


def block_key_for(
    moment: datetime, tz: tzinfo, granularity: Granularity = "week"
) -> BlockKey:
    """Which block a moment belongs to, in `tz`.

    Raises on a naive datetime rather than assuming UTC. `Event` already refuses naive
    timestamps; this keeps the same rule at the one other place a datetime enters.
    """
    if moment.tzinfo is None:
        raise ValueError(
            "naive datetime has no block: a block boundary is local, so the timezone "
            "has to be known rather than assumed"
        )
    local = moment.astimezone(tz).date()
    if granularity == "day":
        return BlockKey(start=local, kind="day")

    iso_weekday = local.isocalendar()[2]  # Monday 1 through Sunday 7.
    if iso_weekday <= 5:
        return BlockKey(start=local - timedelta(days=iso_weekday - 1), kind="weekday")
    return BlockKey(start=local - timedelta(days=iso_weekday - 6), kind="weekend")


def _span_keys(first: BlockKey, last: BlockKey) -> list[BlockKey]:
    """Every block key from `first` to `last` inclusive, of `first`'s kind.

    Walks real calendar dates rather than incrementing a week number, so 52/53-week years
    and the week straddling New Year are handled by the calendar rather than by arithmetic.
    """
    step = timedelta(days=1 if first.kind == "day" else 7)
    keys: list[BlockKey] = []
    current = first.start
    while current <= last.start:
        keys.append(BlockKey(start=current, kind=first.kind))
        current += step
    return keys


def blocks_from_events(
    events: Iterable[Event],
    *,
    tz: tzinfo,
    granularity: Granularity = "week",
    fill_gaps: bool = True,
) -> list[Block]:
    """Group events into blocks, in calendar order.

    **A block with no events is a real observation of zero, not a missing block**, and
    `fill_gaps` exists because getting this wrong costs labels and biases the median. If
    someone browsed nothing all weekend, that weekend genuinely had zero activity — the
    corpus covers that period either way. Dropping it would remove a true zero from the
    median, pushing the median up, and would also delete a label that a person would have
    found informative ("you were away last weekend").

    Only blocks *outside* the observed span are absent, because those really were not
    observed. The distinction is between "nothing happened" and "nobody was looking", which
    is D72's `expired` rule in yet another place.
    """
    grouped: dict[BlockKey, list[Event]] = defaultdict(list)
    for event in events:
        grouped[block_key_for(event.occurred_at, tz, granularity)].append(event)

    keys = set(grouped)
    if fill_gaps and grouped:
        for kind in BLOCK_TYPES_BY_GRANULARITY[granularity]:
            of_kind = sorted(key for key in grouped if key.kind == kind)
            if len(of_kind) >= 2:
                keys |= set(_span_keys(of_kind[0], of_kind[-1]))

    blocks: list[Block] = []
    for key in sorted(keys):
        items = sorted(grouped.get(key, []), key=lambda event: event.occurred_at)
        if items:
            first_at, last_at = items[0].occurred_at, items[-1].occurred_at
        else:
            # An empty block still needs a position in time, for novelty's lookback and
            # for ordering. Its own calendar start is the honest choice.
            first_at = last_at = datetime.combine(key.start, time.min, tzinfo=tz)
        blocks.append(
            Block(key=key, events=tuple(items), first_at=first_at, last_at=last_at)
        )
    return blocks


def complete_blocks(blocks: Sequence[Block], *, tz: tzinfo) -> list[Block]:
    """Drop the first and last block of each type, which are almost certainly partial.

    A corpus starts and ends mid-week. The first weekend block may hold only its Sunday and
    the last only its Saturday, and a half-length block has a systematically lower count
    than a whole one. Left in, those two would sit in the same median as full blocks and
    drag it down — a measurement artefact that looks exactly like a behaviour change.

    Blocks in the middle are kept whatever their activity: a quiet week is real data, and
    dropping quiet blocks would bias the median upward, which is the same mistake in the
    other direction.
    """
    kept: list[Block] = []
    for kind in {block.kind for block in blocks}:
        of_kind = [block for block in blocks if block.kind == kind]
        if len(of_kind) <= 2:
            # Nothing survives trimming both ends. Return none of this type rather than
            # something arbitrary — the caller reports it as insufficient history.
            continue
        kept.extend(of_kind[1:-1])
    return sorted(kept, key=lambda block: block.key)


def category_counts(block: Block) -> dict[str, int]:
    """Events per category inside one block."""
    counts: dict[str, int] = defaultdict(int)
    for event in block.events:
        counts[event.category] += 1
    return dict(counts)
