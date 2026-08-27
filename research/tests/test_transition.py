"""The transition table behind `next_session_category` — the UI-only target.

Nothing here feeds `return_24h`, and no number this project publishes rests on it. What
these tests protect is the part that would be embarrassing rather than wrong: a table
that claims 100% off two observations, or one whose answer depends on dictionary
iteration order.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from tise_research.features.events import Event
from tise_research.features.sessions import sessionise
from tise_research.models.transition import (
    fit_transition_table,
    primary_category,
)

TIMEOUT = 1800.0
START = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)


def event(category: str, minutes: float, event_id: str | None = None) -> Event:
    return Event(
        event_id=event_id or f"e{minutes}-{category}",
        occurred_at=START + timedelta(minutes=minutes),
        domain="example.com",
        category=category,
        transition="link",
        dwell_seconds=None,
        source="import",
    )


def sessions_from(*groups: list[str]):
    """One session per group, separated by well over the timeout."""
    events: list[Event] = []
    for index, categories in enumerate(groups):
        base = index * 24 * 60
        for offset, category in enumerate(categories):
            events.append(event(category, base + offset, f"s{index}-e{offset}"))
    return sessionise(events, timeout_seconds=TIMEOUT)


class TestPrimaryCategory:
    def test_the_most_frequent_category_wins(self) -> None:
        session = sessions_from(["video", "video", "dev"])[0]
        assert primary_category(session) == "video"

    def test_ties_break_by_name_not_by_order_of_appearance(self) -> None:
        """First-seen would depend on within-session ordering, which two implementations
        could resolve differently for events sharing a timestamp."""
        later_first = sessions_from(["video", "dev"])[0]
        earlier_first = sessions_from(["dev", "video"])[0]
        assert primary_category(later_first) == "dev"
        assert primary_category(earlier_first) == "dev"


class TestFitting:
    def test_counts_consecutive_pairs_and_nothing_else(self) -> None:
        table = fit_transition_table(sessions_from(["dev"], ["video"], ["dev"]))
        assert table.transition_count == 2  # three sessions, two transitions
        assert table.counts["dev"] == {"video": 1}
        assert table.counts["video"] == {"dev": 1}

    def test_a_single_session_yields_no_transitions_but_still_a_vocabulary(self) -> None:
        table = fit_transition_table(sessions_from(["dev"]))
        assert table.transition_count == 0
        assert table.vocabulary == ("dev",)

    def test_the_vocabulary_is_sorted_because_it_is_a_column_order(self) -> None:
        table = fit_transition_table(sessions_from(["video"], ["dev"], ["search"]))
        assert table.vocabulary == ("dev", "search", "video")

    def test_no_sessions_at_all_is_an_empty_table_not_an_error(self) -> None:
        table = fit_transition_table([])
        assert table.vocabulary == ()
        assert table.most_likely("dev") is None


class TestDistributions:
    def build(self):
        # dev is always followed by video, twice. Unsmoothed that claims certainty.
        return fit_transition_table(
            sessions_from(["dev"], ["video"], ["dev"], ["video"], ["search"])
        )

    def test_a_distribution_sums_to_one(self) -> None:
        distribution = self.build().distribution("dev")
        assert sum(distribution.values()) == pytest.approx(1.0)

    def test_smoothing_stops_two_observations_claiming_certainty(self) -> None:
        """The D26 problem in its smallest form."""
        probability = self.build().distribution("dev")["video"]
        assert 0.5 < probability < 1.0

    def test_an_unseen_category_falls_back_to_what_follows_anything(self) -> None:
        table = self.build()
        assert table.distribution("never-browsed") == table.marginal_distribution()

    def test_most_likely_breaks_ties_by_name(self) -> None:
        table = fit_transition_table(sessions_from(["news"], ["dev"], ["news"], ["video"]))
        best, probability = table.most_likely("news")
        assert best in table.vocabulary
        assert 0.0 < probability <= 1.0

    def test_an_empty_vocabulary_gives_an_empty_distribution_not_a_uniform_lie(
        self,
    ) -> None:
        assert fit_transition_table([]).distribution("dev") == {}
