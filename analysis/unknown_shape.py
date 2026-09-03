"""What `unknown` is actually made of, and what naming its head would be worth.

**This script fits nothing.** It counts, and every number it prints would be identical if no
model existed. That is what allows a bar to be set from it (D88).

**Why it exists.** D89 measured that clustering `unknown` by session co-occurrence finds zero
clusters at every threshold, and concluded the bucket "is a long tail of domains visited once
or twice". The first half is right and load-bearing: over half of these domains are seen
exactly once, so there is no co-visit signal to cluster on, and no amount of tuning reaches
it.

The second half read the domain count and not the event mass. In every corpus this project
has, **one domain is more than half of `unknown`** while most domains are seen once. Both
facts come from the same data. The tail is real and it is irrelevant; the head is where all
the weight is, and naming it needs no clustering at all.

**The head is institutional, and that is by design.** D26 and D88 keep employer, school,
council and neighbourhood domains out of the shipped map, because a published list of
workplaces is a profile of the people who work at them. So the head of `unknown` is large
*because the privacy design put it there*, and the only correct place to resolve it is on the
device, by the person. `overrides` and the editor for it already exist (D114). What does not
exist is anything that tells a person which domain is costing them.

Aggregates only. **No domain name is printed**, on any path, ever — pass `--local` to write
the ranked list to `data/`, which is gitignored, for acting on rather than publishing.
"""

from __future__ import annotations

import argparse
import collections
from dataclasses import replace
from pathlib import Path

from tise_research.categories import load_category_map
from tise_research.data.load import TiseExport, load_export
from tise_research.features.attention import ENGAGED_FEATURE_SET, attention_examples
from tise_research.features.events import Event

UNKNOWN = "unknown"

#: Reported concentration depths. The first is the whole argument.
DEPTHS = (1, 3, 5, 10, 20)

#: How many of the head a person would plausibly be asked about in one sitting.
PROMPTS = 3


def concentration(domains: collections.Counter[str]) -> dict[str, object]:
    """Where the mass sits, and how much of the tail is unreachable."""
    counts = sorted(domains.values(), reverse=True)
    total = sum(counts)
    if total == 0:
        return {"events": 0, "domains": 0, "share": {}, "seen_once": 0}
    return {
        "events": total,
        "domains": len(counts),
        "share": {n: sum(counts[:n]) / total for n in DEPTHS},
        "seen_once": sum(1 for c in counts if c == 1),
    }


def session_spread(events: list[Event]) -> dict[int, int]:
    """Domains appearing in at least k sessions — the input clustering would need."""
    from tise_research.features.sessions import sessionise

    seen: dict[str, set[str]] = collections.defaultdict(set)
    for session in sessionise(events, timeout_seconds=1800.0):
        for event in session.events:
            if event.category == UNKNOWN:
                seen[event.domain].add(session.session_id)
    return {k: sum(1 for s in seen.values() if len(s) >= k) for k in (2, 3, 5)}


def _named_labels(events: list[Event], timeout: float) -> tuple[int, int, float, int]:
    """`(labels, named, largest_category_share, categories)` for a set of events."""
    rows = attention_examples(events, timeout_seconds=timeout, feature_set=ENGAGED_FEATURE_SET)
    named = [r for r in rows if r.label.subject != UNKNOWN]
    per = collections.Counter(r.label.subject for r in named)
    largest = max(per.values()) / len(named) if named else 0.0
    return len(rows), len(named), largest, len(per)


def counterfactual(export: TiseExport, prompts: int) -> dict[str, object]:
    """What answering the top `prompts` would be worth, as a bracket rather than a guess.

    The product asks a person to pick a category and this script cannot know which they would
    pick, so it does not pretend to. It computes the two ends instead:

    * **merged** — the named domains join one already-established category. Best case: they
      inherit its history and clear the ten-prior-visit rule immediately.
    * **separate** — each gets a category of its own. Worst case: every one starts from zero
      and produces nothing until its eleventh dwelled visit.

    A real answer lands between them, and the bar has to be met at the *worst* end to mean
    anything.
    """
    events = list(export.events_with_dwell())
    timeout = export.session_timeout_seconds
    unknown = collections.Counter(e.domain for e in events if e.category == UNKNOWN)
    head = [name for name, _ in unknown.most_common(prompts)]

    labels, named, largest, categories = _named_labels(events, timeout)
    host = collections.Counter(
        e.category for e in events if e.category != UNKNOWN and e.dwell_seconds is not None
    )
    into = host.most_common(1)[0][0] if host else "search"

    merged = [replace(e, category=into) if e.domain in head else e for e in events]
    separate = [
        replace(e, category=f"named:{e.domain}") if e.domain in head else e for e in events
    ]

    return {
        "prompts": prompts,
        "head_events": sum(unknown[name] for name in head),
        "unknown_events": sum(unknown.values()),
        "today": (labels, named, largest, categories),
        "merged": _named_labels(merged, timeout),
        "separate": _named_labels(separate, timeout),
        "merged_into": into,
    }


