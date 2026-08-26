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

_RAW = json.loads(FIXTURE.read_text(encoding="utf-8"))


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
    raw = dict(_RAW, schema="tise.export.v2")
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
    assert EXPORT_SCHEMA == "tise.export.v1"
    assert _RAW["schema"] == EXPORT_SCHEMA


def test_the_fixture_holds_no_url() -> None:
    """The same assertion the extension makes, made again on the other side of the pipe."""
    text = FIXTURE.read_text(encoding="utf-8")
    assert "http://" not in text
    assert "https://" not in text
    assert "?" not in text
