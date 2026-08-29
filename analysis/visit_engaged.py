"""T-A — `visit_engaged`: will this visit hold you? **A pre-registered adoption test.**

    uv run python analysis/visit_engaged.py

Writes `docs/benchmarks/visit-engaged.md`.

Everything this script scores was fixed in **D94, before any model was fitted to it**: the
label, the feature set, the bar, the cluster unit and the adoption rule. Git holds the
order. That is the whole difference between this page and `analysis/attention.py`, which
measured the same label in D93 and was explicitly forbidden from adopting anything.

**The label is deliberately unchanged from D93.** Same visits, same median split, same
outcome. Two things and only two things move:

* **Features** — `as_2` adds four domain features and two sequence features to `as_1`'s
  twelve. `domain` has been stored since T1 and read by **zero** features until now, and no
  target this project has tried has ever looked at the order of visits.
* **The cluster unit** — **session**, not category. Every interval this project published
  was resampled over 9-12 clusters because the subject was always the category. D93 had
  2,805 test rows and an interval built from **11 things**, and missed excluding zero by
  0.0001. Width scales with one over the square root of the cluster count.

Keeping the label fixed is what makes the difference attributable. Both models are fitted
inside **one** `run_backtest` call, so their folds are identical by construction rather than
by two scripts agreeing — the same reason `tournament.py` is built that way.

**The bar is a constant.** D93 established that `category_base_rate` is *worse* than a
constant on this label, because a per-category median split makes every category ~50% by
construction. Scoring against it would be scoring against a baseline the label sabotages.

Firefox records no duration and is skipped (D18: corpora are never merged). Aggregates
only; no domain, URL or title is written anywhere by this script.
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
from tise_research.eval.intervals import Interval, brier_difference_interval  # noqa: E402
from tise_research.features.attention import (  # noqa: E402
    ATTENTION_FEATURE_SET,
    DAILY_DOMAIN_MIN_DAYS,
    DAILY_DOMAIN_WINDOW_DAYS,
    DEFAULT_MIN_PRIOR_VISITS,
    DEFAULT_TRAILING_VISITS,
    DOMAIN_SHARE_WINDOW,
    DOMAIN_VISIT_SCALE,
    ENGAGED_FEATURE_SET,
    attention_examples,
)
from tise_research.features.labels import Label  # noqa: E402
from tise_research.features.vector import FeatureRow  # noqa: E402
from tise_research.models.baselines import Baseline, fit_per_key  # noqa: E402
from tise_research.models.logreg import DEFAULT_SPEC, predict_proba, train  # noqa: E402
from tise_research.models.prep import design_columns, fit_preprocessor  # noqa: E402

TIMEOUT_SECONDS = 1800.0
N_FOLDS = 5

#: D94. The constant, not the per-category rate — see the module docstring.
BAR_MODEL = "global_base_rate"

#: The rival the report would be dishonest without, added in D97. Four of `as_2`'s six new
#: features read the domain, so "a per-domain rate table would do the same job" is the first
#: thing a sceptical reader should be able to check, and D24 makes baselines mandatory.
#:
#: **It is not the bar.** D94 fixed the bar as a constant before anything was fitted;
#: promoting this to the bar after seeing the coefficients would be choosing the rule from
#: the result. It is reported beside the verdict and never inside it.
DOMAIN_BAR = "domain_base_rate"

#: Matches `category_base_rate`, so the two rate tables differ only in what they key on.
BASELINE_SMOOTHING = 5.0

#: The corpus the adoption rule is stated over. Edge is the larger of the two with dwell,
#: and D94 named it before any of this was fitted so it could not be chosen afterwards.
ADOPTION_CORPUS = "history-edge"

#: Share of the pooled test rows in a single cluster above which the interval is flagged as
#: concentrated. A cluster bootstrap over n groups is only worth its n if the groups are of
#: comparable size: if one holds most of the rows, most resamples are decided by whether
#: that one group was drawn, and the width understates how little independent evidence
#: there is. A fifth is **declared, not fitted** — it is a reporting threshold, and no
#: adoption decision reads it.
CONCENTRATION_FLAG = 0.20


def model_name(feature_set: str) -> str:
    """`as_2` -> `logreg_as2`. Derived, never typed: D87 shipped a hardcoded model name
    next to a dynamic feature set, and a test pinned the bug rather than catching it."""
    return f"logreg_{feature_set.replace('_', '')}"


CHALLENGER = model_name(ENGAGED_FEATURE_SET)
INCUMBENT = model_name(ATTENTION_FEATURE_SET)


@dataclass(frozen=True, slots=True)
class _Model(Baseline):
    name: str
    feature_set: str
    preprocessor: object
    state: object
    rows: dict[str, FeatureRow]

    def predict(self, label: Label) -> float:
        row = self.rows[label.label_id]
        return predict_proba(self.state, self.preprocessor.transform(row))  # type: ignore[attr-defined]


def _fitter(name: str, feature_set: str, rows: dict[str, FeatureRow]):
    def fit(labels):
        window = [rows[label.label_id] for label in labels]
        preprocessor = fit_preprocessor(window)
        state = train(
            preprocessor.matrix(window),
            [label.outcome for label in labels],
            spec=DEFAULT_SPEC,
            n_columns=len(design_columns(feature_set)),
        )
        return _Model(name, feature_set, preprocessor, state, rows)

    return fit


def _domain_rate_fitter(domains: dict[str, str]):
    """A smoothed rate per domain, keyed the same way the feature rows are."""

    def fit(labels):
        return fit_per_key(
            labels,
            name=DOMAIN_BAR,
            key=lambda label: domains[label.label_id],
            smoothing=BASELINE_SMOOTHING,
        )

    return fit


@dataclass(frozen=True, slots=True)
class CorpusResult:
    name: str
    events: int
    with_dwell: int
    sessions: int
    result: BacktestResult
    #: The pre-registered comparison: `as_2` against the constant, clustered by session.
    session_interval: Interval | None
    #: The same comparison under the old cluster unit, so the effect of *changing the unit*
    #: is visible rather than asserted. D94 predicted this is where the width goes.
    subject_interval: Interval | None
    #: Rows, the optimistic bound. Reported for the ladder, never for a claim.
    row_interval: Interval | None
    #: `as_2` against `as_1` on identical folds — what the six new features are worth on
    #: their own, separated from what the cluster unit is worth.
    feature_interval: Interval | None
    #: `as_2` against a per-domain rate table. Not the bar; the rival that would make the
    #: model redundant if it matched it.
    domain_interval: Interval | None
    #: How many distinct domains the rate table held. A table with one bucket per row
    #: memorises rather than generalises, and the count is the only way to see that.
    train_domains: int
    coefficients: tuple[tuple[str, float], ...]
    #: How the pooled test rows are spread across the sessions they were clustered by.
    #: An interval over 27 clusters means something quite different when one of them holds
    #: 43% of the rows, and the count alone does not say which case you are in.
    test_sessions: int
    largest_session_share: float
    median_session_size: int

    def brier(self, name: str) -> float:
        return self.result.models[name].brier

    @property
    def adopted(self) -> bool:
        """The pre-registered rule, evaluated. Nothing else in this file may decide it."""
        interval = self.session_interval
        return interval is not None and interval.excludes_zero and interval.point > 0.0

    @property
    def concentrated(self) -> bool:
        """Reported alongside the verdict, never part of it.

        D94 fixed the adoption rule before anything was fitted. Adding a concentration
        condition now — after seeing which corpus is concentrated — would be choosing the
        rule from the result, which is the whole thing pre-registration exists to stop.
        """
        return self.largest_session_share >= CONCENTRATION_FLAG


def measure(copy_path: Path, *, view: str) -> CorpusResult:
    events = load_events(copy_path, view=view)
    with_dwell = sum(1 for event in events if event.dwell_seconds is not None)
    if not with_dwell:
        raise ValueError(f"{copy_path.stem}: no dwell recorded")

    both = {
        feature_set: attention_examples(
            events, timeout_seconds=TIMEOUT_SECONDS, feature_set=feature_set
        )
        for feature_set in (ATTENTION_FEATURE_SET, ENGAGED_FEATURE_SET)
    }
    incumbent, challenger = both[ATTENTION_FEATURE_SET], both[ENGAGED_FEATURE_SET]

    # D94 claims the label is identical across the two sets. Checked, not trusted: if it
    # ever stops being true, every comparison on this page silently becomes a comparison
    # between two different questions.
    if [example.label for example in incumbent] != [
        example.label for example in challenger
    ]:
        raise AssertionError(
            f"{copy_path.stem}: {ATTENTION_FEATURE_SET} and {ENGAGED_FEATURE_SET} "
            "produced different labels. The comparison on this page assumes they do not."
        )

    if len(challenger) < N_FOLDS * 2:
        raise ValueError(f"{copy_path.stem}: only {len(challenger)} labels")

    rows = {
        feature_set: {
            example.label.label_id: example.row
            for example in examples
        }
        for feature_set, examples in both.items()
    }
    domains = {
        example.label.label_id: example.domain
        for example in challenger
    }
    labels = [example.label for example in challenger]
    result = run_backtest(
        labels,
        n_folds=N_FOLDS,
        extra_models={
            INCUMBENT: _fitter(
                INCUMBENT, ATTENTION_FEATURE_SET, rows[ATTENTION_FEATURE_SET]
            ),
            CHALLENGER: _fitter(
                CHALLENGER, ENGAGED_FEATURE_SET, rows[ENGAGED_FEATURE_SET]
            ),
            DOMAIN_BAR: _domain_rate_fitter(domains),
        },
    )

    outcomes = result.pooled_outcomes
    model = result.pooled_probabilities[CHALLENGER]
    bar = result.pooled_probabilities[BAR_MODEL]

    per_session = Counter(result.pooled_sessions)
    sizes = sorted(per_session.values(), reverse=True)

    fitted = _fitter(CHALLENGER, ENGAGED_FEATURE_SET, rows[ENGAGED_FEATURE_SET])(labels)
    return CorpusResult(
        test_sessions=len(per_session),
        largest_session_share=(sizes[0] / len(outcomes)) if sizes and outcomes else 0.0,
        median_session_size=sizes[len(sizes) // 2] if sizes else 0,
        name=copy_path.stem,
        events=len(events),
        with_dwell=with_dwell,
        sessions=len({label.session_id for label in labels}),
        result=result,
        session_interval=brier_difference_interval(
            outcomes, model, bar, subjects=result.pooled_sessions, unit="session"
        ),
        subject_interval=brier_difference_interval(
            outcomes, model, bar, subjects=result.pooled_subjects
        ),
        row_interval=brier_difference_interval(outcomes, model, bar),
        feature_interval=brier_difference_interval(
            outcomes,
            model,
            result.pooled_probabilities[INCUMBENT],
            subjects=result.pooled_sessions,
            unit="session",
        ),
        domain_interval=brier_difference_interval(
            outcomes,
            model,
            result.pooled_probabilities[DOMAIN_BAR],
            subjects=result.pooled_sessions,
            unit="session",
        ),
        train_domains=len(set(domains.values())),
        coefficients=tuple(
            zip(
                design_columns(ENGAGED_FEATURE_SET),
                fitted.state.weights,  # type: ignore[attr-defined]
                strict=True,
            )
        ),
    )


def _described(interval: Interval | None) -> str:
    return "not computable" if interval is None else interval.describe()


def _section(item: CorpusResult) -> str:
    rows = ["| Model | Brier | Log loss | Skill |", "|---|---:|---:|---:|"]
    for model in sorted(item.result.models.values(), key=lambda m: m.brier):
        mark = ""
        if model.name == CHALLENGER:
            mark = " **(the model)**"
        elif model.name == INCUMBENT:
            mark = " *(D93's model)*"
        elif model.name == BAR_MODEL:
            mark = " *(the bar)*"
        elif model.name == DOMAIN_BAR:
            mark = " *(the rival, not the bar)*"
        skill = "reference" if model.skill is None else f"{model.skill:+.3f}"
        rows.append(
            f"| `{model.name}`{mark} | {model.brier:.4f} | {model.log_loss:.4f} | {skill} |"
        )

    weights = ["| Feature | Standardised weight |", "|---|---:|"]
    new = set(design_columns(ENGAGED_FEATURE_SET)) - set(
        design_columns(ATTENTION_FEATURE_SET)
    )
    for name, weight in sorted(item.coefficients, key=lambda pair: -abs(pair[1])):
        mark = " **(new in `as_2`)**" if name in new else ""
        weights.append(f"| `{name}`{mark} | {weight:+.3f} |")

    verdict = "**clears its bar**" if item.adopted else "**does not clear its bar**"
    if item.concentrated:
        concentration = (
            f"**Concentrated.** The largest single session holds "
            f"**{item.largest_session_share:.1%}** of the {len(item.result.pooled_outcomes):,} "
            f"pooled test rows, against a median session of {item.median_session_size}. "
            f"An interval over {item.test_sessions} clusters is worth {item.test_sessions} "
            "clusters only when they are of comparable size; here most resamples are "
            "decided by whether that one session was drawn, so the width below is more "
            "optimistic than its `n=` suggests. Read this corpus as weaker evidence than "
            "its interval reads."
        )
    else:
        concentration = (
            f"**Evenly spread.** The largest single session holds "
            f"{item.largest_session_share:.1%} of the "
            f"{len(item.result.pooled_outcomes):,} pooled test rows, median session "
            f"{item.median_session_size}. No cluster dominates the resampling."
        )

    return f"""### {item.name}

