"""Read an export file written by the extension.

This is the only route by which browsing data reaches the research tier. There is no
server, no API and no database connection — Python reads a file the user chose to write
and chose to hand over. So the privacy feature and the research pipeline are the same
mechanism, and neither can be true without the other.

The schema string is checked and a mismatch raises. A loader that silently accepts a
format it does not understand produces a corpus that looks fine and is wrong, which is
the failure mode this project can least afford.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from tise_research.features.events import Event

__all__ = ["EXPORT_SCHEMA", "TiseExport", "load_export", "parse_export"]

EXPORT_SCHEMA = "tise.export.v1"

_REQUIRED = ("schema", "exportedAt", "events")


@dataclass(frozen=True, slots=True)
class TiseExport:
    """An export, with the metadata a benchmark needs to be reproducible."""

    exported_at: datetime
    extension_version: str
    #: Which map produced these categories. A benchmark without this is unrepeatable.
    category_map_version: int
    suffix_list_version: int
    session_timeout_seconds: float
    raw_retention_days: int
    overrides: dict[str, str]
    events: tuple[Event, ...]


def _parse_instant(value: str) -> datetime:
    """Parse the extension's ISO 8601. `fromisoformat` handles the `Z` from 3.11 on."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"naive timestamp in export: {value!r}")
    return parsed


def parse_export(raw: dict[str, Any]) -> TiseExport:
    """Validate and convert. Pure — takes parsed JSON, touches no filesystem."""
    missing = [key for key in _REQUIRED if key not in raw]
    if missing:
        raise ValueError(f"export is missing required keys: {missing}")

    if raw["schema"] != EXPORT_SCHEMA:
        raise ValueError(
            f"unsupported export schema {raw['schema']!r}; this loader reads "
            f"{EXPORT_SCHEMA!r}. Refusing rather than guessing."
        )

    events = []
    for index, row in enumerate(raw["events"]):
        try:
            events.append(
                Event(
                    event_id=str(row["eventId"]),
                    occurred_at=_parse_instant(str(row["occurredAt"])),
                    domain=str(row["domain"]),
                    category=str(row["category"]),
                    transition=str(row["transition"]),
                    dwell_seconds=row["dwellSeconds"],
                    source=str(row["source"]),
                )
            )
        except (KeyError, ValueError) as error:
            raise ValueError(f"event {index} is malformed: {error}") from error

    # `sessionId` is deliberately dropped. Session ids are locally assigned and opaque
    # (D36); the research tier re-derives sessions from timestamps with `sessionise`, and
    # carrying the extension's ids across would invite a comparison that must never be
    # made.
    return TiseExport(
        exported_at=_parse_instant(str(raw["exportedAt"])),
        extension_version=str(raw.get("extensionVersion", "unknown")),
        category_map_version=int(raw.get("categoryMapVersion", 0)),
        suffix_list_version=int(raw.get("suffixListVersion", 0)),
        session_timeout_seconds=float(raw.get("sessionTimeoutSeconds", 0)),
        raw_retention_days=int(raw.get("rawRetentionDays", 0)),
        overrides={str(k): str(v) for k, v in (raw.get("overrides") or {}).items()},
        events=tuple(sorted(events, key=lambda event: (event.occurred_at, event.event_id))),
    )


def load_export(path: Path) -> TiseExport:
    return parse_export(json.loads(path.read_text(encoding="utf-8")))


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarise an extension export.")
    parser.add_argument("--export", type=Path, required=True, help="path to the JSON export")
    args = parser.parse_args()

    export = load_export(args.export)
    categories = Counter(event.category for event in export.events)
    sources = Counter(event.source for event in export.events)

    print(f"schema           {EXPORT_SCHEMA}")
    print(f"exported         {export.exported_at.isoformat()}")
    print(f"extension        {export.extension_version}")
    print(f"category map     v{export.category_map_version}")
    print(f"suffix list      v{export.suffix_list_version}")
    print(f"session timeout  {export.session_timeout_seconds:g}s")
    print(f"raw retention    {export.raw_retention_days} days")
    print(f"overrides        {len(export.overrides)}")
    print(f"events           {len(export.events):,}")

    if export.events:
        first = export.events[0].occurred_at
        last = export.events[-1].occurred_at
        span_days = (last - first).total_seconds() / 86400
        print(f"span             {first.date()} to {last.date()} ({span_days:.1f} days)")
        print(f"sources          {dict(sources)}")
        print("categories")
        for category, count in categories.most_common():
            share = count / len(export.events)
            print(f"  {category:<12} {count:>7,}  {share:>6.1%}")

    # Every event carries dwell_seconds=None by D35. Say so rather than let a reader
    # assume the `full` compat class is available from an export.
    with_dwell = sum(1 for event in export.events if event.dwell_seconds is not None)
    # ASCII only: a Windows console in cp1252 turns an em dash into a replacement char,
    # and a tool that mangles its own output invites doubt about the numbers next to it.
    print(f"\nevents with dwell time: {with_dwell} (D35 - the API cannot supply it)")


if __name__ == "__main__":
    main()
