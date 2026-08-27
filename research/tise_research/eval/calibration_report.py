"""Render `docs/benchmarks/calibration.md`. Nothing in it is typed by hand.

The reliability curve is drawn as a text table rather than a plot, for the same reason
every other report here is Markdown: a number in a committed file can be diffed, and an
image cannot. Bin populations sit next to every point, because on a few hundred labels the
low bins can hold three predictions and an ECE that averages those against a bin of two
hundred is arithmetic rather than measurement.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from tise_research.eval.abstain import DEFAULT_THRESHOLDS, wilson_lower_bound
from tise_research.eval.calibrate import CALIBRATION_FRACTION, CalibrationResult
from tise_research.models.calibrate import CALIBRATION_METHOD, CALIBRATION_VERSION

__all__ = ["write_calibration_report"]


def _f(value: float | None, places: int = 4) -> str:
    return "n/a" if value is None else f"{value:.{places}f}"


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def _reliability_table(result: CalibrationResult) -> str:
    rows = [
        "| Bin | n | Predicted (raw) | Observed | Predicted (calibrated) | Observed |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for raw, cal in zip(
        result.reliability_raw, result.reliability_calibrated, strict=True
    ):
        if raw.count == 0 and cal.count == 0:
            rows.append(
                f"| {raw.low:.1f}–{raw.high:.1f} | 0 | — | — | — | — |"
            )
            continue
        rows.append(
            f"| {raw.low:.1f}–{raw.high:.1f} | {raw.count} | "
            f"{_f(raw.mean_predicted, 3)} | {_f(raw.observed_rate, 3)} | "
            f"{_f(cal.mean_predicted, 3)} | {_f(cal.observed_rate, 3)} |"
        )
    return "\n".join(rows)


def _fold_table(result: CalibrationResult) -> str:
    rows = [
        "| Fold | Fit | Calib | Test | Brier raw | Brier cal | ECE raw | ECE cal | "
        "Platt `a` | Threshold | Test acc | Test cov | Naive thr | Naive acc |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for fold in result.folds:
        policy = fold.policy
        threshold = (
            f"{policy.threshold:.2f}" if policy and policy.target_met else "**none**"
        )
        naive = fold.naive_policy
        naive_threshold = (
            f"{naive.threshold:.2f}" if naive and naive.target_met else "none"
        )
        rows.append(
            f"| {fold.index} | {fold.n_fit} | {fold.n_calibration} | {fold.n_test} | "
            f"{_f(fold.raw_brier)} | {_f(fold.calibrated_brier)} | "
            f"{_f(fold.raw_ece)} | {_f(fold.calibrated_ece)} | "
            f"{fold.calibrator.a:.3f} | {threshold} | "
            f"{_pct(fold.test_accuracy)} | {_pct(fold.test_coverage)} | "
            f"{naive_threshold} | {_pct(fold.naive_test_accuracy)} |"
        )
    return "\n".join(rows)


def _coverage_table(result: CalibrationResult) -> str:
    rows = [
        "| Threshold | Coverage | Answered | Accuracy answered | Accuracy abstained |",
        "|---:|---:|---:|---:|---:|",
    ]
    wanted = {0.50, 0.60, 0.70, 0.80, 0.90, 0.95}
    for point in result.coverage_curve:
        if round(point.threshold, 2) not in wanted:
            continue
        rows.append(
            f"| {point.threshold:.2f} | {point.coverage:.1%} | {point.answered} | "
            f"{_pct(point.accuracy)} | {_pct(point.abstained_accuracy)} |"
        )
    return "\n".join(rows)


def _held(folds, target: float, strict: bool) -> tuple[int, int, list[float]]:
    """How often a rule's threshold kept its promise on the test window."""
    chosen = [
        f
        for f in folds
        if (f.policy if strict else f.naive_policy)
        and (f.policy if strict else f.naive_policy).target_met
    ]
    accuracies = [
        (f.test_accuracy if strict else f.naive_test_accuracy) for f in chosen
    ]
    coverages = [
        (f.test_coverage if strict else f.naive_test_coverage) for f in chosen
    ]
    kept = sum(1 for a in accuracies if a is not None and a >= target)
    return len(chosen), kept, [c for c in coverages if c is not None]


