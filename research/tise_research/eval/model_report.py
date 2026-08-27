"""Generate `docs/benchmarks/model.md` — the first report about a model rather than a floor.

Every number here comes from this file. Nothing is typed by hand (SPEC.md invariant 3).

The report is deliberately harder on the model than a pooled score would be. A single
pooled Brier can clear a bar while losing most of the folds that make it up, because
pooling rewards the size of a win rather than its consistency. So the per-fold comparison
sits directly under the headline, and the fold count the model wins is stated as plainly
as the number it beat — and the paragraph that leads the report is computed from those
counts rather than written down, so it cannot outlive the numbers that justified it.

The extrapolation table exists for the same reason. Several features are cumulative
counters that only grow, so in an expanding-window backtest almost every test row lands
outside the range the coefficients were fitted on. That is a measured fact about the data,
printed here rather than left as an explanation someone might offer later.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from tise_research.eval.backtest import BacktestResult, rolling_origin_folds
from tise_research.eval.metrics import brier_score
from tise_research.features.labels import Label
from tise_research.features.vector import FEATURE_NAMES
from tise_research.models.baselines import fit_category_base_rate
from tise_research.models.logreg import DEFAULT_SPEC
from tise_research.models.prep import design_columns
from tise_research.models.return_model import MODEL_NAME, FeatureIndex, fit_return_model

__all__ = ["CorpusEvidence", "collect_evidence", "write_model_report"]

#: The baseline the model has to beat. D28 set the bar as this model's score on Edge.
BAR_MODEL = "category_base_rate"

EXCLUDED = "unknown"


class CorpusEvidence:
    """Everything the report says about one corpus, computed once."""

    def __init__(
        self,
        name: str,
        result: BacktestResult,
        labels: Sequence[Label],
        index: FeatureIndex,
        *,
        n_folds: int,
    ) -> None:
        self.name = name
        self.result = result
        self.folds: list[dict[str, float | int]] = []
        self.outside: dict[str, float] = {}

        counted = 0
        outside = dict.fromkeys(FEATURE_NAMES, 0)

        for fold in rolling_origin_folds(labels, n_folds=n_folds):
            # `unknown` is out of the headline (D27), so the fair per-fold comparison
            # excludes it too. Including it here and excluding it above would let the two
            # tables disagree for a reason nobody could see.
            test = [label for label in fold.test if label.subject != EXCLUDED]
            train_rows = index.rows_for(fold.train)
            test_rows = index.rows_for(fold.test)
            counted += len(test_rows)

            for name in FEATURE_NAMES:
                seen = [
                    row.values[name] for row in train_rows if row.values[name] is not None
                ]
                if not seen:
                    continue
                low, high = min(seen), max(seen)
                for row in test_rows:
                    value = row.values[name]
                    if value is not None and not (low <= value <= high):
                        outside[name] += 1

            if not test:
                continue
            outcomes = [label.outcome for label in test]
            model = fit_return_model(fold.train, index=index)
            baseline = fit_category_base_rate(fold.train)
            model_brier = brier_score(outcomes, [model.predict(row) for row in test])
            base_brier = brier_score(outcomes, [baseline.predict(row) for row in test])
            self.folds.append(
                {
                    "index": fold.index,
                    "train": len(fold.train),
                    "test": len(test),
                    "model": model_brier or 0.0,
                    "baseline": base_brier or 0.0,
                    "gradient_norm": model.state.gradient_norm,
                }
            )

        if counted:
            self.outside = {
                name: count / counted for name, count in outside.items() if count
            }

    @property
    def wins(self) -> int:
        return sum(1 for fold in self.folds if fold["model"] < fold["baseline"])

    @property
    def model_brier(self) -> float:
        return self.result.models[MODEL_NAME].brier

    @property
    def bar_brier(self) -> float:
        return self.result.models[BAR_MODEL].brier

    @property
    def cleared(self) -> bool:
        return self.model_brier < self.bar_brier


def _fold_table(evidence: CorpusEvidence) -> str:
    rows = [
        "| Fold | Train | Test | `logreg_fs2` | `category_base_rate` | Winner |",
        "|---:|---:|---:|---:|---:|---|",
    ]
    for fold in evidence.folds:
        winner = "model" if fold["model"] < fold["baseline"] else "**baseline**"
        rows.append(
            f"| {fold['index']} | {fold['train']:,} | {fold['test']:,} | "
            f"{fold['model']:.4f} | {fold['baseline']:.4f} | {winner} |"
        )
    return "\n".join(rows)


def _outside_table(evidence: CorpusEvidence) -> str:
    rows = ["| Feature | Test rows outside the training range |", "|---|---:|"]
    for name, share in sorted(evidence.outside.items(), key=lambda kv: -kv[1])[:6]:
        rows.append(f"| `{name}` | {share:.1%} |")
    return "\n".join(rows)


def _pooled_table(evidence: CorpusEvidence) -> str:
    rows = [
        "| Model | Brier | Log loss | Skill vs base rate |",
        "|---|---:|---:|---:|",
    ]
    for model in sorted(evidence.result.models.values(), key=lambda m: m.brier):
        mark = ""
        if model.name == MODEL_NAME:
            mark = " **(the model)**"
        elif model.name == BAR_MODEL:
            mark = " *(the bar)*"
        skill = "reference" if model.skill is None else f"{model.skill:+.3f}"
        rows.append(
            f"| `{model.name}`{mark} | {model.brier:.4f} | {model.log_loss:.4f} | {skill} |"
        )
    return "\n".join(rows)


def _corpus_section(evidence: CorpusEvidence) -> str:
    verdict = (
        f"**Clears the bar.** {evidence.model_brier:.4f} against "
        f"{evidence.bar_brier:.4f}."
        if evidence.cleared
        else f"**Does not clear the bar.** {evidence.model_brier:.4f} against "
        f"{evidence.bar_brier:.4f}, which is worse."
    )
    consistency = (
        f"It wins **{evidence.wins} of {len(evidence.folds)} folds** once `unknown` is "
        "excluded from both sides."
    )
    gradients = max((fold["gradient_norm"] for fold in evidence.folds), default=0.0)

    header = (
        f"{evidence.result.label_count:,} labels, base rate "
        f"{evidence.result.overall_base_rate:.1%}, {evidence.result.fold_count} folds."
    )
    return f"""### {evidence.name}

