"""The rest of the feature set: frequency, priors, session context, and the vector.

`extension/src/features/` holds the mirrors. The parity fixture proves the two agree;
these tests prove the Python side is right in the first place, which parity alone would
not — two implementations can agree and both be wrong.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from tise_research.features.context import (
    category_events_in_session,
    day_of_week,
    hour_of_day,
    session_category_count,
    session_event_count,
)
from tise_research.features.events import Event
from tise_research.features.frequency import (
    category_share,
    days_seen,
    event_count,
    session_count,
)
from tise_research.features.priors import prior_return_rate, prior_session_count
from tise_research.features.vector import (
    COMPAT,
    FEATURE_NAMES,
    FEATURE_SET,
    FEATURE_SETS,
    FIRST_SEEN_SCALE_HOURS,
    PRIOR_SESSION_RATE_SCALE,
    compute_features,
    saturate,
)

TIMEOUT = 1800.0
HORIZON = 24.0
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "parity_expected.json"


def at(day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(2026, 6, day, hour, minute, tzinfo=UTC)


def event(category: str, when: datetime, event_id: str | None = None) -> Event:
    return Event(
        event_id=event_id or f"e{when.isoformat()}",
        occurred_at=when,
        domain="example.com",
        category=category,
        transition="link",
        dwell_seconds=None,
        source="import",
    )


class TestFrequency:
    def test_counts_only_inside_the_window(self) -> None:
        events = [event("video", at(1)), event("video", at(9)), event("video", at(9, 12))]
        # Window is [day 10 - 7d, day 10) = [day 3, day 10).
        assert event_count(events, "video", window_end=at(10), days=7) == 2

    def test_the_window_is_half_open_at_both_ends(self) -> None:
        window_end = at(10)
        start = window_end - timedelta(days=7)
        events = [event("video", start), event("video", window_end)]
        # The start is included, the end is not.
        assert event_count(events, "video", window_end=window_end, days=7) == 1

    def test_days_seen_separates_a_habit_from_a_binge(self) -> None:
        binge = [event("video", at(9, hour), f"b{hour}") for hour in range(5)]
        habit = [event("video", at(day, 9), f"h{day}") for day in (5, 6, 7, 8, 9)]

        assert event_count(binge, "video", window_end=at(10), days=7) == 5
        assert event_count(habit, "video", window_end=at(10), days=7) == 5
        assert days_seen(binge, "video", window_end=at(10), days=7) == 1
        assert days_seen(habit, "video", window_end=at(10), days=7) == 5

    def test_session_count_uses_only_windowed_events(self) -> None:
        events = [event("video", at(9, 9)), event("video", at(9, 10))]
        assert (
            session_count(
                events, "video", window_end=at(10), days=7, timeout_seconds=TIMEOUT
            )
            == 2
        )

    def test_share_is_none_when_there_is_nothing_to_divide_by(self) -> None:
        assert category_share([], "video", window_end=at(10), days=30) is None

    def test_share_of_an_absent_category_is_zero_not_none(self) -> None:
        """Zero and None mean different things and both are real answers."""
        events = [event("dev", at(9))]
        assert category_share(events, "video", window_end=at(10), days=30) == 0.0


class TestPriors:
    def build(self) -> list[Event]:
        # Sessions on days 1, 2 and 5. Day 1 is returned to within 24h; day 2 is not.
        return [
            event("video", at(1, 9), "a"),
            event("video", at(2, 8), "b"),
            event("video", at(5, 9), "c"),
        ]

    def test_counts_only_sessions_whose_horizon_has_elapsed(self) -> None:
        events = self.build()
        # At day 2 09:00, session 1 (ended day 1 09:00) resolved at day 2 09:00 — exactly
        # the boundary, so it counts. Session 2 (day 2 08:00) has not.
        assert (
            prior_session_count(
                events,
                "video",
                window_end=at(2, 9),
                timeout_seconds=TIMEOUT,
                horizon_hours=HORIZON,
            )
            == 1
        )

    def test_an_unresolved_session_is_excluded_from_both_sides(self) -> None:
        """Not counted as a miss. That is the leak, and it is the tempting shortcut."""
        events = self.build()
        rate = prior_return_rate(
            events,
            "video",
            window_end=at(2, 9),
            timeout_seconds=TIMEOUT,
            horizon_hours=HORIZON,
        )
        # Session 1 was returned to (day 2 08:00 is inside 24h), so the rate is 1.0 and
        # not 0.5 — the unresolved session 2 is absent from the denominator.
        assert rate == 1.0

    def test_is_none_before_anything_has_resolved(self) -> None:
        assert (
            prior_return_rate(
                self.build(),
                "video",
                window_end=at(1, 10),
                timeout_seconds=TIMEOUT,
                horizon_hours=HORIZON,
            )
            is None
        )

    def test_never_invents_a_prior_of_one_half(self) -> None:
        """0.5 would be a number fitted downstream as though it had been measured."""
        assert (
            prior_return_rate(
                [], "video", window_end=at(9), timeout_seconds=TIMEOUT, horizon_hours=HORIZON
            )
            is None
        )

    def test_a_return_exactly_on_the_horizon_counts(self) -> None:
        events = [event("video", at(1, 9), "a"), event("video", at(2, 9), "b")]
        assert (
            prior_return_rate(
                events,
                "video",
                window_end=at(4),
                timeout_seconds=TIMEOUT,
                horizon_hours=HORIZON,
            )
            == 0.5  # session 1 returned; session 2 did not
        )


class TestContext:
    def test_a_later_event_cannot_extend_the_session_being_described(self) -> None:
        """The subtlest leak in the set."""
        window_end = at(1, 10)
        events = [event("video", at(1, 9, 40), "a"), event("video", window_end, "b")]
        before = session_event_count(
            events, window_end=window_end, timeout_seconds=TIMEOUT
        )

        # Ten minutes later — inside the timeout, so it would merge if the session were
        # re-derived from the whole corpus.
        soon = [*events, event("video", at(1, 10, 10), "c")]
        after = session_event_count(soon, window_end=window_end, timeout_seconds=TIMEOUT)
        assert after == before

    def test_counts_the_session_that_closes_at_window_end(self) -> None:
        events = [
            event("video", at(1, 9), "a"),
            event("dev", at(1, 9, 10), "b"),
            event("video", at(1, 9, 20), "c"),
        ]
        close = at(1, 9, 20)
        assert session_event_count(events, window_end=close, timeout_seconds=TIMEOUT) == 3
        assert session_category_count(events, window_end=close, timeout_seconds=TIMEOUT) == 2
        assert (
            category_events_in_session(
                events, "video", window_end=close, timeout_seconds=TIMEOUT
            )
            == 2
        )

    def test_hour_and_day_are_utc(self) -> None:
        assert hour_of_day(at(1, 14)) == 14
        # 2026-06-01 is a Monday, and Python counts Monday as 0.
        assert day_of_week(at(1)) == 0
        assert day_of_week(at(7)) == 6  # Sunday


class TestVector:
    def test_produces_exactly_the_declared_features(self) -> None:
        row = compute_features(
            [event("video", at(1, 9))],
            "video",
            window_end=at(1, 10),
            timeout_seconds=TIMEOUT,
            horizon_hours=HORIZON,
        )
        assert tuple(row.values) == FEATURE_NAMES
        assert row.feature_set == FEATURE_SET

    def test_every_feature_is_history_class(self) -> None:
        """D35 left the `full` class empty. The mechanism stays; the class is empty.

        Checked across **every** feature set, not just the shipped one: a new set whose
        features had no declared compat class would be a set that could silently smuggle
        in something the extension cannot compute.
        """
        assert set(COMPAT.values()) == {"history"}
        for feature_set, names in FEATURE_SETS.items():
            undeclared = set(names) - set(COMPAT)
            assert not undeclared, f"{feature_set} has undeclared features: {undeclared}"

    def test_the_whole_vector_is_leakage_safe(self) -> None:
        events = [event("video", at(1, 9), "a"), event("dev", at(1, 9, 30), "b")]
        window_end = at(1, 9, 30)
        before = compute_features(
            events,
            "video",
            window_end=window_end,
            timeout_seconds=TIMEOUT,
            horizon_hours=HORIZON,
        )

        future = [*events, event("video", at(20, 12), "future")]
        after = compute_features(
            future,
            "video",
            window_end=window_end,
            timeout_seconds=TIMEOUT,
            horizon_hours=HORIZON,
        )
        assert after.values == before.values

    def test_empty_history_produces_a_full_row_of_defined_values(self) -> None:
        row = compute_features(
            [], "video", window_end=at(9), timeout_seconds=TIMEOUT, horizon_hours=HORIZON
        )
        assert set(row.values) == set(FEATURE_NAMES)
        assert row.values["eventCount7d"] == 0.0
        assert row.values["hoursSinceLastSeen"] is None
        assert row.values["categoryShare30d"] is None


@pytest.mark.parity
class TestTheFixtureIsWorthTrusting:
    """A fixture that never exercises a feature cannot catch a bug in it."""

    def setup_method(self) -> None:
        self.expected = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_column_order_is_pinned(self) -> None:
        assert tuple(self.expected["featureNames"]) == FEATURE_NAMES
        assert self.expected["featureSet"] == FEATURE_SET

    def test_every_feature_appears_in_every_row(self) -> None:
        for row in self.expected["features"]:
            assert tuple(row["values"]) == FEATURE_NAMES
            assert row["compat"] == "history"

    def test_prior_return_rate_has_real_variety(self) -> None:
        rates = [
            row["values"]["priorReturnRate"]
            for row in self.expected["features"]
            if row["values"]["priorReturnRate"] is not None
        ]
        assert len(rates) >= 4
        assert len(set(rates)) >= 3
        assert any(0 < rate < 1 for rate in rates), "a rate of only 0 and 1 proves little"

    def test_every_feature_varies_somewhere_in_the_fixture(self) -> None:
        """A column that is constant across every row is not being tested by parity."""
        constant = []
        for name in FEATURE_NAMES:
            values = {row["values"][name] for row in self.expected["features"]}
            if len(values) == 1:
                constant.append(name)
        assert not constant, f"these features never vary in the fixture: {constant}"


class TestBoundedReplacements:
    """`fs_3`'s two features (D81). The properties, not the values.

    Each is tested for the thing it was introduced to guarantee — boundedness — rather
    than for a particular number, because the numbers follow from declared scales that
    could reasonably change while the guarantee must not.
    """

    def test_saturate_is_bounded_however_large_the_input(self) -> None:
        for value in (0.0, 1.0, 168.0, 1e6, 1e12):
            assert 0.0 <= saturate(value, FIRST_SEEN_SCALE_HOURS) < 1.0

    def test_saturate_reaches_one_half_at_its_scale(self) -> None:
        """The scale is the half-way point, which is what makes it interpretable."""
        assert saturate(FIRST_SEEN_SCALE_HOURS, FIRST_SEEN_SCALE_HOURS) == 0.5
        assert saturate(PRIOR_SESSION_RATE_SCALE, PRIOR_SESSION_RATE_SCALE) == 0.5

    def test_saturate_is_monotonic(self) -> None:
        """The ordering `hoursSinceFirstSeen` carried has to survive the transform."""
        values = [saturate(v, 168.0) for v in (0.0, 10.0, 100.0, 1_000.0, 10_000.0)]
        assert values == sorted(values)

    def test_saturate_refuses_a_negative(self) -> None:
        """Negative hours mean a leakage guard failed upstream. Do not smooth it over."""
        with pytest.raises(ValueError, match="negative"):
            saturate(-1.0, 168.0)

    def build(self) -> list[Event]:
        return [
            event("video", at(1, 9), "a"),
            event("video", at(2, 8), "b"),
            event("video", at(5, 9), "c"),
        ]

    def row(self, events, window_end, feature_set="fs_3"):
        return compute_features(
            events,
            "video",
            window_end=window_end,
            timeout_seconds=TIMEOUT,
            horizon_hours=HORIZON,
            feature_set=feature_set,
        )

    def test_fs3_replaces_exactly_two_features_and_keeps_their_positions(self) -> None:
        fs2, fs3 = FEATURE_SETS["fs_2"], FEATURE_SETS["fs_3"]
        assert len(fs2) == len(fs3)
        differing = [(a, b) for a, b in zip(fs2, fs3, strict=True) if a != b]
        assert differing == [
            ("hoursSinceFirstSeen", "firstSeenSaturation"),
            ("priorSessionCount", "priorSessionRate"),
        ]

    def test_an_unseen_category_leaves_saturation_absent_not_zero(self) -> None:
        """Never seen is an absence. Zero would say "seen just now", which is a claim."""
        row = self.row([event("dev", at(1, 9), "x")], at(2))
        assert row.values["firstSeenSaturation"] is None

    def test_the_rate_is_zero_rather_than_absent_when_nothing_has_resolved(self) -> None:
        """No prior sessions is a measured zero, unlike never having been seen."""
        row = self.row(self.build(), at(1, 10))
        assert row.values["priorSessionRate"] == 0.0

    def test_the_rate_denominator_has_a_one_day_floor(self) -> None:
        """Without it, a category first seen an hour ago reports sessions per hour.

        The floor needs a **short horizon** to bind at all, and that is worth knowing:
        a prior session only counts once `session_end + horizon <= window_end`, so at the
        default 24-hour horizon at least a day has always been observed by the time the
        count is non-zero, and the floor can never be reached. Removing it failed zero
        tests until this one used a horizon that reaches it.
        """
        events = [event("video", at(1, 9), "a"), event("video", at(1, 9, 20), "b")]
        row = compute_features(
            events,
            "video",
            window_end=at(1, 10, 30),
            timeout_seconds=TIMEOUT,
            horizon_hours=1.0,
            feature_set="fs_3",
        )
        # One resolved session, 1.5 hours observed. Without the floor the rate would be
        # ~16 sessions a day and saturate to 0.94; with it the rate is 1 a day.
        assert row.values["priorSessionRate"] == 0.5

    def test_the_floor_cannot_bind_at_the_default_horizon(self) -> None:
        """Stated as a test so the guard above is not mistaken for a live code path."""
        events = [event("video", at(1, 9), "a"), event("video", at(1, 9, 20), "b")]
        row = self.row(events, at(1, 10, 30))
        assert row.values["priorSessionRate"] == 0.0  # nothing has resolved yet

    def test_both_replacements_are_bounded_on_real_looking_input(self) -> None:
        for window_end in (at(2), at(5), at(9), at(30)):
            row = self.row(self.build(), window_end)
            saturation = row.values["firstSeenSaturation"]
            assert saturation is None or 0.0 <= saturation < 1.0
            assert 0.0 <= row.values["priorSessionRate"] < 1.0

    def test_fs3_is_still_leakage_safe(self) -> None:
        """The whole-vector guard from `fs_2`, re-run against the new features."""
        events = self.build()
        window_end = at(2, 9)
        before = self.row(events, window_end)
        after = self.row([*events, event("video", at(3, 9), "z")], window_end)
        assert before.values == after.values

    def test_the_two_sets_agree_on_every_shared_feature(self) -> None:
        """`fs_3` changes two features and must not perturb the other twelve."""
        events = self.build()
        fs2 = self.row(events, at(5), feature_set="fs_2")
        fs3 = self.row(events, at(5), feature_set="fs_3")
        shared = set(fs2.values) & set(fs3.values)
        assert len(shared) == 12
        for name in shared:
            assert fs2.values[name] == fs3.values[name]

    def test_the_row_records_which_set_produced_it(self) -> None:
        assert self.row(self.build(), at(5)).feature_set == "fs_3"

    def test_an_unknown_feature_set_is_refused(self) -> None:
        with pytest.raises(ValueError, match="unknown feature set"):
            self.row(self.build(), at(5), feature_set="fs_99")
