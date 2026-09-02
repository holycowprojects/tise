"""`browsing_next_hour` labels and `pr_1` features (D94's T-B, feature set declared unrun).

Two claims in `presence.py` are worth more than the arithmetic and both are asserted here
rather than trusted:

* **No feature reads an event at or after the boundary it describes.** Appending activity
  to the future must move no earlier row.
* **An hour with no browsing is a label, not a gap.** It is most of this target — a person
  sleeps — and dropping empty hours is the T19b defect, where a block nobody browsed
  vanished and lifted every median after it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from tise_research.features.events import Event
from tise_research.features.presence import (
    PRESENCE_FEATURE_SET,
    RHYTHM_WINDOW_DAYS,
    TARGET,
    presence_examples,
)
from tise_research.features.vector import FEATURE_SETS
from tise_research.models.prep import design_columns, fit_preprocessor, nullable_features

#: A Monday, so weekday/weekend arithmetic is checkable by counting days.
START = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)


def event(hours: float, index: int = 0, category: str = "video") -> Event:
    at = START + timedelta(hours=hours, seconds=index)
    return Event(
        event_id=f"e-{hours}-{index}",
        occurred_at=at,
        domain="example.com",
        category=category,
        transition="link",
        dwell_seconds=None,
        source="import",
    )


def corpus(active_hours: list[int], *, per_hour: int = 1) -> list[Event]:
    """One event list with `per_hour` events in each named hour offset from START."""
    return [
        event(hour, index) for hour in active_hours for index in range(per_hour)
    ]


# --------------------------------------------------------------------------------------
# The label
# --------------------------------------------------------------------------------------


def test_empty_hours_are_labelled_negative_not_dropped() -> None:
    """The whole target. Hours 1-4 hold nothing and must appear as four negatives."""
    examples = presence_examples(corpus([0, 5]))

    # Boundaries 1, 2, 3, 4 — hour 0 and hour 5 are excluded as boundary hours.
    assert [example.label.window_end.hour for example in examples] == [1, 2, 3, 4]
    assert [example.label.outcome for example in examples] == [False] * 4


def test_a_visit_makes_its_own_hour_positive() -> None:
    examples = presence_examples(corpus([0, 2, 6]))
    outcomes = {
        example.label.window_end.hour: example.label.outcome for example in examples
    }
    assert outcomes == {1: False, 2: True, 3: False, 4: False, 5: False}


def test_both_boundary_hours_are_excluded() -> None:
    """Both are positive by construction — they are where the data was cut, not a result."""
    examples = presence_examples(corpus([0, 1, 2, 3]))
    hours = [example.label.window_end.hour for example in examples]
    assert hours == [1, 2]
    assert 0 not in hours, "the first hour holds the first visit by definition"
    assert 3 not in hours, "the last hour holds the last visit by definition"


def test_subject_is_the_hour_being_predicted_not_the_hour_standing_in() -> None:
    """D94 makes `category_base_rate` the per-hour rate through this field alone.

    Keyed on the hour Tise stands in, the bar would be a rhythm lagged by an hour, which
    is a different and weaker baseline wearing the same name.
    """
    examples = presence_examples(corpus([0, 4]))
    for example in examples:
        assert example.label.subject == f"{example.label.window_end.hour:02d}"


def test_session_id_carries_the_calendar_day() -> None:
    """D94's cluster unit. `run_backtest` clusters on whatever this field holds."""
    examples = presence_examples(corpus([0, 30]))
    days = {example.label.session_id for example in examples}
    assert days == {"2026-06-01", "2026-06-02"}


def test_labels_are_chronological_and_hourly() -> None:
    examples = presence_examples(corpus([0, 10]))
    ends = [example.label.window_end for example in examples]
    assert ends == sorted(ends)
    gaps = {second - first for first, second in zip(ends, ends[1:], strict=False)}
    assert gaps == {timedelta(hours=1)}


def test_target_and_horizon_are_stamped() -> None:
    example = presence_examples(corpus([0, 3]))[0]
    assert example.label.target == TARGET
    assert example.label.horizon_hours == 1.0


def test_no_events_produces_nothing() -> None:
    assert presence_examples([]) == []


def test_a_single_hour_produces_nothing() -> None:
    """First hour and last hour are the same hour, so there is no interior to label."""
    assert presence_examples(corpus([0], per_hour=3)) == []


def test_label_ids_are_unique() -> None:
    examples = presence_examples(corpus([0, 50]))
    ids = [example.label.label_id for example in examples]
    assert len(set(ids)) == len(ids)


