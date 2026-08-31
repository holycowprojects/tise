"""T-C's bar, challenger and rival.

The challenger is the **shipped** transition table, reached through `fit_transition_pairs`.
That is the point of T-C: the table has existed in both languages since T10 and has never
been scored, so a research re-implementation would benchmark something nobody runs. The
first class here asserts the two entry points still agree.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tise_research.features.events import Event
from tise_research.features.sessions import Session
from tise_research.features.transitions import CategoryTransition
from tise_research.models.next_category import (
    BAR_MODEL,
    fit_bounce_back,
    fit_global_mode,
    fit_transition_ranker,
)
from tise_research.models.transition import fit_transition_pairs, fit_transition_table

START = datetime(2026, 3, 1, 9, tzinfo=UTC)


def transition(
    source: str, target: str, *, index: int = 0, previous: str | None = None
) -> CategoryTransition:
    return CategoryTransition(
        transition_id=f"t{index}",
        at=START + timedelta(hours=index),
        from_category=source,
        to_category=target,
        session_id="s1",
        within_session=True,
        previous_category=previous,
        from_run_events=1,
    )


class TestSharedCounting:
    def test_the_session_table_and_the_pair_table_agree(self):
        # `fit_transition_table` now delegates. If these diverge, the benchmarked table
        # and the shipped one are two different models.
        primaries = ["news", "video", "news", "work", "video", "news"]
        sessions = [
            Session(
                session_id=f"s{index}",
                started_at=START + timedelta(hours=index),
                ended_at=START + timedelta(hours=index),
                events=(
                    Event(
                        event_id=f"e{index}",
                        occurred_at=START + timedelta(hours=index),
                        domain=f"{category}.example",
                        category=category,
                        transition="link",
                    ),
                ),
            )
            for index, category in enumerate(primaries)
        ]
        from_sessions = fit_transition_table(sessions)
        from_pairs = fit_transition_pairs(list(zip(primaries, primaries[1:], strict=False)))
        assert from_sessions.counts == from_pairs.counts
        assert from_sessions.marginal == from_pairs.marginal
        assert from_sessions.vocabulary == from_pairs.vocabulary

    def test_a_category_only_ever_arrived_at_is_still_in_the_vocabulary(self):
        table = fit_transition_pairs([("news", "video")])
        assert table.vocabulary == ("news", "video")
        assert set(table.distribution("news")) == {"news", "video"}

    def test_a_lone_session_keeps_its_category_in_the_vocabulary(self):
        # One session produces no pair, and `fit_transition_pairs` only ever sees pairs.
        # Without the union in `fit_transition_table` the table would be empty of the one
        # category it has actually observed.
        session = Session(
            session_id="s1",
            started_at=START,
            ended_at=START,
            events=(
                Event(
                    event_id="e0",
                    occurred_at=START,
                    domain="news.example",
                    category="news",
                    transition="link",
                ),
            ),
        )
        assert fit_transition_table([session]).vocabulary == ("news",)


class TestGlobalMode:
    def test_predicts_the_most_common_target_whatever_the_source(self):
        model = fit_global_mode(
            [transition("a", "video", index=i) for i in range(5)]
            + [transition("b", "news", index=5 + i) for i in range(2)]
        )
        assert model.name == BAR_MODEL
        assert model.ranking(transition("z", "anything"))[0] == "video"

    def test_ties_break_by_name_not_by_insertion_order(self):
        # Without this the score would move when the training set was merely reordered.
        forward = fit_global_mode([transition("x", "video"), transition("x", "news", index=1)])
        backward = fit_global_mode([transition("x", "news"), transition("x", "video", index=1)])
        assert forward.order == backward.order == ("news", "video")

    def test_ranks_every_observed_category(self):
        model = fit_global_mode(
            [
                transition("a", "video"),
                transition("a", "news", index=1),
                transition("a", "work", index=2),
            ]
        )
        assert set(model.ranking(transition("a", "video"))) == {"video", "news", "work"}


class TestTransitionRanker:
    def test_conditions_on_the_source_category(self):
        training = (
            [transition("news", "video", index=i) for i in range(8)]
            + [transition("work", "search", index=8 + i) for i in range(8)]
        )
        model = fit_transition_ranker(training)
        assert model.ranking(transition("news", "?"))[0] == "video"
        assert model.ranking(transition("work", "?"))[0] == "search"

    def test_an_unseen_source_falls_back_to_the_marginal(self):
        # Smoothing pulls every row toward what follows anything, so a source the training
        # window never held still gets the global answer rather than an arbitrary one.
        training = [transition("news", "video", index=i) for i in range(6)]
        model = fit_transition_ranker(training)
        assert model.ranking(transition("astronomy", "?"))[0] == "video"

    def test_top1_matches_the_shipped_tables_own_answer(self):
        # Two routes to the same claim would eventually disagree; this pins them.
        training = [
            transition("news", "video", index=0),
            transition("news", "video", index=1),
            transition("news", "work", index=2),
        ]
        model = fit_transition_ranker(training)
        best = model.table.most_likely("news")
        assert best is not None
        assert model.ranking(transition("news", "?"))[0] == best[0]

    def test_empty_training_does_not_crash(self):
        model = fit_transition_ranker([])
        assert model.ranking(transition("news", "?")) == ()


class TestBounceBack:
    def test_predicts_the_category_before_the_one_just_finished(self):
        model = fit_bounce_back(
            [transition("a", "video", index=i) for i in range(4)]
            + [transition("a", "news", index=4)]
        )
        assert model.ranking(transition("work", "?", previous="news"))[0] == "news"

    def test_falls_back_to_the_bar_when_there_is_no_previous(self):
        # At the start of the corpus it has nothing of its own to say. Falling back to the
        # bar keeps the comparison a comparison.
        training = [transition("a", "video", index=i) for i in range(4)]
        model = fit_bounce_back(training)
        assert model.ranking(transition("work", "?", previous=None))[0] == "video"

    def test_falls_back_when_the_previous_category_is_unknown_to_training(self):
        training = [transition("a", "video", index=i) for i in range(4)]
        model = fit_bounce_back(training)
        assert model.ranking(transition("work", "?", previous="astronomy"))[0] == "video"

    def test_the_ranking_stays_a_permutation(self):
        training = [
            transition("a", "video", index=0),
            transition("a", "news", index=1),
            transition("a", "work", index=2),
        ]
        model = fit_bounce_back(training)
        ranking = model.ranking(transition("x", "?", previous="work"))
        assert ranking[0] == "work"
        assert sorted(ranking) == ["news", "video", "work"]
