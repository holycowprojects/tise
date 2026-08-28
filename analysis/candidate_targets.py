"""T19 — which of the four candidate targets can this data actually support?

    uv run python analysis/candidate_targets.py

Writes `docs/benchmarks/candidate-targets.md`. **No model is fitted and nothing is scored**,
which is exactly why D88 allows the data-sufficiency gate to be set after reading it: there
is no performance number here that a bar could be quietly fitted to.

D88 retired `return_24h` on an argument. This is the measurement that argument still owes.
It can kill `block_volume` — if the labels are too few or the base rate collapses to
something a constant already predicts — and T20 pre-registers whatever survives, before any
model exists.

Aggregates only. No domain, URL or title is written anywhere by this script.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, tzinfo
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "research"))

from tise_research.data.chrome_history import DEFAULT_VIEW  # noqa: E402
from tise_research.data.corpus import load_events  # noqa: E402
from tise_research.eval.candidates import (  # noqa: E402
    DEFAULT_MIN_PRIOR_BLOCKS,
    DEFAULT_TRAILING_BLOCKS,
    BlockVolumeStats,
    DormancyStats,
    NextCategoryStats,
    NoveltyStats,
    block_volume_stats,
    dormancy_stats,
    next_category_stats,
    novelty_stats,
)
from tise_research.eval.clusters import (  # noqa: E402
    DEFAULT_THRESHOLD,
    ClusterStats,
    cluster_stats,
)
from tise_research.features.blocks import (  # noqa: E402
    BLOCK_TYPES,
    Block,
    blocks_from_events,
    complete_blocks,
)
from tise_research.features.sessions import sessionise  # noqa: E402

TIMEOUT_SECONDS = 1800.0

#: Thresholds reported around the declared one, so a reader can see whether the answer
#: rests on the exact value. Sensitivity, not a search — none of these picks anything.
THRESHOLD_SWEEP = (0.3, 0.4, 0.5, 0.6, 0.7)

#: Minimum-prior-block values to report label yield at. With only a handful of blocks in
#: eight weeks this rule may be the binding constraint rather than the data, and that has
#: to be visible. Reported, never selected from — D88 fixed the declared value at 6.
PRIOR_SWEEP = (2, 3, 4, 6, 8)


@dataclass(frozen=True, slots=True)
class CorpusMeasurement:
    name: str
    events: int
    blocks: dict[str, int]
    volume: dict[str, BlockVolumeStats]
    novelty: dict[str, NoveltyStats]
    dormancy: dict[str, DormancyStats]
    next_category: NextCategoryStats
    clusters: ClusterStats
    sweep: dict[float, int]
    #: Labels at each candidate `min_prior`, per block type. Sensitivity, not selection:
    #: with only a handful of blocks the minimum-history rule may be doing all the work,
    #: and that has to be visible rather than inferred.
    prior_sweep: dict[str, dict[int, int]]
    #: The same target at **daily** granularity. Weekly blocks turn months of browsing
    #: into a handful of numbers; a day is the smallest unit that still has a "usual".
    daily: BlockVolumeStats
    daily_blocks: int


def _pct(value: float | None, spec: str = ".1%") -> str:
    return "—" if value is None else format(value, spec)


def measure(copy_path: Path, *, tz: tzinfo, view: str) -> CorpusMeasurement:
    events = load_events(copy_path, view=view)
    every_block = blocks_from_events(events, tz=tz)
    blocks: list[Block] = complete_blocks(every_block, tz=tz)
    daily_blocks: list[Block] = complete_blocks(
        blocks_from_events(events, tz=tz, granularity="day"), tz=tz
    )

    sessions = [
        sorted({event.category for event in session.events})
        for session in sessionise(events, timeout_seconds=TIMEOUT_SECONDS)
    ]

    return CorpusMeasurement(
        name=copy_path.stem,
        events=len(events),
        blocks={kind: sum(1 for b in blocks if b.kind == kind) for kind in BLOCK_TYPES},
        volume={
            kind: block_volume_stats(blocks, kind=kind) for kind in BLOCK_TYPES
        },
        novelty={
            kind: novelty_stats(blocks, events, kind=kind) for kind in BLOCK_TYPES
        },
        dormancy={kind: dormancy_stats(blocks, kind=kind) for kind in BLOCK_TYPES},
        next_category=next_category_stats(sessions),
        clusters=cluster_stats(events, timeout_seconds=TIMEOUT_SECONDS),
        sweep={
            value: cluster_stats(
                events, timeout_seconds=TIMEOUT_SECONDS, threshold=value
            ).clusters
            for value in THRESHOLD_SWEEP
        },
        prior_sweep={
            kind: {
                value: block_volume_stats(blocks, kind=kind, min_prior=value).labels
                for value in PRIOR_SWEEP
            }
            for kind in BLOCK_TYPES
        },
        daily=block_volume_stats(daily_blocks, kind="day"),
        daily_blocks=len(daily_blocks),
    )


def _volume_section(item: CorpusMeasurement) -> str:
    rows = [
        "| Block | Blocks | Labels | Base rate `>` | Base rate `>=` | Ties | "
        "Median was 0 | Qualifying topics | Rejected sparse | Base rate, shares | "
        "Volume trend |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for kind, stats in [
        *((kind, item.volume[kind]) for kind in BLOCK_TYPES),
        ("**day**", item.daily),
    ]:
        rows.append(
            f"| {kind} | {stats.blocks} | {stats.labels} | "
            f"{_pct(stats.base_rate_strict)} | {_pct(stats.base_rate_inclusive)} | "
            f"{_pct(stats.tie_rate)} | {_pct(stats.zero_median_rate)} | "
            f"{stats.qualifying_topics} | {stats.rejected_sparse} | "
            f"{_pct(stats.base_rate_share_strict)} | "
            f"{_pct(stats.volume_trend, '.2f')}× |"
        )
    return "\n".join(rows)


def _candidate_section(item: CorpusMeasurement) -> str:
    rows = [
        "| Candidate | Block | Labels | Base rate | Note |",
        "|---|---|---:|---:|---|",
    ]
    for kind in BLOCK_TYPES:
        novelty = item.novelty[kind]
        rows.append(
            f"| novelty | {kind} | {novelty.labels} | {_pct(novelty.base_rate)} | "
            f"{_pct(novelty.mean_new_domains, '.1f')} new domains per block |"
        )
    for kind in BLOCK_TYPES:
        dormant = item.dormancy[kind]
        rows.append(
            f"| dormancy | {kind} | {dormant.labels} | {_pct(dormant.return_rate)} | "
            f"{dormant.topics} topics, absent 2 blocks |"
        )
    nxt = item.next_category
    rows.append(
        f"| next_session_category | session | {nxt.transitions} | "
        f"{_pct(nxt.majority_successor_rate)} | always-the-mode floor; "
        f"per-category mode {_pct(nxt.per_category_mode_rate)}, "
        f"{nxt.categories} categories |"
    )
    return "\n".join(rows)


def _prior_section(item: CorpusMeasurement) -> str:
    header = " | ".join(f"`min_prior={value}`" for value in PRIOR_SWEEP)
    rows = [
        f"| Block | {header} |",
        "|---|" + "---:|" * len(PRIOR_SWEEP),
    ]
    for kind in BLOCK_TYPES:
        counts = item.prior_sweep[kind]
        cells = " | ".join(str(counts[value]) for value in PRIOR_SWEEP)
        rows.append(f"| {kind} | {cells} |")
    return "\n".join(rows)


def _cluster_section(item: CorpusMeasurement) -> str:
    stats = item.clusters
    sweep = " · ".join(
        f"{value:.1f} → {count}" for value, count in sorted(item.sweep.items())
    )
    return "\n".join(
        [
            f"`unknown` holds **{stats.unknown_events:,} events** across "
            f"**{stats.unknown_domains}** domains, of which {stats.clusterable_domains} "
            f"appear in enough sessions to cluster at all.",
            "",
            "| Clusters | Domains clustered | Largest | `unknown` events named | "
            "Half-to-half agreement |",
            "|---:|---:|---:|---:|---:|",
            f"| {stats.clusters} | {stats.clustered_domains} | {stats.largest_cluster} | "
            f"{_pct(stats.events_covered)} | {_pct(stats.half_agreement)} |",
            "",
            f"Clusters found at each similarity threshold: {sweep}. "
            f"The declared value is **{DEFAULT_THRESHOLD}**; the sweep is sensitivity, "
            "not a search, and nothing here is selected by it.",
        ]
    )


def _corpus_section(item: CorpusMeasurement) -> str:
    return f"""### {item.name}

