# Tise V1 — Task List

Full detail in [`plan.md`](plan.md). Spec in [`../SPEC.md`](../SPEC.md).

Tick a task only when its verification commands pass. Each task leaves the repository
working and committable.

---

## ⚠ Read this first — two targets retired, the third adopted

**Go to [START HERE](#-start-here--phase-7-one-target-adopted-and-three-still-open) below (Phase 7).**
Everything above it is history, kept because it is the evidence trail.

- **`return_24h` retired** as the product target (D88) — measurable, and not a question
  anyone cares about.
- **`block_volume` retired too** (D92) — it produced labels but the model lost to *a single
  constant*, and `same_as_last` was far worse, so "above your usual" is close to independent
  day to day.
- **`visit_engaged` is adopted (D97)** — T-A cleared the bar D94 wrote down before the
  measurement, on both corpora with dwell. **It is not shipped**: it needs live attention
  spans and has no TypeScript twin, so the extension still trains `return_24h` and still
  shows nothing. That work is **T-G**.
- T-B, T-C, T-D remain pre-registered and **unfitted**; T-E and T-F are descriptive (D95).
- **`visit_engaged` REPLICATES on 1,326 other people (D100)** — +0.0091 [+0.0086, +0.0097],
  and it beats a constant for **88.6%** of them individually. T-A no longer rests on one
  person. **It is still not shipped** — that is T-G.

T1–T21 below are left ticked and unedited. The machinery they produced — collection,
sessions, features, parity, prediction, resolution, export, migration — is **reused**, not
rewritten. Do not redo them, and do not quote their numbers as current: the generated
reports in `docs/benchmarks/` carry superseded banners for the same reason.

Work order: **T-H is done and T-A survived it.** Next is **T-G** (ship `visit_engaged`,
gated on having enough live attention spans — a count from the store, not a date) or
**T-B → T-C → T-D**, with T-E/T-F available any time (both descriptive, neither needs to
clear a prediction bar).

---

## Phase 6 — The new target

- [x] **T18b · Make the public artifacts tell the truth after D88** · S · deps: D88
  - Verify: `uv run pytest` ✓ 629 Python, 338 TypeScript, both linters clean, builds
  - **`README.md` was pre-alpha-era and wrong five ways** — the repo's front page. Said
    *"no working code yet"*; listed `service/ Local Python service` and `ml/`, **neither of
    which exists and the first of which was explicitly rejected** — a reader auditing the
    privacy claim saw a local service described in the layout; said benchmarks were "not
    yet available" with twelve reports committed; and stated the duration trap **backwards**
    (implying live data has dwell time, when the API has none for either source)
  - **All 12 benchmark reports described a retired target with nothing saying so.** Same
    defect class as D86/D87 — right numbers, wrong frame — twelve times, in the public
    artifacts. Banners are now **generated** from `tise_research/reports.py`, never typed:
    a writer names its target, the module decides. `RETIRED_TARGETS` gains one line per
    retirement and every report updates on its next regeneration. Typing twelve banners
    would be twelve literals, which is exactly what went stale in the first place
  - Three tiers, because over-marking is its own dishonesty: **superseded** (8 reports),
    **partly superseded** (`history-shape-*`: visits/day, session boundaries and domain
    concentration stand; the label tables do not), and **untouched** (`import-simulation-*`
    is target-agnostic and correctly carries no banner)
  - Regeneration was **pure addition** — 8/12/8 lines added, 0 removed, **no figure moved**,
    which re-confirms determinism. Only deletion was a stale `--target return_24h` command
  - **A divergence I introduced an hour after writing D87 about divergence:** SPEC's
    `Prediction.target` union listed the new targets while `prediction.ts` still ships the
    old one. Fixed by marking shipped vs target-state rather than by changing TS — the
    extension still predicts `return_24h` until T21

- [x] **T19 · Measure all four candidate targets** · M · deps: none — **GATE FIRED** (D89)
  - Verify: `uv run python analysis/candidate_targets.py` ✓ — 646 Python, 338 TypeScript,
    both linters clean. Report at `docs/benchmarks/candidate-targets.md`
  - **`block_volume` is not adopted.** Chrome yields **1 label**, Firefox **0**, Edge **47**
    against `return_24h`'s 503 on the same browsing. A weekly block gives each topic two
    observations a week; a trailing median consumes most of eight weeks of them
  - **D88's 50/50 claim is false here — 60.6% / 57.1% on Edge** — and not for either reason
    D88 anticipated. Ties are 6.1%/0.0%, median-zero is 0.0%. **A median split is 50/50 only
    on a stationary series**, and volume trends are Chrome **5.45×**, Edge **3.57×**,
    Firefox **0.15×**. The base rate moves with each corpus's trend and changes direction
  - **The trend is probably history retention, not behaviour** — which is worse: medians
    bootstrapped from imported history would be systematically low, so the first live blocks
    read "above your usual" almost regardless of what the person did. Testable against the
    owed import-vs-live check
  - **`novelty` weekday is dead at 91.7%.** `dormancy` is usable (13–15%) but small
  - **`next_session_category` has 238 labels — five times every block target combined** —
    with a 33.2% always-the-mode floor against a 44.5% per-category mode. Both are modes of
    observed data, not fitted models. Built since T10 in both languages, **never benchmarked**
  - **Clustering `unknown` finds 0 clusters at every threshold 0.3–0.7.** Only 7 of Edge's
    67 `unknown` domains appear in ≥3 sessions. The bucket is a long tail of one-off
    domains, not hidden categories — the share is real, the proposed mechanism does not
    reach it
  - **A bug found inside T19 that changed the answer:** blocks existed only where events
    did, so a week with no browsing vanished. A weekend nobody browsed is a *real zero*;
    dropping it lifts every later median and deletes an informative label. Edge weekend
    labels 7 → 14. Found by the yield being implausible, not by a test — now covered
  - No model is fitted and nothing is scored. Purely descriptive, which is why D88 permits
    the data-sufficiency gate to be set *after* it
  - Per corpus, per candidate: **label yield, base rate, and how many topics survive**
    - `block_volume` — weekday and weekend separately; how many topics clear the
      qualifying rule (present in ≥ half the prior blocks) and how many die to the
      median-zero problem
    - `novelty` — base rate of "a domain not seen in the prior 30 days". **If this is near
      100% the target is dead**, and this is the number that says so
    - `dormancy` — how many of D26's 9 sub-floor categories become answerable
    - `next_session_category` — top-1/top-3 from the transition table that already exists
      and has **never been benchmarked**. Largest label supply of the four
  - Also: **cluster stability** from session co-occurrence + time-of-day, and what share of
    `unknown` becomes nameable. Currently 79 labels / 92.5% positive on Chrome, all discarded
  - Also: **counts vs shares** for `block_volume`. A share cancels a uniform import-vs-live
    offset; counts are more intuitive. Cheap to compute both now, expensive to retrofit
  - Verify: `uv run python analysis/candidate_targets.py` + tests; report at
    `docs/benchmarks/candidate-targets.md`
  - **Not to be done here:** choosing the target. That is T20, after these numbers exist

- [x] **T19b · A day as the block, measured** · S · deps: T19 — **Akash's question** (D90)
  - *"Let each day be a block? instead of weekday and weekend?"* — measured, it reverses
    D89's conclusion. Labels **48 → 403** from identical browsing, and **every corpus now
    produces some**: Chrome 1 → **124**, Edge 47 → **196**, Firefox 0 → **83**
  - **The zero-inflation risk I named did not materialise, and I had it backwards.** Daily
    counts are zero far more often, but the qualifying rule already excludes exactly those
    topics — present in ≥half the prior blocks implies a median ≥1. **Median-zero is 0.0%
    on all three corpora**; 4–7 topics survive per corpus
  - **Still not 50/50, and now missing low** — 36.3% / 39.3% / 47.0% against weekly's
    57–61%. Ties are 2.4–3.6% and cannot explain it. The target is no longer *saturated*,
    which is weaker than balanced but is the property that matters
  - **Shares are closer to balanced on all three** — 41.1% / 44.4% / 49.4%. Three corpora
    agreeing, unlike the single 50.0% D89 refused to read anything into
  - `block_volume` is **viable**, not correct. Nothing scored, no model fitted

- [x] **T20 · Pre-register the target** · S · deps: T19, T19b — **done** (D91)
  - Committed **before any model exists** for these targets. Git holds the order, as D81
  - **`block_volume`, daily** is the target. Every parameter declared: 10-block trailing
    window, 6 prior blocks minimum, present-in-half qualifying rule, **strict `>`**, and
    **raw counts rather than shares**
  - **Counts over shares was the close call.** Shares are nearer balanced (41–49% vs
    36–47%) and cancel the unmeasured import-vs-live offset. But shares are
    **compositional** — video spiking makes dev's card read "down" when dev did not move,
    which is arithmetically true and substantively false. And the offset argument is much
    weaker daily: a 10-block window spans **10 days**, so imports age out in a fortnight.
    Shares reported alongside throughout, so a wrong call here is visible
  - **What ships is now two independent questions**, a distinction `return_24h` never had:
    (1) does the target ship — yes if the user's own data clears the qualifying rule;
    (2) does the *learned model* ship, or the base-rate table? A card can be driven by
    `category_base_rate` alone, so **ML is justified only if it beats that**
  - **The bar:** paired Brier vs `category_base_rate`, subject-clustered, must **exclude
    zero in the model's favour on Edge**. Stricter than D81's adopt-unless-worse, because
    there the argument was structural and here the only argument *is* the score.
    **If unmet, the table ships** — an outcome with a written plan, not a failure
  - **Predictions:** (1) beats `global_base_rate` everywhere; (2) **not** distinguishable
    from `category_base_rate` on Edge — every such comparison in this project has included
    zero; (3) **`same_as_last` beats `category_base_rate` somewhere**, because daily
    browsing is bursty and a per-topic average cannot represent persistence. (3) is the one
    most likely to change what gets built
  - **`next_session_category` is secondary**, measured because it has never been
    benchmarked. Its bar is the **33.2% floor**, not the 44.5% per-category mode — that
    figure is in-sample and using it would score a model against its own fit. It can become
    primary only if `block_volume` fails its gate **on a real profile**, never by scoring
    better; that exception is written down precisely to stop the forking path

- [x] **T21 · Build and measure `block_volume`** · L · deps: T20 — **the table ships, not
      the model** (D92)
  - Verify: `uv run python analysis/block_volume.py` ✓ — 663 Python, 338 TypeScript, both
    linters clean. Report at `docs/benchmarks/block-volume.md`
  - **Two of D91's three predictions FAILED**, and the one that HELD was written so that
    holding it means the model misses its own bar
  - **Prediction 1 failed, and that is worse than missing the bar.** Edge: model **0.2607**
    against `global_base_rate` **0.2529** — *beaten by a single constant*, on all three
    corpora. Ten features and eleven design columns lose to predicting one number
  - **Prediction 3 failed, and it kills the mechanism `bs_1` was built around.**
    `same_as_last` scores 0.4140 vs the bar's 0.2479 on Edge — far worse, everywhere.
    Weights agree independently: `prevAbove` **−0.041**, `streakAbove` **+0.065**. So
    "was today above your usual?" is close to **independent day to day**
  - **The card survives; the model does not.** *"Shopping today · 71% — 11 of your last 15"*
    is `category_base_rate` alone: a per-topic rate, computable on-device with no training,
    and **nothing measured beats it**
  - **Across three targets the same finding:** on one person's browsing a per-topic rate is
    very hard to beat. Logreg on 14 features, on 18, XGBoost tuned for small data, and now a
    purpose-built block set have all failed to separate from one
  - `bs_1` declared in `vector.py` **before fitting**, with no TS twin — nothing ships until
    a target is adopted. Leakage is structural: labels and features emitted in one forward
    pass before the block joins any state, and `test_block_labels.py` asserts it

- [x] **T22b · Attention (dwell) — scouting measurement** · M · deps: T21 (D93)
  - Reasoning from the data rather than from a target put **dwell** at the top. One label
    per *visit*: did you stay longer than your recent median for this category?
  - Verify: `uv run python analysis/attention.py` ✓ — 675 Python, 338 TypeScript, clean.
    Report at `docs/benchmarks/attention.md`
  - **10,502 labels** against `block_volume`'s 403 — **26×** — and base rates of **50.0%
    and 50.3%**, the first target whose median split actually landed on 50%
  - **But it does not survive the honest comparison.** It separates from
    `category_base_rate` on both corpora — and that bar is **worse than a constant** here,
    because a per-category median split makes every category ~50% by construction, so
    estimating twelve identical rates only adds variance. Against a constant, **neither
    corpus separates**; Edge misses by **0.0001** on the lower bound
  - **`transition` carried real weight on its first ever use** — `arrivedLink` −0.212 and
    `arrivedTyped` −0.141, second and third largest. Collected since T1, read by no feature
    until now. **It belongs in every future feature set**, independent of this target
  - **The caveat that could explain all of it:** `visit_duration` measures how long a *tab
    held a URL*, not attention. A tab left open overnight looks like deep engagement.
    `idle` + window focus is what separates them — and that needs the `tabs` permission
  - Worth a pre-registration; **not** worth a permission request yet

---

## ▶ START HERE — Phase 7, one target adopted and three still open

**Akash's direction: Tise predicts all four.** D94 fixed every definition, bar, cluster unit
and adoption rule **before implementation**. **T-A has now been fitted and adopted (D97);
T-B, T-C and T-D remain untouched.**

**Akash authorised both `tabs` and `idle`, with live collection.** Both are optional
permissions, consent-gated exactly as `history` already is.

**`idle` fixes labels, not the model, which is worth more.** It turns "the tab was open" into
"the person was present" — the caveat D93 named as able to account for its whole effect,
since `visit_duration` records a tab left open overnight as deep engagement. It also replaces
the 30-minute session timeout, a *declared guess* since D17 because T1 looked for an
empirical trough in the gap distribution and **found none**. Every session-derived feature in
the project rests on that guess.

**The change that applies to all four:** every interval this project has published was
resampled over **9–12 clusters**, because the subject has always been the category. D93's
Edge run had 2,805 test rows and an interval built from **11 things**. Width scales with
1/√clusters, so nothing here could ever resolve a small effect. D94 declares **session**
clustering, with category reported alongside — and records that it was proposed *after*
seeing D93 fail, which is why it is registered ahead of the run rather than applied to the
old one.

**T-A measured what that was worth, and it was decisive.** The identical point estimate
**includes zero under the old subject unit on both corpora** (n=9, n=11) and **excludes it
under sessions** (n=27, n=155). Without D94's change T-A would have failed. And a cluster
*count* is not cluster quality — Chrome's 27 sessions include one holding **43%** of its
rows, so every clustered report now prints the spread beside the count.

**Stopping rule, fixed in D94:** if none of T-A, T-B or T-C separates from its declared bar,
the finding is that this data does not support a model, Tise ships descriptive, and that is
published as the headline. **T-A separated, so the rule is not triggered** — but it does not
retire either: T-B and T-C still report against their own bars, and a failure there is still
published as a failure.

- [x] **T-0 · Attention collection** · M — **shipped before T-A on purpose** (D96)
  - **Data has lead time; model changes do not.** T-D cannot be measured on any corpus, so
    every day not collecting is data that cannot be recovered. Collection runs now; **no
    target is adopted and the extension still shows nothing**
  - `tabs` + `idle` **optional** permissions, consent-gated as `history` is. Attention spans
    in a new `attention` store at **DB v5**, expiring with raw events (they describe the
    browsing, not what was learned from it)
  - **Three rules, each tested:** never invent a span (unknown tab -> record nothing); a
    zero-length span is the *absence* of a measurement, not a measurement of zero; spans are
    **capped at 30 min** because an unbounded one is a laptop lid, not a person
  - `tabId` used to attribute a span and **never stored** - absent from `EVENT_FIELDS`, so
    the privacy test fails if it ever leaks
  - **The manifest guard failed and was updated deliberately**, then strengthened: `cookies`,
    `webRequest`, `scripting`, `storage` and six others are now asserted absent from both lists
  - **Akash still owes the real-profile check** - reload the build and confirm the `fs_3`
    migration preserves the row count with `skipped` at 0. One reload covers both

- [x] **T-A · `visit_engaged`** · M — **ADOPTED (D97)**. First target in the project to
      clear a bar written down before the measurement
  - Verify: `uv run python analysis/visit_engaged.py` ✓ 697 Python, 356 TypeScript, both
    linters clean, builds → `docs/benchmarks/visit-engaged.md`
  - **Edge** (the adoption corpus, named in D94 before anything was fitted):
    **+0.0112 [+0.0068, +0.0159]**, session-clustered, n=155 — excludes zero.
    **Chrome:** +0.0038 [+0.0006, +0.0101], n=27 — excludes zero
  - **Both halves of D94's change were necessary, and it is measured.** Under the *old*
    subject unit the identical estimate **includes zero on both corpora** (n=9, n=11). With
    the unit held fixed, `as_2` still beats `as_1` by +0.0057 [+0.0024, +0.0094] on Edge.
    D93 had neither and missed by 0.0001
  - **`domain` carries it on first use** — stored since T1, read by zero features until now.
    `domainDwellLevel` is the **second-largest coefficient on both corpora**
  - **The rival, added because the coefficients demand it** (D24): `domain_base_rate`, the
    same construction as `category_base_rate` keyed on the domain. On Edge it nearly matches
    D93's *whole model* (0.2453 vs 0.2446); on Chrome it does nothing (0.2499 vs 0.2500).
    The model beats it on both. **Reported beside the verdict, never inside it**
  - **Chrome is the weaker corpus and the page says so** — one session holds **43%** of its
    2,224 test rows. A cluster count is not cluster quality, and `n=` cannot tell them apart
  - Also settled: `brier_difference_interval(unit=)`; `run_backtest` keeps `pooled_sessions`;
    the target had two names (`attention_dwell` in code, `visit_engaged` in SPEC) and now has
    one; regenerating `attention.md` moved **no figure**, which is how `as_1` is known intact

- [x] **T-G1 · `as_2` in TypeScript, with parity** · L — done. **363 TypeScript / 761
      Python**, both linters clean, builds
  - `extension/src/features/attention.ts` mirrors `attention.py`. **TypeScript reproduced
    Python's oracle on the first run** — 20 dwell-carrying events, 473 fixture insertions
    and **one deletion, which was a comma**: no existing expected value moved
  - **A feature-set registry**, mirroring Python: `featureNames`, `nullableFeatures`,
    `designColumns`. `fs_3` stays the default so no existing caller changed
  - **A parity bug I wrote and caught:** `getHours()`/`getDay()` are *local*; this project is
    UTC on both sides (`context.ts` sets it). It would have shifted every hour feature and
    `isDailyDomain` by the machine's offset and failed nothing but the fixture
  - **A real bug TypeScript found:** `rows.map(rawRow)` passes the array index as the second
    argument — invisible until `rawRow` took one
  - **A guarantee replaced rather than dropped:** widening `values` to string keys lost a
    compile-time check, so `rawRow` now rejects *extra* keys, which the type never checked.
    The preprocessor carries its feature set, because two sets' widths can coincide and a
    length check would not catch an `fs_3` row entering an `as_2` preprocessor
  - The fixture **asserts it reaches its own edges**: both nullable features, both outcomes,
    more than one session, and a dwell landing *exactly* on the threshold that a `>=`
    implementation would pass everything else on

- [ ] **T-G · Ship `visit_engaged` end to end** · L · deps: **T-G1 done**, and collected spans
  - **Next: the span→dwell join** — read the `attention` store, attach `dwellSeconds` to
    events in memory, never to disk. Unblocked, no data needed
  - **Then training and prediction, which are gated.** Akash has not yet reloaded the
    extension, so span collection may not have started counting
  - **Adopted is not shipped, and this is the gap.** `as_2` is the `full` compat class: it
    needs dwell, which only live attention spans can supply. D96 started collecting them
    days ago, there is **no TypeScript twin of `as_2`**, so the parity contract is unmet
  - Work: `as_2` in `extension/src/features/vector.ts` + `prep.ts`, extend the parity oracle,
    attention-derived labels in the extension, then training and prediction
  - **Gate: enough live spans to train on.** Not a date — a count, measured from the store.
    Until then the extension keeps training `return_24h` and keeps showing nothing
  - The import-vs-live offset check below becomes due in the same window

- [x] **T-H · Does `visit_engaged` replicate on other people?** · L — **YES (D100).**
      **+0.0091 [+0.0086, +0.0097]** over **1,326 panelists**; the model beats a constant for
      **88.6%** of them individually
  - Verify: `uv run python analysis/replication.py` ✓ 1,326 analysed, 822 excluded, **0
    errors, 0 rows dropped**, ~70 min. Report at `data/replication.md` (gitignored)
  - **6 of D99's 7 predictions held. The one that failed, failed upward:** it predicted
    55–80% of people positive and the answer was **88.6%** — the number D99 named as the one
    that actually answers the question, and the estimate was wrong in the flattering
    direction. Recorded rather than filed under "6 of 7"
  - **ρ = +0.348** between visit count and effect size, so Akash's heavy-vs-median question is
    answered as a **slope across 1,326 people** rather than two underpowered batches
  - **Gender: 0.0002 difference**, a null *predicted in advance*. **Age is a monotone gradient**
    (75.8% at 18–24 to 95.4% at 64–80) that **nobody pre-registered**, so it is a hypothesis
    for a future test and must not be reported as a finding
  - The corpus records **idle-excluded** dwell, so D93's standing caveat — that tab-open time
    could account for the whole effect — is answered rather than outstanding
  - Superseded run notes: `uv run python analysis/replication.py` — approximately **75
    minutes**. Writes `data/replication.md`, gitignored, **not** `docs/benchmarks/`
  - **This can retire T-A.** D97 adopted `visit_engaged` on one person. If the population
    interval includes zero, the adoption is withdrawn to *single-person result*, `SPEC.md`
    and `README.md` are corrected, and the failure is published as loudly as the adoption
  - **Corpus:** GESIS/Respondi, Zenodo 4757574 — 2,148 consenting German panelists, October
    2018, 9.15M visits, CC BY-NC. **Akash reports permission granted**; the reply itself
    still needs pasting into `docs/gesis-permission-request.md` so the record names a person
    and a date
  - **It records `active_seconds`** — idle-excluded attention, *better* than the
    `visit_duration` D97 used, so D93's standing caveat becomes a measurement
  - **1,326 of 2,148 are eligible** (753 fail the 1,000-visit floor, 69 the 20-session
    floor, **0 the 200-label floor** — that gate never bound, and the report must say so).
    **8,586,879 labels.** Median 4,204 per person; **523 people match or exceed Akash's
    Edge corpus**, so he is a heavier browser than most of this panel
  - **The cluster is the person**, so the interval is built from ~1,326 clusters against
    D93's 11 and T-A's 27/155. For the first time the interval is not the binding constraint
  - Everything else — eligibility, feature sets, bar, statistic, verdict rule and **seven
    predictions** — is fixed in D99 and scored automatically by the report

- [x] **T-H0 · The machinery T-H needs** · L — built, tested, not run (D99)
  - `research/tise_research/data/web_tracking.py` — reader and sharder. The 680MB file is
    **not** grouped by person, so it is sharded on a *stable* id hash: Python's `hash()` is
    salted per process and would make the corpus non-reproducible. 27 tests
  - `as_1n` / `as_2n` — the corpus has **no transition column**, so the three arrival flags
    are **dropped, not zero-filled** (D51). This is a different model from D97's and every
    report must say so
  - **`Label.label_id`** — analyses keyed rows on `(subject, window_end)`, which is unique
    on Akash's browsing and not in general. 0.02% of GESIS rows are a second visit by one
    person in one second. The guard added in D97 found nothing here and **fired on the first
    external corpus**; the indexing changed rather than discarding real visits
  - **`fast_logreg.py` — a numpy trainer, proven equal to the shipped one.** Agreement on
    real rows is **4.4e-16** on weights and **3.3e-16** on probabilities, seven orders inside
    the 1e-9 parity tolerance, at **52x** the speed. Without it this run is hundreds of
    hours. **The extension is untouched** — it ships no Python and no numpy, and `logreg.py`
    stays the definition. One test deletes the module if it stops being faster
  - Verify: `uv run pytest` ✓ **761 Python**, 356 TypeScript, both linters clean, builds

- [ ] **T-B · `browsing_next_hour`** — "will you be here?"
  - **Subject is the hour-of-day bucket**, so `category_base_rate` becomes the per-hour rate
    automatically and needs no new baseline code
  - **Bar is the rhythm, not a flat rate** — beating a flat rate would be trivial
  - Cluster unit: calendar day. D94 predicts this one **fails** its bar

- [ ] **T-C · `next_category`** — "what comes next?"
  - Multiclass, **top-1 accuracy** against T19's **33.2% always-the-mode floor** — explicitly
    *not* the 44.5% per-category mode, which is in-sample
  - **Within-session** transitions as well as between; D94 predicts >1,500 labels per corpus
  - Needs new plumbing: `run_backtest` is binary, so accuracy folds + a bootstrap on the
    accuracy difference

- [ ] **T-D · `tab_return`** — "will you come back to this tab?"
  - **`tabs` permission authorised.** Not measurable on any corpus — the history database
    records visits, not tabs — so this needs live collection and starts accumulating from
    the day it ships
  - Work: optional `tabs` permission in the manifest, consent-gated exactly as `history` is;
    tab activation/deactivation collection; then wait for data

- [ ] **T-E · Session intent clustering** · M — **from D95, descriptive**
  - Unsupervised clustering of *sessions* into recurring types (research, routine checking,
    entertainment, exploration) from session-level features: domain count, duration,
    transition distribution, navigation entropy, idle periods
  - **A different shape from everything tried** — it describes a session rather than
    predicting a topic, and needs no labels. Same machinery as T10b's domain clustering
  - **Descriptive, so it ships without clearing a prediction bar.** That matters given D92:
    the base-rate table is hard to beat, and this does not have to beat it

- [ ] **T-F · Domain association rules** · S — **from D95, descriptive**
  - Which domains co-occur within a session. Association rules / FP-Growth
  - Uses `domain`, stored since T1 and read by **zero** features. Needs no model

---

- [ ] **T22 · Measure `next_session_category`** · M · deps: T21 — **superseded by T-C**,
      which subsumes it and adds within-session transitions
  - The remaining candidate. 238 labels, **never fitted at all**, code in both languages
    since T10. Bar fixed in D91: beat the **33.2% always-the-mode floor** by a
    subject-clustered interval excluding zero — *not* the 44.5% per-category mode, which is
    in-sample and would score a model against its own fit
  - D91 also fixed the only circumstance in which it can become primary, so a good score
    cannot become a route to shipping it

- [ ] **T23 · Ship the base-rate card** · M · deps: T21
  - D92: the card works without a model. Per-topic rate, denominator shown, computed
    on-device. This is shippable now and does not wait on T22
  - D81's discipline. Argument, exact definition, predictions and adoption rule committed
    **before** any model is fitted — git holds the order
  - Sets the **performance** bar. The **data-sufficiency** gate is set from T19 (D88 splits
    these deliberately: one has no score available to bias it, the other does)
  - Must state plainly that T19 may kill `block_volume` and promote another candidate

- [ ] **T21 · Build the new target end to end** · L · deps: T20
  - Labels, features, blocks, the two weekly cards, learned clusters
  - **Import may set the yardstick; only live collection may score** (D88). An imported
    block may contribute to a median; a prediction may never be resolved against one —
    D72's rule in a new place, and it keeps the scorecard clean during bootstrap
  - Trailing window ~10 blocks, so the import ages itself out in ~5 weeks and no offset
    correction is needed
  - Cold start: bootstrap from import; describe-don't-predict as the fallback for a thin
    import (57 days on this profile; someone else's may return ten)

- [ ] **Owed check — the import-vs-live offset** · S · deps: T21
  - **Never measured.** D65's 7.7% was research-view vs extension-view, a research bug
    D78/D79 fixed. Live uses `webNavigation` and drops redirect hops natively; import reads
    the history DB, cannot, and approximates with `isLikelyRedirect` — which fires on 0.95%
    of visits, its firing rate and not its error rate
  - After ~14 days of live collection, re-import that same window and compare block counts
    against what was collected live. No new permission

---

## Phase 0 — Does the signal exist? (Python only, no extension)

- [x] **T1 · Measure the shape of real browsing history** · M · deps: none
  - Copy Chrome's `History` db, parse it, measure visits/day, gap distribution, top domains
  - Find the session boundary empirically; estimate `return_24h` labels/week at 8 / 15 / 25 categories
  - Report `full` and `history` variants separately — the API has no visit duration
  - Verify: `uv run python analysis/history_shape.py --out docs/benchmarks/ --browser Chrome` ✓ (78 tests, lint clean)
  - Run per browser, one at a time, never merged (D18) and never automatically (D21).
    Firefox needs `--engine firefox`; Chrome and Edge share the Chromium schema.
  - **Edge is the primary research corpus** (D20) — 5,706 visits, 90-day span
  - **GATE: PASSED** — 348 labels in 8 weeks (Chrome), 398 (Edge), after fixing the
    label definition. Adopted: per (category, session) @ 30m (D16, D17).
  - Session boundary **not found empirically**; it is a declared hyperparameter instead
  - Fixed inside this task: redirect hops counted as navigations; gap-valley left-edge
    bug; `.gitignore` `data/` swallowing `research/tise_research/data/`

- [x] **T2 · Define the category set, seed the domain map** · S · deps: T1
  - 15 categories + `unknown`; **generic map, not the author's domain list** (D22)
  - Coverage: Edge 86.8% (primary, needs 80%) · Firefox 87.8% · Chrome 78.1% (D23)
  - Chrome's ceiling is structural — one self-owned domain is 14.5% of it
  - Verify: `uv run pytest research/tests/test_categories.py` ✓ (138 tests, lint clean)
  - **Carry into T4: `youtube.com` is 49.6% of the primary corpus.** Baselines must be
    reported per category, and majority-class is mandatory (D24).

- [x] **T3 · Resolver, sessioniser, label generator, parity fixture** · M · deps: T2
  - Resolver: override → map → keyword rules → `unknown`; rules live in `domains.json`
    so TypeScript reads them rather than reimplementing them
  - `sessionise` moved to `features/` (parity-critical); verified behaviourally neutral
  - Labels: one per (category, session); leakage test appends future events and asserts
    no earlier label moves
  - Fixture frozen, and **the freeze was tested by breaking it** — flipping `>` to `>=`
    failed three tests
  - Verify: `uv run pytest research/tests/test_sessions.py research/tests/test_labels.py` ✓
    (211 tests, lint clean)
  - Labels vs T1 estimate: Chrome +5.4%, Edge −7.2%, Firefox −15.2% — all inside ±20%
  - **Carry into T4:** nine of fifteen categories have <10 labels (D26); `unknown` is the
    2nd largest category at 84% positive and must be reported separately (D27)

- [x] **T4 · Baselines and the first honest backtest** · M · deps: T3
  - 5 baselines (majority-class mandatory, D24), rolling-origin expanding folds
  - Brier + log loss + skill + base rate, per fold and per category
  - Verify: `uv run python -m tise_research.eval.backtest --target return_24h` ✓
    (283 tests, lint clean, byte-identical across runs)
  - **The bar for T11 is Brier 0.1254 on Edge** (`category_base_rate`, skill +0.328) — D28
  - `majority_class` is best on `video`/`search`/`news`; "always yes" is what to beat (D29)
  - `same_as_last` is the first documented failure case — kept, not fixed (D30)
  - `full` vs `history` identical here by construction; becomes live at T10

- [x] **CHECKPOINT A** — real numbers from real browsing; gate passed; fixture frozen
  - **Last cheap exit. Everything after this is product engineering.**
  - [x] Owed before any number reaches the README: confidence intervals — **done**
    (D80). The README still carries no numbers, so the promise was never broken

---

## Phase 1 — Collect

- [x] **T5 · Permission spike** · S · deps: none — **run 2026-08-26, 5 variants**
  - **Manifest decided (D31):** `webNavigation`, `alarms`, `offscreen` required;
    `history` optional; **no host permissions**
  - **I was wrong (D32):** `webNavigation` needs no host permissions. B and C returned
    identical results, so `<all_urls>` buys nothing
  - **Consent flow proven (D33):** installs with zero capability, grant at runtime,
    listeners re-attach without reload. Chrome focuses **Deny** — T15 must persuade first
  - Duration trap **observed**, not just documented: `VisitItem` has no duration field
  - Backfill fan-out 0.7 ms/page → ~3.5 s for 5,000 pages. T7 imports in one pass
  - **Unresolved, recorded honestly:** default 24h/100-row truncation could not be
    measured on a 20-page profile. Mitigation is unconditional — always pass explicit
    `startTime` and `maxResults`
  - Verify: A saw 0 nav events, B saw 0 history events ✓

- [x] **T6 · Extension scaffold and live collector** · M · deps: T5, T2
  - Vite + TS + MV3, IndexedDB, normaliser; URL reduced to domain before the event exists
  - Verify: `npm run build && npm test` ✓ (90 TS tests, ESLint clean, `dist/` loads)
  - **Domain reduction is already cross-language tested** (D34) — `research/fixtures/`
    `domain_cases.json`, 30 URLs, asserted by both languages. Broken once on purpose;
    both suites failed the same row
  - **Dwell is never measured, live or imported** (D35) — uniform absence beats a
    distribution shift between import and live. `full` is research-only, permanently
  - **Install collects nothing** (D37) — consent and pause are separate states, the gate
    runs before the URL is parsed, and settings live in IndexedDB so no `storage`
    permission is needed
  - Runtime dependencies: **one** (`idb`). `fake-indexeddb` is test-only (D38)
  - **Verified in Chrome 2026-08-26.** Installed inert (0 events before consent), then
    26 events from ~10 sites. Every stored domain bare — `dominos.co.in` reduced under
    the multi-part suffix correctly. Pause held at 26
  - **Observed, and deliberately not acted on:** `unknown` was 12/26 (46%) on that
    sample, against 13.2% on the Edge corpus. Ten hand-picked varied sites are not a
    coverage measurement — fixing the map against them would be tuning on the test.
    Carried to T10 (D39)

- [x] **T7 · First-run history import** · M · deps: T6
  - Explicit consent, idempotent, `dwellSeconds: null`, non-blocking
  - Verify: `npm test -- import` ✓ (111 TS tests, ESLint clean). Idempotency broken
    deliberately once — both duplicate tests failed, then reverted
  - **Redirects: the API hides the qualifiers, so they are inferred** from a 50 ms
    referrer gap — below human reaction time, argued before it was measured. Scored
    against the history file's real transition bits: precision 0.947 Edge / 0.931 Chrome
    (D40, `analysis/redirect_heuristic.py`)
  - Runs in the service worker, so closing the popup does not cancel it. Two consents,
    not merged: app-level first, Chrome's dialog second (D41)
  - Every `search` bound explicit, so T5's unmeasured 24h/100-row default never applies
  - **Verified in Chrome 2026-08-26**, in a fresh profile: permission dialog focuses
    Deny (D33 again), import ran, 66 events from a near-empty profile, categories
    resolving. The ~5,000-event check is still owed on a profile with real history
  - **Defect found by looking at the running extension** (D43): a visit seen by both live
    collection and a later import was stored twice. Import now stops at the earliest live
    event. Broken deliberately, two tests failed, reverted

- [ ] **T10b · Discovered categories** · M · deps: T10 — **new, from D42**
  - Cluster domains by session co-occurrence and time-of-day. No text, no titles, no
    server, no model API. Clusters named by their most frequent member
  - **Must be versioned as its own taxonomy and benchmarked separately.** Categories are
    the prediction's subject; swapping them silently makes D28's Brier 0.1254 describe a
    different target
  - Cheaper wins first: surface the user override in T14; spike titles → keyword rules
  - Verify: `uv run pytest -m parity`; tournament reports both taxonomies side by side

- [x] **T8 · Retention, deletion, export** · M · deps: T6
  - `raw_retention_days` default 30, `0` = forever; delete-all leaves zero rows
  - Verify: `npm test` ✓ (135 TS tests) and
    `uv run python -m tise_research.data.load --export research/fixtures/export_v1.json` ✓
  - **Delete-all takes consent and the `history` permission with it** (D44) — after it
    runs, Tise is in the state it installs in and cannot store anything
  - **The export carries everything, including the user's overrides** (D45), and the map
    and suffix versions, without which a benchmark is unrepeatable
  - **The alarm is created on install/startup, never at module scope** (D46) —
    re-creating an alarm resets its schedule, so a worker that wakes per navigation would
    push retention forward forever and silently never expire anything

- [x] **CHECKPOINT B** — loop closed: browser → export → Python → labels
  - `research/fixtures/export_v1.json` is the third shared-data contract. The extension
    asserts its exporter reproduces it; Python asserts its loader reads it and that
    `sessionise` and `return_24h_labels` run on the result unaided
  - Broken deliberately: dropping `suffixListVersion` from the exporter failed three
    TypeScript tests, then reverted
  - **Still owed — your hands:** export from the browser, then run the loader on the real
    file rather than the fixture

---

## Phase 2 — Features, twice

- [x] **T9 · Port sessioniser + one feature to TS; stand up the parity suite** · M · deps: T3, T6
  - Compare both implementations on the fixture within 1e-9
  - Verify: `uv run pytest -m parity` ✓ (6 parity tests, 339 total) `&& npm test` ✓ (150)
  - **Broken deliberately twice**: `>` → `>=` on the session boundary failed 6 tests;
    weakening the leakage guard `>=` → `>` failed 2. Both reverted
  - **The oracle is a committed file, not a cross-language process call** (D48). Neither
    suite shells out to the other; either can run alone
  - **Not compared, deliberately:** session id *strings* (D36 — instants compared as
    epoch ms instead). **`labels` is not yet checked by TS** — T10. The TS suite asserts
    the exact top-level key set of the oracle, so a new section fails the build rather
    than looking verified
  - **Three implementations of the session rule are now under test in two languages**
    (D49): Python batch, TS batch, TS incremental. A test replays the fixture through the
    incremental one and asserts it matches the batch grouping
  - `featureSet: "fs_1"`. The fixture gained two sections and **nothing frozen changed** —
    66 insertions, no deletions (D50)

- [x] **T10 · Port the remaining features** · M · deps: T9
  - 14 features, `featureSet: "fs_2"`, **all compat class `history`** — D35 left the
    `full` class empty, and the mechanism stays anyway (D51)
  - Verify: `uv run pytest -m parity` ✓ (10 parity tests, 361 total) `&& npm test` ✓ (159)
  - **`priorReturnRate` excludes sessions whose horizon has not elapsed** (D52). Counting
    them as misses is the tempting shortcut, and it is a leak
  - **Feature rows now live in their own store at DB v2** (D53). A row 400 days old
    survives a 30-day retention pass; delete-all still takes it
  - Fixture extended **append-only** for prior-rate variety — no deletions in any frozen
    field
  - Broken deliberately three times, two tests each: the weekday convention, the
    prior-rate guard, the half-open window
  - **Found a flaw in my own tests:** two assertions read values out of the fixture
    instead of computing them, so they could never fail from a TypeScript bug. Both fixed

- [x] **CHECKPOINT C** — parity green; leakage test passes on both sides
  - CI-blocking is T17's job. The suite exists and bites now.

---

## Phase 3 — Predict

- [x] **T11 · In-browser training** · M · deps: T10
  - Transition table + logreg, chunked, resumable, alarm-driven. **No offscreen document**
    — chunking removed the premise (D59), and Akash removed the permission (D63). The
    manifest is now `webNavigation` + `alarms`, `history` optional, no hosts
  - Verify: `uv run pytest -q` ✓ (422) `&& npm test` ✓ (227), both linters clean, builds
  - **The bar is cleared, and the result is weaker than that number** (D60). Edge Brier
    **0.1119** vs the 0.1254 bar, skill +0.400 — while winning only **2 of 5 folds**.
    Chrome **loses outright** (0.2195 vs 0.1868). Firefox clears it, 4 of 5. 8 of 15 folds
    across everything. `docs/benchmarks/model.md`, generated not typed
  - **The model wins early folds and loses late ones, everywhere.** Measured lead, not a
    conclusion: 77.5% of Edge test rows have `hoursSinceFirstSeen` outside the range it
    was fitted on. Cumulative counters act as a calendar index. Fixing it is T16, and the
    fix must be chosen without looking at these numbers
  - **The optimiser is hand-written in both languages** (D54) — LBFGS is not reproducible
    in a browser. Parity holds to **2.2e-16** after 4,000 steps, seven orders below
    tolerance
  - **The step size is derived from the matrix, not declared** (D55). A hand-picked rate
    passed every test and would have diverged on someone else's browsing
  - Labels now persist in their own store at DB v3 (D58) — provisional until the horizon
    elapses, so they cannot live inside an immutable feature row
  - **Found by breaking it: the fixture never touched the horizon boundary** (D61). `<=`
    to `<` failed 0 of 227 tests. Two events appended, purely additive, verified against
    `git show HEAD`; the same break now fails 3
  - **Verified in Chrome 2026-08-27 (D64).** 5,105 events imported, **334 labels, 72%
    positive**, final gradient **4.2e-6**, under a minute. Label yield and base rate match
    the research corpora; D62's budget holds on a real profile
  - **The 90-day import returned 57 days and that is correct** — the history file holds
    zero visits before 2026-07-01. The T5 truncation question is closed, measured
  - The Python loader read the real export unchanged. **Both owed verifications done**
  - **New finding (D65): the redirect heuristic fires on 0.95%, not the 12.2% D40
    scored.** The research view keeps `google.com/url` and drops the landing page; the
    extension keeps the landing page. Totals agree to 63 events, composition differs by
    **7.7%**. The extension is arguably the more correct view. Nothing changed on it —
    it is a T16 problem because it invalidates corpus-level comparability, not code parity

- [x] **T12 · Calibration and abstention** · M · deps: T11
  - Platt (`cal_1`), not isotonic — two parameters is what a few hundred labels support
    (D66). It reuses the model's own optimiser, so there is still **one** to keep in parity
  - Verify: `uv run python -m tise_research.eval.calibrate --model logreg` ✓
    `&& npm test -- calibration` ✓ — 474 Python, 273 TypeScript, both linters clean
  - **Calibration works:** ECE Edge 0.1664 → **0.0541**, Chrome 0.1845 → 0.1113,
    Firefox 0.2439 → 0.1254
  - **And MCE got worse on Edge, 0.5120 → 0.9991** (D68). The average improved while one
    narrow range became catastrophic. Reported next to ECE, which is why MCE exists
  - **Tise abstains from everything on this data** (D70), and that is the machinery
    working. No threshold certified the declared 90% target on any fold. Pooled, 0.85
    answers 59% at 90.0% — but certifying a margin that thin needs **>12,800** answered
    rows and the calibration slices hold 61–133. The shortfall is the margin, not the model
  - **The first threshold rule was broken and the data said so** (D69): it qualified on
    4 of 5 folds and kept its promise on 1. Now selected on a **Wilson lower bound**;
    `z=0` recovers the old rule and both are reported side by side. A skill-free model
    passed the old rule 3% of the time and the new one 0 times in 200
  - The three-way split is chronological: 70% fit / 30% calibrate / test untouched (D67).
    The extension makes the same trade, so the benchmarks describe what ships
  - **Two more fixture gaps, found by breaking things** (D71): a real decile-binning bug
    (`int(0.3/0.1) == 2`), and a logit clamp no parity test touched. Both closed

- [x] **T13 · Prediction registry and automatic outcome resolution** · M · deps: T12
  - `hit` / `miss` / `expired` resolved with no user confirmation anywhere (D6)
  - Verify: `npm test -- registry` ✓ — 491 Python, 318 TypeScript, both linters clean
  - **`expired` is not a miss** (D72). A window Tise did not watch produces no measurement
    and is scored by nobody — D52's rule in a new place. Needed a coverage log of when
    collection was off, hooked into `saveSettings` so every route in is caught
  - **Resolution is a pure function**, so idempotence and restart-safety are structural
    rather than arranged (D73). `resolveAll` returns only what changed, so "a second pass
    does nothing" is directly assertable
  - **Abstained predictions are stored**, and on this data that is all of them (D74). The
    only way to learn whether abstaining was right is to write down what would have been
    said. T16 needs exactly these rows
  - Export is now **v2**; the loader reads v1 too and `export_v1.json` stays frozen, so
    backward compatibility is tested rather than asserted (D76)
  - **Third hole in my own tests** (D77): one of eight breaks failed *nothing* — the
    registry pass could rewrite resolved predictions back to `pending` and no test noticed,
    because every test stopped at an early return. Fixed with an end-to-end group
  - Owed: the two manual checks — satisfy a prediction by browsing, and let one expire

- [ ] **Owed verification — the `fs_3` migration on a real profile** · S · deps: T16
  - **Highest-value check outstanding.** The Chrome profile from D64 holds ~5,105 events,
    `fs_2` feature rows and a trained model. Loading the new build runs `migrateFeatureRows`
    for real, against rows this project has never seen it applied to
  - Every claim about it so far is from synthetic corpora. T5, T7 and T11 each had a
    documented-looking claim fail on contact with a browser
  - What to look for: the popup's model panel after one alarm — row count should be roughly
    what it was before, **not** reset to the last 30 days. `skipped` must be 0
  - An export afterwards also re-checks D76's loader against a profile that has migrated

- [ ] **CHECKPOINT D** — the extension scores itself; reliability curve exists

---

## Phase 4 — Show it

- [ ] **T14 · Dashboard** · M · deps: T13
  - Probability, window, evidence, scorecard; abstained predictions hidden, not greyed
  - Purchase intent labelled "not evaluated"
  - Verify: `npm test && npm run build`

- [ ] **T15 · Onboarding and privacy settings** · M · deps: T14
  - No source listed that V1 does not implement; nothing collected before consent
  - Verify: fresh profile install; confirm zero writes pre-consent

---

## Phase 5 — Publish

- [x] **T16 · Model tournament and benchmark report** · M · deps: T13
  - Identical folds for every model; report the XGBoost-vs-shipped gap; one documented failure
  - Verify: `uv run python -m tise_research.eval.tournament` ✓ — 606 Python, 333 TypeScript,
    both linters clean. Report at `docs/benchmarks/tournament.md`
  - [x] **The tournament — every pre-registered prediction held** (D84 pre-registration,
    D85 result). `xgb_default` loses on all three corpora and on Chrome loses to a
    *constant*; `xgb_small` wins on Edge alone (0.1084 vs 0.1129) and loses on the other
    two. **The adoption rule fires nowhere** — all twelve intervals include zero — so
    `logreg_fs3` remains what ships, as D84 fixed in advance
  - **The pre-registered trap here was the mirror of D81's.** Not which fix to choose after
    seeing scores, but **how strong to make the opponent**: tuned, a challenger reports a
    maximum over draws that is mostly noise at 271 rows; at library defaults on a few
    hundred rows it overfits and loses to an opponent quietly weakened. Both produce a
    table that looks honest. Two declared configurations, **no search anywhere in T16**
  - **What it licenses:** not "as good as XGBoost" — "271 test rows cannot tell them
    apart". D80's finding one level up. The in-browser constraint has **not been shown to
    cost anything measurable on this data**
  - **The width ladder is the finding I did not predict.** D82 *argued* interval width is a
    property of the comparison; three comparisons over the **same 271 Edge rows** now
    measure it — `logreg_fs2` 0.0060, `xgb_small` 0.0273, `category_base_rate` 0.0404.
    **Monotone in shared structure, 6.7x end to end, sample held exactly fixed**
  - **The documented failure is not dull.** Edge `video`, Saturday 2026-08-08: 373 events
    in 7 days, seen all 7, 51.5% of 30-day activity, 89.3% prior return rate, last seen
    **4 minutes** earlier. Tise said **99.1%**; the person did not return. Squared error
    0.9831 of 1.0. **A mis-encoded feature, not a calibration failure**, and Platt cannot
    reach it
  - **D85 explained that row as a weekend effect and the explanation was wrong** (D86).
    Measured: Edge Saturday returns at **74.6% against 71.6% overall** — an *above*-average
    day. A causal claim with no number behind it is invariant 3's failure wearing prose,
    and prose fails no test. The conclusion survived; the argument for it did not
  - **The replacement is measured and stronger.** Day-of-week is **non-monotone on all
    three corpora** — Chrome 29.2-point spread, Edge 21.1, Firefox 18.5, peaks disagreeing
    — and one linear coefficient on an integer 0–6 cannot represent that in either
    direction. `docs/benchmarks/day-of-week.md`. **Nothing was changed and no feature was
    added**; a `sin`/`cos` pair would be a losslessly migratable `fs_4`, needing D81-style
    pre-registration first
  - **The width ladder was not pre-registered** (D86) — built after the intervals were
    seen, so it lacks the standing of the three predictions. It does replicate: monotone
    on all three corpora, which it was not constructed on
  - `xgboost` 3.4.1 + `scikit-learn` 1.9.0, **dev group only**, research tier, no TS twin,
    not in the parity contract. Both authorised
  - **Two latent bugs found on the way**, neither affecting a published number: `model.md`
    named `fs_2` after D83 shipped `fs_3` (literals beside dynamic figures) and
    `model_report.py` had **no test file at all** — D78's `corpus.py` hole, in the file
    every model claim passes through; and `backtest.py --with-model` gave `--view` to
    `load_labels` but not `load_events`
  - [x] **`fs_3` ships** (D83, Akash authorised). Both languages, oracle regenerated, and
    the parity suite bit on the way — 15 failures against an `fs_2` oracle, then exactly
    the four expected sections moved and `labels`/`sessions`/`resolutions` stayed
    byte-identical. Fold wins 8 → **10 of 15**; every interval vs the bar still includes
    zero, so the headline is unchanged
  - **A feature-set change would have silently reset the model** — training filters to the
    current set and `refreshDataset` can only recompute rows whose events survive. A
    lossless migration was possible only because `fs_3`'s features are arithmetic on
    stored `fs_2` values. **Freeze the feature set before the Web Store listing**: the next
    change may not be migratable, and post-launch it resets every user's history
  - [x] **Cumulative features — transformed, and it worked** (D81 pre-registration, D82
    result). `hoursSinceFirstSeen` → `firstSeenSaturation` = `h/(h+168)`;
    `priorSessionCount` → `priorSessionRate` = sessions/day, `r/(r+1)`. Both scales
    declared from existing windows, not fitted. **Pre-registered before implementation**,
    so "chosen without looking at the numbers" is provable from git rather than asserted
  - **Worst excursion beyond the fitted range collapses** on every corpus: Chrome
    0.25→0.03 and 0.33→0.04, Edge 0.12→0.01 and 0.42→0.10, Firefox 0.55→0.11 and 0.36→0.02
  - **`fs_3` is the project's first established result** — Chrome +0.0072 [+0.0032,
    +0.0179] and Firefox +0.0088 [+0.0028, +0.0232] both exclude zero. **Against my own
    pre-registered prediction that it would not.** Not established on Edge, the primary
    corpus, where the point estimate marginally favours `fs_2`
  - **An interval's width is a property of the comparison, not the sample.** The same 141
    Chrome rows that cannot separate the model from the baseline separate `fs_2` from
    `fs_3` easily, because the two share 12 of 14 features and their paired differences
    are tiny. Corrects a natural misreading of D80
  - Verify: `uv run pytest research/tests/test_baseline_gate.py`
  - [x] **Confidence intervals — done, and the headline did not survive them** (D80).
    Every 95% interval on the paired Brier difference **includes zero, on every corpus,
    under both resampling units**. D28's bar is not shown to be cleared on Edge, and the
    model is not shown to lose on Chrome either. `model.md` leads with that, computed
    from the intervals rather than written down
  - **The fold counts were never evidence.** A no-skill model wins 2 of 5 or more with
    probability **0.81**; even 5 of 5 is 0.031. D60's most-quoted caveat was as unfounded
    as the score it cautioned against
  - **Reachable, unlike D70's abstention gap:** separating Edge's +0.0130 from zero needs
    roughly **1,151 test rows against 271** — about 4x the data, versus the >12,800
    answered rows T12 needed. Neither is a promise; both size the distance to decisive
  - **Cumulative features extrapolate** — 77.5% of Edge test rows sit outside the fitted
    range of `hoursSinceFirstSeen`. Any transform must be chosen without looking at the
    current scores, or it is fitted to the test set (D60)
  - [x] **Corpus comparability — settled and re-run** (D78, mechanism corrected by D79).
    Not a choice between three fixes: the premise was wrong. Chromium offers a **page**
    only when one of its visits passes `TransitionIsVisible` — chain end, main frame, not
    keyword-generated — and then hands over all of that page's visits. So the research
    tier's `REDIRECT_MASK` filter kept chain *starts* (`google.com/url`, no redirect bit)
    and threw away landing pages. Three named views now, default `shipped`; Firefox
    reconstructs the same definition from `from_visit`
  - **D78 inferred the rule; D79 read it from Chromium's source and it was wrong twice** —
    two of three terms omitted, and per-visit where it is per-page. The corrected
    simulation reproduces the real import's `redirect` skip count **exactly (49)** and its
    composition to **0.6%**, against 1.5% and then 7.7%. Akash's call to check the docs
  - **The corpus fix did not rescue the model, and that is the result.** Chrome
    0.2195 → **0.2096** (2→3 folds), Edge 0.1119 → **0.1124**, Firefox 0.2263 → **0.2219**
    (4→3 folds), fold total unchanged at 8 of 15, D28's Edge bar identical to 4dp.
    D60 has now survived two separate corrections to the corpus underneath it
  - **Two breaks that failed nothing** (D78, D79): `load_events` could drop the `view` it
    was handed and no test noticed — `corpus.py` had no test file at all, and it is the
    one door every published number comes through. Then the fixture written *for* the D79
    bug still could not fail, because its extra hop was itself visible. Both closed;
    counting break failures caught both

- [ ] **T17 · CI** · S · deps: T10
  - Both suites on push/PR; parity failure blocks; secret scanning + dependency audit
  - Verify: a PR with a deliberate parity break is blocked

- [ ] **T18 · Web Store preparation** · M · deps: T15, T16, T17
  - Privacy policy URL, permission justifications, disclosures, company developer account
  - Blocked on open questions 4 and 5 (licence holder, policy hosting)
  - Verify: `npm run package`; fresh-profile install of the packaged build

- [ ] **CHECKPOINT E** — all 12 spec success criteria met; every number traceable

---

## Blocked on you, not on code

- [x] **Copyright holder** — Akash Navet and Holy Cow Studios Private Limited (D47)
- [x] **Privacy policy hosting** — a Tise section on the Holy Cow Studios privacy policy
      page (D47). Text drafted at `docs/privacy-policy.md`, ready to paste
- [ ] **Publish that section and give me the exact URL** — the Web Store needs it before
      submission, and it goes in the listing
- [ ] **Confirm `privacy@holycowstudios.in` exists**, or name a different address. It is a
      suggestion in the draft, not a fact
- [ ] Chrome Web Store developer account registered under the company identity (D13) —
      one-time fee, you register and pay it
- [ ] Icons: 16/32/48/128px. HCS artwork, or a plain mark I generate and you replace
