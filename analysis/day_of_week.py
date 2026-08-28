"""Return rate by day of week — written to check a story, and it failed the check.

D85 documented the shipped model's worst row: an Edge `video` window ending on a Saturday
where every continuation feature was at its ceiling, the model said 99.1%, and the person
did not come back. The entry then explained it — "the thing that appears to have happened
is a weekend" — and that explanation was never measured. This script measures it.

**It is wrong.** On Edge, Saturday returns at a rate *above* the corpus average. The story
was a plausible narrative attached to a single row, which is the exact failure SPEC.md
invariant 3 exists to prevent; the invariant is usually read as being about fabricated
figures, and a causal claim with no number behind it is the same defect wearing prose.

What survives the check is better than what it replaced. The day-of-week pattern is real
and **non-monotone** — on Edge, Monday is the highest day and Sunday the lowest, with
Friday low and Saturday high in between. `dayOfWeek` enters `fs_3` as a plain integer 0-6
carrying one linear coefficient, and no such coefficient can represent a non-monotone
pattern in any direction. So the conclusion "a mis-encoded feature, not a calibration
failure" holds. The reason given for it did not.

Nothing here is a decision to add cyclic encoding. `return_model.py` states the position:
that change gets made against a measured number, with the plain version's score beside it,
or it is tuning against an intuition. This is the measurement, not the change.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from tise_research.data.chrome_history import DEFAULT_VIEW
from tise_research.eval.backtest import EXCLUDED_FROM_HEADLINE
from tise_research.features.labels import Label

__all__ = ["DayRate", "day_of_week_rates", "write_day_of_week_report"]

DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

#: Below this many labels on a day, the rate is counted but not reported. D26's rule, and
#: it applies with more force here: a day with six labels can show any rate at all.
MIN_DAY_LABELS = 20


class DayRate:
    """One weekday's outcome count. `reported` follows D26's label floor."""

    __slots__ = ("day", "positives", "total")

    def __init__(self, day: int) -> None:
        self.day = day
        self.positives = 0
        self.total = 0

    @property
    def rate(self) -> float | None:
        return self.positives / self.total if self.total else None

    @property
    def reported(self) -> bool:
        return self.total >= MIN_DAY_LABELS

    @property
    def name(self) -> str:
        return DAY_NAMES[self.day]


def day_of_week_rates(labels: list[Label]) -> tuple[list[DayRate], float | None]:
    """Return rate per weekday of `window_end`, plus the overall rate.

    `unknown` is excluded exactly as it is from every headline (D27), so this table and
    the model's own numbers describe the same population.
    """
    days = [DayRate(index) for index in range(7)]
    positives = total = 0
    for label in labels:
        if label.subject == EXCLUDED_FROM_HEADLINE:
            continue
        bucket = days[label.window_end.weekday()]
        bucket.total += 1
        total += 1
        if label.outcome:
            bucket.positives += 1
            positives += 1
    return days, (positives / total if total else None)


def _corpus_section(name: str, days: list[DayRate], overall: float | None) -> str:
    lines = [f"### {name}", ""]
    if overall is None:
        return "\n".join([*lines, "_No labels._"])

    lines.extend(
        [
            f"Overall return rate **{overall:.1%}**. Days below {MIN_DAY_LABELS} labels "
            "are counted but not scored (D26).",
            "",
            "| Day | Returned | Labels | Rate | vs overall |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for day in days:
        if not day.reported:
            shown_rate = "not scored"
            delta = "—"
        else:
            rate = day.rate
            assert rate is not None
            shown_rate = f"{rate:.1%}"
            delta = f"{rate - overall:+.1%}"
        lines.append(
            f"| {day.name} | {day.positives} | {day.total} | {shown_rate} | {delta} |"
        )

    scored = [day for day in days if day.reported and day.rate is not None]
    if len(scored) >= 3:
        rates = [day.rate for day in scored]
        assert all(rate is not None for rate in rates)
        best = max(scored, key=lambda day: day.rate or 0.0)
        worst = min(scored, key=lambda day: day.rate or 1.0)
        ordered = sorted(scored, key=lambda day: day.day)
        values = [day.rate or 0.0 for day in ordered]
        monotone = values == sorted(values) or values == sorted(values, reverse=True)
        lines.extend(
            [
                "",
                f"Highest **{best.name}** at {best.rate:.1%}, lowest **{worst.name}** at "
                f"{worst.rate:.1%} — a spread of "
                f"{(best.rate or 0.0) - (worst.rate or 0.0):.1%}. Across the days in "
                "calendar order this pattern is "
                + (
                    "**monotone**, so a single linear coefficient could in principle "
                    "represent it."
                    if monotone
                    else "**not monotone**, so a single linear coefficient on an integer "
                    "0-6 cannot represent it in either direction."
                ),
            ]
        )
    return "\n".join(lines)


def write_day_of_week_report(
    sections: list[tuple[str, list[DayRate], float | None]],
    *,
    out_dir: Path,
    timeout_seconds: float,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "day-of-week.md"
    body = "\n\n".join(
        _corpus_section(name, days, overall) for name, days, overall in sections
    )
    path.write_text(
        f"""# Return rate by day of week

Generated by `analysis/day_of_week.py`. **Do not edit by hand.** Regenerate with:

```
uv run python analysis/day_of_week.py
```

Session timeout {timeout_seconds:,.0f}s (D17), horizon 24h, `unknown` excluded (D27).
Corpora measured **separately and never merged** (D18).

## Why this exists

D85 documented the shipped model's worst single row — an Edge `video` window ending on a
Saturday, every continuation feature at its ceiling, 99.1% said, no return — and then
explained it as a weekend effect. **That explanation was never measured, and it is wrong:**
Saturday's return rate on Edge is *above* the corpus average. A causal story with no number
behind it is the same defect as a fabricated figure, in prose.

What survives is the structural half of the claim, and it is stronger than the story it
replaces. Where the pattern below is **non-monotone**, no single linear coefficient on an
integer 0-6 can represent it in either direction — so `dayOfWeek`'s encoding, not the
calibrator, is what fails on rows like that one.

This measures; it does not change anything. `models/return_model.py` holds the position that
a cyclic encoding gets added against a measured number with the plain version beside it, or
it is tuning against an intuition. **The model has not been changed and no feature was
added.** D86 records what this found.

{body}
""",
        encoding="utf-8",
    )
    return path


def main() -> int:
    from tise_research.data.corpus import load_labels

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=None)
    parser.add_argument("--timeout-seconds", type=float, default=1800.0)
    parser.add_argument("--out", type=Path, default=Path("docs/benchmarks"))
    parser.add_argument(
        "--view", default=DEFAULT_VIEW, choices=["shipped", "chosen", "raw"]
    )
    args = parser.parse_args()

    copies = [args.corpus] if args.corpus else sorted(Path("data").glob("history-*.copy"))
    if not copies:
        print("No corpus found. Run analysis/history_shape.py first.")
        return 1

    sections: list[tuple[str, list[DayRate], float | None]] = []
    for copy_path in copies:
        labels = load_labels(
            copy_path, timeout_seconds=args.timeout_seconds, view=args.view
        )
        days, overall = day_of_week_rates(labels)
        sections.append((copy_path.stem, days, overall))
        shown = "n/a" if overall is None else f"{overall:.1%}"
        print(f"{copy_path.stem}: {len(labels):,} labels, overall {shown}")

    path = write_day_of_week_report(
        sections, out_dir=args.out, timeout_seconds=args.timeout_seconds
    )
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
