"""Shared builders for the two history schemas.

These exist so that the view tests (D78) and the corpus tests measure the same fixture.
A redirect chain written two different ways in two test files is a place where one of
them can quietly stop describing the trap it was written for.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

#: Chrome PageTransition bits, spelled out so a reader does not have to decode hex.
LINK = 0
TYPED = 1
CHAIN_START = 0x1000_0000
CHAIN_END = 0x2000_0000
CLIENT_REDIRECT = 0x4000_0000
SERVER_REDIRECT = 0x8000_0000

#: D65's trace: a Google result click that redirects three times to a hotel page, then a
#: separate typed navigation a minute later. The chain **start** carries no redirect bit;
#: the page the person landed on carries two. Filtering on the redirect bits therefore
#: keeps `google.com` and throws the hotel away, which is backwards — see D78.
CHROME_REDIRECT_CHAIN: list[tuple[int, str, int, int, int]] = [
    (1, "https://www.google.com/url?url=x", LINK | CHAIN_START, 0, 13_400_000_000_000_000),
    (2, "http://zivasuites.com/", LINK | CLIENT_REDIRECT, 1, 13_400_000_000_001_000),
    (3, "https://zivasuites.com/", LINK | SERVER_REDIRECT, 2, 13_400_000_000_002_000),
    (
        4,
        "https://zivasuites.com/#b",
        LINK | CLIENT_REDIRECT | CHAIN_END,
        3,
        13_400_000_000_003_000,
    ),
    (5, "https://example.com/", TYPED | CHAIN_START | CHAIN_END, 0, 13_400_000_060_000_000),
]


#: `KEYWORD_GENERATED`, which Chromium's visibility test excludes even when CHAIN_END is
#: set. Read from the source, not inferred (D79).
KEYWORD_GENERATED = 10

#: The case that separates a **page-level** filter from a **per-visit** one.
#:
#: The distinguishing visit is 3: `shop.example/` appearing *mid-chain*, so it is not
#: visible on its own — but its page is offered anyway, because visit 1 visited it
#: normally. `getVisits()` then returns visit 3 too, so the extension is given it. A
#: per-visit filter drops it, and agrees with reality on every other fixture here, because
#: they all give each visit its own URL. That is why D78's mechanism went unnoticed, and
#: why the first attempt at this fixture failed to discriminate either: visit 3 must be
#: **not visible itself** for the two rules to disagree.
#:
#: `start.example/` is the mirror — it only ever appears as a chain start, so it is never
#: offered. `kw.example/` carries CHAIN_END and is still excluded, by core type.
CHROME_MIXED_PAGE: list[tuple[int, str, int, int, int]] = [
    (1, "https://shop.example/", TYPED | CHAIN_START | CHAIN_END, 0, 13_400_000_000_000_000),
    (2, "https://start.example/", LINK | CHAIN_START, 0, 13_400_000_100_000_000),
    (3, "https://shop.example/", LINK | CLIENT_REDIRECT, 2, 13_400_000_100_001_000),
    (
        4,
        "https://dest.example/",
        LINK | SERVER_REDIRECT | CHAIN_END,
        3,
        13_400_000_100_002_000,
    ),
    (
        5,
        "https://kw.example/",
        KEYWORD_GENERATED | CHAIN_START | CHAIN_END,
        0,
        13_400_000_200_000_000,
    ),
]

#: Firefox's version of the same discriminating case. Visit 3 is `shop.example/` reached by
#: a redirect and then redirected away from, so it is mid-chain and not visible on its own;
#: visit 1 makes the page visible, so visit 3 still comes through.
FIREFOX_MIXED_PAGE: list[tuple[int, str, int, int, int]] = [
    (1, "https://shop.example/", 2, 0, 1_780_000_000_000_000),
    (2, "https://start.example/", 1, 0, 1_780_000_100_000_000),
    (3, "https://shop.example/", 6, 2, 1_780_000_100_001_000),
    (4, "https://dest.example/", 5, 3, 1_780_000_100_002_000),
]


#: The same chain in Firefox's vocabulary. The redirect type sits on the visit that was
#: redirected *to*, which is the opposite end of the chain from Chrome — so dropping the
#: redirect types here throws away the landing page too, by a different route.
FIREFOX_REDIRECT_CHAIN: list[tuple[int, str, int, int, int]] = [
    (1, "https://www.google.com/url?url=x", 1, 0, 1_780_000_000_000_000),
    (2, "http://zivasuites.com/", 6, 1, 1_780_000_000_001_000),
    (3, "https://zivasuites.com/", 5, 2, 1_780_000_000_002_000),
    (4, "https://example.com/", 2, 0, 1_780_000_060_000_000),
]


def write_chrome_history(path: Path, rows: list[tuple[int, str, int, int, int]]) -> None:
    """Build a minimal Chrome history database. Rows are (id, url, transition, from, us)."""
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE urls (id INTEGER PRIMARY KEY, url TEXT, title TEXT, "
        "visit_count INTEGER, typed_count INTEGER, last_visit_time INTEGER, hidden INTEGER)"
    )
    connection.execute(
        "CREATE TABLE visits (id INTEGER PRIMARY KEY, url INTEGER, visit_time INTEGER, "
        "from_visit INTEGER, transition INTEGER, visit_duration INTEGER)"
    )
    for visit_id, url, transition, from_visit, visit_us in rows:
        connection.execute(
            "INSERT INTO urls VALUES (?, ?, '', 1, 0, ?, 0)", (visit_id, url, visit_us)
        )
        connection.execute(
            "INSERT INTO visits VALUES (?, ?, ?, ?, ?, 0)",
            (visit_id, visit_id, visit_us, from_visit, transition),
        )
    connection.commit()
    connection.close()


def write_firefox_places(path: Path, rows: list[tuple[int, str, int, int, int]]) -> None:
    """Minimal `places.sqlite`. Rows are (id, url, visit_type, from_visit, micros)."""
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE moz_places (id INTEGER PRIMARY KEY, url TEXT)")
    connection.execute(
        "CREATE TABLE moz_historyvisits (id INTEGER PRIMARY KEY, from_visit INTEGER, "
        "place_id INTEGER, visit_date INTEGER, visit_type INTEGER)"
    )
    for visit_id, url, visit_type, from_visit, micros in rows:
        connection.execute("INSERT INTO moz_places VALUES (?, ?)", (visit_id, url))
        connection.execute(
            "INSERT INTO moz_historyvisits VALUES (?, ?, ?, ?, ?)",
            (visit_id, from_visit, visit_id, micros, visit_type),
        )
    connection.commit()
    connection.close()
