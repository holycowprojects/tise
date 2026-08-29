"""T21 — measure `block_volume` against the bar D91 fixed in advance.

    uv run python analysis/block_volume.py

Writes `docs/benchmarks/block-volume.md`. Every number comes from this file.

D91 pre-registered three predictions and one adoption rule **before any model was fitted to
this target**. This script produces the numbers those are checked against, and the verdict
paragraph at the top of the report is *computed* from the intervals rather than written down,
so it cannot outlive the numbers that justified it.

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
from tise_research.eval.backtest import BacktestResult, run_backtest  # noqa: E402
from tise_research.eval.intervals import Interval, brier_difference_interval  # noqa: E402
from tise_research.features.block_labels import (  # noqa: E402
    DEFAULT_MIN_PRIOR,
    DEFAULT_TRAILING,
    BlockIndex,
    block_volume_examples,
)
from tise_research.features.blocks import blocks_from_events, complete_blocks  # noqa: E402
from tise_research.features.vector import FEATURE_SETS  # noqa: E402
from tise_research.models.block_model import (  # noqa: E402
    BLOCK_MODEL_NAME,
    make_block_model_fitter,
)
from tise_research.models.prep import design_columns  # noqa: E402
from tise_research.reports import superseded_banner  # noqa: E402

#: D91's reference. Beating chance is uninteresting; beating a per-topic table is the question.
BAR_MODEL = "category_base_rate"

#: D91's third prediction rests on this one.
PERSISTENCE_MODEL = "same_as_last"

FLOOR_MODEL = "global_base_rate"
PRIMARY_CORPUS = "history-edge"
N_FOLDS = 5


@dataclass(frozen=True, slots=True)
class CorpusResult:
    name: str
    result: BacktestResult
    subject_interval: Interval | None
    row_interval: Interval | None
    #: `same_as_last` against the bar. D91 prediction 3.
    persistence_interval: Interval | None
    coefficients: tuple[tuple[str, float], ...]

    def brier(self, name: str) -> float:
        return self.result.models[name].brier

    @property
    def adopts_model(self) -> bool:
        """D91: subject-clustered interval excluding zero **in the model's favour**."""
        interval = self.subject_interval
        return interval is not None and interval.excludes_zero and interval.point > 0.0


def measure(copy_path: Path, *, tz: tzinfo, view: str) -> CorpusResult:
    events = load_events(copy_path, view=view)
    blocks = complete_blocks(
        blocks_from_events(events, tz=tz, granularity="day"), tz=tz
    )
    examples = block_volume_examples(blocks)
    if len(examples) < N_FOLDS * 2:
        raise ValueError(f"{copy_path.stem}: only {len(examples)} labels")

    index = BlockIndex.from_examples(examples)
    labels = [example.label for example in examples]
    result = run_backtest(
        labels,
        n_folds=N_FOLDS,
        extra_models={BLOCK_MODEL_NAME: make_block_model_fitter(index)},
    )

    outcomes = result.pooled_outcomes
    model = result.pooled_probabilities[BLOCK_MODEL_NAME]
    bar = result.pooled_probabilities[BAR_MODEL]

    # Fitted on everything, for reporting direction and size only. Not a result: it is an
    # in-sample fit and the scores above are what the predictions are checked against.
    whole = make_block_model_fitter(index)(labels)
    weights = whole.state.weights  # type: ignore[attr-defined]
    coefficients = tuple(zip(design_columns("bs_1"), weights, strict=True))

    return CorpusResult(
        name=copy_path.stem,
        result=result,
        subject_interval=brier_difference_interval(
            outcomes, model, bar, subjects=result.pooled_subjects
        ),
        row_interval=brier_difference_interval(outcomes, model, bar),
        persistence_interval=brier_difference_interval(
            outcomes,
            result.pooled_probabilities[PERSISTENCE_MODEL],
            bar,
            subjects=result.pooled_subjects,
        ),
        coefficients=coefficients,
    )


def _prediction_table(
    beats_floor: list[str],
    established: list[str],
    persistence_wins: list[str],
    corpora: int,
) -> str:
    """D91's three predictions against what happened. Computed, never written down."""

    def listed(names: list[str]) -> str:
        return ", ".join(f"`{name}`" for name in names) if names else "**nothing**"

    def verdict(held: bool) -> str:
        return "**HELD**" if held else "**FAILED**"

    return "\n".join(
        [
            "| # | Prediction | Verdict | What happened |",
            "|---|---|---|---|",
            f"| 1 | Model beats `{FLOOR_MODEL}` on all three "
            f"| {verdict(len(beats_floor) == corpora)} "
            f"| beats it on {listed(beats_floor)} |",
            f"| 2 | Model **not** distinguishable from the bar on {PRIMARY_CORPUS} "
            f"| {verdict(PRIMARY_CORPUS not in established)} "
            f"| distinguishable on {listed(established)} |",
            f"| 3 | `{PERSISTENCE_MODEL}` beats the bar somewhere "
            f"| {verdict(bool(persistence_wins))} "
            f"| beats it on {listed(persistence_wins)} |",
        ]
    )


def _describe(interval: Interval | None) -> str:
    return "not computable" if interval is None else interval.describe()


def _pooled_table(item: CorpusResult) -> str:
    rows = ["| Model | Brier | Log loss | Skill vs base rate |", "|---|---:|---:|---:|"]
    for model in sorted(item.result.models.values(), key=lambda m: m.brier):
        mark = ""
        if model.name == BLOCK_MODEL_NAME:
            mark = " **(the model)**"
        elif model.name == BAR_MODEL:
            mark = " *(the bar)*"
        skill = "reference" if model.skill is None else f"{model.skill:+.3f}"
        rows.append(
            f"| `{model.name}`{mark} | {model.brier:.4f} | {model.log_loss:.4f} | {skill} |"
        )
    return "\n".join(rows)