def _sample_size_note(result: CalibrationResult) -> str:
    """What it would take to certify the target, from the pooled curve.

    Reported as a diagnostic, never adopted. When no threshold qualifies, the useful
    question is whether the model is bad or the evidence is thin, and these two numbers
    separate them: a model that is comfortably above target certifies on a small sample,
    while one that is barely above needs an enormous one.
    """
    target = result.target_accuracy
    best = None
    for point in result.coverage_curve:
        if point.accuracy is None or point.answered < 20:
            continue
        if point.accuracy >= target and (best is None or point.coverage > best.coverage):
            best = point
    if best is None:
        return (
            f"No threshold reaches {target:.0%} even as a point estimate on the pooled "
            "test window, so this is the model falling short rather than the evidence "
            "being thin."
        )

    needed = None
    for candidate in (100, 200, 400, 800, 1600, 3200, 6400, 12800):
        if wilson_lower_bound(round(best.accuracy * candidate), candidate) >= target:
            needed = candidate
            break
    slices = [fold.n_calibration for fold in result.folds]
    span = f"{min(slices)}–{max(slices)}" if slices else "n/a"
    reach = f"about {needed:,}" if needed else "more than 12,800"

    return (
        f"Pooled, threshold {best.threshold:.2f} answers {best.coverage:.0%} of cases at "
        f"**{best.accuracy:.1%}** accuracy — above the {target:.0%} target as a point "
        f"estimate. Certifying that margin at 95% confidence would need **{reach} answered "
        f"rows**; calibration slices here hold {span}. "
        "So the shortfall is the width of the margin, not the model: a threshold that was "
        "comfortably above target would certify on a fraction of the data, while one a "
        "point above it needs an enormous sample to distinguish from luck."
    )


def _section(result: CalibrationResult) -> str:
    target = result.target_accuracy
    n_strict, kept_strict, cov_strict = _held(result.folds, target, strict=True)
    n_naive, kept_naive, cov_naive = _held(result.folds, target, strict=False)

    def phrase(n: int, kept: int, coverages: list[float], label: str) -> str:
        if n == 0:
            return f"{label}: no threshold qualified on any fold."
        span = (
            f", answering {min(coverages):.0%}–{max(coverages):.0%} of cases"
            if coverages
            else ""
        )
        return (
            f"{label}: qualified on **{n} of {len(result.folds)}** folds and held on the "
            f"test window in **{kept} of {n}**{span}."
        )

    if n_strict == 0 and n_naive == 0:
        verdict = (
            f"**No threshold reached {target:.0%} on any fold, under either rule.** The "
            "policy is to answer nothing. That is the honest outcome and not a bug: the "
            "promise the threshold exists to keep cannot be kept on this data."
        )
    else:
        verdict = "\n\n".join(
            (
                phrase(n_strict, kept_strict, cov_strict, "Shipped rule (lower bound)"),
                phrase(n_naive, kept_naive, cov_naive, "Naive rule (point estimate)"),
            )
        )

    ece_delta = (
        result.raw_ece - result.calibrated_ece
        if result.raw_ece is not None and result.calibrated_ece is not None
        else None
    )
    direction = (
        "improved" if ece_delta and ece_delta > 0 else "did not improve"
    )

    return f"""### {result.corpus}

{result.label_count:,} labels, {len(result.folds)} folds scored.

| | Raw | Calibrated |
|---|---:|---:|
| Brier | {_f(result.raw_brier)} | {_f(result.calibrated_brier)} |
| ECE ({result.bins} bins) | {_f(result.raw_ece)} | {_f(result.calibrated_ece)} |
| Worst bin (MCE) | {_f(result.raw_mce)} | {_f(result.calibrated_mce)} |

Calibration **{direction}** expected calibration error here.

{verdict}

{_sample_size_note(result)}

**Per fold.** `a` is the Platt slope: below 1 means the raw model was over-confident and
is being pulled toward the base rate; above 1 means it was under-confident.

{_fold_table(result)}

**Reliability**, pooled over every fold's test window, `unknown` excluded.

{_reliability_table(result)}

**Accuracy against coverage**, pooled, on calibrated probabilities.

{_coverage_table(result)}
"""


