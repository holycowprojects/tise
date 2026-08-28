"""Does the bounded feature set do what D81 said it would?

D81 pre-registered this comparison before `fs_3` existed: the argument for replacing
`hoursSinceFirstSeen` and `priorSessionCount`, the exact transforms, three predictions, and
an adoption rule fixed in advance. This script produces the numbers those predictions are
checked against, and nothing here decides anything the pre-registration did not already
decide.

**The mechanism metric is the size of the excursion, not its frequency.** D81 predicted
that the *share* of test rows outside the fitted range would not fall to zero, because a
bounded feature still has an observed training range narrower than its bound —
`priorReturnRate` is already in [0, 1] and still shows 13.2% outside. What a bound buys is
a limit on how far outside a value can land. So the number reported here is the excursion
beyond the training range **in units of the training range's own width**, which is
comparable across features that have nothing else in common.

Both feature sets are scored inside **one** backtest run, so the folds, the labels and the
baselines are identical by construction rather than by care.

Aggregates only. No domain, URL or title is written anywhere by this script.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from tise_research.data.corpus import load_events, load_labels
from tise_research.eval.backtest import rolling_origin_folds, run_backtest
from tise_research.eval.intervals import brier_difference_interval
from tise_research.features.labels import DEFAULT_HORIZON_HOURS, Label
from tise_research.features.vector import FEATURE_SETS
from tise_research.models.return_model import (
    FeatureIndex,
    make_return_model_fitter,
    model_name,
)
from tise_research.reports import superseded_banner

#: The two features D81 replaced, under both names. Everything else is untouched and is
#: reported only so a reader can see it was untouched.
REPLACED = (
    ("hoursSinceFirstSeen", "firstSeenSaturation"),
    ("priorSessionCount", "priorSessionRate"),
)

TIMEOUT_SECONDS = 1800.0
EXCLUDED = "unknown"


@dataclass(frozen=True, slots=True)
class Excursion:
    """How far test values land outside the range a coefficient was fitted on."""

    feature: str
    #: Share of test rows outside the training range. D81 predicted this would *not* fall.
    share_outside: float
    #: Largest excursion, in units of the training range's width. The mechanism claim.
    worst: float | None
    #: Mean over the rows that are outside; None when none are.
    mean_outside: float | None
    rows: int


def _excursions(
    labels: Sequence[Label], index: FeatureIndex, *, n_folds: int
) -> dict[str, Excursion]:
    """Pooled over folds, using the same expanding windows the backtest uses."""
    names = FEATURE_SETS[index.feature_set]
    outside: dict[str, list[float]] = {name: [] for name in names}
    counted = dict.fromkeys(names, 0)

    for fold in rolling_origin_folds(labels, n_folds=n_folds):
        train_rows = index.rows_for(fold.train)
        test_rows = index.rows_for(fold.test)
        for name in names:
            seen = [
                row.values[name] for row in train_rows if row.values[name] is not None
            ]
            if not seen:
                continue
            low, high = min(seen), max(seen)
            width = high - low
            for row in test_rows:
                value = row.values[name]
                if value is None:
                    continue
                counted[name] += 1
                if low <= value <= high:
                    continue
                distance = (value - high) if value > high else (low - value)
                # A feature that never varied in training has no width to measure
                # against, and `fit_preprocessor` has already turned it into zeros.
                outside[name].append(distance / width if width > 0 else float("inf"))

    result: dict[str, Excursion] = {}
    for name in names:
        rows = counted[name]
        over = outside[name]
        result[name] = Excursion(
            feature=name,
            share_outside=(len(over) / rows) if rows else 0.0,
            worst=max(over) if over else None,
            mean_outside=(sum(over) / len(over)) if over else None,
            rows=rows,
        )
    return result


def _format(value: float | None, spec: str = ".2f") -> str:
    if value is None:
        return "—"
    if value == float("inf"):
        return "∞"
    return format(value, spec)


def _excursion_table(
    before: dict[str, Excursion], after: dict[str, Excursion]
) -> str:
    lines = [
        "| Feature | Set | Rows outside | Worst excursion | Mean excursion |",
        "|---|---|---:|---:|---:|",
    ]
    for old, new in REPLACED:
        for label, name, table in (("`fs_2`", old, before), ("`fs_3`", new, after)):
            item = table[name]
            lines.append(
                f"| `{name}` | {label} | {item.share_outside:.1%} | "
                f"{_format(item.worst)} | {_format(item.mean_outside)} |"
            )
    return "\n".join(lines)


def _unchanged_table(
    before: dict[str, Excursion], after: dict[str, Excursion]
) -> str:
    """Proof that nothing else moved. A transform that quietly changed twelve other
    features would make the comparison unattributable."""
    replaced = {name for pair in REPLACED for name in pair}
    lines = ["| Feature | Worst excursion, `fs_2` | `fs_3` |", "|---|---:|---:|"]
    for name in sorted(before):
        if name in replaced:
            continue
        lines.append(
            f"| `{name}` | {_format(before[name].worst)} | {_format(after[name].worst)} |"
        )
    return "\n".join(lines)


def render(
    corpus: str,
    before: dict[str, Excursion],
    after: dict[str, Excursion],
    interval_text: str,
) -> str:
    return f"""## {corpus}

