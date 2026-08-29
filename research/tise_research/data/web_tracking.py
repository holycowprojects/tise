"""Read the GESIS/Respondi web tracking panel into per-person events (D99).

Kulshrestha, Oliveira, Karaçalık, Bonnay & Wagner (2021), *Web Routineness and Limits of
Predictability*, ICWSM. Data: Zenodo 10.5281/zenodo.4757574, supplied by Respondi AG,
**CC BY-NC 4.0**. 2,148 consenting German panelists, October 2018, 9,151,243 visits.

**Why this reader exists.** Every number this project has published came from one person.
This corpus is the only public source found that records **per-visit `active_seconds`** —
idle-excluded attention — for a large number of real people, which is what `visit_engaged`
is defined on. D99 fixes the whole analysis in advance; this module only turns rows into
`Event`s and makes no modelling choice that D99 did not already declare.

**One person at a time, always.** `load_events` takes a single panelist. Corpora are never
merged (D18) and neither are people: a model fitted across panelists describes someone who
does not exist. The sharding helper exists so that per-person iteration is affordable, not
so that people can be pooled.

**No URL reaches an `Event`.** The publishers already redacted the `url` column to `0`, so
SPEC invariant 2 holds at the source; this reader never reads that column regardless.

**Two fields the corpus does not have, and what is done about them.**

* **No transition type.** `Event.transition` is set to `UNKNOWN_TRANSITION` and no feature
  may read it — `as_1n`/`as_2n` exist precisely so the arrival flags are *dropped* rather
  than filled with a zero that was never measured (D51).
* **No timezone.** `used_at` is a naive local German wall clock. It is stamped with a fixed
  `+02:00` rather than a real zone, and that is deliberate: everything downstream reads
  *wall-clock* fields (`.hour`, `.weekday()`) or *gaps between consecutive visits*, and a
  fixed offset leaves both exactly as recorded. A real DST-aware zone would instead insert a
  one-hour discontinuity at 03:00 on 28 October 2018, in the middle of the observation
  window, which would fabricate a session boundary that no person experienced. `tzdata` is
  also not installed here, and adding a dependency is Akash's call, not this module's.
"""

from __future__ import annotations

import csv
import sys
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tise_research.features.events import Event

__all__ = [
    "GERMANY_OFFSET",
    "MULTI_CATEGORY_SEPARATOR",
    "UNCATEGORIZED",
    "UNKNOWN_TRANSITION",
    "count_visits_per_panelist",
    "load_category_map",
    "load_demographics",
    "load_events",
    "shard_by_panelist",
]

#: See the module docstring. A fixed offset, not a zone, and on purpose.
GERMANY_OFFSET = timezone(timedelta(hours=2))

#: The corpus has no transition column. Nothing may read this value; it exists so the field
#: is honest rather than empty.
UNKNOWN_TRANSITION = "unknown"

#: A domain may list several categories, e.g. "information-tech,media-sharing". D99 fixes
#: the rule: take the first listed. Arbitrary, declared in advance, and not revisited.
MULTI_CATEGORY_SEPARATOR = ","

#: Their own 43rd category, reused for a domain absent from the map rather than inventing a
#: label. Their taxonomy is used as given (D99) — mapping it onto Tise's fifteen would be a
#: choice made knowing what it was for.
UNCATEGORIZED = "uncategorized"

_VISIT_COLUMNS = ("panelist_id", "used_at", "active_seconds", "domain")


def _reader(path: Path):
    handle = path.open("r", encoding="utf-8", errors="replace", newline="")
    return handle, csv.DictReader(handle)


def load_category_map(path: Path) -> dict[str, str]:
    """domain -> category, taking the first of any multi-category listing (D99)."""
    mapping: dict[str, str] = {}
    handle, reader = _reader(path)
    with handle:
        for row in reader:
            domain = (row.get("domain") or "").strip().lower()
            raw = (row.get("category_names") or "").strip()
            if not domain:
                continue
            first = raw.split(MULTI_CATEGORY_SEPARATOR)[0].strip()
            mapping[domain] = first or UNCATEGORIZED
    return mapping


def load_demographics(path: Path) -> dict[str, tuple[str, str]]:
    """panelist_id -> (gender, age band). Reported alongside results, never used to select.

    Missing values stay empty strings rather than becoming "unknown": two panelists have no
    gender and 34 have no age band, and a bucket named "unknown" would quietly become a
    third gender in any breakdown.
    """
    people: dict[str, tuple[str, str]] = {}
    handle, reader = _reader(path)
    with handle:
        for row in reader:
            panelist = (row.get("panelist_id") or "").strip()
            if panelist:
                people[panelist] = (
                    (row.get("gender") or "").strip(),
                    (row.get("age_recode") or "").strip(),
                )
    return people


