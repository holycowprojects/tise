"""T1 — measure the shape of real browsing history.

This is the gate. It answers the question the whole project rests on: does one person's
actual browsing contain enough signal to predict anything? If fewer than ~300
`return_24h` labels are reachable in eight weeks at any sensible category count, the
prediction target changes before a line of extension code is written.

Run:
    uv run python analysis/history_shape.py --out docs/benchmarks/

Two outputs, deliberately split:

* ``docs/benchmarks/history-shape.md`` — **published**. Distributions, coverage
  percentages, label estimates. No domain names, no visit counts per domain.
* ``data/history-shape-domains.md`` — **local only, gitignored**. The ranked domain
  table, which T2 needs to build the category map.

The split exists because a ranked list of a person's top domains with visit counts is a
profile of that person, and this repository is public. See SPEC.md invariant 2.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, tzinfo
from pathlib import Path

from tise_research.data.chrome_history import (
    Visit,
    copy_history_db,
    default_history_path,
    load_visits,
)
from tise_research.data.shape import (
    LabelStats,
    ascii_histogram,
    estimate_return_24h_labels,
    find_gap_valley,
    inter_visit_gaps,
    percentiles,
    sessionise,
    visits_per_day,
)

#: Category counts to test. The winner sets the taxonomy size at T2.
CATEGORY_COUNTS = (8, 15, 25)

#: The gate, from tasks/plan.md. Eight weeks of browsing must reach this.
GATE_LABELS = 300
GATE_WEEKS = 8

#: Session timeouts to report alongside whatever the histogram actually says, so the
#: empirical answer can be compared against the conventional one rather than replaced
#: by it.
CANDIDATE_TIMEOUTS = (300, 900, 1800, 3600)

GAP_PERCENTILES = (5, 25, 50, 75, 90, 95, 99)


def pseudo_categorise(visits: list[Visit], count: int) -> list[tuple[datetime, str]]:
    """Assign each visit to one of `count` proxy categories.

    T2 builds the real taxonomy; it depends on this task's output, so T1 cannot use it.
    The proxy is the top ``count - 1`` domains by visit volume, each as its own
    category, with everything else collapsed into ``other``.

    This is a **lower bound** on label volume, not an estimate of the real thing: a real
    taxonomy groups related domains together, which produces more visits per category
    and therefore more days on which a category appears.
    """
    frequency = Counter(visit.domain for visit in visits)
    top = {domain for domain, _ in frequency.most_common(max(count - 1, 1))}
    return [
        (visit.visited_at, visit.domain if visit.domain in top else "other")
        for visit in visits
    ]


def coverage_of_top_n(visits: list[Visit], n: int) -> float:
    """Share of visits accounted for by the top `n` domains. Feeds T2's ≥80% target."""
    if not visits:
        return 0.0
    frequency = Counter(visit.domain for visit in visits)
    return sum(count for _, count in frequency.most_common(n)) / len(visits)


