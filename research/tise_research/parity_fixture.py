"""Build the parity fixture — the oracle TypeScript must reproduce exactly.

    uv run python -m tise_research.parity_fixture

Writes `research/fixtures/parity_events.json` (input) and `parity_expected.json`
(Python's answer). At T9 the TypeScript implementation runs over the same input and its
output is compared to the same expected file. If they disagree, one of them is wrong and
the build stops.

**The events are synthetic and hand-designed, never real browsing.** Two reasons: this
file is committed and public, and a fixture must exercise the exact boundaries a real
history rarely contains — a gap landing precisely on the session timeout, a recurrence
landing precisely on the horizon. SPEC.md permits synthetic data as a test fixture and
forbids it as a benchmark; this is the permitted use.

Every case below is here on purpose:

* a gap of exactly the timeout, which must **not** split a session
* a gap one second longer, which must
* several categories inside one session
* a domain resolved by the map, one by a keyword rule, one overridden by the user, and
  one that resolves to `unknown`
* a recurrence inside the horizon and one outside it
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from tise_research.categories import load_category_map
from tise_research.features.events import Event
from tise_research.features.labels import return_24h_labels
from tise_research.features.recency import FEATURE_SET, hours_since_last_seen
from tise_research.features.resolver import resolve
from tise_research.features.sessions import sessionise

#: research/tise_research/parity_fixture.py -> repo root is three parents up.
REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "research" / "fixtures"

TIMEOUT_SECONDS = 1800.0
HORIZON_HOURS = 24.0

#: `nothing-here.example` would resolve to `unknown`; the override must win.
OVERRIDES = {"nothing-here.example": "work"}


def _at(day: int, hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(2026, 6, day, hour, minute, second, tzinfo=UTC)


#: (occurred_at, domain). Order is deliberate; the pipeline sorts anyway.
RAW_EVENTS: list[tuple[datetime, str]] = [
    # --- session 1: three events, including a gap of EXACTLY the timeout -------------
    (_at(1, 9, 0), "youtube.com"),          # map -> video
    (_at(1, 9, 20), "youtube.com"),         # +20m, same session
    (_at(1, 9, 50), "google.com"),          # +30m exactly -> still the same session
    # --- session 2: starts one second past the timeout ------------------------------
    (_at(1, 10, 20, 1), "github.com"),      # +30m01s -> new session
    (_at(1, 10, 25), "someministry.gov.in"),  # keyword rule -> government
    (_at(1, 10, 30), "nothing-here.example"),  # override -> work
    (_at(1, 10, 35), "personal-site.example"),  # nothing matches -> unknown
    # --- session 3: next day, inside the 24h horizon of session 1 -------------------
    (_at(2, 9, 0), "youtube.com"),
    (_at(2, 9, 5), "google.com"),
    # --- session 4: two days later, OUTSIDE the horizon of session 2 ----------------
    (_at(3, 12, 0), "github.com"),
]


def build_events() -> list[Event]:
    category_map = load_category_map()
    events: list[Event] = []
    for index, (occurred_at, domain) in enumerate(RAW_EVENTS):
        resolution = resolve(domain, category_map=category_map, overrides=OVERRIDES)
        events.append(
            Event(
                event_id=f"evt-{index:03d}",
                occurred_at=occurred_at,
                domain=domain,
                category=resolution.category,
                transition="link",
                dwell_seconds=None,
                source="import",
            )
        )
    return events


def build_input_document() -> dict:
    """The input side. Deliberately carries **no category** — resolving the domain is
    part of what parity checks, so handing TypeScript the answer would defeat it."""
    return {
        "note": [
            "Parity fixture INPUT. Synthetic, hand-designed, never real browsing.",
            "TypeScript must reproduce parity_expected.json from exactly this.",
            "Events carry no category: resolving the domain is part of what is compared.",
            "Regenerate with: uv run python -m tise_research.parity_fixture",
        ],
        "categoryMapVersion": load_category_map().version,
        "timeoutSeconds": TIMEOUT_SECONDS,
        "horizonHours": HORIZON_HOURS,
        "overrides": OVERRIDES,
        "events": [
            {
                "eventId": f"evt-{index:03d}",
                "occurredAt": occurred_at.isoformat(),
                "domain": domain,
                "transition": "link",
                "dwellSeconds": None,
                "source": "import",
            }
            for index, (occurred_at, domain) in enumerate(RAW_EVENTS)
        ],
    }


def build_expected_document() -> dict:
    category_map = load_category_map()
    events = build_events()

    resolutions = []
    for _, domain in RAW_EVENTS:
        resolution = resolve(domain, category_map=category_map, overrides=OVERRIDES)
        entry = {
            "domain": domain,
            "category": resolution.category,
            "source": resolution.source,
        }
        if entry not in resolutions:
            resolutions.append(entry)

    sessions = [
        {
            "sessionId": session.session_id,
            "startedAt": session.started_at.isoformat(),
            "endedAt": session.ended_at.isoformat(),
            "durationSeconds": session.duration_seconds,
            "eventIds": [event.event_id for event in session.events],
            "categories": sorted(session.categories),
        }
        for session in sessionise(events, timeout_seconds=TIMEOUT_SECONDS)
    ]

    labels = [
        {
            "target": label.target,
            "subject": label.subject,
            "windowEnd": label.window_end.isoformat(),
            "outcome": label.outcome,
            "horizonHours": label.horizon_hours,
            "sessionId": label.session_id,
        }
        for label in return_24h_labels(
            events, timeout_seconds=TIMEOUT_SECONDS, horizon_hours=HORIZON_HOURS
        )
    ]

    # One feature row per label, aligned by index. This is the shape the model consumes:
    # a vector computed at the instant its label became decidable, and never after.
    label_objects = return_24h_labels(
        events, timeout_seconds=TIMEOUT_SECONDS, horizon_hours=HORIZON_HOURS
    )
    features = [
        {
            "subject": label.subject,
            "windowEnd": label.window_end.isoformat(),
            "values": {
                "hoursSinceLastSeen": hours_since_last_seen(
                    events, label.subject, window_end=label.window_end
                ),
            },
        }
        for label in label_objects
    ]

    unknown_count = sum(1 for event in events if event.category == "unknown")

    return {
        "note": [
            "Parity fixture EXPECTED OUTPUT, produced by the Python implementation.",
            "TypeScript must match this exactly. A mismatch means one side is wrong;",
            "it is never a reason to regenerate this file without understanding why.",
        ],
        "categoryMapVersion": category_map.version,
        "timeoutSeconds": TIMEOUT_SECONDS,
        "horizonHours": HORIZON_HOURS,
        "featureSet": FEATURE_SET,
        "resolutions": resolutions,
        "sessions": sessions,
        "labels": labels,
        "features": features,
        "summary": {
            "eventCount": len(events),
            "sessionCount": len(sessions),
            "labelCount": len(labels),
            "positiveCount": sum(1 for label in labels if label["outcome"]),
            "unknownEventCount": unknown_count,
        },
    }


def _write(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {path.relative_to(REPO_ROOT)}")


def main() -> int:
    _write(FIXTURE_DIR / "parity_events.json", build_input_document())
    expected = build_expected_document()
    _write(FIXTURE_DIR / "parity_expected.json", expected)

    summary = expected["summary"]
    print(
        f"  {summary['eventCount']} events -> {summary['sessionCount']} sessions -> "
        f"{summary['labelCount']} labels ({summary['positiveCount']} positive)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
