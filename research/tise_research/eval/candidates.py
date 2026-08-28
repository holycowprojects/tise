"""T19 — measure the four candidate targets. **No model is fitted and nothing is scored.**

That restriction is the reason D88 permits the data-sufficiency gate to be set *after* this
runs: a descriptive measurement produces no score, so there is nothing here that could bias
a bar chosen from it. The performance bar is pre-registered separately, in T20, before any
model exists.

What each candidate needs to survive is the same pair of numbers — **how many labels, and
what base rate** — plus, for `block_volume`, how many topics are left standing once the
qualifying rule is applied.

**The tie problem, which is the thing most likely to bite.** D88 claims a median split is
50/50 by construction. That is true of a continuous quantity. These are **integer event
counts over a handful of blocks**, so a count landing exactly on the median is common, and
"strictly above the median" then loses every tie. The base rate can sit well below 50% for
a reason that has nothing to do with behaviour. Both rules are therefore measured — strict
`>` and inclusive `>=` — with the tie rate reported beside them, so T20 chooses with the
number in front of it rather than by argument.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from statistics import median

from tise_research.features.blocks import (
    BLOCK_TYPES,
    Block,
    BlockType,
    category_counts,
)
from tise_research.features.events import Event

__all__ = [
    "DEFAULT_MIN_PRIOR_BLOCKS",
    "DEFAULT_TRAILING_BLOCKS",
    "BlockVolumeStats",
    "DormancyStats",
    "NextCategoryStats",
    "NoveltyStats",
    "block_volume_stats",
    "dormancy_stats",
    "next_category_stats",
    "novelty_stats",
]

#: Trailing window the median is taken over. D88 chose ~10 so an imported bootstrap ages
#: out in about five weeks of live collection.
DEFAULT_TRAILING_BLOCKS = 10

#: A topic needs this many prior blocks of the type before it can be predicted at all.
#: Below it there is no median worth the name.
DEFAULT_MIN_PRIOR_BLOCKS = 6

#: Days of history a domain must be absent from to count as new, for `novelty`.
NOVELTY_LOOKBACK_DAYS = 30


@dataclass(frozen=True, slots=True)
class BlockVolumeStats:
    """One block type's label yield under both tie rules."""

    kind: BlockType
    blocks: int
    #: Labels emitted once the qualifying rule is applied.
    labels: int
    #: Positive rate under `count > median`. Ties are negatives.
    base_rate_strict: float | None
    #: Positive rate under `count >= median`. Ties are positives.
    base_rate_inclusive: float | None
    #: Share of labels where the count landed exactly on the median.
    tie_rate: float | None
    #: Topics that ever cleared the qualifying rule.
    qualifying_topics: int
    #: Topics rejected because they appeared in under half their prior blocks.
    rejected_sparse: int
    #: Of the labels emitted, the share whose trailing median was zero. D88's known flaw:
    #: "above zero" is "did it appear", and the 50% property does not hold there.
    zero_median_rate: float | None
    #: Same target expressed as a share of the block's activity rather than a raw count.
    #: A share cancels a uniform import-versus-live offset; a count does not.
    base_rate_share_strict: float | None
    #: Mean events per block, second half of the corpus over first half. A median split is
    #: only 50/50 on a **stationary** series: if activity grows, the current block beats a
    #: median of earlier blocks more often than not, for reasons that are nothing to do
    #: with the topic. Measured here so the base rate above can be read rather than
    #: guessed at.
    volume_trend: float | None


def _trailing(values: Sequence[int], window: int) -> list[int]:
    return list(values[-window:]) if window > 0 else list(values)


def block_volume_stats(
    blocks: Sequence[Block],
    *,
    kind: BlockType,
    trailing: int = DEFAULT_TRAILING_BLOCKS,
    min_prior: int = DEFAULT_MIN_PRIOR_BLOCKS,
) -> BlockVolumeStats:
    """Walk blocks of one type in order, emitting a label per qualifying topic.

    Strictly forward-only: a block's label is decided from blocks *before* it and nothing
    else. That is the leakage rule in the same shape it takes everywhere else in this
    repository, and it is why the counts here can be compared against a backtest later.
    """
    ordered = [block for block in blocks if block.kind == kind]

    history: dict[str, list[int]] = defaultdict(list)
    share_history: dict[str, list[float]] = defaultdict(list)
    seen_topics: set[str] = set()

    positives_strict = positives_inclusive = ties = zero_medians = 0
    positives_share_strict = 0
    labels = 0
    qualifying: set[str] = set()
    rejected: set[str] = set()

    for block in ordered:
        counts = category_counts(block)
        total = sum(counts.values()) or 1

        for topic in sorted(seen_topics):
            prior = history[topic]
            if len(prior) < min_prior:
                continue
            window = _trailing(prior, trailing)
            # The qualifying rule: present in at least half the window. Below that the
            # median is 0 and "more than 0" is a different question (D88).
            if sum(1 for value in window if value > 0) * 2 < len(window):
                rejected.add(topic)
                continue

            qualifying.add(topic)
            observed = counts.get(topic, 0)
            threshold = median(window)
            labels += 1
            if observed > threshold:
                positives_strict += 1
            if observed >= threshold:
                positives_inclusive += 1
            if observed == threshold:
                ties += 1
            if threshold == 0:
                zero_medians += 1

            share_window = _trailing(share_history[topic], trailing)
            if share_window and (observed / total) > median(share_window):
                positives_share_strict += 1

        # Recorded only after every label for this block is emitted, so nothing above ever
        # sees the block it is predicting.
        for topic in set(seen_topics) | set(counts):
            history[topic].append(counts.get(topic, 0))
            share_history[topic].append(counts.get(topic, 0) / total)
        seen_topics |= set(counts)

    def rate(count: int) -> float | None:
        return count / labels if labels else None

    volumes = [len(block.events) for block in ordered]
    trend: float | None = None
    if len(volumes) >= 4:
        half = len(volumes) // 2
        early = sum(volumes[:half]) / half
        late = sum(volumes[half:]) / (len(volumes) - half)
        trend = (late / early) if early else None

    return BlockVolumeStats(
        kind=kind,
        blocks=len(ordered),
        labels=labels,
        base_rate_strict=rate(positives_strict),
        base_rate_inclusive=rate(positives_inclusive),
        tie_rate=rate(ties),
        qualifying_topics=len(qualifying),
        rejected_sparse=len(rejected - qualifying),
        zero_median_rate=rate(zero_medians),
        base_rate_share_strict=rate(positives_share_strict),
        volume_trend=trend,
    )


