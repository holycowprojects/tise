"""The category resolver.

Four layers, first match wins: **user override -> shipped map -> keyword rules ->
`unknown`.** Every layer is data-driven and every rule lives in `domains.json`, so the
TypeScript port at T9 reads the same rules rather than reimplementing them. A resolver
that disagreed between languages would silently recategorise history and invalidate
every benchmark.

`unknown` is a valid outcome. The resolver reports *why* it answered — which layer fired
— so the unknown rate is measurable rather than hidden.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from tise_research.categories import load_category_map
from tise_research.features.resolver import (
    Resolution,
    resolve,
    resolve_many,
    unknown_rate,
)

MAP = load_category_map()


def category_of(domain: str, **kwargs) -> str:
    return resolve(domain, category_map=MAP, **kwargs).category


class TestLayerPrecedence:
    def test_map_beats_rules(self):
        """`amazon.in` is mapped to shopping; no rule should override an explicit entry."""
        result = resolve("amazon.in", category_map=MAP)
        assert result.category == "shopping"
        assert result.source == "map"

    def test_override_beats_map(self):
        """The user is always right about their own browsing."""
        result = resolve("youtube.com", category_map=MAP, overrides={"youtube.com": "work"})
        assert result.category == "work"
        assert result.source == "override"

    def test_rules_fire_only_when_the_map_misses(self):
        result = resolve("someministry.gov.in", category_map=MAP)
        assert result.category == "government"
        assert result.source == "rule"

    def test_unmatched_falls_back_to_unknown(self):
        result = resolve("a-domain-nobody-has.example", category_map=MAP)
        assert result.category == "unknown"
        assert result.source == "fallback"


class TestKeywordRules:
    """Rules exist to catch *classes* of site the shipped map can never enumerate —
    every local government portal, every school. They are deliberately conservative:
    a wrong category is worse than `unknown`, because `unknown` is honest."""

    @pytest.mark.parametrize(
        ("domain", "expected"),
        [
            ("keralapolice.gov.in", "government"),
            ("parivahan.nic.in", "government"),
            ("someagency.gov", "government"),
            ("stanford.edu", "learning"),
            ("someschool.edu.in", "learning"),
            ("iitb.ac.in", "learning"),
            ("stmaryschool.org", "learning"),
            ("someuniversity.org", "learning"),
            ("mylocalbank.com", "finance"),
            ("bestinsurance.co.in", "finance"),
            ("localnews24.com", "news"),
            ("goodhotels.co.in", "travel"),
        ],
    )
    def test_rule_matches(self, domain, expected):
        assert category_of(domain) == expected

    def test_rules_are_ordered_and_first_match_wins(self):
        """Determinism is the whole point: the TypeScript port must agree exactly."""
        rules = MAP.rules
        assert rules, "no rules defined"
        first = next(r for r in rules if r.matches("anyministry.gov.in"))
        assert first.category == "government"

    @pytest.mark.parametrize(
        "domain",
        ["youtube.com", "google.com", "github.com", "amazon.in", "wikipedia.org"],
    )
    def test_rules_never_hijack_a_mapped_domain(self, domain):
        assert resolve(domain, category_map=MAP).source == "map"


class TestPurity:
    def test_same_input_same_output(self):
        first = resolve("example.gov.in", category_map=MAP)
        second = resolve("example.gov.in", category_map=MAP)
        assert first == second

    def test_returns_a_frozen_result(self):
        result = resolve("youtube.com", category_map=MAP)
        assert isinstance(result, Resolution)
        with pytest.raises(FrozenInstanceError):
            result.category = "video"  # type: ignore[misc]

    def test_case_and_whitespace_are_normalised(self):
        assert category_of("  YouTube.COM ") == "video"

    def test_empty_domain_is_unknown_not_an_error(self):
        assert category_of("") == "unknown"


class TestReporting:
    def test_resolve_many_preserves_order(self):
        domains = ["youtube.com", "nothing.example", "someoffice.gov.in"]
        results = resolve_many(domains, category_map=MAP)
        assert [r.category for r in results] == ["video", "unknown", "government"]

    def test_unknown_rate_is_a_share_not_a_count(self):
        domains = ["youtube.com", "nothing.example", "alsonothing.example", "google.com"]
        assert unknown_rate(domains, category_map=MAP) == pytest.approx(0.5)

    def test_unknown_rate_of_empty_input_is_none(self):
        """Zero would claim perfect coverage of nothing."""
        assert unknown_rate([], category_map=MAP) is None
