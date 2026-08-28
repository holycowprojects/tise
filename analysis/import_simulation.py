"""Replay the shipped import against the history file, and see what it really drops.

**Why this exists.** D65 recorded that the redirect heuristic fires on 0.95% of visits in
production while `analysis/redirect_heuristic.py` scored it at recall 0.657 against the
file's redirect bits, and read that as the rule "recovering roughly one in fourteen".

That comparison assumed both were shown the same visits. They were not. **Chrome's
history API returns only the *end* of each redirect chain** — the same filter that makes
the history UI show a landing page rather than the hops that reached it. Measured against
this corpus: 98.5% of chain-end visits reached the export, against 8.7% of the rest.

So the API had already removed most redirect hops before the extension applied any rule
of its own, and it removed the chain *start* too — `google.com/url?...` is a chain start
with no redirect bit, which is why the research view keeps it and the extension does not.
D40's 50 ms rule is left judging the remainder with its referrers deleted.

This script therefore simulates the import in two stages, and the first one is the part
that was missing: **what Chrome hands over**, then **what the extension does with it**.
The verdict is cross-tabulated against the ground-truth redirect bit only the file
carries.

It is a *simulation of the product*, not a second product. Where it differs from
`prepareEvents` it is a bug in this file, and the differences that remain are listed in
`KNOWN_DIVERGENCES` rather than left for a reader to discover.

Aggregates only. No domain, URL or title is written to any path outside `data/`.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tise_research.data.chrome_history import (
    REDIRECT_MASK,
    SUBFRAME_TRANSITIONS,
    datetime_to_webkit,
    registrable_domain,
    transition_core,
    webkit_to_datetime,
)

#: Mirrors `REDIRECT_GAP_MS` in `extension/src/collect/import.ts`. Duplicated rather than
#: imported because there is no route from Python to a TypeScript constant; if it drifts,
#: this script is measuring a rule the extension does not apply.
REDIRECT_GAP_MS = 50

#: Mirrors `DEFAULT_IMPORT_DAYS`.
DEFAULT_IMPORT_DAYS = 90

#: Chrome's PageTransition chain markers. A redirect chain runs from a CHAIN_START visit
#: to a CHAIN_END one; everything between is a hop. The history API returns chain ends,
#: which is why the UI shows where you landed rather than what bounced you there.
CHAIN_START = 0x1000_0000
CHAIN_END = 0x2000_0000

#: Where this simulation cannot be faithful, stated rather than hidden.
KNOWN_DIVERGENCES = (
    "The API stage is emulated as the chain-end filter, which matches 98.5%/8.7% on this "
    "corpus but is inferred from behaviour, not read from Chrome's source. Anything else "
    "`search()` does — ordering, internal caps — is not observable from a file.",
    "`getVisits` returns visits in milliseconds; the file stores microseconds. Gaps are "
    "compared in microseconds here, which is finer, so a hop this script flags at 50 ms "
    "the extension also flags.",
    "The extension never sees the redirect bits. They are used here only to label rows, "
    "never to decide one.",
)

_ROWS = """
SELECT v.id, v.visit_time, v.transition, v.from_visit, u.url
FROM visits AS v
JOIN urls AS u ON u.id = v.url
ORDER BY v.visit_time
"""

#: Every fate a visit can meet, in the order it meets them. `api-hidden` is Chrome's own
#: decision and happens before the extension has any say.
VERDICTS = ("api-hidden", "out-of-window", "subframe", "redirect", "not-web", "kept")


@dataclass(frozen=True, slots=True)
class Row:
    visit_id: int
    visit_time_us: int
    transition: int
    from_visit: int
    url: str

    @property
    def is_redirect_hop(self) -> bool:
        return bool(self.transition & REDIRECT_MASK)

    @property
    def is_chain_end(self) -> bool:
        """Whether Chrome's history API will hand this visit over at all."""
        return bool(self.transition & CHAIN_END)


def load_rows(db: Path) -> list[Row]:
    connection = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        return [Row(*row) for row in connection.execute(_ROWS)]
    finally:
        connection.close()


