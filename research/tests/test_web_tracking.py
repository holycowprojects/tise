"""The GESIS reader (D99). Every event behind the replication number comes through here.

Nothing in this project is allowed to sit untested behind a published figure, and this
module makes four choices that would each be invisible if wrong: which category a
multi-category domain gets, what happens to a row that cannot be parsed, what timezone a
naive stamp is given, and which shard a panelist lands in.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from tise_research.data.web_tracking import (
    GERMANY_OFFSET,
    UNCATEGORIZED,
    UNKNOWN_TRANSITION,
    iter_panelists,
    load_category_map,
    load_demographics,
    load_events,
    shard_by_panelist,
)
from tise_research.features.vector import ARRIVAL_FEATURES, FEATURE_SETS


def _write(path: Path, header: list[str], rows: list[list[str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def _row(panelist="1", stamp="2018-10-05 22:02:38", active="10", domain="a.com"):
    return {
        "panelist_id": panelist,
        "used_at": stamp,
        "active_seconds": active,
        "domain": domain,
    }


class TestCategoryMap:
    def test_a_multi_category_domain_takes_the_first(self, tmp_path: Path) -> None:
        # D99 fixed this rule in advance precisely because it is arbitrary. Picking the
        # first is defensible; picking whichever produced a better score would not be.
        path = _write(
            tmp_path / "cats.csv",
            ["domain", "category_names"],
            [["a.com", "information-tech,media-sharing"], ["b.com", "shopping"]],
        )
        mapping = load_category_map(path)
        assert mapping["a.com"] == "information-tech"
        assert mapping["b.com"] == "shopping"

    def test_a_blank_category_becomes_uncategorized(self, tmp_path: Path) -> None:
        path = _write(tmp_path / "cats.csv", ["domain", "category_names"], [["a.com", ""]])
        assert load_category_map(path)["a.com"] == UNCATEGORIZED

    def test_domains_are_lowercased_on_both_sides(self, tmp_path: Path) -> None:
        # A case mismatch would silently send every visit to `uncategorized`, which looks
        # like a finding about the person rather than a bug in the join.
        path = _write(
            tmp_path / "cats.csv", ["domain", "category_names"], [["A.COM", "shopping"]]
        )
        mapping = load_category_map(path)
        events, _ = load_events([_row(domain="a.com")], panelist="1", categories=mapping)
        assert events[0].category == "shopping"


class TestDemographics:
    def test_missing_values_stay_empty_rather_than_becoming_a_group(
        self, tmp_path: Path
    ) -> None:
        # Two panelists have no gender and 34 no age band. A bucket called "unknown" would
        # quietly become a third gender in the breakdown D99 pre-registered.
        path = _write(
            tmp_path / "users.csv",
            ["panelist_id", "gender", "age_recode"],
            [["1", "male", "[18,24]"], ["2", "", ""]],
        )
        people = load_demographics(path)
        assert people["1"] == ("male", "[18,24]")
        assert people["2"] == ("", "")


class TestEventsFromRows:
    def test_a_usable_row_becomes_an_event(self) -> None:
        events, dropped = load_events(
            [_row()], panelist="7", categories={"a.com": "shopping"}
        )
        assert dropped == 0
        assert len(events) == 1
        event = events[0]
        assert event.domain == "a.com"
        assert event.category == "shopping"
        assert event.dwell_seconds == 10.0
        assert event.source == "import"

    def test_an_unmapped_domain_is_uncategorized_not_invented(self) -> None:
        events, _ = load_events([_row(domain="nowhere.com")], panelist="1", categories={})
        assert events[0].category == UNCATEGORIZED

    @pytest.mark.parametrize(
        "bad",
        [
            _row(stamp=""),
            _row(active=""),
            _row(domain=""),
            _row(stamp="not-a-date"),
            _row(active="not-a-number"),
            _row(active="-5"),
        ],
        ids=["no stamp", "no dwell", "no domain", "bad stamp", "bad dwell", "negative"],
    )
    def test_an_unusable_row_is_dropped_and_counted(self, bad) -> None:
        # Counted, never silently skipped: a quiet drop changes the denominator of every
        # rate computed afterwards and nothing reports it.
        events, dropped = load_events([bad], panelist="1", categories={})
        assert events == []
        assert dropped == 1

    def test_events_come_back_in_time_order(self) -> None:
        rows = [
            _row(stamp="2018-10-05 22:00:00"),
            _row(stamp="2018-10-05 08:00:00"),
            _row(stamp="2018-10-05 12:00:00"),
        ]
        events, _ = load_events(rows, panelist="1", categories={})
        assert [event.occurred_at.hour for event in events] == [8, 12, 22]

    def test_ids_are_unique_within_a_panelist(self) -> None:
        # `attention.py` indexes feature rows by event id, and 0.02% of GESIS rows share a
        # person and a second. Duplicate ids there would score one row against two labels.
        rows = [_row(stamp="2018-10-05 22:02:38") for _ in range(5)]
        events, _ = load_events(rows, panelist="1", categories={})
        assert len({event.event_id for event in events}) == len(events)


class TestTimezone:
    def test_the_wall_clock_is_preserved_exactly(self) -> None:
        # Everything downstream reads wall-clock fields. A conversion here would shift
        # hour-of-day and could move a late-night visit into the wrong weekday.
        events, _ = load_events(
            [_row(stamp="2018-10-05 22:02:38")], panelist="1", categories={}
        )
        moment = events[0].occurred_at
        assert (moment.hour, moment.minute, moment.second) == (22, 2, 38)
        assert moment.utcoffset() == GERMANY_OFFSET.utcoffset(None)

    def test_no_discontinuity_across_the_dst_change(self) -> None:
        # 28 October 2018, 03:00 local, is inside the observation window. A DST-aware zone
        # would insert a one-hour jump there and fabricate a session boundary no person
        # experienced. A fixed offset cannot.
        before, _ = load_events(
            [_row(stamp="2018-10-28 02:30:00")], panelist="1", categories={}
        )
        after, _ = load_events(
            [_row(stamp="2018-10-28 03:30:00")], panelist="1", categories={}
        )
        gap = (after[0].occurred_at - before[0].occurred_at).total_seconds()
        assert gap == 3600.0

    def test_events_are_timezone_aware(self) -> None:
        # `Event.__post_init__` refuses naive datetimes; this asserts the reader satisfies
        # it rather than relying on the exception being hit in production.
        events, _ = load_events([_row()], panelist="1", categories={})
        assert events[0].occurred_at.tzinfo is not None


class TestTransitionIsAbsent:
    def test_the_transition_is_marked_unknown(self) -> None:
        events, _ = load_events([_row()], panelist="1", categories={})
        assert events[0].transition == UNKNOWN_TRANSITION

    @pytest.mark.parametrize("feature_set", ["as_1n", "as_2n"])
    def test_the_no_transition_sets_read_no_arrival_flag(self, feature_set: str) -> None:
        """The guard that makes the reader's `UNKNOWN_TRANSITION` harmless.

        If an arrival flag ever re-entered these sets it would be computed from a constant
        placeholder — a feature that looks measured and is not, on every row, which is the
        defect D51 forbids and which no score would reveal.
        """
        assert not set(FEATURE_SETS[feature_set]) & set(ARRIVAL_FEATURES)

    @pytest.mark.parametrize("feature_set", ["as_1", "as_2"])
    def test_the_ordinary_sets_still_have_them(self, feature_set: str) -> None:
        assert set(ARRIVAL_FEATURES) <= set(FEATURE_SETS[feature_set])

    def test_dropping_arrival_flags_changes_nothing_else(self) -> None:
        # `as_1n` must be `as_1` minus three, in the original order — not a reordering,
        # which would silently swap two coefficients in any side-by-side reading.
        assert list(FEATURE_SETS["as_1n"]) == [
            name for name in FEATURE_SETS["as_1"] if name not in ARRIVAL_FEATURES
        ]
        assert list(FEATURE_SETS["as_2n"]) == [
            name for name in FEATURE_SETS["as_2"] if name not in ARRIVAL_FEATURES
        ]


class TestSharding:
    def _corpus(self, tmp_path: Path) -> Path:
        rows = [
            [str(panelist), f"2018-10-0{1 + index % 9} 10:00:00", "10", "a.com"]
            for panelist in range(30)
            for index in range(4)
        ]
        return _write(
            tmp_path / "browsing.csv",
            [
                "web_visits_id",
                "id",
                "panelist_id",
                "url",
                "used_at",
                "active_seconds",
                "domain",
            ],
            [["0", "0", r[0], "0", r[1], r[2], r[3]] for r in rows],
        )

    def test_every_panelist_lands_in_exactly_one_shard(self, tmp_path: Path) -> None:
        # The property the whole approach rests on: a person split across shards would be
        # analysed twice, each time on part of their browsing.
        shard_by_panelist(self._corpus(tmp_path), out_dir=tmp_path / "s", shards=8)
        seen: dict[str, str] = {}
        for shard in sorted((tmp_path / "s").glob("shard-*.csv")):
            with shard.open(encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    panelist = row["panelist_id"]
                    assert seen.setdefault(panelist, shard.name) == shard.name
        assert len(seen) == 30

    def test_no_row_is_lost(self, tmp_path: Path) -> None:
        shard_by_panelist(self._corpus(tmp_path), out_dir=tmp_path / "s", shards=8)
        total = 0
        for shard in (tmp_path / "s").glob("shard-*.csv"):
            with shard.open(encoding="utf-8", newline="") as handle:
                total += sum(1 for _ in csv.DictReader(handle))
        assert total == 30 * 4

    def test_sharding_is_reproducible(self, tmp_path: Path) -> None:
        """`hash()` is salted per process, so using it would give different shards on every
        run and make the corpus non-reproducible. This asserts the placement is stable."""
        corpus = self._corpus(tmp_path)
        placements = []
        for run in ("a", "b"):
            shard_by_panelist(corpus, out_dir=tmp_path / run, shards=8)
            here: dict[str, str] = {}
            for shard in sorted((tmp_path / run).glob("shard-*.csv")):
                with shard.open(encoding="utf-8", newline="") as handle:
                    for row in csv.DictReader(handle):
                        here[row["panelist_id"]] = shard.name
            placements.append(here)
        assert placements[0] == placements[1]

    def test_panelists_read_back_whole(self, tmp_path: Path) -> None:
        shard_by_panelist(self._corpus(tmp_path), out_dir=tmp_path / "s", shards=8)
        recovered = 0
        for shard in sorted((tmp_path / "s").glob("shard-*.csv")):
            for _panelist, events, dropped in iter_panelists(shard, categories={}):
                assert dropped == 0
                assert len(events) == 4
                recovered += 1
        assert recovered == 30
