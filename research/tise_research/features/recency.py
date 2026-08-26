"""Recency features — how long since this category was last seen.

The first feature implemented in both languages, and therefore the first real test of the
parity mechanism. `extension/src/features/recency.ts` is the mirror.

**Every function here takes `window_end` and filters strictly before it.** That is the
structural defence against leakage: it is not possible to write a leaking feature without
deleting that line, and `test_recency.py` asserts it by appending future events and
checking that no value moves.

Returning `None` for "never seen" rather than a large number is deliberate. A sentinel
like 9999 hours is a number the model will happily fit a coefficient to, and it means
something categorically different from a real measurement. The consumer decides how to
encode absence; this layer refuses to invent it.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from tise_research.features.events import Event

__all__ = ["hours_since_first_seen", "hours_since_last_seen"]

SECONDS_PER_HOUR = 3600.0


def hours_since_last_seen(
    events: Sequence[Event], category: str, *, window_end: datetime
) -> float | None:
    """Hours since the most recent event in `category` strictly before `window_end`.

    Returns None when the category has never been seen in that window. Note that a
    category can be absent here even though it produced the label being computed: the
    label closes at the end of its session, and an event *at* that instant is not
    strictly before it.
    """
    if window_end.tzinfo is None:
        raise ValueError(
            "naive window_end: an aware instant is required, or the leakage guard "
            "compares wrongly and silently stops guarding"
        )

    latest: datetime | None = None
    for event in events:
        if event.occurred_at >= window_end:  # leakage guard
            continue
        if event.category != category:
            continue
        if latest is None or event.occurred_at > latest:
            latest = event.occurred_at

    if latest is None:
        return None
    return (window_end - latest).total_seconds() / SECONDS_PER_HOUR


def hours_since_first_seen(
    events: Sequence[Event], category: str, *, window_end: datetime
) -> float | None:
    """Hours since the category was **first** seen, strictly before `window_end`.

    How long this has been a thing the person does, as against how recently they did it.
    A category first seen an hour ago and one first seen a year ago behave differently
    even when `hours_since_last_seen` is identical.
    """
    if window_end.tzinfo is None:
        raise ValueError("naive window_end: an aware instant is required")

    earliest: datetime | None = None
    for event in events:
        if event.occurred_at >= window_end:  # leakage guard
            continue
        if event.category != category:
            continue
        if earliest is None or event.occurred_at < earliest:
            earliest = event.occurred_at

    if earliest is None:
        return None
    return (window_end - earliest).total_seconds() / SECONDS_PER_HOUR
