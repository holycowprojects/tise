"""The tournament (D84): what does refusing to ship XGBoost cost?

Generates `docs/benchmarks/tournament.md`. Every number here comes from this file.

**This is not a model selection.** XGBoost cannot run in a browser service worker, so the
result cannot change what ships and D84 fixed that before the first score existed. What is
being measured is the size of the gap the in-browser constraint opens, reported as an
interval rather than a point estimate — because D80 established that a point estimate on
this much data is a number with an interval around it that usually contains zero.

Two things make the comparison honest, and both are structural rather than promised:

* **Identical folds, by construction.** Every model is fitted inside one `run_backtest`
  call, on the same `Fold` objects, from one `FeatureIndex`. Running the challenger in a
  separate pass and lining the tables up afterwards would leave the fold boundaries free to
  drift, and nothing in the output would show it.
* **A paired interval, not two independent ones.** Both models score the same rows, so the
  estimand is the per-row squared-error difference. Two separate intervals that overlap say
  almost nothing about whether the difference is real; the paired one is the comparison.

The failure case at the end is chosen by `max` over squared error, not by looking for a
good story — D84 registered that, including the part about publishing the dull one if the
worst row turns out to be dull.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from tise_research.data.chrome_history import DEFAULT_VIEW
from tise_research.eval.backtest import (
    EXCLUDED_FROM_HEADLINE,
    BacktestResult,
    rolling_origin_folds,
    run_backtest,
)
from tise_research.eval.intervals import Interval, brier_difference_interval
from tise_research.features.labels import DEFAULT_HORIZON_HOURS, Label
from tise_research.features.vector import DEFAULT_FEATURE_SET, feature_names
from tise_research.models.challengers import (
    CHALLENGERS,
    XGB_SMALL,
    ChallengerSpec,
    make_challenger_fitter,
    xgboost_version,
)
from tise_research.models.prep import nullable_features
from tise_research.models.return_model import (
    MODEL_NAME,
    FeatureIndex,
    make_return_model_fitter,
    model_name,
)

__all__ = [
    "CorpusTournament",
    "FailureCase",
    "run_tournament",
    "write_tournament_report",
]

#: The corpus D84 names for the adoption rule and the failure case. It is the primary
#: because D28's bar was set on it.
PRIMARY_CORPUS = "history-edge"

#: The baseline D28 set the bar with, and the third rung of the width ladder.
BAR_MODEL = "category_base_rate"

#: The set `fs_3` replaced (D83). Fitted only to give the width ladder its narrow rung.
PREVIOUS_FEATURE_SET = "fs_2"


@dataclass(frozen=True, slots=True)
class FailureCase:
    """The shipped model's single worst pooled test row on a corpus."""

    subject: str
    window_end: str
    probability: float
    outcome: bool
    squared_error: float
    values: dict[str, float | None]


@dataclass(frozen=True, slots=True)
class WidthRung:
    """One comparison's interval width, for the ladder below."""

    against: str
    shares: str
    width: float
    point: float


@dataclass(frozen=True, slots=True)
class CorpusTournament:
    name: str
    result: BacktestResult
    #: challenger name -> paired interval against the shipped model, subject-clustered.
    subject_intervals: dict[str, Interval | None]
    #: The same, resampling rows. Optimistic, reported next to the defensible one.
    row_intervals: dict[str, Interval | None]
    failure: FailureCase | None
    #: D82 claimed interval width is a property of the comparison rather than the sample.
    #: These are three comparisons over the *same* pooled rows, ordered by how much
    #: structure the two models share — so the claim is measured here, not restated.
    width_ladder: tuple[WidthRung, ...]
    #: Share of the pooled rows whose value was null, per nullable feature. D84 requires
    #: this printed: the challenger gets native missing handling and the shipped model gets
    #: mean imputation, so any gap includes whatever that difference is worth.
    null_shares: dict[str, float]

    def brier(self, name: str) -> float:
        return self.result.models[name].brier

    def fires_adoption_rule(self, challenger: str) -> bool:
        """D84: only a subject-clustered interval excluding zero *for the challenger*."""
        interval = self.subject_intervals.get(challenger)
        return interval is not None and interval.excludes_zero and interval.point > 0.0


