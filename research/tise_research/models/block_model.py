"""The `block_volume` model: `bs_1` rows in, a probability out (D91, T21).

Deliberately the *same* logistic regression, preprocessor and hand-written optimiser as
`return_24h` used. Only the target and the feature set are new. Changing the model class at
the same time as the target would make any difference in the result unattributable to
either, and D91 pre-registered a comparison against `category_base_rate`, not against a
different algorithm.

`ReturnModel` is not reused directly because it holds a `FeatureIndex` that recomputes rows
from events; block rows come from a single forward walk and cannot be recomputed from a
label alone. That difference is the leakage guarantee, so it is kept rather than smoothed
over.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from tise_research.features.block_labels import BLOCK_FEATURE_SET, BlockIndex
from tise_research.features.labels import Label
from tise_research.models.baselines import Baseline
from tise_research.models.logreg import (
    DEFAULT_SPEC,
    LogRegSpec,
    LogRegState,
    predict_proba,
    train,
)
from tise_research.models.prep import Preprocessor, design_columns, fit_preprocessor

__all__ = ["BLOCK_MODEL_NAME", "BlockModel", "fit_block_model", "make_block_model_fitter"]

BLOCK_MODEL_NAME = f"logreg_{BLOCK_FEATURE_SET.replace('_', '')}"


@dataclass(frozen=True, slots=True)
class BlockModel(Baseline):
    name: str
    preprocessor: Preprocessor
    state: LogRegState
    index: BlockIndex

    def predict(self, label: Label) -> float:
        return predict_proba(self.state, self.preprocessor.transform(self.index.row_for(label)))


def fit_block_model(
    labels: Sequence[Label],
    *,
    index: BlockIndex,
    spec: LogRegSpec = DEFAULT_SPEC,
) -> BlockModel:
    """Fit on one training window. Nothing at or after its end may be in `labels`."""
    rows = index.rows_for(labels)
    preprocessor = fit_preprocessor(rows)
    state = train(
        preprocessor.matrix(rows),
        [label.outcome for label in labels],
        spec=spec,
        n_columns=len(design_columns(BLOCK_FEATURE_SET)),
    )
    return BlockModel(
        name=BLOCK_MODEL_NAME, preprocessor=preprocessor, state=state, index=index
    )


def make_block_model_fitter(
    index: BlockIndex, *, spec: LogRegSpec = DEFAULT_SPEC
) -> Callable[[Sequence[Label]], Baseline]:
    def fit(labels: Sequence[Label]) -> Baseline:
        return fit_block_model(labels, index=index, spec=spec)

    return fit