{item.events:,} events, {item.with_dwell:,} with a recorded duration.
**{item.result.label_count:,} labels** across {item.sessions:,} sessions,
{len(item.result.pooled_outcomes):,} pooled test rows, base rate
{item.result.overall_base_rate:.1%}.

{chr(10).join(rows)}

#### The pre-registered comparison

`{CHALLENGER}` against `{BAR_MODEL}`, paired, **clustered by session**. Positive favours
the model. On this corpus it {verdict}:

{_described(item.session_interval)}

#### How the clusters are spread

{concentration}

#### The same difference under three units

The point estimate is identical in all three rows — only the width moves, and it moves with
the number of things resampled. This is the ladder D94 was written about:

| Unit | Interval |
|---|---|
| session | {_described(item.session_interval)} |
| subject (the old unit) | {_described(item.subject_interval)} |
| row (optimistic, never a claim) | {_described(item.row_interval)} |

#### What the six new features are worth

`{CHALLENGER}` against `{INCUMBENT}` on identical folds — the features alone, with the
cluster unit held fixed:

{_described(item.feature_interval)}

#### Would a per-domain rate table do the same job?

The question the coefficient table invites, and the one this page would be dishonest
without. `{DOMAIN_BAR}` is a smoothed rate per domain — the same construction as
`category_base_rate`, same smoothing, keyed on the domain instead of the category. It is
fitted per fold on that fold's training window alone; across the whole corpus the labelled
visits span **{item.train_domains:,} distinct domains**, against fifteen categories.
`{CHALLENGER}` against it, session-clustered:

{_described(item.domain_interval)}

**This is not the bar.** D94 fixed the bar as a constant before anything was fitted, and
promoting a rival to the bar after seeing the coefficients would be choosing the rule from
the result.

#### Fitted weights

In-sample, standardised columns. Six features and their two indicators are new:

{chr(10).join(weights)}
"""


def write_report(items: list[CorpusResult], *, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "visit-engaged.md"

    adoption = next((item for item in items if item.name == ADOPTION_CORPUS), None)
    if adoption is None:
        outcome = (
            f"**Undecided.** The adoption corpus `{ADOPTION_CORPUS}` is not in this run, "
            "and the rule was written over it before anything was fitted."
        )
    elif adoption.adopted:
        outcome = (
            f"**`{ENGAGED_FEATURE_SET}` clears the bar on `{ADOPTION_CORPUS}`.** The "
            "session-clustered interval against the constant excludes zero in the model's "
            "favour, which is the rule D94 fixed in advance. This is the first target in "
            "the project to clear a bar that was registered before it was measured."
        )
        if adoption.concentrated:
            outcome += (
                f" **But its clusters are concentrated** — the largest session holds "
                f"{adoption.largest_session_share:.1%} of the pooled test rows, so the "
                "interval is more optimistic than its cluster count suggests. See the "
                "spread section below."
            )
    else:
        outcome = (
            f"**`{ENGAGED_FEATURE_SET}` does not clear the bar on `{ADOPTION_CORPUS}`.** "
            "The session-clustered interval against the constant includes zero. Under "
            "D94's stopping rule this target is not adopted, whatever the point estimate "
            "or the other corpus says."
        )

    both = [
        item.name
        for item in items
        if item.brier(CHALLENGER) < item.brier(INCUMBENT)
    ]
    beat_bar = [item.name for item in items if item.brier(CHALLENGER) < item.brier(BAR_MODEL)]
    beat_domain = [
        item.name for item in items if item.brier(CHALLENGER) < item.brier(DOMAIN_BAR)
    ]

    def listed(names: list[str]) -> str:
        return ", ".join(f"`{n}`" for n in names) if names else "**nothing**"

    path.write_text(
        f"""# T-A · `visit_engaged` — will this visit hold you?

