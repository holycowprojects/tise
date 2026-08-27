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

__all__ = [
    "EXPORT_SCHEMA",
    "SUPPORTED_SCHEMAS",
    "ExportedPrediction",
    "TiseExport",
    "load_export",
    "parse_export",
]

#: What the extension writes today.
EXPORT_SCHEMA = "tise.export.v2"

#: What this loader will read. v2 added `predictions`; a v1 file is a v2 file without them,
#: so it is still readable and loads with an empty tuple. Accepting v1 is a deliberate
#: promise rather than an accident of parsing — someone who exported their browsing months
#: ago should not find the file unreadable because a later version added a key.
SUPPORTED_SCHEMAS = ("tise.export.v1", "tise.export.v2")

_REQUIRED = ("schema", "exportedAt", "events")


@dataclass(frozen=True, slots=True)
class ExportedPrediction:
    """One row of the prediction registry, as the extension recorded it.

    `outcome` is `"pending"`, `"hit"`, `"miss"` or `"expired"`. **`expired` is not a miss**
    — it means the window closed while Tise was not watching, so nothing was measured, and
    anything scoring these must exclude them rather than counting them as negatives. That
    is D52's rule in a new place, and it is the one thing about this record that a reader
    is most likely to get wrong.
    """

    prediction_id: str
    created_at: datetime
    target: str
    subject: str
    probability: float
    window_start: datetime
    window_end: datetime
    abstained: bool
    model_name: str
    model_version: str
    feature_set: str
    data_cutoff: datetime
    evidence: tuple[str, ...]
    outcome: str
    resolved_at: datetime | None

    @property
    def scoreable(self) -> bool:
        """Only `hit` and `miss` are measurements. See the note on `outcome`."""
        return self.outcome in ("hit", "miss")


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
    #: Empty for a v1 export, which predates the registry.
    predictions: tuple[ExportedPrediction, ...] = ()
    schema: str = EXPORT_SCHEMA


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

    if raw["schema"] not in SUPPORTED_SCHEMAS:
        raise ValueError(
            f"unsupported export schema {raw['schema']!r}; this loader reads "
            f"{SUPPORTED_SCHEMAS!r}. Refusing rather than guessing."
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

    predictions = []
    for index, row in enumerate(raw.get("predictions") or []):
        try:
            resolved = row["resolvedAt"]
            predictions.append(
                ExportedPrediction(
                    prediction_id=str(row["predictionId"]),
                    created_at=_parse_instant(str(row["createdAt"])),
                    target=str(row["target"]),
                    subject=str(row["subject"]),
                    probability=float(row["probability"]),
                    window_start=_parse_instant(str(row["windowStart"])),
                    window_end=_parse_instant(str(row["windowEnd"])),
                    abstained=bool(row["abstained"]),
                    model_name=str(row["modelName"]),
                    model_version=str(row["modelVersion"]),
                    feature_set=str(row["featureSet"]),
                    data_cutoff=_parse_instant(str(row["dataCutoff"])),
                    evidence=tuple(str(line) for line in row["evidence"]),
                    outcome=str(row["outcome"]),
                    resolved_at=None if resolved is None else _parse_instant(str(resolved)),
                )
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"prediction {index} is malformed: {error}") from error

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
        predictions=tuple(
            sorted(predictions, key=lambda row: (row.window_start, row.subject))
        ),
        schema=str(raw["schema"]),
    )


def prediction_summary(export: TiseExport) -> str:
    """Counts by outcome, with the unscoreable ones called out rather than folded in."""
    if not export.predictions:
        return "  none recorded"
    counts = Counter(row.outcome for row in export.predictions)
    abstained = sum(1 for row in export.predictions if row.abstained)
    scoreable = sum(1 for row in export.predictions if row.scoreable)
    lines = [
        f"  {outcome:<10} {count:>6,}" for outcome, count in sorted(counts.items())
    ]
    lines.append(f"  {'abstained':<10} {abstained:>6,}  (recorded, never displayed)")
    lines.append(
        f"  {'scoreable':<10} {scoreable:>6,}  (hit or miss; expired is not a miss)"
    )
    return "\n".join(lines)


def load_export(path: Path) -> TiseExport:
    return parse_export(json.loads(path.read_text(encoding="utf-8")))


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarise an extension export.")
    parser.add_argument("--export", type=Path, required=True, help="path to the JSON export")
    args = parser.parse_args()

    export = load_export(args.export)
    categories = Counter(event.category for event in export.events)
    sources = Counter(event.source for event in export.events)

    print(f"schema           {export.schema}")
    print(f"exported         {export.exported_at.isoformat()}")
    print(f"extension        {export.extension_version}")
    print(f"category map     v{export.category_map_version}")
    print(f"suffix list      v{export.suffix_list_version}")
    print(f"session timeout  {export.session_timeout_seconds:g}s")
    print(f"raw retention    {export.raw_retention_days} days")
    print(f"overrides        {len(export.overrides)}")
    print(f"events           {len(export.events):,}")
    print(f"predictions      {len(export.predictions):,}")

    print("predictions by outcome")
    print(prediction_summary(export))

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