# --------------------------------------------------------------------------------------
# Leakage
# --------------------------------------------------------------------------------------


def test_appending_future_activity_moves_no_earlier_feature() -> None:
    """The guard, stated directly. Extra events after the span must change nothing before it.

    The corpus end decides *which* boundaries get a label — that is not leakage, since a
    feature never sees it — so the shared prefix is what is compared.
    """
    before = presence_examples(corpus([0, 3, 7, 20]))
    after = presence_examples(corpus([0, 3, 7, 20, 21, 22, 30, 44]))

    assert len(after) > len(before)
    for original, extended in zip(before, after, strict=False):
        assert original.row.window_end == extended.row.window_end
        assert original.row.values == extended.row.values


def test_an_event_exactly_on_the_boundary_is_the_outcome_not_a_feature() -> None:
    """A visit at 03:00:00 belongs to the hour being predicted, never to what is known."""
    events = [event(0), event(3), event(6)]
    examples = {
        example.label.window_end.hour: example for example in presence_examples(events)
    }

    third = examples[3]
    assert third.label.outcome is True, "the visit lands inside [03:00, 04:00)"
    # Its own visit must not count as activity already observed.
    assert third.row.values["visitsLastHour"] == 0.0
    # ...and the boundary before it, which really did have nothing, agrees.
    assert examples[2].row.values["visitsLastHour"] == 0.0


# --------------------------------------------------------------------------------------
# The features
# --------------------------------------------------------------------------------------


def test_every_declared_feature_is_produced_in_order() -> None:
    example = presence_examples(corpus([0, 5]))[0]
    assert tuple(example.row.values) == FEATURE_SETS[PRESENCE_FEATURE_SET]
    assert example.row.feature_set == PRESENCE_FEATURE_SET
    assert example.row.compat == "history"


def test_hour_encoding_is_cyclic() -> None:
    """23:00 and 00:00 must be neighbours. A plain integer makes them maximally distant."""
    examples = {
        example.label.window_end: example
        for example in presence_examples(corpus([0, 30]))
    }
    midnight = examples[START + timedelta(hours=24)].row.values
    late = examples[START + timedelta(hours=23)].row.values

    assert midnight["hourSin"] == pytest.approx(0.0, abs=1e-12)
    assert midnight["hourCos"] == pytest.approx(1.0)
    distance = (midnight["hourSin"] - late["hourSin"]) ** 2 + (
        midnight["hourCos"] - late["hourCos"]
    ) ** 2
    assert distance < 0.1


def test_is_weekend_marks_saturday_and_sunday() -> None:
    """START is a Monday, so Saturday opens 120 hours in and Monday returns at 168."""
    examples = {
        example.label.window_end: example
        for example in presence_examples(corpus([0, 200]))
    }
    saturday = examples[START + timedelta(hours=120)].row.values
    monday = examples[START + timedelta(hours=168)].row.values
    friday = examples[START + timedelta(hours=100)].row.values

    assert saturday["isWeekend"] == 1.0
    assert monday["isWeekend"] == 0.0
    assert friday["isWeekend"] == 0.0


def test_recency_rises_as_the_gap_grows() -> None:
    examples = presence_examples(corpus([0, 10]))
    recency = [example.row.values["minutesSinceLast"] for example in examples]
    assert recency == sorted(recency), "each idle hour is further from the last visit"
    assert all(0.0 <= value < 1.0 for value in recency), "saturated, so bounded"


def test_visit_counts_are_measured_zeros_not_absences() -> None:
    """A quiet hour was counted and found empty. An indicator column would claim otherwise."""
    # Boundary 08:00, whose six-hour window [02:00, 08:00) is genuinely empty.
    examples = {
        example.label.window_end.hour: example
        for example in presence_examples(corpus([0, 12]))
    }
    example = examples[8]
    assert example.row.values["visitsLastHour"] == 0.0
    assert example.row.values["visitsLastSixHours"] == 0.0
    assert "visitsLastHour" not in nullable_features(PRESENCE_FEATURE_SET)
    assert "visitsLastSixHours" not in nullable_features(PRESENCE_FEATURE_SET)


def test_visits_last_hour_counts_only_the_hour_just_ended() -> None:
    events = corpus([0], per_hour=4) + corpus([1], per_hour=2) + [event(9)]
    examples = {
        example.label.window_end.hour: example for example in presence_examples(events)
    }
    # At 02:00 the hour just ended is 01:00, which held two visits.
    assert examples[2].row.values["visitsLastHour"] == pytest.approx(2.0 / (2.0 + 5.0))
    # At 03:00 the hour just ended is empty, though six hours still holds all six.
    assert examples[3].row.values["visitsLastHour"] == 0.0
    assert examples[3].row.values["visitsLastSixHours"] == pytest.approx(6.0 / 36.0)


