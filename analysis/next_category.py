"""T-C — `next_category`: what comes next? **A pre-registered adoption test.**

    uv run python analysis/next_category.py

Writes `docs/benchmarks/next-category.md`.

D94 fixed all of it before anything was fitted: the label, the metric, the bar, the cluster
unit and the adoption rule. Git holds the order. This is the fourth target registered that
way and the second to be scored.

**The challenger is the shipped transition table** — the model that has existed in both
languages since T10 and has **never been benchmarked**. That is the whole of T-C. It is
reached through `fit_transition_pairs`, which `fit_transition_table` also delegates to, so
this scores the model that runs rather than a research twin of it.

## Three things this file declares, and all three were written before it was run

**The rule is what D94 pre-registered; the 33.2% is not the number.** T19 measured 33.2%
for the always-the-global-mode rule over a *different* label set — one primary category per
session, self-transitions permitted. T-C's labels are category **changes** (D94), within
sessions as well as between, so the same rule scores differently and its value here is
measured. Fixing the number would also have made the adoption rule impossible to apply: a
paired bootstrap needs the reference's prediction on each row and a constant has none. T19's
figure is printed beside the measured floor so the two cannot be confused.

**The headline excludes labels whose answer is `unknown` (D27).** That bucket is the
person's own frequent domains collapsed into one label. It is unpresentable — no "what's
next" surface can show a chip reading *unknown* — and it is highly predictable, so leaving
it in would inflate the floor and the model together. Conditioning **on** `unknown` is kept:
"you were on something uncategorised, next comes X" is a question a UI can answer. The
all-labels variant is computed and printed beside the headline, so the choice is visible
rather than load-bearing in the dark. This is D27 applied, not a new rule invented here.

**The verdict is read off Edge, session-clustered.** D94 named the corpus and the unit
before any of this existed. The source-category unit is reported beside it, as D94 requires
of every target.

**`bounce_back` is a rival, not the bar.** It predicts the category you were on *before*
the one just finished and reads no counts at all. If it matches the fitted table, the table
is not learning anything a two-line rule does not already know — which is worth knowing and
is not the adoption question. Promoting it after seeing the scores would be choosing the
rule from the result.

## And one thing this file added *after* seeing the numbers

**`constrained_mode` is a post-hoc diagnostic, and saying so is the point.** A label is a
category change, so the answer can never equal the source — and `global_mode` does not know
that. On the rows where the source *is* the global mode, the bar is wrong before it starts.
That is **31.9% of Edge's test rows**, against 0.0% for the table, whose row for a source
holds no self-count. So some unknown share of the table's margin is not learning at all.

`constrained_mode` is the global mode with the source removed. It measures what the counts
are worth on top of knowing only that you will do something different. **It cannot change
the verdict** — D94 named `global_mode` before anything was fitted and that comparison stands
as written. It is reported beside it, and it was found by asking why the floor was so low,
not by shopping for a better number.

All three corpora run: unlike T-A this target needs no dwell, so Firefox is included.
Aggregates only; no domain, URL or title is written anywhere by this script.
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
from tise_research.eval.intervals import Interval  # noqa: E402
from tise_research.eval.multiclass import (  # noqa: E402
    MulticlassResult,
    accuracy_difference_interval,
    run_multiclass_backtest,
)
from tise_research.features.sessions import sessionise  # noqa: E402
from tise_research.features.transitions import (  # noqa: E402
    CategoryTransition,
    category_transitions,
    session_boundaries_without_change,
)
from tise_research.models.next_category import (  # noqa: E402
    BAR_MODEL,
    BOUNCE_BACK_MODEL,
    CHALLENGER_MODEL,
    CONSTRAINED_MODEL,
    fit_bounce_back,
    fit_constrained_mode,
    fit_global_mode,
    fit_transition_ranker,
)

TIMEOUT_SECONDS = 1800.0
N_FOLDS = 5

#: D27. Kept as a *source* category, dropped as an answer — see the module docstring.
EXCLUDED_TARGET = "unknown"

#: The corpus D94 stated the adoption rule over, named before anything was fitted.
ADOPTION_CORPUS = "history-edge"

#: T19's value for the always-the-mode rule on the between-session label set. Printed for
#: continuity with D91 and **never compared against**: it belongs to different labels.
T19_BETWEEN_SESSION_FLOOR = 0.332

#: Share of pooled test rows in one session above which the interval is flagged as
#: concentrated. Declared as a reporting threshold in T-A; no adoption decision reads it.
CONCENTRATION_FLAG = 0.20

MODELS = {
    BAR_MODEL: fit_global_mode,
    CHALLENGER_MODEL: fit_transition_ranker,
    BOUNCE_BACK_MODEL: fit_bounce_back,
    CONSTRAINED_MODEL: fit_constrained_mode,
}


@dataclass(frozen=True, slots=True)
class Variant:
    """One label set scored end to end. The headline and the all-labels run share this."""

    name: str
    transitions: int
    result: MulticlassResult
    #: The pre-registered comparison: the table against the floor, clustered by session.
    session_interval: Interval | None
    #: The same comparison clustered by source category — D94 requires both, side by side.
    source_interval: Interval | None
    #: Rows, the optimistic bound. Reported for the ladder, never for a claim.
    row_interval: Interval | None
    #: The table against `bounce_back`. Not the bar; the rival that would make the table
    #: redundant if it matched it.
    rival_interval: Interval | None
    #: `bounce_back` against the floor, so a reader can see whether the rival beats the bar
    #: even where the table does not.
    rival_vs_bar: Interval | None
    #: The table against `constrained_mode` — what the counts are worth once the floor is
    #: told the one thing the label guarantees. Added after seeing the result; see below.
    constrained_interval: Interval | None
    #: Share of the bar's pooled predictions that were the source category, and therefore
    #: impossible by construction. The number that motivated `constrained_mode`.
    bar_impossible_share: float
    test_sessions: int
    largest_session_share: float
    median_session_size: int

    def top1(self, model: str) -> float:
        return self.result.models[model].top1

    def top3(self, model: str) -> float:
        return self.result.models[model].top3

    @property
    def adopted(self) -> bool:
        """D94's rule, evaluated. Nothing else in this file may decide it."""
        interval = self.session_interval
        return interval is not None and interval.excludes_zero and interval.point > 0.0

    @property
    def concentrated(self) -> bool:
        return self.largest_session_share >= CONCENTRATION_FLAG


