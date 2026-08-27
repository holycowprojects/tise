"""Platt scaling, and the two things it must never do.

It must not invent a correction from a calibration set that contains no information, and
it must not learn the model's training set back. The first is testable here; the second is
structural and lives in `test_backtest.py`, because this module only ever sees numbers.
"""

from __future__ import annotations

import math

import pytest
from tise_research.eval.metrics import brier_score
from tise_research.models.calibrate import (
    CALIBRATION_METHOD,
    CALIBRATION_VERSION,
    apply_calibration,
    fit_platt,
    identity_calibrator,
    logit,
)


def sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def overconfident(rate: float, n: int) -> tuple[list[float], list[bool]]:
    """A model that says 0.95 when the truth is `rate`, and 0.05 when it is 1 - `rate`.

    Deliberately synthetic, and a unit test rather than a benchmark — the permitted use.
    """
    probabilities: list[float] = []
    outcomes: list[bool] = []
    for index in range(n):
        if index % 2 == 0:
            probabilities.append(0.95)
            outcomes.append((index // 2) % 10 < rate * 10)
        else:
            probabilities.append(0.05)
            outcomes.append((index // 2) % 10 < (1 - rate) * 10)
    return probabilities, outcomes


class TestLogit:
    def test_is_the_inverse_of_the_sigmoid(self) -> None:
        for probability in (0.1, 0.25, 0.5, 0.75, 0.9):
            assert sigmoid(logit(probability)) == pytest.approx(probability, abs=1e-12)

    def test_clamps_the_ends_instead_of_returning_infinity(self) -> None:
        """One raw 0 or 1 would otherwise dominate the fit or produce a NaN."""
        assert math.isfinite(logit(0.0))
        assert math.isfinite(logit(1.0))
        assert logit(0.0) < -18 and logit(1.0) > 18


class TestIdentity:
    def test_leaves_every_probability_alone(self) -> None:
        calibrator = identity_calibrator()
        for probability in (0.01, 0.3, 0.5, 0.77, 0.99):
            assert apply_calibration(calibrator, probability) == pytest.approx(
                probability, abs=1e-9
            )

    def test_is_recognisable_as_the_identity(self) -> None:
        """A prediction carrying it is visibly uncalibrated, which is its own claim."""
        assert identity_calibrator().is_identity

    def test_an_empty_calibration_set_gives_the_identity(self) -> None:
        assert fit_platt([], []).is_identity

    def test_one_class_only_gives_the_identity(self) -> None:
        """All-positive calibration data says nothing about where the model is wrong."""
        assert fit_platt([0.9, 0.8, 0.7], [True, True, True]).is_identity
        assert fit_platt([0.9, 0.8, 0.7], [False, False, False]).is_identity


class TestFitting:
    def test_pulls_an_overconfident_model_toward_the_base_rate(self) -> None:
        probabilities, outcomes = overconfident(0.7, 200)
        calibrator = fit_platt(probabilities, outcomes)
        # a < 1 shrinks the logits: the model's 0.95 becomes something less extreme.
        assert calibrator.a < 1.0
        assert apply_calibration(calibrator, 0.95) < 0.95
        assert apply_calibration(calibrator, 0.05) > 0.05

    def test_improves_the_brier_score_of_an_overconfident_model(self) -> None:
        """The point of the exercise, stated as a number rather than a shape."""
        probabilities, outcomes = overconfident(0.7, 200)
        before = brier_score(outcomes, probabilities)
        calibrator = fit_platt(probabilities, outcomes)
        after = brier_score(
            outcomes, [apply_calibration(calibrator, p) for p in probabilities]
        )
        assert before is not None and after is not None
        assert after < before

    def test_leaves_an_already_honest_model_close_to_the_identity(self) -> None:
        """A calibrator that learned "you were right" should look like it did nothing."""
        probabilities = [0.7] * 100 + [0.3] * 100
        outcomes = [i < 70 for i in range(100)] + [i < 30 for i in range(100)]
        calibrator = fit_platt(probabilities, outcomes)
        for probability in (0.3, 0.7):
            assert apply_calibration(calibrator, probability) == pytest.approx(
                probability, abs=0.05
            )

    def test_soft_targets_stop_a_small_set_being_separated_perfectly(self) -> None:
        """Hard 0/1 on six rows drives the fit toward certainty, which is the thing
        calibration removes. The targets are pulled in by one pseudo-count each."""
        probabilities = [0.6, 0.6, 0.6, 0.4, 0.4, 0.4]
        outcomes = [True, True, True, False, False, False]
        calibrator = fit_platt(probabilities, outcomes)
        calibrated = apply_calibration(calibrator, 0.6)
        assert calibrated < 0.95, "a six-row set must not produce near-certainty"

    def test_converges_rather_than_running_out_of_iterations(self) -> None:
        probabilities, outcomes = overconfident(0.7, 200)
        assert fit_platt(probabilities, outcomes).gradient_norm < 1e-6

    def test_records_the_method_the_version_and_what_it_saw(self) -> None:
        """A probability is only reproducible if you know what turned it into one."""
        probabilities, outcomes = overconfident(0.7, 50)
        calibrator = fit_platt(probabilities, outcomes)
        assert calibrator.method == CALIBRATION_METHOD
        assert calibrator.version == CALIBRATION_VERSION
        assert calibrator.n_calibration == 50
        assert 0 < calibrator.n_positive < 50

    def test_misaligned_input_raises(self) -> None:
        with pytest.raises(ValueError, match="aligned"):
            fit_platt([0.5, 0.6], [True])


class TestMonotonicity:
    def test_calibration_never_reorders_predictions(self) -> None:
        """Platt is monotone, so it changes what the numbers mean and not who is ahead.

        That matters for abstention: ranking is preserved, so the confidence ordering the
        threshold acts on is the same before and after.
        """
        probabilities, outcomes = overconfident(0.7, 100)
        calibrator = fit_platt(probabilities, outcomes)
        rising = [0.02, 0.1, 0.3, 0.5, 0.6, 0.85, 0.98]
        mapped = [apply_calibration(calibrator, p) for p in rising]
        assert mapped == sorted(mapped)

    def test_output_is_always_a_probability(self) -> None:
        probabilities, outcomes = overconfident(0.9, 100)
        calibrator = fit_platt(probabilities, outcomes)
        for probability in (0.0, 1e-12, 0.5, 1 - 1e-12, 1.0):
            value = apply_calibration(calibrator, probability)
            assert 0.0 <= value <= 1.0
            assert math.isfinite(value)
