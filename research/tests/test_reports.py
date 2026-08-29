"""The superseded banners, which exist so `docs/benchmarks/` cannot lie about its own age.

D88 retired `return_24h` and twelve reports carried on describing it in the present tense.
The banner fixes that; these tests are about the banner not becoming the next stale literal.

The property worth protecting is **derivation**: a writer names the target it describes and
this module decides what to say. So the tests check the mechanism — that a current target
produces nothing, that a retired one produces a banner naming the right decision, and that
the module refuses to invent a decision for a target nobody retired — rather than checking
today's wording.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tise_research.reports import (
    CURRENT_TARGET,
    RETIRED_TARGETS,
    SHIPPED_TARGET,
    is_retired,
    partly_superseded_banner,
    superseded_banner,
    what_tise_predicts,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestWhoGetsABanner:
    def test_a_retired_target_gets_one(self) -> None:
        assert superseded_banner("return_24h") != ""

    def test_the_current_target_gets_nothing(self) -> None:
        # The property that makes this safe to call unconditionally: a writer keeps the
        # call forever and the banner disappears by itself when its target ships.
        assert superseded_banner(CURRENT_TARGET) == ""

    def test_an_unknown_target_gets_nothing_rather_than_a_guess(self) -> None:
        assert superseded_banner("something_nobody_declared") == ""

    def test_the_current_target_is_not_also_retired(self) -> None:
        # Would produce a report banner-marked as superseded by its own decision.
        assert CURRENT_TARGET not in RETIRED_TARGETS

    def test_is_retired_agrees_with_the_table(self) -> None:
        for target in RETIRED_TARGETS:
            assert is_retired(target)
        assert not is_retired(CURRENT_TARGET)


class TestWhatTheBannerSays:
    def test_it_names_the_retired_target_and_its_decision(self) -> None:
        banner = superseded_banner("return_24h")
        assert "return_24h" in banner
        assert RETIRED_TARGETS["return_24h"] in banner

    def test_it_names_what_replaced_it(self) -> None:
        # A reader who is told a page is stale and not told what is current has to go
        # looking. The banner is the only place they are guaranteed to be standing.
        assert CURRENT_TARGET in superseded_banner("return_24h")

    def test_it_does_not_withdraw_the_numbers(self) -> None:
        # The distinction the whole entry rests on: these figures were measured and are
        # kept deliberately. "Superseded" must not read as "retracted".
        banner = superseded_banner("return_24h").lower()
        assert "measured" in banner
        assert "withdrawn" in banner

    def test_it_renders_as_a_markdown_blockquote(self) -> None:
        # It is spliced into generated markdown; a stray non-quoted line would break out
        # of the callout and read as body text.
        lines = [
            line for line in superseded_banner("return_24h").splitlines() if line.strip()
        ]
        assert lines
        assert all(line.startswith(">") for line in lines)


class TestPartlySuperseded:
    def test_it_names_both_halves(self) -> None:
        banner = partly_superseded_banner(
            "return_24h", stands="Session boundaries stand", retired="The label tables"
        )
        assert "Session boundaries stand" in banner
        assert "The label tables" in banner

    def test_it_is_empty_for_a_current_target(self) -> None:
        assert (
            partly_superseded_banner(CURRENT_TARGET, stands="a", retired="b") == ""
        )

    def test_it_renders_as_a_blockquote_too(self) -> None:
        banner = partly_superseded_banner(
            "return_24h", stands="a", retired="b"
        )
        lines = [line for line in banner.splitlines() if line.strip()]
        assert all(line.startswith(">") for line in lines)


class TestTheShippedTargetIsNotTheGoal:
    """The defect this class exists for was found in this very module (D97).

    `CURRENT_TARGET` said `block_volume` from D88 until D97, and D92 retired
    `block_volume` two decisions earlier. Every test above passed the whole time, because
    every one of them checks the *mechanism* — that a retired target gets a banner naming
    the right decision — and none of them checks that the constant names something real.

    A constant cannot check itself, so these check it against things outside the module:
    the extension's own source, and the retirement table.
    """

    def test_the_shipped_target_matches_what_the_extension_actually_ships(self) -> None:
        # The only external fact available: the TypeScript that runs in the browser. If
        # the extension is rewired to a new target and this constant is not, the banners
        # start describing an extension that does not exist — which is the failure, not
        # the annoyance of updating two files.
        source = (REPO_ROOT / "extension" / "src" / "model" / "predict.ts").read_text(
            encoding="utf-8"
        )
        assert f'export const TARGET = "{SHIPPED_TARGET}"' in source

    def test_the_shipped_target_is_allowed_to_be_retired(self) -> None:
        # The distinction the whole entry is about. A target is retired as a *goal* long
        # before the code stops carrying it, and a banner that conflates the two is false
        # about one of them whichever way it is written.
        assert SHIPPED_TARGET in RETIRED_TARGETS or SHIPPED_TARGET == CURRENT_TARGET

    def test_the_sentence_names_both_when_they_differ(self) -> None:
        sentence = what_tise_predicts()
        if SHIPPED_TARGET == CURRENT_TARGET:
            assert CURRENT_TARGET in sentence
        else:
            assert CURRENT_TARGET in sentence
            assert SHIPPED_TARGET in sentence

    def test_the_banner_carries_that_sentence(self) -> None:
        assert what_tise_predicts() in superseded_banner("return_24h")
        assert what_tise_predicts() in partly_superseded_banner(
            "return_24h", stands="a", retired="b"
        )

    def test_every_retired_target_names_a_decision_that_exists(self) -> None:
        # `block_volume` was retired by D92 and the table did not know for two decisions.
        # This cannot detect a missing entry, but it does catch an invented one.
        decisions = (REPO_ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        for target, decision in RETIRED_TARGETS.items():
            assert f"### {decision} " in decisions, (
                f"{target} claims to be retired by {decision}, which is not in DECISIONS.md"
            )


class TestItRefusesToInvent:
    def test_asking_for_a_decision_on_a_live_target_raises(self) -> None:
        # Reached only through a direct call with a target that is not retired. Raising
        # beats returning a plausible-looking decision id that names nothing.
        from tise_research.reports import _decision

        with pytest.raises(ValueError, match="not retired"):
            _decision(CURRENT_TARGET)
