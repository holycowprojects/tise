"""T-B — `browsing_next_hour`: will you be here? **A pre-registered adoption test.**

    uv run python analysis/browsing_next_hour.py

Writes `docs/benchmarks/browsing-next-hour.md`.

**D94 fixed the label, the subject, the cluster unit, the bar and the adoption rule before
any of this existed**, and git holds the order. It also recorded a prediction about this
exact run, which the report scores automatically rather than leaving to the reader:

> **T-B beats a flat rate easily and does *not* beat the per-hour rate.** Circadian rhythm
> is nearly all of the signal, and a model that adds recent-activity features on top of it
> will find little left. **This is the prediction most likely to embarrass me**, and it is
> why the bar is the rhythm rather than a constant.

**The bar is `category_base_rate`, and on this target that is the per-hour rate.** T-B's
subject is the hour of day being predicted, so the existing per-subject rate table becomes
the circadian rhythm with no new baseline code — D94 chose the subject for that reason.
`global_base_rate` is reported too and is explicitly *not* the bar: beating a flat rate on
a target where a third of the labels are hours a person is asleep would be trivial.

**One rival is declared here, in advance, and it is not the bar.** `rhythm_7d` predicts
this hour's trailing seven-day rate directly — the two-line rule version of the model. It
exists because D92 and D102 both ended the same way: a simple rule matched or beat the
fitted model, and in D102 the rule was found *after* the run and could not change the
verdict. Declaring it before the run is the correction that entry asked for. It cannot
change the adoption rule either, but this time it can be believed.

**The cluster is the calendar day** (D94), which is 56-90 per corpus — the largest cluster
count of any target measured on Akash's own browsing, against T-A's 27/155 and D93's 11.

**All three corpora are usable.** T-B needs no dwell, so unlike T-A this is not restricted
to the two browsers with a duration column, and unlike T-C the label supply does not depend
on how often a person changes topic — it is one label per hour of the span, whatever
happened in it. Aggregates only; no domain, URL or title is written anywhere by this script.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "research"))

from tise_research.data.chrome_history import DEFAULT_VIEW  # noqa: E402
from tise_research.data.corpus import load_events  # noqa: E402
from tise_research.eval.backtest import BacktestResult, run_backtest  # noqa: E402
from tise_research.eval.intervals import (  # noqa: E402
    Interval,
    brier_difference_interval,
    fold_win_probability,
    rows_to_exclude_zero,
)
from tise_research.features.labels import Label  # noqa: E402
from tise_research.features.presence import (  # noqa: E402
    ACTIVITY_WINDOW_HOURS,
    LAST_VISIT_SCALE_MINUTES,
    PRESENCE_FEATURE_SET,
    RHYTHM_WINDOW_DAYS,
    VISITS_LAST_HOUR_SCALE,
    VISITS_LAST_SIX_HOURS_SCALE,
    presence_examples,
)
from tise_research.features.vector import FeatureRow  # noqa: E402
from tise_research.models.baselines import Baseline  # noqa: E402
from tise_research.models.logreg import DEFAULT_SPEC, predict_proba, train  # noqa: E402
from tise_research.models.prep import design_columns, fit_preprocessor  # noqa: E402

N_FOLDS = 5

#: D94, and on this target it *is* the per-hour rate — see the module docstring.
BAR_MODEL = "category_base_rate"

#: Reported, never the bar. D94 said beating this would be trivial.
FLAT_MODEL = "global_base_rate"

#: The two-line rule, **declared before the run** (see the module docstring). It predicts
#: the trailing seven-day rate for this clock hour and nothing else.
RHYTHM_RIVAL = "rhythm_7d"

#: The corpus the adoption rule is stated over. Named in D94 before anything was fitted.
ADOPTION_CORPUS = "history-edge"

#: Share of pooled test rows in one cluster above which the interval is flagged (D97).
#: Days are near-uniform in size here by construction — 24 boundaries each — so this is
#: expected to be quiet, and it is printed anyway: a check that only runs when it fires is
#: a check nobody can tell is working.
CONCENTRATION_FLAG = 0.20

MODEL_NAME = f"logreg_{PRESENCE_FEATURE_SET.replace('_', '')}"


@dataclass(frozen=True, slots=True)
class _Model(Baseline):
    name: str
    preprocessor: object
    state: object
    rows: dict[str, FeatureRow]

    def predict(self, label: Label) -> float:
        row = self.rows[label.label_id]
        return predict_proba(self.state, self.preprocessor.transform(row))  # type: ignore[attr-defined]


def _fitter(rows: dict[str, FeatureRow]):
    def fit(labels):
        window = [rows[label.label_id] for label in labels]
        preprocessor = fit_preprocessor(window)
        state = train(
            preprocessor.matrix(window),
            [label.outcome for label in labels],
            spec=DEFAULT_SPEC,
            n_columns=len(design_columns(PRESENCE_FEATURE_SET)),
        )
        return _Model(MODEL_NAME, preprocessor, state, rows)

    return fit


@dataclass(frozen=True, slots=True)
class _Rhythm(Baseline):
    """`sameHourRate7d` used directly as a probability.

    Fitted on nothing but the fallback: the feature is already a rate, and turning it into
    a prediction takes no parameters. That is the point — it is the cheapest thing that
    could make the model redundant.
    """

    name: str
    rows: dict[str, FeatureRow]
    fallback: float

    def predict(self, label: Label) -> float:
        value = self.rows[label.label_id].values["sameHourRate7d"]
        return self.fallback if value is None else float(value)


def _rhythm_fitter(rows: dict[str, FeatureRow]):
    def fit(labels):
        rate = (
            sum(1 for label in labels if label.outcome) / len(labels) if labels else 0.5
        )
        return _Rhythm(RHYTHM_RIVAL, rows, rate)

    return fit


@dataclass(frozen=True, slots=True)
class CorpusResult:
    name: str
    events: int
    span_hours: int
    result: BacktestResult
    #: The pre-registered comparison: the model against the per-hour rate, day-clustered.
    day_interval: Interval | None
    #: Against the flat rate. D94 predicts this one is easy, and easy is not the claim.
    flat_interval: Interval | None
    #: Against the declared two-line rule.
    rhythm_interval: Interval | None
    #: Rows, the optimistic bound. Reported for the ladder, never for a claim.
    row_interval: Interval | None
    coefficients: tuple[tuple[str, float], ...]
    test_days: int
    largest_day_share: float
    median_day_size: int
    model_fold_wins: int

    def brier(self, name: str) -> float:
        return self.result.models[name].brier

    @property
    def adopted(self) -> bool:
        """D94's rule, evaluated. Nothing else in this file may decide it."""
        interval = self.day_interval
        return interval is not None and interval.excludes_zero and interval.point > 0.0

    @property
    def beats_flat(self) -> bool:
        interval = self.flat_interval
        return interval is not None and interval.excludes_zero and interval.point > 0.0

    @property
    def concentrated(self) -> bool:
        return self.largest_day_share >= CONCENTRATION_FLAG