def count_visits_per_panelist(browsing_path: Path) -> dict[str, int]:
    """One streaming pass. Descriptive only — it is how D99's eligibility gate was set."""
    counts: dict[str, int] = {}
    handle, reader = _reader(browsing_path)
    with handle:
        for row in reader:
            panelist = (row.get("panelist_id") or "").strip()
            if panelist:
                counts[panelist] = counts.get(panelist, 0) + 1
    return counts


def shard_by_panelist(
    browsing_path: Path, *, out_dir: Path, shards: int = 64
) -> list[Path]:
    """Split the 680MB visit file into shards, each holding whole panelists.

    The file is **not** grouped by panelist — users are interleaved throughout — so a single
    streaming pass cannot yield one person at a time, and holding all 9.15M rows to group
    them needs gigabytes. Sharding on a stable hash of the id puts every row for a person in
    exactly one shard, so a shard can be loaded whole and split in memory.

    `hash()` is *not* used: it is salted per process in Python, so shards would not be
    reproducible across runs. A sum of code points is enough here — the only requirement is
    that one panelist lands in one shard, not that the shards are balanced.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [out_dir / f"shard-{index:03d}.csv" for index in range(shards)]

    handle, reader = _reader(browsing_path)
    with handle:
        handles = [path.open("w", encoding="utf-8", newline="") for path in paths]
        try:
            writers = [csv.DictWriter(h, fieldnames=_VISIT_COLUMNS) for h in handles]
            for writer in writers:
                writer.writeheader()
            for row in reader:
                panelist = (row.get("panelist_id") or "").strip()
                if not panelist:
                    continue
                index = sum(ord(character) for character in panelist) % shards
                writers[index].writerow(
                    {name: row.get(name, "") for name in _VISIT_COLUMNS}
                )
        finally:
            for h in handles:
                h.close()
    return paths


def _event(
    panelist: str,
    index: int,
    row: dict[str, str],
    categories: dict[str, str],
) -> Event | None:
    """One row to one `Event`, or None if the row cannot be trusted.

    A row is dropped rather than repaired. Every drop is counted by the caller, because a
    silent drop is a change to the denominator of every rate computed afterwards.
    """
    stamp = (row.get("used_at") or "").strip()
    raw_active = (row.get("active_seconds") or "").strip()
    domain = (row.get("domain") or "").strip().lower()
    if not stamp or not raw_active or not domain:
        return None
    try:
        occurred_at = datetime.fromisoformat(stamp).replace(tzinfo=GERMANY_OFFSET)
        dwell = float(raw_active)
    except ValueError:
        return None
    if dwell < 0.0:
        return None

    return Event(
        event_id=f"p{panelist}-{index:07d}",
        occurred_at=occurred_at,
        domain=domain,
        category=categories.get(domain, UNCATEGORIZED),
        transition=UNKNOWN_TRANSITION,
        dwell_seconds=dwell,
        source="import",
    )


def load_events(
    rows: list[dict[str, str]],
    *,
    panelist: str,
    categories: dict[str, str],
) -> tuple[list[Event], int]:
    """Events for **one** panelist, in time order, plus the count of unusable rows.

    Takes already-read rows rather than a path: the caller loads a shard once and splits it,
    which is what makes per-person iteration affordable. Returning the drop count rather
    than logging it keeps the number available to the report.
    """
    events: list[Event] = []
    dropped = 0
    for index, row in enumerate(rows):
        event = _event(panelist, index, row, categories)
        if event is None:
            dropped += 1
        else:
            events.append(event)
    events.sort(key=lambda item: (item.occurred_at, item.event_id))
    return events, dropped


def iter_panelists(
    shard_path: Path, *, categories: dict[str, str]
) -> Iterator[tuple[str, list[Event], int]]:
    """Every panelist in one shard, as (id, events, dropped rows)."""
    grouped: dict[str, list[dict[str, str]]] = {}
    handle, reader = _reader(shard_path)
    with handle:
        for row in reader:
            panelist = (row.get("panelist_id") or "").strip()
            if panelist:
                grouped.setdefault(panelist, []).append(row)

    for panelist, rows in sorted(grouped.items()):
        events, dropped = load_events(rows, panelist=panelist, categories=categories)
        yield panelist, events, dropped


def main() -> int:
    """Shard the visit file. One-time, and it writes only inside `data/`."""
    root = Path(__file__).resolve().parents[3]
    release = root / "data" / "web_routineness_release"
    browsing = release / "raw" / "browsing.csv"
    if not browsing.exists():
        print(f"not found: {browsing}", file=sys.stderr)
        return 1

    out_dir = root / "data" / "gesis-shards"
    paths = shard_by_panelist(browsing, out_dir=out_dir)
    total = sum(path.stat().st_size for path in paths)
    print(f"wrote {len(paths)} shards, {total / 1e6:,.0f} MB, to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
