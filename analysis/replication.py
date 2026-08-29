"""D99 — does `visit_engaged` replicate on 2,148 other people?

    uv run python analysis/replication.py

Writes `data/replication.md` — **not** `docs/benchmarks/`. The corpus is CC BY-NC and the
report location is a licence decision, so it stays out of the public tree until the
permission recorded in `docs/gesis-permission-request.md` is filed there.

**Everything scored here was fixed in D99 before a line of this file was written**: the
corpus, the eligibility gate, the feature sets, the bar, the statistic, the resampling unit,
the verdict rule and seven predictions. This module executes that and decides nothing.

**The unit is the person.** One analysis per panelist, never pooled (D18). One Brier
difference each, then a bootstrap **across panelists** — which is the D94 insight arriving
where it belongs: intervals in this project were built from 9-12 categories, then from 27
and 155 sessions, and this one is built from over a thousand people.

Aggregates only. No domain, URL, or per-panelist record is written anywhere by this script.
"""

from __future__ import annotations

import argparse
import random
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "research"))

from tise_research.data.web_tracking import (  # noqa: E402
    iter_panelists,
    load_category_map,
    load_demographics,
)
from tise_research.eval.backtest import run_backtest  # noqa: E402
from tise_research.eval.intervals import (  # noqa: E402
    BOOTSTRAP_SEED,
    DEFAULT_LEVEL,
    DEFAULT_RESAMPLES,
    Interval,
    brier_difference,
)
from tise_research.features.attention import attention_examples  # noqa: E402
from tise_research.features.labels import Label  # noqa: E402
from tise_research.features.vector import FeatureRow  # noqa: E402
from tise_research.models.baselines import Baseline, fit_per_key  # noqa: E402
from tise_research.models.fast_logreg import train_fast  # noqa: E402
from tise_research.models.logreg import DEFAULT_SPEC, predict_proba  # noqa: E402
from tise_research.models.prep import design_columns, fit_preprocessor  # noqa: E402

# --- everything below this line is quoted from D99, not chosen here -------------------

TIMEOUT_SECONDS = 1800.0
N_FOLDS = 5

INCUMBENT_SET = "as_1n"
CHALLENGER_SET = "as_2n"
INCUMBENT = "logreg_as1n"
CHALLENGER = "logreg_as2n"
BAR_MODEL = "global_base_rate"
DOMAIN_BAR = "domain_base_rate"
BASELINE_SMOOTHING = 5.0

#: D99's eligibility gate. Declared on quantities that carry no score information.
MIN_VISITS = 1_000
MIN_SESSIONS = 20
MIN_LABELS = 200

#: D99: if runtime forces a subsample, a seeded draw taken before any score is computed.
SUBSAMPLE_SEED = BOOTSTRAP_SEED

# -------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Model(Baseline):
    name: str
    feature_set: str
    preprocessor: object
    state: object
    rows: dict[str, FeatureRow]

    def predict(self, label: Label) -> float:
        row = self.rows[label.label_id]
        return predict_proba(self.state, self.preprocessor.transform(row))  # type: ignore[attr-defined]


def _fitter(name: str, feature_set: str, rows: dict[str, FeatureRow]):
    def fit(labels):
        window = [rows[label.label_id] for label in labels]
        preprocessor = fit_preprocessor(window)
        # The vectorised trainer, proven equal to the shipped one to 4e-16 on real
        # rows by `test_fast_logreg.py` — seven orders inside the 1e-9 parity
        # tolerance. Without it this run is hundreds of hours; with it the published
        # number is still the shipped optimiser's, because it is the same function.
        state = train_fast(
            preprocessor.matrix(window),
            [label.outcome for label in labels],
            spec=DEFAULT_SPEC,
            n_columns=len(design_columns(feature_set)),
        )
        return _Model(name, feature_set, preprocessor, state, rows)

    return fit