def _pooled_labels(labels: Sequence[Label], *, n_folds: int) -> list[Label]:
    """The labels behind `pooled_*`, in the same order the backtest pooled them.

    `run_backtest` walks folds in order and appends each test label that is not `unknown`.
    Reconstructing that here rather than threading the labels through `BacktestResult`
    keeps the pooled arrays as the single source of order — if this drifts, the assertion
    in `_failure_case` fails loudly instead of mislabelling a row.
    """
    pooled: list[Label] = []
    for fold in rolling_origin_folds(labels, n_folds=n_folds):
        pooled.extend(
            label for label in fold.test if label.subject != EXCLUDED_FROM_HEADLINE
        )
    return pooled


def _failure_case(
    result: BacktestResult,
    labels: Sequence[Label],
    index: FeatureIndex,
    *,
    n_folds: int,
) -> FailureCase | None:
    """The row with the largest squared error from the shipped model. Chosen by `max`."""
    probabilities = result.pooled_probabilities.get(MODEL_NAME)
    if not probabilities:
        return None

    pooled = _pooled_labels(labels, n_folds=n_folds)
    if len(pooled) != len(result.pooled_outcomes):
        raise AssertionError(
            f"reconstructed {len(pooled)} pooled labels against "
            f"{len(result.pooled_outcomes)} pooled outcomes; the orders have drifted "
            "and any row named from them would be the wrong row"
        )
    if [label.outcome for label in pooled] != list(result.pooled_outcomes):
        raise AssertionError(
            "reconstructed pooled labels disagree with the pooled outcomes; refusing to "
            "name a failure case from an order that cannot be trusted"
        )

    worst_index = max(
        range(len(pooled)),
        key=lambda i: (probabilities[i] - (1.0 if pooled[i].outcome else 0.0)) ** 2,
    )
    label = pooled[worst_index]
    probability = probabilities[worst_index]
    row = index.row_for(label)
    return FailureCase(
        subject=label.subject,
        window_end=label.window_end.isoformat(),
        probability=probability,
        outcome=label.outcome,
        squared_error=(probability - (1.0 if label.outcome else 0.0)) ** 2,
        values=dict(row.values),
    )


def _null_shares(
    labels: Sequence[Label], index: FeatureIndex, *, n_folds: int
) -> dict[str, float]:
    pooled = _pooled_labels(labels, n_folds=n_folds)
    if not pooled:
        return {}
    rows = index.rows_for(pooled)
    shares: dict[str, float] = {}
    for name in nullable_features(index.feature_set):
        nulls = sum(1 for row in rows if row.values[name] is None)
        if nulls:
            shares[name] = nulls / len(rows)
    return shares


def run_tournament(
    name: str,
    labels: Sequence[Label],
    index: FeatureIndex,
    *,
    n_folds: int = 5,
    specs: Sequence[ChallengerSpec] = CHALLENGERS,
) -> CorpusTournament:
    """One backtest, every model in it. The single call is what makes the folds identical."""
    extra = {MODEL_NAME: make_return_model_fitter(index)}
    for spec in specs:
        extra[spec.name] = make_challenger_fitter(spec, index)

    # The superseded feature set, fitted here only so the width ladder below compares
    # three intervals drawn from one run over one set of rows. It is not a challenger and
    # is not subject to the adoption rule — D83 already decided it.
    previous_index = FeatureIndex(
        events=index.events,
        timeout_seconds=index.timeout_seconds,
        horizon_hours=index.horizon_hours,
        feature_set=PREVIOUS_FEATURE_SET,
    )
    previous_name = model_name(PREVIOUS_FEATURE_SET)
    extra[previous_name] = make_return_model_fitter(previous_index)

    result = run_backtest(labels, n_folds=n_folds, extra_models=extra)
    shipped = result.pooled_probabilities[MODEL_NAME]

    subject_intervals: dict[str, Interval | None] = {}
    row_intervals: dict[str, Interval | None] = {}
    for spec in specs:
        challenger = result.pooled_probabilities[spec.name]
        # Sign convention from D80: `reference - challenger`, so positive favours the
        # challenger. The reference here is the shipped model, not the bar.
        subject_intervals[spec.name] = brier_difference_interval(
            result.pooled_outcomes,
            challenger,
            shipped,
            subjects=result.pooled_subjects,
        )
        row_intervals[spec.name] = brier_difference_interval(
            result.pooled_outcomes, challenger, shipped
        )

    # Same rows, same unit, three degrees of shared structure. Rows rather than subjects:
    # with 10-12 clusters the subject interval is dominated by cluster count, which would
    # confound exactly the thing being measured.
    ladder: list[WidthRung] = []
    for against, shares in (
        (previous_name, f"12 of 14 features ({PREVIOUS_FEATURE_SET} vs {DEFAULT_FEATURE_SET})"),
        (XGB_SMALL.name, "all 18 input columns, different model class"),
        (BAR_MODEL, "nothing but the category"),
    ):
        interval = brier_difference_interval(
            result.pooled_outcomes, result.pooled_probabilities[against], shipped
        )
        if interval is not None:
            ladder.append(
                WidthRung(
                    against=against,
                    shares=shares,
                    width=interval.high - interval.low,
                    point=interval.point,
                )
            )

    return CorpusTournament(
        name=name,
        result=result,
        subject_intervals=subject_intervals,
        row_intervals=row_intervals,
        failure=_failure_case(result, labels, index, n_folds=n_folds),
        width_ladder=tuple(ladder),
        null_shares=_null_shares(labels, index, n_folds=n_folds),
    )


