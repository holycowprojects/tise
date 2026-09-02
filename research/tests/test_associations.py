"""T-F — pair association rules and the null that says how many are coincidence (D95).

The interesting tests are the ones about *confidence being misleading*. A rule whose
consequent appears in nearly every session gets high confidence for free, and a miner that
cannot demonstrate it filters those out is a machine for producing plausible nonsense.
"""

from __future__ import annotations

import random

import pytest
from tise_research.models.associations import (
    association_rules,
    null_rule_band,
    session_itemsets,
)


def sets(*groups: str) -> list[frozenset[str]]:
    """`sets("ab", "abc")` -> two sessions, items being single characters."""
    return [frozenset(group) for group in groups]


# --------------------------------------------------------------------------------------
# Itemsets
# --------------------------------------------------------------------------------------


def test_a_session_counts_each_item_once() -> None:
    """Presence, not count — otherwise rules are dominated by whatever gets reloaded."""
    itemsets = session_itemsets([["a", "a", "a", "b"]])
    assert itemsets == [frozenset({"a", "b"})]


def test_single_item_sessions_are_dropped() -> None:
    """They contribute no pair, and keeping them deflates every confidence by a constant."""
    itemsets = session_itemsets([["a"], ["a", "b"], ["a", "a"]])
    assert itemsets == [frozenset({"a", "b"})]


def test_no_sessions_produces_no_rules() -> None:
    assert association_rules([]) == []


# --------------------------------------------------------------------------------------
# The arithmetic
# --------------------------------------------------------------------------------------


def test_confidence_and_lift_are_computed_as_declared() -> None:
    # 'a' in 6 sessions, 'b' in 6, together in 5, 10 sessions total.
    itemsets = sets("ab", "ab", "ab", "ab", "ab", "ac", "bd", "cd", "cd", "cd")
    rules = {
        (rule.antecedent, rule.consequent): rule
        for rule in association_rules(
            itemsets, min_sessions=5, min_confidence=0.0, min_lift=0.0
        )
    }

    rule = rules[("a", "b")]
    assert rule.support_sessions == 5
    assert rule.antecedent_sessions == 6
    assert rule.consequent_sessions == 6
    assert rule.confidence == pytest.approx(5 / 6)
    assert rule.lift == pytest.approx((5 / 6) / (6 / 10))


def test_both_directions_are_emitted_with_different_confidences() -> None:
    """Same support and lift, different confidence — which is worth showing depends on
    which item the person is looking at."""
    itemsets = sets("ab", "ab", "ab", "b", "b", "b")
    rules = {
        (rule.antecedent, rule.consequent): rule
        for rule in association_rules(
            itemsets, min_sessions=3, min_confidence=0.0, min_lift=0.0
        )
    }

    assert rules[("a", "b")].confidence == pytest.approx(1.0)
    assert rules[("b", "a")].confidence == pytest.approx(0.5)
    assert rules[("a", "b")].lift == pytest.approx(rules[("b", "a")].lift)
    assert rules[("a", "b")].support_sessions == rules[("b", "a")].support_sessions


def test_a_ubiquitous_consequent_gets_high_confidence_and_no_lift() -> None:
    """The defect this whole module exists to avoid.

    'b' is in every session, so *anything* predicts it with confidence 1.0. Lift is exactly
    1.0 — independence — and the rule must not survive a lift threshold above it.
    """
    itemsets = sets("ab", "ab", "ab", "cb", "cb", "cb", "db", "db")
    permissive = association_rules(
        itemsets, min_sessions=3, min_confidence=0.9, min_lift=0.0
    )
    by_pair = {(rule.antecedent, rule.consequent): rule for rule in permissive}
    assert by_pair[("a", "b")].confidence == pytest.approx(1.0)
    assert by_pair[("a", "b")].lift == pytest.approx(1.0)

    filtered = association_rules(itemsets, min_sessions=3, min_confidence=0.9, min_lift=1.5)
    assert not any(rule.consequent == "b" for rule in filtered)