def test_same_hour_rate_is_null_before_a_previous_day_exists() -> None:
    """An absence of corpus, not of behaviour. Zero would say the person was reliably away."""
    examples = presence_examples(corpus([0, 100]))
    first_day = [
        example for example in examples if example.label.window_end < START + timedelta(days=1)
    ]
    assert first_day, "the first day must be labelled, not skipped"
    assert all(
        example.row.values["sameHourRate7d"] is None for example in first_day
    )
    assert "sameHourRate7d" in nullable_features(PRESENCE_FEATURE_SET)


def test_same_hour_rate_counts_only_observed_days() -> None:
    """Browsing at 09:00 every day makes the 09:00 rate 1.0 once enough days exist.

    Unobserved days are excluded from the denominator rather than counted as quiet, which
    is the clamp the module docstring argues for.
    """
    hours = [0] + [24 * day + 9 for day in range(0, 10)] + [24 * 10]
    examples = {
        example.label.window_end: example
        for example in presence_examples(corpus(sorted(hours)))
    }

    ninth_day = examples[START + timedelta(days=9, hours=9)].row.values
    assert ninth_day["sameHourRate7d"] == pytest.approx(1.0)

    # One prior day, and it was active.
    second_day = examples[START + timedelta(days=1, hours=9)].row.values
    assert second_day["sameHourRate7d"] == pytest.approx(1.0)

    quiet = examples[START + timedelta(days=9, hours=14)].row.values
    assert quiet["sameHourRate7d"] == pytest.approx(0.0)


def test_same_hour_rate_looks_back_exactly_seven_days() -> None:
    """Active at 09:00 on day 0 only. By day 8 that day has left the window."""
    hours = [9] + [24 * day for day in range(1, 12)]
    examples = {
        example.label.window_end: example
        for example in presence_examples(corpus(sorted(hours)))
    }
    inside = examples[START + timedelta(days=RHYTHM_WINDOW_DAYS, hours=9)].row.values
    outside = examples[START + timedelta(days=RHYTHM_WINDOW_DAYS + 1, hours=9)].row.values

    assert inside["sameHourRate7d"] == pytest.approx(1.0 / RHYTHM_WINDOW_DAYS)
    assert outside["sameHourRate7d"] == pytest.approx(0.0)


def test_active_hour_share_is_never_null() -> None:
    """Its window always holds the hour before the boundary, so it is always a measurement."""
    examples = presence_examples(corpus([0, 200]))
    assert all(
        example.row.values["activeHourShare7d"] is not None for example in examples
    )
    assert "activeHourShare7d" not in nullable_features(PRESENCE_FEATURE_SET)


def test_active_hour_share_is_a_share() -> None:
    examples = presence_examples(corpus([0, 1, 2, 3, 4, 5, 6, 20]))
    shares = [example.row.values["activeHourShare7d"] for example in examples]
    assert all(0.0 <= share <= 1.0 for share in shares)
    # At 02:00 exactly two hours are observed and both were active.
    assert shares[0] == pytest.approx(1.0)


# --------------------------------------------------------------------------------------
# The rows reach the model
# --------------------------------------------------------------------------------------


def test_rows_build_a_design_matrix_of_the_declared_width() -> None:
    rows = [example.row for example in presence_examples(corpus([0, 60]))]
    preprocessor = fit_preprocessor(rows)
    columns = design_columns(PRESENCE_FEATURE_SET)

    assert preprocessor.feature_set == PRESENCE_FEATURE_SET
    assert preprocessor.columns == columns
    assert len(columns) == len(FEATURE_SETS[PRESENCE_FEATURE_SET]) + 1
    assert all(len(row) == len(columns) for row in preprocessor.matrix(rows))


def test_a_row_from_another_set_is_refused() -> None:
    """`pr_1` is nine design columns and `bs_1` is eleven, so today the widths differ — but
    the guard has to be the feature set, because widths coincide as sets are added."""
    rows = [example.row for example in presence_examples(corpus([0, 30]))]
    preprocessor = fit_preprocessor(rows)
    foreign = type(rows[0])(
        subject=rows[0].subject,
        window_end=rows[0].window_end,
        feature_set="fs_3",
        compat="history",
        values=rows[0].values,
    )
    with pytest.raises(ValueError, match="fitted on"):
        preprocessor.transform(foreign)
