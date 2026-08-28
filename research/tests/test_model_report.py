"""`model.md` is the report every published claim about the model comes through.

It had no test file at all, which is the hole D78 found in `corpus.py` — and it failed the
same way. `write_model_report` hardcoded the string `fs_2` in its title, its prose and the
fold table's column header. D83 shipped `fs_3`; the report was regenerated and the numbers
in it were `fs_3`'s, but every label naming the feature set was a version behind. Nothing
failed, because nothing looked.

The invariant these tests hold is narrow and mechanical: **the report may not name a
feature set or a model it did not score.** A number attached to the wrong name is worse
than a missing number, because it reads as a measurement of something that was never
measured. SPEC.md invariant 3 is usually read as being about the figures; it applies to
the labels on them for exactly the same reason.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from tise_research.eval.backtest import run_backtest
from tise_research.eval.model_report import BAR_MODEL, collect_evidence, write_model_report
from tise_research.features.events import Event
from tise_research.features.labels import return_24h_labels
from tise_research.features.vector import DEFAULT_FEATURE_SET, FEATURE_SETS
from tise_research.models.return_model import (
    MODEL_NAME,
    FeatureIndex,
    make_return_model_fitter,
)

TIMEOUT = 1800.0
HORIZON = 24.0
N_FOLDS = 3
START = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)


def event(category: str, hours: float, event_id: str) -> Event:
    return Event(
        event_id=event_id,
        occurred_at=START + timedelta(hours=hours),
        domain="example.com",
        category=category,
        transition="link",
        dwell_seconds=None,
        source="import",
    )


def corpus() -> list[Event]:
    """Synthetic, and a unit test rather than a benchmark — SPEC.md permits the first."""
    events: list[Event] = []
    for day in range(30):
        events.append(event("video", day * 24, f"v{day}"))
        events.append(event("video", day * 24 + 0.25, f"v{day}b"))
        if day % 3 == 0:
            events.append(event("dev", day * 24 + 3, f"d{day}"))
            events.append(event("dev", day * 24 + 3.25, f"d{day}b"))
        if day % 11 == 0:
            events.append(event("travel", day * 24 + 6, f"t{day}"))
    return events


@pytest.fixture(scope="module")
def report_text(tmp_path_factory: pytest.TempPathFactory) -> str:
    """One generated report, reused. Generating it is the expensive part."""
    events = corpus()
    labels = return_24h_labels(events, timeout_seconds=TIMEOUT, horizon_hours=HORIZON)
    index = FeatureIndex(
        events=events, timeout_seconds=TIMEOUT, horizon_hours=HORIZON
    )
    result = run_backtest(
        labels,
        n_folds=N_FOLDS,
        extra_models={MODEL_NAME: make_return_model_fitter(index)},
    )
    evidence = [
        collect_evidence("history-test", result, labels, index, n_folds=N_FOLDS)
    ]
    path = write_model_report(
        evidence,
        out_dir=tmp_path_factory.mktemp("benchmarks"),
        timeout_seconds=TIMEOUT,
    )
    return path.read_text(encoding="utf-8")


class TestNamesMatchWhatWasScored:
    def test_names_the_shipped_feature_set(self, report_text: str) -> None:
        assert DEFAULT_FEATURE_SET in report_text

    def test_never_names_a_feature_set_it_did_not_score(self, report_text: str) -> None:
        # The bug this file exists for. Every other set in FEATURE_SETS is a set the
        # report did not measure, so naming one is always wrong — and stays wrong for
        # `fs_4` without anybody remembering to update this test.
        for other in FEATURE_SETS:
            if other == DEFAULT_FEATURE_SET:
                continue
            assert other not in report_text, (
                f"report names `{other}` but scored `{DEFAULT_FEATURE_SET}`"
            )

    def test_names_the_model_it_scored(self, report_text: str) -> None:
        assert MODEL_NAME in report_text

    def test_the_fold_table_header_names_that_same_model(self, report_text: str) -> None:
        # The header was a literal while the column beneath it came from MODEL_NAME, so
        # the two could disagree silently. This is the pairing, not either half.
        header = next(
            line for line in report_text.splitlines() if line.startswith("| Fold |")
        )
        assert MODEL_NAME in header
        assert BAR_MODEL in header

    def test_reports_the_feature_count_it_actually_used(self, report_text: str) -> None:
        assert f"the {len(FEATURE_SETS[DEFAULT_FEATURE_SET])} features" in report_text


class TestTheReportSaysWhatItMeasured:
    def test_states_the_regeneration_command(self, report_text: str) -> None:
        assert "Do not edit by hand" in report_text
        assert "tise_research.eval.backtest --with-model" in report_text

    def test_leads_with_the_interval_reading_not_the_point_estimate(
        self, report_text: str
    ) -> None:
        # D80. The headline is computed from `established`, so on data that cannot
        # separate the model from the bar it must say so before the point estimates.
        headline = report_text.index("## The result")
        weaker = report_text.index("By point estimate alone")
        for phrase in ("interval", "bar"):
            assert phrase in report_text[headline:weaker]

    def test_carries_the_baselines(self, report_text: str) -> None:
        # D24 makes them mandatory in every report.
        for baseline in ("majority_class", "global_base_rate", BAR_MODEL):
            assert baseline in report_text
