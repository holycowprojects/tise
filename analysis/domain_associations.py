"""T-F — what co-occurs inside a session. **Descriptive; nothing is predicted.**

    uv run python analysis/domain_associations.py

Writes `docs/benchmarks/domain-associations.md` (committed) and `data/domain-rules.md`
(gitignored).

## The split between those two files is the whole design of this script

A ranked list of the domains a person visits **is a profile of that person**. SPEC invariant
2 forbids storing a URL and D22 forbids publishing a domain list; this repository is public;
and `test_published_reports.py` scans every committed benchmark for anything host-shaped. So:

* **The committed report publishes** how many rules exist, how strong they are, how much of
  the person's browsing they cover, how that compares to chance — and **category-level rules
  in full**, because the fifteen categories are a public vocabulary shipped in
  `domains.json`, not a fact about anyone.
* **The domain-level rules themselves go to `data/`**, gitignored, exactly as D100 put the
  replication report there. Akash can read them; nobody else can.

That is not a limitation of the analysis. Both halves answer real questions, and the public
half is the one that generalises — *how much co-occurrence structure does one person's
browsing contain* is answerable without naming a single site.

## Confidence is the number that misleads

A rule can reach 90% confidence purely because its consequent appears in 90% of sessions.
Lift divides that out. But lift on small counts is noisy, and any corpus yields **some**
high-lift pairs by chance, so D24's mandatory baseline here is a null corpus: same session
sizes, items drawn in proportion to how often each really occurs, no genuine association
anywhere. The rule count means nothing without the count that chance produces.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "research"))

from tise_research.data.chrome_history import DEFAULT_VIEW  # noqa: E402
from tise_research.data.corpus import load_events  # noqa: E402
from tise_research.features.sessions import sessionise  # noqa: E402
from tise_research.models.associations import (  # noqa: E402
    ASSOCIATION_SEED,
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_MIN_LIFT,
    DEFAULT_MIN_SESSIONS,
    Rule,
    association_rules,
    null_rule_band,
    session_itemsets,
)

TIMEOUT_SECONDS = 1800.0

NULL_RUNS = 30

#: D27. `unknown` is a bucket, not a category, and a rule about it is unpresentable — the
#: same reason it is kept out of every headline in this project. Dropped from the
#: **category** analysis only; the domains inside it stay in the domain analysis, where they
#: are never named anyway.
EXCLUDED_CATEGORY = "unknown"

#: How many rules the committed report lists in full. Categories only — see the docstring.
TOP_CATEGORY_RULES = 15


@dataclass(frozen=True, slots=True)
class Level:
    """One analysis at one granularity: domains, or categories."""

    name: str
    sessions: int
    dropped_single: int
    vocabulary: int
    rules: tuple[Rule, ...]
    null_median: float
    null_low: int
    null_high: int
    #: Sessions containing at least one rule's antecedent — how much of the person's
    #: browsing these rules would ever have anything to say about.
    covered_sessions: int
    #: The strongest lift found at **any** confidence, thresholds removed. Without it,
    #: "nothing cleared the bar" is unreadable: a best lift of 1.49 is a near miss and 1.02
    #: is an absence, and the sentence is identical either way.
    best_lift: float
    #: How many pairs were dense enough to be judged at all. A best lift computed over two
    #: eligible pairs says much less than one computed over four hundred.
    eligible_pairs: int

    @property
    def beats_chance(self) -> bool:
        return len(self.rules) > self.null_high

    @property
    def coverage(self) -> float:
        return self.covered_sessions / self.sessions if self.sessions else 0.0


@dataclass(frozen=True, slots=True)
class CorpusResult:
    name: str
    events: int
    total_sessions: int
    domains: Level
    categories: Level


def _level(
    name: str, itemsets: list[frozenset[str]], dropped: int, total: int
) -> Level:
    rules = association_rules(itemsets)
    # Same support floor, the other two thresholds removed, so the report can say how close
    # the corpus came rather than only that it did not arrive.
    unfiltered = association_rules(itemsets, min_confidence=0.0, min_lift=0.0)
    median, low, high = null_rule_band(itemsets, runs=NULL_RUNS)
    antecedents = {rule.antecedent for rule in rules}
    return Level(
        name=name,
        sessions=len(itemsets),
        dropped_single=dropped,
        vocabulary=len({item for items in itemsets for item in items}),
        rules=tuple(rules),
        null_median=median,
        null_low=low,
        null_high=high,
        covered_sessions=sum(
            1 for items in itemsets if items & antecedents
        ),
        best_lift=max((rule.lift for rule in unfiltered), default=0.0),
        # Both directions of a pair share a lift, so the pair count is half the rule count.
        eligible_pairs=len(unfiltered) // 2,
    )


def measure(copy_path: Path, *, view: str) -> CorpusResult:
    events = load_events(copy_path, view=view)
    sessions = sessionise(events, timeout_seconds=TIMEOUT_SECONDS)
    if not sessions:
        raise ValueError(f"{copy_path.stem}: no sessions")

    by_domain = [[event.domain for event in session.events] for session in sessions]
    by_category = [
        [
            event.category
            for event in session.events
            if event.category != EXCLUDED_CATEGORY
        ]
        for session in sessions
    ]

    domain_sets = session_itemsets(by_domain)
    category_sets = session_itemsets(by_category)

    return CorpusResult(
        name=copy_path.stem,
        events=len(events),
        total_sessions=len(sessions),
        domains=_level(
            "domain", domain_sets, len(sessions) - len(domain_sets), len(sessions)
        ),
        categories=_level(
            "category", category_sets, len(sessions) - len(category_sets), len(sessions)
        ),
    )


def _level_summary(level: Level, total_sessions: int) -> str:
    verdict = (
        f"**{len(level.rules)} rules, against {level.null_median:.0f} from chance** "
        f"(95% band [{level.null_low}, {level.null_high}]) — "
        + (
            "more than a corpus of this shape produces with no associations in it."
            if level.beats_chance
            else "**inside the band chance produces**, so this is not evidence of "
            "structure. The rules may still be individually real; the count is not "
            "evidence that any of them is."
        )
    )
    lifts = [rule.lift for rule in level.rules]
    if lifts:
        spread = f"Lift runs {min(lifts):.1f} to {max(lifts):.1f}."
    elif level.best_lift < DEFAULT_MIN_LIFT:
        spread = (
            f"**No rule cleared the thresholds, and none came close**: the strongest lift "
            f"at any confidence was **{level.best_lift:.2f}** over {level.eligible_pairs:,} "
            f"pairs dense enough to judge. That is an absence, not a near miss — "
            f"co-occurrence here is close to what independence predicts."
        )
    else:
        spread = (
            f"No rule cleared **all three** thresholds, though the strongest lift was "
            f"{level.best_lift:.2f} over {level.eligible_pairs:,} eligible pairs: "
            f"confidence, not lift, is what excluded it."
        )
    plural = "categories" if level.name == "category" else f"{level.name}s"
    return (
        f"| sessions with 2+ distinct {plural} | {level.sessions:,} of "
        f"{total_sessions:,} |\n"
        f"| dropped (a single {level.name}, so no pair) | {level.dropped_single:,} |\n"
        f"| distinct {plural} | {level.vocabulary:,} |\n"
        f"| pairs dense enough to judge | {level.eligible_pairs:,} |\n"
        f"| strongest lift at any confidence | {level.best_lift:.2f} |\n"
        f"| rules | {len(level.rules):,} |\n"
        f"| chance rules (median) | {level.null_median:.0f} |\n"
        f"| sessions a rule could speak to | {level.covered_sessions:,} "
        f"({level.coverage:.0%}) |\n\n{verdict} {spread}"
    )


def _section(item: CorpusResult) -> str:
    category_rows = [
        "| Rule | Sessions together | Confidence | Lift |",
        "|---|---:|---:|---:|",
    ]
    for rule in item.categories.rules[:TOP_CATEGORY_RULES]:
        category_rows.append(
            f"| `{rule.antecedent}` → `{rule.consequent}` | "
            f"{rule.support_sessions} of {rule.antecedent_sessions} | "
            f"{rule.confidence:.0%} | {rule.lift:.2f} |"
        )
    if len(item.categories.rules) <= 1:
        category_rows = ["*No category rule cleared all three thresholds.*"]

    return f"""### {item.name}

