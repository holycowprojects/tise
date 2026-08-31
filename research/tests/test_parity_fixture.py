"""The parity fixture is frozen. This is what freezes it.

`parity_expected.json` is the oracle TypeScript is measured against at T9. If the Python
pipeline changes behaviour, this test fails **before** the fixture silently drifts — and
regenerating it becomes a deliberate act with a commit message, rather than a side effect
of someone running the generator.

That matters because the failure it guards against is asymmetric. A broken test is
noticed in seconds. A quietly regenerated oracle means every published benchmark
describes a model nobody shipped, and nothing ever tells you.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from tise_research.parity_fixture import (
    FIXTURE_DIR,
    build_events,
    build_expected_document,
    build_input_document,
)

EVENTS_PATH = FIXTURE_DIR / "parity_events.json"
EXPECTED_PATH = FIXTURE_DIR / "parity_expected.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class TestFixtureIsCommitted:
    def test_both_files_exist(self):
        assert EVENTS_PATH.exists(), "run python -m tise_research.parity_fixture"
        assert EXPECTED_PATH.exists(), "run python -m tise_research.parity_fixture"


@pytest.mark.parity
class TestFixtureIsFrozen:
    def test_regenerating_the_input_reproduces_the_committed_file(self):
        assert build_input_document() == _load(EVENTS_PATH)

    def test_regenerating_the_expected_output_reproduces_the_committed_file(self):
        """If this fails, the pipeline changed. Decide whether that was intended, then
        regenerate deliberately — never as a reflex to make the suite green."""
        assert build_expected_document() == _load(EXPECTED_PATH)


class TestFixtureCoversWhatItClaimsTo:
    """A fixture that misses the boundaries is worse than none: it certifies agreement
    on the easy cases and says nothing about the ones that actually differ."""

    def test_input_carries_no_categories(self):
        """Resolving the domain is part of what parity compares. Handing TypeScript the
        answer would make the comparison meaningless."""
        for event in _load(EVENTS_PATH)["events"]:
            assert "category" not in event

    def test_all_four_resolution_sources_are_exercised(self):
        sources = {entry["source"] for entry in _load(EXPECTED_PATH)["resolutions"]}
        assert sources == {"map", "rule", "override", "fallback"}

    def test_a_gap_of_exactly_the_timeout_does_not_split_a_session(self):
        """The `>` versus `>=` case. This is the single most likely place for the two
        implementations to disagree, and the least likely to show up in real history."""
        expected = _load(EXPECTED_PATH)
        first = expected["sessions"][0]
        assert len(first["eventIds"]) == 3, (
            "the 30-minute gap should have been absorbed into session 1"
        )

    def test_a_gap_one_second_over_the_timeout_does_split(self):
        expected = _load(EXPECTED_PATH)
        assert expected["sessions"][1]["startedAt"].endswith("10:20:01+00:00")

    def test_a_recurrence_lands_exactly_on_the_horizon(self):
        """Without this, `<=` and `<` are indistinguishable and both suites stay green.

        Found at T11 by flipping the boundary in the TypeScript mirror and watching 227
        tests pass. The fixture header had always claimed to cover a recurrence inside the
        horizon and one outside it, and it did — but never one *on* it.
        """
        expected = _load(EXPECTED_PATH)
        horizon = timedelta(hours=expected["horizonHours"])

        # Rebuilt from the pipeline rather than read back out of the oracle, so this
        # asserts a property of the data and not of what was written down.
        moments: dict[str, list[datetime]] = {}
        for event in build_events():
            moments.setdefault(event.category, []).append(event.occurred_at)
        for instants in moments.values():
            instants.sort()

        on_boundary = 0
        for label in expected["labels"]:
            window_end = datetime.fromisoformat(label["windowEnd"])
            after = [m for m in moments[label["subject"]] if m > window_end]
            if after and after[0] == window_end + horizon:
                on_boundary += 1
                assert label["outcome"] is True, (
                    "a recurrence exactly on the horizon is inside it"
                )
        assert on_boundary >= 1, "the horizon boundary is not exercised by any label"

    def test_both_outcomes_appear(self):
        outcomes = {label["outcome"] for label in _load(EXPECTED_PATH)["labels"]}
        assert outcomes == {True, False}, "a fixture with one outcome tests half the code"

    def test_unknown_survives_as_a_category(self):
        subjects = {label["subject"] for label in _load(EXPECTED_PATH)["labels"]}
        assert "unknown" in subjects

    def test_a_session_holds_several_categories(self):
        assert any(
            len(session["categories"]) > 1
            for session in _load(EXPECTED_PATH)["sessions"]
        )

    def test_the_transitions_section_reaches_the_cases_it_exists_for(self):
        """A fixture that only ever changes topic inside one session tests half of it.

        `withinSession` would then be a constant on both sides, and the TypeScript mirror
        could compute it any way at all and still agree.
        """
        section = _load(EXPECTED_PATH)["transitions"]
        transitions = section["transitions"]
        assert transitions, "no category changes to compare"

        flags = {item["withinSession"] for item in transitions}
        assert flags == {True, False}, "needs a change inside a session and across one"

        assert any(item["previousCategory"] is None for item in transitions), (
            "the start of the stream, where there is no previous run, is not exercised"
        )
        assert any(item["previousCategory"] is not None for item in transitions)
        assert any(item["fromRunEvents"] > 1 for item in transitions), (
            "every run is one event long, so run-collapsing is never actually tested"
        )

    def test_a_change_never_lands_on_the_category_it_left(self):
        """The invariant the whole label definition rests on (D94, D102).

        Runs are maximal, so `from` and `to` cannot match. If they ever do, the collapse
        is broken and every count built on it is wrong by an unknown amount.
        """
        for item in _load(EXPECTED_PATH)["transitions"]["transitions"]:
            assert item["fromCategory"] != item["toCategory"], item["transitionId"]

    def test_the_cost_of_the_change_rule_is_recorded(self):
        """Boundaries the collapse absorbed. Reported so the rule can be argued with."""
        assert _load(EXPECTED_PATH)["transitions"]["boundariesWithoutChange"] >= 0


class TestFixtureIsSynthetic:
    """SPEC.md permits synthetic data as a fixture and forbids it as a benchmark.

    It is also the only safe choice for a committed file: real events would publish
    someone's browsing, and real history almost never contains the exact boundaries this
    fixture depends on.
    """

    def test_domains_are_example_or_well_known_only(self):
        allowed_suffixes = (".example", ".gov.in")
        well_known = {"youtube.com", "google.com", "github.com"}
        for event in _load(EVENTS_PATH)["events"]:
            domain = event["domain"]
            assert domain in well_known or domain.endswith(allowed_suffixes), domain

    def test_summary_matches_the_body(self):
        expected = _load(EXPECTED_PATH)
        summary = expected["summary"]
        assert summary["sessionCount"] == len(expected["sessions"])
        assert summary["labelCount"] == len(expected["labels"])
        assert summary["positiveCount"] == sum(
            1 for label in expected["labels"] if label["outcome"]
        )


@pytest.mark.parity
class TestTheModelSectionIsWorthTrusting:
    """A fixture that never exercises a code path cannot catch a bug in it.

    The T10 lesson applies here in full: an assertion that reads a value out of the oracle
    and compares it to itself proves that Python wrote what Python wrote. Every assertion
    below is computed from something else, or is a property the value must satisfy.
    """

    def setup_method(self) -> None:
        self.model = _load(EXPECTED_PATH)["model"]

    def test_the_matrix_is_shaped_like_the_features_it_came_from(self):
        expected = _load(EXPECTED_PATH)
        assert len(self.model["matrix"]) == len(expected["features"])
        assert len(self.model["outcomes"]) == len(expected["labels"])
        for row in self.model["matrix"]:
            assert len(row) == len(self.model["designColumns"])

    def test_training_converged_rather_than_running_out_of_iterations(self):
        """An unconverged fit is not wrong in any way a score reveals, only worse."""
        assert self.model["logreg"]["gradientNorm"] < 1e-8
        assert self.model["logreg"]["iterationsDone"] == self.model["spec"]["iterations"]

    def test_the_step_is_below_the_divergence_threshold_for_this_matrix(self):
        """Recomputed here from the matrix, not read back from the oracle."""
        matrix = self.model["matrix"]
        n = len(matrix)
        bound = (
            sum(1.0 + sum(value * value for value in row) for row in matrix) / (4 * n)
            + self.model["spec"]["l2"] / n
        )
        assert 0.0 < self.model["stepSize"] < 2.0 / bound

    def test_the_column_that_never_varies_gets_a_weight_of_exactly_zero(self):
        """`categoryShare30d` is never absent, so its indicator carries no information.

        The preprocessor turns a zero-variance column into zeros, and a zero column has
        zero gradient, so its weight can never leave the origin. Asserted because the
        alternative — a tiny non-zero coefficient on a column with no information — is
        what happens if the zero-variance guard is dropped.
        """
        columns = self.model["designColumns"]
        weights = self.model["logreg"]["weights"]
        constant = [
            name
            for index, name in enumerate(columns)
            if len({row[index] for row in self.model["matrix"]}) == 1
        ]
        assert constant == ["categoryShare30d__missing"]
        assert weights[columns.index("categoryShare30d__missing")] == 0.0

    def test_predictions_are_probabilities_and_are_not_all_the_same(self):
        predictions = self.model["predictions"]
        assert all(0.0 < value < 1.0 for value in predictions)
        assert len(set(predictions)) > 1, "a constant predictor proves nothing"

    def test_the_transition_table_has_something_to_transition_between(self):
        transition = self.model["transition"]
        assert len(transition["vocabulary"]) >= 2
        assert len(transition["primaries"]) == len(_load(EXPECTED_PATH)["sessions"])

    def test_every_distribution_sums_to_one(self):
        for name, distribution in self.model["transition"]["distributions"].items():
            assert sum(distribution.values()) == pytest.approx(1.0), name
        unseen = self.model["transition"]["unseenDistribution"]
        assert sum(unseen.values()) == pytest.approx(1.0)

    def test_smoothing_keeps_every_row_short_of_certainty(self):
        """The D26 problem: a row built on two observations must not claim 100%."""
        for name, distribution in self.model["transition"]["distributions"].items():
            assert max(distribution.values()) < 1.0, name