# --------------------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------------------


def _pooled_table(tournament: CorpusTournament) -> str:
    rows = ["| Model | Brier | Log loss | Skill vs base rate |", "|---|---:|---:|---:|"]
    for model in sorted(tournament.result.models.values(), key=lambda m: m.brier):
        mark = ""
        if model.name == MODEL_NAME:
            mark = " **(ships)**"
        elif model.name in tournament.subject_intervals:
            mark = " *(challenger, research only)*"
        elif model.name == model_name(PREVIOUS_FEATURE_SET):
            mark = " *(superseded by D83, here for the width ladder)*"
        skill = "reference" if model.skill is None else f"{model.skill:+.3f}"
        rows.append(
            f"| `{model.name}`{mark} | {model.brier:.4f} | {model.log_loss:.4f} | {skill} |"
        )
    return "\n".join(rows)


def _interval_table(tournament: CorpusTournament) -> str:
    rows = [
        f"| Challenger | Unit | Paired Brier difference (`{MODEL_NAME}` − challenger) |",
        "|---|---|---|",
    ]
    for spec in CHALLENGERS:
        for unit, source in (
            ("categories", tournament.subject_intervals),
            ("rows", tournament.row_intervals),
        ):
            interval = source.get(spec.name)
            text = "not computable" if interval is None else interval.describe()
            rows.append(f"| `{spec.name}` | {unit} | {text} |")
    return "\n".join(rows)


def _challenger_table() -> str:
    """The declared configurations, printed from the specs rather than transcribed."""
    rows = []
    for spec in CHALLENGERS:
        if spec.params:
            config = ", ".join(f"`{key}={value}`" for key, value in spec.params.items())
        else:
            config = "library defaults"
        rows.append(f"| `{spec.name}` | {config} | {spec.why} |")
    return "\n".join(rows)


def _failure_section(tournament: CorpusTournament) -> str:
    failure = tournament.failure
    if failure is None:
        return "_No pooled rows, so there is no worst one._"

    said = f"{failure.probability:.1%}"
    happened = "returned" if failure.outcome else "did not return"
    lines = [
        f"The worst single row the shipped model produced on **{tournament.name}**, chosen "
        f"by largest squared error over every pooled test row (`unknown` excluded). It was "
        f"selected by `max`, not by looking for an interesting one — D84 fixed that in "
        f"advance, including the part about publishing a dull one.",
        "",
        f"- **Category:** `{failure.subject}`",
        f"- **Window ended:** {failure.window_end}",
        f"- **Tise said:** {said} chance of returning within 24 hours",
        f"- **What happened:** the person {happened}",
        f"- **Squared error:** {failure.squared_error:.4f} "
        f"(the worst possible is 1.0000)",
        "",
        "The feature vector it saw:",
        "",
        "| Feature | Value |",
        "|---|---:|",
    ]
    for name in feature_names(DEFAULT_FEATURE_SET):
        value = failure.values.get(name)
        shown = "`null`" if value is None else f"{value:.4f}"
        lines.append(f"| `{name}` | {shown} |")
    return "\n".join(lines)