def _domain_rate_fitter(domains: dict[str, str]):
    def fit(labels):
        return fit_per_key(
            labels,
            name=DOMAIN_BAR,
            key=lambda label: domains[label.label_id],
            smoothing=BASELINE_SMOOTHING,
        )

    return fit


@dataclass(frozen=True, slots=True)
class PanelistResult:
    """One person. The per-panelist Brier differences are the population sample."""

    panelist: str
    gender: str
    age_band: str
    visits: int
    sessions: int
    labels: int
    test_rows: int
    base_rate: float
    #: bar - challenger. Positive favours the model, as everywhere in this project.
    vs_bar: float
    vs_incumbent: float
    vs_domain: float
    domain_vs_bar: float


@dataclass(frozen=True, slots=True)
class Excluded:
    panelist: str
    visits: int
    sessions: int
    labels: int
    reason: str


def measure_panelist(
    panelist: str,
    events,
    *,
    gender: str,
    age_band: str,
) -> PanelistResult | Excluded:
    """One panelist end to end, or the reason they were excluded.

    Exclusions are returned rather than skipped: D26's rule applied to people. A gate that
    silently drops the people it does not like is not a gate.
    """
    visits = len(events)
    if visits < MIN_VISITS:
        return Excluded(panelist, visits, 0, 0, "visits")

    from tise_research.features.sessions import sessionise

    sessions = len(sessionise(events, timeout_seconds=TIMEOUT_SECONDS))
    if sessions < MIN_SESSIONS:
        return Excluded(panelist, visits, sessions, 0, "sessions")

    both = {
        name: attention_examples(
            events, timeout_seconds=TIMEOUT_SECONDS, feature_set=name
        )
        for name in (INCUMBENT_SET, CHALLENGER_SET)
    }
    challenger = both[CHALLENGER_SET]
    if len(challenger) < MIN_LABELS:
        return Excluded(panelist, visits, sessions, len(challenger), "labels")

    # D99 inherits D94's identical-label claim; checked, never assumed.
    if [item.label for item in both[INCUMBENT_SET]] != [
        item.label for item in challenger
    ]:
        raise AssertionError(f"{panelist}: feature sets produced different labels")

    rows = {
        name: {
            item.label.label_id: item.row for item in examples
        }
        for name, examples in both.items()
    }
    domains = {
        item.label.label_id: item.domain for item in challenger
    }
    labels = [item.label for item in challenger]

    result = run_backtest(
        labels,
        n_folds=N_FOLDS,
        extra_models={
            INCUMBENT: _fitter(INCUMBENT, INCUMBENT_SET, rows[INCUMBENT_SET]),
            CHALLENGER: _fitter(CHALLENGER, CHALLENGER_SET, rows[CHALLENGER_SET]),
            DOMAIN_BAR: _domain_rate_fitter(domains),
        },
    )

    outcomes = result.pooled_outcomes
    if not outcomes:
        return Excluded(panelist, visits, sessions, len(labels), "no test rows")

    model = result.pooled_probabilities[CHALLENGER]
    bar = result.pooled_probabilities[BAR_MODEL]
    return PanelistResult(
        panelist=panelist,
        gender=gender,
        age_band=age_band,
        visits=visits,
        sessions=sessions,
        labels=len(labels),
        test_rows=len(outcomes),
        base_rate=result.overall_base_rate or 0.0,
        vs_bar=brier_difference(outcomes, model, bar) or 0.0,
        vs_incumbent=brier_difference(
            outcomes, model, result.pooled_probabilities[INCUMBENT]
        )
        or 0.0,
        vs_domain=brier_difference(
            outcomes, model, result.pooled_probabilities[DOMAIN_BAR]
        )
        or 0.0,
        domain_vs_bar=brier_difference(
            outcomes, result.pooled_probabilities[DOMAIN_BAR], bar
        )
        or 0.0,
    )


