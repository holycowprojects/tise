"""The canonical event.

Mirrors `TiseEvent` in SPEC.md field for field. The extension constructs these from live
navigation; the research tier constructs them from an exported file or from a history
database. Both produce the same shape, which is what allows the same feature code to run
over either.

Note what is **not** here: no URL, no path, no query string, no title text. The domain is
already reduced by the time an event exists, so there is no later stage at which a full
URL could be persisted by accident. That is SPEC.md invariant 2 enforced by construction
rather than by review.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

__all__ = ["Event"]


@dataclass(frozen=True, slots=True)
class Event:
    """One navigation the person chose to make."""

    event_id: str
    occurred_at: datetime
    domain: str
    category: str
    transition: str
    #: `full` compat class only. None for anything the extension could observe, because
    #: the chrome.history API does not expose dwell time. Never invent a value here.
    dwell_seconds: float | None = None
    #: "live" (observed by the extension) or "import" (read from browser history).
    source: str = "import"

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None:
            raise ValueError(
                f"{self.event_id}: naive datetime. An aware timestamp is required — a "
                "naive one compares wrongly against window_end and the leakage guard "
                "stops guarding."
            )