def test_thresholds_each_exclude_something() -> None:
    itemsets = sets("ab", "ab", "ab", "ab", "cd", "cd", "ce", "cf", "cg")

    assert association_rules(itemsets, min_sessions=99) == []
    assert association_rules(itemsets, min_sessions=2, min_confidence=1.01) == []
    assert association_rules(itemsets, min_sessions=2, min_confidence=0.0, min_lift=99.0) == []
    assert association_rules(itemsets, min_sessions=2, min_confidence=0.0, min_lift=0.0)


def test_rules_come_back_strongest_first() -> None:
    itemsets = sets("ab", "ab", "ab", "cd", "cd", "cd", "ae", "ce", "be", "de")
    rules = association_rules(itemsets, min_sessions=3, min_confidence=0.0, min_lift=0.0)
    lifts = [rule.lift for rule in rules]
    assert lifts == sorted(lifts, reverse=True)


def test_lift_above_one_means_more_together_than_apart() -> None:
    together = sets("ab", "ab", "ab", "ab", "c", "cd", "d", "cd")
    apart = sets("ac", "ad", "bc", "bd", "ac", "ad", "bc", "bd")

    strong = association_rules(together, min_sessions=4, min_confidence=0.0, min_lift=0.0)
    weak = association_rules(apart, min_sessions=4, min_confidence=0.0, min_lift=0.0)

    assert strong and strong[0].lift > 1.0
    assert all(rule.lift <= 1.0 for rule in weak)


# --------------------------------------------------------------------------------------
# The null — the mandatory baseline (D24) in the form association rules take
# --------------------------------------------------------------------------------------


def test_the_null_finds_almost_nothing_when_there_is_a_real_rule() -> None:
    """A corpus with one planted association must beat what its own shape produces by chance."""
    itemsets = sets(*(["ab"] * 12), *["cd", "ef", "gh", "ij", "kl", "mn"])
    observed = len(association_rules(itemsets, min_sessions=5))
    _, _, high = null_rule_band(itemsets, runs=20, min_sessions=5)

    assert observed > 0
    assert observed > high


def test_the_null_is_not_always_beaten() -> None:
    """The check that keeps the previous test meaningful.

    A null that any corpus clears would certify every rule set ever mined. Here nothing is
    planted, so the observed count must sit inside the band its own shape produces.
    """
    # Pairs drawn uniformly at random. The first version of this test used an arithmetic
    # pairing (`index % 8` with `(index * 3 + 1) % 8`), which pairs every item with exactly
    # one other — strong structure, and the null correctly found 16 rules against a band
    # topping out at 2. The fixture was wrong and the null was right, which is the outcome
    # this pair of tests exists to be able to produce.
    rng = random.Random(3)
    items = "abcdefgh"
    itemsets = [frozenset(rng.sample(items, 2)) for _ in range(60)]
    observed = len(association_rules(itemsets, min_sessions=5))
    _, low, high = null_rule_band(itemsets, runs=20, min_sessions=5)

    assert low <= observed <= high


def test_the_null_preserves_session_sizes_exactly() -> None:
    """Stated in the docstring as exact; the item frequencies are the approximation."""
    from tise_research.models import associations

    itemsets = sets("abc", "de", "fghi", "jk")
    captured: list[list[frozenset[str]]] = []
    real_rules = associations.association_rules

    def spy(drawn, **kwargs):  # type: ignore[no-untyped-def]
        captured.append(list(drawn))
        return real_rules(drawn, **kwargs)

    associations.association_rules = spy  # type: ignore[assignment]
    try:
        null_rule_band(itemsets, runs=3)
    finally:
        associations.association_rules = real_rules  # type: ignore[assignment]

    assert captured
    for drawn in captured:
        assert [len(items) for items in drawn] == [len(items) for items in itemsets]


def test_the_null_is_deterministic_for_a_seed() -> None:
    itemsets = sets("ab", "ab", "ac", "bc", "cd", "de", "ab", "bd")
    assert null_rule_band(itemsets, runs=5) == null_rule_band(itemsets, runs=5)


def test_the_null_terminates_when_one_item_holds_almost_all_the_weight() -> None:
    """The bounded draw. An unbounded weighted sample without replacement can spin forever
    here, and the report would hang rather than fail."""
    itemsets = [frozenset({"a", "b"})] + [frozenset({"a", "z"})] * 60
    median, low, high = null_rule_band(itemsets, runs=5)
    assert median >= 0 and low >= 0 and high >= 0
