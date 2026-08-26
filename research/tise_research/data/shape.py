"""Shape measurements over a stream of visit times.

Every function here is pure: same input, same output, no clock, no filesystem. That is
what lets T1's numbers be regenerated years later, and what lets the TypeScript port at
T9 be compared against them.

The session timeout is *found*, not chosen. Real browsing gaps are bimodal — seconds
within a session, hours between them — and the boundary belongs in the trough. Picking
30 minutes because it is a round number is exactly the kind of undefended constant the
audit of the original documents flagged.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta, tzinfo

__all__ = [
    "LabelStats",
    "ascii_histogram",
    "estimate_return_24h_labels",
    "estimate_return_24h_labels_by_session",
    "estimate_return_24h_labels_by_window",
    "find_gap_valley",
    "inter_visit_gaps",
    "percentiles",
    "sessionise",
    "visits_per_day",
]


def inter_visit_gaps(times: Sequence[datetime]) -> list[float]:
    """Seconds between consecutive visits. Input is sorted first.

    Chrome's `visits` table is ordered in practice but not by contract, and a single
    out-of-order row produces a negative gap that silently poisons the distribution.
    """
    ordered = sorted(times)
    return [
        (later - earlier).total_seconds()
        for earlier, later in zip(ordered, ordered[1:], strict=False)
    ]


def percentiles(values: Sequence[float], points: Iterable[float]) -> dict[float, float | None]:
    """Linear-interpolated percentiles.

    Returns None for an empty input rather than 0.0 — zero is a measurement, absence
    is not, and a benchmark table must never blur the two.
    """
    ordered = sorted(values)
    result: dict[float, float | None] = {}
    for point in points:
        if not ordered:
            result[point] = None
            continue
        position = (point / 100.0) * (len(ordered) - 1)
        low = math.floor(position)
        high = math.ceil(position)
        if low == high:
            result[point] = ordered[low]
        else:
            weight = position - low
            result[point] = ordered[low] * (1 - weight) + ordered[high] * weight
    return result


def visits_per_day(
    times: Sequence[datetime], *, tz: tzinfo = UTC
) -> dict[object, int]:
    """Visit count per calendar day. Days with no browsing are absent, not zero."""
    counts: dict[object, int] = defaultdict(int)
    for moment in times:
        counts[moment.astimezone(tz).date()] += 1
    return dict(counts)


def sessionise(
    times: Sequence[datetime], *, timeout_seconds: float
) -> list[list[datetime]]:
    """Group visits into sessions, splitting on any gap **strictly greater** than the
    timeout.

    The strictness is stated here because the TypeScript port at T9 must reproduce this
    boundary exactly. A `>` versus `>=` disagreement is invisible until the parity suite
    catches it, and would shift every session-derived feature by one visit.
    """
    ordered = sorted(times)
    if not ordered:
        return []

    sessions: list[list[datetime]] = [[ordered[0]]]
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if (current - previous).total_seconds() > timeout_seconds:
            sessions.append([current])
        else:
            sessions[-1].append(current)
    return sessions


def find_gap_valley(gaps: Sequence[float], *, bins: int = 40) -> float | None:
    """Find the trough between the two modes of the log-gap distribution, in seconds.

    Returns None when the distribution is unimodal or too narrow to have a trough — in
    which case there is no empirical session boundary, and the honest thing is to say so
    rather than fall back to a number we liked the look of.
    """
    positive = [gap for gap in gaps if gap > 0]
    if len(positive) < 20:
        return None

    logs = [math.log10(gap) for gap in positive]
    low, high = min(logs), max(logs)
    if high - low < 0.5:  # under half an order of magnitude: one mode, no trough
        return None

    width = (high - low) / bins
    counts = [0] * bins
    for value in logs:
        index = min(int((value - low) / width), bins - 1)
        counts[index] += 1

    # Three-bin moving average: raw histograms of real data are spiky enough that the
    # deepest single bin is often noise rather than the boundary.
    smooth = [
        (counts[max(0, i - 1)] + counts[i] + counts[min(bins - 1, i + 1)]) / 3
        for i in range(bins)
    ]

    first_peak = max(range(bins), key=lambda i: smooth[i])
    separation = max(3, bins // 8)
    far = [i for i in range(bins) if abs(i - first_peak) >= separation]
    if not far:
        return None

    second_peak = max(far, key=lambda i: smooth[i])
    if smooth[second_peak] <= 0:
        return None

    left, right = sorted((first_peak, second_peak))

    # When the trough is flat — and between two well-separated modes it usually is,
    # because nothing happens there at all — plain argmin returns its left edge, which
    # puts the boundary right up against the within-session mode. Take the middle of
    # the tied region instead.
    depth = min(smooth[left : right + 1])
    tied = [
        i for i in range(left, right + 1) if math.isclose(smooth[i], depth, rel_tol=1e-12)
    ]
    trough = tied[len(tied) // 2]

    # A dip that is not much lower than its shoulders is not a boundary.
    if smooth[trough] >= 0.5 * min(smooth[first_peak], smooth[second_peak]):
        return None

    return 10 ** (low + (trough + 0.5) * width)


@dataclass(frozen=True, slots=True)
class LabelStats:
    """How many `return_24h` examples real browsing actually yields.

    This carries the T1 gate. If `labels_per_week * 8` is far below ~300, the primary
    prediction target changes before any extension code exists.
    """

    total: int
    positives: int
    positive_rate: float | None
    span_days: float
    labels_per_week: float
    per_category: dict[str, int] = field(default_factory=dict)


_EMPTY_STATS = LabelStats(0, 0, None, 0.0, 0.0, {})


def _index_events(
    events: Sequence[tuple[datetime, str]],
) -> tuple[dict[str, list[datetime]], float]:
    """Group event times by category (each list sorted) and measure the observed span."""
    by_category: dict[str, list[datetime]] = defaultdict(list)
    for moment, category in events:
        by_category[category].append(moment)
    for moments in by_category.values():
        moments.sort()

    ordered = sorted(moment for moment, _ in events)
    span_days = (
        (ordered[-1] - ordered[0]).total_seconds() / 86_400 if len(ordered) > 1 else 0.0
    )
    return dict(by_category), span_days


def _score_buckets(
    buckets: Sequence[tuple[datetime, str]],
    by_category: dict[str, list[datetime]],
    *,
    horizon_hours: float,
    span_days: float,
) -> LabelStats:
    """Resolve one label per (window_end, category) bucket.

    A label is positive if that category recurs **strictly after** `window_end` and
    within the horizon. `bisect_right` places the cut past any exact match, which is
    what makes "strictly after" true even when a visit lands on the boundary — the same
    strictness `sessionise` documents, for the same reason.
    """
    horizon = timedelta(hours=horizon_hours)
    total = 0
    positives = 0
    per_category: dict[str, int] = defaultdict(int)

    for window_end, category in buckets:
        moments = by_category[category]
        total += 1
        per_category[category] += 1
        index = bisect_right(moments, window_end)
        if index < len(moments) and moments[index] <= window_end + horizon:
            positives += 1

    return LabelStats(
        total=total,
        positives=positives,
        positive_rate=positives / total if total else None,
        span_days=span_days,
        labels_per_week=total / (span_days / 7) if span_days > 0 else 0.0,
        per_category=dict(per_category),
    )


def estimate_return_24h_labels(
    events: Sequence[tuple[datetime, str]],
    *,
    horizon_hours: float = 24.0,
    tz: tzinfo = UTC,
) -> LabelStats:
    """Count `return_24h` labels: one example per (category, day).

    The window closes at the end of each day. The label is positive if that category is
    seen again within `horizon_hours` **after** the window closes.

    Note what this does *not* do: activity on the day itself never decides the label.
    That is the leakage guard in its simplest form — a feature computed at `window_end`
    can see the whole day, and the label can see none of it.

    Measured at T1: this definition is the reason the gate failed. A day is a very large
    bucket, so the dataset is capped at (categories x active days) however much browsing
    happens inside one. See `estimate_return_24h_labels_by_session`.
    """
    if not events:
        return _EMPTY_STATS

    by_category, span_days = _index_events(events)
    buckets = [
        (datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz), category)
        for category, moments in by_category.items()
        for day in sorted({moment.astimezone(tz).date() for moment in moments})
    ]
    return _score_buckets(
        buckets, by_category, horizon_hours=horizon_hours, span_days=span_days
    )


def estimate_return_24h_labels_by_session(
    events: Sequence[tuple[datetime, str]],
    *,
    timeout_seconds: float,
    horizon_hours: float = 24.0,
) -> LabelStats:
    """Count `return_24h` labels: one example per (category, session).

    The window closes at the **end of the session**, so a visit inside the same session
    can never make its own label positive.

    This is the definition that matches what the product actually claims to predict —
    "will you come back to this" is a question about the next session, not the next
    calendar day — and it discards far less structure than the daily definition.

    The session timeout is a declared hyperparameter, not a constant: T1 found no
    empirical trough in the gap distribution to derive one from, so it is reported
    rather than assumed.
    """
    if not events:
        return _EMPTY_STATS

    by_category, span_days = _index_events(events)
    ordered = sorted(events)
    sessions = sessionise([moment for moment, _ in ordered], timeout_seconds=timeout_seconds)

    buckets: list[tuple[datetime, str]] = []
    position = 0
    for session in sessions:
        window_end = session[-1]
        categories = {ordered[position + offset][1] for offset in range(len(session))}
        position += len(session)
        buckets.extend((window_end, category) for category in sorted(categories))

    return _score_buckets(
        buckets, by_category, horizon_hours=horizon_hours, span_days=span_days
    )


def estimate_return_24h_labels_by_window(
    events: Sequence[tuple[datetime, str]],
    *,
    window_hours: float = 6.0,
    horizon_hours: float = 24.0,
    tz: tzinfo = UTC,
) -> LabelStats:
    """Count `return_24h` labels in fixed windows anchored at local midnight.

    A middle ground between the daily and per-session definitions: it does not depend on
    a session timeout, but it still splits a day into several label opportunities. With
    `window_hours=24` it is exactly the daily definition, which is a useful sanity anchor.

    Assumes windows tile the day evenly and that local midnight is well defined. In a
    timezone with daylight saving the transition days are slightly ragged; India, where
    this was measured, has none.
    """
    if not events:
        return _EMPTY_STATS

    by_category, span_days = _index_events(events)

    buckets: set[tuple[datetime, str]] = set()
    for moment, category in events:
        local = moment.astimezone(tz)
        midnight = datetime.combine(local.date(), time.min, tzinfo=tz)
        elapsed_hours = (local - midnight).total_seconds() / 3600
        index = int(elapsed_hours // window_hours)
        buckets.add((midnight + timedelta(hours=window_hours * (index + 1)), category))

    return _score_buckets(
        sorted(buckets), by_category, horizon_hours=horizon_hours, span_days=span_days
    )


def ascii_histogram(
    values: Sequence[float], *, bins: int = 20, width: int = 40, log: bool = False
) -> str:
    """A histogram that survives in a Markdown file and a git diff.

    Deliberately dependency-free. The publication-quality version of this plot is built
    later from the same numbers; this one exists so the committed report is readable
    without opening anything.
    """
    usable = [v for v in values if not log or v > 0]
    if not usable:
        return "(no data)"

    scaled = [math.log10(v) for v in usable] if log else list(usable)
    low, high = min(scaled), max(scaled)
    if high == low:
        high = low + 1.0

    step = (high - low) / bins
    counts = [0] * bins
    for value in scaled:
        counts[min(int((value - low) / step), bins - 1)] += 1

    peak = max(counts) or 1
    lines = []
    for i, count in enumerate(counts):
        edge_low = low + i * step
        edge_high = edge_low + step
        if log:
            label = f"{10 ** edge_low:>10,.1f} - {10 ** edge_high:>10,.1f}"
        else:
            label = f"{edge_low:>10,.1f} - {edge_high:>10,.1f}"
        bar = "#" * round(width * count / peak)
        lines.append(f"{label} | {bar:<{width}} {count:>7,}")
    return "\n".join(lines)
