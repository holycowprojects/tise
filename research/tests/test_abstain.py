"""Choosing when not to answer.

The failure this guards against is a threshold that looks excellent because it answers
four questions. Coverage travels with accuracy everywhere, and `min_answered` stops a
policy qualifying on a handful of cases.
"""

from __future__ import annotations

import random

import pytest
from tise_research.eval.abstain import (
    DEFAULT_CONFIDENCE_Z,
    DEFAULT_TARGET_ACCURACY,
    accuracy_coverage_curve,
    confidence,
    select_threshold,
    wilson_lower_bound,
)


def graded(n: int = 200) -> tuple[list[bool], list[float]]:
    """Confident predictions are usually right; uncertain ones are coin flips.

    Synthetic, and a unit test rather than a benchmark. The real accuracy-coverage curve
    for the shipped model is produced by `eval/calibrate.py` on real browsing.
    """
    outcomes: list[bool] = []
    probabilities: list[float] = []
    for index in range(n):
        if index % 2 == 0:
            probabilities.append(0.95)
            outcomes.append(index % 20 != 0)  # right 9 times in 10
        else:
            probabilities.append(0.55)
            outcomes.append(index % 4 == 1)  # right about half the time
    return outcomes, probabilities


class TestConfidence:
    def test_is_distance_from_the_coin_flip_not_the_probability(self) -> None:
        assert confidence(0.95) == pytest.approx(0.95)
        assert confidence(0.05) == pytest.approx(0.95)
        assert confidence(0.5) == pytest.approx(0.5)

    def test_is_never_below_a_half(self) -> None:
        for probability in (0.0, 0.2, 0.5, 0.8, 1.0):
            assert confidence(probability) >= 0.5


class TestCurve:
    def test_coverage_falls_as_the_threshold_rises(self) -> None:
        outcomes, probabilities = graded()
        curve = accuracy_coverage_curve(outcomes, probabilities)
        coverages = [point.coverage for point in curve]
        assert coverages == sorted(coverages, reverse=True)

    def test_the_lowest_threshold_answers_everything(self) -> None:
        outcomes, probabilities = graded()
        first = accuracy_coverage_curve(outcomes, probabilities)[0]
        assert first.threshold == pytest.approx(0.5)
        assert first.coverage == pytest.approx(1.0)
        assert first.answered == len(outcomes)

    def test_abstaining_raises_accuracy_on_what_is_left(self) -> None:
        """The whole premise. If this is not true, abstention is buying nothing."""
        outcomes, probabilities = graded()
        curve = accuracy_coverage_curve(outcomes, probabilities)
        answer_all = curve[0].accuracy
        strict = next(p for p in curve if p.threshold >= 0.9 and p.accuracy is not None)
        assert answer_all is not None and strict.accuracy is not None
        assert strict.accuracy > answer_all
        assert strict.coverage < 1.0

    def test_reports_how_good_the_abstained_cases_would_have_been(self) -> None:
        """A threshold that abstains from cases it would have got right is wasteful, and
        that is invisible unless it is measured."""
        outcomes, probabilities = graded()
        strict = next(
            p
            for p in accuracy_coverage_curve(outcomes, probabilities)
            if p.threshold >= 0.9
        )
        assert strict.abstained_accuracy is not None
        assert strict.abstained_accuracy < 0.75

    def test_a_threshold_answering_nothing_has_no_accuracy(self) -> None:
        """Not zero. Zero would mean it got everything wrong."""
        curve = accuracy_coverage_curve([True, False], [0.55, 0.45], thresholds=[0.99])
        assert curve[0].answered == 0
        assert curve[0].accuracy is None
        assert curve[0].coverage == 0.0

    def test_misaligned_input_raises(self) -> None:
        with pytest.raises(ValueError, match="outcomes"):
            accuracy_coverage_curve([True, False], [0.5])