@dataclass(frozen=True, slots=True)
class CorpusResult:
    name: str
    events: int
    sessions: int
    #: Session boundaries the run-collapse absorbed because the category did not change.
    #: The declared cost of "a label is a change", printed rather than asserted small.
    boundaries_without_change: int
    all_labels: int
    within_session: int
    unknown_answers: int
    #: The D27-consistent run. The verdict is read off this one.
    headline: Variant
    #: Every label including `unknown` answers. Reported beside, never inside, the verdict.
    with_unknown: Variant


def _scored(name: str, transitions: list[CategoryTransition]) -> Variant:
    result = run_multiclass_backtest(transitions, MODELS, n_folds=N_FOLDS)
    outcomes = result.pooled_outcomes
    table = result.pooled_predictions[CHALLENGER_MODEL]
    bar = result.pooled_predictions[BAR_MODEL]
    rival = result.pooled_predictions[BOUNCE_BACK_MODEL]
    constrained = result.pooled_predictions[CONSTRAINED_MODEL]

    impossible = sum(
        1
        for prediction, source in zip(bar, result.pooled_sources, strict=True)
        if prediction == source
    )
    per_session = Counter(result.pooled_sessions)
    sizes = sorted(per_session.values(), reverse=True)

    return Variant(
        name=name,
        transitions=len(transitions),
        result=result,
        session_interval=accuracy_difference_interval(
            outcomes, table, bar, subjects=result.pooled_sessions, unit="session"
        ),
        source_interval=accuracy_difference_interval(
            outcomes, table, bar, subjects=result.pooled_sources, unit="subject"
        ),
        row_interval=accuracy_difference_interval(outcomes, table, bar),
        rival_interval=accuracy_difference_interval(
            outcomes, table, rival, subjects=result.pooled_sessions, unit="session"
        ),
        rival_vs_bar=accuracy_difference_interval(
            outcomes, rival, bar, subjects=result.pooled_sessions, unit="session"
        ),
        constrained_interval=accuracy_difference_interval(
            outcomes, table, constrained, subjects=result.pooled_sessions, unit="session"
        ),
        bar_impossible_share=(impossible / len(outcomes)) if outcomes else 0.0,
        test_sessions=len(per_session),
        largest_session_share=(sizes[0] / len(outcomes)) if sizes and outcomes else 0.0,
        median_session_size=sizes[len(sizes) // 2] if sizes else 0,
    )


def measure(copy_path: Path, *, view: str) -> CorpusResult:
    events = load_events(copy_path, view=view)
    sessions = sessionise(events, timeout_seconds=TIMEOUT_SECONDS)
    transitions = category_transitions(sessions)

    headline = [item for item in transitions if item.to_category != EXCLUDED_TARGET]
    if len(headline) < N_FOLDS * 2:
        raise ValueError(f"{copy_path.stem}: only {len(headline)} labels after D27")

    return CorpusResult(
        name=copy_path.stem,
        events=len(events),
        sessions=len(sessions),
        boundaries_without_change=session_boundaries_without_change(sessions),
        all_labels=len(transitions),
        within_session=sum(1 for item in transitions if item.within_session),
        unknown_answers=sum(
            1 for item in transitions if item.to_category == EXCLUDED_TARGET
        ),
        headline=_scored("headline", headline),
        with_unknown=_scored("with-unknown", list(transitions)),
    )


def _described(interval: Interval | None) -> str:
    return "not computable" if interval is None else interval.describe()


def _model_table(variant: Variant) -> str:
    rows = ["| Model | Top-1 | Top-3 | Rows |", "|---|---:|---:|---:|"]
    for model in sorted(variant.result.models.values(), key=lambda m: -m.top1):
        mark = {
            CHALLENGER_MODEL: " **(the model)**",
            BAR_MODEL: " *(the bar)*",
            BOUNCE_BACK_MODEL: " *(a rival, not the bar)*",
            CONSTRAINED_MODEL: " *(a rival, added post-hoc, not the bar)*",
        }.get(model.name, "")
        rows.append(
            f"| `{model.name}`{mark} | {model.top1:.1%} | {model.top3:.1%} | {model.n:,} |"
        )
    return "\n".join(rows)


def _fold_table(variant: Variant) -> str:
    rows = [
        f"| Fold | Train | Test | `{BAR_MODEL}` | `{CHALLENGER_MODEL}` | Winner |",
        "|---:|---:|---:|---:|---:|---|",
    ]
    for fold in variant.result.folds:
        scores = dict(fold.accuracy)
        bar = scores.get(BAR_MODEL)
        table = scores.get(CHALLENGER_MODEL)
        if bar is None or table is None:
            continue
        winner = "table" if table > bar else ("bar" if bar > table else "tie")
        rows.append(
            f"| {fold.index} | {fold.train_size:,} | {fold.test_size:,} | "
            f"{bar:.1%} | {table:.1%} | {winner} |"
        )
    return "\n".join(rows)


def _source_table(variant: Variant) -> str:
    rows = [
        f"| From | Test rows | `{BAR_MODEL}` | `{CHALLENGER_MODEL}` | Most common answer |",
        "|---|---:|---:|---:|---|",
    ]
    for source in sorted(
        variant.result.per_source.values(), key=lambda item: -item.n
    ):
        if not source.reported or source.top1 is None:
            rows.append(
                f"| `{source.from_category}` | {source.n} | — | — | "
                f"*below the {variant.result.min_source_labels}-row floor (D26)* |"
            )
            continue
        rows.append(
            f"| `{source.from_category}` | {source.n} | "
            f"{source.top1[BAR_MODEL]:.1%} | {source.top1[CHALLENGER_MODEL]:.1%} | "
            f"`{source.most_common_target}` |"
        )
    return "\n".join(rows)


def _section(item: CorpusResult) -> str:
    headline = item.headline
    verdict = (
        "**Clears its bar.**"
        if headline.adopted
        else "**Does not clear its bar** — the session-clustered interval includes zero."
    )
    concentration = (
        f"\n\n> **Concentration flag.** One session holds "
        f"{headline.largest_session_share:.0%} of the pooled test rows. A cluster count is "
        f"not cluster quality: most resamples are decided by whether that one session was "
        f"drawn. Reported, and no part of the verdict."
        if headline.concentrated
        else ""
    )
    return f"""### `{item.name}`

{item.events:,} events, {item.sessions:,} sessions, **{item.all_labels:,} category
changes** ({item.within_session:,} within a session, {item.all_labels - item.within_session:,}
across a boundary). {item.boundaries_without_change:,} session boundaries produced no label
because the category did not change. After D27, **{headline.transitions:,} labels** carry a
presentable answer; {item.unknown_answers:,} answered `{EXCLUDED_TARGET}`.

{verdict}

{_model_table(headline)}

- **Session-clustered, the pre-registered unit:** {_described(headline.session_interval)}
- Source-category clustered, D94's side-by-side: {_described(headline.source_interval)}
- Rows, the optimistic bound: {_described(headline.row_interval)}
- The table against `{BOUNCE_BACK_MODEL}` *(a rival)*: {_described(headline.rival_interval)}
- `{BOUNCE_BACK_MODEL}` against the bar: {_described(headline.rival_vs_bar)}
- The table against `{CONSTRAINED_MODEL}` *(a rival, post-hoc)*:
  {_described(headline.constrained_interval)}

**The bar spent {headline.bar_impossible_share:.1%} of its predictions on the source
category**, which a category *change* can never answer. The table did so on 0.0% of rows,
because a source's row holds no self-count. That much of the margin below is the floor
being handicapped rather than the table learning.

Pooled test rows span {headline.test_sessions:,} sessions, median {headline.median_session_size}
rows each, largest {headline.largest_session_share:.0%}.{concentration}

**With `{EXCLUDED_TARGET}` answers kept** ({item.with_unknown.transitions:,} labels), for
comparison and not for the verdict: the bar reaches
{item.with_unknown.top1(BAR_MODEL):.1%} and the table
{item.with_unknown.top1(CHALLENGER_MODEL):.1%}, session-clustered
{_described(item.with_unknown.session_interval)}.

#### Folds

{_fold_table(headline)}

#### By source category

{_source_table(headline)}
"""


def write_report(items: list[CorpusResult], *, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "next-category.md"

    adoption = next((item for item in items if item.name == ADOPTION_CORPUS), None)
    if adoption is None:
        outcome = (
            f"**No verdict.** D94 states the adoption rule over `{ADOPTION_CORPUS}`, which "
            "did not run. Nothing on this page adopts anything."
        )
    elif adoption.headline.adopted:
        outcome = (
            f"**`{CHALLENGER_MODEL}` clears its bar on `{ADOPTION_CORPUS}`.** "
            f"{_described(adoption.headline.session_interval)}"
        )
    else:
        outcome = (
            f"**`{CHALLENGER_MODEL}` does not clear its bar on `{ADOPTION_CORPUS}`.** "
            f"{_described(adoption.headline.session_interval)} — so the interval does not "
            "support a directional claim, and T-C is not adopted."
        )

    def verdict(interval: Interval | None) -> str:
        """A claim only where the interval supports one. Point estimates are not verdicts."""
        if interval is None:
            return "not computable"
        if not interval.excludes_zero:
            return "**not established**"
        return "**yes**" if interval.point > 0.0 else "**no — worse**"

    summary = "\n".join(
        [
            f"| Corpus | Labels | `{CHALLENGER_MODEL}` | Clears the bar? | "
            f"Beats `{CONSTRAINED_MODEL}`? |",
            "|---|---:|---:|---|---|",
        ]
        + [
            f"| `{item.name}` | {item.headline.transitions:,} | "
            f"{item.headline.top1(CHALLENGER_MODEL):.1%} | "
            f"{verdict(item.headline.session_interval)} | "
            f"{verdict(item.headline.constrained_interval)} |"
            for item in items
        ]
    )

    impossible = "\n".join(
        [
            f"| Corpus | Bar's impossible predictions | `{BAR_MODEL}` | "
            f"`{CONSTRAINED_MODEL}` |",
            "|---|---:|---:|---:|",
        ]
        + [
            f"| `{item.name}` | {item.headline.bar_impossible_share:.1%} | "
            f"{item.headline.top1(BAR_MODEL):.1%} | "
            f"{item.headline.top1(CONSTRAINED_MODEL):.1%} |"
            for item in items
        ]
    )

    floors = "\n".join(
        f"| `{item.name}` | {item.headline.top1(BAR_MODEL):.1%} | "
        f"{item.headline.transitions:,} |"
        for item in items
    )

    path.write_text(
        f"""# T-C · `next_category` — what comes next?

Generated by `analysis/next_category.py`. **Do not edit by hand.** Regenerate with:

```
uv run python analysis/next_category.py
```

One label per **category change**: the run of visits you just finished ended, and something
different started. Within sessions as well as across their boundaries (D94). Multiclass,
scored on **top-1 accuracy**, top-3 reported alongside.

## The model being tested has existed since T10 and had never been scored

`TransitionTable` ships in both languages and drives the "what's next" surface. Nothing had
ever measured it. That is T-C, and it is the reason this page exists.

## Everything here was fixed in D94, before anything was fitted

- **Label:** every category change, within sessions as well as between them.
- **Metric:** top-1 accuracy. Top-3 is reported and is **not** the bar — reading a verdict
  off it after seeing top-1 would be choosing the metric from the result.
- **Bar:** the always-the-global-mode floor.
- **Cluster unit:** session, with the source category reported side by side.
- **Adoption:** the interval on the accuracy difference against the floor excludes zero in
  the model's favour on `{ADOPTION_CORPUS}`.

### The rule was pre-registered. The 33.2% was not the number.

D91 and T19 measured **{T19_BETWEEN_SESSION_FLOOR:.1%}** for the always-the-mode rule over a
different label set: one primary category per session, self-transitions permitted. T-C's
labels are category *changes*, so the same rule scores differently here and its value is
**measured on these labels**:

| Corpus | Measured floor | Headline labels |
|---|---:|---:|
{floors}

Fixing the *number* would also have made D94's own adoption rule inapplicable — a paired
bootstrap needs the reference's prediction on every row, and a constant has none.

### A label is a change, and that choice costs something

Consecutive visits in one category collapse into a single run, so `from` and `to` always
differ. That removes the easy, high-volume, highly predictable mass — "you will keep doing
what you are doing" — and leaves the hard half. It also means a session boundary where the
category did not change produces **no** label; each corpus below reports how many.

### `{EXCLUDED_TARGET}` is excluded from the answer, not from the question (D27)

No surface can show a chip reading *{EXCLUDED_TARGET}*, and that bucket is the person's own
frequent domains, so it is both unpresentable and unusually predictable. Labels answering
`{EXCLUDED_TARGET}` are dropped from the headline; labels *conditioned on* it are kept. The
all-labels variant is printed for every corpus.

## Result

{outcome}

{summary}

Every column is read off a session-clustered interval, not a point estimate. Two models can
differ by four points and support no claim at all, and this project has published that
mistake before (D80).

`{BOUNCE_BACK_MODEL}` predicts the category you were on *before* the one just finished and
reads no counts at all. It is the cheapest thing that could make a fitted table redundant,
and D24 makes baselines mandatory for exactly that reason. It is **not** the bar.

### The bar is wrong before it starts on a third of the rows

A label is a category *change*, so the answer can never be the source. `{BAR_MODEL}` does
not know that and predicts one category regardless; on every row where the source **is** the
global mode it is guaranteed wrong. Per corpus, the share of the bar's predictions that were
impossible by construction:

{impossible}

`{CHALLENGER_MODEL}` never does this — a source's row in the table holds no self-count — so
part of its margin is the floor being handicapped rather than counts being learned.

**`{CONSTRAINED_MODEL}` separates the two.** It is the global mode with the source category
removed: it knows the one thing the label guarantees and nothing else. Whatever the table
beats it by is what the counts are worth on top of that.

**It was added after these numbers existed, and it cannot change the verdict.** D94 named
`{BAR_MODEL}` before anything was fitted and that comparison stands exactly as written. This
one is reported beside it. It was found by asking why the floor was so low, which is a
different act from choosing a bar that flatters a model — but the ordering is the reader's
to judge, so it is stated rather than smoothed over.

## Results

{chr(10).join(_section(item) for item in items)}

## Limitations

- **A session is a declared 30-minute gap** (D17), and the cluster unit inherits that guess.
  Too long a timeout merges sittings into one cluster and widens the interval; too short
  splits one and narrows it. The `idle` permission (D96) is what would replace the guess
  with a measurement.
- **Cluster counts are not cluster quality.** Both are printed per corpus.
- **Categories are a fixed public map.** Roughly a fifth of visits land in
  `{EXCLUDED_TARGET}`, by design — the map excludes employer, school, council and
  neighbourhood domains, because a domain list is a profile. D88 promoted shrinking that
  bucket, and D95 measured that session co-occurrence clustering does not reach it.
- **One person's browsing**, three browsers, never merged (D18). Agreement between corpora
  is weaker evidence than agreement between people would be.
- **The model reads only the source category.** No time of day, no domain, no run length,
  no recency. That is what the shipped table is; a richer multiclass model is a different
  target and is not registered.
- **No path or URL features.** The URL is dropped at the reader boundary.
""",
        encoding="utf-8",
    )
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "docs" / "benchmarks")
    parser.add_argument(
        "--view", default=DEFAULT_VIEW, choices=["shipped", "chosen", "raw"]
    )
    args = parser.parse_args()

    copies = (
        [args.corpus]
        if args.corpus
        else sorted((REPO_ROOT / "data").glob("history-*.copy"))
    )
    items: list[CorpusResult] = []
    for copy_path in copies:
        try:
            item = measure(copy_path, view=args.view)
        except ValueError as error:
            print(f"Skipping {error}")
            continue
        items.append(item)
        headline = item.headline
        print(
            f"{item.name}: {item.all_labels:,} changes, {headline.transitions:,} after D27, "
            f"{CHALLENGER_MODEL} {headline.top1(CHALLENGER_MODEL):.1%} vs bar "
            f"{headline.top1(BAR_MODEL):.1%} vs {BOUNCE_BACK_MODEL} "
            f"{headline.top1(BOUNCE_BACK_MODEL):.1%}"
        )
        print(f"  session-clustered vs the bar: {_described(headline.session_interval)}")

    if not items:
        print("No corpus produced enough category changes.")
        return 1

    print(f"Wrote {write_report(items, out_dir=args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
