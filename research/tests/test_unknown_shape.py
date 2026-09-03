"""The `unknown` shape measurement.

The assertion that matters most here is not arithmetic: **`report()` must never emit a domain
name.** It is the only defence that survives someone pasting the output into an issue, a
commit message or a benchmark file, and the head of this particular list is institutional by
design (D26) — a person's employer, school or bank. A script that prints aggregates *except
when it happens to print the top one* is the same failure as an allow-list of screenshots.

`local_ranking()` is the single exception and it writes only to `data/`, which is gitignored.
It is tested for the opposite property.
"""

from __future__ import annotations

import collections
from datetime import UTC, datetime, timedelta

from tise_research.data.load import AttentionSpan, TiseExport
from tise_research.features.events import Event

from analysis.unknown_shape import (
    DEPTHS,
    concentration,
    counterfactual,
    local_ranking,
    report,
    session_spread,
)

START = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
SECRET = "my-employer-intranet.example"


def _event(index: int, *, domain: str, category: str, minutes: float) -> Event:
    return Event(
        event_id=f"e{index}",
        occurred_at=START + timedelta(minutes=minutes),
        source="live",
        domain=domain,
        category=category,
        transition="link",
        dwell_seconds=None,
    )


def _span(index: int, seconds: float = 40.0) -> AttentionSpan:
    return AttentionSpan(
        span_id=f"sp{index}",
        event_id=f"e{index}",
        started_at=START,
        ended_at=START + timedelta(seconds=seconds),
        active_seconds=seconds,
        end_reason="navigated",
    )


def _export(events, spans=()) -> TiseExport:
    return TiseExport(
        exported_at=START,
        extension_version="0.1.0",
        category_map_version=1,
        suffix_list_version=1,
        session_timeout_seconds=1800.0,
        raw_retention_days=30,
        overrides={},
        events=tuple(events),
        attention=tuple(spans),
    )


def _profile() -> tuple[list[Event], list[AttentionSpan]]:
    """A head-plus-tail profile: one dominant unknown domain, a long thin tail, and a
    named category with enough history to be a plausible host."""
    events: list[Event] = []
    spans: list[AttentionSpan] = []
    index = 0
    for step in range(40):
        events.append(_event(index, domain=SECRET, category="unknown", minutes=step))
        spans.append(_span(index))
        index += 1
    for tail in range(15):
        events.append(
            _event(index, domain=f"tail{tail}.example", category="unknown", minutes=200 + tail)
        )
        index += 1
    for step in range(20):
        events.append(_event(index, domain="news.example", category="news", minutes=400 + step))
        spans.append(_span(index))
        index += 1
    return events, spans


class TestNoDomainEverReachesTheReport:
    def test_the_aggregate_report_names_nothing(self):
        events, spans = _profile()
        text = report(_export(events, spans))

        assert SECRET not in text
        assert "tail0.example" not in text
        assert "news.example" not in text
        # And it is not empty output that trivially satisfies the above.
        assert "unknown" in text and "%" in text

    def test_the_local_ranking_does_name_them_because_that_is_its_job(self):
        events, spans = _profile()
        listing = local_ranking(_export(events, spans))

        assert SECRET in listing
        assert "LOCAL ONLY" in listing
        assert "Never published" in listing


class TestConcentration:
    def test_it_measures_mass_and_not_domain_count(self):
        # The distinction D89 missed: one domain is most of the events, most domains are
        # seen once, and both are true at the same time.
        counts = collections.Counter({"head": 900} | {f"t{i}": 1 for i in range(99)})
        shape = concentration(counts)

        assert shape["events"] == 999
        assert shape["domains"] == 100
        assert shape["share"][1] > 0.9
        assert shape["seen_once"] == 99

    def test_shares_are_cumulative_and_reach_one(self):
        counts = collections.Counter({f"d{i}": 1 for i in range(20)})
        share = concentration(counts)["share"]
        values = [share[d] for d in DEPTHS]
        assert values == sorted(values)
        assert share[20] == 1.0

    def test_an_empty_bucket_does_not_divide_by_zero(self):
        assert concentration(collections.Counter())["events"] == 0


class TestSessionSpread:
    def test_it_counts_sessions_and_not_visits(self):
        # Forty visits to one domain inside a single sitting is one session, not forty.
        events, _ = _profile()
        spread = session_spread(events)
        assert spread[2] == 0
        assert spread[3] == 0


class TestCounterfactual:
    def test_the_head_is_chosen_by_event_mass(self):
        events, spans = _profile()
        result = counterfactual(_export(events, spans), prompts=1)
        # The dominant domain, not one of the fifteen tail entries.
        assert result["head_events"] == 40

    def test_merging_into_an_established_category_yields_at_least_as_many_labels(self):
        events, spans = _profile()
        result = counterfactual(_export(events, spans), prompts=1)
        _, merged_named, _, _ = result["merged"]
        _, separate_named, _, _ = result["separate"]
        # A new category starts behind the ten-prior-visit rule; an established one does not.
        assert merged_named >= separate_named

    def test_naming_the_head_never_reduces_named_labels_below_today(self):
        events, spans = _profile()
        result = counterfactual(_export(events, spans), prompts=1)
        _, today_named, _, _ = result["today"]
        _, merged_named, _, _ = result["merged"]
        assert merged_named >= today_named
