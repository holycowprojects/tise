"""T-F — which things co-occur inside a session, and how many of those are coincidence.

D95 adopted this from an outside plan: association rules over the domains that appear
together in a session. **Descriptive**, so it ships without clearing a prediction bar.

**Pairs only.** A rule here has a single-item antecedent — *when X is in a session, Y often
is too*. That is what "which domains co-occur" asks, and it is also the only form that stays
honest on this much data: a corpus of a few hundred sessions supports pair counts and does
not support the item-set lattice a general FP-Growth would enumerate, where the number of
candidate rules grows faster than the evidence for any of them.

**Presence, not count.** A session that visits one domain forty times contributes that
domain once. Otherwise the "rules" are dominated by whichever domain a person reloads.

## Confidence is the number that misleads, and lift is only half the fix

A rule can have 90% confidence purely because its consequent is in 90% of all sessions.
**Lift** divides that out, and every reported rule carries both — but lift computed on small
counts is itself noisy, and a corpus will always yield *some* high-lift pairs by chance.

So the mandatory baseline here (D24) is a **null corpus**: sessions of the same sizes, filled
with items drawn in proportion to how often each really occurs, and no genuine association
anywhere. Running the same miner over it says how many rules of each strength this many
sessions produce **when there is nothing to find**. A rule count is meaningless without it,
and published rule-mining almost never reports one.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass

__all__ = [
    "ASSOCIATION_SEED",
    "DEFAULT_MIN_CONFIDENCE",
    "DEFAULT_MIN_LIFT",
    "DEFAULT_MIN_SESSIONS",
    "DEFAULT_NULL_RUNS",
    "Rule",
    "association_rules",
    "null_rule_band",
    "session_itemsets",
]

#: Declared, committed, never tuned — as `BOOTSTRAP_SEED` is (D80).
ASSOCIATION_SEED = 20260902

#: A pair must appear together in at least this many sessions before a rule is emitted.
#: Below it, lift is a ratio of very small integers and moves by whole multiples on one
#: session. Declared rather than fitted, and the report prints how many rules each
#: threshold admits so the choice is visible rather than buried.
DEFAULT_MIN_SESSIONS = 5

DEFAULT_MIN_CONFIDENCE = 0.30

#: Lift of 1.0 is independence. Anything at or below it is not a rule, whatever its
#: confidence says.
DEFAULT_MIN_LIFT = 1.5

DEFAULT_NULL_RUNS = 50


@dataclass(frozen=True, slots=True)
class Rule:
    """`antecedent -> consequent`, with the three numbers that describe it.

    `support_sessions` is a count and not a fraction on purpose: D88's rule is that every
    figure is shown with its denominator, and "8 of your 214 sessions" is checkable in a way
    that "3.7%" is not.
    """

    antecedent: str
    consequent: str
    support_sessions: int
    antecedent_sessions: int
    consequent_sessions: int
    confidence: float
    lift: float


def session_itemsets(
    sessions: Sequence[Sequence[str]], *, min_items: int = 2
) -> list[frozenset[str]]:
    """De-duplicate each session into a set, and drop the ones that cannot co-occur.

    A session holding a single distinct item contributes no pair and is excluded from the
    denominator. Keeping it would deflate every confidence by a constant factor and make
    the numbers depend on how much solitary browsing a person does, which is not what any
    of these rules is about. The report states how many were dropped.
    """
    return [
        frozenset(session)
        for session in sessions
        if len(frozenset(session)) >= min_items
    ]


def association_rules(
    itemsets: Sequence[frozenset[str]],
    *,
    min_sessions: int = DEFAULT_MIN_SESSIONS,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    min_lift: float = DEFAULT_MIN_LIFT,
) -> list[Rule]:
    """Every pair rule clearing all three thresholds, strongest lift first.

    Both directions of a pair are emitted when both qualify: `X -> Y` and `Y -> X` share a
    support and a lift but have different confidences, and which one is worth showing
    depends on which item the person is looking at.
    """
    total = len(itemsets)
    if total == 0:
        return []

    counts: dict[str, int] = {}
    pairs: dict[tuple[str, str], int] = {}
    for items in itemsets:
        ordered = sorted(items)
        for item in ordered:
            counts[item] = counts.get(item, 0) + 1
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                pairs[(left, right)] = pairs.get((left, right), 0) + 1

    rules: list[Rule] = []
    for (left, right), together in pairs.items():
        if together < min_sessions:
            continue
        for antecedent, consequent in ((left, right), (right, left)):
            confidence = together / counts[antecedent]
            lift = confidence / (counts[consequent] / total)
            if confidence < min_confidence or lift < min_lift:
                continue
            rules.append(
                Rule(
                    antecedent=antecedent,
                    consequent=consequent,
                    support_sessions=together,
                    antecedent_sessions=counts[antecedent],
                    consequent_sessions=counts[consequent],
                    confidence=confidence,
                    lift=lift,
                )
            )

    rules.sort(key=lambda rule: (-rule.lift, -rule.support_sessions, rule.antecedent))
    return rules


def null_rule_band(
    itemsets: Sequence[frozenset[str]],
    *,
    runs: int = DEFAULT_NULL_RUNS,
    min_sessions: int = DEFAULT_MIN_SESSIONS,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    min_lift: float = DEFAULT_MIN_LIFT,
    seed: int = ASSOCIATION_SEED,
    level: float = 0.95,
) -> tuple[float, int, int]:
    """`(median, low, high)` rule count on corpora with the same shape and no associations.

    Each null session keeps its **exact size** and is filled by sampling distinct items in
    proportion to how often each really occurs. Item frequencies are therefore preserved in
    expectation rather than exactly — an approximation, stated rather than hidden, and it
    errs toward *more* null rules for common items, which makes the comparison conservative
    in the direction that matters.
    """
    counts: dict[str, int] = {}
    for items in itemsets:
        for item in items:
            counts[item] = counts.get(item, 0) + 1
    vocabulary = sorted(counts)
    weights = [counts[item] for item in vocabulary]

    rng = random.Random(seed)
    totals: list[int] = []
    for _ in range(runs):
        drawn: list[frozenset[str]] = []
        for items in itemsets:
            wanted = min(len(items), len(vocabulary))
            picked: set[str] = set()
            # Weighted draw without replacement. Bounded so a pathological corpus — one
            # item holding almost all the weight — cannot spin here forever; the shortfall
            # is filled uniformly and the session keeps its size.
            for _ in range(wanted * 20):
                if len(picked) == wanted:
                    break
                picked.add(rng.choices(vocabulary, weights=weights, k=1)[0])
            while len(picked) < wanted:
                picked.add(rng.choice(vocabulary))
            drawn.append(frozenset(picked))

        totals.append(
            len(
                association_rules(
                    drawn,
                    min_sessions=min_sessions,
                    min_confidence=min_confidence,
                    min_lift=min_lift,
                )
            )
        )

    totals.sort()
    tail = (1.0 - level) / 2.0
    return (
        _percentile(totals, 0.5),
        int(_percentile(totals, tail)),
        int(math.ceil(_percentile(totals, 1.0 - tail))),
    )


def _percentile(values: list[int], fraction: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    position = fraction * (len(values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(values[lower])
    weight = position - lower
    return values[lower] * (1.0 - weight) + values[upper] * weight
