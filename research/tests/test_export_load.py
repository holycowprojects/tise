"""The export loader, checked against the same fixture the extension is checked against.

`research/fixtures/export_v1.json` is the third shared-data contract in the project,
after `domains.json` and `domain_cases.json`. The extension asserts that its exporter
produces exactly this file; this module asserts that the loader reads it. Neither side
owns it, so a drift in either direction fails a suite instead of quietly producing a
corpus that is subtly not what shipped.

This is Checkpoint B in one file: browser → export → Python → events.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from tise_research.data.load import EXPORT_SCHEMA, load_export, parse_export
from tise_research.features.labels import return_24h_labels
from tise_research.features.sessions import sessionise

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "export_v1.json"
V2_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "export_v2.json"

_RAW = json.loads(FIXTURE.read_text(encoding="utf-8"))
_V2_RAW = json.loads(V2_FIXTURE.read_text(encoding="utf-8"))


def test_the_fixture_loads_without_transformation() -> None:
    """The plan's acceptance criterion, stated as an assertion."""
    export = load_export(FIXTURE)
    assert len(export.events) == 6


def test_metadata_survives_the_round_trip() -> None:
    export = load_export(FIXTURE)
    assert export.extension_version == "0.1.0"
    assert export.category_map_version == 1
    assert export.suffix_list_version == 1
    assert export.session_timeout_seconds == 1800
    assert export.raw_retention_days == 30
    assert export.overrides == {"youtube.com": "learning"}
    assert export.exported_at == datetime(2026, 8, 26, 12, 0, tzinfo=UTC)


def test_events_are_aware_and_ordered() -> None:
    export = load_export(FIXTURE)
    times = [event.occurred_at for event in export.events]
    assert times == sorted(times)
    for event in export.events:
        assert event.occurred_at.tzinfo is not None


def test_no_event_carries_a_dwell_time() -> None:
    """D35. An export cannot supply the `full` compat class and must not appear to."""
    export = load_export(FIXTURE)
    assert all(event.dwell_seconds is None for event in export.events)


def test_session_ids_are_not_carried_across() -> None:
    """D36: the research tier re-derives sessions and never compares ids.

    The `Event` dataclass has no `session_id` field at all, which is the strongest form
    of this rule — it is not possible to compare what does not exist.
    """
    export = load_export(FIXTURE)
    assert not hasattr(export.events[0], "session_id")


def test_the_loop_closes_all_the_way_to_labels() -> None:
    """The point of Checkpoint B: an export becomes a labelled dataset, unaided."""
    export = load_export(FIXTURE)
    sessions = sessionise(export.events, timeout_seconds=export.session_timeout_seconds)
    labels = return_24h_labels(export.events, timeout_seconds=export.session_timeout_seconds)

    session_ends = {session.ended_at for session in sessions}

    assert len(sessions) == 4
    assert labels, "an export that produces no labels has not closed the loop"
    for label in labels:
        assert label.target == "return_24h"
        assert label.window_end.tzinfo is not None
        # A label closes at the end of the session that produced it, never mid-session.
        assert label.window_end in session_ends


def test_an_unknown_schema_is_refused_rather_than_guessed() -> None:
    raw = dict(_RAW, schema="tise.export.v9")
    with pytest.raises(ValueError, match="unsupported export schema"):
        parse_export(raw)


def test_missing_keys_are_named() -> None:
    raw = {k: v for k, v in _RAW.items() if k != "events"}
    with pytest.raises(ValueError, match="missing required keys"):
        parse_export(raw)


def test_a_malformed_event_names_its_index() -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    del raw["events"][2]["domain"]
    with pytest.raises(ValueError, match="event 2 is malformed"):
        parse_export(raw)


def test_a_naive_timestamp_is_refused() -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw["events"][0]["occurredAt"] = "2026-08-24T09:00:00"
    with pytest.raises(ValueError, match="event 0 is malformed"):
        parse_export(raw)


def test_the_schema_string_is_pinned() -> None:
    assert EXPORT_SCHEMA == "tise.export.v2"
    assert _V2_RAW["schema"] == EXPORT_SCHEMA
    assert _RAW["schema"] == "tise.export.v1"