def simulate(
    rows: list[Row], *, start_us: int, end_us: int
) -> tuple[dict[int, str], dict[str, int]]:
    """Apply Chrome's filter, then the shipped ones, in order, to every visit.

    Returns the verdict per visit id and a domain histogram of what survived.

    The two stages are not interchangeable. `referrer_times` is built **after** the API
    stage, over what Chrome actually hands over, because that is what the extension has:
    a hop whose referrer Chrome withheld cannot be judged, and `isLikelyRedirect` keeps
    it. Building the map over the whole file instead would let the 50 ms rule resolve
    referrers the shipped code never receives, and the simulation would quietly describe
    a better import than the one that runs.
    """
    fetched_urls = {row.url for row in rows if start_us <= row.visit_time_us <= end_us}
    in_corpus = [row for row in rows if row.url in fetched_urls]

    verdicts: dict[int, str] = {}
    fetched = []
    for row in in_corpus:
        if row.is_chain_end:
            fetched.append(row)
        else:
            verdicts[row.visit_id] = "api-hidden"

    referrer_times = {row.visit_id: row.visit_time_us for row in fetched}
    limit_us = REDIRECT_GAP_MS * 1000
    kept_domains: Counter[str] = Counter()

    for row in fetched:
        if not (start_us <= row.visit_time_us <= end_us):
            verdicts[row.visit_id] = "out-of-window"
            continue
        if transition_core(row.transition) in SUBFRAME_TRANSITIONS:
            verdicts[row.visit_id] = "subframe"
            continue

        referrer = referrer_times.get(row.from_visit) if row.from_visit else None
        gap_us = row.visit_time_us - referrer if referrer is not None else None
        if gap_us is not None and 0 <= gap_us <= limit_us:
            verdicts[row.visit_id] = "redirect"
            continue

        domain = registrable_domain(row.url)
        if domain is None:
            verdicts[row.visit_id] = "not-web"
            continue

        verdicts[row.visit_id] = "kept"
        kept_domains[domain] += 1

    return verdicts, dict(kept_domains)


def crosstab(rows: list[Row], verdicts: dict[int, str]) -> dict[str, dict[str, int]]:
    """Verdict against ground truth. The row that matters is `redirect hop`."""
    table = {
        "redirect hop": dict.fromkeys(VERDICTS, 0),
        "chosen navigation": dict.fromkeys(VERDICTS, 0),
    }
    for row in rows:
        verdict = verdicts.get(row.visit_id)
        if verdict is None:
            continue
        key = "redirect hop" if row.is_redirect_hop else "chosen navigation"
        table[key][verdict] += 1
    return table


