"""Read Chrome's history database.

Two things about this file bite everyone who touches it:

1. **It is locked while Chrome is running.** Copy it first, read the copy. This module
   never opens the original for anything but a byte copy.
2. **Timestamps are microseconds since 1601-01-01 UTC** (the WebKit epoch), not Unix.
   Treating a Chrome timestamp as Unix puts every visit in the year 15,000-odd and every
   gap becomes nonsense.

**The duration trap.** `visits.visit_duration` exists here and does *not* exist in the
`chrome.history` extension API. Anything computed from `duration_seconds` belongs to the
`full` compat class and can never ship. See SPEC.md.
"""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

__all__ = [
    "SECONDS_1601_TO_1970",
    "Visit",
    "copy_history_db",
    "datetime_to_webkit",
    "default_history_path",
    "is_redirect",
    "load_visits",
    "registrable_domain",
    "transition_core",
    "webkit_to_datetime",
]

# 369 years, including 89 leap days, between 1601-01-01 and 1970-01-01.
SECONDS_1601_TO_1970 = 11_644_473_600

_WEBKIT_EPOCH = datetime(1601, 1, 1, tzinfo=UTC)

# Chrome packs qualifier flags into the high bits of `visits.transition`; the core
# navigation type is the low byte. Values from Chrome's PageTransition enum.
_TRANSITION_CORE = {
    0: "link",
    1: "typed",
    2: "auto_bookmark",
    3: "auto_subframe",
    4: "manual_subframe",
    5: "generated",
    6: "start_page",
    7: "form_submit",
    8: "reload",
    9: "keyword",
    10: "keyword_generated",
}

# Subframe navigations are the page loading its own parts, not a person choosing to go
# somewhere. Counting them inflates visit counts and destroys the gap distribution.
SUBFRAME_TRANSITIONS = frozenset({"auto_subframe", "manual_subframe"})

# Chrome's PageTransition qualifier bits for redirects. A redirect hop is recorded as a
# visit, but nobody chose to go there — a link-shortener, an auth bounce, an ad tracker.
# They arrive milliseconds apart, so counting them fills the gap distribution with
# sub-second entries and buries the within-session mode.
CLIENT_REDIRECT = 0x4000_0000
SERVER_REDIRECT = 0x8000_0000
REDIRECT_MASK = CLIENT_REDIRECT | SERVER_REDIRECT

# --- Provisional public suffix handling -------------------------------------------
#
# PROVISIONAL (T1 only). A real Public Suffix List decision is owed at T2/T6, because
# the extension needs the identical reduction in TypeScript and this function is
# parity-critical: if TS and Python disagree on one domain, every benchmark drifts.
# Adding a PSL dependency is an "ask first" item, so T1 measures with an embedded list
# and reports how many domains fall outside it.
_MULTI_PART_SUFFIXES = frozenset(
    {
        "co.uk", "org.uk", "ac.uk", "gov.uk", "me.uk", "net.uk", "sch.uk",
        "co.in", "net.in", "org.in", "gen.in", "firm.in", "ind.in", "res.in",
        "ac.in", "edu.in", "gov.in", "nic.in",
        "com.au", "net.au", "org.au", "edu.au", "gov.au",
        "co.jp", "ne.jp", "or.jp", "ac.jp", "go.jp",
        "com.br", "com.cn", "net.cn", "org.cn", "gov.cn", "edu.cn",
        "co.nz", "net.nz", "org.nz", "co.za", "org.za",
        "com.sg", "com.my", "com.hk", "com.tw", "com.ph", "com.vn",
        "co.kr", "co.id", "or.id", "ac.id", "co.th", "in.th",
        "com.mx", "com.ar", "com.co", "com.pe", "com.tr", "com.sa", "com.eg",
        "com.pk", "com.bd", "com.lk", "com.np", "co.il", "co.ke", "com.ng",
        "com.ua", "com.ru", "co.ve",
        "github.io", "gitlab.io", "pages.dev", "workers.dev", "vercel.app",
        "netlify.app", "web.app", "firebaseapp.com", "herokuapp.com",
        "s3.amazonaws.com", "blob.core.windows.net",
    }
)

_WEB_SCHEMES = frozenset({"http", "https"})


def webkit_to_datetime(microseconds: int) -> datetime:
    """Convert a Chrome timestamp to a timezone-aware UTC datetime.

    Always aware. A naive datetime compares wrongly against `window_end` and the
    leakage guard silently stops guarding.
    """
    return _WEBKIT_EPOCH + timedelta(microseconds=microseconds)