Generated by `analysis/visit_engaged.py`. **Do not edit by hand.** Regenerate with:

```
uv run python analysis/visit_engaged.py
```

One label per visit: **did you stay longer than your recent median for this category?**
Trailing window {DEFAULT_TRAILING_VISITS} visits, minimum {DEFAULT_MIN_PRIOR_VISITS} prior.
Feature set `{ENGAGED_FEATURE_SET}`, **`full` compat class**.

## This one *can* adopt, and that is the difference

D91 fixed the discipline: a bar pre-registered **before** a model is fitted, or it is not a
bar. **D94 registered all of it in advance** — label, features, bar, cluster unit and the
adoption rule — and git holds the order. `docs/benchmarks/attention.md` measured this same
label in D93 and was explicitly forbidden from adopting anything, because no bar existed
when it ran.

**The bar is a constant** (`{BAR_MODEL}`), not the per-category rate. D93 measured that a
per-category median split makes every category ~50% by construction, so
`category_base_rate` is *worse* than a constant here and scoring against it would be
scoring against a baseline the label sabotages.

**The cluster is the session.** Every interval this project has published was resampled
over 9-12 clusters, because the subject was always the category. D93 had 2,805 test rows
and an interval built from **11 things**, and missed excluding zero by 0.0001.

**The label is unchanged from D93**, and the script asserts it rather than assuming it:
`{ATTENTION_FEATURE_SET}` and `{ENGAGED_FEATURE_SET}` must emit identical labels or the run
fails. Both models are fitted inside one backtest, so their folds are identical by
construction.

