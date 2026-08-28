"""Calibrate `return_24h`, choose an abstention threshold, and report both.

    uv run python -m tise_research.eval.calibrate --model logreg

Writes `docs/benchmarks/calibration.md`. Every number in it comes from here.

**The whole point of this module is the split.** Each fold's training window is cut
chronologically into a *fit* part and a *calibration* part:

```
|<------------- fold.train ------------->|<-- fold.test -->|
|<---- fit ---->|<---- calibration ----->|
```

The model is fitted on the first part only. Platt scaling and the abstention threshold are
derived from the model's predictions on the second part — data the model has never seen —
and both are then applied, frozen, to the test window.

Fitting the calibrator on the model's own training rows is the standard way to get this
wrong, and it does not look wrong. The model is over-confident *on data it memorised*, so
a calibrator fitted there learns to undo memorisation rather than error, and the resulting
probabilities are confidently mis-stated on everything new. There is no error message; the
reliability curve just looks better than the model deserves.

**The model here is weaker than the one in `model.md`, on purpose.** It trains on ~70% of
each training window instead of all of it, because the rest is spent on calibration. That
is the real cost of calibration on a small dataset and it is reported rather than hidden:
the raw column in the tables below is this weaker model, so raw-versus-calibrated is a
like-for-like comparison and neither is compared against T11's numbers.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from tise_research.data.chrome_history import DEFAULT_VIEW
from tise_research.eval.abstain import (
    DEFAULT_TARGET_ACCURACY,
    AbstentionPolicy,
    accuracy_coverage_curve,
    select_threshold,
)
from tise_research.eval.backtest import EXCLUDED_FROM_HEADLINE, rolling_origin_folds
from tise_research.eval.calibration import (
    DEFAULT_BINS,
    ReliabilityBin,
    expected_calibration_error,
    maximum_calibration_error,
    reliability_curve,
)
from tise_research.eval.metrics import brier_score, log_loss
from tise_research.features.labels import DEFAULT_HORIZON_HOURS, Label
from tise_research.models.calibrate import Calibrator, apply_calibration, fit_platt
from tise_research.models.return_model import FeatureIndex, fit_return_model

__all__ = [
    "CALIBRATION_FRACTION",
    "CalibratedFold",
    "CalibrationResult",
    "run_calibrated_backtest",
    "split_for_calibration",
]

#: Share of each training window handed to the calibrator. 0.3 is a declared choice, not a
#: tuned one: too small and the two Platt parameters are fitted on noise, too large and the
#: model itself is starved. It is stated here so that if it is ever changed, the change is
#: visible rather than absorbed into a better-looking number.
CALIBRATION_FRACTION = 0.3

#: Below this many calibration rows, calibrating does more harm than leaving the raw
#: numbers alone — two parameters on a dozen points is fitting noise.
MIN_CALIBRATION_ROWS = 30


def _on_test(
    chosen: AbstentionPolicy | None,
    outcomes: Sequence[bool],
    probabilities: Sequence[float],
) -> tuple[float | None, float | None]:
    """What a chosen threshold actually achieved on the test window.

    This is the only number that says whether the threshold generalised. The accuracy it
    was selected on is a property of the calibration slice; this is a property of the
    future, which is the thing being promised.
    """
    if chosen is None or not chosen.target_met:
        return None, None
    point = accuracy_coverage_curve(
        outcomes, probabilities, thresholds=[chosen.threshold]
    )[0]
    return point.accuracy, point.coverage


def split_for_calibration(
    train: Sequence[Label], *, fraction: float = CALIBRATION_FRACTION
) -> tuple[list[Label], list[Label]]:
    """Cut a training window chronologically into (fit, calibration).

    Chronological, never random: a random split would put a label from Tuesday in the fit
    part and its neighbour from the same session in the calibration part, and the
    calibrator would be measuring the model on data it effectively already saw.
    """
    ordered = sorted(train, key=lambda label: (label.window_end, label.subject))
    cut = int(len(ordered) * (1.0 - fraction))
    return ordered[:cut], ordered[cut:]


@dataclass(frozen=True, slots=True)
class CalibratedFold:
    index: int
    n_fit: int
    n_calibration: int
    n_test: int
    raw_brier: float | None
    calibrated_brier: float | None
    raw_log_loss: float | None
    calibrated_log_loss: float | None
    raw_ece: float | None
    calibrated_ece: float | None
    calibrator: Calibrator
    policy: AbstentionPolicy | None
    #: Accuracy and coverage the policy actually achieved on the **test** window, which is
    #: the only number that says whether the threshold generalised.
    test_accuracy: float | None
    test_coverage: float | None
    #: What the naive point-estimate rule would have chosen, and how it would have fared.
    #: Reported rather than used, so the cost of the correction is visible.
    naive_policy: AbstentionPolicy | None
    naive_test_accuracy: float | None
    naive_test_coverage: float | None


@dataclass(frozen=True, slots=True)
class CalibrationResult:
    corpus: str
    label_count: int
    folds: tuple[CalibratedFold, ...]
    #: Pooled over every fold's test predictions, `unknown` excluded (D27).
    raw_brier: float | None
    calibrated_brier: float | None
    raw_ece: float | None
    calibrated_ece: float | None
    raw_mce: float | None
    calibrated_mce: float | None
    reliability_raw: tuple[ReliabilityBin, ...]
    reliability_calibrated: tuple[ReliabilityBin, ...]
    coverage_curve: tuple
    target_accuracy: float
    bins: int


def run_calibrated_backtest(
    corpus: str,
    labels: Sequence[Label],
    index: FeatureIndex,
    *,
    n_folds: int = 5,
    target_accuracy: float = DEFAULT_TARGET_ACCURACY,
    bins: int = DEFAULT_BINS,
) -> CalibrationResult:
    """Fit, calibrate and score every fold, keeping the three windows strictly apart."""
    folds: list[CalibratedFold] = []
    pooled_outcomes: list[bool] = []
    pooled_raw: list[float] = []
    pooled_calibrated: list[float] = []

    for fold in rolling_origin_folds(labels, n_folds=n_folds):
        fit_labels, calibration_labels = split_for_calibration(fold.train)
        if not fit_labels or not calibration_labels:
            continue

        model = fit_return_model(fit_labels, index=index)

        calibration_raw = [model.predict(label) for label in calibration_labels]
        calibration_outcomes = [label.outcome for label in calibration_labels]
        calibrator = (
            fit_platt(calibration_raw, calibration_outcomes)
            if len(calibration_labels) >= MIN_CALIBRATION_ROWS
            else fit_platt([], [])
        )

        # The threshold is chosen on *calibrated* probabilities, because that is what it
        # will be applied to. Choosing it on raw scores and applying it to calibrated ones
        # would be thresholding a different quantity from the one that was measured.
        calibration_calibrated = [
            apply_calibration(calibrator, p) for p in calibration_raw
        ]
        policy = select_threshold(
            calibration_outcomes,
            calibration_calibrated,
            target_accuracy=target_accuracy,
        )
        naive_policy = select_threshold(
            calibration_outcomes,
            calibration_calibrated,
            target_accuracy=target_accuracy,
            confidence_z=0.0,
        )

        test = [
            label for label in fold.test if label.subject != EXCLUDED_FROM_HEADLINE
        ]
        if not test:
            continue
        outcomes = [label.outcome for label in test]
        raw = [model.predict(label) for label in test]
        calibrated = [apply_calibration(calibrator, p) for p in raw]

        test_accuracy, test_coverage = _on_test(policy, outcomes, calibrated)
        naive_accuracy, naive_coverage = _on_test(naive_policy, outcomes, calibrated)

        folds.append(
            CalibratedFold(
                index=fold.index,
                n_fit=len(fit_labels),
                n_calibration=len(calibration_labels),
                n_test=len(test),
                raw_brier=brier_score(outcomes, raw),
                calibrated_brier=brier_score(outcomes, calibrated),
                raw_log_loss=log_loss(outcomes, raw),
                calibrated_log_loss=log_loss(outcomes, calibrated),
                raw_ece=expected_calibration_error(outcomes, raw, bins=bins),
                calibrated_ece=expected_calibration_error(
                    outcomes, calibrated, bins=bins
                ),
                calibrator=calibrator,
                policy=policy,
                test_accuracy=test_accuracy,
                test_coverage=test_coverage,
                naive_policy=naive_policy,
                naive_test_accuracy=naive_accuracy,
                naive_test_coverage=naive_coverage,
            )
        )
        pooled_outcomes.extend(outcomes)
        pooled_raw.extend(raw)
        pooled_calibrated.extend(calibrated)

    return CalibrationResult(
        corpus=corpus,
        label_count=len(labels),
        folds=tuple(folds),
        raw_brier=brier_score(pooled_outcomes, pooled_raw),
        calibrated_brier=brier_score(pooled_outcomes, pooled_calibrated),
        raw_ece=expected_calibration_error(pooled_outcomes, pooled_raw, bins=bins),
        calibrated_ece=expected_calibration_error(
            pooled_outcomes, pooled_calibrated, bins=bins
        ),
        raw_mce=maximum_calibration_error(pooled_outcomes, pooled_raw, bins=bins),
        calibrated_mce=maximum_calibration_error(
            pooled_outcomes, pooled_calibrated, bins=bins
        ),
        reliability_raw=tuple(reliability_curve(pooled_outcomes, pooled_raw, bins=bins)),
        reliability_calibrated=tuple(
            reliability_curve(pooled_outcomes, pooled_calibrated, bins=bins)
        ),
        coverage_curve=tuple(
            accuracy_coverage_curve(pooled_outcomes, pooled_calibrated)
        ),
        target_accuracy=target_accuracy,
        bins=bins,
    )


def main() -> int:
    from tise_research.data.corpus import load_events, load_labels
    from tise_research.eval.calibration_report import write_calibration_report

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="logreg", choices=["logreg"])
    parser.add_argument("--corpus", type=Path, default=None)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--timeout-seconds", type=float, default=1800.0)
    parser.add_argument("--target-accuracy", type=float, default=DEFAULT_TARGET_ACCURACY)
    parser.add_argument("--out", type=Path, default=Path("docs/benchmarks"))
    parser.add_argument(
        "--view",
        default=DEFAULT_VIEW,
        choices=["shipped", "chosen", "raw"],
        help="Which corpus (D78). `chosen` reproduces the superseded pre-D78 numbers.",
    )
    args = parser.parse_args()

    copies = [args.corpus] if args.corpus else sorted(Path("data").glob("history-*.copy"))
    if not copies:
        print("No corpus found. Run analysis/history_shape.py first.")
        return 1

    results = []
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
        result = run_calibrated_backtest(
            copy_path.stem,
            labels,
            index,
            n_folds=args.folds,
            target_accuracy=args.target_accuracy,
        )
        results.append(result)
        print(
            f"{copy_path.stem}: {len(labels):,} labels, "
            f"ECE {result.raw_ece:.4f} -> {result.calibrated_ece:.4f}"
        )

    if not results:
        print("No corpus had enough labels.")
        return 1

    path = write_calibration_report(
        results, out_dir=args.out, timeout_seconds=args.timeout_seconds
    )
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
