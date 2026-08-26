"""Domain reduction, checked against the same fixture the extension checks itself against.

`registrable_domain` is the privacy boundary *and* the first function every feature is
computed on top of. If Python and TypeScript disagree about one URL, every session and
every feature derived from that domain drifts, and nothing else in the suite would
notice.

The full parity suite arrives at T9 for features. This file starts it early for the one
function that was already implemented twice.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tise_research.categories import SUFFIXES_PATH, load_multi_part_suffixes
from tise_research.data.chrome_history import registrable_domain

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "domain_cases.json"

_CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", _CASES, ids=lambda c: c["url"] or "<empty>")
def test_registrable_domain_matches_the_shared_fixture(case: dict[str, str | None]) -> None:
    assert registrable_domain(case["url"] or "") == case["domain"]


def test_the_extension_reads_this_same_suffix_list() -> None:
    """The file is inside `extension/`, which is the point: one file, two readers."""
    assert SUFFIXES_PATH.exists()
    assert SUFFIXES_PATH.parts[-3:] == ("src", "categories", "suffixes.json")
    assert "extension" in SUFFIXES_PATH.parts


def test_suffix_list_is_well_formed() -> None:
    suffixes = load_multi_part_suffixes()
    assert len(suffixes) > 50

    for suffix in suffixes:
        assert suffix == suffix.strip().lower(), suffix
        assert "." in suffix, suffix
        assert not suffix.startswith("."), suffix
        assert not suffix.endswith("."), suffix


def test_suffix_list_stays_sorted() -> None:
    """Sorted so that a diff to this list is readable, and duplicates are visible."""
    raw = json.loads(SUFFIXES_PATH.read_text(encoding="utf-8"))["multiPartSuffixes"]
    assert raw == sorted(raw)
    assert len(raw) == len(set(raw))


def test_the_provisional_list_admits_what_it_misses() -> None:
    """D34: this is not the Public Suffix List, and the file has to say so.

    A partial list that presents itself as complete is the kind of thing that ends up
    quoted in a benchmark. The disclaimer is part of the data.
    """
    raw = json.loads(SUFFIXES_PATH.read_text(encoding="utf-8"))
    assert "provisional" in raw
    assert "Public Suffix List" in raw["provisional"]
