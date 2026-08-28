"""`block_volume` labels and `bs_1` features, produced in one forward pass (D91, T21).

> For topic *C* and local day *D*: is *C*'s event count on *D* strictly greater than the
> median of *C*'s counts over the trailing 10 complete days before *D*?

**Leakage is structural here rather than guarded.** Everywhere else in this repository a
feature function takes `window_end` and filters strictly before it, and a test checks that
injecting a later event changes nothing. Blocks allow something stronger: the label and its
features are emitted during a single forward walk, from state that only ever contains blocks
already passed. There is no expression in this module that *could* read the block being
predicted — the counts for block *D* are folded into the history only after every label for
*D* has been emitted. The leakage test still exists, because "cannot by construction" is a
claim about code that changes.

**Every parameter comes from D91 and none was chosen here.** Trailing window 10, minimum 6
prior blocks, qualifying rule "present in at least half the window", strict `>`, raw counts
rather than shares. The reasoning for each is in that entry; repeating it here would let the
two drift.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from statistics import median

from tise_research.features.blocks import Block, BlockType, category_counts
from tise_research.features.labels import Label
from tise_research.features.vector import FeatureRow, saturate

__all__ = [
    "BLOCK_FEATURE_SET",
    "BLOCK_TARGET",
    "DEFAULT_MIN_PRIOR",
    "DEFAULT_TRAILING",
    "BlockExample",
    "BlockIndex",
    "block_volume_examples",
]

BLOCK_TARGET = "block_volume"
BLOCK_FEATURE_SET = "bs_1"

#: D91. Not tunable here — changing either belongs in a decision entry, not in a call site.
DEFAULT_TRAILING = 10
DEFAULT_MIN_PRIOR = 6

#: Scale at which `medianLevel` reaches 0.5. Five events a day is an ordinary level for an
#: active topic; declared, not fitted, per D81.
MEDIAN_LEVEL_SCALE = 5.0

#: Scale for `streakAbove` and `daysSinceAbove`, in blocks. Three days is the point at which
#: a run stops being noise. Declared.
STREAK_SCALE = 3.0


@dataclass(frozen=True, slots=True)
class BlockExample:
    """One training example: what was asked, and what it was asked from."""

    label: Label
    row: FeatureRow


@dataclass(slots=True)
class _TopicState:
    """Everything remembered about one topic. Only ever holds blocks already passed."""

    counts: list[int]
    above: list[bool]

    def window(self, trailing: int) -> list[int]:
        return self.counts[-trailing:]

    def qualifies(self, trailing: int) -> bool:
        window = self.window(trailing)
        return bool(window) and sum(1 for value in window if value > 0) * 2 >= len(window)

    def streak(self) -> int:
        count = 0
        for flag in reversed(self.above):
            if not flag:
                break
            count += 1
        return count

    def since_above(self) -> int | None:
        for distance, flag in enumerate(reversed(self.above), start=1):
            if flag:
                return distance - 1
        return None


def _features(
    state: _TopicState,
    *,
    threshold: float,
    trailing: int,
    total_window: Sequence[int],
    previous_total: int,
    weekday: int,
) -> dict[str, float | None]:
    window = state.window(trailing)
    previous = state.counts[-1]
    since = state.since_above()
    total_median = median(total_window) if total_window else 0.0

    # A cyclic pair, so Sunday and Monday are adjacent. D86 measured the day-of-week
    # pattern as non-monotone, which a plain integer cannot represent in either direction.
    angle = 2.0 * math.pi * weekday / 7.0

    return {
        "prevAbove": 1.0 if state.above and state.above[-1] else 0.0,
        # `+1` in the denominator rather than a guard: a median of 0 is legitimate for a
        # topic that has just started qualifying, and dividing by it would raise on data
        # that is not wrong.
        "lastRatio": previous / (threshold + 1.0),
        "streakAbove": saturate(float(state.streak()), STREAK_SCALE),
        "daysSinceAbove": None if since is None else saturate(float(since), STREAK_SCALE),
        "medianLevel": saturate(float(threshold), MEDIAN_LEVEL_SCALE),
        "activeRate10": sum(1 for value in window if value > 0) / len(window),
        "topicShare10": (
            sum(window) / sum(total_window) if sum(total_window) else 0.0
        ),
        "totalRatio": previous_total / (total_median + 1.0),
        "dayOfWeekSin": math.sin(angle),
        "dayOfWeekCos": math.cos(angle),
    }


def block_volume_examples(
    blocks: Sequence[Block],
    *,
    kind: BlockType = "day",
    trailing: int = DEFAULT_TRAILING,
    min_prior: int = DEFAULT_MIN_PRIOR,
) -> list[BlockExample]:
    """Walk blocks of one kind in order, emitting an example per qualifying topic.

    The ordering inside the loop is the whole safety argument: every label and every feature
    for block *D* is produced before *D*'s counts are added to any state.
    """
    ordered = sorted(
        (block for block in blocks if block.kind == kind), key=lambda block: block.key
    )

    topics: dict[str, _TopicState] = {}
    totals: list[int] = []
    examples: list[BlockExample] = []

    for block in ordered:
        counts = category_counts(block)
        block_total = sum(counts.values())
        # `window_end` is the instant the block closed, which is when its label becomes
        # decidable. Midnight after the block's last day.
        window_end = block.first_at.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)

        for subject in sorted(topics):
            state = topics[subject]
            if len(state.counts) < min_prior or not state.qualifies(trailing):
                continue

            window = state.window(trailing)
            threshold = float(median(window))
            observed = counts.get(subject, 0)

            row = FeatureRow(
                subject=subject,
                window_end=window_end,
                feature_set=BLOCK_FEATURE_SET,
                compat="history",
                values=_features(
                    state,
                    threshold=threshold,
                    trailing=trailing,
                    total_window=totals[-trailing:],
                    previous_total=totals[-1] if totals else 0,
                    weekday=block.first_at.weekday(),
                ),
            )
            examples.append(
                BlockExample(
                    label=Label(
                        target=BLOCK_TARGET,
                        subject=subject,
                        window_end=window_end,
                        outcome=observed > threshold,
                        horizon_hours=24.0,
                        session_id=str(block.key),
                    ),
                    row=row,
                )
            )

        # Only now does this block become history. Moving this above the loop would leak
        # the answer into its own features and into its own median.
        for subject in set(topics) | set(counts):
            state = topics.setdefault(subject, _TopicState(counts=[], above=[]))
            observed = counts.get(subject, 0)
            prior = state.window(trailing)
            state.above.append(bool(prior) and observed > float(median(prior)))
            state.counts.append(observed)
        totals.append(block_total)

    return examples


@dataclass(slots=True)
class BlockIndex:
    """Feature rows by `(subject, window_end)`, so a fitter can look one up cheaply.

    The same role `FeatureIndex` plays for `return_24h`, but a lookup rather than a cache:
    the rows were produced by the forward walk above and cannot be recomputed from a label
    alone, which is exactly what makes them impossible to accidentally recompute with the
    wrong window.
    """

    rows: dict[tuple[str, object], FeatureRow]
    feature_set: str = BLOCK_FEATURE_SET

    @classmethod
    def from_examples(cls, examples: Sequence[BlockExample]) -> BlockIndex:
        return cls(
            rows={
                (example.label.subject, example.label.window_end): example.row
                for example in examples
            }
        )

    def row_for(self, label: Label) -> FeatureRow:
        try:
            return self.rows[(label.subject, label.window_end)]
        except KeyError:
            raise KeyError(
                f"no {self.feature_set} row for {label.subject} at {label.window_end}; "
                "labels and rows come from one pass and must not be assembled separately"
            ) from None

    def rows_for(self, labels: Sequence[Label]) -> list[FeatureRow]:
        return [self.row_for(label) for label in labels]
