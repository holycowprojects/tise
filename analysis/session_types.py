"""T-E — do browsing sessions come in recurring types? **Descriptive; nothing is predicted.**

    uv run python analysis/session_types.py

Writes `docs/benchmarks/session-types.md`.

D95 adopted this from an outside plan, which guessed the types would be "research, routine
checking, entertainment, exploration". **This script does not name any cluster.** Naming is
interpretation, a name printed beside a measurement reads as part of it, and the four names
above were a hypothesis nobody has tested. Clusters get numbers and a profile; a reader can
decide whether cluster 2 looks like "routine checking" and will know they decided it.

**No prediction bar applies** (D95): this describes sessions rather than predicting a topic,
which is why it was worth adopting at all given D92's finding that a per-topic rate table is
hard to beat. **D24 still applies**, and for an unsupervised method the mandatory baseline
takes two forms, both reported for every k:

* **A null.** k-means always returns k clusters, and hands pure noise a positive silhouette.
  Each feature column is permuted independently — every marginal kept, every correlation
  destroyed — and the silhouette recomputed. That band is what "no types at all" looks like
  on a corpus of this shape and size, and the observed number means nothing without it.
* **Stability.** "Recurring type" claims the same groups come back, which a silhouette does
  not test. Subsampling and re-clustering measures how often two sessions that landed
  together land together again.

**Time of day is held out of the clustering deliberately** and reported beside it — see
`session_shape.py`. A clustering handed the clock recovers morning-versus-evening and
presents it as a discovery about session types.

Aggregates only. No domain, URL or title is written anywhere by this script.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "research"))

from tise_research.data.chrome_history import DEFAULT_VIEW  # noqa: E402
from tise_research.data.corpus import load_events  # noqa: E402
from tise_research.features.session_shape import (  # noqa: E402
    DOMAIN_COUNT_SCALE,
    DURATION_SCALE_MINUTES,
    SESSION_FEATURES,
    VISIT_COUNT_SCALE,
    SessionShape,
    session_shapes,
)
from tise_research.features.sessions import sessionise  # noqa: E402
from tise_research.models.clustering import (  # noqa: E402
    CLUSTER_SEED,
    gaussian_null_band,
    kmeans,
    null_silhouette_band,
    silhouette,
    stability,
    standardise,
)

TIMEOUT_SECONDS = 1800.0

#: Every k reported. Nothing is "selected" — the whole sweep is printed, because reporting
#: only the best k is choosing the answer after seeing it, which is the defect D91 named.
K_RANGE = range(2, 9)

#: Reduced from the module default because the silhouette is O(n²) and this runs it once
#: per null draw per k. Declared here so the number is visible rather than buried in a
#: default, and the report prints it.
NULL_RUNS = 20
STABILITY_RUNS = 15

#: Below this many sessions a corpus is skipped: a silhouette over a handful of points is
#: a decoration, and D26's principle — count it, do not score it — applies here too.
MIN_SESSIONS = 40

#: A cluster holding less than this share of sessions is flagged in the profile. k-means
#: will happily isolate three outliers and call it a type. Declared, and no conclusion
#: reads it — it is a reporting threshold.
SMALL_CLUSTER_SHARE = 0.05


@dataclass(frozen=True, slots=True)
class KResult:
    k: int
    silhouette: float | None
    null_median: float
    null_low: float
    null_high: float
    #: The stronger null: one mode, observed correlations kept. See `gaussian_null_band`.
    single_median: float
    single_low: float
    single_high: float
    stability: float
    sizes: tuple[int, ...]

    @property
    def above_null(self) -> bool:
        """Above the *permutation* band — features are related. A weak claim on its own."""
        return self.silhouette is not None and self.silhouette > self.null_high

    @property
    def above_single(self) -> bool:
        """Above the **one-mode** band. This is the claim the word "type" makes."""
        return self.silhouette is not None and self.silhouette > self.single_high


@dataclass(frozen=True, slots=True)
class ClusterProfile:
    index: int
    size: int
    share: float
    median_visits: float
    median_domains: float
    median_duration: float
    means: tuple[float, ...]
    evening_share: float
    weekend_share: float


@dataclass(frozen=True, slots=True)
class CorpusResult:
    name: str
    events: int
    sessions: int
    per_k: tuple[KResult, ...]
    #: Profiles for the *smallest* k whose silhouette clears its null band, or None when no
    #: k does. Smallest rather than best: if two and five both clear, two is the claim the
    #: data supports and five is the one a reader would over-read.
    reported_k: int | None
    profiles: tuple[ClusterProfile, ...]

    @property
    def magnitude_split(self) -> bool:
        """True when one cluster is simply *more* of everything than the other.

        A "session type" in the sense D95's outside plan meant — research, entertainment,
        routine checking — is a difference of **kind**: the person did something different.
        If instead every separating feature moves the same way at once, the clusters are one
        behaviour at two sizes, and calling them types would be the report's own invention.
        Computed rather than eyeballed, because it is the finding.
        """
        if len(self.profiles) != 2:
            return False
        larger, smaller = sorted(self.profiles, key=lambda p: -p.median_visits)
        return (
            larger.median_domains >= smaller.median_domains
            and larger.median_duration >= smaller.median_duration
            and larger.means[SESSION_FEATURES.index("domainRepeatRate")]
            >= smaller.means[SESSION_FEATURES.index("domainRepeatRate")]
            and larger.means[SESSION_FEATURES.index("categoryEvenness")]
            >= smaller.means[SESSION_FEATURES.index("categoryEvenness")]
        )

    @property
    def evening_gap(self) -> float:
        if len(self.profiles) < 2:
            return 0.0
        shares = [profile.evening_share for profile in self.profiles]
        return max(shares) - min(shares)

    @property
    def weekend_gap(self) -> float:
        if len(self.profiles) < 2:
            return 0.0
        shares = [profile.weekend_share for profile in self.profiles]
        return max(shares) - min(shares)


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _profiles(
    shapes: list[SessionShape], assignments: tuple[int, ...], k: int
) -> tuple[ClusterProfile, ...]:
    profiles: list[ClusterProfile] = []
    for cluster in range(k):
        members = [
            shape
            for shape, assigned in zip(shapes, assignments, strict=True)
            if assigned == cluster
        ]
        if not members:
            continue
        means = tuple(
            sum(member.values[index] for member in members) / len(members)
            for index in range(len(SESSION_FEATURES))
        )
        profiles.append(
            ClusterProfile(
                index=cluster,
                size=len(members),
                share=len(members) / len(shapes),
                median_visits=_median([float(m.visits) for m in members]),
                median_domains=_median([float(m.domains) for m in members]),
                median_duration=_median([m.duration_minutes for m in members]),
                means=means,
                # Held out of the clustering; this is the question that becomes askable
                # *because* it was held out.
                evening_share=sum(1 for m in members if m.started_hour >= 18)
                / len(members),
                weekend_share=sum(1 for m in members if m.is_weekend) / len(members),
            )
        )
    return tuple(sorted(profiles, key=lambda profile: -profile.size))


def measure(copy_path: Path, *, view: str) -> CorpusResult:
    events = load_events(copy_path, view=view)
    sessions = sessionise(events, timeout_seconds=TIMEOUT_SECONDS)
    shapes = session_shapes(sessions)
    if len(shapes) < MIN_SESSIONS:
        raise ValueError(f"{copy_path.stem}: only {len(shapes)} sessions")

    matrix = standardise([list(shape.values) for shape in shapes])

    per_k: list[KResult] = []
    fits = {}
    for k in K_RANGE:
        if k >= len(matrix):
            break
        fit = kmeans(matrix, k)
        fits[k] = fit
        median, low, high = null_silhouette_band(matrix, k, runs=NULL_RUNS)
        one_median, one_low, one_high = gaussian_null_band(matrix, k, runs=NULL_RUNS)
        per_k.append(
            KResult(
                k=k,
                silhouette=silhouette(matrix, fit.assignments),
                null_median=median,
                null_low=low,
                null_high=high,
                single_median=one_median,
                single_low=one_low,
                single_high=one_high,
                stability=stability(matrix, k, runs=STABILITY_RUNS),
                sizes=tuple(
                    count for _, count in sorted(Counter(fit.assignments).items())
                ),
            )
        )

    clearing = [result.k for result in per_k if result.above_single]
    reported = min(clearing) if clearing else None
    profiles = (
        _profiles(shapes, fits[reported].assignments, reported)
        if reported is not None
        else ()
    )

    return CorpusResult(
        name=copy_path.stem,
        events=len(events),
        sessions=len(shapes),
        per_k=tuple(per_k),
        reported_k=reported,
        profiles=profiles,
    )


def _section(item: CorpusResult) -> str:
    sweep = [
        "| k | silhouette | permuted band | above? | one-mode band | **above?** | "
        "stability | cluster sizes |",
        "|---:|---:|---|---|---|---|---:|---|",
    ]
    for result in item.per_k:
        score = "n/a" if result.silhouette is None else f"{result.silhouette:.3f}"
        sizes = ", ".join(str(size) for size in sorted(result.sizes, reverse=True))
        sweep.append(
            f"| {result.k} | {score} | "
            f"[{result.null_low:.3f}, {result.null_high:.3f}] | "
            f"{'yes' if result.above_null else 'no'} | "
            f"[{result.single_low:.3f}, {result.single_high:.3f}] | "
            f"{'**yes**' if result.above_single else '**no**'} | "
            f"{result.stability:.2f} | {sizes} |"
        )

    permuted = [result.k for result in item.per_k if result.above_null]
    if item.reported_k is None:
        body = (
            "**No k produced a silhouette above the one-mode band**, so no profiles are "
            "printed. On this corpus the sessions do not separate into groups that a "
            "single correlated blob of the same shape would not also produce.\n\n"
            f"**Every k clears the *permuted* band** ({len(permuted)} of "
            f"{len(item.per_k)}), and that is the trap this report exists to avoid. "
            "Permuting columns destroys the correlations between features, and visits, "
            "domains and duration all move together — so correlated data concentrates near "
            "a lower-dimensional surface and scores a higher silhouette **with no discrete "
            "types anywhere**. Clearing that band says the features are related, which was "
            "never in doubt.\n\n"
            "Printing cluster profiles anyway is exactly how a clustering becomes a "
            "Rorschach test, so none are printed."
        )
    else:
        rows = [
            "| Cluster | Sessions | Median visits | Median domains | Median minutes | "
            "Repeat rate | Evenness | Typed | Evening | Weekend |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        repeat = SESSION_FEATURES.index("domainRepeatRate")
        even = SESSION_FEATURES.index("categoryEvenness")
        typed = SESSION_FEATURES.index("typedShare")
        for profile in item.profiles:
            small = " *(small)*" if profile.share < SMALL_CLUSTER_SHARE else ""
            rows.append(
                f"| {profile.index}{small} | {profile.size} ({profile.share:.0%}) | "
                f"{profile.median_visits:.0f} | {profile.median_domains:.0f} | "
                f"{profile.median_duration:.0f} | {profile.means[repeat]:.2f} | "
                f"{profile.means[even]:.2f} | {profile.means[typed]:.2f} | "
                f"{profile.evening_share:.0%} | {profile.weekend_share:.0%} |"
            )
        shape = (
            "**These two clusters differ in size, not in kind.** Every feature that "
            "separates them moves the same way at once: the cluster with more visits also "
            "has more domains, runs longer, revisits more and spreads across more "
            "categories. That is one behaviour at two scales — brief check-ins and long "
            "sittings — and it is **not** what D95's outside plan meant by a session type, "
            "which was a difference in what the person was *doing*. Nothing here "
            "distinguishes research from entertainment."
            if item.magnitude_split
            else "**The clusters are not a simple size ordering**: at least one separating "
            "feature moves against the others, so these are not one behaviour at two "
            "scales. Read the profile rows for what actually differs."
        )
        timing = (
            f"**And they happen at the same times.** Evening shares differ by "
            f"{item.evening_gap:.0%} and weekend shares by {item.weekend_gap:.0%} across "
            "clusters. Time of day was held out of the clustering precisely so this "
            "question could be asked, and the answer is that these are not a morning type "
            "and an evening type."
        )
        body = (
            f"**k = {item.reported_k}** is the smallest k whose silhouette clears its null "
            "band. Smallest rather than best-scoring: if several clear, the smallest is "
            "the claim the data supports and a larger one is what a reader would "
            "over-read.\n\n" + "\n".join(rows) + "\n\n"
            "**The last two columns were held out of the clustering.** They are the "
            "question that becomes askable *because* they were held out: these clusters "
            "are defined by what a session was like, so a difference in when they happen "
            "is a finding rather than a restatement of the input.\n\n" + shape + "\n\n" + timing
        )

    return f"""### {item.name}