def _coefficient_table(item: CorpusResult) -> str:
    ordered = sorted(item.coefficients, key=lambda pair: -abs(pair[1]))
    rows = ["| Feature | Standardised weight |", "|---|---:|"]
    for name, weight in ordered:
        rows.append(f"| `{name}` | {weight:+.3f} |")
    return "\n".join(rows)


def _corpus_section(item: CorpusResult) -> str:
    subject = item.subject_interval
    row = item.row_interval
    persistence = item.persistence_interval
    return f"""### {item.name}

{item.result.label_count:,} labels, {len(item.result.pooled_outcomes):,} pooled test rows,
base rate {item.result.overall_base_rate:.1%}.

{_pooled_table(item)}

**The model against the bar**, paired on the same rows. Positive favours the model:

| Unit | Paired Brier difference (`{BAR_MODEL}` − model) |
|---|---|
| categories *(D91's rule uses this one)* | {_describe(subject)} |
| rows | {_describe(row)} |

**`{PERSISTENCE_MODEL}` against the bar** — D91's third prediction:

| Unit | Paired Brier difference (`{BAR_MODEL}` − `{PERSISTENCE_MODEL}`) |
|---|---|
| categories | {_describe(persistence)} |

**Fitted weights** on all labels, standardised columns. In-sample and reported for
direction and magnitude only — the scores above are what the predictions are checked
against:

{_coefficient_table(item)}
"""


def write_report(items: list[CorpusResult], *, out_dir: Path, tz_name: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "block-volume.md"

    primary = next((item for item in items if item.name == PRIMARY_CORPUS), None)
    beats_floor = [
        item.name for item in items if item.brier(BLOCK_MODEL_NAME) < item.brier(FLOOR_MODEL)
    ]
    established = [item.name for item in items if item.adopts_model]
    persistence_wins = [
        item.name
        for item in items
        if item.brier(PERSISTENCE_MODEL) < item.brier(BAR_MODEL)
    ]

    if primary is None:
        verdict = f"**{PRIMARY_CORPUS} was not measured**, so D91's rule cannot be applied."
    elif primary.adopts_model:
        verdict = (
            "**The bar is cleared.** On "
            f"{PRIMARY_CORPUS} the subject-clustered interval excludes zero in the model's "
            "favour, so D91 adopts the learned model over the base-rate table."
        )
    else:
        verdict = (
            "**The bar is not cleared.** On "
            f"{PRIMARY_CORPUS} the subject-clustered interval includes zero, so under D91 "
            "the **base-rate table ships** and the learned model does not. That is an "
            "outcome with a written plan, not a failure: a card reading \"71% — 11 of your "
            "last 15 days\" is driven by `category_base_rate` alone, and machine learning "
            "has to earn its place rather than be assumed into it."
        )

    return _write(path, items, verdict, beats_floor, established, persistence_wins, tz_name)


def _write(
    path: Path,
    items: list[CorpusResult],
    verdict: str,
    beats_floor: list[str],
    established: list[str],
    persistence_wins: list[str],
    tz_name: str,
) -> Path:
    def listed(names: list[str]) -> str:
        return ", ".join(f"`{name}`" for name in names) if names else "nothing"

    path.write_text(
        f"""# `block_volume` — daily, against a per-topic table

{superseded_banner("block_volume")}
Generated by `analysis/block_volume.py`. **Do not edit by hand.** Regenerate with:

```
uv run python analysis/block_volume.py
```

Blocks are local days in **{tz_name}**, trailing window {DEFAULT_TRAILING}, minimum
{DEFAULT_MIN_PRIOR} prior blocks, strict `>` on raw counts — every parameter fixed in
**D91 before any model was fitted**. Feature set `bs_1`
({len(FEATURE_SETS["bs_1"])} features, {len(design_columns("bs_1"))} design columns).
Corpora measured **separately and never merged** (D18).

## Verdict

{verdict}

## The three predictions D91 recorded

{_prediction_table(beats_floor, established, persistence_wins, len(items))}

Prediction 2 is written so that **holding it means the model fails its own bar**. That is
deliberate: D91 expected the pattern of D80 and D85 to repeat, and recorded the expectation
rather than discovering it afterwards.

## Results

{chr(10).join(_corpus_section(item) for item in items)}

## Limitations

- **One person's browsing**, three browsers, measured separately. As everywhere here.
- **Blocks come from imported history**, reconstructed through the redirect heuristic rather
  than observed. The import-versus-live offset has never been measured (D88).
- **The base rate is not 50%** — 36-47% at daily granularity (D90). D88's claim that a median
  split is balanced by construction is false on real data. What daily buys is a target that
  is not *saturated*, which is weaker.
- **Volume trends contaminate the target** (D89). A ten-block window spans ten days here
  rather than seventy, which shrinks the effect but does not remove it.
- **The fitted weights are in-sample.** They say which direction a feature pushes, not
  whether it helps out of sample.
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

    items: list[CorpusResult] = []
    for copy_path in copies:
        try:
            item = measure(copy_path, tz=tz, view=args.view)
        except ValueError as error:
            print(f"Skipping {error}")
            continue
        items.append(item)
        print(
            f"{item.name}: model {item.brier(BLOCK_MODEL_NAME):.4f} vs bar "
            f"{item.brier(BAR_MODEL):.4f} vs persistence "
            f"{item.brier(PERSISTENCE_MODEL):.4f}"
        )

    if not items:
        print("No corpus had enough labels.")
        return 1

    path = write_report(items, out_dir=args.out, tz_name=tz_name)
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
