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
from pathlib import Path

import pytest
from tise_research.parity_fixture import (
    FIXTURE_DIR,
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