class TestSelection:
    def test_picks_the_lowest_threshold_that_meets_the_target(self) -> None:
        """Lowest, not best: among thresholds that keep the promise, most coverage wins.

        Picking the highest-accuracy threshold instead would abstain from nearly
        everything and report a wonderful number about four predictions.
        """
        # z=0 isolates the "lowest" mechanic from the confidence bound.
        outcomes, probabilities = graded()
        policy = select_threshold(
            outcomes, probabilities, target_accuracy=0.85, confidence_z=0.0
        )
        assert policy is not None and policy.target_met
        assert policy.accuracy >= 0.85

        lower = accuracy_coverage_curve(
            outcomes,
            probabilities,
            thresholds=[round(policy.threshold - 0.01, 2)],
        )[0]
        assert lower.accuracy is None or lower.accuracy < 0.85

    def test_will_not_qualify_on_a_handful_of_cases(self) -> None:
        """3 for 3 is 100% accuracy and no evidence."""
        outcomes = [True, True, True] + [False] * 40
        probabilities = [0.99, 0.99, 0.99] + [0.55] * 40
        policy = select_threshold(
            outcomes, probabilities, target_accuracy=0.95, min_answered=20
        )
        assert policy is not None
        assert not policy.target_met, "three perfect cases must not set the threshold"

    def test_an_unreachable_target_is_a_finding_not_an_error(self) -> None:
        outcomes = [index % 2 == 0 for index in range(100)]
        probabilities = [0.51] * 100
        policy = select_threshold(outcomes, probabilities, target_accuracy=0.99)
        assert policy is not None
        assert not policy.target_met
        assert not policy.answers_anything

    def test_no_data_gives_no_policy(self) -> None:
        assert select_threshold([], []) is None

    def test_the_target_is_above_the_base_rate_it_would_otherwise_measure_nothing(
        self,
    ) -> None:
        """With a base rate near 70%, answering everything already scores about 0.70."""
        assert DEFAULT_TARGET_ACCURACY > 0.75

    def test_the_policy_carries_its_evidence(self) -> None:
        """A threshold quoted without its coverage is half a result."""
        outcomes, probabilities = graded()
        policy = select_threshold(
            outcomes, probabilities, target_accuracy=0.85, confidence_z=0.0
        )
        assert policy is not None
        assert policy.n_validation == len(outcomes)
        assert 0.0 < policy.coverage <= 1.0
        assert policy.target_accuracy == 0.85
        assert policy.confidence_z == 0.0


class TestConfidenceBound:
    """Why the threshold is chosen on a lower bound rather than the observed accuracy."""

    def test_z_of_zero_is_exactly_the_observed_proportion(self) -> None:
        """So the strict rule and the naive one differ by one parameter, and nothing else."""
        assert wilson_lower_bound(90, 100, z=0.0) == pytest.approx(0.9)
        assert wilson_lower_bound(1, 3, z=0.0) == pytest.approx(1 / 3)

    def test_the_bound_is_never_above_what_was_observed(self) -> None:
        for successes, total in ((90, 100), (18, 20), (450, 500), (1, 2)):
            assert wilson_lower_bound(successes, total) <= successes / total

    def test_the_bound_stays_a_probability_even_at_the_extremes(self) -> None:
        """Where the textbook normal approximation escapes [0, 1] and Wilson does not."""
        for successes, total in ((20, 20), (0, 20), (1, 1), (99, 100)):
            bound = wilson_lower_bound(successes, total)
            assert 0.0 <= bound <= 1.0

    def test_a_small_sample_is_punished_more_than_a_large_one(self) -> None:
        """90% of 20 is much weaker evidence than 90% of 500, and the bound says so."""
        small = wilson_lower_bound(18, 20)
        large = wilson_lower_bound(450, 500)
        assert small < large
        assert large < 0.9

    def test_no_data_bounds_to_zero_rather_than_dividing(self) -> None:
        assert wilson_lower_bound(0, 0) == 0.0

    def test_the_strict_rule_never_picks_a_lower_threshold_than_the_naive_one(self) -> None:
        outcomes, probabilities = graded()
        naive = select_threshold(
            outcomes, probabilities, target_accuracy=0.85, confidence_z=0.0
        )
        strict = select_threshold(outcomes, probabilities, target_accuracy=0.85)
        assert naive is not None and strict is not None
        if strict.target_met and naive.target_met:
            assert strict.threshold >= naive.threshold

    def test_the_bound_suppresses_a_skill_free_model_the_naive_rule_accepts(self) -> None:
        """The failure mode, reproduced.

        A model with no skill at all cannot truly reach 90% at any threshold. Taking the
        argmin over fifty noisy estimates finds one that clears the bar by luck often
        enough to matter, and the sampling error on ~100 rows does the rest. The bound
        prices both in.
        """
        rng = random.Random(0)
        naive_met = strict_met = 0
        trials = 200
        for _ in range(trials):
            probabilities = [rng.uniform(0.5, 1.0) for _ in range(100)]
            outcomes = [rng.random() < 0.7 for _ in range(100)]
            naive = select_threshold(
                outcomes, probabilities, target_accuracy=0.90, confidence_z=0.0
            )
            strict = select_threshold(outcomes, probabilities, target_accuracy=0.90)
            naive_met += bool(naive and naive.target_met)
            strict_met += bool(strict and strict.target_met)
        assert naive_met > 0, "the naive rule must actually exhibit the problem"
        assert strict_met < naive_met
        assert strict_met == 0

    def test_the_default_is_a_one_sided_ninety_five_percent_bound(self) -> None:
        assert pytest.approx(1.645) == DEFAULT_CONFIDENCE_Z
