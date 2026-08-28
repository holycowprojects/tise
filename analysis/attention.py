"""Is attention predictable? A scouting measurement, not an adoption test.

    uv run python analysis/attention.py

Writes `docs/benchmarks/attention.md`.

**Nothing here can adopt anything.** D91 fixed the discipline: a performance bar is
pre-registered before a model is fitted, or it is not a bar. No bar exists for this target,
so the model score below is **exploratory** — it says whether the direction is worth a
pre-registration, and nothing more. If it looks promising the next step is T20's procedure
again, not a decision taken from this page.

The question it answers cheaply: since T1 the duration trap has been recorded as permanent —
the history *file* has `visit_duration`, the `chrome.history` API does not. `chrome.tabs`
would let the extension measure dwell live, which turns a research-only signal into a
shippable one. Rather than request that permission on a hope, this measures whether dwell is
predictable at all, using the file we already have.

Firefox records no duration and is skipped. Aggregates only; no domain, URL or title is
written anywhere by this script.
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
from tise_research.eval.backtest import BacktestResult, run_backtest  # noqa: E402
from tise_research.eval.intervals import Interval, brier_difference_interval  # noqa: E402
from tise_research.features.attention import (  # noqa: E402
    ATTENTION_FEATURE_SET,
    DEFAULT_MIN_PRIOR_VISITS,
    DEFAULT_TRAILING_VISITS,
    attention_examples,
)
from tise_research.features.labels import Label  # noqa: E402
from tise_research.features.vector import FeatureRow  # noqa: E402
from tise_research.models.baselines import Baseline  # noqa: E402
from tise_research.models.logreg import DEFAULT_SPEC, predict_proba, train  # noqa: E402
from tise_research.models.prep import design_columns, fit_preprocessor  # noqa: E402

TIMEOUT_SECONDS = 1800.0
BAR_MODEL = "category_base_rate"
FLOOR_MODEL = "global_base_rate"
MODEL_NAME = f"logreg_{ATTENTION_FEATURE_SET.replace('_', '')}"
N_FOLDS = 5


@dataclass(frozen=True, slots=True)
class _Model(Baseline):
    name: str
    preprocessor: object
    state: object
    rows: dict[tuple[str, object], FeatureRow]

    def predict(self, label: Label) -> float:
        row = self.rows[(label.subject, label.window_end)]
        return predict_proba(self.state, self.preprocessor.transform(row))  # type: ignore[attr-defined]


def _fitter(rows: dict[tuple[str, object], FeatureRow]):
    def fit(labels):
        window = [rows[(label.subject, label.window_end)] for label in labels]
        preprocessor = fit_preprocessor(window)
        state = train(
            preprocessor.matrix(window),
            [label.outcome for label in labels],
            spec=DEFAULT_SPEC,
            n_columns=len(design_columns(ATTENTION_FEATURE_SET)),
        )
        return _Model(MODEL_NAME, preprocessor, state, rows)

    return fit


@dataclass(frozen=True, slots=True)
class CorpusResult:
    name: str
    events: int
    with_dwell: int
    result: BacktestResult
    interval: Interval | None
    #: Against the constant. The honest comparison here: the label is a per-category
    #: median split, so `category_base_rate` is ~50% for every category *by construction*
    #: and the nominal bar is barely distinguishable from a constant.
    floor_interval: Interval | None
    coefficients: tuple[tuple[str, float], ...]

    def brier(self, name: str) -> float:
        return self.result.models[name].brier


def measure(copy_path: Path, *, view: str) -> CorpusResult:
    events = load_events(copy_path, view=view)
    with_dwell = sum(1 for event in events if event.dwell_seconds is not None)
    if not with_dwell:
        raise ValueError(f"{copy_path.stem}: no dwell recorded")

    examples = attention_examples(events, timeout_seconds=TIMEOUT_SECONDS)
    if len(examples) < N_FOLDS * 2:
        raise ValueError(f"{copy_path.stem}: only {len(examples)} labels")

    rows = {
        (example.label.subject, example.label.window_end): example.row
        for example in examples
    }
    labels = [example.label for example in examples]
    result = run_backtest(labels, n_folds=N_FOLDS, extra_models={MODEL_NAME: _fitter(rows)})

    fitted = _fitter(rows)(labels)
    return CorpusResult(
        name=copy_path.stem,
        events=len(events),
        with_dwell=with_dwell,
        result=result,
        interval=brier_difference_interval(
            result.pooled_outcomes,
            result.pooled_probabilities[MODEL_NAME],
            result.pooled_probabilities[BAR_MODEL],
            subjects=result.pooled_subjects,
        ),
        floor_interval=brier_difference_interval(
            result.pooled_outcomes,
            result.pooled_probabilities[MODEL_NAME],
            result.pooled_probabilities[FLOOR_MODEL],
            subjects=result.pooled_subjects,
        ),
        coefficients=tuple(
            zip(
                design_columns(ATTENTION_FEATURE_SET),
                fitted.state.weights,  # type: ignore[attr-defined]
                strict=True,
            )
        ),
    )


def _section(item: CorpusResult) -> str:
    rows = ["| Model | Brier | Log loss | Skill |", "|---|---:|---:|---:|"]
    for model in sorted(item.result.models.values(), key=lambda m: m.brier):
        mark = " **(the model)**" if model.name == MODEL_NAME else ""
        mark = " *(the bar)*" if model.name == BAR_MODEL else mark
        skill = "reference" if model.skill is None else f"{model.skill:+.3f}"
        rows.append(
            f"| `{model.name}`{mark} | {model.brier:.4f} | {model.log_loss:.4f} | {skill} |"
        )

    weights = ["| Feature | Standardised weight |", "|---|---:|"]
    for name, weight in sorted(item.coefficients, key=lambda pair: -abs(pair[1])):
        weights.append(f"| `{name}` | {weight:+.3f} |")

    described = "not computable" if item.interval is None else item.interval.describe()
    floor = (
        "not computable"
        if item.floor_interval is None
        else item.floor_interval.describe()
    )
    return f"""### {item.name}