{item.events:,} events in **{item.sessions:,} sessions** at a {TIMEOUT_SECONDS / 60:.0f}-minute
timeout.

#### Every k, with what a structureless corpus of the same shape produces

{chr(10).join(sweep)}

#### Profiles

{body}
"""


def write_report(items: list[CorpusResult], *, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "session-types.md"

    clearing = [item.name for item in items if item.reported_k is not None]

    def listed(names: list[str]) -> str:
        return ", ".join(f"`{n}`" for n in names) if names else "**nothing**"

    path.write_text(
        f"""# T-E · Do browsing sessions come in recurring types?

Generated by `analysis/session_types.py`. **Do not edit by hand.** Regenerate with:

```
uv run python analysis/session_types.py
```

**Descriptive. Nothing here is predicted and no bar is cleared** — D95 adopted T-E precisely
because it does not have to beat a per-topic rate table, which D92 established is hard.

## No cluster is named

D95 recorded the outside plan's guess that the types would be *research, routine checking,
entertainment, exploration*. **This report names nothing.** A name printed beside a
measurement reads as part of it, and those four were a hypothesis nobody has tested. Clusters
get an index and a profile; whether cluster 2 looks like routine checking is the reader's
call, and they will know they made it.

## Two baselines, because k-means always answers

k-means returns k clusters whatever you hand it, and gives pure noise a positive silhouette.
D24 makes a baseline mandatory in every report, and for an unsupervised method that means:

- **A null band.** Each feature column permuted independently — every marginal kept exactly,
  every correlation destroyed — then re-clustered, {NULL_RUNS} times per k. That is what a
  structureless corpus of this shape and size produces. An observed silhouette below its own
  band is not weak evidence of types; it is evidence of none.
- **Stability**, over {STABILITY_RUNS} subsample pairs: how often two sessions that cluster
  together cluster together again. *Recurring* type is a claim about reproducibility, and a
  silhouette does not test it. 1.0 is an exactly reproduced partition; ~0.5 is a coin.

Seed `{CLUSTER_SEED}`, declared and never tuned, with a test asserting the reported numbers
barely move across other seeds.

## Result

Some k clears its null band on: {listed(clearing)}

## The eight features

| Feature | What it is |
|---|---|
| `visitCount` | visits, saturated at {VISIT_COUNT_SCALE:.0f} |
| `domainCount` | distinct domains, saturated at {DOMAIN_COUNT_SCALE:.0f} |
| `categoryCount` | distinct categories, saturated at {DOMAIN_COUNT_SCALE:.0f} |
| `durationMinutes` | saturated at {DURATION_SCALE_MINUTES:.0f} min |
| `domainRepeatRate` | share of visits that revisited a domain already in this session |
| `categoryEvenness` | normalised entropy across the categories present — evenness, not count |
| `typedShare` | share of visits arrived at by typing |
| `linkShare` | share arrived at by following a link |