def population_interval(
    values: list[float],
    *,
    resamples: int = DEFAULT_RESAMPLES,
    level: float = DEFAULT_LEVEL,
    seed: int = BOOTSTRAP_SEED,
) -> Interval | None:
    """Bootstrap the mean over **panelists**. The cluster is the person (D99).

    Each panelist already contributes one number, so this resamples people directly rather
    than rows within people — the within-person structure is summarised, not assumed away.
    """
    if not values:
        return None
    rng = random.Random(seed)
    count = len(values)
    draws = [
        sum(values[rng.randrange(count)] for _ in range(count)) / count
        for _ in range(resamples)
    ]
    draws.sort()
    tail = (1.0 - level) / 2.0

    def percentile(fraction: float) -> float:
        if count == 1:
            return draws[0]
        position = fraction * (len(draws) - 1)
        lower, upper = int(position), min(int(position) + 1, len(draws) - 1)
        weight = position - lower
        return draws[lower] * (1.0 - weight) + draws[upper] * weight

    return Interval(
        point=statistics.fmean(values),
        low=percentile(tail),
        high=percentile(1.0 - tail),
        level=level,
        resamples=resamples,
        unit="panelist",
        units=count,
    )


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    """Rank correlation. Ranks, not values: visit counts run 1,000 to 85,000 and a handful
    of very heavy browsers would otherwise decide the number on their own."""
    if len(xs) < 3:
        return None

    def rank(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        ranks = [0.0] * len(values)
        index = 0
        while index < len(order):
            stop = index
            while stop + 1 < len(order) and values[order[stop + 1]] == values[order[index]]:
                stop += 1
            shared = (index + stop) / 2.0 + 1.0
            for position in range(index, stop + 1):
                ranks[order[position]] = shared
            index = stop + 1
        return ranks

    rx, ry = rank(xs), rank(ys)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return None if dx == 0 or dy == 0 else num / (dx * dy)


def _share_positive(values: list[float]) -> float:
    return sum(1 for value in values if value > 0.0) / len(values) if values else 0.0


def _group_table(results: list[PanelistResult], key) -> str:
    groups: dict[str, list[float]] = {}
    for item in results:
        groups.setdefault(key(item) or "(not given)", []).append(item.vs_bar)
    lines = ["| Group | Panelists | Mean vs the bar | Share positive |", "|---|---:|---:|---:|"]
    for name, values in sorted(groups.items()):
        lines.append(
            f"| {name} | {len(values):,} | {statistics.fmean(values):+.4f} | "
            f"{_share_positive(values):.1%} |"
        )
    return "\n".join(lines)


def _predictions_table(
    results: list[PanelistResult], interval: Interval | None, rho: float | None
) -> str:
    vs_bar = [item.vs_bar for item in results]
    vs_inc = [item.vs_incumbent for item in results]
    vs_dom = [item.vs_domain for item in results]
    dom_bar = [item.domain_vs_bar for item in results]
    share = _share_positive(vs_bar)
    median = statistics.median(vs_bar) if vs_bar else 0.0

    by_gender: dict[str, list[float]] = {}
    for item in results:
        if item.gender:
            by_gender.setdefault(item.gender, []).append(item.vs_bar)
    gap = (
        abs(
            statistics.fmean(by_gender["male"]) - statistics.fmean(by_gender["female"])
        )
        if {"male", "female"} <= set(by_gender)
        else None
    )

    checks = [
        (
            "1. Population interval excludes zero, model's favour",
            interval is not None and interval.excludes_zero and interval.point > 0,
            "not computable" if interval is None else interval.describe(),
        ),
        (
            "2. Median per-panelist difference positive but < +0.0112",
            0.0 < median < 0.0112,
            f"median {median:+.4f}",
        ),
        (
            "3. Share of panelists positive lands in 55-80%",
            0.55 <= share <= 0.80,
            f"{share:.1%}",
        ),
        (
            "4. `as_2n` beats `as_1n` on a majority",
            _share_positive(vs_inc) > 0.5,
            f"{_share_positive(vs_inc):.1%} of panelists",
        ),
        (
            "5. Domain rate table beats the constant on most",
            _share_positive(dom_bar) > 0.5,
            f"{_share_positive(dom_bar):.1%} of panelists",
        ),
        (
            "6. Difference correlates positively with visit count",
            rho is not None and rho > 0.0,
            "not computable" if rho is None else f"Spearman rho = {rho:+.3f}",
        ),
        (
            "7. No meaningful difference by gender",
            gap is not None and gap < 0.0050,
            "not computable" if gap is None else f"|male - female| = {gap:.4f}",
        ),
    ]
    lines = ["| D99 prediction | Held? | Measured |", "|---|:--|---|"]
    for text, held, measured in checks:
        lines.append(f"| {text} | {'**yes**' if held else '**NO**'} | {measured} |")
    lines.append("")
    lines.append(f"**{sum(1 for _, held, _ in checks if held)} of 7 held.**")
    lines.append("")
    lines.append(
        f"`as_2n` vs the domain table: mean {statistics.fmean(vs_dom):+.4f}, "
        f"{_share_positive(vs_dom):.1%} of panelists positive."
    )
    return "\n".join(lines)


def write_report(
    results: list[PanelistResult],
    excluded: list[Excluded],
    *,
    out_path: Path,
    dropped_rows: int,
) -> Path:
    vs_bar = [item.vs_bar for item in results]
    interval = population_interval(vs_bar)
    rho = _spearman([float(item.visits) for item in results], vs_bar)

    reasons: dict[str, int] = {}
    for item in excluded:
        reasons[item.reason] = reasons.get(item.reason, 0) + 1
    funnel = "\n".join(
        f"| excluded — {reason} | {count:,} |" for reason, count in sorted(reasons.items())
    )

    if interval is None:
        verdict = "**Undecided** — no panelist was analysable."
    elif interval.excludes_zero and interval.point > 0.0:
        verdict = (
            "## ✅ `visit_engaged` REPLICATES\n\n"
            "The mean per-panelist Brier difference against the constant, bootstrapped over "
            "**panelists**, excludes zero in the model's favour. That is the rule D99 fixed "
            "before this ran. D97's adoption stands, and it now stands on more than one "
            "person."
        )
    else:
        verdict = (
            "## ❌ `visit_engaged` DOES NOT REPLICATE\n\n"
            "The population interval includes zero. Under D99 this is not appealable: D97's "
            "adoption is withdrawn to *single-person result, did not generalise*, and "
            "`SPEC.md` and `README.md` must be corrected to say so. There is no re-run with "
            "a different gate."
        )

    dropped_note = (
        f"{dropped_rows:,} rows were unusable and dropped."
        if dropped_rows
        else "No rows were dropped."
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        f"""# D99 — does `visit_engaged` replicate on other people?

Generated by `analysis/replication.py`. **Do not edit by hand.**

Corpus: Kulshrestha, Oliveira, Karaçalık, Bonnay & Wagner (2021), *Web Routineness and
Limits of Predictability*, ICWSM — Zenodo 10.5281/zenodo.4757574, data supplied by
Respondi AG, **CC BY-NC 4.0**. 2,148 German panelists, October 2018.

**Every choice scored below was fixed in D99 before this file was written.** Aggregates
only: no domain, URL or per-panelist record appears anywhere on this page.

{verdict}

**Mean per-panelist difference vs the constant**, bootstrapped over panelists. Positive
favours the model:

{"not computable" if interval is None else interval.describe()}

**Share of panelists the model beats the constant for: {_share_positive(vs_bar):.1%}**
— D99 called this the number that actually answers the question, because a pooled interval
can exclude zero while most individuals see nothing.

## Who was analysed

| | Panelists |
|---|---:|
| in the corpus | 2,148 |
{funnel}
| **analysed** | **{len(results):,}** |

{dropped_note}

Eligibility was fixed in D99: at least {MIN_VISITS:,} visits, {MIN_SESSIONS} sessions and
{MIN_LABELS} labels. Excluded panelists are counted here rather than silently skipped —
D26's rule, applied to people.

## D99's predictions, scored

{_predictions_table(results, interval, rho)}

## By gender

{_group_table(results, lambda item: item.gender)}

## By age band

{_group_table(results, lambda item: item.age_band)}

Both breakdowns were pre-registered as **reported, never used to select**. D99 predicted no
meaningful gender difference in advance, precisely so that a difference found afterwards
could not be mistaken for a discovery.

## Limitations

- **Germany, 2018, desktop, one month, paid panel.** Not India, not the US — neither has a
  public dataset with per-visit dwell, which was checked rather than assumed.
- **Zero-dwell visits appear filtered upstream.** Not one of 9,151,243 rows has
  `active_seconds` of zero, missing or negative, which is not what a raw capture looks like.
  Short glances are probably absent and the dwell distribution is biased upward.
- **This is not the model D97 adopted.** The corpus has no transition column, so `as_1n` and
  `as_2n` drop the three arrival flags rather than fill them with a zero that was never
  measured. `arrivedLink` was not a negligible coefficient on Akash's corpora.
- **One month is short**: a category needs 10 prior visits before its first label, so slow
  categories never qualify. The exclusion counts above are part of the result.
- **`tab_return` (T-D) remains untestable** — no tab data here, as everywhere else.
""",
        encoding="utf-8",
    )
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shards", type=Path, default=REPO_ROOT / "data" / "gesis-shards")
    parser.add_argument(
        "--release", type=Path, default=REPO_ROOT / "data" / "web_routineness_release"
    )
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "replication.md")
    parser.add_argument(
        "--sample",
        type=int,
        default=0,
        help="0 = every eligible panelist (D99's primary). Any other value takes a seeded "
        "draw of that many panelists, decided before any score is computed.",
    )
    args = parser.parse_args()

    categories = load_category_map(
        args.release / "pre_processed" / "processed_domain_categories.csv"
    )
    people = load_demographics(args.release / "raw" / "users.csv")
    shards = sorted(args.shards.glob("shard-*.csv"))
    if not shards:
        print(f"no shards in {args.shards}; run tise_research.data.web_tracking first")
        return 1

    chosen: set[str] | None = None
    if args.sample:
        # Drawn from the *ids*, before any model has been fitted, so the sample cannot
        # have been chosen from the results.
        rng = random.Random(SUBSAMPLE_SEED)
        everyone = sorted(people)
        chosen = set(rng.sample(everyone, min(args.sample, len(everyone))))
        print(f"seeded subsample: {len(chosen):,} panelists (seed {SUBSAMPLE_SEED})")

    results: list[PanelistResult] = []
    excluded: list[Excluded] = []
    dropped_rows = 0

    for number, shard in enumerate(shards, start=1):
        for panelist, events, dropped in iter_panelists(shard, categories=categories):
            if chosen is not None and panelist not in chosen:
                continue
            dropped_rows += dropped
            gender, age_band = people.get(panelist, ("", ""))
            outcome = measure_panelist(
                panelist, events, gender=gender, age_band=age_band
            )
            if isinstance(outcome, Excluded):
                excluded.append(outcome)
            else:
                results.append(outcome)
        print(
            f"shard {number}/{len(shards)}: {len(results):,} analysed, "
            f"{len(excluded):,} excluded",
            flush=True,
        )

    if not results:
        print("no panelist cleared the eligibility gate")
        return 1

    path = write_report(results, excluded, out_path=args.out, dropped_rows=dropped_rows)
    values = [item.vs_bar for item in results]
    interval = population_interval(values)
    print()
    print(f"analysed {len(results):,} panelists, excluded {len(excluded):,}")
    print(f"share positive : {_share_positive(values):.1%}")
    print(f"population     : {'n/a' if interval is None else interval.describe()}")
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