**Excursion beyond the fitted range**, in units of the training range's width, pooled over
folds. D81 predicted the *share* would not fall and the *size* would.

{_excursion_table(before, after)}

**`fs_3` against `fs_2`** on identical folds, paired on the same test rows:

{interval_text}

**Every other feature, unchanged by construction and checked anyway:**

{_unchanged_table(before, after)}
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=None)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--out", type=Path, default=Path("docs/benchmarks"))
    args = parser.parse_args()

    copies = [args.corpus] if args.corpus else sorted(Path("data").glob("history-*.copy"))
    if not copies:
        print("No corpus found.")
        return 1

    sections = []
    for copy_path in copies:
        labels = load_labels(copy_path, timeout_seconds=TIMEOUT_SECONDS)
        if len(labels) < args.folds * 2:
            print(f"Skipping {copy_path.stem}: only {len(labels)} labels")
            continue
        events = load_events(copy_path)
        indexes = {
            name: FeatureIndex(
                events=events,
                timeout_seconds=TIMEOUT_SECONDS,
                horizon_hours=DEFAULT_HORIZON_HOURS,
                feature_set=name,
            )
            for name in ("fs_2", "fs_3")
        }

        # One run, both models. Identical folds by construction.
        result = run_backtest(
            labels,
            n_folds=args.folds,
            extra_models={
                model_name(name): make_return_model_fitter(index)
                for name, index in indexes.items()
            },
        )

        interval = brier_difference_interval(
            result.pooled_outcomes,
            result.pooled_probabilities[model_name("fs_3")],
            result.pooled_probabilities[model_name("fs_2")],
            subjects=result.pooled_subjects,
        )
        rows = brier_difference_interval(
            result.pooled_outcomes,
            result.pooled_probabilities[model_name("fs_3")],
            result.pooled_probabilities[model_name("fs_2")],
        )
        assert interval is not None and rows is not None
        worse = interval.high < 0
        verdict = (
            "`fs_3` is **shown to be worse** — the adoption rule's veto fires."
            if worse
            else "The interval includes zero: `fs_3` is **not shown to be worse**, which "
            "is what D81's adoption rule requires of the score."
        )
        interval_text = (
            f"| Paired Brier difference (`fs_2` − `fs_3`), positive favours `fs_3` | 95% |\n"
            f"|---|---|\n"
            f"| resampling rows | {rows.point:+.4f} [{rows.low:+.4f}, {rows.high:+.4f}] |\n"
            f"| resampling categories ({interval.units} clusters) | "
            f"{interval.point:+.4f} [{interval.low:+.4f}, {interval.high:+.4f}] |\n\n"
            f"{verdict}"
        )

        before = _excursions(labels, indexes["fs_2"], n_folds=args.folds)
        after = _excursions(labels, indexes["fs_3"], n_folds=args.folds)
        sections.append(render(copy_path.stem, before, after, interval_text))

        print(f"{copy_path.stem}:")
        for old, new in REPLACED:
            print(
                f"  {old:<22} worst {_format(before[old].worst):>8}"
                f"   ->  {new:<22} worst {_format(after[new].worst):>8}"
            )
        print(f"  fs_3 vs fs_2 (categories): {interval.point:+.4f} "
              f"[{interval.low:+.4f}, {interval.high:+.4f}]")

    args.out.mkdir(parents=True, exist_ok=True)
    report = args.out / "feature-transform.md"
    report.write_text(
        "# Feature transform — `fs_2` against `fs_3`\n\n"
        + superseded_banner("return_24h")
        + "\nGenerated by `analysis/feature_transform.py`. Aggregates only.\n\n"
        "The comparison and its adoption rule were **pre-registered in D81 before `fs_3` "
        "was implemented**, so nothing on this page chose itself after seeing a result.\n\n"
        + "\n".join(sections),
        encoding="utf-8",
    )
    print(f"\nwrote {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