{item.events:,} events in {item.total_sessions:,} sessions.

#### Domains — counts only, never names

| | |
|---|---:|
{_level_summary(item.domains, item.total_sessions)}

The rules themselves are written to `data/domain-rules.md`, which is gitignored. A ranked
list of a person's domains is a profile of that person, and this repository is public.

#### Categories — named in full, because the vocabulary is public

| | |
|---|---:|
{_level_summary(item.categories, item.total_sessions)}

{chr(10).join(category_rows)}
"""


def write_report(items: list[CorpusResult], *, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "domain-associations.md"

    domain_beats = [item.name for item in items if item.domains.beats_chance]
    category_beats = [item.name for item in items if item.categories.beats_chance]

    def listed(names: list[str]) -> str:
        return ", ".join(f"`{n}`" for n in names) if names else "**nothing**"

    path.write_text(
        f"""# T-F · What co-occurs inside a session?

Generated by `analysis/domain_associations.py`. **Do not edit by hand.** Regenerate with:

```
uv run python analysis/domain_associations.py
```

**Descriptive. Nothing here is predicted and no bar is cleared** — D95 adopted T-F precisely
because it does not have to beat a per-topic rate table, which D92 established is hard.

## What this page can and cannot print

A ranked list of the domains a person visits **is a profile of that person**. SPEC invariant
2 and D22 forbid publishing one, and `test_published_reports.py` scans every committed
benchmark for anything host-shaped. So the domain analysis appears here as **counts, spreads
and comparisons against chance**, and its rules are written to gitignored `data/` — the same
split D100 used for the replication report. **Category rules are printed in full**: the
fifteen categories are a public vocabulary shipped in `domains.json`, not a fact about anyone.