def _format_seconds(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value < 90:
        return f"{value:,.0f}s"
    if value < 5400:
        return f"{value / 60:,.1f}m"
    return f"{value / 3600:,.1f}h"


def _label_table(rows: dict[int, LabelStats]) -> str:
    lines = [
        "| Categories | Labels | Positives | Positive rate | Labels/week | "
        f"In {GATE_WEEKS} weeks | Gate |",
        "|---:|---:|---:|---:|---:|---:|:--|",
    ]
    for count, stats in rows.items():
        projected = stats.labels_per_week * GATE_WEEKS
        verdict = "PASS" if projected >= GATE_LABELS else "FAIL"
        rate = "n/a" if stats.positive_rate is None else f"{stats.positive_rate:.1%}"
        lines.append(
            f"| {count} | {stats.total:,} | {stats.positives:,} | {rate} | "
            f"{stats.labels_per_week:,.0f} | {projected:,.0f} | {verdict} |"
        )
    return "\n".join(lines)


def build_public_report(
    visits: list[Visit],
    *,
    tz: tzinfo,
    generated_at: datetime,
    source: Path,
    redirects_excluded: int,
) -> str:
    """The committed report. Aggregates only — no domain names, no per-domain counts."""
    times = [visit.visited_at for visit in visits]
    gaps = inter_visit_gaps(times)
    per_day = visits_per_day(times, tz=tz)
    daily_counts = sorted(per_day.values())
    span_days = (
        (max(times) - min(times)).total_seconds() / 86_400 if len(times) > 1 else 0.0
    )

    with_duration = [v for v in visits if v.duration_seconds is not None]
    duration_share = len(with_duration) / len(visits) if visits else 0.0

    valley = find_gap_valley(gaps)
    label_rows = {
        count: estimate_return_24h_labels(pseudo_categorise(visits, count), tz=tz)
        for count in CATEGORY_COUNTS
    }
    best = max(label_rows.values(), key=lambda s: s.labels_per_week)
    projected_best = best.labels_per_week * GATE_WEEKS
    gate_passed = projected_best >= GATE_LABELS

    gap_pcts = percentiles(gaps, GAP_PERCENTILES)
    day_pcts = percentiles([float(c) for c in daily_counts], (50, 90))

    session_lines = []
    for timeout in CANDIDATE_TIMEOUTS:
        sessions = sessionise(times, timeout_seconds=timeout)
        mean_length = len(times) / len(sessions) if sessions else 0.0
        session_lines.append(
            f"| {_format_seconds(timeout)} | {len(sessions):,} | {mean_length:,.1f} |"
        )

    if valley is not None:
        empirical_sessions = sessionise(times, timeout_seconds=valley)
        empirical = (
            f"**{_format_seconds(valley)}** ({valley:,.0f}s), giving "
            f"{len(empirical_sessions):,} sessions at "
            f"{len(times) / len(empirical_sessions):,.1f} visits each."
        )
    else:
        empirical = (
            "**Not found.** The gap distribution has no clear trough between two modes, "
            "so there is no empirical boundary to adopt. Do not substitute a round "
            "number — record the absence and revisit with more data."
        )

    return f"""# T1 — Shape of real browsing history

Generated by `analysis/history_shape.py` on {generated_at:%Y-%m-%d %H:%M %Z}.
**Do not edit by hand.** Regenerate with:

```
uv run python analysis/history_shape.py --out docs/benchmarks/
```

Source: local Chrome history database (`{source.name}`), one person, timezone `{tz}`.
Domain names and per-domain counts are deliberately **not** in this file — they live in
`data/history-shape-domains.md`, which is gitignored. A ranked list of someone's top
domains is a profile of that person, and this repository is public.

## Verdict

{"**GATE PASSED.**" if gate_passed else "**GATE FAILED.**"} The best proxy taxonomy
reaches **{projected_best:,.0f}** `return_24h` labels in {GATE_WEEKS} weeks, against a
required ~{GATE_LABELS:,}.

{
    "The primary target stands. Proceed to T2."
    if gate_passed
    else "`return_24h` does not yield enough labels at this browsing volume. "
    "Stop and change the target before writing extension code — see the plan's gate."
}

Note that the proxy taxonomy is a **lower bound**. It treats each top domain as its own
category, whereas a real taxonomy groups related domains together, producing more visits
per category and therefore more labelled days.

## Volume

| Measure | Value |
|---|---:|
| Visits (chosen navigations) | {len(visits):,} |
| Redirect hops excluded | {redirects_excluded:,} |
| History span | {span_days:,.1f} days |
| Distinct registrable domains | {len({v.domain for v in visits}):,} |
| Days with any browsing | {len(per_day):,} |
| Median visits per active day | {day_pcts[50]:,.0f} |
| 90th percentile visits per active day | {day_pcts[90]:,.0f} |

## Domain concentration

How much of browsing the top *n* domains account for. T2 needs ≥ 80% coverage from the
shipped map.

| Top n domains | Share of visits |
|---:|---:|
{
    chr(10).join(
        f"| {n} | {coverage_of_top_n(visits, n):.1%} |"
        for n in (10, 25, 50, 100, 200)
    )
}

## Inter-visit gaps

| Percentile | Gap |
|---:|---:|
{chr(10).join(f"| p{p} | {_format_seconds(gap_pcts[p])} |" for p in GAP_PERCENTILES)}

Distribution on a log scale ({len(gaps):,} gaps):

```
{ascii_histogram(gaps, bins=24, log=True)}
```

### Session boundary

Empirically detected trough: {empirical}

For comparison, conventional timeouts on the same data:

| Timeout | Sessions | Mean visits per session |
|---:|---:|---:|
{chr(10).join(session_lines)}

## `return_24h` label volume

One label per (category, day). The window closes at local midnight; the label is
positive if the category recurs within the following 24 hours. Activity on the day
itself never decides the label — that is the leakage guard.

{_label_table(label_rows)}

## Compat variants — `full` versus `history`

Chrome's history **file** records `visit_duration`. The `chrome.history` **API** that the
extension must use does **not**. Anything derived from dwell time is therefore research
only and can never ship.

| | `full` (this file) | `history` (what the extension gets) |
|---|---|---|
| Visit timestamp | yes | yes |
| Transition type | yes | yes |
| Registrable domain | yes | yes |
| **Dwell duration** | **yes** | **no** |
| Referring visit | yes | yes |

Visits in this database carrying a usable duration: **{duration_share:.1%}**
({len(with_duration):,} of {len(visits):,}). A zero duration means *not recorded*, which
is an absence rather than a zero-second dwell, and is excluded from that share.

Everything else in this report — volume, gaps, sessions, label counts — is identical in
both variants, because none of it uses duration. **The label estimate above, and the
gate verdict, are therefore `history`-class results and are safe to build on.**

The exact field list the API returns is confirmed experimentally at T5, not assumed here.

## Known limitations

- **One person's browsing.** Every number describes the author. Nothing here
  generalises, and the published benchmarks must say so.
- **Proxy categories.** The real taxonomy arrives at T2; these counts are a floor.
- **Provisional suffix handling.** `registrable_domain` uses an embedded list of
  multi-part public suffixes rather than the full Public Suffix List. Adding a PSL
  dependency is an "ask first" item, and the choice must be made once for both
  TypeScript and Python because the function is parity-critical. Owed at T2/T6.
- **Chrome retention.** Chrome expires history on its own schedule, so the span above is
  what survived, not everything that happened.
"""


def build_local_domain_table(visits: list[Visit], *, top: int = 100) -> str:
    """The ranked domain table. Never committed — this is the private half."""
    frequency = Counter(visit.domain for visit in visits)
    total = len(visits) or 1
    lines = [
        "# T1 — top domains (LOCAL ONLY)",
        "",
        "Generated by `analysis/history_shape.py`. **Gitignored on purpose.**",
        "This is a ranked profile of one person's browsing. It feeds T2's category map;",
        "it does not go into the repository.",
        "",
        "| Rank | Domain | Visits | Share | Cumulative |",
        "|---:|---|---:|---:|---:|",
    ]
    cumulative = 0
    for rank, (domain, count) in enumerate(frequency.most_common(top), start=1):
        cumulative += count
        lines.append(
            f"| {rank} | {domain} | {count:,} | {count / total:.2%} | "
            f"{cumulative / total:.1%} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/benchmarks"),
        help="Directory for the published report.",
    )
    parser.add_argument(
        "--history",
        type=Path,
        default=None,
        help="Chrome history database. Defaults to the Windows default profile.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Local scratch directory. Gitignored.",
    )
    args = parser.parse_args()

    source = args.history or default_history_path()
    data_dir: Path = args.data_dir
    copy_path = data_dir / "History.copy"

    print(f"Copying {source} -> {copy_path}")
    print("  (the original is opened read-only and never modified)")
    copy_history_db(source, copy_path)

    visits = load_visits(copy_path)
    # Redirect hops are recorded as visits but nobody chose to go there. Counting them
    # is what buried the within-session mode on the first run of this script.
    with_redirects = load_visits(copy_path, exclude_redirects=False)
    redirects_excluded = len(with_redirects) - len(visits)
    print(
        f"Loaded {len(visits):,} chosen navigations "
        f"({redirects_excluded:,} redirect hops excluded)."
    )
    if not visits:
        print("No visits found. Nothing to measure — is this the right profile?")
        return 1

    tz = datetime.now().astimezone().tzinfo
    assert tz is not None

    args.out.mkdir(parents=True, exist_ok=True)
    report_path = args.out / "history-shape.md"
    report_path.write_text(
        build_public_report(
            visits,
            tz=tz,
            generated_at=datetime.now().astimezone(),
            source=source,
            redirects_excluded=redirects_excluded,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {report_path}")

    domains_path = data_dir / "history-shape-domains.md"
    domains_path.write_text(build_local_domain_table(visits), encoding="utf-8")
    print(f"Wrote {domains_path}  (local only, gitignored)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