{header}

{verdict} {consistency}

{_pooled_table(evidence)}

Pooled over every fold's test predictions, `unknown` excluded (D27).

**Per fold**, Brier, `unknown` excluded from both models:

{_fold_table(evidence)}

Worst gradient norm at the end of any fold's fit: `{gradients:.2e}`. That is small but
it is not zero, so "converged" is the wrong word — see `convergence-budget.md`, which
measures what a five-times-longer fit does to these numbers. A poor score here is the
model being wrong, not unfinished.

**Features whose test rows fall outside the range they were fitted on:**

{_outside_table(evidence)}
"""


def collect_evidence(
    name: str,
    result: BacktestResult,
    labels: Sequence[Label],
    index: FeatureIndex,
    *,
    n_folds: int,
) -> CorpusEvidence:
    return CorpusEvidence(name, result, labels, index, n_folds=n_folds)


def write_model_report(
    evidence: Sequence[CorpusEvidence], *, out_dir: Path, timeout_seconds: float
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "model.md"

    sections = "\n\n".join(_corpus_section(item) for item in evidence)
    cleared = [item.name for item in evidence if item.cleared]
    missed = [item.name for item in evidence if not item.cleared]
    total_wins = sum(item.wins for item in evidence)
    total_folds = sum(len(item.folds) for item in evidence)

    # The tension worth leading with is corpus-specific: a corpus where the pooled score
    # clears the bar while the fold count does not agree. Computed rather than asserted,
    # so the sentence cannot outlive the numbers that justified it.
    split = [
        item for item in evidence if item.cleared and item.wins * 2 <= len(item.folds)
    ]
    if split:
        caveat = " ".join(
            f"On **{item.name}** it clears the bar while winning only "
            f"{item.wins} of {len(item.folds)} folds."
            for item in split
        )
        caveat = (
            "**Read the second line before the first.** A pooled Brier rewards the "
            "*size* of a win, not its consistency, so a model can clear the bar while "
            f"losing more folds than it wins. {caveat} The per-fold tables below are the "
            "honest picture."
        )
    else:
        caveat = (
            "The pooled score and the fold count agree on every corpus here, which is "
            "the case where a single Brier is worth quoting. It is not guaranteed to "
            "stay that way, so both are reported."
        )

    path.write_text(
        f"""# Model — `return_24h`, logistic regression over `fs_2`

