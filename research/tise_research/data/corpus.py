"""Turn a history database copy into events and labels.

The one place that knows how a browser database becomes a modelling dataset. Everything
downstream takes `Event` or `Label` and never touches SQLite.

Which reader to use is decided by filename, and the two are genuinely different: Firefox
uses a Unix epoch and different tables. Getting that wrong does not raise — it silently
places every visit in the wrong millennium — so the dispatch is explicit rather than
inferred from the file's contents.
"""

from __future__ import annotations

from pathlib import Path

from tise_research.categories import CategoryMap, load_category_map
from tise_research.data import firefox_history
from tise_research.data.chrome_history import load_visits as load_chromium_visits
from tise_research.features.events import Event
from tise_research.features.labels import DEFAULT_HORIZON_HOURS, Label, return_24h_labels
from tise_research.features.resolver import resolve

__all__ = ["load_events", "load_labels"]


def _is_firefox(path: Path) -> bool:
    return "firefox" in path.stem.lower()


def load_events(
    copy_path: Path,
    *,
    category_map: CategoryMap | None = None,
    overrides: dict[str, str] | None = None,
) -> list[Event]:
    """Read a history copy and resolve every visit to a categorised event."""
    resolved_map = category_map or load_category_map()
    load = firefox_history.load_visits if _is_firefox(copy_path) else load_chromium_visits

    return [
        Event(
            event_id=f"{copy_path.stem}-{index:06d}",
            occurred_at=visit.visited_at,
            domain=visit.domain,
            category=resolve(
                visit.domain, category_map=resolved_map, overrides=overrides
            ).category,
            transition=visit.transition,
            dwell_seconds=visit.duration_seconds,
            source="import",
        )
        for index, visit in enumerate(load(copy_path))
    ]


def load_labels(
    copy_path: Path,
    *,
    timeout_seconds: float,
    horizon_hours: float = DEFAULT_HORIZON_HOURS,
    category_map: CategoryMap | None = None,
    overrides: dict[str, str] | None = None,
) -> list[Label]:
    """Read a history copy and produce `return_24h` labels."""
    events = load_events(copy_path, category_map=category_map, overrides=overrides)
    return return_24h_labels(
        events, timeout_seconds=timeout_seconds, horizon_hours=horizon_hours
    )