def export_domains(path: Path) -> Counter[str]:
    """Imported events only. Live events describe browsing the file's window predates."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Counter(
        str(event["domain"]) for event in raw["events"] if event.get("source") == "import"
    )


def compare(simulated: dict[str, int], exported: Counter[str]) -> dict[str, int | float]:
    """How far apart the two views are, in the units D65 used: events, not domains."""
    names = set(simulated) | set(exported)
    disagreement = sum(abs(simulated.get(name, 0) - exported.get(name, 0)) for name in names)
    total = sum(exported.values())
    return {
        "simulated_events": sum(simulated.values()),
        "exported_events": total,
        "simulated_domains": len(simulated),
        "exported_domains": len(exported),
        "only_simulated": len(set(simulated) - set(exported)),
        "only_exported": len(set(exported) - set(simulated)),
        "per_domain_disagreement": disagreement,
        "per_domain_disagreement_share": (disagreement / total) if total else 0.0,
    }


def render(browser: str, rows: list[Row], verdicts: dict[int, str], window: str) -> str:
    table = crosstab(rows, verdicts)
    considered = len(verdicts)
    hops = sum(table["redirect hop"].values())
    dropped_hops = hops - table["redirect hop"]["kept"]

    lines = [
        f"# Import simulation — {browser}",
        "",
        "Generated by `analysis/import_simulation.py`. Aggregates only.",
        "",
        "**Question:** D65 read the extension's `redirect` skip counter as the share of",
        "redirect hops the import catches, and concluded the rule was recovering one in",
        "fourteen. That assumed the extension was offered every visit the file holds. It",
        "is not: Chrome's history API hands over only the **end** of each redirect chain.",
        "This replays both stages — what Chrome supplies, then what the extension does",
        "with it — against the redirect bits the extension never sees.",
        "",
        f"- Window: {window}",
        f"- Visits considered: **{considered:,}**",
        f"- True redirect hops among them: **{hops:,}** ({hops / considered:.1%})",
        "",
        # Built from VERDICTS, never typed out: a hardcoded header silently shifts every
        # cell one column the moment a stage is added, which is exactly what happened here.
        "| ground truth | " + " | ".join(VERDICTS) + " |",
        "|---" + "|---:" * len(VERDICTS) + "|",
    ]
    for label, counts in table.items():
        cells = " | ".join(f"{counts[verdict]:,}" for verdict in VERDICTS)
        lines.append(f"| {label} | {cells} |")

    share = (dropped_hops / hops) if hops else 0.0
    by_chrome = table["redirect hop"]["api-hidden"]
    by_tise = dropped_hops - by_chrome
    true_flags = table["redirect hop"]["redirect"]
    false_flags = table["chosen navigation"]["redirect"]
    lines += [
        "",
        f"**Redirect hops that never become events: {dropped_hops:,} of {hops:,} "
        f"({share:.1%}).** Chrome withholds {by_chrome:,} of them before the",
        f"extension sees anything; the extension's own rules account for {by_tise:,}.",
        "Reading the `redirect` column alone credits the 50 ms rule with a job Chrome had",
        "already done, and hides that Chrome also withholds each chain's *start* — an",
        "ordinary navigation carrying no redirect bit at all.",
        "",
        f"**What the 50 ms rule does once Chrome has filtered: it flags {true_flags:,} "
        f"true redirect hop(s) and {false_flags:,} ordinary navigation(s).** D40 chose",
        "the threshold for precision on purpose, because a false positive deletes a page",
        "the person really visited while a false negative only leaves a hop in. Against",
        "the corpus Chrome actually supplies, that trade now runs the wrong way. This is",
        "a measurement on one profile per browser and it is not, on its own, grounds to",
        "remove the rule — but it is the number that decides it, and D40 never had it.",
        "",
        "**Known divergences from the shipped code:**",
        "",
    ]
    lines += [f"- {note}" for note in KNOWN_DIVERGENCES]
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay the shipped import over a history.")
    parser.add_argument("--history", type=Path, required=True, help="a `.copy` history db")
    parser.add_argument("--browser", required=True, help="label for the report, e.g. Chrome")
    parser.add_argument("--days", type=int, default=DEFAULT_IMPORT_DAYS)
    parser.add_argument(
        "--now",
        default=None,
        help="ISO instant the import ran; defaults to the last visit in the file",
    )
    parser.add_argument("--export", type=Path, default=None, help="an export to compare to")
    parser.add_argument("--out", type=Path, default=Path("docs/benchmarks"))
    args = parser.parse_args()

    rows = load_rows(args.history)
    if not rows:
        raise SystemExit("no visits in that file")

    now = (
        datetime.fromisoformat(args.now)
        if args.now
        else webkit_to_datetime(rows[-1].visit_time_us)
    )
    if now.tzinfo is None:
        raise SystemExit("--now must carry a timezone")
    start = now.astimezone(UTC) - timedelta(days=args.days)
    start_us, end_us = datetime_to_webkit(start), datetime_to_webkit(now)
    window = f"{start.date()} to {now.astimezone(UTC).date()} ({args.days} days)"

    verdicts, kept_domains = simulate(rows, start_us=start_us, end_us=end_us)

    slug = args.browser.strip().lower().replace(" ", "-")
    args.out.mkdir(parents=True, exist_ok=True)
    report = args.out / f"import-simulation-{slug}.md"
    report.write_text(render(args.browser, rows, verdicts, window), encoding="utf-8")
    print(f"wrote {report}")

    counts = Counter(verdicts.values())
    for verdict in VERDICTS:
        print(f"  {verdict:<14} {counts[verdict]:>7,}")

    if args.export is not None:
        stats = compare(kept_domains, export_domains(args.export))
        print("\nagainst the export (imported events only)")
        for key, value in stats.items():
            formatted = f"{value:.1%}" if isinstance(value, float) else f"{value:,}"
            print(f"  {key:<32} {formatted:>10}")


if __name__ == "__main__":
    main()