@dataclass(frozen=True, slots=True)
class NoveltyStats:
    """Does a block contain a domain not seen in the prior 30 days?"""

    kind: BlockType
    labels: int
    base_rate: float | None
    #: Mean new domains per block, which says whether the rate is one straggler or many.
    mean_new_domains: float | None


def novelty_stats(
    blocks: Sequence[Block],
    events: Sequence[Event],
    *,
    kind: BlockType,
    lookback_days: int = NOVELTY_LOOKBACK_DAYS,
) -> NoveltyStats:
    """Label per block, not per topic — so the supply is small but the question is direct.

    If this comes back near 100% the target is dead: "you will see something new" is not
    information. That is the number this exists to produce.
    """
    ordered = [block for block in blocks if block.kind == kind]
    by_time = sorted(events, key=lambda event: event.occurred_at)

    labels = positives = 0
    new_counts: list[int] = []
    for block in ordered:
        window_start = block.first_at - timedelta(days=lookback_days)
        prior_domains = {
            event.domain
            for event in by_time
            if window_start <= event.occurred_at < block.first_at
        }
        if not prior_domains:
            # No history to be new against; "everything is new" is an artefact.
            continue
        fresh = {event.domain for event in block.events} - prior_domains
        labels += 1
        new_counts.append(len(fresh))
        if fresh:
            positives += 1

    return NoveltyStats(
        kind=kind,
        labels=labels,
        base_rate=(positives / labels) if labels else None,
        mean_new_domains=(sum(new_counts) / len(new_counts)) if new_counts else None,
    )


@dataclass(frozen=True, slots=True)
class DormancyStats:
    """For a topic absent from its recent blocks, does it come back?"""

    kind: BlockType
    labels: int
    #: Share that returned in the next block. A rate near 0 or 1 means the question is
    #: already answered by the absence and needs no model.
    return_rate: float | None
    #: Topics contributing, including ones `block_volume` rejects as too sparse.
    topics: int


def dormancy_stats(
    blocks: Sequence[Block],
    *,
    kind: BlockType,
    absent_blocks: int = 2,
) -> DormancyStats:
    """The destination for topics that fail `block_volume`'s qualifying rule (D88)."""
    ordered = [block for block in blocks if block.kind == kind]
    counts = [category_counts(block) for block in ordered]
    seen: set[str] = set()

    labels = returned = 0
    topics: set[str] = set()
    for index, current in enumerate(counts):
        if index >= absent_blocks:
            recent = counts[index - absent_blocks : index]
            for topic in sorted(seen):
                if any(block.get(topic, 0) > 0 for block in recent):
                    continue
                labels += 1
                topics.add(topic)
                if current.get(topic, 0) > 0:
                    returned += 1
        seen |= set(current)

    return DormancyStats(
        kind=kind,
        labels=labels,
        return_rate=(returned / labels) if labels else None,
        topics=len(topics),
    )


@dataclass(frozen=True, slots=True)
class NextCategoryStats:
    """Label supply and the trivial baseline for `next_session_category`."""

    transitions: int
    categories: int
    #: Accuracy of always predicting the single most common successor overall. The floor
    #: any transition table has to beat, and a base rate rather than a model.
    majority_successor_rate: float | None
    #: Accuracy of predicting each category's own most common successor. Still not a
    #: fitted model — it is the training-set mode, reported to show the ceiling is not
    #: trivially high.
    per_category_mode_rate: float | None


def next_category_stats(sessions: Sequence[Sequence[str]]) -> NextCategoryStats:
    """`sessions` is each session's categories, in order of first appearance.

    Included because the transition table already exists in both languages and has
    **never been benchmarked**, and because its label supply is far larger than any
    block-based target's — every session boundary is one.
    """
    pairs: list[tuple[str, str]] = []
    for index in range(len(sessions) - 1):
        current, following = sessions[index], sessions[index + 1]
        if not current or not following:
            continue
        pairs.append((current[0], following[0]))

    if not pairs:
        return NextCategoryStats(0, 0, None, None)

    successors = [nxt for _, nxt in pairs]
    overall_mode = max(set(successors), key=successors.count)
    majority = sum(1 for nxt in successors if nxt == overall_mode) / len(pairs)

    by_source: dict[str, list[str]] = defaultdict(list)
    for source, nxt in pairs:
        by_source[source].append(nxt)
    correct = sum(
        max(set(values), key=values.count) == value
        for values in by_source.values()
        for value in values
    )

    return NextCategoryStats(
        transitions=len(pairs),
        categories=len({category for pair in pairs for category in pair}),
        majority_successor_rate=majority,
        per_category_mode_rate=correct / len(pairs),
    )


def all_block_volume(
    blocks: Sequence[Block], **kwargs: object
) -> dict[BlockType, BlockVolumeStats]:
    return {
        kind: block_volume_stats(blocks, kind=kind, **kwargs)  # type: ignore[arg-type]
        for kind in BLOCK_TYPES
    }
