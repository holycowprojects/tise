"""The shipped category map.

Two kinds of test live here.

**Structural tests** run anywhere, including CI, and depend on nothing but the committed
JSON. They are what stops the map rotting: a typo'd category name or a full URL sneaking
in as a key would otherwise surface as a silent `unknown` months later.

**Coverage tests** need a real history database and are skipped when one is absent. They
answer T2's acceptance criterion — does the shipped map cover enough real browsing to be
useful — and can only be answered against data that is never committed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tise_research.categories import (
    DEFAULT_MAP_PATH,
    CategoryMap,
    load_category_map,
)

MAP = load_category_map()

#: T2's acceptance criterion, on the designated primary research corpus (D20).
MINIMUM_COVERAGE_PRIMARY = 0.80

#: Floor for every other corpus. Lower on purpose, and the reason is a finding rather
#: than a concession: a shipped map is generic, and a person's *own* domains cannot be
#: in it. One self-owned domain accounts for 14.5% of the Chrome corpus, so a perfect
#: generic map still could not reach 80% there. This floor catches map rot — a category
#: renamed, a block of domains dropped — without failing on that structural ceiling.
MINIMUM_COVERAGE_ANY = 0.70

#: Stem of the primary corpus, per D20.
PRIMARY_CORPUS = "history-edge"


class TestFileShape:
    def test_the_shipped_map_exists_where_the_extension_expects_it(self):
        assert DEFAULT_MAP_PATH.exists()
        assert DEFAULT_MAP_PATH.parts[-3:] == ("src", "categories", "domains.json")

    def test_json_is_valid_and_has_the_expected_top_level_keys(self):
        raw = json.loads(DEFAULT_MAP_PATH.read_text(encoding="utf-8"))
        assert set(raw) >= {"version", "categories", "domains"}

    def test_version_is_an_integer(self):
        """`featureSet` and the map version are recorded together in DECISIONS.md."""
        assert isinstance(MAP.version, int)


class TestCategories:
    def test_every_category_has_a_one_line_definition(self):
        for name, definition in MAP.categories.items():
            assert definition.strip(), f"{name} has no definition"
            assert "\n" not in definition, f"{name}'s definition is not one line"

    def test_unknown_is_a_defined_category(self):
        """It is a valid outcome, not an error. SPEC.md and D-series both depend on it."""
        assert "unknown" in MAP.categories

    def test_unknown_is_never_assigned_to_a_domain(self):
        """`unknown` is what the resolver returns when nothing matched. A domain mapped
        to it would be indistinguishable from an unmapped one."""
        assert "unknown" not in set(MAP.domains.values())

    def test_category_names_are_lowercase_identifiers(self):
        for name in MAP.categories:
            assert name.islower()
            assert name.replace("_", "").isalnum(), name

    def test_category_count_is_in_a_workable_range(self):
        """Too few and every session is the same category; too many and each class is
        starved of labels. T1 measured 8-25 as the workable band."""
        assert 8 <= len(MAP.categories) <= 26


class TestDomains:
    def test_every_domain_maps_to_a_defined_category(self):
        undefined = {
            domain: category
            for domain, category in MAP.domains.items()
            if category not in MAP.categories
        }
        assert not undefined, f"categories used but never defined: {undefined}"

    def test_every_category_except_unknown_has_at_least_one_domain(self):
        """A category nothing maps to cannot be predicted and should not exist."""
        used = set(MAP.domains.values())
        orphans = set(MAP.categories) - used - {"unknown"}
        assert not orphans, f"defined but unreachable: {sorted(orphans)}"

    @pytest.mark.parametrize("forbidden", ["://", "/", "?", "#", " "])
    def test_keys_are_bare_domains_not_urls(self, forbidden):
        """The resolver is handed a registrable domain. A URL here would never match,
        and would put a path into a published file."""
        offenders = [d for d in MAP.domains if forbidden in d]
        assert not offenders, f"{forbidden!r} in {offenders}"

    def test_keys_are_lowercase(self):
        assert [d for d in MAP.domains if d != d.lower()] == []

    def test_keys_look_like_domains(self):
        assert [d for d in MAP.domains if "." not in d] == []

    def test_no_www_prefix(self):
        """`registrable_domain` strips it, so a `www.` key is dead weight."""
        assert [d for d in MAP.domains if d.startswith("www.")] == []


class TestLookup:
    def test_known_domain_resolves(self):
        assert MAP.lookup("youtube.com") == "video"

    def test_unknown_domain_returns_none(self):
        """None means 'the map had nothing'. The resolver decides what to do next —
        keyword rules, then 'unknown'. That layering arrives at T3."""
        assert MAP.lookup("some-domain-nobody-has.example") is None

    def test_lookup_is_case_insensitive(self):
        assert MAP.lookup("YouTube.COM") == "video"


class TestPrivacy:
    """The map is committed and public. A domain list is a profile.

    These assertions are cheap and they encode a decision that is otherwise easy to
    forget when someone adds "just one more" domain that happens to be their employer's.
    """

    def test_map_contains_no_personal_domains_from_the_seed_history(self):
        forbidden = {
            "holycowstudios.in",
            "sharadamandirschool.edu.in",
            "sharadamandir.edu.in",
            "goa.gov.in",
            "goapolice.gov.in",
            "goatransport.gov.in",
            "goaonline.gov.in",
        }
        leaked = forbidden & set(MAP.domains)
        assert not leaked, f"personal or locality-identifying domains published: {leaked}"

    def test_no_ad_or_tracker_domains(self):
        """These are never chosen navigations and would pollute every category."""
        offenders = [
            d
            for d in MAP.domains
            if any(marker in d for marker in ("adservices", "adnxs", "doubleclick"))
        ]
        assert not offenders, offenders


def _local_history_copies() -> list[Path]:
    return sorted(Path("data").glob("history-*.copy"))


@pytest.mark.skipif(
    not _local_history_copies(),
    reason="no local history copy; run analysis/history_shape.py first",
)
class TestCoverageAgainstRealBrowsing:
    """T2's acceptance criterion, measurable only against data that is never committed."""

    @pytest.mark.parametrize("copy_path", _local_history_copies(), ids=lambda p: p.stem)
    def test_map_covers_at_least_the_minimum_share_of_visits(
        self, copy_path: Path, capsys
    ):
        from tise_research.data.chrome_history import load_visits

        if "firefox" in copy_path.stem:
            from tise_research.data.firefox_history import load_visits  # noqa: F811

        visits = load_visits(copy_path)
        if not visits:
            pytest.skip(f"{copy_path.name} holds no visits")

        matched = sum(1 for v in visits if MAP.lookup(v.domain) is not None)
        coverage = matched / len(visits)

        is_primary = copy_path.stem == PRIMARY_CORPUS
        threshold = MINIMUM_COVERAGE_PRIMARY if is_primary else MINIMUM_COVERAGE_ANY

        with capsys.disabled():
            print(
                f"\n  {copy_path.stem}: {coverage:.1%} of {len(visits):,} visits "
                f"covered by map v{MAP.version} "
                f"(needs {threshold:.0%}{', primary corpus' if is_primary else ''})"
            )

        assert coverage >= threshold, (
            f"{copy_path.stem}: {coverage:.1%} < {threshold:.0%}"
        )


def test_map_is_a_category_map_instance():
    assert isinstance(MAP, CategoryMap)
