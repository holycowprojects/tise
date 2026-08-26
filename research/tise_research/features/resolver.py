"""Resolve a registrable domain to a category.

Four layers, first match wins:

1. **User override** — the user is always right about their own browsing.
2. **Shipped map** — explicit `domain -> category` entries.
3. **Keyword rules** — ordered patterns catching classes of site the map cannot
   enumerate: every local government portal, every school, every regional bank.
4. **`unknown`** — a valid answer, not a failure.

Layer 3 does real privacy work as well as coverage work. A rule categorises someone's
council website or their child's school without either ever appearing in a public file.

The resolver reports **which layer answered**. That is what makes the unknown rate
measurable instead of hidden, and it makes it possible to see when a rule is doing
nothing and should be deleted.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from tise_research.categories import CategoryMap

__all__ = ["Resolution", "ResolutionSource", "resolve", "resolve_many", "unknown_rate"]

ResolutionSource = Literal["override", "map", "rule", "fallback"]

UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Resolution:
    """A category and the layer that produced it."""

    category: str
    source: ResolutionSource


def resolve(
    domain: str,
    *,
    category_map: CategoryMap,
    overrides: Mapping[str, str] | None = None,
) -> Resolution:
    """Resolve one domain. Pure: same inputs, same output, no clock, no I/O."""
    normalised = domain.strip().lower()
    if not normalised:
        return Resolution(UNKNOWN, "fallback")

    if overrides:
        override = overrides.get(normalised)
        if override:
            return Resolution(override, "override")

    mapped = category_map.lookup(normalised)
    if mapped is not None:
        return Resolution(mapped, "map")

    for rule in category_map.rules:
        if rule.matches(normalised):
            return Resolution(rule.category, "rule")

    return Resolution(UNKNOWN, "fallback")


def resolve_many(
    domains: Sequence[str],
    *,
    category_map: CategoryMap,
    overrides: Mapping[str, str] | None = None,
) -> list[Resolution]:
    """Resolve a sequence, preserving order."""
    return [
        resolve(domain, category_map=category_map, overrides=overrides)
        for domain in domains
    ]


def unknown_rate(
    domains: Iterable[str],
    *,
    category_map: CategoryMap,
    overrides: Mapping[str, str] | None = None,
) -> float | None:
    """Share of domains that resolved to `unknown`.

    Returns None for an empty input. Zero would claim perfect coverage of nothing, and
    this number goes into a published report.
    """
    total = 0
    unknown = 0
    for domain in domains:
        total += 1
        if resolve(domain, category_map=category_map, overrides=overrides).category == UNKNOWN:
            unknown += 1
    return unknown / total if total else None