The public half is also the half that generalises. *How much co-occurrence structure does one
person's browsing contain* is answerable without naming a single site.

## Rules are pairs, on presence

A rule is `X → Y`: when X is in a session, Y often is too. Single-item antecedents only —
that is what "which domains co-occur" asks, and a few hundred sessions cannot support the
item-set lattice a general FP-Growth enumerates. A session that visits one domain forty times
contributes it **once**, or the rules are dominated by whatever gets reloaded.

Thresholds, all declared: at least **{DEFAULT_MIN_SESSIONS} sessions** together,
**{DEFAULT_MIN_CONFIDENCE:.0%} confidence**, **lift ≥ {DEFAULT_MIN_LIFT}**. Lift 1.0 is
independence; anything at or below it is not a rule whatever its confidence says.

## The baseline, which rule-mining usually omits

Confidence is the misleading number: a rule reaches 90% for free if its consequent is in 90%
of sessions. Lift divides that out, and lift on small counts is itself noisy — any corpus
yields some high-lift pairs by chance. So every count below is printed beside a **null**:
{NULL_RUNS} corpora of the same session sizes, filled with items in proportion to how often
each really occurs, containing **no associations at all**. Seed `{ASSOCIATION_SEED}`,
declared and never tuned.

Session sizes are preserved exactly; item frequencies in expectation rather than exactly,
which errs toward *more* null rules for common items and so makes the comparison conservative.

## Result

- Domain rules beat chance on: {listed(domain_beats)}
- Category rules beat chance on: {listed(category_beats)}

## Results

{chr(10).join(_section(item) for item in items)}

## Limitations

- **One person's browsing**, three browsers. D18 forbids merging them.
- **A session is a declared 30-minute gap** (D17), and every rule here is scoped to one. A
  longer timeout merges sittings and manufactures co-occurrence that never happened; a
  shorter one splits them and destroys real co-occurrence. This is the single most
  load-bearing assumption on the page.
- **Co-occurrence is not order and not causation.** `X → Y` says they appeared in the same
  session, not that X led to Y. T-C measured ordered transitions and is the page for that.
- **`unknown` is excluded from the category analysis** (D27) and its domains are not excluded
  from the domain analysis, where nothing is named anyway. So the two halves of this page
  cover slightly different browsing, deliberately.
- **Thresholds are declared, not fitted**, and the rule count moves with them. Two of the
  three are conventional; none was chosen after seeing which rules survived.
""",
        encoding="utf-8",
    )
    return path


def write_local(items: list[CorpusResult], *, data_dir: Path) -> Path:
    """The domain rules themselves. **Gitignored** — see the module docstring."""
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "domain-rules.md"

    sections = []
    for item in items:
        rows = ["| Rule | Sessions together | Confidence | Lift |", "|---|---:|---:|---:|"]
        for rule in item.domains.rules:
            rows.append(
                f"| {rule.antecedent} -> {rule.consequent} | "
                f"{rule.support_sessions} of {rule.antecedent_sessions} | "
                f"{rule.confidence:.0%} | {rule.lift:.2f} |"
            )
        if len(rows) == 2:
            rows = ["*No domain rule cleared all three thresholds.*"]
        sections.append(f"## {item.name}\n\n{chr(10).join(rows)}\n")

    path.write_text(
        "# T-F domain rules — LOCAL ONLY, NEVER COMMIT\n\n"
        "Generated by `analysis/domain_associations.py`. This file names domains, which is a "
        "profile of a person (SPEC invariant 2, D22). `data/` is gitignored and this file "
        "must stay there. The committed report at `docs/benchmarks/domain-associations.md` "
        "carries the counts and the comparison against chance.\n\n"
        + "\n".join(sections),
        encoding="utf-8",
    )
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "docs" / "benchmarks")
    parser.add_argument("--view", default=DEFAULT_VIEW, choices=["shipped", "chosen", "raw"])
    args = parser.parse_args()

    copies = (
        [args.corpus] if args.corpus else sorted((REPO_ROOT / "data").glob("history-*.copy"))
    )
    items: list[CorpusResult] = []
    for copy_path in copies:
        try:
            item = measure(copy_path, view=args.view)
        except ValueError as error:
            print(f"Skipping {error}")
            continue
        items.append(item)
        print(
            f"{item.name}: {len(item.domains.rules)} domain rules "
            f"(chance {item.domains.null_median:.0f}), "
            f"{len(item.categories.rules)} category rules "
            f"(chance {item.categories.null_median:.0f})"
        )

    if not items:
        print("No corpus produced sessions.")
        return 1

    print(f"Wrote {write_report(items, out_dir=args.out)}")
    print(f"Wrote {write_local(items, data_dir=REPO_ROOT / 'data')} (gitignored)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