def _corpus_section(tournament: CorpusTournament) -> str:
    shipped = tournament.brier(MODEL_NAME)
    lines = [
        f"### {tournament.name}",
        "",
        f"{tournament.result.label_count:,} labels, "
        f"{len(tournament.result.pooled_outcomes):,} pooled test rows, "
        f"{tournament.result.fold_count} folds.",
        "",
        _pooled_table(tournament),
        "",
        "**The gap, as an interval.** Positive favours the challenger. This is the number "
        "D84 registered as *the* result; the point estimates above are the weaker reading.",
        "",
        _interval_table(tournament),
        "",
    ]

    fired = [
        spec.name for spec in CHALLENGERS if tournament.fires_adoption_rule(spec.name)
    ]
    if fired:
        lines.append(
            f"**The adoption rule fires here** for {', '.join(f'`{n}`' for n in fired)}: "
            "a subject-clustered interval that excludes zero in the challenger's favour. "
            "Per D84 that opens a scoped follow-up — *investigate a shippable nonlinear "
            "model* — and changes nothing that ships today."
        )
    else:
        lines.append(
            "**The adoption rule does not fire here.** No challenger's subject-clustered "
            f"interval excludes zero in its own favour against the shipped {shipped:.4f}, "
            "so no gap has been demonstrated on this corpus in either direction."
        )

    if tournament.width_ladder:
        lines.extend(
            [
                "",
                "**Why these intervals are the width they are.** D82 found that an "
                "interval's width is a property of the comparison and not only of the "
                "sample. These three comparisons run over the *same* pooled rows in the "
                "same unit, and differ only in how much structure the two models share:",
                "",
                "| Shipped model compared against | What they share "
                "| Point (positive favours the other model) | 95% width |",
                "|---|---|---:|---:|",
            ]
        )
        for rung in tournament.width_ladder:
            lines.append(
                f"| `{rung.against}` | {rung.shares} | {rung.point:+.4f} | "
                f"{rung.width:.4f} |"
            )
        widest = max(tournament.width_ladder, key=lambda rung: rung.width)
        narrowest = min(tournament.width_ladder, key=lambda rung: rung.width)
        ordered = [rung.width for rung in tournament.width_ladder]
        monotone = ordered == sorted(ordered)
        lines.append("")
        lines.append(
            f"Same rows, same estimator, widths from **{narrowest.width:.4f}** to "
            f"**{widest.width:.4f}** — a factor of "
            f"{widest.width / narrowest.width:.1f} — ordered "
            + (
                "exactly by shared structure. Sample size explains none of it."
                if monotone
                else "**not** monotonically by shared structure, so on this corpus "
                "shared structure is not the whole story."
            )
        )

    if tournament.null_shares:
        lines.extend(
            [
                "",
                "Nulls in the pooled rows — the challenger learns a missing direction for "
                "these and the shipped model mean-fills them, so part of any gap is that "
                "difference rather than the model class (D84):",
                "",
                "| Nullable feature | Share of pooled rows null |",
                "|---|---:|",
            ]
        )
        for name, share in sorted(
            tournament.null_shares.items(), key=lambda kv: -kv[1]
        ):
            lines.append(f"| `{name}` | {share:.1%} |")
    else:
        lines.extend(
            [
                "",
                "No nulls in the pooled rows here, so the imputation asymmetry D84 "
                "registered cannot account for any part of this gap.",
            ]
        )

    return "\n".join(lines)


