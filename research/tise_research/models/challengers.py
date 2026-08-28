"""Challengers for the tournament (D84). Research only — none of this can ship.

The extension trains in the browser with a hand-written optimiser (D54) and one runtime
dependency. XGBoost cannot ship at any score, so nothing here is a candidate for shipping
and nothing here has a TypeScript twin or enters the parity contract. What it measures is
**what the in-browser constraint costs**, and the answer is reported as an interval.

Everything about the configuration was fixed in D84 before this file existed, because the
free parameter in a tournament is not the score — it is how strong I make the opponent.
Tuned, XGBoost reports a maximum over many draws that is mostly noise at these row counts;
left at library defaults on a few hundred rows it overfits and loses to a challenger I
weakened. Both look like an honest table afterwards. So there are exactly two declared
configurations here, and **no search anywhere**.

**The one deliberate difference from the shipped pipeline**, also registered in advance:
the challenger sees the same eighteen design columns from the same `fs_3` rows, but nulls
arrive as `NaN` and XGBoost learns a missing direction for them, instead of being mean-
filled by `prep.py`. Standardisation is omitted because tree splits are invariant to a
monotone per-column transform, so it would change nothing. Imputation is *not* neutral,
which is why passing `NaN` is the fair thing to do — a practitioner building this
challenger would — and why any gap measured here includes whatever the better missing
handling is worth. The report prints the null counts so a reader can size that.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from tise_research.features.labels import Label
from tise_research.models.baselines import NO_INFORMATION, Baseline
from tise_research.models.prep import design_columns, raw_row
from tise_research.models.return_model import FeatureIndex

__all__ = [
    "CHALLENGERS",
    "XGB_DEFAULT",
    "XGB_SMALL",
    "ChallengerSpec",
    "design_vector",
    "make_challenger_fitter",
    "xgboost_version",
]


#: Fixed so a run is reproducible. SPEC.md invariant 3 asks for a committed script behind
#: every number, and a number that moves between runs of that script does not satisfy it.
DETERMINISM: dict[str, Any] = {
    "random_state": 0,
    "n_jobs": 1,
    "tree_method": "exact",
}


@dataclass(frozen=True, slots=True)
class ChallengerSpec:
    """A named, frozen configuration. Declared in D84; not searched, not tuned."""

    name: str
    why: str
    params: dict[str, Any] = field(default_factory=dict)

    def resolved(self) -> dict[str, Any]:
        return {**self.params, **DETERMINISM}


#: The primary. Library defaults assume ~10^5 rows; these folds train on a few hundred, so
#: depth 3 with `min_child_weight=5` is the ordinary small-data posture — every leaf holds
#: at least five of roughly three hundred rows. Primary because it is the **stronger**
#: challenger by argument: the shipped model should face the best opponent that can be
#: specified without searching for one.
XGB_SMALL = ChallengerSpec(
    name="xgb_small",
    why="depth-3 trees sized for a few hundred rows, per D84",
    params={
        "max_depth": 3,
        "n_estimators": 100,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 5,
        "reg_lambda": 1.0,
    },
)

#: The secondary: what a reviewer gets out of the box. Reported so a loss cannot be blamed
#: on my configuring XGBoost badly, nor a win credited to my configuring it well.
XGB_DEFAULT = ChallengerSpec(
    name="xgb_default",
    why="library defaults, untouched, as a reviewer would first run it",
)

CHALLENGERS: tuple[ChallengerSpec, ...] = (XGB_SMALL, XGB_DEFAULT)


def xgboost_version() -> str:
    """Resolved at run time and printed in the report, so the run is reconstructable."""
    import xgboost

    return str(xgboost.__version__)


def design_vector(row: Any) -> list[float]:
    """The eighteen design columns, nulls left as `NaN` rather than filled.

    `raw_row` already separates measured values from missingness indicators and refuses a
    `None` in a feature not declared nullable, so the same guard that protects the linear
    model protects this one.
    """
    values, indicators = raw_row(row)
    return [float("nan") if value is None else value for value in values] + indicators


@dataclass(frozen=True, slots=True)
class _Constant(Baseline):
    """Used when a training window cannot support a fit — see `fit_challenger`."""

    name: str
    value: float

    def predict(self, label: Label) -> float:  # noqa: ARG002 - signature is the contract
        return self.value


@dataclass(frozen=True, slots=True)
class XGBChallenger(Baseline):
    """A fitted booster bound to the feature index that produced its training rows."""

    name: str
    booster: Any
    index: FeatureIndex
    columns: tuple[str, ...]

    def predict(self, label: Label) -> float:
        import numpy as np

        row = self.index.row_for(label)
        matrix = np.asarray([design_vector(row)], dtype=float)
        return float(self.booster.predict_proba(matrix)[0][1])


def fit_challenger(
    labels: Sequence[Label], *, spec: ChallengerSpec, index: FeatureIndex
) -> Baseline:
    """Fit one challenger on one training window. Nothing at or after its end is in it.

    A window with no labels, or with only one outcome present, gets a constant predictor
    rather than a booster. That is not a workaround: a classifier cannot be fitted on one
    class, and the honest prediction from such a window is the rate it observed. The
    baselines make the same choice for the same reason.
    """
    import numpy as np
    from xgboost import XGBClassifier

    if not labels:
        return _Constant(spec.name, NO_INFORMATION)

    outcomes = [label.outcome for label in labels]
    if len(set(outcomes)) < 2:
        return _Constant(spec.name, 1.0 if outcomes[0] else 0.0)

    rows = index.rows_for(labels)
    matrix = np.asarray([design_vector(row) for row in rows], dtype=float)
    target = np.asarray([1 if outcome else 0 for outcome in outcomes], dtype=int)

    booster = XGBClassifier(**spec.resolved())
    booster.fit(matrix, target)
    return XGBChallenger(
        name=spec.name,
        booster=booster,
        index=index,
        columns=design_columns(index.feature_set),
    )


def make_challenger_fitter(
    spec: ChallengerSpec, index: FeatureIndex
) -> Callable[[Sequence[Label]], Baseline]:
    """Bind a spec and an index into the `extra_models` fitter signature."""

    def fit(labels: Sequence[Label]) -> Baseline:
        return fit_challenger(labels, spec=spec, index=index)

    return fit