## Result

{outcome}

- `{CHALLENGER}` beats the bar (`{BAR_MODEL}`) on: {listed(beat_bar)}
- `{CHALLENGER}` beats D93's `{INCUMBENT}` on: {listed(both)}
- `{CHALLENGER}` beats a per-domain rate table (`{DOMAIN_BAR}`) on: {listed(beat_domain)}

The last one is the rival, not the bar — see each corpus below. Four of `as_2`'s six new
features read the domain, so a rate table keyed on the domain is the cheapest thing that
could make the model redundant, and D24 makes baselines mandatory for exactly this reason.

## What `as_2` adds

`{ATTENTION_FEATURE_SET}`'s twelve features, unchanged and in their original positions,
plus six:

| Feature | What it is | Nullable |
|---|---|---|
| `domainVisits` | prior visits to this domain, saturated at {DOMAIN_VISIT_SCALE:.0f} | no |
| `domainShare` | share of the last {DOMAIN_SHARE_WINDOW} visits that were this domain | no |
| `isDailyDomain` | seen on {DAILY_DOMAIN_MIN_DAYS} of the last """
        f"""{DAILY_DOMAIN_WINDOW_DAYS} days | no |
| `domainDwellLevel` | median dwell on this domain, saturated | **yes** |
| `prevSameDomain` | was the immediately preceding visit this domain | no |
| `prevDwellRatio` | the preceding visit's dwell over this category's threshold | **yes** |

The four marked `no` are **measured zeros**: a domain seen zero times has been seen zero
times, and an indicator column would claim the count was never taken. The two marked
**yes** are absences of a *different* history than the minimum-prior rule guarantees —
`domainDwellLevel` when this domain has no recorded duration yet, and `prevDwellRatio` when
the immediately preceding visit has none. Neither is filled with zero, which would say the
person left instantly rather than that nothing was measured (D51).

**Four of these are the first use of `domain` in the project.** It has been stored since T1
and read by exactly zero features. The other two are the first use of visit *order*:
`as_1`'s `sameAsPrevious` and `lastDwellRatio` both look at the previous visit **of this
category**, and these look at the immediately preceding visit whatever it was.

Every scale is **declared, not fitted** (D81), and everything unbounded is saturated.

## Results

{chr(10).join(_section(item) for item in items)}

## Limitations

- **A session is a declared 30-minute gap, and the cluster unit inherits that.** D17 fixed
  the timeout as a guess because T1 looked for an empirical trough in the gap distribution
  and found none. Clustering by session makes that guess load-bearing in a new way: too
  long a timeout merges what a person would call several sittings into one cluster and the
  interval widens; too short splits one sitting and it narrows. The `idle` permission (D96)
  is what would replace the guess with a measurement.
- **Cluster counts are not cluster quality.** Both are printed for each corpus, because a
  bootstrap over 27 groups where one holds 43% of the rows is not the same object as one
  over 27 comparable groups, and the `n=` alone cannot tell them apart.
- **One person's browsing**, two browsers. Firefox has no duration column at all.
- **Dwell here comes from the history database**, which the extension cannot read. D96
  ships live attention spans, and what they measure is *better* than `visit_duration` —
  which counts how long a tab held a URL, so a tab left open overnight records engagement
  that never happened. Nothing on this page corrects for that.
- **The two corpora are the same person**, so agreement between them is weaker evidence
  than two people agreeing would be.
- **No path or URL features.** `Visit` drops the URL at the reader boundary.
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
            f"{item.name}: {item.result.label_count:,} labels, {item.sessions:,} sessions, "
            f"{CHALLENGER} {item.brier(CHALLENGER):.4f} vs {INCUMBENT} "
            f"{item.brier(INCUMBENT):.4f} vs bar {item.brier(BAR_MODEL):.4f}"
        )
        print(f"  session-clustered vs the bar: {_described(item.session_interval)}")

    if not items:
        print("No corpus had usable dwell.")
        return 1

    print(f"Wrote {write_report(items, out_dir=args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
