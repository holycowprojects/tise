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
    (r"(^|/)Screenshots?/", "no screenshot is published, without exception (D118)"),
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

#: Personal identifiers that must never be published, named rather than shaped.
#:
#: The shapes above catch *credentials*. They cannot catch a personal email address, which
#: looks exactly like the intended contact address and is a perfectly ordinary string. D119
#: chose `office@holycowstudios.in` as the published identity precisely so the personal one
#: would not be scraped off a public repository forever — and then D119's own entry spelled
#: the personal address out, in the paragraph explaining why it must not appear, where it
#: survived six further entries (D126).
#:
#: A rule that depends on remembering is the rule that failed. This one is named, so the
#: build fails rather than a reader noticing.
PERSONAL_STRINGS = (
    ("akashnavet@outlook.com", "the author's personal email; D119 publishes office@ instead"),
    ("C:\\Users\\akash", "a local filesystem path carrying the author's username"),
)

#: Real domains from the author's own browsing that are **published on purpose** (D127).
#:
#: Akash's call: they are the evidence. D78's finding — that the research tier kept the
#: redirect plumbing and binned the landing page — is checkable only because the actual
#: chain is printed, and `example.com` in its place would make the entry unfalsifiable.
#: A decision log whose evidence cannot be checked is the thing this project exists against.
#:
#: **The set is closed, and that is the whole point of writing it down.** "Real domains may
#: stay when they are evidence" has no edge to it: every domain arrives looking like
#: evidence to whoever is adding it. So the permitted ones are named here, and a domain that
#: is not on this list fails the build until somebody decides it belongs — which is a
#: deliberate act with a name on it, rather than a judgement call made once at midnight and
#: never revisited. This is the icons rule (four exact paths) and not the screenshot rule
#: (a growing allow-list of things judged safe), because the set is small and does not grow
#: on its own.
EVIDENCE_DOMAINS = {
    "zivasuites.com": "D40/D78 — the real redirect chain the heuristic is judged against",
    "darkreading.com": "D36 — observed, stored bare",
    "dominos.co.in": "D34/D36 — observed, and the three-label multi-part suffix case",
    "nike.in": "D36 — observed, stored bare",
    "zomato.com": "D36 — observed; also a category-map entry",
}

#: Domains that were published as evidence and have been **withdrawn** (D128).
#:
#: Removed from `EVIDENCE_DOMAINS` is not enough on its own. That set is an allow-list, so
#: dropping an entry only stops it being *permitted* — and the guard would then report it as
#: an undeclared domain, whose documented remedy is "add it to EVIDENCE_DOMAINS". The next
#: person to hit that failure would helpfully put it back.
#:
#: These two are different from the other five: each was printed beside **its share of one
#: person's browsing**, which is a profile rather than a citation. Both remain in the shipped
#: category map on purpose — there they are ordinary public services and say nothing about
#: anyone. It is the pairing with a percentage that was withdrawn, not the classification.
WITHDRAWN_DOMAINS = {
    "deepseek.com": "D128 — withdrawn from DECISIONS.md; still a category-map entry",
    "insighttimer.com": "D128 — withdrawn from DECISIONS.md; still a category-map entry",
}

#: Domains that are not evidence about anybody: illustrative, infrastructural, or generic
#: services named in the shipped category map. Separated from the set above so the two
#: questions stay apart — "is this a real person's browsing?" and "is this a real string?".
NEUTRAL_DOMAINS = {
    "example.com",
    "bbc.co.uk",
    "google.com",
    "youtube.com",
    "holycowstudios.in",
    "npmjs.org",
}

DOMAIN_SHAPE = re.compile(
    r"\b[a-z0-9][a-z0-9-]{1,40}"
    r"\.(?:com|co\.uk|co\.in|org|net|io|gov\.in|nic\.in|ac\.in|edu|tv|me|org\.uk)\b"
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


#: The only images this repository publishes. Anything else is a screenshot until proven
#: otherwise, and D118 is what "proven otherwise" cost last time.
PUBLISHABLE_IMAGES = ("extension/icons/icon16.png", "extension/icons/icon32.png",
                      "extension/icons/icon48.png", "extension/icons/icon128.png")

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".heic")


class TestTheOnlyPublishedImagesAreTheProductsOwn:
    """An allow-list of four files, not a pattern.

    `.gitignore` deliberately does **not** ignore `*.png`: the icons are product assets and
    must ship, and a blanket rule with an exception carved out for them is the same shape
    that let two screenshots of a live hotel booking into this repository for a fortnight.
    So the rule lives here instead, where breaking it fails a suite and prints why, rather
    than in a file whose failure mode is a silently missing icon.
    """

    def test_every_tracked_image_is_an_icon(self):
        images = [
            name
            for name in _tracked_files()
            if name.lower().endswith(IMAGE_SUFFIXES)
        ]
        unexpected = [name for name in images if name not in PUBLISHABLE_IMAGES]
        assert not unexpected, (
            "only Tise's own icons may be published. If this is a screenshot, it belongs "
            f"outside the repository: {unexpected}"
        )

    def test_the_icons_themselves_are_still_tracked(self):
        """The mirror. A guard against publishing images is one bad rule away from an
        extension that ships with no icon, and `manifest.json` names all four."""
        tracked = set(_tracked_files())
        for name in PUBLISHABLE_IMAGES:
            assert name in tracked, f"{name} is named by the manifest and is not committed"


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

    def test_no_tracked_file_carries_a_personal_identifier(self):
        """The half a credential scanner cannot see.

        An email address is not credential-shaped; it is an ordinary string that looks
        exactly like the address the project *does* publish. Found by reading the repository
        before making it public, in two places — including the decision entry that exists to
        argue the address must not be published (D126).
        """
        offenders: list[str] = []
        for name in _tracked_files():
            path = REPO_ROOT / name
            if name in SCAN_EXEMPT or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for needle, why in PERSONAL_STRINGS:
                if needle in text:
                    offenders.append(f"{name}: {why}")
        assert not offenders, offenders

    def test_the_personal_scan_would_actually_find_one(self):
        """Same reason as above: a guard that cannot fire is decoration."""
        for needle, _ in PERSONAL_STRINGS:
            assert needle in f"prefix {needle} suffix"


