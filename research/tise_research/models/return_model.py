"""The `return_24h` model: feature rows in, a calibrated-later probability out.

This is the first thing in the project that could be called a model rather than a
baseline, and it is deliberately the *only* new idea in T11 — everything else is
plumbing. It is a logistic regression over the fourteen features of `fs_2`, imputed and
standardised by `prep.py`, optimised by the hand-written descent in `logreg.py`.

**What it is measured against is not chance.** D28 set the bar at Brier 0.1254, which is
what `category_base_rate` scores on Edge. Beating 0.25 means nothing; beating a table of
per-category base rates means the fourteen features carry something the category alone
does not. If it does not clear that bar, the finding is that it does not, and it goes in
`DECISIONS.md` with the number.

**No cyclic encoding, on purpose.** `hourOfDay` and `dayOfWeek` are cyclic, and feeding
them to a linear model as plain integers says 23:00 and 00:00 are maximally far apart.
The standard fix is a sine/cosine pair. It is not here, because adding it before the
plain version has been measured would be tuning against an intuition rather than against
a number, and there would be no way to say afterwards whether it helped. If the model
misses the bar, this is the first thing to try, and it will be tried with the plain
version's score sitting next to it.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from tise_research.features.events import Event
from tise_research.features.labels import Label
from tise_research.features.vector import FeatureRow, compute_features
from tise_research.models.baselines import Baseline
from tise_research.models.logreg import (
    DEFAULT_SPEC,
    LogRegSpec,
    LogRegState,
    predict_proba,
    train,
)
from tise_research.models.prep import Preprocessor, design_columns, fit_preprocessor

__all__ = ["MODEL_NAME", "FeatureIndex", "ReturnModel", "make_return_model_fitter"]

MODEL_NAME = "logreg_fs2"


@dataclass(slots=True)
class FeatureIndex:
    """Feature rows for labels, computed once and reused across folds.

    A rolling-origin backtest sees the same label in every later fold's training window,
    and recomputing its vector each time is the difference between a backtest that runs
    in a minute and one that runs in an hour. The cache is keyed on `(subject,
    window_end)`, which is exactly what `compute_features` depends on — so this is memo-
    isation of a pure function and cannot change a result.

    It is emphatically **not** a place to precompute anything about the future: every row
    is produced by the same leakage-guarded functions, from the same full event list,
    filtered strictly before its own `window_end`.
    """

    events: Sequence[Event]
    timeout_seconds: float
    horizon_hours: float
    _cache: dict[tuple[str, datetime], FeatureRow] = field(default_factory=dict)

    def row_for(self, label: Label) -> FeatureRow:
        key = (label.subject, label.window_end)
        cached = self._cache.get(key)
        if cached is None:
            cached = compute_features(
                self.events,
                label.subject,
                window_end=label.window_end,
                timeout_seconds=self.timeout_seconds,
                horizon_hours=self.horizon_hours,
            )
            self._cache[key] = cached
        return cached

    def rows_for(self, labels: Sequence[Label]) -> list[FeatureRow]:
        return [self.row_for(label) for label in labels]


@dataclass(frozen=True, slots=True)
class ReturnModel(Baseline):
    """A fitted preprocessor and coefficient vector, frozen together.

    The two are inseparable: a coefficient vector applied to differently-scaled columns
    is a different model, so they are fitted on the same window and travel as one object.
    """

    name: str
    preprocessor: Preprocessor
    state: LogRegState
    spec: LogRegSpec
    index: FeatureIndex

    def predict(self, label: Label) -> float:
        row = self.index.row_for(label)
        return predict_proba(self.state, self.preprocessor.transform(row))


def fit_return_model(
    labels: Sequence[Label],
    *,
    index: FeatureIndex,
    spec: LogRegSpec = DEFAULT_SPEC,
    name: str = MODEL_NAME,
) -> ReturnModel:
    """Fit on one training window. Nothing at or after its end may be in `labels`."""
    rows = index.rows_for(labels)
    preprocessor = fit_preprocessor(rows)
    matrix = preprocessor.matrix(rows)
    outcomes = [label.outcome for label in labels]
    state = train(matrix, outcomes, spec=spec, n_columns=len(design_columns()))
    return ReturnModel(
        name=name,
        preprocessor=preprocessor,
        state=state,
        spec=spec,
        index=index,
    )


def make_return_model_fitter(
    index: FeatureIndex, *, spec: LogRegSpec = DEFAULT_SPEC
) -> Callable[[Sequence[Label]], Baseline]:
    """Bind a feature index so the model matches the `ALL_BASELINES` fitter signature."""

    def fit(labels: Sequence[Label]) -> Baseline:
        return fit_return_model(labels, index=index, spec=spec)

    return fit