{item.events:,} events, {item.with_dwell:,} with a recorded duration.
**{item.result.label_count:,} labels**, {len(item.result.pooled_outcomes):,} pooled test
rows, base rate {item.result.overall_base_rate:.1%}.

{chr(10).join(rows)}

**Model against the bar**, paired, subject-clustered. Positive favours the model:

{described}

**Model against the constant** (`{FLOOR_MODEL}`) — the comparison that carries weight here,
since a per-category median split makes the nominal bar ~50% for every category:

{floor}

**Fitted weights**, in-sample, standardised columns:

{chr(10).join(weights)}
"""


def write_report(items: list[CorpusResult], *, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "attention.md"

    total = sum(item.result.label_count for item in items)
    beats_bar = [item.name for item in items if item.brier(MODEL_NAME) < item.brier(BAR_MODEL)]
    beats_floor = [
        item.name for item in items if item.brier(MODEL_NAME) < item.brier(FLOOR_MODEL)
    ]
    separated = [
        item.name
        for item in items
        if item.interval is not None
        and item.interval.excludes_zero
        and item.interval.point > 0.0
    ]

    def listed(names: list[str]) -> str:
        return ", ".join(f"`{n}`" for n in names) if names else "**nothing**"

    path.write_text(
        f"""# Attention — is dwell predictable?

Generated by `analysis/attention.py`. **Do not edit by hand.** Regenerate with:

```
uv run python analysis/attention.py
```

One label per visit: **did you stay longer than your recent median for this category?**
Trailing window {DEFAULT_TRAILING_VISITS} visits, minimum {DEFAULT_MIN_PRIOR_VISITS} prior.
Feature set `{ATTENTION_FEATURE_SET}`, **`full` compat class** — it needs dwell, which the
`chrome.history` API cannot supply. Firefox records no duration and is skipped (D18: corpora
are never merged).

## This is a scouting measurement, not an adoption test

D91 fixed the rule: a performance bar is pre-registered **before** a model is fitted, or it
is not a bar. No bar exists for this target. **Nothing on this page can adopt anything** —
it says whether the direction earns a pre-registration, and nothing else.

## What it found

- **{total:,} labels** across {len(items)} corpora — against `block_volume`'s 403 and
  `return_24h`'s 998. The unit is a visit, which is the finest the data contains.
- Model beats the bar (`{BAR_MODEL}`) on: {listed(beats_bar)}
- Model beats the floor (`{FLOOR_MODEL}`) on: {listed(beats_floor)}
- Separated from the bar by a subject-clustered interval on: {listed(separated)}

## Results

{chr(10).join(_section(item) for item in items)}

## Limitations

- **One person's browsing**, two browsers. Firefox has no duration column at all.
- **Dwell comes from the history database**, which the extension cannot read. Shipping this
  would need the `tabs` permission — the decision this page exists to inform.
- **`visit_duration` is not attention.** It measures how long a tab held a URL, not how long
  a person looked at it. A tab left open overnight records a long duration and no attention.
  Nothing here corrects for that, and `idle` plus window focus is what would.
- **No path or URL features.** `Visit` drops the URL at the reader boundary and this
  measurement does not reach past it.
- **The model is exploratory**, fitted with no pre-registered bar. Its score is a reason to
  pre-register or to stop, not a result.
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
        print(
            f"{item.name}: {item.result.label_count:,} labels, base rate "
            f"{item.result.overall_base_rate:.1%}, model {item.brier(MODEL_NAME):.4f} "
            f"vs bar {item.brier(BAR_MODEL):.4f}"
        )

    if not items:
        print("No corpus had usable dwell.")
        return 1

    print(f"Wrote {write_report(items, out_dir=args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
