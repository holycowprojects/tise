"""Shape measurements: gaps, sessions, and the return_24h label estimate.

Every function here is pure. The label estimator carries the T1 gate, so its arithmetic
is asserted against hand-checked examples rather than a golden file.
"""

from datetime import UTC, datetime, timedelta

import pytest
from tise_research.data.shape import (
    ascii_histogram,
    estimate_return_24h_labels,
    find_gap_valley,
    inter_visit_gaps,
    percentiles,
    sessionise,
    visits_per_day,
)


def t(day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(2026, 6, day, hour, minute, tzinfo=UTC)


class TestInterVisitGaps:
    def test_gaps_in_seconds(self):
        times = [t(1, 10, 0), t(1, 10, 5), t(1, 11, 0)]
        assert inter_visit_gaps(times) == [300.0, 3300.0]

    def test_input_is_sorted_first(self):
        """Chrome's visits table is not guaranteed ordered. Negative gaps are a bug."""
        times = [t(1, 11, 0), t(1, 10, 0), t(1, 10, 5)]
        assert inter_visit_gaps(times) == [300.0, 3300.0]

    def test_fewer_than_two_visits_yields_no_gaps(self):
        assert inter_visit_gaps([]) == []
        assert inter_visit_gaps([t(1)]) == []


class TestPercentiles:
    def test_known_values(self):
        values = list(range(1, 101))  # 1..100
        result = percentiles(values, [50, 90])
        assert result[50] == pytest.approx(50.5, abs=1.0)
        assert result[90] == pytest.approx(90.5, abs=1.0)

    def test_empty_input_returns_none_not_zero(self):
        """Zero is a measurement. None is an absence. Never conflate them."""
        assert percentiles([], [50]) == {50: None}


class TestVisitsPerDay:
    def test_counts_by_calendar_day(self):
        times = [t(1, 9), t(1, 23), t(3, 1)]
        counts = visits_per_day(times)
        assert counts[t(1).date()] == 2
        assert counts[t(3).date()] == 1

    def test_days_with_no_visits_are_absent_not_zero(self):
        counts = visits_per_day([t(1), t(3)])
        assert t(2).date() not in counts


class TestSessionise:
    def test_splits_on_gap_exceeding_timeout(self):
        times = [t(1, 10, 0), t(1, 10, 20), t(1, 12, 0)]
        sessions = sessionise(times, timeout_seconds=1800)
        assert [len(s) for s in sessions] == [2, 1]

    def test_gap_exactly_at_timeout_stays_in_session(self):
        """Boundary is strictly greater than. Stated so the TS port cannot differ."""
        times = [t(1, 10, 0), t(1, 10, 30)]
        assert len(sessionise(times, timeout_seconds=1800)) == 1

    def test_one_second_over_timeout_splits(self):
        times = [t(1, 10, 0), t(1, 10, 30) + timedelta(seconds=1)]
        assert len(sessionise(times, timeout_seconds=1800)) == 2

    def test_empty_input(self):
        assert sessionise([], timeout_seconds=1800) == []


class TestFindGapValley:
    def test_finds_the_trough_between_two_modes(self):
        """Real browsing is bimodal: within-session seconds, between-session hours.
        The session timeout belongs in the trough, not at a round number we liked."""
        within = [8.0 + (i % 5) for i in range(400)]        # ~10s
        between = [20000.0 + (i % 500) for i in range(300)]  # ~6h
        valley = find_gap_valley(within + between)
        assert valley is not None
        assert 30.0 < valley < 5000.0

    def test_returns_none_when_unimodal(self):
        """No trough means no empirical boundary. Say so rather than inventing one."""
        assert find_gap_valley([10.0 + (i % 3) for i in range(200)]) is None

    def test_returns_none_on_empty(self):
        assert find_gap_valley([]) is None


class TestEstimateReturn24hLabels:
    def test_one_positive_one_negative(self):
        """Day 1 'news' recurs on day 2 within 24h of midnight -> positive.
        Day 2 'news' never recurs -> negative."""
        events = [(t(1, 10), "news"), (t(2, 9), "news")]
        stats = estimate_return_24h_labels(events)
        assert stats.total == 2
        assert stats.positives == 1
        assert stats.positive_rate == pytest.approx(0.5)

    def test_one_label_per_category_per_day_not_per_visit(self):
        events = [(t(1, 9), "news"), (t(1, 10), "news"), (t(1, 11), "news")]
        assert estimate_return_24h_labels(events).total == 1

    def test_separate_categories_yield_separate_labels(self):
        events = [(t(1, 9), "news"), (t(1, 10), "shopping")]
        assert estimate_return_24h_labels(events).total == 2

    def test_return_after_the_horizon_is_negative(self):
        """Day 1 label closes at day 2 00:00; a visit on day 3 is 24h+ later."""
        events = [(t(1, 10), "news"), (t(3, 10), "news")]
        stats = estimate_return_24h_labels(events)
        assert stats.positives == 0

    def test_no_future_data_is_used_before_window_end(self):
        """Leakage guard: the label for day 1 must not be decided by day-1 activity."""
        only_same_day = [(t(1, 9), "news"), (t(1, 23, 59), "news")]
        assert estimate_return_24h_labels(only_same_day).positives == 0

    def test_labels_per_week_is_scaled_by_observed_span(self):
        events = [(t(day, 10), "news") for day in range(1, 15)]  # 14 days
        stats = estimate_return_24h_labels(events)
        assert stats.span_days == pytest.approx(13.0, abs=1.0)
        expected = stats.total / (stats.span_days / 7)
        assert stats.labels_per_week == pytest.approx(expected, rel=0.01)

    def test_empty_input_is_all_zeroes_not_a_crash(self):
        stats = estimate_return_24h_labels([])
        assert stats.total == 0
        assert stats.positive_rate is None


class TestAsciiHistogram:
    def test_renders_one_row_per_bin(self):
        out = ascii_histogram([1.0, 2.0, 3.0, 4.0], bins=4)
        assert len([line for line in out.splitlines() if line.strip()]) == 4

    def test_empty_input_returns_a_message_not_an_empty_string(self):
        assert ascii_histogram([], bins=4).strip() != ""