def test_the_fixture_holds_no_url() -> None:
    """The same assertion the extension makes, made again on the other side of the pipe."""
    text = FIXTURE.read_text(encoding="utf-8")
    assert "http://" not in text
    assert "https://" not in text
    assert "?" not in text


class TestBackwardCompatibility:
    """v1 is kept and still read. The promise is tested, not asserted.

    Someone who exported their browsing before the registry existed should not find the
    file unreadable because a later version added a key. The v1 fixture is therefore
    frozen — it is never regenerated — and this class is why.
    """

    def test_a_v1_export_still_loads(self) -> None:
        export = load_export(FIXTURE)
        assert export.schema == "tise.export.v1"
        assert len(export.events) == 6

    def test_a_v1_export_has_no_predictions_rather_than_failing(self) -> None:
        assert load_export(FIXTURE).predictions == ()


class TestPredictions:
    def setup_method(self) -> None:
        self.export = load_export(V2_FIXTURE)

    def test_every_prediction_survives_the_round_trip(self) -> None:
        assert len(self.export.predictions) == 4

    def test_every_outcome_is_exercised_by_the_fixture(self) -> None:
        """A fixture missing an outcome cannot catch a bug in handling it."""
        outcomes = {row.outcome for row in self.export.predictions}
        assert outcomes == {"pending", "hit", "miss", "expired"}

    def test_both_abstention_states_are_exercised(self) -> None:
        states = {row.abstained for row in self.export.predictions}
        assert states == {True, False}

    def test_abstained_predictions_are_present_at_all(self) -> None:
        """They are recorded precisely because they are not displayed."""
        assert any(row.abstained for row in self.export.predictions)

    def test_expired_is_not_scoreable_and_miss_is(self) -> None:
        """The one thing a reader of this record is most likely to get wrong.

        Counting `expired` as a negative would put a fabricated miss into the reliability
        curve — D52's mistake in a new place.
        """
        by_outcome = {row.outcome: row for row in self.export.predictions}
        assert by_outcome["miss"].scoreable is True
        assert by_outcome["hit"].scoreable is True
        assert by_outcome["expired"].scoreable is False
        assert by_outcome["pending"].scoreable is False

    def test_instants_are_aware(self) -> None:
        for row in self.export.predictions:
            assert row.created_at.tzinfo is not None
            assert row.window_start.tzinfo is not None
            assert row.window_end.tzinfo is not None

    def test_a_pending_prediction_has_no_resolution_instant(self) -> None:
        pending = next(r for r in self.export.predictions if r.outcome == "pending")
        assert pending.resolved_at is None

    def test_a_resolved_prediction_has_one(self) -> None:
        settled = [r for r in self.export.predictions if r.outcome != "pending"]
        assert settled and all(r.resolved_at is not None for r in settled)

    def test_the_data_cutoff_never_reaches_into_the_window(self) -> None:
        """A prediction that used data from inside its own window is not a prediction."""
        for row in self.export.predictions:
            assert row.data_cutoff == row.window_start

    def test_the_window_is_the_declared_horizon(self) -> None:
        for row in self.export.predictions:
            span = (row.window_end - row.window_start).total_seconds() / 3600
            assert span == 24.0

    def test_every_prediction_says_what_produced_it(self) -> None:
        """A stored prediction without its model is not reproducible."""
        for row in self.export.predictions:
            assert row.model_name
            assert row.model_version
            assert row.feature_set == "fs_2"

    def test_evidence_carries_no_url(self) -> None:
        for row in self.export.predictions:
            for line in row.evidence:
                assert "http" not in line
                assert "/" not in line

    def test_a_malformed_prediction_names_its_index(self) -> None:
        raw = json.loads(V2_FIXTURE.read_text(encoding="utf-8"))
        del raw["predictions"][1]["probability"]
        with pytest.raises(ValueError, match="prediction 1 is malformed"):
            parse_export(raw)

    def test_predictions_come_back_in_a_stable_order(self) -> None:
        starts = [
            (row.window_start, row.subject) for row in self.export.predictions
        ]
        assert starts == sorted(starts)


def test_the_v2_fixture_holds_no_url() -> None:
    text = V2_FIXTURE.read_text(encoding="utf-8")
    assert "http://" not in text
    assert "https://" not in text
    assert "?" not in text
