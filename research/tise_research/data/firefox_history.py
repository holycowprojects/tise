"""Read Firefox's `places.sqlite` history database.

Firefox is not Chromium and nothing transfers:

* **Timestamps are microseconds since the Unix epoch**, not the WebKit 1601 epoch.
  Reusing the Chrome conversion puts every visit in the wrong millennium.
* Visits are `moz_historyvisits` joined to `moz_places` on `place_id`.
* Redirects and subframes are distinct `visit_type` values, not bit flags.
* **The redirect flag sits on the opposite end of the chain.** Chrome marks the hops;
  Firefox marks the visit that was redirected *to*, so a landing page reached through a
  301 carries `redirect_permanent`. Dropping those types therefore keeps the plumbing and
  discards the page the person landed on — the same inversion D78 found in the Chromium
  reader, arrived at from the other direction. There is no chain-end bit here, so it is
  reconstructed: a visit is a chain end when no redirect visit points back at it.
* **There is no duration column at all.** Firefox is `history`-class throughout — which
  makes it, incidentally, an honest preview of what the shipped extension actually sees.

Schema and `visit_type` values were verified against a real database, not recalled.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tise_research.data.chrome_history import (
    DEFAULT_VIEW,
    Visit,
    VisitView,
    registrable_domain,
)

__all__ = [
    "default_places_path",
    "is_download",
    "is_redirect",
    "is_subframe",
    "load_visits",
    "unix_micros_to_datetime",
    "visit_type_name",
]

_UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)

# nsINavHistoryService transition constants. Names deliberately match the Chromium
# parser's vocabulary so the two browsers' outputs can be compared directly.
_VISIT_TYPES = {
    1: "link",
    2: "typed",
    3: "auto_bookmark",
    4: "auto_subframe",
    5: "redirect_permanent",
    6: "redirect_temporary",
    7: "download",
    8: "manual_subframe",
    9: "reload",
}

REDIRECT_TYPES = frozenset({5, 6})
SUBFRAME_TYPES = frozenset({4, 8})
DOWNLOAD_TYPE = 7


def unix_micros_to_datetime(microseconds: int) -> datetime:
    """Convert a Firefox timestamp to a timezone-aware UTC datetime."""
    return _UNIX_EPOCH + timedelta(microseconds=microseconds)


def visit_type_name(raw: int) -> str:
    """Human-readable transition name, sharing the Chromium parser's vocabulary."""
    return _VISIT_TYPES.get(raw, "unknown")


def is_redirect(raw: int) -> bool:
    """Whether this visit is a redirect hop rather than a chosen navigation."""
    return raw in REDIRECT_TYPES


def is_subframe(raw: int) -> bool:
    """Whether this visit is a page loading its own parts."""
    return raw in SUBFRAME_TYPES


def is_download(raw: int) -> bool:
    """Downloads are not page views.

    Chromium records no equivalent transition, so excluding them keeps both browsers'
    definition of "a visit" the same — which is the only thing that makes the
    cross-browser comparison meaningful.
    """
    return raw == DOWNLOAD_TYPE


def default_places_path() -> Path | None:
    """Locate the default profile's `places.sqlite`, or None if Firefox is not present.

    Checks the classic installer location and the Microsoft Store package, which buries
    the profile under `Packages/Mozilla.Firefox_*/LocalCache/Roaming/`. Where several
    profiles exist, the most recently modified wins.
    """
    roots: list[Path] = []

    appdata = os.environ.get("APPDATA")
    if appdata:
        roots.append(Path(appdata) / "Mozilla" / "Firefox" / "Profiles")

    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        packages = Path(local_appdata) / "Packages"
        if packages.is_dir():
            roots.extend(
                package / "LocalCache" / "Roaming" / "Mozilla" / "Firefox" / "Profiles"
                for package in packages.glob("Mozilla.Firefox_*")
            )

    candidates = [
        found
        for root in roots
        if root.is_dir()
        for found in root.glob("*/places.sqlite")
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


_VISITS_QUERY = """
SELECT v.id, v.from_visit, v.visit_date, v.visit_type, p.url
FROM moz_historyvisits AS v
JOIN moz_places AS p ON p.id = v.place_id
ORDER BY v.visit_date
"""

_REDIRECT_SOURCES_QUERY = f"""
SELECT DISTINCT from_visit FROM moz_historyvisits
WHERE from_visit != 0 AND visit_type IN ({",".join(str(t) for t in sorted(REDIRECT_TYPES))})
"""


def _redirect_sources(connection: sqlite3.Connection) -> set[int]:
    """Visits that something was redirected away from — every link in a chain but the last.

    Firefox has no chain-end bit, so this is the reconstruction. A visit nothing redirects
    away from is where the person ended up, which is the only thing the shipped extension
    would ever be told about on Chromium (D78).
    """
    return {row[0] for row in connection.execute(_REDIRECT_SOURCES_QUERY)}


def load_visits(
    db_path: Path,
    *,
    view: VisitView = DEFAULT_VIEW,
    exclude_subframes: bool = True,
    exclude_downloads: bool = True,
) -> list[Visit]:
    """Read every visit from a *copy* of `places.sqlite`.

    Returns the same `Visit` objects the Chromium parser produces, with
    `duration_seconds` always None — Firefox does not record it, and neither does the
    `chrome.history` API the extension has to use.

    `view` means what it means in the Chromium reader, so the two corpora stay
    comparable. Tise does not run on Firefox, so `shipped` here is not what any product
    saw; it is the same *definition of a visit*, which is what cross-corpus fold counts
    need in order to mean anything.
    """
    uri = f"file:{db_path.as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        redirect_sources = _redirect_sources(connection) if view == "shipped" else set()
        rows: list[tuple[int, int, int, int, str]] = list(connection.execute(_VISITS_QUERY))
    finally:
        connection.close()

    # URL-level, matching Chromium's `search()` (D79): a page is offered when at least
    # one of its visits is visible, and then all of its visits come through.
    visible_urls = (
        {
            url
            for visit_id, _, _, raw_type, url in rows
            if visit_id not in redirect_sources and not is_subframe(raw_type)
        }
        if view == "shipped"
        else set()
    )

    visits: list[Visit] = []
    for _visit_id, _from_visit, visit_date, raw_type, url in rows:
        domain = registrable_domain(url)
        if domain is None:
            continue
        if view == "shipped" and url not in visible_urls:
            continue
        if view == "chosen" and is_redirect(raw_type):
            continue
        if exclude_subframes and is_subframe(raw_type):
            continue
        if exclude_downloads and is_download(raw_type):
            continue
        visits.append(
            Visit(
                visited_at=unix_micros_to_datetime(visit_date),
                domain=domain,
                transition=visit_type_name(raw_type),
                duration_seconds=None,  # Firefox records none. Never invent one.
            )
        )

    return visits