{item.events:,} events. Complete blocks: {item.blocks['weekday']} weekday,
{item.blocks['weekend']} weekend (the first and last of each type are dropped as partial).

**`block_volume`** — trailing window {DEFAULT_TRAILING_BLOCKS} blocks, minimum
{DEFAULT_MIN_PRIOR_BLOCKS} prior blocks before a topic is predictable:

{_volume_section(item)}

**The other three candidates:**

{_candidate_section(item)}

**Label yield against the minimum-history rule** — sensitivity only. D88 declared
{DEFAULT_MIN_PRIOR_BLOCKS}; with this few blocks that rule may be the binding constraint
rather than the data, and this makes which one it is visible:

{_prior_section(item)}

**Splitting `unknown`:**

{_cluster_section(item)}
"""


def write_report(
    items: list[CorpusMeasurement], *, out_dir: Path, tz_name: str
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "candidate-targets.md"

    path.write_text(
        f"""# Candidate targets — what the data can support

Generated by `analysis/candidate_targets.py`. **Do not edit by hand.** Regenerate with:

```
uv run python analysis/candidate_targets.py
```

Session timeout {TIMEOUT_SECONDS:,.0f}s (D17). Blocks are local weeks in **{tz_name}** —
a block boundary is a fact about someone's week, so UTC would put Friday evening in the
wrong place. Corpora measured **separately and never merged** (D18).

