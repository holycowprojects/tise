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
    "Block",
    "BlockKey",
    "BlockType",
    "block_key_for",
    "blocks_from_events",
    "category_counts",
    "complete_blocks",
]

BlockType = Literal["weekday", "weekend"]

#: Ordered so reports iterate the two types the same way everywhere.
BLOCK_TYPES: tuple[BlockType, ...] = ("weekday", "weekend")

#: Days in each block, used to decide whether a block was fully observed.
BLOCK_LENGTH_DAYS: dict[BlockType, int] = {"weekday": 5, "weekend": 2}


@dataclass(frozen=True, slots=True, order=True)
class BlockKey:
    """Identity of one block. Ordered, so sorting gives calendar order.

    `iso_year` before `iso_week` before `kind` puts a week's weekday block ahead of its
    weekend block, which is the order the prediction loop runs in.
    """

    iso_year: int
    iso_week: int
    kind: BlockType

    def __str__(self) -> str:
        return f"{self.iso_year}-W{self.iso_week:02d}-{self.kind}"


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


def block_key_for(moment: datetime, tz: tzinfo) -> BlockKey:
    """Which block a moment belongs to, in `tz`.

    Raises on a naive datetime rather than assuming UTC. `Event` already refuses naive
    timestamps; this keeps the same rule at the one other place a datetime enters.
    """
    if moment.tzinfo is None:
        raise ValueError(
            "naive datetime has no block: a block boundary is local, so the timezone "
            "has to be known rather than assumed"
        )
    local = moment.astimezone(tz)
    iso_year, iso_week, iso_weekday = local.date().isocalendar()
    # isocalendar() numbers Monday 1 through Sunday 7.
    kind: BlockType = "weekday" if iso_weekday <= 5 else "weekend"
    return BlockKey(iso_year=iso_year, iso_week=iso_week, kind=kind)


def _week_keys(first: BlockKey, last: BlockKey, tz: tzinfo) -> list[BlockKey]:
    """Every block key from `first` to `last` inclusive, of `first`'s kind.

    Walks actual Mondays rather than incrementing a week number, so the 52/53-week years
    and the week straddling New Year are handled by the calendar instead of by arithmetic.
    """
    start = date.fromisocalendar(first.iso_year, first.iso_week, 1)
    end = date.fromisocalendar(last.iso_year, last.iso_week, 1)
    keys: list[BlockKey] = []
    current = start
    while current <= end:
        iso_year, iso_week, _ = current.isocalendar()
        keys.append(BlockKey(iso_year=iso_year, iso_week=iso_week, kind=first.kind))
        current += timedelta(days=7)
    return keys


def blocks_from_events(
    events: Iterable[Event], *, tz: tzinfo, fill_gaps: bool = True
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
        grouped[block_key_for(event.occurred_at, tz)].append(event)

    keys = set(grouped)
    if fill_gaps and grouped:
        for kind in BLOCK_TYPES:
            of_kind = sorted(key for key in grouped if key.kind == kind)
            if len(of_kind) >= 2:
                keys |= set(_week_keys(of_kind[0], of_kind[-1], tz))

    blocks: list[Block] = []
    for key in sorted(keys):
        items = sorted(grouped.get(key, []), key=lambda event: event.occurred_at)
        if items:
            first_at, last_at = items[0].occurred_at, items[-1].occurred_at
        else:
            # An empty block still needs a position in time, for novelty's lookback and
            # for ordering. Use the block's own calendar start.
            monday = date.fromisocalendar(key.iso_year, key.iso_week, 1)
            offset = 0 if key.kind == "weekday" else 5
            first_at = last_at = datetime.combine(
                monday + timedelta(days=offset), time.min, tzinfo=tz
            )
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
    for kind in BLOCK_TYPES:
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
