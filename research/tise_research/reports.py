"""Provenance banners for generated reports.

`docs/benchmarks/` is the public face of the showcase. When D88 retired `return_24h` as the
product target, twelve reports carried on describing it in the present tense with nothing
saying otherwise — `model.md` still opens "Model — `return_24h`" and reads as current. Right
numbers, wrong frame, which is the defect D86 and D87 were both written about.

**The banner is derived, never typed.** A writer declares which target its report describes;
this module decides whether that target is retired and what to say. When a target is
superseded in its turn, `RETIRED_TARGETS` gains one line and every report updates on its next
regeneration. A banner pasted into each writer would be twelve literals, and literals are
what went stale in the first place — D87 found the same bug in three places.

**And then this module went stale anyway (D97).** `block_volume` was retired by D92 and
`CURRENT_TARGET` still named it two decisions later, so eight generated reports spent that
whole time telling readers Tise predicted a target the project had abandoned. Derivation was
not the flaw: a single constant was being asked to mean both *what the project is building
toward* and *what the extension actually runs*, and those diverge by design — D96 records
that no target is wired in before it is built end to end, so they are **meant** to differ.
Whichever thing the constant named, the banner was false about the other. They are now
`CURRENT_TARGET` and `SHIPPED_TARGET`, `what_tise_predicts()` says both, and a test pins
`SHIPPED_TARGET` against `extension/src/model/predict.ts` — the one fact outside this
module's own opinion of itself.

A report is one of three things, and the distinction matters because over-marking is its own
dishonesty:

* **superseded** — its subject is a retired target. Every number describes something the
  project no longer builds.
* **partly superseded** — it measures the browsing itself *and* something target-specific.
  `history-shape-*.md` is the case: visits per day, session boundaries and domain
  concentration are facts about the data and stand; the label-volume tables belong to the
  retired target.
* **current** — target-agnostic. `import-simulation-*.md` and `redirect-heuristic-*.md`
  describe how visits reach the extension and are unaffected by what gets predicted.
"""

from __future__ import annotations

__all__ = [
    "CURRENT_TARGET",
    "RETIRED_TARGETS",
    "SHIPPED_TARGET",
    "is_retired",
    "partly_superseded_banner",
    "superseded_banner",
    "what_tise_predicts",
]

#: What the project builds toward now. Reports about this target carry no banner.
#:
#: **This is a goal, not a claim about the shipped code** — see `SHIPPED_TARGET`. Between
#: D88 and D97 this constant said `block_volume`, which D92 retired, so eight generated
#: reports spent two decisions telling readers that Tise predicted a target the project had
#: already abandoned. Right numbers, wrong frame, in the module written to prevent exactly
#: that. The lesson is not "remember to update it": it is that one constant was being asked
#: to mean two different things, and one of them was always wrong.
CURRENT_TARGET = "visit_engaged"

#: What the extension in `extension/` actually trains and predicts **today**. It lags
#: `CURRENT_TARGET` on purpose: D96 records that wiring in an unadopted target is the
#: mistake five entries have been spent avoiding, so a target becomes current when it clears
#: its bar and shipped only when it is built end to end. A banner that named only one of
#: these would be false about the other.
SHIPPED_TARGET = "return_24h"

#: Retired target -> the decision that retired it. One line per retirement, and every
#: generated report follows from it.
RETIRED_TARGETS: dict[str, str] = {
    "return_24h": "D88",
    "block_volume": "D92",
}


def is_retired(target: str) -> bool:
    return target in RETIRED_TARGETS


def _decision(target: str) -> str:
    try:
        return RETIRED_TARGETS[target]
    except KeyError:
        raise ValueError(
            f"{target!r} is not retired, so it has no superseding decision. "
            f"Current target is {CURRENT_TARGET!r}."
        ) from None


def what_tise_predicts() -> str:
    """One sentence that is true about both the goal and the shipped code.

    Written once and reused by both banners, because the two sentences drifting apart is
    the same failure at a smaller scale.
    """
    if SHIPPED_TARGET == CURRENT_TARGET:
        return f"Tise predicts **`{CURRENT_TARGET}`**."
    return (
        f"The project now builds toward **`{CURRENT_TARGET}`**, and the shipped extension"
        f" still trains **`{SHIPPED_TARGET}`** — no target is wired in before it is built"
        f" end to end."
    )


def superseded_banner(target: str) -> str:
    """Banner for a report whose whole subject is a retired target.

    Returns an empty string for a target that is still current, so a writer can call this
    unconditionally and stop carrying the banner automatically once its target ships.
    """
    if not is_retired(target):
        return ""
    decision = _decision(target)
    return (
        f"> ### ⚠ Superseded — this report describes a retired target\n"
        f">\n"
        f"> **`{target}` was retired as the product target in {decision}.**"
        f" {what_tise_predicts()}\n"
        f">\n"
        f"> Every number below was really measured and none of it has been withdrawn — it is"
        f" kept deliberately, because it is the evidence that *justified* retiring the"
        f" target. It is not a description of what Tise currently does, and no figure here"
        f" should be quoted as a current result.\n"
        f">\n"
        f"> See {decision} in [`DECISIONS.md`](../../DECISIONS.md).\n"
    )


def partly_superseded_banner(target: str, *, stands: str, retired: str) -> str:
    """Banner for a report that measures the data itself *and* a retired target.

    `stands` names what survives the retirement; `retired` names what does not. Both are
    required rather than defaulted, because a vague "parts of this are out of date" tells a
    reader nothing about which parts.
    """
    if not is_retired(target):
        return ""
    decision = _decision(target)
    return (
        f"> ### ⚠ Partly superseded\n"
        f">\n"
        f"> **{stands}** — measurements of the browsing itself, unaffected by what is being"
        f" predicted.\n"
        f">\n"
        f"> **{retired}** belongs to `{target}`, retired as the product target in"
        f" {decision}. {what_tise_predicts()}\n"
        f">\n"
        f"> See {decision} in [`DECISIONS.md`](../../DECISIONS.md).\n"
    )