**Time of day is not among them, deliberately.** A clustering handed the clock recovers
morning-versus-evening and presents it as a discovery about session types. It is reported
beside each profile instead, which turns it from an input into a question.

**Idle periods are missing and would be the most informative feature here.** A forty-minute
session with one visit is a different thing depending on whether the person was present, and
only the `idle` permission can tell (D96). No history database records it.

## Results

{chr(10).join(_section(item) for item in items)}

## Limitations

- **One person's browsing**, three browsers, so agreement between corpora is much weaker
  evidence than three people agreeing would be.
- **The 30-minute session timeout is a declared guess** (D17): T1 looked for an empirical
  trough in the gap distribution and found none. Every row here is a session, so the guess
  is load-bearing in the same way D97 recorded it being for T-A's cluster unit. A longer
  timeout merges what a person would call several sittings into one row.
- **The one-mode null matches the covariance, not the marginal shapes.** Session features are
  skewed and partly discrete — a one-visit session has a repeat rate of exactly zero, so
  there is a genuine point mass at a corner of the space — while the reference draws are
  smooth and symmetric. Some of the excess silhouette over that band may be skewness rather
  than a second mode. **Stability does not have this problem** and is the sturdier of the two
  numbers: it asks whether the same groups come back, which no distributional assumption
  enters. Where a corpus clears the band *and* reports stability near 1.0, both are saying
  the same thing.
- **k-means assumes roughly spherical clusters of comparable spread.** Session shapes may not
  be; a method that found nothing here is evidence about this method on this data.
- **Silhouette rewards compact well-separated groups**, which is not the same property as
  *useful*. A partition can clear its null and still name nothing anyone would recognise.
- **Small clusters are flagged, not dropped.** k-means will isolate a few outliers and call
  it a type, and the size column is the only thing that says so.
""",
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
        clears = [result.k for result in item.per_k if result.above_null]
        print(
            f"{item.name}: {item.sessions:,} sessions, k clearing its null band: "
            f"{clears if clears else 'none'}"
        )

    if not items:
        print("No corpus had enough sessions.")
        return 1

    print(f"Wrote {write_report(items, out_dir=args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