class TestTheEvidenceDomainsAreAClosedSet:
    """Real browsing survives in the decision log on purpose, and only the declared part.

    D126 found real domains from the author's own browsing published as evidence and left
    the question open rather than resolving it quietly. D127 resolved it: they stay, because
    D78's redirect finding is only checkable against the real chain and a substituted
    `example.com` would make the entry unfalsifiable.

    **That answer needs an edge or it is not an answer.** "Real domains may stay when they
    are evidence" permits everything, since a domain always looks like evidence to whoever
    is pasting it in. So the permitted set is named, and anything else fails here — which
    turns adding one into a decision somebody makes on the record.
    """

    #: Where real browsing is allowed to appear. Not the whole repository: the shipped
    #: category map is a public vocabulary by design (D26), and the lockfile is registries.
    SCANNED = ("DECISIONS.md",)

    def test_no_undeclared_domain_appears_in_the_decision_log(self):
        permitted = set(EVIDENCE_DOMAINS) | NEUTRAL_DOMAINS
        offenders: dict[str, set[str]] = {}
        for name in self.SCANNED:
            text = (REPO_ROOT / name).read_text(encoding="utf-8")
            found = {d for d in DOMAIN_SHAPE.findall(text) if d not in permitted}
            if found:
                offenders[name] = found
        assert not offenders, (
            f"undeclared domains: {offenders}. If one is a real visit kept as evidence, "
            "add it to EVIDENCE_DOMAINS with the entry it supports. If it is illustrative, "
            "add it to NEUTRAL_DOMAINS. Deciding that is the point of this failing."
        )

    def test_every_declared_evidence_domain_is_still_cited(self):
        # A stale allow-list is how the screenshot rule failed: entries outlived the thing
        # they permitted and nobody rechecked them. A domain nothing cites is one nobody
        # would miss, so it should be removed rather than left standing as permission.
        text = (REPO_ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        unused = [domain for domain in EVIDENCE_DOMAINS if domain not in text]
        assert not unused, f"declared but no longer cited, so no longer needed: {unused}"

    def test_the_domain_scan_can_actually_fire(self):
        planted = "a visit to someones-real-employer.com was recorded"
        found = set(DOMAIN_SHAPE.findall(planted))
        assert found == {"someones-real-employer.com"}
        assert not found & (set(EVIDENCE_DOMAINS) | NEUTRAL_DOMAINS)


class TestAWithdrawnDomainStaysWithdrawn:
    """Removing a name from an allow-list does not keep it out (D128).

    `EVIDENCE_DOMAINS` grants permission, so deleting an entry only revokes it. The domain
    would then trip the undeclared-domain guard, whose failure message says to add it to
    `EVIDENCE_DOMAINS` — which is precisely the wrong remedy for a name that was taken out
    deliberately. A revocation needs to be stated, or the next failure quietly reverses it.
    """

    def test_no_withdrawn_domain_reappears_in_the_decision_log(self):
        text = (REPO_ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        back = [domain for domain in WITHDRAWN_DOMAINS if domain in text]
        assert not back, (
            f"withdrawn and published again: {back}. These were removed on purpose — each "
            "had been printed beside its share of one person's browsing. Do not add them "
            "to EVIDENCE_DOMAINS."
        )

    def test_withdrawn_and_permitted_are_disjoint(self):
        # The two sets contradict each other if they ever overlap, and the guard would then
        # both permit and forbid the same name depending on which test ran.
        assert not set(WITHDRAWN_DOMAINS) & set(EVIDENCE_DOMAINS)
        assert not set(WITHDRAWN_DOMAINS) & NEUTRAL_DOMAINS

    def test_the_shipped_category_map_still_classifies_them(self):
        """Withdrawing the citation is not withdrawing the classification.

        These are ordinary public services. In `domains.json` they are a public vocabulary
        shipped to everyone and describe nobody; removing them would degrade the map for
        every user and protect no one, because the map records no visits.
        """
        import json

        mapping = json.loads(
            (REPO_ROOT / "extension/src/categories/domains.json").read_text(encoding="utf-8")
        )
        flat = mapping.get("domains", mapping)
        for domain in WITHDRAWN_DOMAINS:
            assert domain in flat, f"{domain} should stay in the shipped map"
