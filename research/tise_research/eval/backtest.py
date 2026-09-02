"""Rolling-origin backtest for `return_24h`.

Folds expand: fold *n* trains on everything before its cutoff and tests on the chunk
immediately after. Nothing is shuffled, no fold trains on data that comes after its test
window, and there is no random seed anywhere — the result is byte-identical run to run.

That matters more than it sounds. A leaked evaluation does not look broken; it looks
*good*. There is no error message and no failing assertion, only a benchmark table that
is quietly fictional. So the fold structure is asserted directly in
`research/tests/test_backtest.py` rather than trusted.

Two reporting rules come from earlier tasks and are enforced here:

* **D26 — a category below the label floor gets no score.** Nine of fifteen categories
  have fewer than ten labels on real browsing. A Brier score over three points is a
  decoration, and printing one implies a measurement that was never made.
* **D27 — `unknown` is excluded from the headline.** It is the user's own frequent
  domains collapsed into one bucket: highly predictable, so it inflates every aggregate,
  and unpresentable, so no UI can ever show it.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from tise_research.data.chrome_history import DEFAULT_VIEW
from tise_research.eval.metrics import base_rate, brier_score, log_loss, skill_score
from tise_research.features.labels import DEFAULT_HORIZON_HOURS, Label
from tise_research.models.baselines import ALL_BASELINES, Baseline

__all__ = [
    "BacktestResult",
    "CategoryResult",
    "Fold",
    "FoldResult",
    "ModelResult",
    "expanding_windows",
    "rolling_origin_folds",
    "run_backtest",
]

#: Share of labels reserved as the first training window before scoring begins.
DEFAULT_INITIAL_TRAIN_FRACTION = 0.4

#: D26. Below this many *test* labels, a category is counted but not scored.
DEFAULT_MIN_CATEGORY_LABELS = 20

#: D27. Kept out of every aggregate, reported on its own.
EXCLUDED_FROM_HEADLINE = "unknown"

#: The reference every skill score is measured against.
REFERENCE_MODEL = "global_base_rate"


@dataclass(frozen=True, slots=True)
class Fold:
    index: int
    train: tuple[Label, ...]
    test: tuple[Label, ...]
    train_end: datetime
    test_end: datetime


def expanding_windows(
    n_items: int,
    *,
    n_folds: int = 5,
    initial_train_fraction: float = DEFAULT_INITIAL_TRAIN_FRACTION,
) -> list[tuple[int, int]]:
    """`(train_stop, test_stop)` index pairs over a chronologically ordered sequence.

    Fold *n* trains on `[0, train_stop)` and tests on `[train_stop, test_stop)`. The final
    fold absorbs the remainder so no item is silently dropped.

    **Extracted so a second target cannot cut its folds differently.** `run_backtest` is
    binary-only, and T-C needed a multiclass backtest; a second copy of this arithmetic is
    exactly the kind of thing that drifts by one item and produces two benchmark tables
    that are not comparable. Both callers now cut identical boundaries by construction, and
    `test_multiclass.py` asserts it against `rolling_origin_folds` directly.
    """
    if n_items < n_folds * 2:
        raise ValueError(
            f"{n_items} labels cannot support {n_folds} folds; "
            "reduce n_folds or collect more history"
        )

    start = max(int(n_items * initial_train_fraction), n_folds)
    remaining = n_items - start
    if remaining < n_folds:
        raise ValueError(
            f"only {remaining} labels after the initial training window; "
            f"cannot cut {n_folds} folds"
        )

    chunk = remaining // n_folds
    windows: list[tuple[int, int]] = []
    for index in range(n_folds):
        train_stop = start + index * chunk
        test_stop = n_items if index == n_folds - 1 else train_stop + chunk
        windows.append((train_stop, test_stop))
    return windows


def rolling_origin_folds(
    labels: Sequence[Label],
    *,
    n_folds: int = 5,
    initial_train_fraction: float = DEFAULT_INITIAL_TRAIN_FRACTION,
) -> list[Fold]:
    """Split time-sorted labels into expanding-window folds.

    Boundaries are index-based over labels sorted by `window_end`, which keeps test
    windows comparable in size. They remain strictly chronological — each fold's report
    carries its calendar range so the spread over real time is visible rather than
    assumed.
    """
    ordered = sorted(labels, key=lambda label: (label.window_end, label.subject))
    windows = expanding_windows(
        len(ordered), n_folds=n_folds, initial_train_fraction=initial_train_fraction
    )

    folds: list[Fold] = []
    for index, (train_stop, test_stop) in enumerate(windows):
        train = tuple(ordered[:train_stop])
        test = tuple(ordered[train_stop:test_stop])
        folds.append(
            Fold(
                index=index,
                train=train,
                test=test,
                train_end=train[-1].window_end,
                test_end=test[-1].window_end,
            )
        )
    return folds


@dataclass(frozen=True, slots=True)
class FoldResult:
    index: int
    train_size: int
    test_size: int
    train_end: datetime
    test_end: datetime
    base_rate: float | None
    #: model name -> Brier score on this fold
    brier: tuple[tuple[str, float | None], ...]


@dataclass(frozen=True, slots=True)
class ModelResult:
    """Pooled over every fold's test predictions, not averaged over fold scores.

    Averaging fold scores would weight a fold of 12 labels the same as one of 90.
    """

    name: str
    brier: float
    log_loss: float
    skill: float | None
    n: int


@dataclass(frozen=True, slots=True)
class CategoryResult:
    subject: str
    n: int
    base_rate: float | None
    #: False when below the label floor: counted, deliberately not scored (D26).
    reported: bool
    brier: float | None = None
    best_model: str | None = None


@dataclass(frozen=True, slots=True)
class BacktestResult:
    target: str
    label_count: int
    fold_count: int
    overall_base_rate: float | None
    models: dict[str, ModelResult]
    folds: tuple[FoldResult, ...]
    per_category: dict[str, CategoryResult]
    #: The pooled headline test rows, kept so an interval can be computed after the fact
    #: (D80). Outcomes, each model's probability, and the subject each row belongs to —
    #: the last is what makes a cluster bootstrap possible, and a Brier score alone
    #: cannot be given an interval once these are thrown away.
    pooled_outcomes: tuple[bool, ...]
    pooled_subjects: tuple[str, ...]
    pooled_probabilities: dict[str, tuple[float, ...]]
    headline_excludes_unknown: bool
    unknown_label_count: int
    min_category_labels: int
    span_start: datetime | None = None
    span_end: datetime | None = None
    #: The session each pooled row belongs to, aligned with `pooled_subjects`. D94: the
    #: cluster does not have to be the category, and while it always was, every published
    #: interval was built from 9-12 things regardless of how many rows it held. Kept
    #: alongside rather than instead of the subject so both bounds stay available.
    pooled_sessions: tuple[str, ...] = ()
    #: The `label_id` of each pooled row, aligned with `pooled_outcomes`. Without it a
    #: pooled row cannot be mapped back to the feature that produced it, so an analysis
    #: can report a score over every test row and never over an interesting *slice* of
    #: them. Empty for emitters that supply no id — `return_24h` predates the field.
    pooled_label_ids: tuple[str, ...] = ()


def run_backtest(
    labels: Sequence[Label],
    *,
    n_folds: int = 5,
    initial_train_fraction: float = DEFAULT_INITIAL_TRAIN_FRACTION,
    min_category_labels: int = DEFAULT_MIN_CATEGORY_LABELS,
    extra_models: dict[str, Callable[[Sequence[Label]], Baseline]] | None = None,
) -> BacktestResult:
    """Fit every model on each fold's training window and score its test window.

    `extra_models` is added *alongside* the baselines, never in place of them. D24 makes
    the baselines mandatory in every report, and a model that appears without them is a
    number with nothing underneath it.
    """
    fitters: dict[str, Callable[[Sequence[Label]], Baseline]] = {
        **ALL_BASELINES,
        **(extra_models or {}),
    }
    folds = rolling_origin_folds(
        labels, n_folds=n_folds, initial_train_fraction=initial_train_fraction
    )

    pooled_outcomes: dict[str, list[bool]] = defaultdict(list)
    pooled_probabilities: dict[str, list[float]] = defaultdict(list)
    pooled_subjects: list[str] = []
    pooled_sessions: list[str] = []
    pooled_label_ids: list[str] = []
    by_category: dict[str, dict[str, list]] = defaultdict(
        lambda: {"outcomes": [], "probabilities": defaultdict(list)}
    )
    fold_results: list[FoldResult] = []

    for fold in folds:
        fitted = {name: fit(fold.train) for name, fit in fitters.items()}
        outcomes = [label.outcome for label in fold.test]

        fold_brier: list[tuple[str, float | None]] = []
        for name, model in fitted.items():
            probabilities = [model.predict(label) for label in fold.test]
            fold_brier.append((name, brier_score(outcomes, probabilities)))

            # `unknown` is pooled separately and never enters the headline (D27).
            for label, probability in zip(fold.test, probabilities, strict=True):
                bucket = by_category[label.subject]
                bucket["probabilities"][name].append(probability)
                if name == REFERENCE_MODEL:
                    bucket["outcomes"].append(label.outcome)
                if label.subject != EXCLUDED_FROM_HEADLINE:
                    pooled_probabilities[name].append(probability)
                    if name == REFERENCE_MODEL:
                        pooled_outcomes["_"].append(label.outcome)
                        pooled_subjects.append(label.subject)
                        pooled_sessions.append(label.session_id)
                        pooled_label_ids.append(label.label_id)

        fold_results.append(
            FoldResult(
                index=fold.index,
                train_size=len(fold.train),
                test_size=len(fold.test),
                train_end=fold.train_end,
                test_end=fold.test_end,
                base_rate=base_rate(outcomes),
                brier=tuple(fold_brier),
            )
        )

    headline_outcomes = pooled_outcomes["_"]
    reference_brier = brier_score(
        headline_outcomes, pooled_probabilities[REFERENCE_MODEL]
    )

    models: dict[str, ModelResult] = {}
    for name in fitters:
        probabilities = pooled_probabilities[name]
        models[name] = ModelResult(
            name=name,
            brier=brier_score(headline_outcomes, probabilities) or 0.0,
            log_loss=log_loss(headline_outcomes, probabilities) or 0.0,
            skill=skill_score(
                brier_score(headline_outcomes, probabilities), reference_brier
            ),
            n=len(probabilities),
        )

    per_category: dict[str, CategoryResult] = {}
    for subject, bucket in sorted(by_category.items()):
        outcomes = bucket["outcomes"]
        if len(outcomes) < min_category_labels:
            per_category[subject] = CategoryResult(
                subject=subject,
                n=len(outcomes),
                base_rate=base_rate(outcomes),
                reported=False,
            )
            continue
        scores = {
            name: brier_score(outcomes, bucket["probabilities"][name])
            for name in fitters
        }
        best = min(scores, key=lambda name: scores[name] if scores[name] else 1.0)
        per_category[subject] = CategoryResult(
            subject=subject,
            n=len(outcomes),
            base_rate=base_rate(outcomes),
            reported=True,
            brier=scores[best],
            best_model=best,
        )

    ordered = sorted(labels, key=lambda label: label.window_end)
    return BacktestResult(
        target="return_24h",
        label_count=len(ordered),
        fold_count=len(folds),
        overall_base_rate=base_rate([label.outcome for label in ordered]),
        models=models,
        folds=tuple(fold_results),
        per_category=per_category,
        pooled_outcomes=tuple(headline_outcomes),
        pooled_subjects=tuple(pooled_subjects),
        pooled_sessions=tuple(pooled_sessions),
        pooled_label_ids=tuple(pooled_label_ids),
        pooled_probabilities={
            name: tuple(pooled_probabilities[name]) for name in fitters
        },
        headline_excludes_unknown=True,
        unknown_label_count=sum(
            1 for label in ordered if label.subject == EXCLUDED_FROM_HEADLINE
        ),
        min_category_labels=min_category_labels,
        span_start=ordered[0].window_end if ordered else None,
        span_end=ordered[-1].window_end if ordered else None,
    )


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------


def main() -> int:
    from tise_research.data.corpus import load_labels
    from tise_research.eval.report import write_baseline_report

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="return_24h", choices=["return_24h"])
    parser.add_argument(
        "--corpus",
        type=Path,
        default=None,
        help="History database copy. Defaults to every copy in data/.",
    )
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--timeout-seconds", type=float, default=1800.0)
    parser.add_argument("--out", type=Path, default=Path("docs/benchmarks"))
    parser.add_argument(
        "--view",
        default=DEFAULT_VIEW,
        choices=["shipped", "chosen", "raw"],
        help="Which corpus (D78). `chosen` reproduces the superseded pre-D78 numbers.",
    )
    parser.add_argument(
        "--with-model",
        action="store_true",
        help="Fit logreg_fs2 alongside the baselines and write model.md as well.",
    )
    args = parser.parse_args()

    copies = [args.corpus] if args.corpus else sorted(Path("data").glob("history-*.copy"))
    if not copies:
        print("No corpus found. Run analysis/history_shape.py first.")
        return 1

    results: dict[str, BacktestResult] = {}
    evidence = []
    for copy_path in copies:
        labels = load_labels(
            copy_path, timeout_seconds=args.timeout_seconds, view=args.view
        )
        if len(labels) < args.folds * 2:
            print(f"Skipping {copy_path.stem}: only {len(labels)} labels")
            continue

        extra = None
        index = None
        if args.with_model:
            from tise_research.data.corpus import load_events
            from tise_research.models.return_model import (
                MODEL_NAME,
                FeatureIndex,
                make_return_model_fitter,
            )

            index = FeatureIndex(
                # The view has to match the one the labels came from. Without it,
                # `--view chosen` labels from one corpus and computes features from
                # another, and D78 exists because that distinction changes the numbers.
                # The default path is unaffected — both default to `shipped` — so no
                # published number was ever built this way.
                events=load_events(copy_path, view=args.view),
                timeout_seconds=args.timeout_seconds,
                horizon_hours=DEFAULT_HORIZON_HOURS,
            )
            extra = {MODEL_NAME: make_return_model_fitter(index)}

        result = run_backtest(labels, n_folds=args.folds, extra_models=extra)
        results[copy_path.stem] = result
        print(f"{copy_path.stem}: {len(labels):,} labels, {args.folds} folds")

        if args.with_model and index is not None:
            from tise_research.eval.model_report import collect_evidence

            evidence.append(
                collect_evidence(
                    copy_path.stem, result, labels, index, n_folds=args.folds
                )
            )

    if not results:
        print("No corpus had enough labels to backtest.")
        return 1

    path = write_baseline_report(
        results, out_dir=args.out, timeout_seconds=args.timeout_seconds
    )
    print(f"Wrote {path}")

    if evidence:
        from tise_research.eval.model_report import write_model_report

        model_path = write_model_report(
            evidence, out_dir=args.out, timeout_seconds=args.timeout_seconds
        )
        print(f"Wrote {model_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
