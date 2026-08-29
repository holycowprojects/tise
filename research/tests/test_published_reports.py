"""The published benchmarks must not name a domain. Asserted, not promised.

Every writer in `analysis/` says "aggregates only" in its docstring and until now that was
the whole control. It held, but a docstring is a claim and this is the check.

**Why it matters more after D97.** `visit_engaged.py` is the first report writer that
*handles* domains: `AttentionExample` carries one so a per-domain baseline can be fitted, and
four of `as_2`'s features read it. A ranked list of a person's domains is a profile of that
person (SPEC invariant 2), this repository is public, and the distance between "fits a
baseline on domains" and "prints the top ten" is one debugging session.

This scans what is actually committed rather than what a writer intends, so it also covers
reports whose generator has since changed and anything pasted in by hand.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = REPO_ROOT / "docs" / "benchmarks"

#: A bare host, e.g. `youtube.com`. Deliberately broad: it is easier to allow a false
#: positive by name below than to discover a real one after publishing.
DOMAIN = re.compile(
    r"\b[a-z0-9][a-z0-9-]{1,40}\."
    r"(?:com|org|net|io|co|dev|ai|gov|edu|in|uk|me|app|xyz|info|tv)\b"
)

#: Hosts that are allowed to appear because they are infrastructure, not browsing. Each
#: needs a reason; "it looked harmless" is how the first real one gets through.
ALLOWED = {
    # The Chrome Web Store and Chrome docs, if a report ever cites them.
    "chrome.google.com",
    "developer.chrome.com",
    # The project's own contact domain, which appears in the privacy policy draft.
    "holycowstudios.in",
    # Conventional placeholders. Never a real host.
    "example.com",
    "example.org",
}


def _reports() -> list[Path]:
    return sorted(BENCHMARKS.glob("*.md"))


def test_there_are_reports_to_check() -> None:
    """Guards the guard: a glob that silently matches nothing passes every test below."""
    assert len(_reports()) >= 10


@pytest.mark.parametrize("path", _reports(), ids=lambda p: p.name)
def test_no_report_names_a_domain(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    found = {match.group(0) for match in DOMAIN.finditer(text)} - ALLOWED
    assert not found, (
        f"{path.name} names {sorted(found)}. The published benchmarks are aggregates only "
        "— a ranked list of a person's domains is a profile of that person, and this "
        "repository is public (SPEC invariant 2). Add it to ALLOWED with a reason only if "
        "it is infrastructure rather than browsing."
    )


def test_the_local_domain_tables_are_not_committed() -> None:
    """`history_shape.py` writes a ranked domain table on purpose — to `data/`, gitignored.

    D98 found that the same script, run from a subdirectory, wrote one to a path no ignore
    rule covered. The rules are path-independent now; this asserts the outcome rather than
    the rule.
    """
    stray = [
        path
        for path in REPO_ROOT.rglob("history-shape-domains-*.md")
        if ".git" not in path.parts and path.parent.name != "data"
    ]
    assert not stray, f"a local-only domain table escaped data/: {stray}"
