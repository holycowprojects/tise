"""The gate that decides whether `visit_engaged` may ship.

Untested logic behind a number in `DECISIONS.md` is the thing this repository is about, and
this script's output is going there. Two of its assertions matter more than the arithmetic:

* **The thresholds are D99's, and this checks that they still are.** They are reproduced as
  constants in `analysis/engagement_gate.py` rather than imported, because `replication.py`
  is a script and importing one script from another to share three integers is worse than
  the duplication. But a copy that can drift is a copy that will, and the whole argument for
  reusing D99's rule is that nobody chose it after seeing this profile's numbers. So the two
  are pinned together here, in the file that would otherwise let them separate.

* **Dwell-carrying visits are not all visits, and label-bearing sessions are not all
  sessions.** Both translations are stated in the script's docstring, and both are exactly
  the kind that go on meaning something plausible after they stop being right. On this
  profile the looser reading of each would pass a criterion the strict one fails.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from tise_research.data.load import AttentionSpan, TiseExport
from tise_research.features.events import Event

from analysis.engagement_gate import (
    MIN_LABELS,
    MIN_SESSIONS,
    MIN_VISITS,
    measure,
    report,
    verdicts,
)

START = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)


def _event(index: int, *, category: str, minutes: float, domain: str = "a.example") -> Event:
    return Event(
        event_id=f"e{index}",
        occurred_at=START + timedelta(minutes=minutes),
        source="live",
        domain=domain,
        category=category,
        transition="link",
        dwell_seconds=None,
    )


def _span(index: int, seconds: float) -> AttentionSpan:
    return AttentionSpan(
        span_id=f"sp{index}",
        event_id=f"e{index}",
        started_at=START,
        ended_at=START + timedelta(seconds=seconds),
        active_seconds=seconds,
        end_reason="navigated",
    )


def _export(events, spans, retention_days: int = 30) -> TiseExport:
    return TiseExport(
        exported_at=START,
        extension_version="0.1.0",
        category_map_version=1,
        suffix_list_version=1,
        session_timeout_seconds=1800.0,
        raw_retention_days=retention_days,
        overrides={},
        events=tuple(events),
        attention=tuple(spans),
    )


class TestTheThresholdsAreD99s:
    """If this fails, the gate stopped being the one nobody chose after the fact."""

    def test_they_match_the_replication_that_declared_them(self) -> None:
        replication = pytest.importorskip("analysis.replication")
        assert MIN_VISITS == replication.MIN_VISITS
        assert MIN_SESSIONS == replication.MIN_SESSIONS
        assert MIN_LABELS == replication.MIN_LABELS


class TestTheTranslationsThatCouldQuietlyMeanSomethingElse:
    def test_a_visit_with_no_span_is_not_a_dwell_carrying_visit(self) -> None:
        # Twenty visits, spans on four of them. The GESIS corpus had duration on every
        # visit, so there these two counts were the same number.
        events = [_event(i, category="news", minutes=i * 5) for i in range(20)]
        spans = [_span(i, 40.0) for i in range(4)]
        measured = measure(_export(events, spans))

        assert measured["events"] == 20
        assert measured["dwelled_visits"] == 4

    def test_a_session_holding_no_label_is_not_counted(self) -> None:
        # One long-running session of dwelled visits, and a second sitting hours later
        # whose visits carry no attention at all.
        dwelled = [_event(i, category="news", minutes=i * 5) for i in range(14)]
        quiet = [_event(100 + i, category="news", minutes=600 + i * 5) for i in range(5)]
        spans = [_span(i, 40.0) for i in range(14)]
        measured = measure(_export(dwelled + quiet, spans))

        assert measured["sessions_all"] == 2
        assert measured["sessions_with_labels"] == 1


class TestTheCounts:
    def test_a_category_produces_labels_only_after_ten_prior_dwelled_visits(self) -> None:
        events = [_event(i, category="news", minutes=i * 5) for i in range(14)]
        spans = [_span(i, 40.0) for i in range(14)]
        measured = measure(_export(events, spans))

        # Fourteen dwelled visits, the first ten of which are history for the rest.
        assert measured["dwelled_visits"] == 14
        assert measured["labels"] == 4

    def test_unknown_is_counted_but_held_out_of_the_named_total(self) -> None:
        events = [_event(i, category="news", minutes=i * 5) for i in range(14)]
        events += [
            _event(100 + i, category="unknown", minutes=1000 + i * 5) for i in range(14)
        ]
        spans = [_span(i, 40.0) for i in range(14)]
        spans += [_span(100 + i, 40.0) for i in range(14)]
        measured = measure(_export(events, spans))

        assert measured["labels"] == 8
        assert measured["labels_excluding_unknown"] == 4
        assert measured["by_category"]["unknown"] == 4

    def test_an_export_with_no_attention_measures_zero_rather_than_failing(self) -> None:
        events = [_event(i, category="news", minutes=i * 5) for i in range(20)]
        measured = measure(_export(events, []))

        assert measured["dwelled_visits"] == 0
        assert measured["labels"] == 0
        assert measured["visits_per_day"] == 0.0
        assert measured["largest_session_share"] == 0.0


class TestTheVerdict:
    def test_nothing_passes_on_an_empty_profile(self) -> None:
        measured = measure(_export([], []))
        assert all(observed < required for _, observed, required, _ in verdicts(measured))

    def test_the_report_says_so_out_loud(self) -> None:
        events = [_event(i, category="news", minutes=i * 5) for i in range(14)]
        spans = [_span(i, 40.0) for i in range(14)]
        text = report(measure(_export(events, spans)))

        assert "does not pass" in text
        # A failing gate has to say how far off it is, or it is a wall rather than a gate.
        # These fourteen visits arrive minutes apart, so the implied rate is enormous and
        # the window holds far more than the criterion: the reachable branch.
        assert "days to go" in text


class TestTheCeilingRatherThanACountdown:
    """D123: raw events expire, so the visit count is a window and not a running total.

    Dividing a shortfall by a rate assumes a total. Doing that on a profile whose window
    saturates below the bar prints a date that will never arrive, which is what this script
    did for eighteen days. Both branches are asserted because a ceiling check that cannot
    come back "reachable" has not been tested, it has been run.
    """

    def _profile(self, visits: int, over_days: float):
        """`visits` dwelled visits spread evenly across `over_days`."""
        events: list[Event] = []
        spans: list[AttentionSpan] = []
        step = over_days * 24 * 60 / max(1, visits - 1)
        for index in range(visits):
            events.append(_event(index, category="news", minutes=index * step))
            spans.append(_span(index, 40.0))
        return events, spans

    def test_a_rate_that_cannot_fill_the_window_refuses_to_print_a_date(self) -> None:
        # 20 visits/day against a 30-day window holds 600 — short of 1,000, forever.
        events, spans = self._profile(400, over_days=20.0)
        text = report(measure(_export(events, spans, retention_days=30)))

        assert "cannot hold" in text
        assert "at saturation" in text
        assert "days to go" not in text
        assert "short of the visit criterion" not in text

    def test_a_rate_that_does_fill_the_window_still_gets_its_countdown(self) -> None:
        # 100 visits/day against the same window holds 3,000, so a date is meaningful.
        events, spans = self._profile(400, over_days=4.0)
        text = report(measure(_export(events, spans, retention_days=30)))

        assert "days to go" in text
        assert "cannot hold" not in text

    def test_keeping_events_forever_makes_the_count_genuinely_cumulative(self) -> None:
        # Retention 0 is "keep forever" in settings, and only there is a shortfall over a
        # rate a real date rather than an assumption.
        events, spans = self._profile(400, over_days=20.0)
        text = report(measure(_export(events, spans, retention_days=0)))

        assert "short of the visit criterion" in text
        assert "cumulative" in text
        assert "cannot hold" not in text

    def test_the_loosest_reading_divides_by_its_own_span_and_not_the_dwell_span(self) -> None:
        """Imported history is wider than the dwell window, and mixing them inflates it.

        Written because the first version of this comparison did exactly that and printed a
        looser reading of 1,150 against a 1,000 bar — a pass, from an arithmetic mismatch,
        in the one line whose job is to show the verdict survives the loose reading.
        """
        # 400 dwelled visits over 20 days, plus imported history stretching 40 days back.
        events, spans = self._profile(400, over_days=20.0)
        imported = [
            Event(
                event_id=f"imp{i}",
                occurred_at=START - timedelta(days=40) + timedelta(hours=i),
                source="import",
                domain="a.example",
                category="news",
                transition="link",
                dwell_seconds=None,
            )
            for i in range(400)
        ]
        measured = measure(_export(imported + events, spans, retention_days=30))

        # The two spans are genuinely different, which is what makes the mistake possible.
        assert float(measured["stored_days"]) > float(measured["collection_days"])

        text = report(measured)
        loose = next(line for line in text.splitlines() if "every stored event" in line)
        # 800 events over ~60 stored days is ~13/day. Dividing by the 20-day dwell window
        # instead gives ~40/day, and the ceiling it implies clears the bar it is meant to
        # be tested against.
        assert "13.3/day" in loose
        assert "40.0/day" not in loose

    def test_the_ceiling_is_computed_from_retention_and_not_hardcoded(self) -> None:
        events, spans = self._profile(400, over_days=20.0)
        tight = report(measure(_export(events, spans, retention_days=30)))
        roomy = report(measure(_export(events, spans, retention_days=180)))

        assert "cannot hold" in tight
        # Same browsing, longer window: the same rate now reaches the bar.
        assert "cannot hold" not in roomy
        assert "180-day window" in roomy

    def test_a_profile_meeting_all_three_passes(self) -> None:
        # Enough visits, enough sittings, enough labels: sessions are split by putting a
        # gap wider than the 1800s timeout between them.
        events: list[Event] = []
        spans: list[AttentionSpan] = []
        index = 0
        for sitting in range(MIN_SESSIONS + 2):
            for step in range(60):
                minutes = sitting * 24 * 60 + step
                events.append(_event(index, category="news", minutes=minutes))
                spans.append(_span(index, 40.0))
                index += 1

        measured = measure(_export(events, spans))
        assert measured["dwelled_visits"] >= MIN_VISITS
        assert measured["sessions_with_labels"] >= MIN_SESSIONS
        assert measured["labels"] >= MIN_LABELS
        assert all(observed >= required for _, observed, required, _ in verdicts(measured))
        assert "PASSES" in report(measured)