def write_calibration_report(
    results: Sequence[CalibrationResult], *, out_dir: Path, timeout_seconds: float
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "calibration.md"
    sections = "\n\n".join(_section(result) for result in results)
    target = results[0].target_accuracy if results else 0.0

    path.write_text(
        f"""# Calibration and abstention — `return_24h`

Generated by `tise_research.eval.calibration_report`. **Do not edit by hand.**

```
uv run python -m tise_research.eval.calibrate --model logreg
```

Session timeout {timeout_seconds:,.0f}s (D17), horizon 24h. Corpora measured separately
and never merged (D18). `unknown` excluded from every number (D27).

## What is being asked

A logistic regression already emits something in [0, 1], which is why calibration is easy
to skip. It is not the same thing as a probability. "0.8" is a probability only if, across
every occasion the model said 0.8, the thing happened about 80% of the time. A model can
have a respectable Brier score while being systematically over-confident, and **abstention
is meaningless until the number it thresholds is honest** — a threshold on a
mis-calibrated score is a threshold on nothing in particular.

Method: **{CALIBRATION_METHOD}** scaling, version `{CALIBRATION_VERSION}`. Two parameters
fitted on the logit scale, so `a = 1, b = 0` is exactly the identity. Isotonic regression
is the more flexible calibrator and the wrong one at these sample sizes — it would fit the
calibration set's noise and report it as confidence. It becomes the right answer at
roughly ten times the labels.

## The split, which is the whole exercise

```
|<------------- fold.train ------------->|<-- fold.test -->|
|<---- fit {1 - CALIBRATION_FRACTION:.0%} ---->|<-- calibration {CALIBRATION_FRACTION:.0%} -->|
```

The model is fitted on the first part. Platt scaling **and** the abstention threshold are
derived from the model's predictions on the second — data the model has never seen — then
frozen and applied to the test window.

Fitting the calibrator on the model's own training rows is the standard way to get this
wrong, and it does not look wrong. The model is over-confident on data it memorised, so a
calibrator fitted there learns to undo memorisation rather than error. There is no error
message; the reliability curve simply looks better than the model deserves.

**The model on this page is weaker than the one in `model.md`**, and deliberately so: it
trains on {1 - CALIBRATION_FRACTION:.0%} of each training window because the rest is spent
on calibration. That is the real price of calibrating a small dataset. The raw column
below is this weaker model, so raw-versus-calibrated is like-for-like — and neither column
should be compared against T11's numbers.

## Abstention

Confidence is `max(p, 1 - p)`: distance from the coin flip, so 0.05 and 0.95 are equally
confident. The target accuracy is **{target:.0%}**, a *declared* policy choice with the
same status as the 30-minute session timeout (D17) — stated in advance so that whether it
is reachable becomes a finding rather than a knob. With a base rate near 70%, answering
everything already scores about 0.70, so a lower target would be met by abstaining from
nothing.

Among thresholds meeting the target, the **lowest** wins: the point is to answer as much as
possible while keeping the promise. Picking the highest-accuracy threshold instead would
abstain from nearly everything and report a wonderful number about four predictions. A
threshold must answer at least 20 validation cases to qualify — 3 for 3 is 100% accuracy
and no evidence.

Thresholds tried run from {DEFAULT_THRESHOLDS[0]:.2f} to {DEFAULT_THRESHOLDS[-1]:.2f}.

{sections}

## Limitations

- **One person's browsing.** Every number describes the author.
- **No confidence intervals**, so a fold-to-fold difference of a few points is not
  evidence of anything. T16.
- **ECE depends on the bin count**, which is why it is stated everywhere it appears. It is
  not comparable across reports that binned differently.
- **Small bins.** With a base rate near 70% predictions crowd into the top bins, and the
  low ones can hold single figures. Populations are printed next to every point for
  exactly this reason.
- **The threshold is chosen per fold and reported per fold.** There is no single shipped
  threshold on this page; the extension derives its own the same way, from its own
  calibration slice, and stores it with the model.
""",
        encoding="utf-8",
    )
    return path
