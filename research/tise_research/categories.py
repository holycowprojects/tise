"""Load the shipped domain -> category map.

The map itself lives in `extension/src/categories/domains.json` — inside the extension,
not inside the research package — because the extension is what ships it. Python reads
the same file the browser does, so there is exactly one map and no opportunity for the
two to drift. That is the same reasoning as the parity suite, applied to data instead of
code.

This module deliberately stops at a **lookup**. The full resolver — map, then keyword
rules, then `unknown`, with a user override on top — is T3's, and layering it here would
put half of it in the wrong place.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = ["DEFAULT_MAP_PATH", "CategoryMap", "CategoryRule", "load_category_map"]

#: research/tise_research/categories.py -> repo root is three parents up.
_REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MAP_PATH = _REPO_ROOT / "extension" / "src" / "categories" / "domains.json"


@dataclass(frozen=True, slots=True)
class CategoryRule:
    """One keyword rule, applied only when the domain map misses.

    Kept as data rather than code precisely so the TypeScript port cannot drift: both
    languages read this list, neither owns it.
    """

    kind: str  # "suffix" | "contains"
    value: str
    category: str

    def matches(self, domain: str) -> bool:
        if self.kind == "suffix":
            return domain.endswith(self.value)
        if self.kind == "contains":
            return self.value in domain
        raise ValueError(f"unknown rule kind: {self.kind!r}")


@dataclass(frozen=True, slots=True)
class CategoryMap:
    """The shipped map, already validated enough to be useful.

    `version` is bumped whenever the mapping changes in a way that could move a
    prediction, and is recorded in `DECISIONS.md` alongside the `featureSet` version —
    a benchmark is only reproducible if you know which map produced it.
    """

    version: int
    categories: dict[str, str]
    domains: dict[str, str]
    #: Ordered. First match wins, and the order is part of the contract.
    rules: tuple[CategoryRule, ...] = ()

    def lookup(self, domain: str) -> str | None:
        """Category for a registrable domain, or None if the map has nothing.

        None is not `unknown`. None means "this layer had no answer"; `unknown` is a
        decision the resolver makes after every layer has declined.
        """
        return self.domains.get(domain.strip().lower())


def load_category_map(path: Path | None = None) -> CategoryMap:
    """Read and validate the shipped map.

    Validation is minimal and structural — enough that a malformed file fails loudly
    here rather than silently categorising everything as `unknown` three tasks later.
    """
    source = path or DEFAULT_MAP_PATH
    raw: dict[str, Any] = json.loads(source.read_text(encoding="utf-8"))

    missing = {"version", "categories", "domains"} - set(raw)
    if missing:
        raise ValueError(f"{source} is missing required keys: {sorted(missing)}")

    categories = {str(k): str(v) for k, v in raw["categories"].items()}
    domains = {str(k).lower(): str(v) for k, v in raw["domains"].items()}

    rules = tuple(
        CategoryRule(
            kind=str(entry["kind"]),
            value=str(entry["value"]).lower(),
            category=str(entry["category"]),
        )
        for entry in raw.get("rules", ())
    )

    undefined = sorted(
        {c for c in domains.values() if c not in categories}
        | {r.category for r in rules if r.category not in categories}
    )
    if undefined:
        raise ValueError(f"{source} references undefined categories: {undefined}")

    bad_kinds = sorted({r.kind for r in rules} - {"suffix", "contains"})
    if bad_kinds:
        raise ValueError(f"{source} has unsupported rule kinds: {bad_kinds}")

    return CategoryMap(
        version=int(raw["version"]),
        categories=categories,
        domains=domains,
        rules=rules,
    )