def report(export: TiseExport) -> str:
    events = list(export.events_with_dwell())
    total = len(events)
    unknown_events = [e for e in events if e.category == UNKNOWN]
    by_domain = collections.Counter(e.domain for e in unknown_events)
    shape = concentration(by_domain)
    dwelled = collections.Counter(
        e.domain for e in unknown_events if e.dwell_seconds is not None
    )

    lines = [
        f"`unknown` holds {shape['events']:,} of {total:,} events "
        f"({shape['events'] / total:.1%}) across {shape['domains']} domains",
        "",
        "Where the mass sits",
        "",
    ]
    for depth in DEPTHS:
        share = shape["share"][depth]
        lines.append(f"  top {depth:>2} domains   {share:>6.1%} of unknown events")
    lines.append("")
    once = int(shape["seen_once"])
    domains = int(shape["domains"])
    lines.append(
        f"  seen exactly once   {once} of {domains} domains ({once / domains:.0%})"
    )

    spread = session_spread(events)
    lines.append("")
    lines.append("What clustering would have to work with")
    lines.append("")
    for k, n in sorted(spread.items()):
        lines.append(f"  domains in >={k} sessions   {n}")
    lines.append("")
    lines.append("  A domain seen once has no co-visit signal at any threshold. This is the")
    lines.append("  half of D89 that holds, and it is why no amount of tuning reaches it.")

    lines.append("")
    lines.append(
        f"Dwell-carrying unknown visits: {sum(dwelled.values())} "
        f"across {len(dwelled)} domains"
    )
    if dwelled:
        top = dwelled.most_common(1)[0][1]
        lines.append(f"  largest single domain   {top / sum(dwelled.values()):.1%} of them")
        lines.append("  Ranked by events and by dwelled visits, the head is not always the")
        lines.append("  same domain. Only dwelled visits produce labels.")

    cf = counterfactual(export, PROMPTS)
    labels, named, largest, categories = cf["today"]  # type: ignore[misc]
    lines.append("")
    lines.append(f"If the top {cf['prompts']} were named  "
                 f"({cf['head_events']:,} of {cf['unknown_events']:,} unknown events)")
    lines.append("")
    lines.append("                        labels   named   largest category   categories")
    for key, label in (("today", "today"), ("merged", "merged"), ("separate", "separate")):
        a, b, c, d = cf[key]  # type: ignore[misc]
        lines.append(f"  {label:<20}  {a:>6}  {b:>6}   {c:>15.0%}   {d:>10}")
    lines.append("")
    lines.append(
        f"  merged = joined `{cf['merged_into']}`, the largest established category, so"
    )
    lines.append("  they clear the ten-prior-visit rule at once. separate = a category each,")
    lines.append("  starting from zero. A real answer lands between the two, and a bar has to")
    lines.append("  be met at `separate` to mean anything.")
    return "\n".join(lines)


def local_ranking(export: TiseExport, limit: int = 25) -> str:
    """The ranked list, for `data/` only. This is the one output that names domains."""
    events = list(export.events_with_dwell())
    unknown = [e for e in events if e.category == UNKNOWN]
    by_domain = collections.Counter(e.domain for e in unknown)
    dwelled = collections.Counter(e.domain for e in unknown if e.dwell_seconds is not None)

    lines = [
        "# Unknown domains, ranked — LOCAL ONLY",
        "",
        "Gitignored, and named here because acting on it needs the names. Never published:",
        "the head of this list is institutional by design (D26), and publishing it would be",
        "publishing a profile.",
        "",
        "| events | dwelled | domain |",
        "|---:|---:|---|",
    ]
    for name, count in by_domain.most_common(limit):
        lines.append(f"| {count:,} | {dwelled.get(name, 0)} | `{name}` |")
    return "\n".join(lines) + "\n"


def history_corpora() -> list[tuple[str, collections.Counter[str]]]:
    """Unknown-domain counts from any local history copy, for the generalisation check."""
    from tise_research.data.chrome_history import load_visits

    category_map = load_category_map()
    out: list[tuple[str, collections.Counter[str]]] = []
    for path in sorted(Path("data").glob("history-*.copy")):
        if "firefox" in path.stem:
            from tise_research.data.firefox_history import load_visits as load  # noqa: F811
        else:
            load = load_visits
        try:
            visits = load(path)
        except Exception:  # noqa: BLE001 — a corpus that will not open is not a failure here
            continue
        counts = collections.Counter(
            v.domain for v in visits if category_map.lookup(v.domain) is None
        )
        if counts:
            out.append((path.stem, counts))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "export", nargs="?", type=Path, help="a v3 export; default newest in data/"
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="also write the ranked domain list to data/unknown-domains.md (gitignored)",
    )
    args = parser.parse_args()

    path = args.export
    if path is None:
        candidates = sorted(Path("data").glob("tise-export-*.json"))
        if not candidates:
            raise SystemExit("no export in data/; export one from the dashboard first")
        path = candidates[-1]

    export = load_export(path)
    print(f"{path.name}   exported {export.exported_at.isoformat(timespec='seconds')}")
    print()
    print(report(export))

    corpora = history_corpora()
    if corpora:
        print()
        print("Does the head generalise? (imported history, event mass only)")
        print()
        for name, counts in corpora:
            shape = concentration(counts)
            once = int(shape["seen_once"])
            print(
                f"  {name:<18} {shape['events']:>6,} events / {shape['domains']:>3} domains"
                f"   top1 {shape['share'][1]:>5.1%}   top10 {shape['share'][10]:>5.1%}"
                f"   seen-once {once / shape['domains']:>3.0%}"
            )

    if args.local:
        out = Path("data") / "unknown-domains.md"
        out.write_text(local_ranking(export), encoding="utf-8")
        print()
        print(f"wrote {out} (gitignored)")


if __name__ == "__main__":
    main()
