"""Scoring a multiclass target, and putting an interval on the difference.

**Why this exists.** `run_backtest` scores `Label.outcome`, which is a bool, with Brier.
T-C's outcome is a category name and its metric is top-1 accuracy, so none of that applies.
D94 fixed the adoption rule as "a bootstrap interval on the accuracy difference against the
floor excludes zero in the model's favour on Edge", and nothing here could produce one.

**The sign convention is the opposite of `intervals.py`, and that is the single most
dangerous thing in this file.** Brier is an error, so there `reference - challenger` is
positive when the challenger wins. Accuracy is a score, so here it is
**`challenger - reference`**. Both mean "positive favours the challenger", which is the
property worth keeping stable across the project; the arithmetic that delivers it is
inverted, and getting it backwards would invert a published verdict with nothing to catch
it. It is restated on every function for that reason.

**The bootstrap is paired and clustered, exactly as `brier_difference_interval` is.** Both
models predict the *same* rows, so the quantity with a meaningful interval is the per-row
difference in correctness — `+1` where the challenger alone is right, `-1` where the
reference alone is, `0` where they agree — not two separately estimated accuracies. The
percentile machinery, the resample count and the seed are imported rather than re-declared,
so a change to any of them moves both targets together.

**Folds come from `expanding_windows`**, the same index arithmetic `rolling_origin_folds`
uses. A second implementation of "where do the folds go" is how two benchmark tables stop
being comparable, and `test_multiclass.py` asserts the boundaries agree.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from tise_research.eval.backtest import DEFAULT_INITIAL_TRAIN_FRACTION, expanding_windows
from tise_research.eval.intervals import (
    BOOTSTRAP_SEED,
    DEFAULT_LEVEL,
    DEFAULT_RESAMPLES,
    Interval,
    percentile,
)
from tise_research.features.transitions import CategoryTransition

__all__ = [
    "DEFAULT_MIN_SOURCE_LABELS",
    "MulticlassFold",
    "MulticlassFoldResult",
    "MulticlassModel",
    "MulticlassModelResult",
    "MulticlassResult",
    "SourceResult",
    "accuracy",
    "accuracy_difference",
    "accuracy_difference_interval",
    "multiclass_folds",
    "run_multiclass_backtest",
    "top_k_accuracy",
]

#: D26's floor, applied to the source category rather than to the subject of a binary
#: label. Below this many *test* rows a per-category accuracy is a decoration.
DEFAULT_MIN_SOURCE_LABELS = 20


class MulticlassModel:
    """Anything that ranks categories for a transition. The multiclass `Baseline`.

    `ranking` returns every candidate category in descending order of belief, ties broken
    by name so top-1 never depends on dict iteration order. Top-1 is `ranking(...)[0]`,
    which is why there is no separate `predict`: two methods that could disagree about the
    same model is a defect waiting for a corpus that exposes it.
    """

    name: str

    def ranking(self, transition: CategoryTransition) -> tuple[str, ...]:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class MulticlassFold:
    index: int
    train: tuple[CategoryTransition, ...]
    test: tuple[CategoryTransition, ...]
    train_end: datetime
    test_end: datetime


def multiclass_folds(
    transitions: Sequence[CategoryTransition],
    *,
    n_folds: int = 5,
    initial_train_fraction: float = DEFAULT_INITIAL_TRAIN_FRACTION,
) -> list[MulticlassFold]:
    """Expanding-window folds over transitions ordered by when the answer became known."""
    ordered = sorted(transitions, key=lambda item: (item.at, item.transition_id))
    windows = expanding_windows(
        len(ordered), n_folds=n_folds, initial_train_fraction=initial_train_fraction
    )
    folds: list[MulticlassFold] = []
    for index, (train_stop, test_stop) in enumerate(windows):
        train = tuple(ordered[:train_stop])
        test = tuple(ordered[train_stop:test_stop])
        folds.append(
            MulticlassFold(
                index=index,
                train=train,
                test=test,
                train_end=train[-1].at,
                test_end=test[-1].at,
            )
        )
    return folds


def accuracy(outcomes: Sequence[str], predictions: Sequence[str]) -> float | None:
    """Share of rows the top-1 prediction got exactly right. None for no rows."""
    if len(outcomes) != len(predictions):
        raise ValueError(
            f"length mismatch: {len(outcomes)} outcomes, {len(predictions)} predictions"
        )
    if not outcomes:
        return None
    hits = sum(
        1
        for outcome, prediction in zip(outcomes, predictions, strict=True)
        if outcome == prediction
    )
    return hits / len(outcomes)


def top_k_accuracy(
    outcomes: Sequence[str], rankings: Sequence[Sequence[str]], k: int
) -> float | None:
    """Share of rows whose true category appears in the first `k` ranked candidates.

    Reported alongside top-1 because a "what's next" surface can show three chips, and a
    model that is right about a shortlist is a different and still useful claim. It is
    **not** the bar: D94 named top-1, and reading a verdict off top-3 after seeing top-1
    would be choosing the metric from the result.
    """
    if len(outcomes) != len(rankings):
        raise ValueError(
            f"length mismatch: {len(outcomes)} outcomes, {len(rankings)} rankings"
        )
    if not outcomes:
        return None
    if k < 1:
        raise ValueError(f"k must be at least 1, got {k}")
    hits = sum(
        1
        for outcome, ranking in zip(outcomes, rankings, strict=True)
        if outcome in ranking[:k]
    )
    return hits / len(outcomes)


def _paired_correctness(
    outcomes: Sequence[str],
    challenger: Sequence[str],
    reference: Sequence[str],
) -> list[float]:
    """Per-row `challenger correct - reference correct`, each term 0 or 1."""
    if not (len(outcomes) == len(challenger) == len(reference)):
        raise ValueError(
            f"length mismatch: {len(outcomes)} outcomes, {len(challenger)} challenger, "
            f"{len(reference)} reference"
        )
    return [
        float(c == outcome) - float(r == outcome)
        for outcome, c, r in zip(outcomes, challenger, reference, strict=True)
    ]


def accuracy_difference(
    outcomes: Sequence[str],
    challenger: Sequence[str],
    reference: Sequence[str],
) -> float | None:
    """`challenger - reference` accuracy. **Positive means the challenger is better.**

    Note the inversion against `brier_difference`, which is `reference - challenger`
    because Brier is an error and this is a score. Both are positive when the challenger
    wins; see the module docstring.
    """
    if not outcomes:
        return None
    paired = _paired_correctness(outcomes, challenger, reference)
    return sum(paired) / len(paired)


def accuracy_difference_interval(
    outcomes: Sequence[str],
    challenger: Sequence[str],
    reference: Sequence[str],
    *,
    subjects: Sequence[str] | None = None,
    unit: str = "session",
    resamples: int = DEFAULT_RESAMPLES,
    level: float = DEFAULT_LEVEL,
    seed: int = BOOTSTRAP_SEED,
) -> Interval | None:
    """Paired percentile bootstrap on `challenger - reference` accuracy.

    **Positive means the challenger is better.**

    Pass `subjects` to resample whole clusters instead of rows. D94 fixed T-C's cluster as
    the session, and the default names it — but naming is all `unit` does, and passing no
    `subjects` still resamples rows however it is labelled, so the caller must pass both.

    Returns None for empty input rather than a zero-width interval at zero, which would
    read as a confident finding of no difference.
    """
    point = accuracy_difference(outcomes, challenger, reference)
    if point is None:
        return None

    paired = _paired_correctness(outcomes, challenger, reference)

    rng = random.Random(seed)
    if subjects is None:
        groups = [[index] for index in range(len(paired))]
        unit_name = "row"
    else:
        if len(subjects) != len(paired):
            raise ValueError(
                f"length mismatch: {len(subjects)} subjects, {len(paired)} rows"
            )
        clustered: dict[str, list[int]] = {}
        for index, subject in enumerate(subjects):
            clustered.setdefault(subject, []).append(index)
        groups = list(clustered.values())
        unit_name = unit

    draws: list[float] = []
    count = len(groups)
    for _ in range(resamples):
        total = 0.0
        rows = 0
        for _ in range(count):
            for index in groups[rng.randrange(count)]:
                total += paired[index]
                rows += 1
        # A resample cannot be empty: every group holds at least one row.
        draws.append(total / rows)

    draws.sort()
    tail = (1.0 - level) / 2.0
    return Interval(
        point=point,
        low=percentile(draws, tail),
        high=percentile(draws, 1.0 - tail),
        level=level,
        resamples=resamples,
        unit=unit_name,
        units=count,
    )


@dataclass(frozen=True, slots=True)
class MulticlassFoldResult:
    index: int
    train_size: int
    test_size: int
    train_end: datetime
    test_end: datetime
    #: model name -> top-1 accuracy on this fold
    accuracy: tuple[tuple[str, float | None], ...]


@dataclass(frozen=True, slots=True)
class MulticlassModelResult:
    """Pooled over every fold's test rows, not averaged over fold accuracies.

    Averaging fold scores would weight a fold of 12 rows the same as one of 90.
    """

    name: str
    top1: float
    top3: float
    n: int


@dataclass(frozen=True, slots=True)
class SourceResult:
    """Per source category. D26: below the floor, counted and deliberately not scored."""

    from_category: str
    n: int
    reported: bool
    top1: dict[str, float] | None = None
    most_common_target: str | None = None


@dataclass(frozen=True, slots=True)
class MulticlassResult:
    target: str
    label_count: int
    fold_count: int
    models: dict[str, MulticlassModelResult]
    folds: tuple[MulticlassFoldResult, ...]
    per_source: dict[str, SourceResult]
    #: The pooled test rows, kept so an interval can be computed after the fact (D80).
    pooled_outcomes: tuple[str, ...]
    pooled_sessions: tuple[str, ...]
    pooled_sources: tuple[str, ...]
    #: model name -> that model's top-1 prediction for each pooled row, aligned.
    pooled_predictions: dict[str, tuple[str, ...]]
    #: model name -> that model's full ranking for each pooled row, aligned. Top-3 is read
    #: from here rather than recomputed, so the two numbers cannot disagree.
    pooled_rankings: dict[str, tuple[tuple[str, ...], ...]]
    min_source_labels: int
    span_start: datetime | None = None
    span_end: datetime | None = None


def run_multiclass_backtest(
    transitions: Sequence[CategoryTransition],
    models: dict[str, Callable[[Sequence[CategoryTransition]], MulticlassModel]],
    *,
    n_folds: int = 5,
    initial_train_fraction: float = DEFAULT_INITIAL_TRAIN_FRACTION,
    min_source_labels: int = DEFAULT_MIN_SOURCE_LABELS,
    target: str = "next_category",
) -> MulticlassResult:
    """Fit every model on each fold's training window and score its test window.

    Every model is fitted inside **one** call, so their folds are identical by construction
    rather than by two scripts agreeing — the same reason `tournament.py` is built that
    way, and the reason the paired bootstrap downstream is valid at all.
    """
    if not models:
        raise ValueError("no models to score; the bar is a model too and must be passed")

    folds = multiclass_folds(
        transitions, n_folds=n_folds, initial_train_fraction=initial_train_fraction
    )

    pooled_outcomes: list[str] = []
    pooled_sessions: list[str] = []
    pooled_sources: list[str] = []
    pooled_predictions: dict[str, list[str]] = {name: [] for name in models}
    pooled_rankings: dict[str, list[tuple[str, ...]]] = {name: [] for name in models}
    fold_results: list[MulticlassFoldResult] = []

    for fold in folds:
        fitted = {name: fit(fold.train) for name, fit in models.items()}
        outcomes = [item.to_category for item in fold.test]

        pooled_outcomes.extend(outcomes)
        pooled_sessions.extend(item.session_id for item in fold.test)
        pooled_sources.extend(item.from_category for item in fold.test)

        fold_accuracy: list[tuple[str, float | None]] = []
        for name, model in fitted.items():
            rankings = [model.ranking(item) for item in fold.test]
            predictions = [ranking[0] if ranking else "" for ranking in rankings]
            pooled_rankings[name].extend(rankings)
            pooled_predictions[name].extend(predictions)
            fold_accuracy.append((name, accuracy(outcomes, predictions)))

        fold_results.append(
            MulticlassFoldResult(
                index=fold.index,
                train_size=len(fold.train),
                test_size=len(fold.test),
                train_end=fold.train_end,
                test_end=fold.test_end,
                accuracy=tuple(fold_accuracy),
            )
        )

    results: dict[str, MulticlassModelResult] = {}
    for name in models:
        results[name] = MulticlassModelResult(
            name=name,
            top1=accuracy(pooled_outcomes, pooled_predictions[name]) or 0.0,
            top3=top_k_accuracy(pooled_outcomes, pooled_rankings[name], 3) or 0.0,
            n=len(pooled_outcomes),
        )

    by_source: dict[str, list[int]] = {}
    for index, source in enumerate(pooled_sources):
        by_source.setdefault(source, []).append(index)

    per_source: dict[str, SourceResult] = {}
    for source, indices in sorted(by_source.items()):
        targets = [pooled_outcomes[index] for index in indices]
        if len(indices) < min_source_labels:
            per_source[source] = SourceResult(
                from_category=source, n=len(indices), reported=False
            )
            continue
        per_source[source] = SourceResult(
            from_category=source,
            n=len(indices),
            reported=True,
            top1={
                name: accuracy(targets, [pooled_predictions[name][i] for i in indices])
                or 0.0
                for name in models
            },
            most_common_target=min(
                set(targets), key=lambda value: (-targets.count(value), value)
            ),
        )

    ordered = sorted(transitions, key=lambda item: item.at)
    return MulticlassResult(
        target=target,
        label_count=len(ordered),
        fold_count=len(folds),
        models=results,
        folds=tuple(fold_results),
        per_source=per_source,
        pooled_outcomes=tuple(pooled_outcomes),
        pooled_sessions=tuple(pooled_sessions),
        pooled_sources=tuple(pooled_sources),
        pooled_predictions={
            name: tuple(values) for name, values in pooled_predictions.items()
        },
        pooled_rankings={name: tuple(values) for name, values in pooled_rankings.items()},
        min_source_labels=min_source_labels,
        span_start=ordered[0].at if ordered else None,
        span_end=ordered[-1].at if ordered else None,
    )
