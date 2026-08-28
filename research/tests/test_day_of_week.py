"""The day-of-week measurement (D86), which exists because a claim went unmeasured.

D85 explained the shipped model's worst row as a weekend effect and never checked it. The
check says otherwise. An entry written to correct an unmeasured claim would be a poor place
to introduce a second one, so the logic that produces the correction is tested here.

Two things carry the conclusion and neither is arithmetic anyone would call obvious:

* **The monotone verdict.** The published sentence — that no single linear coefficient on
  an integer 0-6 can represent this pattern — is true only if the pattern really is
  non-monotone. If that check ever silently returned the wrong answer, the report would
  print a confident structural claim about a pattern that contradicts it.
* **D26's label floor.** Firefox has days with nine labels. Scoring one would let a rate
  built from a handful of rows sit in a table beside rates built from a hundred.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tise_research.eval.backtest import EXCLUDED_FROM_HEADLINE
from tise_research.features.labels import Label

from analysis.day_of_week import (
    DAY_NAMES,
    MIN_DAY_LABELS,
    day_of_week_rates,
    write_day_of_week_report,
)

#: 2026-06-01 is a Monday, so `weekday()` and the offsets below line up readably.
MONDAY = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def label(day_offset: int, outcome: bool, subject: str = "video") -> Label:
    return Label(
        target="return_24h",
        subject=subject,
        window_end=MONDAY + timedelta(days=day_offset),
        outcome=outcome,
        horizon_hours=24.0,
        session_id=f"s-{day_offset}-{outcome}",
    )


class TestRates:
    def test_buckets_by_the_weekday_of_window_end(self) -> None:
        days, overall = day_of_week_rates(
            [label(0, True), label(0, False), label(1, True)]
        )
        assert days[0].positives == 1
        assert days[0].total == 2
        assert days[1].total == 1
        assert overall is not None
        assert overall == 2 / 3

    def test_the_first_bucket_really_is_monday(self) -> None:
        # An off-by-one here would rename every row of the published table while leaving
        # every number in it correct, which is the hardest kind of wrong to notice.
        assert DAY_NAMES[0] == "Monday"
        assert MONDAY.weekday() == 0
        days, _ = day_of_week_rates([label(0, True)])
        assert days[0].name == "Monday"
        assert days[0].total == 1

    def test_excludes_unknown_exactly_as_the_headline_does(self) -> None:
        # D27. If this table included `unknown` and the model's tables did not, the two
        # would describe different populations and the comparison would be meaningless.
        days, overall = day_of_week_rates(
            [label(0, True), label(0, False, subject=EXCLUDED_FROM_HEADLINE)]
        )
        assert days[0].total == 1
        assert overall == 1.0

    def test_no_labels_gives_no_rate_rather_than_zero(self) -> None:
        days, overall = day_of_week_rates([])
        assert overall is None
        assert all(day.rate is None for day in days)


class TestTheLabelFloor:
    def test_a_thin_day_is_counted_but_not_scored(self) -> None:
        days, _ = day_of_week_rates([label(0, True) for _ in range(MIN_DAY_LABELS - 1)])
        assert days[0].total == MIN_DAY_LABELS - 1
        assert not days[0].reported

    def test_a_day_at_the_floor_is_scored(self) -> None:
        days, _ = day_of_week_rates([label(0, True) for _ in range(MIN_DAY_LABELS)])
        assert days[0].reported


class TestTheMonotoneVerdict:
    def _report(self, rates: dict[int, float]) -> str:
        """Build a corpus whose scored days have exactly the given rates."""
        labels: list[Label] = []
        for day, rate in rates.items():
            positives = round(rate * MIN_DAY_LABELS)
            for index in range(MIN_DAY_LABELS):
                labels.append(label(day, index < positives))
        days, overall = day_of_week_rates(labels)
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = write_day_of_week_report(
                [("history-test", days, overall)],
                out_dir=Path(tmp),
                timeout_seconds=1800.0,
            )
            return path.read_text(encoding="utf-8")

    def test_calls_a_rising_pattern_monotone(self) -> None:
        text = self._report({0: 0.2, 1: 0.4, 2: 0.6, 3: 0.8})
        assert "**monotone**" in text
        assert "**not monotone**" not in text

    def test_calls_a_falling_pattern_monotone(self) -> None:
        # Monotone in either direction is representable by one coefficient — with a
        # negative one. Only checking `sorted()` ascending would call this non-monotone
        # and print a structural claim that is not true.
        text = self._report({0: 0.8, 1: 0.6, 2: 0.4, 3: 0.2})
        assert "**monotone**" in text
        assert "**not monotone**" not in text

    def test_calls_a_peaked_pattern_not_monotone(self) -> None:
        # The shape the real corpora have: high in the middle of the week, low at both
        # ends. This is the verdict the published conclusion rests on.
        text = self._report({0: 0.2, 1: 0.9, 2: 0.3, 3: 0.8})
        assert "**not monotone**" in text


class TestTheReport:
    def test_says_it_changed_nothing(self) -> None:
        # `return_model.py` holds that a cyclic encoding is added against a measured
        # number, not an intuition. This report is the measurement; it must not read as
        # the change.
        days, overall = day_of_week_rates([label(index % 7, True) for index in range(70)])
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = write_day_of_week_report(
                [("history-test", days, overall)],
                out_dir=Path(tmp),
                timeout_seconds=1800.0,
            )
            text = path.read_text(encoding="utf-8")
        # Matched without the wrapped tail, so re-flowing the paragraph cannot break it.
        assert "The model has not been changed" in text
        assert "Do not edit by hand" in text
