"""Attention (dwell) labels, and the two properties the measurement rests on.

**Leakage.** Same structural guarantee as `block_labels.py`: a visit's label and features are
emitted before that visit joins any state. Asserted rather than trusted.

**Balance.** The label is a median split against the category's own recent dwell, which
should give a base rate near 50% for any person and any category. D88 claimed that property
for `block_volume` and D90 measured it false at daily granularity, so it is checked here
rather than assumed — this is the first target in the project where it actually holds.

**Label identity across feature sets.** T-A's whole claim to attribution is that `as_1` and
`as_2` produce the *same* labels, so any score change is the features and the cluster unit
rather than a redefinition. That is checked here as well as inside the analysis script.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from tise_research.features.attention import (
    ATTENTION_FEATURE_SET,
    DAILY_DOMAIN_MIN_DAYS,
    ENGAGED_FEATURE_SET,
    VISIT_ENGAGED_TARGET,
    attention_examples,
)
from tise_research.features.events import Event
from tise_research.features.sessions import sessionise
from tise_research.features.vector import FEATURE_SETS
from tise_research.models.prep import design_columns, fit_preprocessor, nullable_features

START = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)
TIMEOUT = 1800.0


def event(
    index: int,
    dwell: float | None,
    *,
    category: str = "video",
    transition: str = "link",
    minutes: float | None = None,
    domain: str = "example.com",
) -> Event:
    at = START + timedelta(minutes=minutes if minutes is not None else index * 5)
    return Event(
        event_id=f"e{index}",
        occurred_at=at,
        domain=domain,
        category=category,
        transition=transition,
        dwell_seconds=dwell,
        source="import",
    )


def examples_for(dwells: list[float | None], **kwargs):
    events = [event(i, d) for i, d in enumerate(dwells)]
    return attention_examples(events, timeout_seconds=TIMEOUT, **kwargs)


class TestLeakage:
    def test_a_visit_is_not_in_its_own_median(self) -> None:
        # Ten visits at 10s, then one at 500s. If the spike were inside its own median the
        # comparison would be against a raised threshold; it must be against the flat ten.
        examples = examples_for([10.0] * 10 + [500.0], min_prior=10, trailing=20)
        assert len(examples) == 1
        assert examples[0].label.outcome is True

    def test_appending_later_visits_changes_no_earlier_example(self) -> None:
        short = examples_for([10.0] * 15, min_prior=10)
        long = examples_for([10.0] * 15 + [900.0, 900.0], min_prior=10)
        assert len(long) > len(short)
        for before, after in zip(short, long, strict=False):
            assert before.label == after.label
            assert before.row.values == after.row.values


class TestLabels:
    def test_nothing_is_emitted_before_the_minimum_history(self) -> None:
        assert examples_for([10.0] * 9, min_prior=10) == []

    def test_a_visit_without_dwell_is_skipped_not_imputed(self) -> None:
        # A missing duration is not a short one. D51: never invent a value.
        with_gap = examples_for([10.0] * 10 + [None, 20.0], min_prior=10)
        assert len(with_gap) == 1
        assert with_gap[0].label.outcome is True

    def test_a_flat_series_ties_and_strict_comparison_makes_it_negative(self) -> None:
        examples = examples_for([10.0] * 20, min_prior=10)
        assert examples
        assert not any(example.label.outcome for example in examples)

    def test_the_split_is_balanced_on_an_alternating_series(self) -> None:
        # The property the whole target rests on: a median split is ~50% by construction.
        # block_volume claimed this and measured 36-47% (D90); here it should hold.
        dwells: list[float | None] = [5.0, 50.0] * 30
        examples = examples_for(dwells, min_prior=10)
        assert len(examples) > 20
        positives = sum(1 for example in examples if example.label.outcome)
        assert 0.4 <= positives / len(examples) <= 0.6

    def test_each_category_gets_its_own_median(self) -> None:
        # A category that is always slow must not be judged against a fast one's median.
        events = []
        for index in range(30):
            events.append(event(index, 5.0, category="news", minutes=index * 5))
            events.append(event(1000 + index, 300.0, category="video", minutes=index * 5 + 1))
        examples = attention_examples(events, timeout_seconds=TIMEOUT, min_prior=10)
        by_subject = {example.label.subject for example in examples}
        assert by_subject == {"news", "video"}
        # Both are flat within themselves, so neither should ever exceed its own median.
        assert not any(example.label.outcome for example in examples)


class TestFeatures:
    def test_rows_carry_the_declared_set_and_no_nulls(self) -> None:
        for example in examples_for([10.0, 40.0] * 15, min_prior=10):
            assert example.row.feature_set == ATTENTION_FEATURE_SET
            assert set(example.row.values) == set(FEATURE_SETS[ATTENTION_FEATURE_SET])
            assert all(value is not None for value in example.row.values.values())

    def test_it_is_declared_full_compat_because_it_needs_dwell(self) -> None:
        # The duration trap. Marking this `history` would claim the extension can compute
        # it today, which it cannot without the tabs permission.
        example = examples_for([10.0, 40.0] * 15, min_prior=10)[0]
        assert example.row.compat == "full"
        assert example.label.target == VISIT_ENGAGED_TARGET

    def test_transition_reaches_the_features(self) -> None:
        # `transition` has been collected since T1 and read by no feature until now.
        events = [
            event(index, 10.0, transition="typed" if index % 2 else "link")
            for index in range(30)
        ]
        examples = attention_examples(events, timeout_seconds=TIMEOUT, min_prior=10)
        flags = {example.row.values["arrivedTyped"] for example in examples}
        assert flags == {0.0, 1.0}

    def test_hour_is_cyclic(self) -> None:
        examples = examples_for([10.0, 40.0] * 15, min_prior=10)
        for example in examples:
            sin = example.row.values["hourSin"]
            cos = example.row.values["hourCos"]
            assert sin is not None and cos is not None
            assert sin * sin + cos * cos == pytest.approx(1.0)

    def test_rows_fit_the_declared_design_matrix(self) -> None:
        rows = [example.row for example in examples_for([10.0, 40.0] * 15, min_prior=10)]
        preprocessor = fit_preprocessor(rows)
        assert preprocessor.feature_set == ATTENTION_FEATURE_SET
        assert len(preprocessor.transform(rows[0])) == len(
            design_columns(ATTENTION_FEATURE_SET)
        )


class TestSessionId:
    """The label carries the session, not the visit.

    D94 makes the session the resampling unit, which is only possible if the label knows
    which session it came from. Until T-A it carried the *event* id — unique per row, so a
    session-clustered bootstrap over it would have silently degenerated into a row
    bootstrap and reported `n=` the row count while calling them sessions.
    """

    def _two_sessions(self) -> list[Event]:
        first = [event(index, 10.0, minutes=index * 5) for index in range(30)]
        # A two-hour gap is far past the 30-minute timeout.
        second = [
            event(100 + index, 10.0, minutes=30 * 5 + 120 + index * 5)
            for index in range(15)
        ]
        return first + second

    def test_labels_carry_the_session_id_not_the_event_id(self) -> None:
        events = self._two_sessions()
        sessions = sessionise(events, timeout_seconds=TIMEOUT)
        assert len(sessions) == 2

        examples = attention_examples(events, timeout_seconds=TIMEOUT, min_prior=10)
        ids = {example.label.session_id for example in examples}
        assert ids == {session.session_id for session in sessions}

    def test_many_visits_share_one_session_id(self) -> None:
        # The whole point: far fewer clusters than rows, which is what makes the interval
        # honest rather than optimistic.
        examples = attention_examples(
            self._two_sessions(), timeout_seconds=TIMEOUT, min_prior=10
        )
        ids = {example.label.session_id for example in examples}
        assert len(ids) < len(examples)


class TestAs2:
    """`as_2` — the six features T-A adds, and the two that may legitimately be absent."""

    def test_both_feature_sets_produce_identical_labels(self) -> None:
        # D94's attribution claim. If this ever fails, T-A stops being a comparison
        # between two models and becomes a comparison between two questions.
        events = [event(index, 10.0 if index % 2 else 40.0) for index in range(40)]
        first = attention_examples(
            events, timeout_seconds=TIMEOUT, min_prior=10, feature_set=ATTENTION_FEATURE_SET
        )
        second = attention_examples(
            events, timeout_seconds=TIMEOUT, min_prior=10, feature_set=ENGAGED_FEATURE_SET
        )
        assert [example.label for example in first] == [
            example.label for example in second
        ]

    def test_as_2_leaves_every_as_1_value_untouched(self) -> None:
        events = [event(index, 10.0 if index % 2 else 40.0) for index in range(40)]
        first = attention_examples(
            events, timeout_seconds=TIMEOUT, min_prior=10, feature_set=ATTENTION_FEATURE_SET
        )
        second = attention_examples(
            events, timeout_seconds=TIMEOUT, min_prior=10, feature_set=ENGAGED_FEATURE_SET
        )
        shared = FEATURE_SETS[ATTENTION_FEATURE_SET]
        for before, after in zip(first, second, strict=True):
            assert {name: after.row.values[name] for name in shared} == before.row.values

    def test_rows_carry_the_declared_set(self) -> None:
        examples = examples_for(
            [10.0, 40.0] * 15, min_prior=10, feature_set=ENGAGED_FEATURE_SET
        )
        for example in examples:
            assert example.row.feature_set == ENGAGED_FEATURE_SET
            assert set(example.row.values) == set(FEATURE_SETS[ENGAGED_FEATURE_SET])

    def test_only_the_declared_features_are_ever_null(self) -> None:
        # The guard that keeps `prep.py`'s declaration honest: anything that comes back
        # None without being declared nullable makes `raw_row` raise, and anything
        # declared but never null gets an indicator column of zeros.
        events = [
            event(index, None if index in {12, 20} else 10.0, domain=f"d{index % 3}.com")
            for index in range(40)
        ]
        examples = attention_examples(
            events, timeout_seconds=TIMEOUT, min_prior=10, feature_set=ENGAGED_FEATURE_SET
        )
        assert examples
        nulls = {
            name
            for example in examples
            for name, value in example.row.values.items()
            if value is None
        }
        assert nulls <= set(nullable_features(ENGAGED_FEATURE_SET))

    def test_a_new_domain_has_no_dwell_level_and_it_is_absent_not_zero(self) -> None:
        # Filling this with zero would say the person leaves this domain instantly, which
        # is the opposite of "never measured". D51.
        events = [event(index, 10.0, domain="known.com") for index in range(12)]
        events.append(event(99, 10.0, minutes=12 * 5, domain="brand-new.com"))
        examples = attention_examples(
            events, timeout_seconds=TIMEOUT, min_prior=10, feature_set=ENGAGED_FEATURE_SET
        )
        last = examples[-1].row.values
        assert last["domainDwellLevel"] is None
        assert last["domainVisits"] == 0.0

    def test_prev_dwell_ratio_is_absent_when_the_previous_visit_had_no_duration(
        self,
    ) -> None:
        # The previous visit is not skipped over to find one that has a duration: "the
        # visit before this one" is the feature, and substituting an earlier one would
        # change its meaning while keeping its name.
        examples = examples_for(
            [10.0] * 10 + [None, 20.0], min_prior=10, feature_set=ENGAGED_FEATURE_SET
        )
        assert len(examples) == 1
        assert examples[0].row.values["prevDwellRatio"] is None

    def test_domain_features_separate_two_domains(self) -> None:
        # `domain` has been stored since T1 and read by zero features. This is the first
        # test in the project that it reaches a model at all.
        events = [
            event(index, 10.0, domain="often.com" if index % 4 else "rare.com")
            for index in range(40)
        ]
        examples = attention_examples(
            events, timeout_seconds=TIMEOUT, min_prior=10, feature_set=ENGAGED_FEATURE_SET
        )
        shares = {example.row.values["domainShare"] for example in examples}
        assert len(shares) > 1, "one domain's share must differ from the other's"

        visits = {example.row.values["domainVisits"] for example in examples}
        assert len(visits) > 1, "the frequent domain must outcount the rare one"

    def test_prev_same_domain_reads_the_immediately_preceding_visit(self) -> None:
        alternating = [
            event(index, 10.0, domain=f"d{index % 2}.com") for index in range(30)
        ]
        repeated = [event(index, 10.0, domain="one.com") for index in range(30)]

        def flags(events: list[Event]) -> set[float | None]:
            return {
                example.row.values["prevSameDomain"]
                for example in attention_examples(
                    events,
                    timeout_seconds=TIMEOUT,
                    min_prior=10,
                    feature_set=ENGAGED_FEATURE_SET,
                )
            }

        assert flags(alternating) == {0.0}
        assert flags(repeated) == {1.0}

    def test_is_daily_domain_counts_days_and_not_visits(self) -> None:
        # A hundred visits in one afternoon is not a daily habit, and the feature has to
        # say so or it is just `domainVisits` again under another name.
        one_day = [event(index, 10.0, minutes=index * 5) for index in range(40)]
        assert {
            example.row.values["isDailyDomain"]
            for example in attention_examples(
                one_day,
                timeout_seconds=TIMEOUT,
                min_prior=10,
                feature_set=ENGAGED_FEATURE_SET,
            )
        } == {0.0}

        spread = [
            event(day * 10 + index, 10.0, minutes=day * 1440 + index * 5)
            for day in range(8)
            for index in range(5)
        ]
        values = [
            example.row.values["isDailyDomain"]
            for example in attention_examples(
                spread,
                timeout_seconds=TIMEOUT,
                min_prior=10,
                feature_set=ENGAGED_FEATURE_SET,
            )
        ]
        assert values[0] == 0.0, "two days of history is not a daily habit"
        assert values[-1] == 1.0
        assert values.count(1.0) >= DAILY_DOMAIN_MIN_DAYS

    def test_appending_later_visits_changes_no_earlier_example(self) -> None:
        # Leakage, for the domain and sequence state as well as the dwell medians.
        def run(events: list[Event]):
            return attention_examples(
                events,
                timeout_seconds=TIMEOUT,
                min_prior=10,
                feature_set=ENGAGED_FEATURE_SET,
            )

        base = [event(index, 10.0, domain=f"d{index % 3}.com") for index in range(20)]
        extra = base + [
            event(100 + index, 900.0, minutes=(20 + index) * 5, domain="d0.com")
            for index in range(10)
        ]
        short, long = run(base), run(extra)
        assert len(long) > len(short)
        for before, after in zip(short, long, strict=False):
            assert before.label == after.label
            assert before.row.values == after.row.values

    def test_rows_fit_the_declared_design_matrix(self) -> None:
        rows = [
            example.row
            for example in examples_for(
                [10.0, 40.0] * 15, min_prior=10, feature_set=ENGAGED_FEATURE_SET
            )
        ]
        preprocessor = fit_preprocessor(rows)
        assert preprocessor.feature_set == ENGAGED_FEATURE_SET
        assert len(preprocessor.transform(rows[0])) == len(
            design_columns(ENGAGED_FEATURE_SET)
        )


class TestLabelIdentity:
    """Rows are indexed by a unique label id, not by `(subject, window_end)`.

    The earlier guard refused two visits to one category in one instant, because every
    consumer keyed rows on that pair. It found nothing on Akash's browsing and fired on the
    **first** external corpus: the GESIS panel (D99) records to the second, and 0.02% of its
    rows are a second visit by the same person in the same second. Refusing them would
    discard real visits over an indexing choice, so the indexing changed instead.
    """

    def _same_instant(self) -> list[Event]:
        events = [event(index, 10.0, minutes=index * 5) for index in range(12)]
        events.append(event(90, 10.0, minutes=60))
        events.append(event(91, 20.0, minutes=60))
        return events

    def test_two_visits_at_one_instant_both_get_labels(self) -> None:
        examples = attention_examples(
            self._same_instant(), timeout_seconds=TIMEOUT, min_prior=10
        )
        at_the_instant = [
            item
            for item in examples
            if item.label.window_end == START + timedelta(minutes=60)
        ]
        assert len(at_the_instant) == 2, "both visits are real and both are labelled"

    def test_colliding_visits_get_distinct_label_ids(self) -> None:
        # The property the row index depends on. Two labels sharing an id would silently
        # score one feature row twice, which is the defect the old guard was standing in for.
        examples = attention_examples(
            self._same_instant(), timeout_seconds=TIMEOUT, min_prior=10
        )
        ids = [item.label.label_id for item in examples]
        assert len(ids) == len(set(ids))
        assert all(ids)

    def test_a_row_can_be_recovered_for_every_label(self) -> None:
        # Exactly what the analysis scripts do. Under the old key this lookup returned one
        # row for two different labels and nothing reported it.
        examples = attention_examples(
            self._same_instant(),
            timeout_seconds=TIMEOUT,
            min_prior=10,
            feature_set=ENGAGED_FEATURE_SET,
        )
        rows = {item.label.label_id: item.row for item in examples}
        assert len(rows) == len(examples)
        for item in examples:
            assert rows[item.label.label_id] is item.row

    def test_a_duplicate_event_id_is_still_refused(self) -> None:
        # The guard did not go away, it moved to the thing that must actually be unique.
        # The reused id must belong to a *labelled* visit: only labelled visits are
        # registered, because only they index a feature row. Index 11 clears min_prior=10;
        # index 7 would not, and reusing that id would prove nothing.
        events = [event(index, 10.0, minutes=index * 5) for index in range(12)]
        events.append(event(11, 10.0, minutes=61))  # reuses event_id "e11"
        with pytest.raises(ValueError, match="duplicate event id"):
            attention_examples(events, timeout_seconds=TIMEOUT, min_prior=10)