def write_tournament_report(
    tournaments: Sequence[CorpusTournament], *, out_dir: Path, timeout_seconds: float
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "tournament.md"

    fired = sorted(
        {
            spec.name
            for tournament in tournaments
            if tournament.name == PRIMARY_CORPUS
            for spec in CHALLENGERS
            if tournament.fires_adoption_rule(spec.name)
        }
    )
    primary = next(
        (item for item in tournaments if item.name == PRIMARY_CORPUS), None
    )

    if primary is None:
        headline = (
            f"**{PRIMARY_CORPUS} was not measured in this run**, and D84's adoption rule "
            "is defined on it, so the rule is neither fired nor cleared here."
        )
    elif fired:
        headline = (
            "**A gap is demonstrated on the primary corpus.** "
            + ", ".join(f"`{name}`" for name in fired)
            + f" beats `{MODEL_NAME}` on {PRIMARY_CORPUS} by a subject-clustered interval "
            "that excludes zero. Per D84 this opens a scoped follow-up and changes nothing "
            "that ships today — XGBoost cannot run in a service worker at any score."
        )
    else:
        headline = (
            "**No gap is demonstrated.** On "
            f"{PRIMARY_CORPUS}, the corpus D84 fixed the rule on, no challenger's "
            "subject-clustered interval excludes zero in its own favour. That is not a "
            "claim that the shipped model matches XGBoost — it is a claim that this much "
            "data cannot tell them apart, which is the same finding D80 reached about the "
            "model and its bar."
        )

    sections = "\n\n".join(_corpus_section(item) for item in tournaments)
    failures = "\n\n".join(
        f"### {item.name}\n\n{_failure_section(item)}"
        for item in tournaments
        if item.name == PRIMARY_CORPUS
    )

    path.write_text(
        f"""# Tournament — what the in-browser constraint costs

Generated by `tise_research.eval.tournament`. **Do not edit by hand.** Regenerate with:

```
uv run python -m tise_research.eval.tournament
```

Session timeout {timeout_seconds:,.0f}s (D17), horizon 24h, feature set `{DEFAULT_FEATURE_SET}`.
Corpora measured **separately and never merged** (D18). XGBoost **{xgboost_version()}**,
`random_state=0`, `n_jobs=1`, `tree_method=exact`.

## Read this first

`{MODEL_NAME}` is what the extension ships. The challengers are **research only** and
cannot ship at any score: the extension trains in a browser service worker with a
hand-written optimiser (D54) and one runtime dependency. So this page is **not a model
selection**. It measures what that constraint costs.

Both configurations, the seeds, the adoption rule and the choice of failure case were
fixed in **D84 before this code existed**, because the free parameter in a tournament is
not the score — it is how strong the opponent is made. Tuned, a challenger reports a
maximum over many draws that is mostly noise at these row counts; left at library defaults
on a few hundred rows it overfits and loses to an opponent that was quietly weakened.
**No hyperparameter search was run.**

{headline}

## The challengers

| Name | Configuration | Why this one |
|---|---|---|
{_challenger_table()}

One difference from the shipped pipeline, registered in advance: the challengers see the
same eighteen design columns from the same `{DEFAULT_FEATURE_SET}` rows, but nulls arrive
as `NaN` and XGBoost learns a missing direction for them rather than being mean-filled by
`prep.py`. Standardisation is omitted because tree splits are invariant to it. Imputation
is not neutral, so **any gap below includes whatever the better missing handling is
worth** — the null counts per corpus are printed so a reader can size that.

## Results

{sections}

## The documented failure

{failures}
""",
        encoding="utf-8",
    )
    return path


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------


def main() -> int:
    from tise_research.data.corpus import load_events, load_labels

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=None)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--timeout-seconds", type=float, default=1800.0)
    parser.add_argument("--out", type=Path, default=Path("docs/benchmarks"))
    parser.add_argument(
        "--view", default=DEFAULT_VIEW, choices=["shipped", "chosen", "raw"]
    )
    args = parser.parse_args()

    copies = [args.corpus] if args.corpus else sorted(Path("data").glob("history-*.copy"))
    if not copies:
        print("No corpus found. Run analysis/history_shape.py first.")
        return 1

    tournaments: list[CorpusTournament] = []
    for copy_path in copies:
        labels = load_labels(
            copy_path, timeout_seconds=args.timeout_seconds, view=args.view
        )
        if len(labels) < args.folds * 2:
            print(f"Skipping {copy_path.stem}: only {len(labels)} labels")
            continue
        index = FeatureIndex(
            events=load_events(copy_path, view=args.view),
            timeout_seconds=args.timeout_seconds,
            horizon_hours=DEFAULT_HORIZON_HOURS,
        )
        tournament = run_tournament(
            copy_path.stem, labels, index, n_folds=args.folds
        )
        tournaments.append(tournament)
        shipped = tournament.brier(MODEL_NAME)
        challenger = tournament.brier(XGB_SMALL.name)
        print(
            f"{copy_path.stem}: {len(labels):,} labels, "
            f"{MODEL_NAME} {shipped:.4f} vs {XGB_SMALL.name} {challenger:.4f}"
        )

    if not tournaments:
        print("No corpus had enough labels.")
        return 1

    path = write_tournament_report(
        tournaments, out_dir=args.out, timeout_seconds=args.timeout_seconds
    )
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