def measure(copy_path: Path, *, view: str) -> CorpusResult:
    events = load_events(copy_path, view=view)
    examples = presence_examples(events)
    if len(examples) < N_FOLDS * 2:
        raise ValueError(f"{copy_path.stem}: only {len(examples)} labels")

    rows = {example.label.label_id: example.row for example in examples}
    labels = [example.label for example in examples]

    # D27 excludes `unknown` from every headline. This target has no category in it, so the
    # exclusion is a no-op — asserted rather than assumed, because a silent exclusion would
    # quietly drop an hour of the day from every aggregate on the page.
    if any(label.subject == "unknown" for label in labels):
        raise AssertionError(f"{copy_path.stem}: an hour label was subjected 'unknown'")

    result = run_backtest(
        labels,
        n_folds=N_FOLDS,
        extra_models={
            MODEL_NAME: _fitter(rows),
            RHYTHM_RIVAL: _rhythm_fitter(rows),
        },
    )

    outcomes = result.pooled_outcomes
    model = result.pooled_probabilities[MODEL_NAME]
    per_day = Counter(result.pooled_sessions)
    sizes = sorted(per_day.values(), reverse=True)

    wins = sum(
        1
        for fold in result.folds
        for scores in [dict(fold.brier)]
        if scores.get(MODEL_NAME) is not None
        and scores.get(BAR_MODEL) is not None
        and scores[MODEL_NAME] < scores[BAR_MODEL]
    )

    fitted = _fitter(rows)(labels)
    return CorpusResult(
        name=copy_path.stem,
        events=len(events),
        span_hours=len(examples),
        result=result,
        day_interval=brier_difference_interval(
            outcomes,
            model,
            result.pooled_probabilities[BAR_MODEL],
            subjects=result.pooled_sessions,
            unit="day",
        ),
        flat_interval=brier_difference_interval(
            outcomes,
            model,
            result.pooled_probabilities[FLAT_MODEL],
            subjects=result.pooled_sessions,
            unit="day",
        ),
        rhythm_interval=brier_difference_interval(
            outcomes,
            model,
            result.pooled_probabilities[RHYTHM_RIVAL],
            subjects=result.pooled_sessions,
            unit="day",
        ),
        row_interval=brier_difference_interval(
            outcomes, model, result.pooled_probabilities[BAR_MODEL]
        ),
        coefficients=tuple(
            zip(
                design_columns(PRESENCE_FEATURE_SET),
                fitted.state.weights,  # type: ignore[attr-defined]
                strict=True,
            )
        ),
        test_days=len(per_day),
        largest_day_share=(sizes[0] / len(outcomes)) if sizes and outcomes else 0.0,
        median_day_size=sizes[len(sizes) // 2] if sizes else 0,
        model_fold_wins=wins,
    )


def _described(interval: Interval | None) -> str:
    return "not computable" if interval is None else interval.describe()


def _section(item: CorpusResult) -> str:
    rows = ["| Model | Brier | Log loss | Skill |", "|---|---:|---:|---:|"]
    marks = {
        MODEL_NAME: " **(the model)**",
        BAR_MODEL: " *(the bar — the per-hour rate)*",
        FLAT_MODEL: " *(a flat rate, not the bar)*",
        RHYTHM_RIVAL: " *(the declared two-line rule)*",
    }
    for model in sorted(item.result.models.values(), key=lambda m: m.brier):
        skill = "reference" if model.skill is None else f"{model.skill:+.3f}"
        rows.append(
            f"| `{model.name}`{marks.get(model.name, '')} | {model.brier:.4f} | "
            f"{model.log_loss:.4f} | {skill} |"
        )

    weights = ["| Column | Standardised weight |", "|---|---:|"]
    for name, weight in sorted(item.coefficients, key=lambda pair: -abs(pair[1])):
        weights.append(f"| `{name}` | {weight:+.3f} |")

    verdict = "**clears its bar**" if item.adopted else "**does not clear its bar**"
    shortfall = ""
    if item.day_interval is not None and not item.day_interval.excludes_zero:
        needed = rows_to_exclude_zero(item.day_interval, len(item.result.pooled_outcomes))
        if needed is not None:
            shortfall = (
                f"\nRoughly **{needed:,} test rows** would be needed for a difference this "
                f"size to exclude zero, against the {len(item.result.pooled_outcomes):,} "
                "here — about "
                f"{needed / max(len(item.result.pooled_outcomes), 1):.0f}x the data. That "
                "assumes the point estimate survives collecting it, which is exactly what "
                "is not known: if the true difference is zero, no sample size ever "
                "excludes it.\n"
            )

    chance = fold_win_probability(item.model_fold_wins, len(item.result.folds))
    fold_line = (
        f"The model beat the bar on **{item.model_fold_wins} of "
        f"{len(item.result.folds)} folds**. A model with no skill at all does that or "
        f"better {chance:.1%} of the time, so the fold count is not evidence — it is "
        "printed because omitting it is how D60 read better than it was."
    )

    concentration = (
        f"The largest single day holds {item.largest_day_share:.1%} of the "
        f"{len(item.result.pooled_outcomes):,} pooled test rows, median day "
        f"{item.median_day_size}. "
        + (
            "**Concentrated** — read the interval as more optimistic than its `n=` suggests."
            if item.concentrated
            else "No cluster dominates the resampling, which is expected here: a day is "
            "24 boundaries whether or not anyone browsed in them."
        )
    )

    return f"""### {item.name}

{item.events:,} events over a span of **{item.span_hours:,} labelled hours**
({item.span_hours / 24.0:.0f} days), base rate {item.result.overall_base_rate:.1%} —
that share of hours held at least one visit.

{chr(10).join(rows)}

#### The pre-registered comparison

`{MODEL_NAME}` against `{BAR_MODEL}` — the per-hour rate — paired, **clustered by calendar
day**. Positive favours the model. On this corpus it {verdict}:

{_described(item.day_interval)}
{shortfall}
{fold_line}

#### Against a flat rate, which is not the bar

{_described(item.flat_interval)}

D94 predicted this one is easy and said so before the run, which is why it is not the bar.

#### Against the declared two-line rule

`{RHYTHM_RIVAL}` predicts this hour's trailing {RHYTHM_WINDOW_DAYS}-day rate and nothing
else. `{MODEL_NAME}` against it, day-clustered:

{_described(item.rhythm_interval)}

#### How the clusters are spread

{concentration}

#### The same difference under two units

| Unit | Interval |
|---|---|
| day (the declared unit) | {_described(item.day_interval)} |
| row (optimistic, never a claim) | {_described(item.row_interval)} |

#### Fitted weights

In-sample, standardised columns. For reading which features carry the model, not for
scoring it:

{chr(10).join(weights)}
"""


def write_report(items: list[CorpusResult], *, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "browsing-next-hour.md"

    adoption = next((item for item in items if item.name == ADOPTION_CORPUS), None)
    if adoption is None:
        outcome = (
            f"**Undecided.** The adoption corpus `{ADOPTION_CORPUS}` is not in this run, "
            "and D94 named it before anything was fitted."
        )
    elif adoption.adopted:
        outcome = (
            f"**`{PRESENCE_FEATURE_SET}` clears the bar on `{ADOPTION_CORPUS}`.** The "
            "day-clustered interval against the per-hour rate excludes zero in the "
            "model's favour, which is the rule D94 fixed in advance. **D94's third "
            "prediction — that this target would not beat the rhythm — is wrong**, and "
            "the entry recording it named it as the one most likely to embarrass."
        )
    else:
        outcome = (
            f"**`{PRESENCE_FEATURE_SET}` does not clear the bar on `{ADOPTION_CORPUS}`.** "
            "The day-clustered interval against the per-hour rate includes zero. Under "
            "D94's rule this target is not adopted, whatever the point estimate or the "
            "other corpora say. **D94's third prediction holds**: circadian rhythm is "
            "nearly all of the signal and recent-activity features find little left."
        )

    beat_bar = [item.name for item in items if item.brier(MODEL_NAME) < item.brier(BAR_MODEL)]
    beat_flat = [item.name for item in items if item.beats_flat]
    beat_rhythm = [
        item.name for item in items if item.brier(MODEL_NAME) < item.brier(RHYTHM_RIVAL)
    ]
    bar_beats_flat = [
        item.name for item in items if item.brier(BAR_MODEL) < item.brier(FLAT_MODEL)
    ]

    def listed(names: list[str]) -> str:
        return ", ".join(f"`{n}`" for n in names) if names else "**nothing**"

    path.write_text(
        f"""# T-B · `browsing_next_hour` — will you be here?

Generated by `analysis/browsing_next_hour.py`. **Do not edit by hand.** Regenerate with:

```
uv run python analysis/browsing_next_hour.py
```

One label per clock hour in the observed span: **will at least one visit occur in the next
hour?** Feature set `{PRESENCE_FEATURE_SET}`, **`history` compat class** — no dwell, no
permission, shippable the day it clears a bar.

## What was fixed before this ran, and what was fixed here

**D94 fixed the label, the subject, the cluster unit, the bar and the adoption rule**
before any of this existed, and git holds the order. It left the **feature set** open, so
`{PRESENCE_FEATURE_SET}` was declared in `vector.py` and committed **unrun** ahead of these
numbers — the same discipline D81 and D99 used, for the same reason.

**The bar is the rhythm.** T-B's subject is the hour of day being predicted, which makes
`{BAR_MODEL}` the per-hour rate with no new baseline code — D94 chose the subject for
exactly that. A flat rate is reported and is explicitly **not** the bar: roughly a third of
these labels are hours a person is asleep, so beating a constant proves nothing.

**One rival was declared in advance:** `{RHYTHM_RIVAL}`, this hour's trailing
{RHYTHM_WINDOW_DAYS}-day rate used directly as a probability. D92 and D102 both ended with
a simple rule matching or beating the fitted model, and in D102 the rule was only found
*after* the run, so it could not change anything. This one was written down first.

## Result

{outcome}

- `{MODEL_NAME}` has a lower Brier than the bar (`{BAR_MODEL}`) on: {listed(beat_bar)}
- It **separates** from a flat rate (`{FLAT_MODEL}`) on: {listed(beat_flat)}
- It has a lower Brier than the two-line rule (`{RHYTHM_RIVAL}`) on: {listed(beat_rhythm)}
- The bar itself beats a flat rate on: {listed(bar_beats_flat)} — this is the circadian
  rhythm's own effect size, and it is the reason the bar is what it is.

## `{PRESENCE_FEATURE_SET}`

Eight features, every scale **declared and not fitted** (D81), everything unbounded
saturated. The set has to contain the rhythm — the bar *is* the rhythm, so a model denied
the hour of day could not beat it even in principle.

| Feature | What it is | Nullable |
|---|---|---|
| `hourSin` | the hour as a smooth cycle | no |
| `hourCos` | the other half of it | no |
| `isWeekend` | Saturday or Sunday | no |
| `minutesSinceLast` | since the last visit, saturated at """
        f"""{LAST_VISIT_SCALE_MINUTES:.0f} min | no |
| `visitsLastHour` | in the hour just ended, saturated at {VISITS_LAST_HOUR_SCALE:.0f} | no |
| `visitsLastSixHours` | in the last six, saturated at {VISITS_LAST_SIX_HOURS_SCALE:.0f} | no |
| `sameHourRate7d` | this clock hour's rate over the last {RHYTHM_WINDOW_DAYS} days | **yes** |
| `activeHourShare7d` | share of the last {ACTIVITY_WINDOW_HOURS} hours with a visit | no |

The three places the model can beat the bar, and nowhere else: **the week** (`isWeekend` —
the bar pools every Tuesday 10am with every Sunday 10am), **right now**
(`minutesSinceLast`, `visitsLastHour`, `visitsLastSixHours` — whether the person is at the
machine, which a rhythm cannot hold), and **their own recent rhythm** (`sameHourRate7d`,
`activeHourShare7d` — a trailing version of the bar that moves when a routine does).

Only `sameHourRate7d` is nullable, and it is an absence of *corpus* rather than of
behaviour: in the first day of a corpus, none of the previous seven days was observed.
Filling it with zero would say the person was reliably absent then, which is the opposite
of unknown (D51). The visit counts are **measured zeros** — a quiet hour was counted and
found empty.

## Results

{chr(10).join(_section(item) for item in items)}

## Limitations

- **One person's browsing**, three browsers, so agreement between corpora is much weaker
  evidence than three people agreeing would be.
- **A corpus is one browser.** An hour with no visits here may be an hour spent browsing
  somewhere else, which would enter as a false negative. D18 forbids merging histories, so
  this is not fixable by combining them — it is a property of the question.
- **An hour with the computer switched off is a real negative and reads as a choice.**
  Tise cannot tell "chose not to browse" from "was not at a machine", and for a prediction
  shown to a person those are the same answer.
- **Both boundary hours are excluded**, because both are positive by construction — they
  hold the first and last visit of the corpus by definition.
- **Retention shapes the span.** Chrome's history file holds nothing before a certain date
  (D64), so the span is what the browser kept, not what the person did.
- **In-sample weights.** The coefficient table is fitted on everything and is for reading
  which features carry the model, not for scoring it.
""",
        encoding="utf-8",
    )
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "docs" / "benchmarks")
    parser.add_argument("--view", default=DEFAULT_VIEW, choices=["shipped", "chosen", "raw"])
    args = parser.parse_args()

    copies = (
        [args.corpus] if args.corpus else sorted((REPO_ROOT / "data").glob("history-*.copy"))
    )
    items: list[CorpusResult] = []
    for copy_path in copies:
        try:
            item = measure(copy_path, view=args.view)
        except ValueError as error:
            print(f"Skipping {error}")
            continue
        items.append(item)
        print(
            f"{item.name}: {item.span_hours:,} hourly labels, {item.test_days} test days, "
            f"{MODEL_NAME} {item.brier(MODEL_NAME):.4f} vs bar {item.brier(BAR_MODEL):.4f} "
            f"vs flat {item.brier(FLAT_MODEL):.4f} vs rule {item.brier(RHYTHM_RIVAL):.4f}"
        )
        print(f"  day-clustered vs the bar: {_described(item.day_interval)}")

    if not items:
        print("No corpus produced enough hourly labels.")
        return 1

    print(f"Wrote {write_report(items, out_dir=args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
