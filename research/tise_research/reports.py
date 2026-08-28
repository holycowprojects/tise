"""Provenance banners for generated reports.

`docs/benchmarks/` is the public face of the showcase. When D88 retired `return_24h` as the
product target, twelve reports carried on describing it in the present tense with nothing
saying otherwise — `model.md` still opens "Model — `return_24h`" and reads as current. Right
numbers, wrong frame, which is the defect D86 and D87 were both written about.

**The banner is derived, never typed.** A writer declares which target its report describes;
this module decides whether that target is retired and what to say. When `block_volume` is
eventually superseded in its turn, `RETIRED_TARGETS` gains one line and every report updates
on its next regeneration. A banner pasted into each writer would be twelve literals, and
literals are what went stale in the first place — D87 found the same bug in three places.

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
    "is_retired",
    "partly_superseded_banner",
    "superseded_banner",
]

#: What the project predicts now. Reports about this target carry no banner.
CURRENT_TARGET = "block_volume"

#: Retired target -> the decision that retired it. One line per retirement, and every
#: generated report follows from it.
RETIRED_TARGETS: dict[str, str] = {
    "return_24h": "D88",
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
        f"> **`{target}` was retired as the product target in {decision}.** Tise now"
        f" predicts **`{CURRENT_TARGET}`**.\n"
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
        f" {decision}. Tise now predicts **`{CURRENT_TARGET}`**.\n"
        f">\n"
        f"> See {decision} in [`DECISIONS.md`](../../DECISIONS.md).\n"
    )