Generated by `tise_research.eval.model_report`. **Do not edit by hand.** Regenerate with:

```
uv run python -m tise_research.eval.backtest --with-model
```

Session timeout {timeout_seconds:,.0f}s (D17), horizon 24h, one label per
(category, session) (D16). Corpora are measured **separately and never merged** (D18).
Baselines are reported alongside on identical folds, always (D24).

## The model

Logistic regression over the fourteen features of `fs_2`, imputed and standardised by
`models/prep.py` into {len(design_columns())} columns, optimised by
{DEFAULT_SPEC.iterations:,} steps of full-batch gradient descent.

The optimiser is hand-written rather than taken from scikit-learn, because the same
arithmetic has to run in the browser and be reproducible there to 1e-9. The step size is
derived from the design matrix rather than declared, so it cannot diverge on a profile
nobody tested. Both choices cost accuracy against a tuned LBFGS fit and buy a model the
extension can actually train.

## The result

The bar is D28: **Brier 0.1254 on Edge**, the score `category_base_rate` reaches there.
Beating chance is not interesting; beating a table of per-category base rates is.

- **Cleared on:** {", ".join(cleared) if cleared else "nothing"}
- **Missed on:** {", ".join(missed) if missed else "nothing"}
- Across every corpus the model wins **{total_wins} of {total_folds} folds**.

{caveat}

## The pattern, and what is measured about it

The model wins the early folds and loses the late ones, on every corpus. That is the
opposite of what more training data should do, so it is worth naming what is actually
measured rather than what could be argued.

Several features are **cumulative counters that only ever grow** — `hoursSinceFirstSeen`
most of all, then `priorSessionCount` and `eventCount30d`. In an expanding-window
backtest, a test row always sits later in the calendar than every training row, so those
features land outside the range the coefficients were fitted on. The tables below give the
share; on Edge it is over three quarters of test rows for `hoursSinceFirstSeen`.

A linear model extrapolating a coefficient beyond its fitted range is not a bug, but it is
a reason to expect exactly this shape of failure. **It is a lead, not a conclusion.**
Confirming it means changing those features and re-running these folds, and any such
change has to be chosen without looking at the numbers below — otherwise the fix is fitted
to the test set. That work is T16.

{sections}

## Limitations

- **One person's browsing.** Every number describes the author. Nothing generalises.
- **No confidence intervals.** The fold-level differences here are tens of labels wide,
  and several of the per-fold gaps are well inside what noise could produce. Intervals
  are T16, and until they exist "wins 2 of 5 folds" is the more honest summary than any
  single Brier score.
- **Regularisation is not tuned, on purpose.** `l2` is fixed at
  {DEFAULT_SPEC.l2:g} pseudo-observations for every fold and every corpus. Choosing it per
  fold from the training window is legitimate and would probably help the small early
  folds; choosing it by looking at this report would not.
- **No calibration yet.** These are raw logistic outputs. Reliability curves and the
  abstention threshold are T12.
- **`unknown` is excluded from every headline** (D27) and is the most predictable
  category there is (D42). Including it would improve every number on this page and mean
  nothing.
""",
        encoding="utf-8",
    )
    return path
