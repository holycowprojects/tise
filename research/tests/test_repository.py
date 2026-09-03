"""What the repository itself must never contain.

T17 asks for "secret scanning". The generic kind — AWS keys, GitHub tokens — is here and
costs nothing, but it is not what this repository is actually at risk of leaking. Tise has
no credentials. What it has is a copy of one person's browsing, and invariant 5 says none
of it is ever committed.

That invariant has been enforced by `.gitignore` and by remembering. `.gitignore` is a
list of patterns someone has to have thought of in advance, and D97 records the time it
was not: running `analysis/history_shape.py` from `research/` wrote a fresh copy of the
live Chrome history to `research/data/`, which the anchored `/data/` rule did not cover.
Nothing except noticing stood between that file and a commit.

So this asks the other question. Not *is it ignored* but **is it tracked** — because
`git ls-files` is the truth about what would be published, and an ignore rule is only a
prediction about it. It runs in both suites' worth of places: locally on every
`uv run pytest`, and in CI before anything is merged.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Paths that must never be tracked, and why each one is here.
#:
#: Anchored deliberately. `.gitignore` carries a comment explaining that a bare `data/`
#: would also swallow the source package `research/tise_research/data/`, and the first
#: draft of this guard made exactly that mistake and flagged seven source files. The
#: anchoring is pinned by its own test below so the lesson does not have to be relearnt.
FORBIDDEN_PATHS = (
    (r"^data/", "the local corpus: a copy of a real person's browsing"),
    (r"\.sqlite3?$|\.db$", "a browser history database"),
    (r"\.copy(-wal|-shm)?$", "a copy of a live history database, wherever it landed"),
    (r"tise-export-.*\.json$", "an export is a profile of a person"),
    (r"history-shape-domains-", "a ranked domain list is a profile of a person"),
    (r"/ss_t[ta]", "verification screenshots taken on a real profile"),
    (r"\.local\.md$", "local working notes, never published"),
    (r"^\.env|\.key$|\.pem$", "credentials"),
)

#: Credential shapes. Present for completeness rather than because this project has any:
#: a repository that never holds a secret is exactly the one where a stray token would go
#: unnoticed, because nobody is looking.
SECRET_SHAPES = (
    (r"AKIA[0-9A-Z]{16}", "AWS access key id"),
    (r"ghp_[A-Za-z0-9]{36}", "GitHub personal access token"),
    (r"github_pat_[A-Za-z0-9_]{40,}", "GitHub fine-grained token"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private key"),
    (r"xox[baprs]-[A-Za-z0-9-]{12,}", "Slack token"),
    (r"AIza[0-9A-Za-z_\-]{35}", "Google API key"),
    (r"\bsk-[A-Za-z0-9]{32,}", "OpenAI-style API key"),
)

#: This file names every shape it looks for, so it cannot scan itself — the same reason
#: `privacy.test.ts` strips comments before its own source scan. Nothing else is exempt.
SCAN_EXEMPT = {"research/tests/test_repository.py"}

TEXT_SUFFIXES = {
    ".py", ".ts", ".js", ".json", ".md", ".yml", ".yaml", ".html", ".css", ".txt",
    ".toml", ".cfg", ".ini", ".sh", ".gitignore", ".gitattributes", "",
}


def _tracked_files() -> list[str]:
    if shutil.which("git") is None:
        pytest.skip("git is not on PATH, so what is tracked cannot be established")
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip("not a git working tree; this guard has nothing to inspect")
    return [name for name in result.stdout.split("\0") if name]


class TestNothingForbiddenIsTracked:
    """`git ls-files` is what would be published. `.gitignore` is a guess about it."""

    def test_the_working_tree_is_a_repository_with_files_in_it(self):
        # Without this, every assertion below passes vacuously on an empty list — which
        # is precisely how a guard stops guarding without anyone noticing.
        assert len(_tracked_files()) > 100

    @pytest.mark.parametrize(
        ("pattern", "reason"), FORBIDDEN_PATHS, ids=[p for p, _ in FORBIDDEN_PATHS]
    )
    def test_no_tracked_path_matches(self, pattern: str, reason: str):
        expression = re.compile(pattern, re.IGNORECASE)
        offenders = [name for name in _tracked_files() if expression.search(name)]
        assert not offenders, f"{reason}: {offenders}"

    def test_the_data_rule_is_anchored_and_the_source_package_survives_it(self):
        """The trap this guard fell into once, kept where it can fail again.

        `research/tise_research/data/` is source code — the loaders for Chrome, Firefox
        and the corpus. An unanchored `data/` rule flags all seven files, and the
        cheapest way to make that noise stop is to weaken the rule that guards the real
        directory.
        """
        tracked = _tracked_files()
        package = [n for n in tracked if n.startswith("research/tise_research/data/")]
        assert len(package) >= 5, "the loader package should be tracked"

        expression = re.compile(r"^data/")
        assert not [n for n in package if expression.search(n)]


class TestNoCredentialShapedStringIsCommitted:
    def test_tracked_text_files_carry_no_token(self):
        offenders: list[str] = []
        for name in _tracked_files():
            if name in SCAN_EXEMPT:
                continue
            path = REPO_ROOT / name
            if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for pattern, label in SECRET_SHAPES:
                if re.search(pattern, text):
                    offenders.append(f"{name}: {label}")
        assert not offenders, offenders

    def test_the_scan_would_actually_find_one(self):
        """A scanner that has never matched anything has never been shown to work."""
        planted = "AKIA" + "ABCDEFGHIJKLMNOP"
        assert any(re.search(pattern, planted) for pattern, _ in SECRET_SHAPES)