def datetime_to_webkit(value: datetime) -> int:
    """Convert a datetime back to a Chrome timestamp. Inverse of `webkit_to_datetime`."""
    if value.tzinfo is None:
        raise ValueError("refusing a naive datetime: attach a timezone first")
    delta = value.astimezone(UTC) - _WEBKIT_EPOCH
    return round(delta.total_seconds() * 1_000_000)


def transition_core(raw: int) -> str:
    """The core navigation type, with Chrome's qualifier flags masked off."""
    return _TRANSITION_CORE.get(raw & 0xFF, "unknown")


def is_redirect(raw: int) -> bool:
    """Whether this visit is a redirect hop rather than a chosen navigation."""
    return bool(raw & REDIRECT_MASK)


def _is_ip_literal(host: str) -> bool:
    if ":" in host:  # urlsplit already stripped the IPv6 brackets
        return True
    parts = host.split(".")
    return len(parts) == 4 and all(p.isdigit() for p in parts)


def registrable_domain(url: str) -> str | None:
    """Reduce a URL to its registrable domain, or None if it is not web browsing.

    This is where SPEC.md invariant 2 is enforced: the path, query string and fragment
    are discarded *here*, before any event object exists, so there is no later stage at
    which they could be persisted by accident.

    Returns None for non-web schemes, localhost and IP literals. Those are not browsing
    behaviour, and `file://` URLs are private paths.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return None

    if parts.scheme.lower() not in _WEB_SCHEMES:
        return None

    host = parts.hostname  # lowercased, port stripped, IPv6 brackets removed
    if not host:
        return None
    if host == "localhost" or host.endswith(".localhost"):
        return None
    if _is_ip_literal(host):
        return None

    labels = host.strip(".").split(".")
    if len(labels) < 2:
        return None

    if ".".join(labels[-2:]) in _MULTI_PART_SUFFIXES:
        # The two-label suffix is public, so the registrable domain needs a third label.
        return ".".join(labels[-3:]) if len(labels) >= 3 else None

    return ".".join(labels[-2:])


def default_history_path() -> Path:
    """Chrome's default-profile history database on Windows."""
    local_app_data = Path.home() / "AppData" / "Local"
    return local_app_data / "Google" / "Chrome" / "User Data" / "Default" / "History"


def copy_history_db(source: Path, dest: Path) -> Path:
    """Copy the locked history database (and its WAL sidecars) so it can be read.

    The source is opened for reading only and is never modified. Sidecars are copied
    because unflushed recent visits live in the write-ahead log, and omitting them
    silently truncates the most recent days.
    """
    if not source.exists():
        raise FileNotFoundError(f"no Chrome history database at {source}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    for suffix in ("-wal", "-shm"):
        sidecar = source.with_name(source.name + suffix)
        if sidecar.exists():
            shutil.copy2(sidecar, dest.with_name(dest.name + suffix))
    return dest


@dataclass(frozen=True, slots=True)
class Visit:
    """One navigation, already reduced to a domain. No URL survives this boundary."""

    visited_at: datetime
    domain: str
    transition: str
    #: `full` compat class only — the chrome.history API cannot provide this.
    duration_seconds: float | None


_VISITS_QUERY = """
SELECT v.visit_time, v.transition, v.visit_duration, u.url
FROM visits AS v
JOIN urls AS u ON u.id = v.url
ORDER BY v.visit_time
"""


def load_visits(
    db_path: Path,
    *,
    exclude_subframes: bool = True,
    exclude_redirects: bool = True,
) -> list[Visit]:
    """Read every visit from a *copy* of the history database.

    Returns visits in chronological order, reduced to registrable domains. Visits whose
    URL is not web browsing (extension pages, `file://`, localhost) are dropped.

    Subframes and redirect hops are excluded by default because neither is a person
    deciding to go somewhere, and both distort the gap distribution the session boundary
    is derived from.
    """
    uri = f"file:{db_path.as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        rows: Iterator[tuple[int, int, int, str]] = connection.execute(_VISITS_QUERY)
        visits: list[Visit] = []
        for visit_time, raw_transition, raw_duration, url in rows:
            domain = registrable_domain(url)
            if domain is None:
                continue
            if exclude_redirects and is_redirect(raw_transition):
                continue
            transition = transition_core(raw_transition)
            if exclude_subframes and transition in SUBFRAME_TRANSITIONS:
                continue
            visits.append(
                Visit(
                    visited_at=webkit_to_datetime(visit_time),
                    domain=domain,
                    transition=transition,
                    # 0 means "not recorded", which is an absence, not a zero-second dwell.
                    duration_seconds=(raw_duration / 1_000_000) if raw_duration > 0 else None,
                )
            )
    finally:
        connection.close()

    return visits