## What this is, and what it deliberately is not

D88 retired `return_24h` on an argument and recorded that **nothing about the replacement
had been measured**. This is that measurement.

**No model is fitted and nothing is scored here.** That restriction is what allows the
data-sufficiency gate to be set from this page without the circularity D81 exists to
prevent — there is no performance number a bar could be fitted to. The performance bar is
pre-registered separately in T20, before any model exists.

This can kill `block_volume`. If the labels are too few, or the base rate collapses to
something a constant already predicts, one of the other candidates takes its place.

## How to read the `block_volume` table

**The tie columns are the point.** D88 claims a median split is 50/50 by construction, and
that is true of a continuous quantity. These are integer event counts over a handful of
blocks, so a count landing exactly on the median is common and `>` loses every tie. Both
rules are reported with the tie rate beside them; the truth is between them and T20 picks
with the number in front of it.

**"Median was 0"** is D88's recorded flaw made visible: where the trailing median is zero,
"above the median" is just "did it appear", and the 50/50 property does not hold for those
labels however the ties are broken.

**"Base rate, shares"** is the same target computed on each topic's share of the block
rather than its raw count. A share cancels a uniform import-versus-live offset — which has
never been measured — and normalises for how much browsing happened that week.

## Results

{chr(10).join(_corpus_section(item) for item in items)}

## Limitations

- **One person's browsing**, across three browsers measured separately, as everywhere in
  `docs/benchmarks/`. Between-browser variation here is a lower bound on between-person.
- **Blocks come from imported history**, which is reconstructed through the redirect
  heuristic rather than observed. D88 records that the import-versus-live offset has never
  been measured; a systematic difference would shift counts, though a median split is far
  less sensitive to it than an absolute threshold would be.
- **The first and last block of each type are dropped** as partial. A half-length block has
  a systematically lower count than a whole one, and left in it would drag the median down
  in a way that looks exactly like a behaviour change.
- **Nothing here is a score.** No model has been fitted to any of these targets, so none of
  these base rates says whether a model could beat them.
""",
        encoding="utf-8",
    )
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "docs" / "benchmarks")
    parser.add_argument(
        "--view", default=DEFAULT_VIEW, choices=["shipped", "chosen", "raw"]
    )
    args = parser.parse_args()

    copies = (
        [args.corpus]
        if args.corpus
        else sorted((REPO_ROOT / "data").glob("history-*.copy"))
    )
    if not copies:
        print("No corpus found in data/.")
        return 1

    tz = datetime.now().astimezone().tzinfo
    assert tz is not None
    tz_name = datetime.now().astimezone().strftime("%Z") or str(tz)

    items: list[CorpusMeasurement] = []
    for copy_path in copies:
        item = measure(copy_path, tz=tz, view=args.view)
        items.append(item)
        weekend = item.volume["weekend"]
        print(
            f"{item.name}: {item.blocks['weekday']}+{item.blocks['weekend']} blocks, "
            f"weekend labels {weekend.labels} at {_pct(weekend.base_rate_strict)} "
            f"(ties {_pct(weekend.tie_rate)})"
        )

    path = write_report(items, out_dir=args.out, tz_name=tz_name)
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
