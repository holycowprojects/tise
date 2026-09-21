# Tise — Decision Log

Every non-obvious choice in this project, why it was made, and what was rejected.

This file exists because the reasoning is part of the point. Anyone can publish a model.
Almost nobody publishes the argument that produced it.

Entries are append-only. When a decision is reversed, the old entry stays and a new one
supersedes it, with the reason.

---

## 2026-08-26 — Audit of the original design documents

Tise began as three documents (`tise.md`, `tise_workflow.md`, `user_tise.md`, now in
`docs/design-history/`). They were reviewed before any code was written. What follows is
what held up and what did not.

### What held up

- **The maths produces the number, the language layer only narrates it.** Stated in all
  three documents and never contradicted. This remains the central principle.
- **Leakage-safe chronological evaluation.** Rolling-origin backtests, never a random
  shuffle. Correct, and rare in personal-analytics projects.
- **Calibration as a first-class requirement.** A stated 70% should happen about 70% of
  the time, and that is measured rather than assumed.
- **Knowing when not to predict.** Buried in one section of the original, but it is one
  of the strongest ideas in the project.
- **Minimum data collection.** No passwords, no cookies, no keystrokes, no page content
  by default. The prohibition list was identical across all three documents.

### What did not hold up

**1. Portfolio project and consumer product were being designed simultaneously.**
`tise.md` was written for a job interview; `user_tise.md` was written for customers. The
two demand different scopes, and the documents never chose. This was the root cause of
most other problems.

**2. Retention contradicted the evaluation plan.** The privacy screen specified 30-day
raw retention. The backtest plan showed five-month folds. Both cannot be true.

**3. Ground truth had two incompatible definitions.** One section recorded outcomes
automatically; another forbade collecting the page data that would reveal them; a third
added a manual Yes/No button and then claimed automatic confirmation in the same
sentence.

**4. The example benchmark table could not be produced.** It listed MAE, MASE and Brier
for Seasonal Naive, ETS, XGBoost, Chronos and TimesFM. MAE and MASE score point
forecasts; Brier scores probabilities. Those models emit point forecasts and have no
Brier score to report.

**5. The headline prediction was the hardest possible target.** Purchase intent occurs a
few times a month, giving too few positive examples to train on or calibrate against —
and it cannot be confirmed without reading checkout pages the privacy design forbids.

**6. Time-series foundation models were aimed at the wrong problem shape.** Chronos and
TimesFM forecast numeric series. Next-event, event-within-window and time-to-event are
classification and survival problems. TSFMs apply only to activity-volume forecasting,
the least interesting task in the document, and they need far more history than a new
user has.

**7. The manifest example collected nothing.** It requested `storage` and optional `tabs`.
Observing navigation needs `webNavigation` plus host permissions, and host permissions go
in `optional_host_permissions`, a field never mentioned. No background service worker was
declared.

**8. The privacy screen advertised a data source V1 excludes.** "Application Activity"
appeared as a toggle; application monitoring is an explicit V1 non-goal.

**9. Ten days of plan against roughly ten weeks of scope.** "Day 7 — Dashboard" is a
complete analytics UI. "Day 6 — Calibration" arrives when five days of data exist.

**10. The synthetic-data plan was circular.** Generating sequences with a known pattern
and then demonstrating that a model recovers that pattern proves only that the generator
and the model agree. Useful as a test fixture; worthless as a benchmark.

**11. The two long documents were ~80% duplicated and had already drifted.** The event
schema and several feature names differed between them.

**12. Performance targets were not derived from anything.** "Prediction under 5 seconds"
against an inference that takes about a millisecond.

---

## 2026-08-26 — Founding decisions

Numbered as decided. Reasoning matters more than the choice.

### D1 — Purpose: capability showcase, published open source

Tise exists to demonstrate that Holy Cow Studios builds serious machine learning, not
only chatbots and automations. It is published publicly on GitHub.

*Why open source rather than a private repo:* a client cannot verify a case study, but
they can read source code. Publishing turns the privacy claims from marketing into
something auditable.

*Consequence:* the README, the benchmark numbers and the commit history are all part of
the pitch, and the code quality is on display.

### D2 — Every user's data stays on their own machine

No telemetry, no sync, no aggregate collection. Nothing is ever transmitted.

*Consequence, accepted:* there is no population model and no cross-user comparison. Every
published number comes from a single user's browsing — the author's. This is stated
plainly rather than obscured.

### D3 — Code ships before results

The repository is published with working code and clearly marked placeholder benchmarks.
Real numbers are added as data accumulates.

*Why:* a benchmark table that visibly fills in across commits is more credible than one
that appears complete in the initial commit.

### D4 — No deadline

*Consequence:* the failure mode is abandonment at 70%, not rushing. Every milestone must
be independently committable and leave the repository in a working, publishable state.

### D5 — Three things are being proven at once

Rigorous ML, product polish, and privacy. Sequenced by cost rather than treated as equal
work: privacy decisions come first because they are cheap now and brutal to retrofit;
ML rigour is the substance; polish is capped at a deliberately small number of screens
because it is the only one of the three with no natural ceiling.

### D6 — Purchase prediction is a demo; frequent events are what gets measured

Purchase prediction remains as an illustration and is labelled as unmeasured.

The evaluated predictions are ones that occur many times a day and confirm themselves
from the event stream — no user confirmation button in the loop.

*Why:* frequent, self-confirming events produce hundreds of labelled examples a month
instead of a handful, which is the difference between a real calibration curve and noise.

*Superseded:* the original documents' framing of purchase intent as the headline.

### D7 — Ships to both GitHub and the Chrome Web Store

The Web Store listing is itself part of the argument: a public listing declaring that
the extension transmits nothing, linked to source code anyone can audit.

*Consequences:* a privacy policy at a public URL is required; every permission needs a
written justification; there is a one-time developer registration fee.

### D8 — No LLM in V1

No API calls, no keys, no transmission. Explanations are generated from templates over
the same evidence the model used.

*Rejected — bring-your-own-key:* almost no users complete the setup; storing an API key
contradicts this project's own rule against storing credentials; optional transmission
still requires third-party disclosure on the listing, losing the unqualified claim; and
the support burden is entirely unrelated to the ML work.

*Design requirement:* the explanation layer is an interface with a template
implementation as default, so a local model can be added later without touching anything
else.

### D9 — Prediction happens at event level as well as session level

The author's Chrome use is bursty rather than continuous, producing fewer but denser
sessions. Predicting within sessions yields far more labelled examples from the same
browsing.

*Open:* the 30-minute session timeout inherited from the original document is a guess.
It will be measured against real history before being fixed.

### D10 — First run imports existing Chrome history

Onboarding reads existing browser history through the `history` API, so a new user gets
real predictions immediately instead of waiting weeks.

*Problem it solves:* D2 means no shared model exists, so every user would otherwise start
completely cold.

*Known issue:* imported history has no dwell time — only URL, title, timestamp, visit
count and transition type. A model trained on imported history and served on live events
would see two different feature sets. A history-compatible feature set is required for
the bootstrap model, with the full set used once live data accumulates.

### D11 — Raw events kept 30 days; derived features kept indefinitely

Resolves the retention contradiction. URLs are the sensitive part and are discarded;
aggregated behaviour is what the model needs and is retained.

*Implementation:* a single config value `raw_retention_days`, defaulting to `30`, where
`0` means keep forever. The author's own instance sets `0`. Same code path and same
build, so both settings are exercised and the author still runs exactly what users run.

*Consequence:* features cannot be recomputed once raw data is discarded. A better feature
invented later applies only going forward. Feature design carries more weight than usual
because it is effectively irreversible.

### D12 — Akash writes the code; Claude specs, reviews and advises

*Consequence:* deliverables from Claude are specifications with acceptance criteria,
reviews and design arguments — not a finished codebase.

*Related:* this decision log is part of the deliverable. If the capability being
demonstrated is working effectively with AI on arbitrary problems, the reasoning trail is
the evidence.

### D13 — Company branding deferred; Web Store identity is not

Whether the repository carries Holy Cow Studios branding is undecided and can stay
undecided — GitHub redirects a repository moved to an organisation, so it costs nothing
to defer.

The Chrome Web Store publisher account is different: the listing, extension ID, reviews
and install base attach to whichever account publishes, and transferring is awkward. So
the developer account is registered under the company identity from the start, even
while the listing carries no branding.

### D14 — No time commitment

*Consequence:* milestones must be resumable cold. Anything that requires holding context
across weeks will not survive the gap.

---

## Open questions

Recorded so they are not silently resolved by whoever writes the code first.

- **Q1 — What exactly does V1 predict?** Proposed: next session category, and return to
  a topic within 24 hours. Both frequent, both self-confirming. Not yet decided.
- **Q2 — How is a domain mapped to a category?** The entire feature pipeline depends on
  it and the original documents never specified it. Hand-built map, title classifier, or
  something else. This is the largest undesigned piece of work in the project.
- **Q3 — Does a separate web dashboard survive?** With no LLM and no cloud, a second
  application to install and maintain may buy nothing over rendering the dashboard as an
  extension page. Proposed: drop it, and keep a local Python service purely for training
  and prediction.
- ~~**Q4 — What is the session timeout?**~~ **Resolved by D17:** 30 minutes, declared as a
  hyperparameter rather than discovered as a constant.
- ~~**Q5 — How is a `return_24h` label defined?**~~ **Resolved by D16:** one label per
  (category, session).
- ~~**Q6 — Is Chrome actually the primary surface?**~~ **Resolved by D19/D20:** no. Brave
  is. V1 ships to all Chromium browsers from one codebase.
- **Q7 — Should the browser split be surfaced to the user?** A Tise user running four
  browsers sees predictions from one. Silently partial, or stated in the UI? Blocks T15.

---

## 2026-08-26 — D15 supersedes D12: Claude implements

**Superseded:** D12 ("Akash writes the code; Claude specs, reviews and advises").

Akash invoked `/build` twice against the T1 task after saying "build tise with me".
Repeated instruction to implement is a decision, not an ambiguity. Claude writes the
code; Akash directs, reviews and decides.

*Unchanged:* the "ask first" list in `SPEC.md` still gates permissions, dependencies,
schema changes, network calls and publishing. Implementing does not widen authority.

---

## 2026-08-26 — T1 result: the gate did not pass

Produced by `analysis/history_shape.py`. Full report: `docs/benchmarks/history-shape.md`.

### What was measured

56 days of the author's Chrome history: **5,011 chosen navigations** across **133**
registrable domains on **47 active days**, median 27 visits per active day. The top 10
domains account for 86% of visits, which comfortably clears T2's ≥80% coverage target.

### The gate result

`return_24h`, defined as **one label per (category, day)**, yields **163 labels in eight
weeks** at the best proxy taxonomy (25 categories). The gate required ~300. Positive rate
runs 56–69%, so class balance is not the problem — **label count is.**

The verdict is stable: it was 180 before a measurement fix and 163 after, and the fix
only removed non-events.

### Two defects found and fixed inside T1

1. **Redirect hops were being counted as navigations.** Chrome records each hop of a
   redirect chain as a visit. Excluding them (`CLIENT_REDIRECT | SERVER_REDIRECT`) cut
   distinct domains from 236 to 133 and raised top-10 coverage from 80% to 86% — the
   earlier numbers were substantially tracker and auth-bounce noise.
2. **`find_gap_valley` returned the left edge of a flat trough**, not its middle, placing
   a candidate session boundary at 19s. Fixed to take the midpoint of the tied region.

### An honest negative result

**No empirical session boundary was found.** The gap distribution does not have a clean
two-mode shape at this volume, so `find_gap_valley` returns `None` rather than a number.
This is recorded rather than papered over: the plan explicitly said the session timeout
would be resolved by T1, and it was not. Substituting 30 minutes because it is
conventional is precisely the undefended constant the audit of the original documents
flagged. **Open question Q4.**

### Why the gate failed, precisely

Not browsing volume. The binding constraint is the **label definition**: one example per
category per day caps the dataset at (categories × active days) no matter how much
browsing happens inside a day. At 47 active days in 56, the ceiling was already close.

*Consequence:* the label definition is what should be revisited first, ahead of the
target itself. Decision pending — see Q5.

---

## 2026-08-26 — T1 (second pass): the gate passes. D16, D17, D18.

Supersedes the verdict above. The measurement was not wrong; the label definition was.
Reports: `docs/benchmarks/history-shape-chrome.md`, `history-shape-edge.md`.

### D16 — `return_24h` labels are emitted per (category, session)

**Resolves Q5.** Same events, same target, same horizon — only the bucket size changes.
At 25 proxy categories, projected to eight weeks:

| Definition | Chrome | Edge | Positive rate |
|---|---:|---:|---:|
| per (category, day) | 163 | 184 | 54–56% |
| per (category, session) @ 15m | **348** | **398** | 72% |
| per (category, session) @ 30m | 298 | 339 | 67% |
| per (category, session) @ 60m | 247 | 293 | 61% |
| per (category, 3h window) | 266 | 318 | 66–68% |

The daily definition capped the dataset at (categories × active days) no matter how much
browsing happened inside a day. Per-session roughly doubles it without inventing anything.

*Rejected:* fixed windows. They avoid needing a session timeout, but they cut through the
middle of real sessions and they do not correspond to anything the product claims to
predict. "Will you come back to this" is a question about the next session.

### D17 — The session timeout is 30 minutes, and it is a declared hyperparameter

**Resolves Q4** — not by finding the trough T1 could not find, but by reframing what kind
of quantity this is.

**15 minutes produces the most labels and is rejected anyway.** Choosing it would be
tuning a hyperparameter to clear a threshold, and the threshold (~300) was a judgment
call, not a derived number. A benchmark whose headline depends on a constant picked to
beat its own gate is exactly the failure the audit of the original documents flagged.

30 minutes is chosen because:

- **Class balance.** 67% positive versus 72% at 15m. A majority-class baseline already
  scores 72% at 15m, which makes the reliability curve less informative and the model's
  advantage harder to demonstrate honestly.
- **It is not the value that maximises the metric.** That is the point.
- Chrome reaches 298 against a ~300 target — at the gate, and the gate was never precise
  to ±2. Edge reaches 339.

It is reported in every benchmark and pinned in the parity fixture. It is never assumed.

### D18 — Browsers are measured separately and never merged

Edge history was measured because it exists and is actively used. It is **not** combined
with Chrome, and no model will be trained on the union.

- The extension only ever observes one browser's stream. A model trained on merged data
  describes a person it will never meet — the same error as training on `visit_duration`.
- Both browsers are used concurrently. Interleaving them by timestamp manufactures
  sessions that never happened, corrupting the exact quantity being measured.

*Kept for later:* train on one browser, evaluate on the other. Same person, genuinely
different context — a real generalisation test for the benchmark report, and it only
works while they stay separate.

### The result worth more than the gate

The two browsers are independent datasets — different span (56 vs 90 days), different
volume (27 vs 67 median visits per active day), different domain mix. **The positive
rates match to within 0.3 points at every timeout** (72.0/72.0, 67.3/67.2, 60.7/62.0).

A pattern that reproduces across two independent datasets from the same person is
evidence the structure is real rather than an artifact of one history file. This is the
first genuine finding of the project.

**Narrowed by the next entry** once a third browser was measured — the claim held for two
and does not hold universally.

### Noted, not acted on

Akash browses **more in Edge than in Chrome** (5,706 navigations over 90 days versus
5,012 over 56). D7 still ships to the Chrome Web Store, and the extension runs unchanged
in Edge because it is Chromium. But the assumption that Chrome is the primary surface was
never checked, and it is not obviously right.

---

## 2026-08-26 — Multiple browsers. D19, D20, D21.

Akash uses different browsers for different kinds of work — a deliberate context
separation, not an accident. Each is measured separately; none are merged (D18).

| Browser | Visits | Span | Active days | Median/day | Domains | Labels/8wk @30m | Positive rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| Edge | 5,706 | 89.6 | 67 | 67 | 144 | 339 | 67.2% |
| Chrome | 5,012 | 55.9 | 47 | 27 | 133 | 298 | 67.3% |
| Firefox | 909 | 38.1 | 34 | 16 | 67 | 300 | 55.9% |

### D21 — One installed browser is excluded from research at the author's request

A fourth browser is installed and in daily use. **Its history is not to be read, copied,
measured or referenced**, and any numbers previously derived from it have been deleted.
Nothing derived from it was ever committed.

This is not a technical constraint and needs no justification. It is recorded so that a
future session does not "helpfully" rediscover the database and sweep it in. **Any browser
discovery must be opt-in per browser, never automatic.**

*Consequence:* browser sweeps are always explicit. `analysis/history_shape.py` takes one
database at a time by design, and it stays that way.

### D19 — V1 ships to Chromium browsers from one codebase

Chrome, Edge, Brave, Opera, Vivaldi and Arc share the extension API *and* the history
schema. Nearly all install extensions directly from the Chrome Web Store, so the shipping
surface is **one Chrome Web Store listing**, plus optionally a second Edge Add-ons listing
for discovery. No second codebase.

Note this is a statement about *where the product runs*, which is unrelated to D21 — which
browsers' history is used for research is a separate question with a separate answer.

**Firefox is measured but not shipped to.** It is a genuine port, not a rebuild: separate
store, and no offscreen documents — which T11's chunked in-browser training depends on.
Revisit after V1.

*Consequence for T18:* permission justifications and the privacy policy must cover both
listings. *Consequence for T5:* the permission spike should confirm the set works in Edge
as well as Chrome.

### D20 — Edge is the primary research corpus; Chrome is not

Chrome was the default only because it was the first database found. Edge has more visits
(5,706 vs 5,012), a longer span (90 vs 56 days), more active days (67 vs 47) and more
domains. **T2 builds the category taxonomy from Edge's domain list**, then checks coverage
against Chrome and Firefox.

### The generalisation claim, narrowed

The previous entry said positive rates "match to within 0.3 points at every timeout".
True of Chrome and Edge. **Not true once Firefox is included.** At a 30-minute timeout:

- Chrome 67.3%, Edge 67.2% — two heavily-used contexts, within 0.1 points
- Firefox 55.9% — an 11-point outlier

The defensible claim is narrower: **the pattern is stable across independent,
heavily-used contexts and degrades in a lightly-used one** — which is what anyone would
predict from 909 visits across 38 sporadic days. That is still a real generalisation
result, and it now carries its own documented failure case, which spec criterion 12
requires anyway.

### Firefox has no dwell duration at all

0 of 909 visits carry one — the column does not exist. That makes Firefox the only corpus
here that is `history`-class by construction, with no `full` variant to be tempted by. It
is an honest preview of exactly what the shipped extension sees.

### Excluded deliberately: WebView2 stores

Sixteen Chromium history databases exist on this machine. Twelve belong to **embedded
WebView2 runtimes inside applications** — Outlook, Copilot, GitHub Desktop, the LinkedIn
app, Photos, the Microsoft Store, Ollama. Identical schema, so a naive sweep ingests them
happily. They are app internals, not browsing, and no extension can run in them. Any
future browser discovery must exclude `EBWebView` and `WebView2UserData` paths by name.

---

## 2026-08-26 — T2: the category map. D22, D23, D24.

Map: `extension/src/categories/domains.json` (v1). Tests: `research/tests/test_categories.py`.

### D22 — Fifteen categories, and the map is generic rather than the author's

`video · search · news · social · shopping · ai · dev · learning · work · finance ·
government · property · travel · reference · wellness`, plus `unknown`.

**The shipped map contains only domains a large population uses.** It was seeded from
real browsing but deliberately excludes the author's employer, his child's school,
locality-specific government portals, neighbourhood businesses, his bank and his
insurer. This file is committed and public, and a domain list is a profile: publishing
one would disclose employer, city and family from a file nobody would think to check.

A test enforces it by name, because the failure mode is somebody later adding "just one
more" domain that happens to be their own.

*Consequence:* the map cannot cover personal browsing, by construction. That is what the
user override in the resolver is for — see D23.

### D23 — A generic map has a coverage ceiling, and that is a finding, not a shortfall

| Corpus | Coverage | Threshold |
|---|---:|---:|
| Edge (primary, D20) | **86.8%** | 80% |
| Firefox | 87.8% | 70% |
| Chrome | 78.1% | 70% |

Chrome sits lower for one reason: **`holycowstudios.in` is 14.5% of it.** A person's own
domain cannot be in a shipped map, so no amount of map work reaches 80% there. Of
*coverable* browsing, Chrome is at 91%.

The primary corpus therefore carries the 80% criterion, and every other corpus carries a
70% floor whose job is to catch map rot — a category renamed, a block of domains dropped
— rather than to relitigate this ceiling. Both numbers are in the test, with the reason.

*Consequence:* the user override is not a nice-to-have. For a user whose own site is a
sixth of their browsing, it is the difference between a working product and a useless
one. T15 must make it easy to reach, not bury it in settings.

### D24 — The class distribution is severely skewed, and the benchmark must say so

`youtube.com` alone is **49.6%** of the primary corpus. With `google.com` at 20.2%, two
domains are 70% of all browsing.

So `video` and `search` will dominate every category-level model. Specifically:

- **`next_session_category` is close to trivial.** Always-guess-`video` is a strong
  baseline, and any accuracy figure that omits it is misleading.
- **`return_24h` for `video` is near-certain**, which inflates the headline positive rate
  while saying nothing about whether the model learned anything.
- The interesting signal is in the tail, where the labels are scarcest.

*Consequence for T4:* baselines must be reported **per category**, not only in aggregate,
and the majority-class baseline is mandatory. A model that beats the base rate overall
while losing to it on eleven of fifteen categories has not worked, and an aggregate-only
table would hide that completely.

This is the same class of defect as the original documents' unproducible benchmark table:
a number that is technically correct and practically meaningless.

### Map gaps that the measurement caught

The first draft missed several genuinely generic services — `deepseek.com` alone was 11.8%
of the Firefox corpus, and `insighttimer.com` 15.7%, which is why `wellness` exists as a
category at all. Coverage there went from 53.5% to 87.8% once they were added.

Worth noting as method: the taxonomy was not designed and then validated. It was drafted,
measured, found wanting, and corrected — which is the only reason `wellness` exists.

---

## 2026-08-26 — T3: resolver, sessioniser, labels, parity fixture. D25, D26, D27.

Files: `research/tise_research/features/{events,sessions,labels,resolver}.py`,
`research/fixtures/parity_{events,expected}.json`. 211 tests, Ruff clean.

### Label counts validated against T1's estimate

T1 projected label volume from a *proxy* taxonomy (top-N domains). T3 produces labels from
the real one. The acceptance criterion was ±20%:

| Corpus | T1 proxy @30m | T3 actual | Delta |
|---|---:|---:|---:|
| Chrome | 297 | 313 | +5.4% |
| Edge | 542 | 503 | −7.2% |
| Firefox | 204 | 173 | −15.2% |

All inside tolerance, so the gate decision stands on measured ground rather than on the
proxy that produced it. Projected to eight weeks: Chrome 314, Edge 314, Firefox 254.

### D25 — The sessioniser's canonical home is `features/`, not `data/`

`sessionise` was written in `data/shape.py` for T1. It is parity-critical, so it moved to
`features/sessions.py`, which is the package TypeScript mirrors. `shape.py` re-exports it;
there is one implementation, not two kept in step by hand.

Verified behaviourally neutral: the relocated function produces byte-identical session
groupings to an inline copy of the pre-move code, on both real corpora, at four timeouts.

`session_id` is derived from the **session start instant**, not a running index. The
extension assigns ids live and can never renumber earlier sessions, so an index would
disagree with the research tier the moment history is imported out of order.

### The parity fixture, and proof that it works

`parity_events.json` (input, no categories — resolving is part of what is compared) and
`parity_expected.json` (Python's answer). Synthetic and hand-designed: the file is
committed, and real history almost never contains the exact boundaries that matter —
a gap landing precisely on the timeout, a recurrence landing precisely on the horizon.

10 events → 4 sessions → 9 labels, 2 positive. All four resolution sources exercised.

**The freeze was tested by breaking it.** Flipping the session boundary from `>` to `>=`
failed three tests, including the fixture freeze. A parity suite that has never failed has
never been tested, and this one now has.

### D26 — Most categories have too few labels to model, and T4 must say so

Per-category label counts on Edge, the primary corpus:

| Category | Labels | Positive |
|---|---:|---:|
| video | 186 | 90.3% |
| search | 120 | 76.7% |
| news | 73 | 69.9% |
| unknown | 57 | 50.9% |
| work | 17 | 29.4% |
| dev | 12 | 16.7% |
| *nine others* | 2–9 each | mostly 0% |

Four categories hold 87% of the labels. Nine have fewer than ten, several have two or
three, and a category with three labels cannot be modelled, calibrated or honestly
reported — a reliability curve over three points is a decoration.

*Consequence for T4:* declare a **minimum label count** below which a category is reported
as *not modelled* rather than given a number. Aggregate metrics must state how many
categories they cover. "The model achieves X" over a set that quietly excludes nine of
fifteen categories is the same defect as the original documents' benchmark table.

### D27 — `unknown` is not noise; it is the user's own frequent sites

`unknown` is the **second largest** category on Chrome (77 labels) with an **84.4%**
positive rate. That is not a failure of the map. It is `holycowstudios.in` and the rest of
one person's personal domains, collapsed into one bucket — sites visited constantly and
therefore highly predictable.

Two consequences, and they pull in opposite directions:

- **It inflates headline accuracy.** A model scoring well on `unknown` looks good while
  predicting a bucket with no meaning.
- **It is unpresentable.** "You will return to *unknown* within 24 hours" is not a
  sentence any UI can show.

*Consequence:* `unknown` is reported **separately** from the headline metric, never folded
into it. And this is the strongest argument yet for the user override (D23): categorising
your own three most-visited domains converts the largest meaningless bucket in the model
into three meaningful ones.

### The browser split is visible in the data

Dominant categories differ sharply by browser — Chrome: search, dev, ai. Edge: video,
search, news. Firefox: ai, search.

That is D18 confirmed quantitatively rather than assumed. These are genuinely different
behavioural contexts, and merging them would have produced a blend describing no real
activity.

---

## 2026-08-26 — T4: baselines and the first honest backtest. D28, D29, D30.

Report: `docs/benchmarks/baselines.md`, generated by `tise_research.eval.report`.
283 tests, Ruff clean, output byte-identical across runs.

### The numbers

Five baselines, rolling-origin expanding folds, no shuffle, no seed. Skill is fractional
improvement in Brier over `global_base_rate`; `unknown` excluded from all of it (D27).

| Model | Edge | Chrome | Firefox |
|---|---:|---:|---:|
| `category_base_rate` | **+0.328** | **+0.152** | **+0.029** |
| `majority_class` | +0.146 | −0.368 | −0.619 |
| `time_of_day` | +0.017 | −0.031 | −0.004 |
| `global_base_rate` | reference | reference | reference |
| `same_as_last` | −0.453 | −0.322 | −0.354 |

Base rates: Edge 69.8%, Chrome 70.3%, Firefox 64.7%. Headline test sets after excluding
`unknown`: 270, 136 and 83 labels.

### D28 — The bar for T11 is `category_base_rate`, not the base rate

Only one baseline beats the reference on all three corpora, and it is barely a model:
"what fraction of the time does this category get returned to." On Edge it takes Brier
from 0.1866 to **0.1254**.

*Consequence:* T11's logistic regression is not interesting because it beats chance. It is
interesting only if it beats **0.1254 on Edge**, on these exact folds. That number goes in
the README before the model exists, so it cannot be quietly reframed afterwards.

### D29 — `majority_class` is the strongest argument in the report

It has the **second-best Brier on Edge** (0.1593, beating the base-rate model) — and a log
loss of **2.20** against the reference's 0.56. It is a hard 0/1 predictor, so its log loss
is the clamp, not a measurement.

Worse, per category it is the *best* model for the three biggest classes: `video` (95.2%
positive), `search` (87.3%) and `news` (83.3%). For the categories that dominate this
person's browsing, **"always say yes" is the model to beat.**

This is exactly the failure D24 predicted, now measured rather than anticipated.

*Consequence:* it is mandatory in every table, and any claim of the form "Tise predicts
your next session with X% accuracy" is dishonest unless X is compared against it. Brier
and log loss must always appear **together**: either alone flatters a different wrong
model.

### D30 — `same_as_last` is the project's first documented failure case

Worse than the reference on all three corpora, and on Edge fold 3 its Brier is **0.782** —
comparable to predicting the opposite of the truth. Spec criterion 12 requires at least
one documented failure with its cause; this is it.

**Cause:** it is frozen after fitting, so it repeats the last outcome seen *in training*
across an entire test window. When a category's behaviour flips near the boundary, it is
confidently wrong for every subsequent label in the fold.

*Kept, not fixed.* An online version would score better and teach less. The failure
demonstrates something worth publishing: that a plausible-sounding heuristic can be worse
than useless, and that the harness detects it rather than averaging it away.

### The `full` versus `history` distinction is not yet live

None of these baselines uses dwell time — they see only category and `window_end` — so the
two variants are **identical by construction**, and the report says so rather than
fabricating a difference. It becomes live at T10.

### Honest limitations

- Headline test sets are **83–270 labels**. Small. Confidence intervals would be wide and
  are not yet computed; T16 owes them before any number is promoted to the README.
- Only **3 of 12** categories cleared the 20-label floor on Edge. The rest are counted and
  left unscored (D26).
- Signal tracks corpus size exactly as expected: Edge +0.328, Chrome +0.152, Firefox
  +0.029. The lightly-used browser has almost nothing to learn from.

---

## CHECKPOINT A — Phase 0 complete

- [x] Real numbers from real browsing, produced entirely by committed scripts.
- [x] The T1 gate was passed — after being failed once and the cause corrected.
- [x] Parity fixture committed, frozen, and **verified by breaking it**.
- [x] `DECISIONS.md` records the session timeout (D17), the category set (D22) and the
      measured label volume (T3), all as measurements rather than assumptions.
- [x] 283 tests, Ruff clean, deterministic output.

**This is the last cheap exit.** Everything after this point is product engineering.

What Phase 0 established, in one line: a per-category base rate beats a global one by
33% on the best corpus, "always say yes" beats both on the three dominant categories, and
nine of fifteen categories do not have enough data to model at all.

---

## 2026-08-26 — T5: the permission spike, run. D31, D32, D33.

Five variants loaded in a throwaway Chrome profile. Findings in `docs/permissions.md`;
the spike is kept under `spike/permissions/` so anyone can re-run it.

### D32 — Correction: `webNavigation` does **not** need host permissions

This project previously recorded, from a web search, that `webNavigation` could not see
URLs without host permissions. **That is false.**

- Variant B: `webNavigation` alone, no hosts → **26 events, full URLs**
- Variant C: `webNavigation` + `<all_urls>` → **the same 26 events**

`<all_urls>` buys nothing and would have cost the broadest warning Chrome shows.

Audit finding 7 still stands — the original manifest could not have collected anything —
but the reason recorded against it was wrong. It failed because it declared neither
`webNavigation` nor `history` and had no service worker.

This is the second documented-looking claim in this project to fail contact with a
browser. **T5 was correctly specified as an empirical task**, and the general lesson is
kept: documentation is good enough to design against and never good enough to promise
with.

### D31 — Manifest: `webNavigation` required, `history` optional, no hosts

```jsonc
"permissions":          ["webNavigation", "alarms", "offscreen"],
"optional_permissions": ["history"],
// no host_permissions
```

Supersedes the earlier proposal of `history` as a required permission.

**`webNavigation` collects; `history` backfills.** They are not interchangeable:

| | `history` | `webNavigation` |
|---|---|---|
| Install warning | *"Read and change your browsing history on all signed-in devices"* | *"Read your browsing history"* |
| Transition inline | **no** — `HistoryItem` has no transition field | **yes** — `transitionType`, `transitionQualifiers` |
| Frame id | no | **yes** |
| Reads existing history | **yes** | no |

`webNavigation` has the milder warning *and* the richer payload. Its
`transitionQualifiers` and `frameId` map directly onto the redirect and subframe filters
built at T1, with no extra API call per visit — where the `history` route would need a
`getVisits()` call per visit purely to recover what `webNavigation` gives away.

But `webNavigation` only sees the future. Only `history.search()` reads what was already
browsed, which D10's first-run import needs. Hence one required, one optional.

**No host permissions.** Observed unnecessary for both routes.

### D33 — Consent is granted at runtime, and the dialog defaults to Deny

Variant E proved the flow end to end: installed holding only `alarms` and `offscreen`,
`chrome.history` genuinely absent, 0 events. After one click the grant landed,
`permissions.onAdded` fired, and listeners re-attached **without reloading the extension**.

So Tise can install with **no capability to read anything** and acquire it only when the
user decides. Not a policy — an absence of capability.

The dialog, screenshotted rather than paraphrased:

> *"Tise" has requested additional permissions. It could: Read and change your browsing
> history on all your signed-in devices.* `[Allow] [Deny]`

**Deny is the focused button.** Chrome designs this dialog to be declined, so the screen
that precedes it has to do the persuading (T15). The empty state for a user who declines
must be honest and permanent, never a nag.

### Backfill measured; one question left open honestly

`getVisits` costs **0.7 ms per page**, independent of corpus size. Extrapolated to ~5,000
pages, a full visit-level backfill is **~3.5 seconds**. T7 imports in one pass; no
chunking needed.

**What could not be measured:** whether `search`'s defaults truncate to 24 hours and 100
rows. All four query variations returned 20 rows, because the throwaway profile held 20
pages all from one day — there was nothing to truncate. The popup's "NO" verdict is an
artefact of the experiment, not a fact about Chrome, and is recorded as such.

It changes nothing: the mitigation is unconditional. Always pass `startTime` and
`maxResults` explicitly; never rely on a default. Confirming the truncation would require
running against real history and would buy nothing the mitigation does not already give.

### Also confirmed

- `VisitItem` = `id, isLocal, referringVisitId, transition, visitId, visitTime`.
  **No duration field.** The duration trap is now observed, not merely documented.
- `HistoryItem` = `id, lastVisitTime, title, typedCount, url, visitCount`. No transition.
- IndexedDB works with **no** `storage` permission.
- `alarms` and `offscreen` are present only when requested, and silent at install.
- "Removing a permission breaks collection" holds both ways: A saw 0 navigation events,
  B saw 0 history events.

---

## T6 — extension scaffold and live collector

### D34 — The public suffix list stays provisional, and moves to a file both languages read

`registrable_domain` needs a list of multi-part public suffixes to know that `bbc.co.uk`
is a site and `co.uk` is not. T1 embedded that list in Python and marked the real
decision as owed at T6. This is it.

**Not the Public Suffix List.** The real PSL is ~230KB and changes monthly. Bundling it
would mean deciding what a stale copy does to a benchmark computed six months later, and
that is a bigger commitment than V1 has earned.

**The list moves to `extension/src/categories/suffixes.json`**, which the extension's
`collect/domain.ts` and the research tier's `chrome_history.py` both read. Same reasoning
as `domains.json`: one file, two readers, no owner, so the two implementations cannot
drift. The file carries its own disclaimer, and a test asserts the disclaimer is there —
a partial list that presents itself as complete is exactly the thing that ends up quoted
in a benchmark.

Verified behaviourally neutral: all 283 Phase 0 tests pass unchanged after the move, and
map coverage stays at Edge 86.8% / Firefox 87.8% / Chrome 78.1%.

### D35 — Dwell time is never measured, in either direction

`TiseEvent.dwellSeconds` is `null` for live events as well as imported ones, and
`assertStorable` throws if anything sets it.

The obvious alternative — measure dwell live, since the extension *can*, and accept
`null` only for imports — is worse. Imported and observed events would then differ in
feature space, and a model trained across that boundary degrades silently as the import
ages out under retention. Uniform absence is a worse dataset and a more honest one.

The consequence is stated plainly: the `full` compat class is research-only, permanently.
Nothing that ships can ever use a dwell-derived feature. That is the duration trap
resolved rather than worked around.

### D36 — Session ids are locally assigned and opaque

The extension assigns a session id as browsing happens; the research tier re-derives
sessions from timestamps with `sessionise` and **never compares its ids to the
extension's**.

What the two implementations must agree on is the *grouping* — which events fall in which
session — and that is what the parity suite checks. Requiring the id strings to match
would mean pinning Python's `isoformat` against JavaScript's `toISOString` across
microsecond precision, which buys nothing and breaks quietly.

The boundary rule itself is shared and strict: a new session opens on a gap **strictly
greater** than the timeout. A `>` versus `>=` disagreement shifts every session-derived
feature by one event and is invisible until a test catches it, so both implementations
carry a test at exactly 30 minutes.

### D37 — Consent and pause are separate states; install collects nothing

`consentGrantedAt: string | null` and `paused: boolean`, both in IndexedDB, not one
boolean. Collapsing them would make "I paused this for an hour" indistinguishable from
"I never agreed to this", and only one of those should survive a reinstall.

Fresh install: `consentGrantedAt` is `null` and **nothing is written**. The
`webNavigation` listener is still registered at the top level of the service worker —
MV3 requires that for the worker to be woken at all — so the gate lives one layer down,
in `collect()`, and is checked *before the URL is parsed*.

Settings live in IndexedDB rather than `chrome.storage.local` because
`chrome.storage` needs a `storage` permission and IndexedDB does not (observed at T5, all
five variants). A test asserts no source file uses `chrome.storage`, so the manifest
cannot acquire that permission by accident.

### D38 — `fake-indexeddb` added as a test-only dependency

Asked and approved. It never reaches `dist/` — the Web Store only ever sees the bundle.

The alternative was a hand-rolled in-memory store behind an interface, and it was
rejected for a specific reason: the assertions it would carry are the ones that claim *no
URL is ever stored*. Against a mock, those assertions prove that the mock behaves the way
I expected IndexedDB to behave. T5 disproved two of my expectations about Chrome in one
afternoon.

Runtime dependencies remain exactly one: `idb`.

### T6 findings

- **`npm run build` type-checks twice, against two configs.** The shipped source compiles
  with no Node types at all, so anything in `src/` or `ui/` reaching for a Node API is a
  compile error rather than a runtime one in someone's browser.
- **Domain reduction is under cross-language test already**, five tasks before the parity
  suite was scheduled. `research/fixtures/domain_cases.json` holds 30 URLs and both
  languages assert against it. Broken deliberately once (`bbc.co.uk` → `co.uk`): both
  suites failed on the same row, then reverted.
- **The pause gate was broken deliberately too** — two storage tests failed, then
  reverted.
- The popup is a **developer surface**, explicitly labelled as one in its own UI. T14 and
  T15 replace it. It exists so T6 could be verified by hand rather than through devtools.

### T6 verification — observed in Chrome, 2026-08-26

Loaded unpacked from `extension/dist/`. Chrome's install line was *"Read your browsing
history"* and nothing else — no site access line, because there are no host permissions.

| Claim | Verdict |
|---|---|
| Installs holding nothing: 0 events before consent | **observed** — screenshot `ss_tt1` |
| Consent flips it to collecting, still 0 events | **observed** — `ss_tt2` |
| Live collection works: 26 events from ~10 sites | **observed** — `ss_tt3` |
| Every stored domain is bare, no path or query | **observed** — `darkreading.com`, `dominos.co.in`, `nike.in`, `zomato.com`, `google.com` |
| Multi-part suffixes reduce correctly in the browser | **observed** — `dominos.co.in` kept three labels (D34) |
| Pause stops writes | **observed** — `ss_tt4`, held at 26 |

26 events from ~10 sites is the expected ratio: several sites committed more than one
navigation, and three consecutive `nike.in` rows are one site being browsed, not a bug.

### D39 — The map's coverage on unfamiliar browsing is a T10 question, not a T6 fix

`unknown` was **12 of 26** on the verification sample — 46%, against the 13.2% measured
on the Edge corpus (D23). `dominos.co.in` and `nike.in` both fell through to `unknown`.

**Not acted on, deliberately.** Ten sites chosen to be varied are not a coverage
measurement; they are the opposite of one, because the whole point of picking them was
that they differed from each other. Adding those four domains to `domains.json` would
improve a number computed on the sample that motivated the change — the same mistake as
picking a 15-minute session timeout at T1 because it scored better.

The real question is whether the keyword rules can catch consumer brands the way they
catch government portals, and that is answered with a corpus, at T10, or by leaving it
to the user override which already beats every other layer.

### T6 verification — one interface finding

The popup is taller than Chrome's popup viewport and scrolls; the "Filtered out" counts
sit below the fold and were not visible in the verification screenshots. Harmless in a
developer surface, and a fixed constraint for T14: the dashboard has a height budget,
and the popup is not where the scorecard goes.

---

## T7 — first-run history import

### D40 — An import infers redirects from reaction time, because Chrome will not tell it

**The asymmetry.** Live collection reads `transitionQualifiers` from `webNavigation` and
drops redirect hops outright. `chrome.history` exposes `VisitItem.transition` as a *core
type only* — there are no qualifiers, observed at T5. So the import cannot make the same
call the same way.

This matters for the reason D35 matters. If live drops redirects and import does not,
imported and observed events have different distributions, and every session-derived
feature computed across that boundary drifts as the import ages out under retention. T1
already measured what redirects do to the shape: median inter-visit gap down to about a
second, domain count inflated from 133 to 236.

**The rule.** Drop a visit whose `referringVisitId` resolves to a visit at most **50 ms**
earlier.

**The threshold is argued, not fitted.** A person cannot follow a link 50 ms after the
page they are on commits; that is below human reaction time, so a navigation that close
was not a decision. The reasoning came first and would stand without a table.

**Then it was measured**, against the redirect bits in the history *file*, which the API
hides but the database keeps — `analysis/redirect_heuristic.py`, reports in
`docs/benchmarks/redirect-heuristic-{edge,chrome}.md`:

| | Edge | Chrome |
|---|---|---|
| Visits | 6,074 | 5,740 |
| Actual redirect hops | 233 (3.8%) | 702 (12.2%) |
| Precision at 50 ms | **0.947** | **0.931** |
| Recall at 50 ms | 0.773 | 0.657 |
| Referrer resolvable | 100% | 99.4% |

Precision matters more than recall here and the rule is asymmetric on purpose: a false
positive deletes a navigation the person really made, a false negative leaves one hop in.
For the same reason, a visit whose referrer was never fetched is **kept** — it cannot be
judged, and the safe direction is to keep it.

The threshold sweep is in the reports, and it is worth reading: precision holds above
0.9 up to 250 ms and then collapses — 0.47 by 500 ms on Chrome. There is a real cliff
there, and 50 ms sits well clear of it rather than balanced on the edge.

**What this does not do.** It leaves 0.9% (Edge) to 4.2% (Chrome) of imported visits as
undetected redirect hops, against 3.8% and 12.2% untreated. The mismatch is reduced, not
eliminated, and that is stated rather than rounded away.

### D41 — The import runs in the service worker and needs two separate consents

The popup asks; the worker does the work. Closing the popup mid-import does not cancel
it, and progress is written to storage as it goes, so reopening picks the state back up.
T5 measured the whole pass at ~3.5 s for 5,000 pages, so there is nothing to chunk.

Two consents, deliberately not merged:

1. **Tise may store anything at all** — the app-level decision from D37. Until this
   exists, the import block is not even shown. Offering to read someone's entire history
   before they have agreed to the small thing is asking for the large thing first.
2. **Chrome's own permission dialog** for `history`, from a click. It focuses *Deny*
   (D33), so the copy above the button does the persuading, and declining is written as a
   valid outcome in the UI rather than a nag: *"That is a valid answer. Tise collects
   from here on and never asks again."*

Every bound on `search` is passed explicitly — `text`, `startTime`, `endTime`,
`maxResults`. The 24-hour/100-row default T5 could not measure therefore never applies,
and never needs to be confirmed.

### D42 — `unknown` is not a defect to be minimised, and learned categories are a separate target

Raised after T6 showed `unknown` at 46% on a ten-site sample: can Tise learn its own
categories?

**First, what `unknown` actually is.** D27 measured it as the second largest category and
**84% positive** for `return_24h` — the most predictable thing in the corpus. It is the
person's own frequent sites, which no shipped map could contain. Minimising it buys no
accuracy. It buys **legibility**: "you will return to `unknown` within 24 hours, 84%
confident" is true and useless.

**Second, the constraint that decides the design.** A category is the *subject* of the
prediction — one label per (category, session). Change the category definition and the
label set changes with it, so Brier 0.1254 (D28) stops describing the same target. A
learned taxonomy must be versioned and benchmarked as its own target, never swapped in
silently, or every published number quietly starts describing something else.

Three layers, and they are not alternatives:

1. **Surface the override that already exists.** The resolver's layer 1 already beats
   every other layer and is already tested; it has no UI. Most of the win, no ML, T14.
2. **Titles into keyword induction.** `HistoryItem` carries `title` (observed at T5) and
   `history` is already optional, so this needs **no new permission**. Needs a T5-style
   spike first: `onVisited` often fires before the title exists.
3. **Behavioural clustering — the actual answer.** Cluster domains by session
   co-occurrence and time-of-day. No text, no titles, no server, no model API: a
   co-occurrence matrix over ~130 domains. Clusters are named by their most frequent
   member — *"sites like zomato.com"* — because without an LLM you cannot name a cluster,
   and that phrasing is honest rather than a workaround.

Layer 3 is a feature computation and therefore parity-critical, so it lands after T10 as
**T10b**, benchmarked as its own taxonomy version against the fixed one.

### D43 — The import stops where live collection starts

**Found by looking at a running extension, not by a test.** T7 shipped with an
idempotency check that was real but incomplete: importing twice creates no duplicates,
because an imported event's id is `imp_<visitId>` and Chrome's visit ids are stable.

That says nothing about a visit seen by **both** routes. A page browsed while Tise was
collecting is stored once as a live event with a uuid, and again by a later import as
`imp_<visitId>`. The two ids are legitimately different, so no id-based check can catch
it. The corpus would silently double-count exactly the period the user browsed the most.

**The fix is not to overlap.** The import window ends at the earliest live event, or at
the present if there are none. An import fills in what came *before* Tise was watching,
which is what a backfill is for.

The alternative — fuzzy-matching on domain and a timestamp tolerance — was rejected. It
needs a tolerance constant nobody can defend, it is wrong in both directions (two real
visits to the same domain a second apart are not a duplicate), and it would have to run
on every imported row.

`ImportProgress.stoppedAt` records the cut, and the popup says *"Stopped at <date>, where
Tise's own collection begins"* rather than letting a short import look like a failure.

**The T7 verification did not expose this**, because the events collected at T6 had been
deleted before the import ran. It was visible only in the arithmetic of a screenshot:
total events equalled imported events exactly, which is true when nothing was collected
live and would have been false the moment it was.

### D43 addendum — pausing leaves a hole, and the hole is correct

Written straight after D43, appended rather than folded in, because the entry is already
recorded.

The import window ends at the *earliest* live event, so any period after that is never
backfilled — including a period the user **paused** through, when Tise was installed and
consented but deliberately not watching.

That looked like a limitation and is not. Pausing means "do not record this". An import
that later reached back and filled in exactly the stretch someone paused for would
undo the only thing pausing does. Refusing to backfill a paused period is the behaviour
the pause button promises.

What this does cost is honesty in the UI, and that lands in T15: a user who pauses for a
week should be told that week is gone rather than discovering it in a chart.

---

## T8 — retention, deletion, export

### D44 — "Delete all" takes consent and the permission with it

`deleteEverything()` clears both stores: every event, every setting, the session cursor,
the import progress, the rejection counters. After it runs, `loadSettings()` returns the
defaults — `consentGrantedAt: null` — so Tise is in exactly the state it installs in and
cannot store anything until asked again.

The popup goes one step further and calls `chrome.permissions.remove({permissions:
["history"]})`. Keeping a granted permission after "delete everything" would leave Tise
able to read a history it has just promised to have forgotten. Giving the capability back
is the difference between deleting the record and deleting the ability to remake it.

Confirmation is a second click on the same button, not a `confirm()` dialog: in a popup a
modal can dismiss the popup along with itself, and a destructive action whose
confirmation can eat itself is worse than no confirmation. The armed state disarms after
six seconds.

### D45 — An export contains everything Tise holds, including the user's overrides

`tise.export.v1` carries the events *and* the settings that produced them — category map
version, suffix list version, session timeout, retention setting, and the user's own
domain overrides.

Two reasons, and the second is the one that decided it:

1. **Reproducibility.** A benchmark is meaningless without knowing which map produced the
   categories. The version numbers travel with the data or they are lost.
2. **An export that omits part of the store is the visible half of the truth.** The
   overrides are the user's own annotations about their own browsing; leaving them out to
   look more minimal would make the file a summary rather than an export.

The file is written indented rather than minified. A privacy claim nobody can open and
read is a claim nobody can check.

`sessionId` is exported but **deliberately dropped by the loader**. `Event` in the
research tier has no such field, so it is not possible to compare the extension's session
ids against re-derived ones (D36) — the rule is enforced by absence rather than by
discipline.

### D46 — The retention alarm is created on install and startup, never at the top level

`chrome.alarms.create` with an existing name **resets that alarm's schedule**. A service
worker that wakes on every navigation and re-creates its alarm at module scope would push
the next firing forward forever: raw events would never expire, the extension would look
fine, and the retention promise would quietly be false.

So it is registered from `onInstalled` and `onStartup` only. Period is six hours —
frequent enough that a day's expiry is never far off, cheap enough to ignore.

Retention touches the `events` store and nothing else, by construction. When the
`features` store arrives at T10 it must survive raw deletion (D11), and the safest
guarantee is that the code which deletes knows about exactly one store.

`rawRetentionDays: 0` means keep everything. Zero is the natural way to write "no limit"
in a settings field; a magic `null` or `-1` is the kind of thing that gets mishandled
once and silently deletes a corpus. Both settings are tested, and so is the boundary —
an event exactly at the cutoff is kept.

### CHECKPOINT B — the loop is closed

Browser → export → Python → labels, with no server, no API and no database connection
between them.

`research/fixtures/export_v1.json` is the third shared-data contract, after
`domains.json` and `domain_cases.json`. The extension asserts its exporter reproduces
that file exactly; Python asserts its loader reads it and that
`sessionise` and `return_24h_labels` run on the result unaided. Broken deliberately once
by dropping `suffixListVersion` from the exporter: three TypeScript tests failed, then
reverted.

The loader refuses an unrecognised `schema` string rather than guessing. A loader that
silently accepts a format it does not understand produces a corpus that looks fine and is
wrong, which is the failure this project can least afford.

Counts at the checkpoint: **327 Python tests, 135 TypeScript tests**, Ruff and ESLint
clean.

---

## Open questions, resolved late (recorded 2026-08-26, after T8)

The "Open questions" list near the top of this file still marks Q1, Q2 and Q3 as
undecided. They were decided by the work rather than by an entry, which is exactly how a
reasoning trail goes stale. Appended rather than edited, per the append-only rule.

- **Q1 — What exactly does V1 predict?** **Resolved.** `return_24h` per (category,
  session), D16. `next_session_category` remains in the `Prediction` schema but is not
  evaluated in V1, and the dashboard must say so (D6). Purchase intent is not predicted
  at all — that was the audit's first finding.
- **Q2 — How is a domain mapped to a category?** **Resolved by D22/D23**: a shipped,
  deliberately generic `domains.json`, then ordered keyword rules, then `unknown`, with a
  user override on top. Measured coverage: Edge 86.8%, Firefox 87.8%, Chrome 78.1%. D42
  adds what happens next and, more importantly, why `unknown` is not a defect.
- **Q3 — Does a separate web dashboard survive?** **Resolved: no.** There is no server,
  no API and no local Python service in the product. The extension does everything; Python
  runs only on the author's machine, fed by the export file. Checkpoint B is that decision
  working end to end.

**Still open: Q7** — a Tise user running four browsers sees predictions from one. Silently
partial, or stated in the UI? Blocks T15, and it is a product question rather than a
technical one.

### D47 — Copyright, and where the privacy policy lives

**Copyright: Akash Navet and Holy Cow Studios Private Limited**, both named. Tise is a
company showcase written by a director of that company, and a licence naming only one of
them would misstate which.

**The privacy policy is a section of the Holy Cow Studios privacy policy page**, not a
document of its own. That is the right shape for the same reason the extension is open
source: a policy hosted on the company's own page, next to everything else the company
publishes, is a claim the company has made — not a file that could quietly move.

Drafted at `docs/privacy-policy.md`, with two conditions written into the file itself:

1. **Every claim is re-checked against the shipped build before it goes live.** The draft
   describes V1 as specified. Anything unimplemented at submission gets cut, not softened
   — a policy describing an intention is false on the day it is published.
2. **The contact address is a suggestion until confirmed.** `privacy@holycowstudios.in` is
   proposed, and a personal address is not substituted without a decision to publish it.

The draft states what is stored as a five-row table and what is never stored as a list,
and it explains the reduction with a worked example rather than a promise: a URL with a
path and a query becomes a domain, and the rest no longer exists to be stored.

Still outstanding for T18: the live URL once the section is published, and the Web Store
developer account under the company identity (D13).

---

## T9 — the parity suite

### D48 — The oracle is a committed file, not a cross-language process call

The obvious harness runs both implementations and diffs them, which means pytest shelling
out to node or the reverse. Rejected. It couples two toolchains, makes CI's failure modes
about process invocation rather than about features, and means neither suite can be run
alone.

Instead **Python generates the oracle and both languages assert against it.**
`research/fixtures/parity_expected.json` is regenerated by
`uv run python -m tise_research.parity_fixture` and committed; `research/tests/` asserts
Python still reproduces it, `extension/tests/parity.test.ts` asserts TypeScript does too.
Either suite runs on its own, and a drift in either direction fails the one that drifted.

The file carries the rule in its own header: *"A mismatch means one side is wrong; it is
never a reason to regenerate this file without understanding why."*

**What is compared:** the resolver's category *and* which layer answered it; the number of
sessions, their membership by event id, their start and end instants, duration and
category sets; and every feature value to within 1e-9.

**What is not compared, deliberately:**

- **Session id strings.** They are locally assigned and opaque (D36). Pinning Python's
  `isoformat` against JavaScript's `toISOString` across microsecond precision buys nothing
  and breaks quietly. Instants are compared as epoch milliseconds instead, so the
  formatting difference never enters into it.
- **Labels.** Ported at T10. This is the dangerous kind of gap — an unchecked section that
  looks verified because the suite next to it is green — so the TypeScript suite asserts
  the *exact set of top-level keys* in the oracle. Adding a section to the fixture fails
  the build until someone decides whether TypeScript checks it.

**Broken deliberately, twice.** Flipping the session boundary from `>` to `>=` failed six
tests; weakening the leakage guard from `>=` to `>` failed two. Both reverted.

### D49 — Two sessionisers in TypeScript, and a test that they agree

`collect/session.ts` assigns a session to one event at a time, because live collection
cannot see the future. `features/sessions.ts` groups a whole corpus at once, which is what
the import and the trainer need.

Two implementations of one rule is normally a smell. Here it is unavoidable — the shapes
of the two problems genuinely differ — so the risk is handled rather than removed: a test
replays the fixture through the incremental version and asserts the grouping matches the
batch version exactly. A disagreement would put live and imported events in different
sessions for the same browsing, which is precisely the failure D43 was also about.

That makes three implementations of the session rule under test, in two languages.

### D50 — `featureSet: "fs_1"`, and the fixture gained a section rather than being replaced

The first feature is `hoursSinceLastSeen`, and it returns **null** for "never seen" rather
than a sentinel. A stand-in like 9999 hours is a number a model will happily fit a
coefficient to, and it means something categorically different from a measurement. The
layer that computes the feature refuses to invent an encoding for absence; the consumer
decides.

The fixture gained `featureSet` and `features` and **nothing already frozen changed** — 66
insertions, no deletions. The sessions, labels and resolutions T3 froze are byte-identical,
which is the evidence that adding a feature did not quietly alter the oracle.

Two properties of the fixture are asserted by both languages, because without them a
passing suite would prove less than it appears to:

- **It contains a never-seen case.** Without one, TypeScript could substitute a sentinel
  and still pass. The case arises naturally: a label closes at the end of its session, and
  the event that created it is *at* that instant, so it is not strictly before it.
- **It contains a non-terminating value** (`0.24972222222222223`). A fixture of round
  numbers proves very little about two floating-point implementations.

---

## T10 — the full feature set, in both languages

### D51 — Fourteen features, `featureSet: "fs_2"`, and every one of them `history`

| Feature | What it is for |
|---|---|
| `hoursSinceLastSeen`, `hoursSinceFirstSeen` | how recently, and how long this has been a thing they do |
| `eventCount7d`, `eventCount30d` | volume at two horizons |
| `daysSeen7d` | separates a habit from a binge — thirty events on one afternoon and thirty over a fortnight have the same count |
| `sessionCount7d` | volume in sessions rather than clicks |
| `categoryShare30d` | share of attention, not absolute amount |
| `priorReturnRate`, `priorSessionCount` | the person's own measured return rate, and how much it rests on |
| `sessionEventCount`, `sessionCategoryCount`, `categoryEventsInSession` | the shape of the session that produced the label |
| `hourOfDay`, `dayOfWeek` | rhythm |

**Every feature is compat class `history`, and the `full` class is empty.** That is D35
arriving at its conclusion: because Tise never measures dwell in either direction, no
shipped feature can depend on it, and the `full`/`history` split that T1 introduced now
only matters for research-only exploration. The mechanism stays — the distinction is real,
and the day it stops being empty must not be the day it gets invented.

**Absence is `null`, never a sentinel.** A stand-in like 9999 hours, or a prior of 0.5, is
a number a model will fit a coefficient to as though it had been measured. Several of the
fourteen can be null, and the parity suite asserts TypeScript reproduces the nulls rather
than filling them in.

**Time is UTC, and it costs signal.** Local days would be the more behavioural unit —
people have mornings, not 00:00 UTC — but the browser's timezone and the research
machine's are not the same, and a feature that depends on which computer ran it cannot be
in a parity suite. Recorded as a known limitation rather than smoothed over.

### D52 — `priorReturnRate` excludes sessions whose horizon has not elapsed

The strongest feature in the set, and the one that leaks if written the obvious way.

Deciding whether a past session was returned to means looking at the 24 hours after it —
and for a recent session, some of those hours are still in the future at `window_end`.
Counting it as a miss says "no return" when the return may be an hour away. Counting it as
a hit reads the future outright. **Both are wrong, and the miss is the tempting one**,
because it looks conservative.

So a prior session counts only when `session_end + horizon <= window_end`. Unresolved
sessions are absent from **both** numerator and denominator, and `priorSessionCount`
travels alongside so a rate built on two sessions is visibly different from one built on
forty.

The parity fixture was extended to make this testable: it now carries a run of `dev`
sessions with deliberately mixed outcomes, so `priorReturnRate` takes values of 0, 0.25,
0.286, 0.333 and 0.5 rather than being null almost everywhere. **The extension is
append-only** — every added event falls more than 24 hours after the last previously
frozen session closed, so no existing session or label changed, and the diff has no
deletions in any frozen field.

### D53 — Feature rows live in their own store, at database version 2

D11 said derived features outlive raw events. This is where that becomes true rather than
intended: a third IndexedDB store, keyed on `(featureSet, subject, windowEnd)` so
recomputation replaces rather than duplicates — which matters because training is chunked
and resumable and will recompute a window it has already seen.

`enforceRetention` touches `events` and nothing else, and a test now asserts that a
feature row whose window is 400 days old survives a 30-day retention pass.

**Deletion is not retention.** `deleteEverything` clears the feature store too. Retention
is a promise about how long raw browsing is kept; "delete everything" is a promise about
everything.

### T10 findings — three deliberate breaks, and one weak test of my own

Each break failed exactly two tests, then was reverted:

| Break | Why it matters |
|---|---|
| `dayOfWeek` without the Sunday-to-Monday conversion | Python's `weekday()` is Monday=0, JavaScript's `getUTCDay()` is Sunday=0. Every day-of-week coefficient shifted by one, and nothing outside parity would notice |
| `priorReturnRate` counting unresolved sessions | the leak D52 exists to prevent |
| the frequency window closed rather than half-open | an event exactly at `window_end` counted, on the wrong side of the boundary |

**And a flaw in my own test.** The first break should have failed the "Monday=0" test as
well as the vector comparison. It did not, and the reason was that the test read the value
out of the fixture rather than computing it — it was asserting that Python had written what
Python wrote, and could never have failed from a TypeScript bug. A second test,
"reproduces repeating decimals", had the same shape. Both now assert against the
implementation.

Worth recording because it is the failure mode a parity suite is *most* prone to: a test
that reads the oracle and calls it verification.

---

## T11 — in-browser training

### D54 — The optimiser is written out by hand, in both languages

scikit-learn solves logistic regression with LBFGS: a line search over a quasi-Newton
approximation. Nothing in a browser is going to reproduce its iterates to 1e-9, and a
model whose coefficients cannot be reproduced in the extension is a model the extension
does not ship. The whole premise of Tise is that training happens on the user's own
machine over the user's own browsing, so the optimiser has to be something both languages
can execute identically.

It is therefore **full-batch gradient descent with a fixed iteration count**, from a
starting point of all zeros, accumulating in a fixed row-major order. No random
initialisation, no seed, no early stopping — every one of those is a place two
implementations can diverge without either being wrong.

The cost is real: LBFGS would converge in tens of iterations where this takes thousands.
That is the price of the parity contract, and it is paid rather than argued away.

**Measured:** on the fixture, after 4,000 gradient steps and ~72,000 `exp` calls, the
largest disagreement between Python and TypeScript is **2.2e-16** on any coefficient and
**4.4e-16** on any matrix cell — seven orders of magnitude below the 1e-9 tolerance. The
concern that accumulated floating-point error would make the tolerance tight turned out
to be unfounded, and it was checked rather than assumed.

### D55 — The step size is derived from the design matrix, not declared

A hand-picked learning rate works on the data it was picked on. Gradient descent diverges
once the step exceeds `2/L`, and `L` depends on how collinear the columns are — which
depends on whose browsing it is. "0.5 worked on my history" is not a claim worth shipping
to somebody else's machine, where the failure would be a model that silently produces
garbage rather than an error anyone sees.

So the step is `1/L` for an upper bound on the curvature computed from the matrix itself:
a quarter of the mean squared row norm plus `l2/n`. It provably cannot diverge for any
input, including perfectly collinear columns.

This was **not** the first design. The first used a declared `learning_rate = 0.5`,
which passed every test — and would have diverged on a profile whose columns happened to
be more correlated than mine. The bound is a smaller step and costs iterations; the
iteration count went from 1,000 to 4,000 to pay for it.

The guarantee is tested by violating it: a test multiplies the step by 400 and asserts the
fit does diverge. A bound nobody has watched do anything is arithmetic, not a safeguard.

### D56 — Absence gets its own column rather than a filled-in value

D51 made absence `null` and never a sentinel, precisely so nothing downstream fits a
coefficient to a number that was never measured. A linear model cannot consume `null`, so
something has to go there — and whatever goes there is exactly the invented number D51
forbade.

The resolution is to fill with the **training mean** and add a **column recording that the
fill happened**. The model learns what absence is worth instead of being told it is worth
the average. Four of the fourteen features are nullable, so the design matrix has 18
columns.

`priorReturnRate__missing` is very nearly `priorSessionCount == 0` restated, so two of
those columns are close to collinear. That redundancy is left in and recorded rather than
tidied away: dropping the indicator because another column implies it would be reasoning
about the data instead of measuring it, and L2 absorbs it.

Standardisation is **part of the fitted model** — means and deviations come from the
training window only and are reapplied unchanged. Refitting them across train and test is
the textbook leak, and it does not look like a leak; it looks like a slightly better
score. A column with no variation in training gets a scale of 1, which turns it into
zeros: it carries no information, and the model should not be able to fit it. On the
fixture exactly one column is constant (`categoryShare30d__missing`) and its coefficient
is exactly 0, which a test asserts.

### D57 — Training is chunked, and the training set is pinned when a job starts

MV3 terminates service workers with no warning and no callback, so anything that must
finish cannot be one long call. Training advances a fixed number of steps per wake-up and
writes a complete, resumable state each time. Chunked training and one-shot training
produce **bitwise identical** results, asserted by running at chunk sizes of 1, 3, 7, 50,
999 and 10,000 and by dropping the database handle between chunks.

The subtler half: chunk seven must train on exactly what chunk one did. If browsing
happens mid-run, or an import backfills older history, the set moves and the result is
several fits blended by accident — which looks like nothing at all. So a job records its
window and row count, and **restarts** if either stops matching. Restarting is visible and
cheap; continuing is invisible and wrong.

### D58 — Labels live in their own store, at database version 3

A feature row alone cannot retrain anything; it has no answer attached. So labels persist
on the same terms as features (D11) — outliving raw events, so a person keeps what was
learned from their browsing without keeping the browsing.

They are a separate store rather than a field on `FeatureRow` because the two have
different lifecycles. **A feature vector is final the instant it is computed. An outcome is
provisional until its horizon has elapsed**, and is rewritten when it resolves. Putting a
mutable field inside an immutable row is how a "recomputed" feature quietly becomes a
different feature. It also keeps the `FeatureRow` schema unchanged, which is on the
ask-first list.

`enforceRetention` still touches `events` and nothing else. `deleteEverything` clears
labels, features and the trained model: retention is a promise about how long raw browsing
is kept, deletion is a promise about everything.

### D59 — The offscreen document was not needed, and the permission has not been removed

The plan specified training in an offscreen document, on the reasoning that training is
long-running. **Chunking removes the premise**: no single call is long. The service worker
does a chunk in milliseconds and is free to die immediately afterwards.

So `offscreen` is currently an unused permission. It has **not** been removed, for two
reasons. Removing a permission is a manifest change and is on the ask-first list. And D31
justified it from an observation, so retiring it deserves an observation too — a timed
chunk on a profile with real history, not an argument from the shape of the code.

Recommendation to Akash: remove it at T18 unless a real-profile timing says otherwise. A
permission the extension does not use is a permission that has to be justified to the Web
Store and to anyone reading the manifest, and "we might need it later" is exactly the
reasoning that produces the manifests this project criticised at T5.

### D60 — The bar is cleared on Edge, and the result is weaker than that number alone

D28 set the bar at **Brier 0.1254 on Edge**, what `category_base_rate` scores there.

`logreg_fs2` scores **0.1119**, skill **+0.400** against the base rate's +0.328. The bar
is cleared, on the corpus it was set on, on identical folds.

**That is the most flattering true sentence available, and it is not the whole result.**

- On Edge the model wins **2 of 5 folds**. The pooled score clears the bar because the two
  folds it wins, it wins by a lot. Pooling rewards the size of a win, not its consistency.
- On **Chrome it loses outright**: 0.2195 against 0.1868, barely better than reporting the
  global base rate.
- On Firefox it clears the bar and wins 4 of 5 folds.
- Across all three corpora: **8 of 15 folds**.

The pattern is the same everywhere: **the model wins the early folds and loses the late
ones**, which is the opposite of what more training data should do.

One measured fact bears on that, and it is a lead rather than a conclusion. Several
features are cumulative counters that only grow, so in an expanding-window backtest a test
row always sits later in the calendar than every training row. On Edge, **77.5% of test
rows have `hoursSinceFirstSeen` outside the range the coefficients were fitted on**;
`priorSessionCount` 42.1%, `eventCount30d` 31.1%. A linear model extrapolating beyond its
fitted range is a reason to expect exactly this shape of failure.

Confirming it means changing those features and re-running these folds — and the change
has to be chosen **without looking at these numbers**, or the fix is fitted to the test
set. That is T16, along with the confidence intervals that would say whether a 2-of-5
fold split means anything at all at these sample sizes.

Nothing was tuned to produce this. `l2` is fixed at 1 for every fold and every corpus,
and no feature was added, dropped or transformed after seeing a score. The cyclic encoding
of `hourOfDay` and `dayOfWeek` that a linear model would ordinarily want was deliberately
**not** added, so that if it is added later its effect can be measured against this.

### D61 — The parity fixture never tested the horizon boundary, and now does

Found the way these things get found: the label boundary in the TypeScript mirror was
changed from `<=` to `<` on purpose, and **all 227 tests passed**.

The fixture header had claimed since T3 to cover "a recurrence inside the horizon and one
outside it", and it did. It never covered one landing *on* it, so the boundary itself was
unobservable and either language could have had it wrong indefinitely. The closest any
label came to 24 hours was 23.25.

Two events were appended — a session on day 12 and a return exactly 24 hours later — and
the same break now fails 3 tests. The extension is additive: no existing outcome changed,
no label was dropped, every previously frozen session is preserved, and that was verified
against `git show HEAD` rather than asserted. A fixture-trust test now requires at least
one label to sit exactly on the horizon, so the gap cannot silently reopen.

This is the second time a hole has been found in the tests rather than the code — T10 had
two assertions that read values out of the oracle instead of computing them. Both were
found by breaking something and counting what failed. **A parity suite that has never been
watched fail has not been tested**, and the count matters as much as the failure: a break
that fails one test where it should fail three is itself a finding.

### D62 — The iteration budget is justified by a measurement, not by a threshold

4,000 steps reaches a gradient norm around 1e-16 on the synthetic fixture and only about
**2.4e-5** on real browsing. Calling the latter "converged" would use a word the number
does not support, and the first draft of `model.md` did exactly that before the number was
read properly.

The useful question is not whether the gradient reaches zero but whether the remaining
distance changes an answer this project publishes. `analysis/convergence_budget.py`
answers it directly: multiplying the budget by five moves the pooled Brier by **1.3e-5 on
Edge, 4.2e-6 on Chrome, 4.5e-8 on Firefox** — all far below the fourth decimal place the
reports quote.

So the budget is sufficient *for the claims being made*, which is a different and smaller
statement than "the optimiser has finished". Raising it would cost battery on somebody
else's laptop to buy a change nobody can see. Both halves are in
`docs/benchmarks/convergence-budget.md` so the distinction stays visible.

### D63 — `offscreen` withdrawn from the manifest

Amends D31, which required `webNavigation`, `alarms` and `offscreen`. The manifest is now
**`webNavigation` + `alarms`**, `history` optional, no host permissions.

D31 justified `offscreen` for training, and that justification was sound when written.
D57 then built training as a chunked, alarm-driven job: each wake-up advances a fixed
number of gradient steps and writes a complete resumable state, so no single call is long
enough for the worker's lifetime to matter. The premise was gone; the permission had
outlived it.

D59 recorded this and left the permission in place pending a real-profile timing, on the
principle that retiring something justified by observation deserves an observation. Akash
overrode that and removed it now. He is right, and the reasoning is worth keeping: **an
unused permission is not neutral.** It has to be justified to the Web Store, it appears in
the install warning, and it sits in a manifest whose whole claim is that nothing is
requested that is not needed. Waiting for a measurement before removing a capability
nothing calls is the same "we might need it later" reasoning this project criticised at T5
— and the timing that D59 wanted can be taken with the permission absent just as easily,
because if the chunked trainer ever did need a document that outlives the worker, the
manifest test would fail rather than the code silently succeeding.

`manifest.test.ts` now asserts the string appears nowhere in the manifest, as a separate
assertion from the permission-set equality: one says "the set is what we expect", the
other says "this specific capability is not requested". The T5 justification text survives
struck through in `docs/permissions.md` rather than deleted, because that file's value is
the record of what was justified and why, including the parts that stopped being true.

### D64 — T11 verified on a real profile, and the truncation question is closed

Akash ran the built extension on his signed-in Chrome on 2026-08-27
(`Screenshots/t11-1.png` … `t11_6.png`, gitignored). Observed, not argued:

| | |
|---|---|
| Imported | **5,105 events**, 22 not-web and 49 redirect rejected |
| Trained | **334 labels, 72% positive**, `fs_2` |
| Final gradient | **4.2e-6** |
| Elapsed | under a minute, popup to popup |

Three things this settles.

**The T5 truncation worry was unfounded, and it is now measured rather than mitigated.**
T5 could not test the default 24h/100-row truncation on a 20-page profile and left it
open, mitigated unconditionally by always passing explicit `startTime`, `endTime` and
`maxResults`. The import asked for 90 days and returned 57. That looked exactly like
truncation. It is not: the history *file* for the same browser holds **zero visits before
2026-07-01**, so 57 days is all the history that exists. The import is complete.

**D62's iteration budget holds on a real profile.** The worst fold gradient in the
research backtest was 2.4e-5; a real 334-label fit reached **4.2e-6**, comfortably inside.
The 4,000-step budget is not something that only works on the author's research corpora.

**The label yield matches the research corpora.** 334 labels at 72% positive against
Chrome's 313 at 70.3% and Edge's 503 at 69.8%. Nothing about the extension's own pipeline
produces a different-shaped dataset from the one the benchmarks were computed on — which
was not guaranteed and is the reason to check.

The Python loader also read the real export unchanged, which closes the second
verification owed since T8. Both owed verifications are now done.

### D65 — The redirect asymmetry is real, and it runs the opposite way to D40's assumption

D40 built a referrer-gap heuristic so that imports would not carry redirect hops that live
collection drops, and scored it against the history file's redirect bits: on Chrome, 702
hops (12.2%), precision 0.931, recall 0.657.

**In production it fires on 0.95% of visits, not 12.2%.** 49 of ~5,176. It is recovering
roughly one in fourteen of what the file's bits identify.

Tracing one case end to end — a Google result click on 18 August — shows why, and shows
that the framing was wrong:

```
google.com/url?url=...zivasuites...   core=LINK, no redirect bit
www.zivasuites.com/                   CLIENT_REDIRECT
www.zivasuites.com/  (https)          SERVER_REDIRECT
www.zivasuites.com/#banner            CLIENT_REDIRECT
```

The research pipeline excludes redirect hops, so it keeps **`google.com`** and throws the
hotel away. The extension has no qualifier bits to filter on (the T7 qualifier trap:
`VisitItem.transition` is core-only), the four hops land inside the same minute but not
inside the 50 ms window, and it keeps **`zivasuites.com`**.

So the two views of the same browsing disagree — and **the extension is arguably the more
correct one.** The person clicked a search result and read a hotel page. The hotel is the
navigation they chose; `google.com/url` is plumbing. D40 assumed the file was the ground
truth the product should be made to match. On this evidence the product's view is the
better description of behaviour, and the research corpus is the one losing information.

Quantified over the overlapping window, 5,057 export events against 4,994 file visits:

- Totals differ by **63** — near enough to look like agreement.
- Per-domain they disagree on **391 events, 7.7% of the corpus**.
- 95 domains appear only in the export (109 events); `google.com` is 115 higher in the
  file, which is the same mechanism seen from the other end.

**Matching totals concealed a composition difference of 7.7%**, and an earlier reading of
these numbers in-session took the totals as agreement. That is the mistake this entry
exists to record: two counts that agree are not two datasets that agree.

Nothing is changed on the strength of this. It affects **T16**, because every published
benchmark is computed on the research view while the extension ships the other one — the
parity suite guarantees the two *implementations* agree and says nothing about the two
*event streams* agreeing. Options, none chosen yet: teach `load_visits` to follow a
redirect chain to its landing page, widen the gap window, or drop the heuristic and accept
landing pages on both sides. Each changes the corpus, so each invalidates the numbers in
`docs/benchmarks/` and has to be re-run rather than argued.

A thing that was *not* found, recorded because it was chased: the export contains 95
domains the file's redirect-filtered view lacks, and Chrome's permission dialog says
"on all your signed-in devices", so synced history from another device merging into one
profile — a D18 violation — was the leading hypothesis for a while. It is not that. Every
one of those domains is present in the local file as redirect hops. No sync, no merge.

---

## T12 — calibration and abstention

### D66 — Platt, not isotonic, and it reuses the model's own optimiser

Isotonic regression is the more flexible calibrator and the wrong one at this scale. It
fits a free-form monotone step function, which needs a lot of data; on the few hundred
labels a real profile produces it would fit the calibration set's noise and report it as
confidence. Platt fits **two parameters**, which is about the most this data supports.
Isotonic becomes the right answer at roughly ten times the labels — a reason to revisit it
then, not a reason to reach for it now.

Platt scaling *is* a one-feature logistic regression, so it reuses `logreg`. That took one
small generalisation: targets became `bool | float`, since the gradient `p - y` is
identical for a soft target and the `1.0 if outcome else 0.0` conversion was the only thing
rounding them away. The result is **one optimiser in this project to keep in parity rather
than two** — and it is the one already measured agreeing across languages to 2e-16.

The input is the **logit** of the raw probability, not the probability, which makes
`a = 1, b = 0` exactly the identity. A calibrator that has learned "you were already right"
is then visibly the identity rather than some arbitrary pair.

**Soft targets, from Platt's original paper.** Fitting to hard 0/1 on a small calibration
set drives the coefficients toward separating it perfectly, which is exactly the
overconfidence calibration exists to remove. The ends are pulled in by one pseudo-count
each — the same shape of fix as the smoothing in `baselines.py` and the transition table.

An identity calibrator is returned when there is nothing to learn from: no data, or one
class only. It is deliberately not a silent no-op — a prediction carrying the identity is
*visibly uncalibrated*, which is a different claim from a calibrated one, and the popup
says which.

**Measured on real browsing, calibration works.** ECE falls on every corpus:
Edge 0.1664 → 0.0541, Chrome 0.1845 → 0.1113, Firefox 0.2439 → 0.1254.

### D67 — The three-way split, and what it costs

Each fold's training window is cut chronologically: 70% to fit the model, 30% to fit the
calibrator and choose the threshold. The test window is untouched by both.

Fitting the calibrator on the model's own training rows is the standard way to get this
wrong, and **it does not look wrong**. The model is over-confident on data it memorised, so
a calibrator fitted there learns to undo memorisation rather than error, and the
probabilities come out confidently mis-stated on everything new. There is no error
message; the reliability curve simply looks better than the model deserves.

The split is chronological, never random. A random split would put a label from Tuesday in
the fit part and its neighbour from the same session in the calibration part, and the
calibrator would be measuring the model on data it effectively already saw.

**The cost is real and is reported rather than absorbed.** The model in `calibration.md`
trains on 70% of what the model in `model.md` trains on, so its raw Brier is worse. The raw
and calibrated columns are the same weakened model, so that comparison is like-for-like —
and neither column is comparable to T11's numbers. The extension makes the same trade with
the same fraction, so the benchmarks describe the thing that ships.

### D68 — MCE got worse while ECE got better, and both are reported

On Edge, calibration improved expected calibration error from 0.1664 to 0.0541 and made
the **worst bin worse**: maximum calibration error went 0.5120 → 0.9991. Five predictions
were pushed to about 0.001 and all five turned out positive.

This is exactly what MCE exists to reveal and precisely why it is reported next to ECE. An
average over bins can improve while the model becomes catastrophically wrong in one narrow
range — and that range is where a user would act most confidently on the answer. A report
quoting only ECE here would be true and misleading.

The mechanism is fold 0, whose model is poor (raw Brier 0.3350) and whose calibrator slope
is 0.313 — a hard squash that drives some predictions to the floor. Nothing is done about
it at T12. It is a T16 problem, and it is written down rather than smoothed.

### D69 — The abstention threshold rests on a lower confidence bound, not the observed accuracy

The rule as first written was "the lowest threshold whose accuracy on the calibration slice
clears the target". It is **optimistically biased twice over**, and the measurement showed
it plainly: on Edge that rule qualified on **4 of 5 folds and kept its promise on 1 of
them**.

Two mechanisms, neither of which needs these numbers to establish:

1. **Argmin over noise.** Fifty candidate thresholds are tried and the first one clearing
   the bar is taken. A model with *no skill at all* was accepted by that rule on 3% of
   simulated 100-row slices — a threshold that clears by luck.
2. **Sampling error, which dominates.** On ~100 answered rows the standard error of an
   accuracy near 90% is about 3 points, so a threshold measured at exactly the target sits
   below it roughly half the time.

The fix is to require the **Wilson lower bound** of the answered accuracy to clear the
target, not the point estimate. `z = 0` recovers the old rule exactly, so the two differ by
one parameter and are reported side by side in `calibration.md` rather than one quietly
replacing the other. The simulation that accepted a skill-free model 3% of the time under
the old rule accepts it **0 times in 200** under the new one.

**Honest about the order of events:** the failure was observed first, then the correction
applied. The correction is justified by an argument that does not depend on these numbers —
argmin over noisy estimates is biased whatever the data says — but it was not foreseen, and
recording that is the point of this entry.

### D70 — On this data Tise abstains from everything, and that is the result

Under the shipped rule, **no threshold qualified on any fold of any corpus**. The extension
predicts nothing.

That is not a bug and it is not a failure of the abstention machinery — it is the
machinery working. The declared target is 90% (D-style declared hyperparameter, stated in
advance like the 30-minute session timeout so that reachability is a *finding* rather than
a knob). Pooled on Edge, threshold 0.85 answers 59% of cases at 90.0% accuracy — above
target as a point estimate. Certifying a margin that thin at 95% confidence would need
**more than 12,800 answered rows**; the calibration slices hold 61–133.

So the shortfall is **the width of the margin, not the model**. The arithmetic is
instructive: an observed 95% certifies against a 90% target on about 100 rows, an observed
93% needs about 400, an observed 91% needs about 3,200. Tise is at roughly 90–91%.

Three ways out, none taken at T12 because each would be tuning against the numbers above:
lower the target, gather more history, or improve the model so its accuracy at high
confidence has room to spare. The third is the interesting one and it is T16's job.

The popup says so in words rather than showing a prediction anyway: *"predicts nothing — no
confidence threshold reached the 90% target on held-out data."* Abstained predictions are
**absent from the UI, not greyed out** — a greyed-out prediction is still a prediction, and
people read it.

### D71 — Two more fixture gaps found the same way, and closed the same way

The reliability curve had a real binning bug: `int(0.3 / 0.1)` is 2, because `0.3 / 0.1` is
2.9999999999999996. Every prediction landing exactly on a decile edge fell one bin left.
Predictions cluster on round numbers, so this was not rare — it tilted whole populations.
Bin membership is now decided by comparing against `(index + 1) / bins`, which is exact
against the same double the edge is reported as. Found by a test written to assert the
half-open convention, not by inspection.

And the parity fixture did not exercise the logit clamp: a fitted model never emits a raw 0
or 1, so removing the clamp broke exactly **one** TypeScript unit test and **no** parity
test. That is the D61 shape again — a boundary the fixture claimed no coverage of and
therefore could not defend. Fixed the same way, by putting the boundary in the fixture:
`logitCases` now carries 0.0, 1e-15, 0.5, 1-1e-15 and 1.0, and the same break now fails
two tests.

The `model` section of the oracle also gained its own key-set guard. The top-level guard
introduced at T9 would not have noticed `calibration` being added *inside* `model` — the
same failure it exists to prevent, one level down.

Six deliberate breaks, each reverted: hard targets instead of soft, the logit clamp, the
Wilson bound reduced to a point estimate, threshold selection taking the highest instead of
the lowest, abstention ignoring an unmet target, and training no longer holding out a
calibration slice.

---

## T13 — the prediction registry

### D72 — `expired` is not a miss, and that needed a record of when Tise was not watching

SPEC.md gave the four outcomes — `pending`, `hit`, `miss`, `expired` — and did not say
what separates the last two. It matters more than it looks.

A `miss` is a **claim about the world**: the window closed and the person did not come
back. That claim is only true if Tise was watching for the whole window. If collection was
paused for six of the twenty-four hours, "no return was seen" is not evidence that no
return happened — it is the absence of evidence, and recording it as a miss puts a
fabricated negative into the reliability curve.

So `expired` means *the window closed and Tise could not tell*, and it is **scored by
nobody**. `ExportedPrediction.scoreable` is true for `hit` and `miss` only.

This is D52's rule in a new place. There, prior sessions whose horizon had not elapsed were
excluded from both sides of the ratio rather than counted as misses, because counting them
as misses is the tempting shortcut that looks conservative and is wrong. Same shortcut,
same answer.

Three things produce `expired`, and each is a real hole rather than a hypothetical one:

- **Collection was off** for part of the window — paused, or consent withdrawn.
- **The window opened before consent** was ever given.
- **Retention deleted the evidence** before anyone looked. Rare at a 30-day window against
  a 24-hour horizon, and not impossible.

A **closed browser is not a gap**. If the person was not browsing, no return genuinely
happened, and that is a real miss. What counts is Tise being unable to observe browsing
that may have occurred.

`storage/coverage.ts` records gaps rather than uptime, because gaps are rare — an empty
list is the honest representation of "always watching". Recording is hooked into
`saveSettings`, which is the single choke point every route into pausing passes through:
the popup, consent withdrawal, delete-all. Hooking the callers instead would mean
remembering at every future call site, and the failure would be silent — predictions
resolving to `miss` for windows nobody watched.

**A hit is still a hit through a gap.** A return that *was* observed is evidence whatever
was missed around it; only the negative needs full coverage to be trustworthy.

### D73 — Resolution is a pure function, so idempotence is structural

The acceptance criterion was "resolution is idempotent and correct across browser
restarts". That is met by `resolveOutcome` being a pure function of
`(prediction, events, coverage, now)` — there is no cursor to lose, no partial progress to
reconcile, and no "last resolved at" marker that could disagree with the store.

`resolveAll` returns only the predictions whose outcome *changed*, which makes idempotence
directly assertable: a second pass over the same state returns an empty list, rather than
having to be inferred from row counts that happen to match.

The registry pass creates before it resolves, so a session that closed and was returned to
between two alarms gets both its prediction and its resolution in one pass.

### D74 — Abstained predictions are stored, and on this data that is all of them

Every prediction is written to the registry including the ones the abstention policy
refuses to display. They are stored *precisely because* they are not shown: the only way to
learn whether abstaining was the right call is to write down what would have been said and
check it against what happened.

D70 makes this concrete rather than theoretical. On the author's own browsing **every**
prediction is abstained, so a registry keeping only displayed predictions would be empty
and could never answer whether the silence was justified. T16 will need exactly these rows.

The popup panel therefore shows counts and no predictions. That is not a placeholder for
T14 — a panel listing "what Tise thinks you will do next" would be listing things the
measurement said not to claim.

### D75 — `windowEnd` means opposite ends of the same day in two schemas

A `Label` and a `FeatureRow` have a `windowEnd`: the instant the label became *decidable*,
which is when a session closed. Features look strictly before it.

A `Prediction` has `windowStart` and `windowEnd`: the span the prediction is *about*.
`windowStart` is that same session close; `windowEnd` is 24 hours later.

So `prediction.windowStart === label.windowEnd` — the same instant under two names, and
`prediction.windowEnd` is a full day past anything a `Label` calls by that name. Both are
strings, so nothing catches a confusion between them at the type level.

Renaming was considered and rejected: `Prediction`'s field names are fixed by SPEC.md, and
`Label.windowEnd` is in the frozen parity fixture and in every committed benchmark. The
mitigation is that **exactly one function performs the conversion** (`buildPredictions`),
it is spelled out where it happens, and `assertStorablePrediction` enforces
`dataCutoff === windowStart` on every write — so a prediction built from the wrong end of
the day cannot be stored at all.

### D76 — The export is v2, and v1 is kept readable on purpose

`predictions` was added to the export, so the schema moved to `tise.export.v2`. The change
is additive — a v2 file is a v1 file with one more key — and the version moved anyway,
because "the loader happens to ignore it" is not a contract. A loader silently accepting a
file whose predictions it dropped would produce a benchmark missing exactly the rows the
file was exported to carry.

The Python loader reads **both**. `research/fixtures/export_v1.json` is kept frozen and is
never regenerated: someone who exported their browsing before the registry existed should
not find the file unreadable because a later version added a key, and keeping the old
fixture is how that promise is *tested* rather than asserted.

`export_v2.json` is hand-designed like the parity fixture, and exercises all four outcomes
and both abstention states. A fixture missing an outcome cannot catch a bug in handling it.

### D77 — A third hole in my own tests, found the same way

Eight deliberate breaks. Seven failed between one and three tests. The eighth — removing
the filter that stops the registry pass rewriting predictions it has already made — failed
**nothing**.

That break resets a resolved outcome back to `pending`, silently erasing a measurement.
The cause was the shape of the suite rather than the code: every registry test either
exercised `updateRegistry`'s refusals (no consent, no model) or called `resolveAll`
directly, so the path *between* them — the one that needs a trained model to reach — had no
test through it at all.

Fixed with an end-to-end group that trains a real model and runs the pass twice. The same
break now fails.

This is the third time: T10 had two assertions that read values out of the oracle instead
of computing them; T12 had a logit clamp no parity test touched; T13 had a whole code path
behind an early return. **The count matters as much as the failure** — a break that fails
nothing is a finding about the tests, and the only way to see it is to break things one at
a time and count.

---

## T16 — model tournament and benchmark report

### D78 — Chrome's history API hands over redirect chain *ends*, and that was the corpus bug

D65 left one thing open and named it as T16's first job: the research corpus and the
extension disagreed about 7.7% of events, every published benchmark rested on the research
side, and three candidate fixes were listed with none chosen. Choosing between them turned
out to be the wrong task, because the premise underneath all three was wrong.

**What was assumed.** D40 built a 50 ms referrer-gap rule so that an import would drop the
redirect hops that live collection drops with `transitionQualifiers`. It was scored against
the file's redirect bits and reached precision 0.931, recall 0.657 on Chrome. D65 then
observed the shipped rule firing on 0.95% of visits rather than the file's 12.2%, and read
that as the rule recovering roughly one hop in fourteen.

**What is true.** `chrome.history.search()` returns only visits marked `CHAIN_END` — the
same filter that makes the history UI show the page you landed on rather than the three
bounces that got you there. Measured on the Chrome corpus by joining the export's
`imp_<visitId>` event ids directly against the file's visit ids, so this is an exact join
and not an inference from totals:

| | in the export |
|---|---:|
| chain-end visits | 5,019 of 5,094 (**98.5%**) |
| everything else | 56 of 646 (**8.7%**) |

521 distinct URLs in the window have no visit in the export at all, and 97.1% of them have
no chain-end visit. Both symptoms D65 could not explain fall out of that one fact:

- **365 visits the file holds that the import never wrote**, each passing every shipped
  filter. 99.5% sit on a page that is wholly absent.
- **220 redirect hops the import kept despite a sub-50 ms gap in the file.** For
  **100% of them** the referring visit is present in the file and absent from the export.
  The rule did not misjudge them; it was handed no referrer and, correctly, kept them.

So the heuristic was never recovering one in fourteen. It was being shown a corpus Chrome
had already filtered, with the referrers it needed to judge the remainder deleted.

**And once Chrome has filtered, the 50 ms rule is net harmful on this evidence.** Replayed
over the corpus the API actually supplies, it flags **1 true redirect hop and 34 ordinary
navigations** on Chrome, and **0 and 10** on Edge. D40 tuned that threshold for precision
deliberately — a false positive deletes a page the person really visited, a false negative
only leaves a hop in — and against the real input that trade now runs backwards: 44 real
navigations deleted across two corpora to remove one hop. D40's precision of 0.931 was
measured against every row in the file, which is not the population the rule ever sees.

Nothing is changed on the strength of that. It is two profiles, the rule is in shipped
code, and touching collection is a product change rather than a corpus one. It is recorded
here as the number that decides it, which D40 never had.

**The bits are not complements, and that is the whole problem.** A chain *start* such as
`google.com/url?...` carries **no redirect bit at all**. Filtering on `REDIRECT_MASK` —
what the research tier did from T1 until now — therefore keeps the plumbing and discards
the page the person actually read. D65 guessed the extension's view was "arguably more
correct". It is not arguable: the extension's view is Chrome's own answer to *where did
you go*, and the research corpus was the one losing information.

**Decision: three named views, and the default is what ships.**

- `shipped` — chain ends only. **Every benchmark uses this.** A number computed on visits
  the product cannot be given describes a model that was never run.
- `chosen` — the pre-D78 filter, kept so the superseded numbers stay *reproducible* rather
  than merely quoted. `--view chosen` regenerates them.
- `raw` — every hop, for measuring what the filters do. Never for modelling.

`load_visits`, `load_events`, `load_labels`, the backtest and the calibration run all take
it, so a benchmark cannot silently be computed on a corpus nobody asked for.

**Firefox gets the same definition, reconstructed.** Firefox has no chain-end bit and puts
its redirect flag on the *opposite end* of the chain: the page redirected **to** carries
`redirect_permanent`. Dropping those types therefore discards landing pages too, by a
different route — the same inversion, arrived at from the other side. A visit nothing
redirects away from is the chain end, and that is reconstructible from `from_visit`. Tise
never runs on Firefox, so `shipped` there is not what any product saw; it is the same
*definition of a visit*, which is what a fold count compared across browsers needs in
order to mean anything.

**What it changed, including where it changed little.** Simulating both stages —
`analysis/import_simulation.py` — reproduces the real export to **1.5%** per-domain
disagreement, against the 7.7% D65 measured, and the residual 72 events is about one day
of browsing, which is how much older the file copy is than the export. But the effect on
the headline is small, and saying so is the point of measuring it:

| corpus | events, `chosen` → `shipped` | disagreement | model Brier | folds won |
|---|---|---:|---|---|
| Edge (primary) | 5,711 → 5,734 | 1.3% | 0.1119 → **0.1124** (worse) | 2 of 5, unchanged |
| Chrome | 5,012 → 5,068 | 6.5% | 0.2195 → **0.2099** (better) | 2 of 5 → 3 of 5 |
| Firefox | 909 → 910 | 3.4% | 0.2263 → **0.2298** (worse) | 4 of 5 → 3 of 5 |

Edge moves least because Edge has the fewest redirect chains — 3.8% of visits against
Chrome's 12.2%, which D40's own table said and nobody read that way. **The corpus fix did
not move the model in a consistent direction**: it helps on Chrome, hurts slightly on Edge
and Firefox, and the fold total is unchanged at **8 of 15**. D28's bar on Edge is identical
to four decimals (0.1254), the model still clears it there and still loses on Chrome.

**D60's conclusion survives the corpus it was computed on being wrong.** That is a weaker
result than a fix that rescued the model, and it is what the numbers say. It is worth
being plain about the shape of it: this entry corrects a real error in how the data was
read, and the error was not what was holding the model back.

`hoursSinceFirstSeen` still puts 76.8% of Edge test rows outside its fitted range. The
extrapolation lead is untouched and is still T16's next job.

**Found by breaking it, and it failed nothing.** Four deliberate breaks. Three failed
between four and seven tests. The fourth — making `load_events` drop the `view` it was
handed — failed **zero**, because `corpus.py` had no test file at all and every downstream
test builds its events in memory. That is the single most dangerous shape in this project:
the one door every published number comes through, able to silently substitute a different
corpus. Closed by `research/tests/test_corpus.py`; the same break now fails four.

This is the fourth time counting failures has found a hole rather than a bug — T10's
oracle-reading assertions, T11's untouched horizon boundary, T12's untested logit clamp,
now T13's early return and T16's missing door. A break that fails nothing is a finding
about the tests, and the only way to see it is to break one thing at a time and count.

**What this does not settle.** The chain-end filter is inferred from behaviour — 98.5%
against 8.7% on one corpus — not read out of Chromium's source. It is stated that way in
`analysis/import_simulation.py` under `KNOWN_DIVERGENCES`, and a browser probe that reads
`chrome.history.search()` results against the file directly would settle it. Nothing in the
extension changed on the strength of this: the import's behaviour was already right, and it
was the corpus that was describing something else.

### D79 — D78 got the conclusion right and the mechanism wrong, and reading the source found it

Akash asked whether I wanted to study the browser documentation before going further. The
answer should have been yes before D78 was written, not after.

D78 inferred Chromium's filter from behaviour: a 98.5%/8.7% split between chain-end visits
and everything else, on one corpus. That inference was **directionally right and
structurally wrong in two ways**, and both were found by reading `TransitionIsVisible` in
`components/history/core/browser/visit_database.cc` rather than by measuring harder.

**First: the rule has three terms, not one.**

```cpp
(ui::PAGE_TRANSITION_CHAIN_END & transition) != 0 &&
ui::PageTransitionIsMainFrame(page_transition) &&
!ui::PageTransitionCoreTypeIs(page_transition, ui::PAGE_TRANSITION_KEYWORD_GENERATED)
```

D78 had the first and omitted the other two. `KEYWORD_GENERATED` in particular is a term
no amount of measuring this corpus would have suggested.

**Second, and it matters more: the filter is per *page*, not per *visit*.** `search()`
selects URLs having at least one visible visit; `getVisits()` then returns **every** visit
of a selected URL, visible or not. D78 filtered visit-by-visit. Splitting the same corpus
by that distinction shows it immediately:

| non-chain-end visits | present in the real export |
|---|---:|
| on a page that also has a visible visit | **91.8%** (56 of 61) |
| on a page with no visible visit | **0.0%** (0 of 585) |

D78's headline 8.7% was the average of 91.8% and 0.0% — a real number describing two
populations that behave nothing alike. Averaging across a bimodal split and reading the
mean as a mechanism is the same error as D65's "totals agree, so the datasets agree",
one level up.

**The corrected model reproduces the shipped import almost exactly.** The simulation's
`redirect` skip count is now **49**, which is the exact figure D65 read off the real
import, and per-domain composition agrees to **0.6%** — against 1.5% under D78's mechanism
and 7.7% before any of this. The residual is about one day of browsing, which is how much
older the file copy is than the export.

| corpus | `chosen` | `shipped` (D79) | composition gap | model Brier | folds |
|---|---:|---:|---:|---|---|
| Edge (primary) | 5,711 | 5,755 | 1.5% | 0.1119 → **0.1124** | 2 of 5, unchanged |
| Chrome | 5,012 | 5,129 | 7.0% | 0.2195 → **0.2096** | 2 of 5 → 3 of 5 |
| Firefox | 909 | 915 | 3.9% | 0.2263 → **0.2219** | 4 of 5 → 3 of 5 |

Every benchmark re-run again. **The conclusion is unchanged for the third time**: 8 of 15
folds, D28's Edge bar identical to four decimals, clears on Edge and Firefox, loses on
Chrome. D60 has now survived two different corrections to the corpus it was computed on.

**Why the tests could not catch this, and why the first fix did not either.** Every fixture
gave each visit its own URL, so page-level and visit-level filtering are indistinguishable
on them — the suite would have passed either way. That is not a missing assertion but a
missing *case*: a fixture can be thorough about the trap it was written for and silent
about the one beside it.

The first replacement fixture **still failed to discriminate**, and only the break count
showed it. Reverting to per-visit filtering failed **zero** tests, because the hop I had
added was itself a chain end and therefore visible under either rule. The distinguishing
visit has to be one that is *not visible on its own*, on a page made visible by some other
visit — which is precisely the 61-visit population in the table above. `CHROME_MIXED_PAGE`
and `FIREFOX_MIXED_PAGE` now carry that case, plus a page that only ever starts a chain and
a keyword-generated page. The same two breaks now fail.

That is worth stating plainly: writing a test *for* a bug I had just diagnosed, with the
mechanism in front of me, I still wrote one that could not fail. Counting break failures
is not a flourish on top of the tests; on this occasion it was the only thing standing
between a real fix and a fix that merely looked tested.

**The general lesson, and the reason this entry exists at all.** D78 was arrived at by
exact measurement — a one-to-one join, no sampling, no inference from totals — and was
still wrong about *why*. Measurement establishes that something happens; it does not
establish the rule producing it, and a mechanism guessed from a strong correlation is still
a guess. The source was public and one fetch away the whole time.

**Superseded by this entry:** D78's `is_chain_end`-based filter and its statement that the
API "hands over chain ends only". `is_chain_end` remains as a bit test; `is_visible` is the
product-visible rule. D78's diagnosis of the original defect — that the research corpus
kept chain starts and discarded landing pages — stands.

### D80 — Confidence intervals, and the headline claim does not survive them

The bar was owed intervals since CHECKPOINT A: *"owed before any number reaches the README:
confidence intervals (T16)"*. They now exist, and the first thing they do is withdraw the
project's flagship claim.

**Every 95% interval on the paired Brier difference includes zero, on every corpus, under
both resampling units.**

| corpus | rows | bar − model | 95% (rows) | 95% (categories) | folds |
|---|---:|---:|---|---|---|
| Edge (primary) | 271 | +0.0130 | [−0.0071, +0.0319] | [−0.0138, +0.0397] | 2 of 5, p=0.81 |
| Chrome | 141 | −0.0133 | [−0.0438, +0.0163] | [−0.0608, +0.0156] | 2 of 5, p=0.81 |
| Firefox | 83 | +0.0259 | [−0.0302, +0.0837] | [−0.0220, +0.1865] | 3 of 5, p=0.50 |

So **D28's bar has not been shown to be cleared on Edge**, and — symmetrically — the model
has **not been shown to lose on Chrome** either. D60's headline, repeated through D78 and
D79, was a point estimate inside an interval containing zero. `model.md` now leads with
that, computed from the intervals rather than written down.

**This also retires a smaller embarrassment.** Across this session I reported Edge moving
0.1119 → 0.1124 → 0.1124 and called it "worse" twice. The interval half-width there is
about 0.02. I was narrating differences forty times smaller than the resolution of the
measurement, in an append-only decision log, as though they were findings. They were not
findings; they were the fourth decimal place of a noisy estimate.

**Method.** The comparison is **paired**: both models score the same rows, so the estimand
is the per-row difference in squared error, not two independently estimated Brier scores.
Checking whether two separate intervals overlap is a weaker and frequently wrong test —
overlapping intervals are entirely compatible with a difference that reliably excludes zero.

**Two resampling units, both published.** Resampling rows assumes labels are independent.
They are not: all of them come from about twelve categories, and sessions within a category
share whatever makes that category predictable. Resampling **categories** respects that and
is the bound a claim about *the model* has to survive. Reporting only the row interval
would have been the flattering choice and, on Edge, would still not have cleared zero.

**The fold counts were never evidence.** A model with no skill wins each fold with
probability one half, so "wins 2 of 5" happens **81%** of the time by chance and even a
clean sweep of 5 is 0.031. With five folds the count cannot be convincing in either
direction — which retrospectively means D60's most-quoted caveat, "wins only 2 of 5 folds",
was as unfounded as the Brier score it was cautioning against.

**How far off is decisive?** Roughly **1,151 test rows on Edge against the 271 there** —
about four times the data, and only if the point estimate survives collecting it. That is
worth contrasting with D70, where certifying the abstention target needed >12,800 answered
rows: this gap is reachable, that one was not. Neither number is a promise; both are
statements about how far the evidence is from being decisive.

**A seed, declared.** `BOOTSTRAP_SEED = 20260828`, committed and never tuned. The optimiser
deliberately has none (D54) because it must be reproducible in a browser; here randomness
*is* the method, and a fixed seed is what makes a published interval regenerable. A test
asserts the bounds move by less than 0.01 across other seeds, so the seed is an
implementation detail rather than a choice shaping a number.

**Found by breaking it, in the fixture again.** The first version of `test_intervals.py`
used probabilities of 0.9 and 0.1 throughout, which makes every row's paired difference
exactly 0.24 — zero variance. The bootstrap correctly returned a zero-width interval and
two tests failed on it. A fixture with no spread cannot exercise anything that estimates
spread, which is the same lesson as D79's fixture, one domain over.

**What this does not say.** Not that the model is worthless, and not that it equals the
baseline. It says this much of one person's browsing cannot separate them, which is a
statement about the evidence rather than about the model. The honest position for the
README, T18 and any published claim is: **`logreg_fs2` is not yet distinguishable from a
table of per-category base rates.**

### D81 — Pre-registering the feature transform, before any number about it exists

T16 requires that the fix for the cumulative-feature problem be **chosen without looking at
the fold scores**, or it is fitted to the test set. That constraint is unenforceable after
the fact: nobody can prove which numbers were on screen when a decision was made. So this
entry is committed *before* the replacement features are implemented, and the result gets
its own entry afterwards. Git holds the order.

**The diagnosis, restated from what is already published.** `model.md` reports the share of
test rows whose feature value falls outside the range the coefficients were fitted on. On
Edge: `hoursSinceFirstSeen` **76.8%**, `priorSessionCount` **42.1%**. On Chrome, 67.5% and
24.2%. Both features can only ever increase, so in an expanding-window backtest every test
row sits later in the calendar than every training row and the feature works as an index of
which fold you are in.

**The argument for changing them does not depend on any score.** `hoursSinceFirstSeen` and
`priorSessionCount` are not properties of how a person behaves. They are properties of
**when observation started**. Two people with identical habits, one of whom installed Tise a
year earlier, produce different values for both. Tise ships to individuals whose install
date is arbitrary and whose history import reaches back an arbitrary distance — D64 found a
90-day import returning 57 days, because that profile had nothing older. A coefficient
learned against the author's install date transfers to nobody, and drifts for the author
too, every day. That is a reason to replace them even if it made every published number
worse, and it is the reason being acted on.

**The rule being applied: replace a feature that grows with the calendar by a bounded one.**
Boundedness makes a large excursion beyond the fitted range *structurally impossible* rather
than merely unlikely.

1. `hoursSinceFirstSeen` → **`firstSeenSaturation`** = `h / (h + 168)`, in [0, 1).
   The scale is **168 hours = 7 days**, taken from the 7-day windows already in `fs_2`, so
   the feature set carries one notion of "recent" rather than two. The signal it keeps is
   the real one: the difference between a category first seen yesterday and one first seen
   a month ago is large, and the difference between 300 days and 330 days is nothing.
2. `priorSessionCount` → **`priorSessionRate`** = sessions per observed day, saturated:
   `r / (r + 1)` where `r = resolved_prior_sessions / max(observed_days, 1)`. The scale is
   **one session per day**, the natural unit of a daily habit. This is the behavioural
   quantity the raw count was standing in for — how often, not how many since install.

**Deliberately not touched:** `eventCount7d`, `eventCount30d`, `sessionCount7d`,
`sessionEventCount`, `sessionCategoryCount`, `categoryEventsInSession`. These are unbounded
counts and some show excursions too, but they are **windowed** — they rise and fall, and do
not index the calendar. `eventCount30d`'s excursion has a different cause (early history is
shorter than the window and fills in) and it self-corrects. Fixing what was not diagnosed
would make the result unattributable.

This becomes **`fs_3`**. `fs_2` is kept and benchmarked on identical folds, because a
replacement that cannot be compared against what it replaced is not a measurement. `fs_2`
remains what the extension ships until this is decided.

**Predictions, recorded now.**

1. **The share of test rows outside the fitted range will *not* fall to zero for the two
   replaced features, and that is expected.** A bounded feature still has an observed
   training range narrower than [0, 1) — `priorReturnRate` is already bounded and still
   shows 13.2% outside. Share-outside is therefore the wrong mechanism metric.
2. **The right metric is the size of the excursion, not its frequency**: how far beyond the
   training range a test value lands, in units of the training range's own width. For a
   feature bounded in [0, 1) this cannot exceed 1/width; for an unbounded counter it has no
   limit. **Prediction: the maximum relative excursion for the two replaced features falls
   substantially. This is the mechanism claim and the one that can fail cleanly.**
3. **Prediction: `fs_3` will not be distinguishable from `fs_2` by interval.** D80 showed
   271 Edge test rows cannot separate a Brier difference of 0.013 from zero; there is no
   reason a feature swap would clear a bar the model itself could not.

**The adoption rule, fixed now so it cannot be chosen to fit the outcome.** Adopt `fs_3` if
**both**:

- the maximum relative excursion for the two replaced features falls, prediction 2; **and**
- the paired interval on `fs_3` versus `fs_2` **does not exclude zero in `fs_2`'s favour** —
  that is, `fs_3` is not shown to be worse.

Adoption is therefore on the **argument plus the mechanism**, with the score acting only as
a veto. It is explicitly **not** conditional on `fs_3` scoring better, because D80 
established that this corpus cannot demonstrate "better" for a difference of this size, and
a rule requiring it would be a rule that can never fire honestly. If `fs_3` scores worse by
point estimate while its interval includes zero, it is still adopted, and that sentence is
written here rather than after the fact.

### D82 — The transform works, and the prediction I got wrong is the useful part

D81 was committed before `fs_3` existed. Three predictions were recorded there. Two held
and one was wrong, and the wrong one taught more than the two that held.

**Prediction 1 — the share of out-of-range rows would not fall. Held, exactly.**

For `firstSeenSaturation` the share is not merely similar but **identical to the digit**:
67.5% on Chrome, 76.8% on Edge, 75.0% on Firefox, before and after. That is a mathematical
certainty rather than a coincidence — saturation is strictly monotone, so it preserves
ordering, so precisely the same rows fall outside precisely the same rank boundaries. Share
-outside was *incapable* of detecting this change. Had the mechanism metric not been fixed
in advance, the obvious table would have shown a transform doing nothing at all.

`priorSessionRate` is not a monotone transform of `priorSessionCount` — it divides by
observed days — so its share did move, 24.2% → 4.1% on Chrome and 30.8% → 1.9% on Firefox.

**Prediction 2 — the size of the excursion would fall. Held, on every corpus.**

Worst excursion, in units of the training range's own width:

| corpus | `hoursSinceFirstSeen` → `firstSeenSaturation` | `priorSessionCount` → `priorSessionRate` |
|---|---|---|
| Chrome | 0.25 → **0.03** | 0.33 → **0.04** |
| Edge | 0.12 → **0.01** | 0.42 → **0.10** |
| Firefox | 0.55 → **0.11** | 0.36 → **0.02** |

The other twelve features are unchanged, and `feature-transform.md` prints them so that is
checkable rather than asserted.

**Prediction 3 — `fs_3` would not be distinguishable from `fs_2`. Wrong on two corpora.**

| corpus | `fs_2` − `fs_3`, positive favours `fs_3` | 95% (categories) | |
|---|---:|---|---|
| Chrome | +0.0072 | [+0.0032, +0.0179] | **excludes zero** |
| Edge | −0.0006 | [−0.0083, +0.0024] | includes zero |
| Firefox | +0.0088 | [+0.0028, +0.0232] | **excludes zero** |

**This is the first established result in the project** — the first interval that excludes
zero — and it arrived against my own recorded prediction, which is the only reason it is
worth much.

**Why this does not contradict D80, and the lesson.** D80 found that 141 Chrome test rows
could not separate the model from `category_base_rate`. The *same 141 rows* separate `fs_2`
from `fs_3` comfortably. Nothing about the sample changed; the **comparison** changed.
`fs_2` and `fs_3` share twelve of fourteen features, so the two models make almost the same
error on almost every row, the paired differences are small and tightly concentrated, and
the standard error of their mean is correspondingly tiny. Against a structurally different
predictor the paired differences are large and scattered, and the same rows buy far less.

**An interval's width is a property of the comparison, not just of the sample size.** D80's
">12,800 rows" and "1,151 rows" are answers to the questions those comparisons asked, and
neither is a general statement about what this corpus can resolve. That is the correction
this entry makes to a natural misreading of D80 — including one I was about to make, since
prediction 3 was exactly that misreading written down in advance.

**Two things this result is not.** The intervals are 95% and three corpora were tested, so
roughly a one-in-seven chance of at least one spurious exclusion; two exclusions in the same
direction is a good deal stronger than one, and it is still three corpora from one person.
And the improvement is **not demonstrated on Edge**, which is the primary corpus (D20) and
where the point estimate very slightly favours `fs_2`. "Better on two of three, undecided on
the one that matters most" is the honest summary.

**The adoption rule fires: `fs_3` is adopted.** D81 required the mechanism to improve and
the score not to be worse; the mechanism improved everywhere and the score is better on two
corpora and undecided on the third. Adoption was never conditional on beating `fs_2`, and it
is worth noting that had prediction 3 held, `fs_3` would have been adopted anyway on the
argument alone — which is exactly why the rule was fixed in advance.

**Found by breaking it: three of five breaks failed nothing, and one was a real bug.**

- **`Preprocessor.transform` did not check the feature set, and could not have.** `fs_2` and
  `fs_3` both produce eighteen columns, so `zip(strict=True)` passes and an `fs_2` row
  transforms cleanly through an `fs_3` preprocessor — every coefficient after the first
  differing column applied to the wrong feature, silently, with no error anywhere. The
  widths matching is exactly what made `fs_3` a clean in-place replacement, and it is what
  removed the only guard that existed. `Preprocessor` now carries its feature set.
- **Nothing fitted a model on `fs_3` rows at all.** The features had tests; the machinery
  turning them into a design matrix did not, so breaking the nullable-list lookup and the
  mixed-set guard both failed zero tests.
- **A test named for the one-day floor did not exercise the floor**, and its own comment
  said so — "the floor is not what is binding here" — which I wrote and did not act on.
  Removing the floor failed nothing. Investigating why produced a small result worth
  keeping: **at the default 24-hour horizon the floor is unreachable**, because a prior
  session only counts once `session_end + horizon <= window_end`, so a day has always
  elapsed by the time the count is non-zero. It is a guard for short horizons, now tested
  with one, and a second test pins that it cannot bind at the default.

That is the sixth, seventh and eighth hole this method has found. The recurring shape is
now clear enough to name: **the tests follow the code that was interesting to write.** The
features were interesting, so they were tested; the plumbing that carries them was not.

**What adoption still needs, and has not had.** `fs_2` remains what the extension ships.
Making `fs_3` the shipped set changes the `FeatureRow` schema, which is on the ask-first
list, and it requires the TypeScript mirror, a regenerated parity oracle, and every
benchmark re-run on `fs_3`. None of that is done here. The research tier computes both sets;
the product still computes one.

### D83 — Shipping `fs_3`, and the migration that keeps D11's promise across a version bump

Akash authorised the schema change. `fs_3` is now what the extension computes, stores and
trains on, in both languages.

**The thing that nearly went wrong.** Training filters stored rows to the current feature
set, and `refreshDataset` can only recompute a row if the events behind it still exist. Raw
events expire after thirty days; derived rows do not, and that asymmetry **is** the privacy
design (D11) — a person keeps the model learned from their browsing without keeping the
browsing. So a naive version bump would have stranded every row older than the retention
window in `fs_2`, silently, and restarted the model from the last month of browsing. Nothing
would have reported it: a smaller training set is not an error, it is just quietly worse.

**Why a migration is possible here.** `fs_3`'s two features are pure arithmetic transforms
of values `fs_2` already stored:

    firstSeenSaturation = h / (h + 168)                     from hoursSinceFirstSeen
    priorSessionRate    = r / (r + 1),  r = c / max(h/24,1) from both stored values

So the conversion needs no events at all, and `migrate.test.ts` asserts the strong form
rather than the convenient one: a migrated row is **identical** to the row `computeFeatures`
would have written, checked across every label of a fortnight's corpus. Anything less would
mean training on two subtly different definitions of one feature.

That this works is luck the design earned rather than luck it was handed — D81 made the two
features transforms of existing ones for simplicity, and this is the second thing that
choice bought after `feature_transform.py`'s single-pass comparison.

**It runs inside `refreshDataset`**, which is the one function every path into the dataset
passes through. Hooking the two callers instead would mean remembering at every future call
site, and the failure would be silent. Same reasoning as D72 hooking `saveSettings`.

**Old rows are kept.** They are the only record of what the previous model was trained on,
they cost little, and deleting them would make the migration irreversible for no gain. A
recomputed `fs_3` row is never overwritten by a migrated one: rows built from events are
authoritative over arithmetic on older rows.

**The evidence line survives, by inverting the transform.** `prediction.ts` said "returned
within a day after 70% of the last 40 sessions", and the count that qualifies the rate is no
longer a feature. Saturation is invertible, so `priorSessionsFrom` recovers it exactly —
this is arithmetic on values the row already holds, not a reconstruction, and a test checks
the round-trip at several ages and counts. The qualification matters: a rate built on two
sessions has to read differently from one built on forty, or the evidence overstates itself.

**The parity suite bit, which is the whole reason it exists.** Changing TypeScript to `fs_3`
against an `fs_2` oracle failed 15 tests immediately. Regenerating the oracle moved exactly
the sections it should — `featureNames`, `featureSet`, `features`, `model` — and left
`labels`, `sessions`, `resolutions` and `summary` byte-identical, which is checkable
evidence that the change did what it claimed and nothing else.

**What shipped `fs_3` scores.** Still nothing distinguishable from the bar, as expected —
D82's improvement was `fs_3` over `fs_2`, not over `category_base_rate`:

| corpus | Brier, `fs_2` → `fs_3` | vs bar, 95% (categories) | folds |
|---|---|---|---|
| Chrome | 0.2096 → 0.2024 | −0.0060 [−0.0466, +0.0230] | 3 of 5 |
| Edge | 0.1124 → 0.1129 | +0.0124 [−0.0210, +0.0410] | 3 of 5 |
| Firefox | 0.2219 → 0.2131 | +0.0347 [−0.0119, +0.2049] | 4 of 5 |

Fold wins go from 8 of 15 to **10 of 15**. Every interval still includes zero, so the
headline is unchanged and remains the honest one.

**Calibration moved in two directions and is reported both ways.** `fs_3` is markedly better
calibrated *before* Platt — Edge ECE 0.1803 → **0.1144**, Firefox 0.2480 → **0.1774** — and
the Platt step then has less to do. After calibration Edge improves slightly (0.0706 →
0.0678) while Chrome and Firefox get worse (0.1030 → 0.1133, 0.1066 → 0.1592). There are no
intervals on ECE, so none of that is established, and it is recorded rather than explained.

**A warning for the next feature set, which is the durable part of this entry.** This
migration works because these particular features were derivable from stored ones. **A
future feature needing anything not already in the row cannot be migrated this way**, and
the honest options there are to recompute what the retention window still covers and say
plainly what was lost. Post-launch that would silently reset every user's long-term training
history. **The feature set should be frozen before the Web Store listing**, and if it is
ever changed afterwards the release notes have to say what it costs.

**Found by breaking it.** Four breaks, two of which initially failed nothing: migration
overwriting freshly computed rows, and `refreshDataset` no longer migrating at all. The
second was a genuine hole — nothing tested the choke point — and is now covered by two
tests, including one asserting migration happens *with no events at all*, which is the case
the whole mechanism exists for.

**A methodology note, because it produced a false reading.** The first was not a hole: a
shell-escaping accident in the break command had written NUL bytes into two template
literals instead of applying the edit, so the "break" never applied and the suite passed for
the wrong reason. Both occurrences were corrupted identically, so the key still matched
itself and nothing failed. **A break that appears to fail nothing must be confirmed to have
actually applied** — otherwise the technique reports a hole in the tests when the truth is a
hole in the tooling.

### D84 — Pre-registering the tournament, before the challenger exists

T16's last deliverable is the XGBoost-versus-shipped gap. It needs pre-registering for a
reason that is the *mirror* of D81's, not a repeat of it. D81's risk was choosing a fix
after seeing the scores. Here the scores are not the free parameter — **the challenger's
strength is**, and I control it.

XGBoost has dozens of hyperparameters. Tune them and report the best configuration, and
the published gap is a maximum over many draws; on the 271 Edge test rows that maximum is
mostly noise. Leave them at library defaults against training windows of **201 to 441
rows** (`model.md`, Edge), and the challenger overfits, loses, and the shipped model wins
against an opponent I quietly weakened. **Both failures produce a table indistinguishable
from an honest one**, which is exactly the situation pre-registration exists for.

**What this tournament can and cannot decide, stated before the result.** The extension
trains in the browser, with a hand-written optimiser (D54) and one runtime dependency.
XGBoost cannot ship at any score. So this is **not a model selection.** It measures what
the shipping constraint costs, expressed as an interval. Writing that down now stops the
result being written up afterwards as though a decision hung on it.

**The challenger.** `xgboost`, pinned, in the research tier's **dev group only** — the
tier whose `pyproject.toml` already says it "runs on the author's machine only; never
shipped". It never enters the parity contract, has no TypeScript twin, and every table it
appears in labels it research-only. Two configurations, both declared now, neither searched:

1. **`xgb_small` — the primary.** `max_depth=3`, `n_estimators=100`, `learning_rate=0.05`,
   `subsample=0.8`, `colsample_bytree=0.8`, `min_child_weight=5`, `reg_lambda=1.0`.
   Library defaults assume ~10⁵ rows; these folds train on a few hundred. Depth 3 with
   `min_child_weight=5` is the ordinary small-data posture — every leaf holds at least 5 of
   ~300 rows. It is primary because it is the **stronger** challenger by argument, and the
   shipped model should face the best opponent I can specify without searching for one.
2. **`xgb_default` — secondary.** Library defaults, untouched: what a reviewer gets out of
   the box. Reported so that a loss cannot be blamed on my configuring XGBoost badly, nor a
   win credited to my configuring it well.

**No hyperparameter search will be run in T16.** If one ever is, it gets its own entry
saying so, and every number after it is a number from a search.

**Determinism.** `random_state=0`, `n_jobs=1`, `tree_method="exact"`, and the resolved
library version printed in the report. SPEC.md invariant 3 wants a committed script behind
every number; a number that moves between runs of that script does not satisfy it.

**One deliberate asymmetry, named now rather than discovered later.** The challenger is
fitted through the same `extra_models` hook, on the same `Fold` objects, from the same
`fs_3` `FeatureIndex` — so the rows are identical. But it is given **nulls as `NaN` and
uses XGBoost's own missing-direction learning**, rather than the mean-imputation in
`prep.py` that the linear model needs. Standardisation would have been neutral (tree splits
are invariant to a monotone per-column transform); imputation is not. The fair challenger is
the one a competent practitioner would build, and they would pass `NaN`. The consequence is
registered too: **any gap measured here includes whatever the better missing handling is
worth**, and the report prints the null counts so a reader can judge how much of it that
could be.

**Predictions, recorded now.**

1. **`xgb_default` scores worse than the shipped model on at least one corpus** by point
   estimate, from overfitting a few hundred rows with depth-6 trees.
2. **`xgb_small` beats the shipped model on at least one corpus** by point estimate. Trees
   split on the category directly and can represent interactions that 18 linear columns
   cannot.
3. **No paired interval between `xgb_small` and the shipped model excludes zero on Edge.**
   This one is stated carefully rather than by reflex, because D82 caught the reflex out:
   interval width is a property of the comparison, and `fs_2` versus `fs_3` separated easily
   *because* they shared 12 of 14 features and their per-row differences were tiny. A tree
   ensemble and a linear fit share no structure, so their per-row differences should be
   large and variable and the interval wide. **This is the prediction most likely to be
   wrong, and the one worth being wrong about.**

**The adoption rule, fixed now.**

- Whatever the result, **`logreg_fs3` remains what ships.** There is no outcome of this
  tournament that changes the extension in T16.
- The result opens a follow-up task **only if** `xgb_small`'s paired interval against the
  shipped model excludes zero **in the challenger's favour, under the subject-cluster unit,
  on Edge**. Point estimates do not qualify, and fold counts especially do not — D80 settled
  that they were never evidence.
- If it fires, the follow-up is scoped as *investigate a shippable nonlinear model* and
  nothing further. A shallow tree is a sequence of comparisons and could in principle be
  written in TypeScript; a win here would be evidence worth costing, not a mandate.
- **The number reported as "the gap" is the interval, not the point estimate.**

**The failure case, chosen by rule so it cannot be shopped for.** T16 also owes one
documented failure. It is the single pooled Edge test row with the **largest squared error**
from the shipped model, `unknown` excluded: its category, its feature vector, the
probability given, the outcome, and the evidence line the UI would have shown. Selected by
`max`, not by hunting for a good story — and if the worst row turns out to be dull, the dull
one is what gets published.

### D85 — The tournament: every prediction held, and the width ladder is the real finding

D84 registered three predictions and an adoption rule before any of this code existed.
`docs/benchmarks/tournament.md` has the tables; this is what they mean.

**Prediction 1 held, harder than predicted.** `xgb_default` scores worse than the shipped
model on **all three** corpora, not the one the prediction asked for: Chrome 0.2256 against
0.2024, Edge 0.1287 against 0.1129, Firefox 0.2437 against 0.2131. Out of the box it also
loses to `category_base_rate` on Chrome and Firefox, and on Chrome it loses to
`global_base_rate` — **a constant beats it**. That is the whole reason `xgb_small` is the
primary and this one is the reference: reported alone, this row would have been a straw man
dressed as a result.

**Prediction 2 held, and only just.** `xgb_small` beats the shipped model on exactly one
corpus — Edge, 0.1084 against 0.1129 — and loses on Chrome (0.2141 against 0.2024) and
Firefox (0.2260 against 0.2131). Point estimates favour what ships, 2 corpora to 1.

**Prediction 3 held.** `xgb_small` against the shipped model on Edge, subject-clustered:
**+0.0045 [−0.0082, +0.0362]**. Rows: +0.0045 [−0.0086, +0.0187]. Both include zero, as do
all twelve intervals on the page.

**The adoption rule does not fire, on any corpus, for either challenger.** `logreg_fs3`
remains what ships — which D84 fixed in advance, so nothing about that was contingent.

**What this licenses, and what it does not.** Not "the shipped model is as good as
XGBoost". The claim is "271 test rows cannot tell them apart" — D80's finding about the
model and its bar, reached again one level up. The sentence that can go in the README is
that the in-browser constraint has **not been shown to cost anything measurable on this
data**: weaker than "costs nothing", stronger than silence.

**The finding I did not predict.** D82 argued that an interval's width is a property of the
comparison rather than of the sample, correcting a natural misreading of D80. That was an
argument. The tournament makes it a measurement, because three comparisons now run over the
**same 271 Edge rows**, in the same unit, from one backtest:

| Shipped model against | What they share | Point | 95% width |
|---|---|---:|---:|
| `logreg_fs2` | 12 of 14 features | +0.0006 | **0.0060** |
| `xgb_small` | all 18 input columns, different model class | +0.0045 | **0.0273** |
| `category_base_rate` | nothing but the category | −0.0124 | **0.0404** |

**Monotone in shared structure, a factor of 6.7 end to end, with the sample held exactly
fixed.** Sample size explains none of it. `fs_2` versus `fs_3` differs from the bar
comparison by more than the bar comparison differs from zero.

It also confirms the *mechanism* registered for prediction 3, not only its conclusion. The
prediction was that the interval would be too wide to exclude zero, and it is: at the
narrowest rung's width a point estimate of +0.0045 would have sat clear of zero, and at
0.0273 it does not. The reasoning that produced the prediction is the reasoning the data
supports — which is worth recording precisely because D79 and D82 are entries where it was
not.

**The documented failure, chosen by `max` as registered.** Edge, category `video`, window
ending Saturday 2026-08-08. Every feature that could say *this continues* was at its
ceiling: 373 events in 7 days, seen on all 7 of them, 27 sessions, 51.5% of all 30-day
activity, prior return rate 89.3%, and last seen **four minutes** before the window closed.
Tise said **99.1%**. The person did not come back. Squared error **0.9831** out of a
possible 1.0000.

The interesting part is what the feature set cannot say. The thing that appears to have
happened is a weekend, and `dayOfWeek` sits in `fs_3` as a plain integer — deliberately, per
`return_model.py`, until a cyclic encoding is measured rather than assumed — so a single
linear coefficient must express "Saturday" as being five-sevenths of the way from Monday to
Sunday. **This is a missing feature, not a calibration failure**, and Platt cannot reach it.
It would not have been displayed: D70 found Tise abstains from everything on this data. That
is the abstention machinery working, though it is not evidence about *this* row — a model
that abstains from everything abstains from the good ones too.

**The asymmetry D84 registered turns out to be negligible where it mattered.** The
challenger gets native missing handling and the shipped model gets mean imputation, so any
gap could have been partly that. On Edge only **0.4%** of pooled rows carry a null
(`priorReturnRate`); Chrome 1.4%, Firefox 3.6%. It cannot account for the Edge difference.

**Dependencies:** `xgboost` 3.4.1 and `scikit-learn` 1.9.0, **dev group only** — the research
tier that `pyproject.toml` already declares is never shipped. No TypeScript twin, not in the
parity contract, and every table labels them research-only. Both authorised by Akash;
scikit-learn is required by `XGBClassifier`, and D84 had already committed to "library
defaults, what a reviewer gets out of the box", which is that wrapper.

**Two latent bugs found on the way, neither affecting a published number.** `model.md` named
`fs_2` throughout after D83 shipped `fs_3` — string literals in the report writer where the
figures beside them were dynamic — and `model_report.py` had **no test file at all**, the
same hole D78 found in `corpus.py`, in the one file every claim about the model passes
through. Separately, `backtest.py --with-model` passed `--view` to `load_labels` but not to
`load_events`, so a non-default view would have labelled from one corpus and computed
features from another; the default path is unaffected, which is why nothing published was
built that way.

### D86 — D85 explained the failure case with a story, and the story is wrong

D85 documented the shipped model's worst row and then explained it: *"The thing that appears
to have happened is a weekend."* That sentence was never measured. `analysis/day_of_week.py`
measures it, and it is wrong.

**On Edge — the corpus that row came from — Saturday returns at 74.6% against a 71.6%
overall rate.** It is an *above*-average day, +3.0 points. The failure happened on one of
the better days for returning, not a worse one. Saturday is not consistently anything
either: Chrome −9.0 points, Firefox −7.3, Edge +3.0. There is no weekend effect here to
point at.

**How this got written.** It is the failure SPEC.md invariant 3 exists to prevent, wearing
prose. The invariant is habitually read as being about figures — do not publish a number a
committed script did not produce — and a *causal claim* with no number behind it is the same
defect: a plausible narrative attached to a single row, in the entry that documents that row.
Nothing failed, because prose fails nothing. This is the fourth time in the project that the
break-it discipline's blind spot has been the same one: **it only protects claims that are
code.** D78 and D79 were mechanisms inferred rather than read; this is an explanation
invented rather than measured.

**What survives is better than what it replaced.** The pattern is real, substantial, and
**non-monotone on all three corpora**:

| Corpus | Highest | Lowest | Spread |
|---|---|---|---:|
| history-chrome | Friday 81.4% | Sunday 52.2% | **29.2 points** |
| history-edge | Monday 79.5% | Sunday 58.5% | **21.1 points** |
| history-firefox | Wednesday 76.2% | Saturday 57.7% | **18.5 points** |

The peaks disagree across corpora and none of the three orderings rises or falls with the
calendar. `dayOfWeek` enters `fs_3` as a plain integer 0–6 carrying **one linear
coefficient**, and no such coefficient can represent a non-monotone pattern in either
direction. So D85's conclusion — *a mis-encoded feature, not a calibration failure, and
Platt cannot reach it* — **holds, for a measured reason instead of a story.** The claim
survived; the argument for it did not, and the replacement is the stronger one.

**This changes nothing and is not a decision to add cyclic encoding.** `return_model.py`
states the position: that change is made against a measured number with the plain version
beside it, or it is tuning against an intuition. This is the measurement. Two things should
be weighed before anyone acts on it — and neither is settled here:

- T16 recorded that the feature set should be **frozen before the Web Store listing**, and
  adding a feature now runs against that. But a `sin`/`cos` pair over `dayOfWeek` is
  arithmetic on a value already stored in every `FeatureRow`, so it is **losslessly
  migratable exactly as `fs_3` was** — it is in the cheap class, not the expensive one.
- D80's finding applies to it as much as to anything else: a 21-point spread in base rate is
  not a promise of a 21-point improvement in Brier, and any `fs_4` would need pre-registering
  the way D81 did before a single fold was scored.

**A second, smaller caveat on D85, recorded here rather than left implicit.** The width
ladder was **not pre-registered**. It was built after the intervals were seen, so it does not
have the standing of the three predictions above it in that entry and should not be read
beside them as though it did. What it has instead is replication: it was constructed on Edge
and the generator computes it independently on the other two, where it is **monotone as
well** — factors of 3.0 on Chrome, 6.7 on Edge, 5.4 on Firefox. A post-hoc pattern that
holds on two corpora it was not built from is worth more than one that does not, and still
less than one that was predicted.

### D87 — The third stale label, and this time the test was holding it in place

`predict.ts` wrote `modelName: "logreg_fs2"` onto every prediction it stored, while the
`featureSet` field on the line below it derived `fs_3` from the constant. Since D83 every
stored prediction has named one feature set and recorded another. The probability was
right; the record of what produced it was a version behind.

That is the same defect as D86's `model.md` titles, in a worse place — a report is
regenerated, a stored record is not. It is now fixed at the source: `modelName(featureSet)`
in `train.ts` mirrors `model_name` in `return_model.py`, and `MODEL_NAME` follows
`FEATURE_SET`. **`replaceAll`, not `replace`** — Python's `str.replace` takes every
occurrence and JavaScript's takes only the first, so a set named `fs_3_b` would have
produced two different names in the two languages. The parity suite would not have caught
it: a model's display name is not a feature and is not in the oracle.

**The new part, and the reason this gets its own entry.** D78 and D86 were failures of
*absence* — `corpus.py` had no test file, `model_report.py` had no test file. This one had a
test. `registry.test.ts` asserted `expect(stored.modelName).toBe("logreg_fs2")` **and
passed**, three lines above an assertion that derived `featureSet` dynamically. The test was
not missing the bug; it was **pinning it in place**, and it would have gone on doing so
through every future feature set. A test that hardcodes the value it is guarding converts a
bug into a specification.

So the guard added is not another value assertion. `tests/model-name.test.ts` checks the
**shape of the code**: no source file may contain a quoted `logreg_*` name at all, comments
excepted. A value test passes again the moment someone writes a literal that happens to be
current; this one cannot. The break was confirmed applied before it was believed — the
literal was verified present in `predict.ts` by grep, then failed exactly one test.

The registry test keeps its assertion but gains the one that was missing:
`modelName === modelName(featureSet)`, the **pairing** rather than either half. Neither
field alone could ever have revealed the contradiction.

**No migration is needed, and that is luck rather than design.** The `fs_3` build has not
yet been loaded on the real profile — that is the check still owed from D83 — so every
prediction stored there dates from the `fs_2` era and its `modelName` is correct. Had the
owed check been done promptly, this bug would have written wrong labels into real records
first. The lesson is not that the delay helped; it is that a stale literal on a **stored**
field has a blast radius a report does not, and the two should not have been treated as the
same severity when the first one was found.

---

## The target changes

### D88 — Retiring `return_24h`: the model was fine, the question was wrong

Everything from D15 to D87 evaluated one target: *given activity in topic X, will the
person return to X within 24 hours?* It is being retired as the product target. Akash's
diagnosis, in his words: **"Average user does not care the prediction for a session."**

**This is not a model failure, and it matters that it is recorded as something else.** D80
found the model indistinguishable from a table of per-category base rates. D70 found it
abstains from everything. Those were treated as evidence about the *model* — more data, a
better transform, a stronger challenger. D85's tournament closed off the last of those:
XGBoost cannot separate itself from a hand-written logistic regression either. The
consistent reading across all three is that **the target carries little to predict**, and
no model was going to fix that.

Two root causes, both structural:

1. **A base rate of 65-72% is nearly all of the answer.** Always saying "yes" is already
   ~70% right, `category_base_rate` reaches Brier 0.1254, and the 90% abstention target is
   almost free to reach and nearly impossible to beat. Most of every label's information is
   spent re-establishing what was already known.
2. **A session is not a unit a person cares about.** Tise computes 6-7 predictions a day
   and shows none. Even answered, "you may revisit `video` within 24 hours" is not
   information anyone acts on.

**`return_24h` is retired as the product target and kept as research.** D15-D87, every
report in `docs/benchmarks/`, and the intervals all stand as a recorded, superseded result.
They are the evidence trail that justifies this change; deleting them would remove the
reason for it. The prediction, resolution and registry machinery is reused rather than
rewritten — D72's `expired` rule, D73's pure resolution, D74's stored abstentions and D76's
export all carry over unchanged.

### The new target — `block_volume`

> Will this category's activity in the next block be **above that category's own trailing
> median** for blocks of that type?

- **Blocks:** `weekday` (Mon-Fri) and `weekend` (Sat-Sun), **fixed** for V1. Learned
  per-person blocks stay on the roadmap — Chrome peaks on Friday at 81.4%, so there is
  evidence for them, but they need many weeks before stabilising and make cold start worse.
- **The loop:** Friday night predicts the weekend; Sunday night predicts the week.
- **Resolves itself** at block end. D6 survives intact — still no confirmation button.

**The load-bearing property is that a median split has a base rate of 50% by construction,
for every user, whatever their habits.** That is the direct answer to cause 1 above. It also
transfers: `return_24h` silently inherited *this author's* 70% base rate as a premise, and
someone browsing very differently would have received a target that was near-saturated or
near-empty with nothing in the design noticing. A median is computed from whoever is using
it. This is D81's argument — replace what encodes the observer with what encodes the
behaviour — applied to the target rather than to a feature.

**The known flaw, recorded now rather than discovered later.** The 50% guarantee holds only
where the trailing median is above zero. A category appearing in 2 of the last 10 weekends
has a median of 0, "more than 0" collapses back to "will it appear at all", and the base
rate goes with it. So a category qualifies for a volume card only if it appeared in **at
least half** the prior blocks; everything rarer is routed to the dormancy card instead,
where "is this finished?" is the better question anyway.

### Abstention is replaced, not weakened

D69 and D70's machinery — Wilson lower bound, certify or stay silent — is retired with the
target it was built for. It is replaced by: **always show the probability, always show its
denominator.**

> **Shopping this weekend - 71%** — *11 of your last 15 weekends.*

One floor remains: a category needs a minimum number of prior blocks before it appears at
all. Thin evidence becomes **visible** rather than being hidden behind silence, which is
what D70's rule amounted to in practice. Percentages are whole numbers; a decimal place
implies 1-in-1000 resolution from fifteen observations.

### Categories must be learned, not only looked up

`unknown` holds **79 labels at 92.5% positive on Chrome** — roughly a fifth of all labels,
discarded from every published number because a bucket called "unknown" is unpresentable.
It is large *by design*: the shipped map excludes employer, school, local government and
neighbourhood domains on purpose, because the file is public and a domain list is a profile.
So a user's actual life lands there and stays there.

A bigger shipped map cannot fix this — the missing domains are personal by nature. T10b is
therefore promoted from optional to load-bearing: **cluster domains by session
co-occurrence and time of day, on-device**, and ask the user to name a cluster once it has
held together. No text, no titles, no server, no LLM. The taxonomy becomes theirs.

**More categories is not the goal and would not help on its own.** D26 already finds 9 of 15
categories below the label floor; the taxonomy is too fine for the data, not too coarse. The
objective is specifically to *convert `unknown` into named clusters*, not to multiply
categories.

### Cold start bootstraps from imported history

The first-run import gives real blocks immediately — D64's 90-day request returned 57 days,
about eight blocks of each type — so a median exists on day one and the first weekend can be
predicted.

**Correction to something asserted earlier in this session:** D65's 7.7% composition gap was
the *research tier's* view against the extension's, a research bug D78/D79 fixed. **The
import-versus-live offset has never been measured.** Live collection uses `webNavigation`,
which drops redirect hops natively; import reads the history database, which cannot, and
approximates it with the `isLikelyRedirect` heuristic. The heuristic fires on 0.95% of
visits, which is its firing rate and not its error rate.

Since that offset cannot be measured without a profile carrying both sources over the same
days, **the design does not depend on knowing it**:

1. **A trailing window of ~10 blocks ages the import out.** After roughly five weeks of live
   collection the imported blocks have left the window and the bias is gone, with no scale
   factor to compute and nothing to get wrong.
2. **Import may set the yardstick; only live collection may score.** An imported block can
   contribute to a median. A prediction may **never** be resolved against one. This is D72's
   rule in a new place — a window Tise did not watch produces no measurement — and it means
   the approximation can affect what Tise *says* during bootstrap but can never reach the
   scorecard.
3. **The bootstrap period says so on the card**, and the line disappears once the window
   holds only live data.
4. **Measuring the offset is added to the owed real-profile checks:** after ~14 days, re-
   import that window and compare against what was collected live. No new permission.

The describe-don't-predict screen survives as the fallback for a thin import — that profile
returned 57 days because it held nothing older, and someone else's may return ten.

### The gate is split in two

T1's founding gate — ~300 labels in 8 weeks or change the target — is being renegotiated,
deliberately and on the record. Akash chose to set the replacement after measuring. That is
sound for one half and not the other, so it is split:

- **Data sufficiency: set after the measurement.** It is calibrated to what is achievable and
  there is no score available to bias it — the measurement is descriptive, and fits no model.
- **Performance: pre-registered before any model is fitted**, the way D81 did it. Choosing a
  bar after seeing what a model scores is the failure the whole method exists to prevent.

### What is now unmeasured, and must not be forgotten

Nothing in this entry has been measured. Whether `block_volume` yields usable labels at
2 per category per week, whether the qualifying rule leaves enough categories standing,
whether co-occurrence clusters are stable, whether novelty has any room in its base rate —
all open. `return_24h` at least had T1's gate run before a line of it was built.

The next task is that measurement, and **the target is pre-registered only after it** —
including the possibility that the measurement kills `block_volume` and one of the other
three candidates takes its place.

### D89 — T19's measurement: `block_volume` does not survive contact with the data

D88 retired `return_24h` on an argument and recorded, in its own closing section, that
nothing about the replacement had been measured. `analysis/candidate_targets.py` is that
measurement. **No model was fitted and nothing was scored**, which is what makes the
data-sufficiency gate settable from it. The gate fires.

**Two of the three corpora produce zero labels.** Chrome: 7 weekday and 5 weekend complete
blocks, **1 label total**. Firefox: 4 and 4, **0 labels**. Edge, the largest at a 90-day
span, produces **33 weekday and 14 weekend** — 47 against `return_24h`'s 503 on the same
browsing, roughly a **10x drop**. At the most permissive minimum-history setting measured
(`min_prior=2`) Edge reaches 116 and Chrome 44; Firefox still reaches 25.

The arithmetic was always going to say this and the argument talked past it: a weekly block
gives each topic **two observations a week**, so eight weeks of history is eight numbers per
topic per block type. A trailing median needs most of them, and what is left over is the
label supply. This was raised before T19 and is now measured rather than argued.

**The 50/50 claim is false on this data, and the reason is not the one D88 anticipated.**
D88's load-bearing property was that a median split has a base rate of 50% by construction,
for every user. Measured on Edge: **60.6% weekday, 57.1% weekend**.

The two mechanisms D88 named as risks are not responsible. Ties are **6.1% and 0.0%**, and
the trailing median was zero on **0.0%** of labels — the qualifying rule does its job. The
cause is a third thing, which the entry did not consider:

> **A median split is 50/50 only on a stationary series.** These are not stationary. Mean
> events per block, second half over first: Chrome weekday **5.45x**, Edge weekday
> **3.57x**, Edge weekend **2.93x**, Firefox weekday **0.15x**.

With activity growing threefold across the window, the current block beats a median of
earlier blocks far more often than not, for reasons that have nothing to do with the topic
being predicted. On Firefox, where volume *falls*, the bias runs the other way. So the base
rate does not merely miss 50% — it **moves with each corpus's trend, and even changes
direction**, which is precisely the property `return_24h` was retired for lacking.

**And the trend is probably an artefact, which makes it worse rather than better.** Browsers
expire history on their own schedule; `history-shape-*.md` has recorded that as a limitation
since T1. A 5.45x rise over eight weeks is not plausible as behaviour change, and the simpler
reading is that the *older* blocks have been thinned by retention. That has a direct
consequence for D88's cold-start design: **medians bootstrapped from imported history are
systematically low, so the first live blocks would read as "above your usual" almost
regardless of what the person did.** The bootstrap would not be neutral; it would be biased
in a known direction. Not proven — retention and behaviour cannot be separated from one
corpus — but it is the more parsimonious explanation and it is testable against the owed
import-versus-live check.

**The share variant behaves differently and is not obviously better.** Computing the same
target on each topic's share of the block rather than its raw count gives Edge **36.4%
weekday, 50.0% weekend**. Weekend lands exactly on 50%, weekday overshoots downward.
A share normalises out the volume trend, which is why weekend improves; it also makes topics
compositional, so one topic rising forces others down. One number at 50.0% is not evidence
that shares work.

**The other three candidates, measured on the same blocks.**

| Candidate | Labels (Edge) | Base rate | Verdict |
|---|---:|---:|---|
| `novelty` weekday | 12 | **91.7%** | Dead. "You will see something new this week" is not information. |
| `novelty` weekend | 10 | 70.0% | Alive but thin, and 10 labels is not a basis for anything. |
| `dormancy` weekday | 27 | 14.8% | Usable base rate, small supply. |
| `dormancy` weekend | 30 | 13.3% | Same. Consistent across block types, which is mildly reassuring. |
| `next_session_category` | **238** | 33.2% floor | **Five times the label supply of every block target combined.** |

`next_session_category` is the surprise, and it was already built. Always predicting the
single most common successor scores **33.2%**; predicting each category's own most common
successor scores **44.5%** across 14 categories. Neither is a fitted model — both are modes
of the observed data — and the eleven-point gap between them is headroom a transition table
could occupy. The machinery has existed since T10 in both languages and has **never been
benchmarked**.

**Splitting `unknown` by co-occurrence does not work on this data.** Edge's `unknown` holds
661 events across 67 domains, of which **7** appear in three or more sessions. Clustering
finds **0 clusters at every threshold from 0.3 to 0.7**. The bucket is not a few hidden
categories; it is a long tail of domains visited once or twice. D88 promoted this from
optional to load-bearing on the strength of `unknown` holding a fifth of the labels — the
share is real, the proposed mechanism does not reach it. A different signal (title keywords,
which the rules layer already contemplates) or simply asking the user would be needed, and
neither has been measured.

**What this changes.** `block_volume` is **not adopted**. It fails the data-sufficiency gate
on two corpora outright, produces a tenth of the labels on the third, and its central
statistical property does not hold on non-stationary data — which every one of these corpora
is, whether by behaviour or by retention.

Nothing is chosen in its place here. T20 pre-registers the replacement, and this page is what
it chooses from. The candidate with a measured claim to it is `next_session_category`, on
label supply and on a floor-to-mode gap that is not zero; that is a statement about what to
pre-register, not a decision that it works.

**The method note.** Two targets have now been retired, one after being built and benchmarked
across seventy decision entries, the other before a line of product code was written. The
difference is that D88 recorded "nothing about this is measured" as a first-class item and
put the measurement ahead of the build. **The gate cost one session; `return_24h` cost
months.** That is the entire argument for gates, and it now has both halves of the comparison
in the same repository.

**One bug found and fixed inside T19, which changed the answer.** `blocks_from_events`
originally created a block only where events existed, so a week with no browsing simply
vanished. A weekend nobody browsed is a **real observation of zero**, not a missing block:
dropping it removes a true zero from the median, pushes every later median up, and deletes a
label a person would have found informative. Fixing it moved Edge's weekend labels from 7 to
14 — the finding above is the number *after* the fix. It was noticed because the label yield
was implausibly low, not because a test failed, and `test_blocks.py` now covers it.

### D90 — A day is the right block, and the question that produced it was one sentence long

D89 concluded that `block_volume` fails on label supply. Akash's response was a question:
*"Let each day be a block? instead of weekday and weekend?"* Measured, it changes the answer.

| Corpus | Weekly labels | **Daily labels** | Qualifying topics |
|---|---:|---:|---:|
| history-chrome | 1 | **124** | 7 |
| history-edge | 47 | **196** | 6 |
| history-firefox | 0 | **83** | 4 |
| **total** | **48** | **403** | |

**Every corpus now produces labels, including the two that produced none.** Firefox went
from never reaching the starting line to 83. The total is an **8x increase from identical
browsing** — no new data, only a smaller unit.

**The mechanism is the one D89 identified.** A weekly block converts months of browsing into
a handful of numbers per topic, and a trailing median consumes most of them before the first
label exists. A day is the smallest unit that still has a "usual", so the same history buys
five to seven times as many questions.

**The risk I named did not materialise, and I had the reason backwards.** Before running it I
expected daily counts to be zero-inflated — a topic seen three days a week has a daily
history like `[2, 0, 0, 3, 0, 1, 0]`, whose median is 0, which is exactly D88's known flaw.
Measured, the **median-zero rate is 0.0% on all three corpora**. The qualifying rule handles
it: a topic present in at least half its prior blocks necessarily has a median of at least 1,
so the rule that was written for the weekly case already excludes the failure case at daily
granularity. Four to seven topics survive per corpus, which is enough for a card.

**The 50/50 property still does not hold, and it now misses in the other direction.** Base
rates are **36.3% Chrome, 39.3% Edge, 47.0% Firefox** under `>`, against 57-61% for weekly.
Ties are 2.4-3.6% and cannot account for it. So D88's central claim remains false at daily
granularity — the target is simply no longer *saturated*, which is a weaker and more
achievable property than being balanced.

**The share variant is closer to balanced on every corpus**: 41.1%, 44.4%, 49.4% against
36.3%, 39.3%, 47.0%. That is three corpora agreeing in the same direction rather than the
single 50.0% that D89 correctly refused to read anything into. It is now the better-supported
of the two framings, though "better" here means 41-49% rather than 50%.

**What this does not do.** It does not make `block_volume` correct — it makes it *viable*,
which it was not. The trend contamination is smaller because a ten-block trailing window now
spans ten days rather than seventy, but Chrome still trends 3.38x across its span and the
retention hypothesis from D89 is untested either way. Nothing has been scored. No model has
been fitted to any of this.

**Where it leaves T20.** Two candidates now have a measured claim, and they are close enough
that the choice is a real one rather than a formality:

| | Labels | Balance |
|---|---:|---|
| `block_volume`, daily | **403** | 36-47%, or 41-49% on shares |
| `next_session_category` | 238 | 33.2% floor against a 44.5% mode |

D89 named `next_session_category` as the only candidate passing both tests. That sentence is
now out of date: daily `block_volume` passes both as well, and on more labels. T20
pre-registers between them, with both measured, and the argument for either is now a
comparison rather than an assertion.

**The method note, which is the part worth keeping.** D88 chose weekday/weekend blocks from
an argument about how people experience a week. It was a good argument and it was wrong, and
one question about the block size recovered the target D89 had just declared dead. The
measurement had been built by then, so answering it cost an hour — the same machinery, one
parameter. **Build the measurement before the conviction, and a change of mind is cheap.**

### D91 — Pre-registering the target, before any model is fitted

D88 split the gate deliberately: data sufficiency set **after** T19's measurement, because a
descriptive measurement produces no score to bias it; performance set **before** any model
exists, because a bar chosen after seeing what a model scores is not a bar. T19 and T19b
supplied the first half. This entry fixes the second, and every choice below is made with no
model score of any kind in existence for these targets.

Committed before implementation. Git holds the order, as it did for D81.

---

#### The target: `block_volume`, daily

> For topic *C* and local day *D*: is *C*'s event count on *D* **strictly greater** than the
> median of *C*'s counts over the trailing 10 complete days before *D*?

Every parameter, declared now:

| | Value | Why this and not something else |
|---|---|---|
| Block | one **local** calendar day | Smallest unit that still has a "usual". D90: weekly gave 48 labels, daily gives 403. |
| Trailing window | **10 blocks** | D88 chose ~10 so an imported bootstrap ages out. At daily granularity that is 10 days rather than 70, which also shrinks the trend contamination D89 found. |
| Minimum history | **6 prior blocks** | Below that there is no median worth the name. |
| Qualifying rule | present in **≥ half** the window | D88's rule. T19b showed it already excludes the median-zero case at daily granularity: measured 0.0% on all three corpora. |
| Comparison | **strict `>`** | Matches the claim the card makes — "more than usual" is not "at least usual". Ties are 2.4–3.6% (T19b) so little rests on it, and the tie rate is published beside every base rate. |
| Quantity | **raw counts**, not shares | See below. |

**Counts, not shares, and this one is genuinely close.** Shares are nearer balanced on all
three corpora (41.1 / 44.4 / 49.4 against 36.3 / 39.3 / 47.0) and cancel the unmeasured
import-versus-live offset. Two things decide it the other way. First, shares are
**compositional**: if video spikes, every other topic's share falls, so a card would read
"dev is down" when dev did not move — a statement that is arithmetically true and
substantively false, which is the worst kind. Second, the offset argument is much weaker at
daily granularity than it was at weekly: a 10-block trailing window now spans **10 days**, so
imported blocks age out of every median within a fortnight rather than over two months.
Shares are computed and reported alongside throughout, so if this is wrong it is visible.

**The base rate will not be 50%, and that is accepted rather than assumed away.** T19b
measured 36–47%. D88's claim that a median split is balanced by construction is false on real
data and has been for two entries now. What daily granularity buys is that the target is not
*saturated* — unlike `return_24h` at 65–72%, where a constant answer was already most of the
way right. Not-saturated is the property that matters, and it is weaker than what D88 claimed.

---

#### What ships is decided in two independent steps

This distinction did not exist for `return_24h` and its absence is part of why that target
ran as long as it did.

**Step 1 — does the target ship at all?** Yes, if the data-sufficiency gate passes. That gate
is now a **shipping rule that runs on the user's machine**, not a fact about this corpus:

> A topic gets a volume card only once it has **6 prior blocks** and clears the qualifying
> rule. A user sees no volume cards at all until at least **one** topic qualifies.

On these corpora that yields 4–7 topics each, so it passes here. Its real job is on somebody
else's browsing, where it may not.

**Step 2 — does the *learned model* ship, or the base-rate table?** Separate question, and
the honest answer may be the table. A card reading *"Shopping today · 71% — 11 of your last
15 days"* can be driven by `category_base_rate` alone. **Machine learning is justified only if
it beats that**, and if it does not, Tise ships the table and says so in the README. That is a
smaller claim and a true one, and D80's whole lesson is that the smaller true claim is worth
more than the larger unsupported one.

---

#### The performance bar, fixed now

The reference is **`category_base_rate`** — a per-topic table of how often that topic is above
its own median. D28's principle, transplanted: beating chance is uninteresting, beating a
per-topic table is the question.

**The learned model is adopted over the table only if** its paired Brier difference against
`category_base_rate`, resampled by **subject cluster**, **excludes zero in the model's
favour**, on **Edge** (the largest corpus, 196 labels).

Point estimates do not qualify. Fold counts especially do not — D80 established a no-skill
model wins 2 of 5 folds or more 81% of the time. This is a **stricter** rule than D81's
adopt-unless-worse, and deliberately so: D81 was adopting a feature transform on a structural
argument with the score as a veto, whereas here the only argument for the model over the table
*is* the score.

**If the bar is not cleared, the table ships.** That is not a failure state, it is an outcome
with a written plan.

---

#### Predictions, recorded now

1. **The model will beat `global_base_rate` on all three corpora** by point estimate. A low
   bar, and failing it would mean the features carry nothing at all.
2. **The model will not be distinguishable from `category_base_rate` by subject-clustered
   interval on Edge.** Every such comparison in this project has included zero — D80 for the
   model against its bar, D85 for XGBoost against the model. I expect the pattern to hold and
   the bar in the section above to go unmet.
3. **`same_as_last` will beat `category_base_rate` on at least one corpus.** This is the
   interesting one and it is specific to daily blocks. Browsing is bursty and autocorrelated:
   a heavy shopping day is more likely to follow a heavy shopping day. A per-topic average
   cannot represent that at all, and a one-step persistence rule can. If it holds, the useful
   signal in this target is **persistence**, not the per-topic rate — and that is a finding
   about what to build next regardless of what the model scores.

Prediction 2 is the one I would most like to be wrong about, and prediction 3 is the one most
likely to change what gets built.

---

#### The secondary: `next_session_category`

Measured in the same run, because it has existed in both languages since T10 and has **never
been benchmarked**, which is a hole in the project independent of any of this.

Its bar, also fixed now: **top-1 accuracy on rolling-origin test folds must exceed the 33.2%
always-the-global-mode floor**, by a subject-clustered interval excluding zero.

The 44.5% per-category mode from T19 is **not** a bar — it is an in-sample figure, the
training-set mode scored on itself, and using it as a threshold would be scoring a model
against its own fit.

**It cannot be promoted over `block_volume` by scoring better.** The two answer different
questions and only one has a stated product. The single circumstance in which
`next_session_category` becomes primary is fixed here: **`block_volume` fails its
data-sufficiency gate on a real profile** — not on these corpora, where it passes — **and**
`next_session_category` clears the bar above. Any other route from "it scored well" to "it
ships" is the garden of forking paths, and writing the exception down now is what stops it.

---

#### What this entry cannot do

It cannot make the target correct. T19b established that `block_volume` is **viable** — it
produces labels on every corpus — and nothing more. No model has been fitted to it, its base
rate is unbalanced, and the trend contamination D89 found is smaller at daily granularity but
unquantified. Those are open, and the next entry reports them against these predictions.

### D92 — `block_volume` is measurable and not predictable. The table ships, the model does not.

D91 fixed the bar, the parameters and three predictions before any model existed for this
target. `analysis/block_volume.py` produces the numbers. Two of the three predictions failed,
and the one that held was the one written so that **holding it means the model fails**.

| # | Prediction | Verdict |
|---|---|---|
| 1 | The model beats `global_base_rate` on all three corpora | **FAILED** — beats it on none |
| 2 | The model is **not** distinguishable from `category_base_rate` on Edge | **HELD** |
| 3 | `same_as_last` beats `category_base_rate` somewhere | **FAILED** — beats it on none |

**D91's adoption rule is not met, so the base-rate table ships and the learned model does
not.** That was written down in advance as an outcome with a plan rather than a failure
state, and it is the outcome.

**Prediction 1 failing is worse than the bar being missed.** Edge: model **0.2607**,
`category_base_rate` 0.2479, `global_base_rate` **0.2529**. The model is beaten by a single
constant. Chrome is the only corpus where it edges the bar at all (0.2439 against 0.2454) and
it still loses to the constant there. Ten features, eleven design columns, and the fit is
worse than predicting one number for everything.

**Prediction 3 failing is the informative one, and it kills the mechanism the feature set was
built around.** The argument was that daily browsing is bursty and autocorrelated — a heavy
shopping day follows a heavy shopping day — so persistence should be real signal that a
per-topic average cannot represent. Measured, `same_as_last` scores **0.4140 against the
bar's 0.2479** on Edge, 0.3337 against 0.2454 on Chrome, 0.5939 against 0.2641 on Firefox. Not
marginally worse: **far** worse, on every corpus.

The fitted weights say the same thing independently. Of the four persistence features in
`bs_1`, `prevAbove` carries **−0.041** and `streakAbove` **+0.065** — both indistinguishable
from nothing. The largest weight is `medianLevel` at **+0.563**, which is a statement about
how big a topic is, not about what it is doing.

**So "was today above your usual?" is close to independent from day to day.** Yesterday
being above tells you almost nothing about today. That is a real property of the data and it
is the opposite of what the target was designed around: D88 chose a median split precisely so
the answer would vary, and it varies — it just varies unpredictably.

**What this means for the product.** The card survives; the model does not.

> **Shopping today · 71%** — *11 of your last 15 days.*

is driven by `category_base_rate` alone: a per-topic count of how often that topic has been
above its own median. It is honest, it is computable on-device with no training at all, and on
this data **nothing measured beats it**. Tise can ship that card today and say plainly in the
README that the number behind it is a rate rather than a model. D80's lesson, one level up:
the smaller true claim is worth more than the larger unsupported one.

**What has now been established across three targets.** `return_24h` was measurable and
uninteresting. `block_volume` weekly had too few labels. `block_volume` daily has labels and
no learnable structure. The consistent finding, stated plainly: **on one person's browsing, a
per-topic rate is very hard to beat**, and every model this project has fitted — logistic
regression on 14 features, on 18, XGBoost tuned for small data, and now a purpose-built
block feature set — has failed to separate itself from one.

That is a result, and it is the honest headline for the showcase. It is also the strongest
argument for the abstention and interval machinery being the thing worth demonstrating,
rather than any accuracy figure.

**Caveats that are real but do not rescue it.** Edge's pooled test set is 90 rows across 5
subject clusters, so the intervals are wide and the *bar* comparison is genuinely undecided
in both directions. But prediction 1 does not depend on an interval: the model loses to a
constant by point estimate on all three corpora, and no amount of additional data changes a
sign that consistent into a positive result. The base rate is 36-47% rather than 50% (D90),
and volume trends still contaminate the target (D89) — both make the target worse, neither
makes the model better.

**What is not concluded here.** `next_session_category` is untouched. D91 registered it as
secondary with its own bar — the 33.2% always-the-mode floor — and the one circumstance in
which it becomes primary. It has 238 labels against this target's 403 and, unlike this one,
has never been fitted at all. It is the remaining candidate.

### D93 — Attention: the best data this project has had, and still not an established result

Akash's instruction was to reason from the data rather than from a target. Doing that puts
**dwell** at the top: one label per visit rather than per session or per day, and a median
split against the category's own recent dwell. `analysis/attention.py` measures it on the
history file, which records `visit_duration` even though the API does not.

**This is a scouting measurement and cannot adopt anything.** No bar was pre-registered for
this target, so the model score below says whether the direction earns a pre-registration
and nothing more. D91's rule stands: a bar chosen after seeing a score is not a bar.

**Two things are better than anything measured before.**

| | `return_24h` | `block_volume` daily | **attention** |
|---|---:|---:|---:|
| Labels | 998 | 403 | **10,502** |
| Base rate | 65-72% | 36-47% | **50.0% / 50.3%** |

**26x the labels of the last target, and the first target whose base rate actually landed on
50%.** D88 claimed a median split gives that by construction; D90 measured it false for daily
blocks, where the unit was coarse enough for volume trends to dominate. At visit level the
trailing window spans hours, and the property finally holds.

**And then the result does not survive the honest comparison.**

| Comparison | Chrome | Edge |
|---|---|---|
| vs `category_base_rate` — the nominal bar | +0.0020 [+0.0012, +0.0319] **excludes zero** | +0.0065 [+0.0048, +0.0201] **excludes zero** |
| vs `global_base_rate` — a constant | +0.0012 [−0.0051, +0.0191] **includes zero** | +0.0055 [−0.0001, +0.0097] **includes zero** |

It would have been easy to publish the first row: *the first time in this project a model has
separated from its bar, on both corpora.* That sentence is true and it is misleading, which
is the D86 failure mode exactly.

**`category_base_rate` is the wrong bar for this target, and it is wrong by construction.**
The label is "above **your own median for this category**", so every category's rate is ~50%
by definition. Estimating twelve per-category rates that are all the same number adds
variance and nothing else — which is why the bar scores **worse than a constant** on both
corpora (0.2508 against 0.2500 on Chrome, 0.2511 against 0.2501 on Edge). Beating it is not
an achievement; it is beating a noisier version of a constant.

Against the constant, **neither corpus separates.** Edge misses by **0.0001** on the lower
bound. That is close enough to be worth pursuing and not close enough to claim, and the
distinction between those two is the whole discipline.

**What did carry weight, and it is the first time.** The largest coefficients on Edge are
`dwellLevel` (−0.256) and then **`arrivedLink` (−0.212)** and **`arrivedTyped` (−0.141)**.
`transition` has been collected since T1 and read by **no feature in this project until
now** — and on its first use it lands among the strongest signals. How you arrived at a page
conditions how long you stay. That is a genuine conditional, of the kind every previous
feature set lacked.

**The caveat that could account for all of it.** `visit_duration` measures how long a **tab
held a URL**, not how long a person looked at it. A tab left open overnight records a long
duration and no attention whatsoever. So part of what the model is predicting may be "will
this tab stay open", which is a different and much less interesting question. **`idle` plus
window focus is what separates the two**, and neither is available without the `tabs`
permission — which is the decision this page exists to inform, and which is now better
informed in both directions.

**What this changes.**

- The direction is worth a pre-registration. It is **not** worth a permission request yet,
  because the honest comparison did not separate.
- `bs_1` and the block work are superseded as candidates, not deleted.
- **`transition` should be in every future feature set.** That finding is independent of
  whether attention survives, and it applies to `next_session_category` immediately.
- The realistic path to separating from a constant is better labels rather than a better
  model: `idle` and focus would turn "tab was open" into "person was present", and that is
  the difference the interval is currently straddling.

**Method note.** Three targets have now been chosen from an argument and measured
afterwards. This one was chosen by reading the data first — what does it describe, what
questions does it naturally answer — and it produced 26x the labels and the first balanced
base rate on the first attempt. That is not proof the approach is better, but it is the only
target that arrived at a plausible result without a redesign, and it took one session.

---

## Four targets, one pre-registration

### D94 — Pre-registering all four targets, before any of them is fitted

Akash's direction: Tise predicts all four candidates identified by reasoning from the data
rather than from a target. This entry fixes every definition, bar, cluster unit and adoption
rule **before implementation**. Git holds the order, as it did for D81 and D91.

**One change applies to all four, and it is the most consequential thing in this entry.**

#### The cluster unit changes, and here is the argument and the confession

Every interval this project has published was resampled over **9-12 subject clusters**,
because the subject has always been the category and there are ~15 of them. D93's Edge run
had **2,805 test rows** and an interval built from **11 things**. Bootstrap width scales
roughly with 1/√clusters, so no comparison in this repository has ever been able to resolve a
small effect — regardless of how much data it had.

**The confession:** I am proposing this *after* seeing that category-clustering failed to
separate D93's result, and the arithmetic suggests session-clustering would have separated
it (√(147/11) ≈ 3.7× narrower, which turns +0.0055 [−0.0001, +0.0097] into roughly
[+0.0042, +0.0068]). That is exactly the shape of a forking path, and it is why this is
being registered in advance of the run rather than applied to the old one.

**The argument, which stands independently of that:** for a **per-visit** label the natural
correlation unit is the **session**, not the category. Two visits in one sitting share
context, device state, mood and time; two visits to `video` three months apart share only a
label. Clustering by category models a dependence that is weaker than the one actually
present, and ignores the one that is.

**The rule:** every target below declares its cluster unit in advance, and **both** the
declared unit and the category unit are reported side by side. If they disagree, that
disagreement is the finding and gets its own entry.

---

### T-A · `visit_engaged` — will this visit hold you?

> At the moment a page opens: will dwell exceed the median dwell for this **category** over
> its trailing 20 visits?

**The label is deliberately identical to D93's `as_1`.** D93 measured 10,502 labels at a
50.0%/50.3% base rate and missed separation from a constant by 0.0001. Changing the label
now would make any improvement unattributable. **One thing changes: the features** (`domain`
and sequence context added) **and one thing changes: the cluster unit**. Both are stated
here so the comparison against D93 is exact.

- **Features** — `as_2` = `as_1` plus domain familiarity (visits to this domain, share of
  its category, is-this-a-daily-domain), sequence context (previous category, previous
  domain, previous dwell ratio, same-domain-as-previous). **`domain` has been stored since
  T1 and read by zero features**; this is its first use.
- **Cluster unit:** session. Category reported alongside.
- **Bar:** `global_base_rate`, a constant. D93 established that `category_base_rate` is the
  wrong bar here and is *worse than a constant*, because a per-category median split makes
  every category ~50% by construction.
- **Adoption:** the paired interval against the constant, session-clustered, excludes zero
  in the model's favour **on Edge**.

### T-B · `browsing_next_hour` — will you be here?

> For each clock hour in the observed span: will at least one visit occur in the next hour?

- **Subject is the hour-of-day bucket**, not the category. That makes
  `category_base_rate` the *per-hour* rate automatically, which is the correct bar and needs
  no new baseline code.
- **Cluster unit:** calendar day (56-90 per corpus).
- **Bar:** the per-hour rate. Beating a flat rate would be trivial — circadian rhythm is the
  strongest regularity a person has — so the bar is the rhythm itself.
- **Adoption:** interval against the **per-hour rate** excludes zero in the model's favour on
  Edge. Beating only `global_base_rate` does **not** qualify.

### T-C · `next_category` — what comes next?

> Given the category just finished, which category comes next?

- **Multiclass**, so Brier does not apply directly. Evaluated on **top-1 accuracy**, with
  top-3 reported.
- **Labels:** every category change, **within** sessions as well as between them. D91 fixed
  the between-session bar; the within-session supply is far larger and untested.
- **Cluster unit:** session.
- **Bar:** the **33.2% always-the-global-mode floor** from T19. Explicitly *not* the 44.5%
  per-category mode, which is in-sample and would score a model against its own fit.
- **Adoption:** bootstrap interval on the accuracy difference against the floor excludes
  zero in the model's favour on Edge.

### T-D · `tab_return` — will you come back to this tab?

> When a tab is switched away from: will it be activated again before it is closed?

- **Cannot be measured on any existing corpus.** The history database records visits, not
  tabs, so there is no offline version of this. It requires the **`tabs`** permission and
  live collection, and it is registered here so its definition is fixed before any data
  exists rather than shaped by the first data that arrives.
- **Cluster unit:** session. **Bar:** `global_base_rate`.
- **Blocked**, and stated as blocked rather than quietly deferred.

---

### Predictions, recorded now

1. **T-A separates from the constant on Edge.** The direct claim, and the one I most expect
   to be right — D93 missed by 0.0001 with neither `domain` nor sequence features and with a
   cluster unit that could not resolve the effect.
2. **`domain` features carry more weight than `transition` did.** `transition` entered at
   −0.212 on first use. Domain familiarity distinguishes a site visited 400 times from one
   seen once, which is a larger behavioural difference than link-versus-typed.
3. **T-B beats a flat rate easily and does *not* beat the per-hour rate.** Circadian rhythm
   is nearly all of the signal, and a model that adds recent-activity features on top of it
   will find little left. **This is the prediction most likely to embarrass me**, and it is
   why the bar is the rhythm rather than a constant.
4. **T-C's within-session supply exceeds 1,500 labels per corpus** — an order of magnitude
   above the 238 between-session transitions T19 measured.

### The stopping rule, fixed now

Akash has said machine learning stays. That is the direction and it is not in question
here. What is fixed here is what counts as an answer:

**If none of T-A, T-B or T-C separates from its declared bar, the finding is that one
person's browsing at this scale does not support a model, Tise ships descriptive, and that
result is published as the headline rather than buried.** T-D remains open only because it
is unmeasured, not because it is a fallback.

Three targets, three bars, all declared before a line of the model exists.

### D95 — An outside plan reviewed: two candidates adopted, four confidence claims contradicted

Akash supplied an external technical overview, *Local On-Device Browser Behavioral Prediction
System*. It is not committed to this repository — its provenance is not ours to vouch for —
so everything load-bearing from it is restated here and this entry stands alone.

**Its data inventory is effectively identical to the Tier 0/1/2 list built here**, `idle`
included. Two analyses arriving independently at the same inventory is worth something: it
raises confidence that the *data* audit is right, and it says nothing about whether the
*predictions* are achievable, which is where this project's evidence lives and the document
has none.

**What it proposes that D94 already covers.** Next navigation action, next domain (T-C),
routine and session-start (T-B), session continuation (needs `idle`), next tab behaviour
(T-D), domain habit and recurrence. Roughly 80% of its recommendations are already
pre-registered or are natural extensions. Its architecture recommendations agree with ours:
statistics and Markov before gradient boosting before sequence networks, and "do not start
with a Transformer".

---

#### Two candidates adopted from it

**T-E · session intent clustering.** Unsupervised clustering of sessions into recurring types
— research, routine checking, entertainment, exploration — from session-level features
(domain count, duration, transition distribution, entropy, idle periods). We had not
considered this and it is a genuinely different shape from everything tried: it describes a
session rather than predicting a topic, needs no labels, and is the same machinery T10b's
domain clustering would use. **Descriptive, so it can ship without clearing a prediction
bar**, which matters given D92's finding that the base-rate table is hard to beat.

**T-F · domain association rules.** Which domains co-occur within a session, via association
rules or FP-Growth. Co-occurrence was identified here as untapped; this names the method.
`domain` is stored, read by zero features, and this is a use for it that needs no model.

---

#### Four confidence claims its own table makes, contradicted by measurements here

The document's §18 rates prediction potential without measuring any of it. Four of those
ratings conflict with numbers this project has already produced.

| Its claim | Our measurement |
|---|---|
| Session continuation/end — **High** | **Saturated.** Chrome averages ~35 visits per session, so "will this continue" is ~97% yes. A constant is 97% accurate and useless — the exact trap `return_24h` fell into at 70%. Its *other* framing ("ends within 5/10/30 minutes") is sound; the binary one is not. |
| Next transition type — **Very High** | `link` is the large majority of transitions. Accuracy will be high and **skill near zero**. Same trap. |
| Next domain — **Very High** | Next *category* measures a 33.2% always-the-mode floor against 44.5% in-sample (T19). With ~227 domains, top-1 falls much further. Top-3 is plausible; "Very High" is not supported. |
| Personal anomaly detection — **Very High** | **Unmeasurable.** Anomaly detection has no ground truth; the document concedes it trains without labelled anomalies and then rates it Very High regardless. |

**The anomaly rating is disqualifying for this project specifically, not merely optimistic.**
Tise's differentiator is that every published number came from a committed script with an
interval on it. An unfalsifiable headline capability is **purchase intent returning under a
new name** — D6 removed that target for exactly this reason, and reintroducing it as the
flagship would undo the one thing the showcase demonstrates. Anomaly detection may still be
worth building as a *labelled demo*, never as an evaluated claim.

---

#### The two things it does not address, which are the two that have actually beaten us

**Scale.** It never confronts how little data one person produces. Eight weeks of browsing is
~5,000 events. It recommends LightGBM, XGBoost, HMMs and LSTMs without noting that
`block_volume` yielded **403 labels** across three corpora, where a boosted ensemble overfits
immediately — D85 measured exactly that. Every failure in this project has been label count
and cluster count, not model class.

**Baselines.** It lists metrics thoroughly and **never says compare against a per-topic
rate**. That omission is the entire history of this project: four models, all matched or
beaten by `category_base_rate`. A plan recommending gradient boosting without a mandatory
baseline comparison leads directly into the four failures already recorded here. D24 makes
baselines mandatory in every report and that rule stands above anything this document says.

---

#### One correction, and one thing adopted

**Rejected: §20's "hash or locally tokenize sensitive identifiers".** Hashes of low-entropy
paths invert trivially — a URL path space is small enough to brute-force in seconds, so a
hashed path is a reversible path. If path features are ever adopted, they are bounded
non-reversible signals, never hashes. This does not change the still-open invariant-2
decision; it removes one wrong way of implementing it.

**Adopted: §17's confidence buckets** — "High / Medium / Low / Insufficient data" rather than
a precise probability from a poorly-calibrated model. This is close to what D88 already
decided (always show the denominator) and is the better UI expression of it. A bucket plus a
denominator says more honestly what a bare percentage implies falsely.

---

**Net effect on the plan:** two candidates added (T-E, T-F), both descriptive and neither
requiring a prediction bar to be useful; four confidence claims recorded as contradicted so
they cannot be quoted back at us later; two omissions recorded because they are the
constraints that have actually decided every result here. T-A through T-D are unchanged, and
D94's stopping rule still governs.

### D96 — Attention collection ships before the target that needs it, because data has lead time

Akash authorised `tabs` and `idle` with live collection. This ships the collection **now**,
before T-A is measured and before any target is adopted, for one reason: **model changes have
no lead time and data collection does.** T-D cannot be measured on any corpus at all — the
history database records visits, not tabs — so every day not collecting is a day of data that
cannot be recovered later. Nothing else about the extension changes: it still trains
`return_24h` and still shows nothing, because no target is adopted and wiring one in before it
clears its bar is the mistake five entries have been spent avoiding.

**What is measured is better than `visit_duration`, not merely equal to it.** D35 recorded the
duration trap as permanent and `dwellSeconds` has been `null` since T1. The history file's
`visit_duration` counts how long a *tab held a URL*, so a tab left open overnight records deep
engagement that never happened — D93 named exactly that as capable of accounting for its whole
effect. A span ends when the person looks away.

**Three rules carry the honesty of the mechanism, and each has a test.**

1. **Never invent a span.** Switching to a tab Tise never saw a navigation in records
   *nothing*. A span with a guessed `eventId` is indistinguishable from a measured one
   afterwards — D51's principle applied to time instead of features.
2. **A zero-length span is the absence of a measurement, not a measurement of zero.** Storing
   one would drag every average toward zero for rows that were never observed, so `closeSpan`
   returns `null` and `assertStorableSpan` refuses it.
3. **An unbounded span is a laptop lid, not a person.** Spans are **capped at 30 minutes**.
   When the worker dies mid-span the reopening code cannot distinguish an hour of reading from
   an hour of a closed laptop, and a single 14-hour span would outweigh a month of real ones.

**A separate store, not a field on the event.** `attention` is a new store at DB version 5.
An event is final when written; a span is opened, possibly extended across a tab switch and
back, and closed later. Putting attention on the event row would mean mutating a row
everything else treats as immutable — the mistake `labels` was separated from `features` to
avoid (D58). Unlike `features` and `labels`, spans **do not** outlive raw events: they
describe the browsing rather than what was learned from it, so retention removes them on the
same schedule.

**State lives in IndexedDB, not `chrome.storage.session`.** MV3 kills the worker constantly,
so an in-memory open span would be lost several times an hour and every span silently
truncated. `chrome.storage.session` would work and needs the **`storage` permission** —
`db.ts` keeps every cursor in IndexedDB precisely so the manifest stays at the permissions
D31 justified and not one more, and that reasoning holds here.

**`tabId` is used and never stored.** It attributes a span to the right navigation and is
discarded with the call. It is absent from `TiseEvent` and from `EVENT_FIELDS`, so the
existing privacy test fails if it ever reaches a stored row.

**Permission being granted is not consent.** Every listener checks `consentGrantedAt` and the
paused flag before reading or writing anything. A person can grant `tabs` and still not have
agreed that Tise may store.

**The manifest guard did its job and was updated deliberately.** `manifest.test.ts` asserted
`optional_permissions` equals exactly `["history"]` and failed — which is the point of it
existing (D31: permission creep must be deliberate). It now asserts the new set **and** gains
a stronger companion: that `cookies`, `webRequest`, `scripting`, `declarativeNetRequest`,
`browsingData`, `management`, `downloads`, `bookmarks`, `topSites` and `storage` appear in
neither list. D95 recorded why `cookies` in particular is the wrong trade — its values *are*
credentials, and it needs host permissions for every site.

356 TypeScript tests, 675 Python, both linters clean, builds.

### D97 — T-A clears its bar. The first target this project has adopted on a rule written before the measurement

`visit_engaged` — *at the moment a page opens, will you stay longer than you usually stay on
pages of this topic?* — separates from its declared bar on both corpora with dwell.

|  | `history-chrome` | `history-edge` *(the adoption corpus)* |
|---|---|---|
| labels / pooled test rows | 4,935 / 2,224 | 5,567 / 2,805 |
| `logreg_as2` | **0.2462** | **0.2388** |
| `logreg_as1` (D93) | 0.2488 | 0.2446 |
| `domain_base_rate` | 0.2499 | 0.2453 |
| `global_base_rate` (**the bar**) | 0.2500 | 0.2501 |
| **vs the bar, session-clustered** | **+0.0038 [+0.0006, +0.0101]** (n=27) | **+0.0112 [+0.0068, +0.0159]** (n=155) |
| vs the bar, *subject*-clustered | +0.0038 [−0.0005, +0.0318] (n=9) — **includes zero** | +0.0112 [−0.0054, +0.0166] (n=11) — **includes zero** |
| vs `as_1`, session-clustered | +0.0026 [+0.0004, +0.0036] | +0.0057 [+0.0024, +0.0094] |
| vs the domain table, session-clustered | +0.0037 [+0.0005, +0.0094] | +0.0065 [+0.0022, +0.0109] |

**D94 fixed every one of those choices before the code existed** — the label, the feature
set, the bar, the resampling unit and the adoption rule. Git holds the order. That is the
only reason this row of numbers means anything: five entries have been spent on targets that
were measured and then argued about, and this is the first one where there was nothing left
to argue.

**Both halves of D94's change were necessary, and that is measured rather than assumed.**
The subject-clustered row exists to answer exactly this. Under the *old* cluster unit — the
category, 9 and 11 clusters — the identical point estimate **includes zero on both
corpora**. Under sessions it excludes zero on both. And with the cluster unit held fixed,
`as_2` beats `as_1` by an interval that also excludes zero on both. So neither change alone
would have carried it: the features moved the estimate, the unit made the estimate
resolvable, and D93 failed by 0.0001 because it had neither.

**`domain` earns its place on its first use.** It has been stored since T1 and read by zero
features until now, and `domainDwellLevel` — the median dwell on this domain — is the
**second-largest coefficient on both corpora**. That is the diagnosis confirmed: every
target this project retired asked about *a topic in isolation*, which is precisely the
question a per-topic rate already answers, so a per-topic rate was hard to beat. `news` is a
bucket; the domain is the thing the person actually went to.

**The rival was added because the coefficient table demands it, not because the rule did.**
Four of `as_2`'s six new features read the domain, so "a per-domain rate table would do the
same job" is the first thing a sceptical reader should be able to check, and D24 makes
baselines mandatory. `domain_base_rate` is `category_base_rate`'s construction and smoothing
keyed on the domain instead. **On Edge it very nearly matches D93's entire twelve-feature
model** — 0.2453 against 0.2446 — which is the strongest single piece of evidence for the
diagnosis above. On Chrome it does **nothing at all** (0.2499 against the constant's 0.2500),
where 217 domains split 2,224 rows against Edge's 127 splitting 2,805. The model beats it on
both regardless. It is reported beside the verdict and never inside it: promoting a rival to
the bar after seeing the coefficients would be choosing the rule from the result.

**Chrome clears the bar and should be read as the weaker corpus.** Its pooled test window is
eleven days and **one session holds 43% of its rows**, against a median session of five. A
bootstrap over 27 clusters is worth 27 clusters only when they are comparable; here most
resamples turn on whether that one session was drawn. The report says so on the page, in a
section that prints the spread for every corpus — a cluster *count* cannot distinguish these
two cases and the `n=` alone is what a reader would otherwise trust. The threshold that
triggers the wording is declared at a fifth and **no adoption decision reads it**, for the
same reason: adding a concentration condition after seeing which corpus is concentrated
would be choosing the rule from the result.

**A 957-visit session is the D17 timeout showing through.** Clustering by session makes a
*declared guess* load-bearing in a new way — too long a timeout merges several sittings into
one cluster and widens the interval, too short splits one and narrows it. T1 looked for an
empirical trough in the gap distribution and found none, so there is no natural value to
discover. `idle` (authorised, D96) is what replaces the guess with a measurement, and this
is now the second reason to want it.

**Adopted is not shipped, and the gap is the point.** `as_2` is the `full` compat class: it
needs dwell, which the `chrome.history` API cannot supply and which the research tier reads
from the history *file*. D96 shipped live attention collection precisely so this day would
not start from zero, but those spans are days old, there is no TypeScript twin of `as_2`, and
the parity contract is therefore unmet. **The extension still trains `return_24h` and still
shows nothing.** Wiring in a target before it is built end to end is the mistake five entries
have been spent avoiding, and clearing a bar does not exempt it.

**Two smaller things settled on the way.**

`brier_difference_interval` now takes `unit=`, which names what a cluster is and changes no
arithmetic. Until D94 the cluster was always the category and the word "subject" was always
right; an interval that resampled sessions while printing `subjects, n=11` would be a right
number under a wrong label, which is the D86/D87 defect. `run_backtest` keeps
`pooled_sessions` alongside `pooled_subjects` so both bounds stay computable after the fact.

And the target had two names: SPEC's `Prediction.target` union has said `visit_engaged` since
D94 while the code emitted `attention_dwell`. One name now. No published figure moved,
because no report prints the target string — and regenerating `attention.md` after all of
this changed **not one figure**, which is how the `as_1` half of the comparison above is
known to be untouched.

697 Python tests, 356 TypeScript, both linters clean, builds.

### D98 — Two provenance defects found while publishing T-A, one of them a near-miss on the privacy invariant

Neither of these is about the model. Both were found by *regenerating* the benchmark site
rather than by reading it, and both are cases where the machinery built to keep the public
artifacts honest was itself wrong.

**`reports.py` had gone stale, in the module written to stop reports going stale.**
`CURRENT_TARGET` said `block_volume`. D92 retired `block_volume` two decisions earlier, so
for that whole time **eight generated reports told readers that Tise now predicts a target
the project had already abandoned** — under a heading marked "Superseded", which is the
part that makes it worse. D88 created this module because twelve reports described a retired
target with nothing saying so; the fix was to derive the banner instead of typing it, and
the derived banner was wrong for two decisions.

**Derivation was not the flaw. The constant was being asked to mean two things.** *What the
project builds toward* and *what the extension actually runs* are different by design — D96
records that no target is wired in before it is built end to end, so they are **meant** to
diverge, and whichever of the two that single constant named, the banner was false about the
other. It is now `CURRENT_TARGET` and `SHIPPED_TARGET`, with one shared sentence
(`what_tise_predicts()`) that names both, so the two cannot drift apart in the wording
either.

Every existing test passed throughout, and they were not bad tests — they check the
*mechanism*: that a retired target gets a banner naming the right decision, that a current
target gets nothing, that the module refuses to invent a decision. None of them could check
that the constant named something real, because **a constant cannot check itself**. The new
test therefore reaches outside the module for the only external fact available: it asserts
`SHIPPED_TARGET` against the literal in `extension/src/model/predict.ts`. That is the same
shape as the parity contract — two tiers, one fact, asserted across the boundary.

`block-volume.md` also had **no banner at all**, D88's original defect one target later, and
now carries one. `attention.md` gained a forward pointer to `visit-engaged.md`: its numbers
stand and are not withdrawn, but it is no longer the project's latest word on its own
question.

**And the second one: `analysis/history_shape.py` re-read the live browser.** Regenerating
that report the way the report itself instructed —

```
uv run python analysis/history_shape.py --out docs/benchmarks/
```

— opened the **live Chrome profile**, copied it afresh, and rewrote the page against three
extra days of browsing. Every figure on it moved: 5,129 visits became 5,418, the T1 gate
count 358 became 377. The code three lines below that command already explained the hazard
in a comment; the printed instruction walked straight into it. Reverted, and the page now
prints `--history data/history-chrome.copy` and says why.

**The near-miss.** Run from `research/`, the cwd-relative `--data-dir` default put that copy
of a person's browsing history in **`research/data/`** — a path **no `.gitignore` rule
covered**. The `/data/` rule is anchored deliberately, so a bare `data/` would not swallow
the `research/tise_research/data/` source package, and an anchored rule protects one
directory rather than the file. It was never committed and it is deleted. Nothing except
noticing stood in the way, which is not a control.

Both ends are closed. Paths in that script are anchored to the repository root, so running
it from a subdirectory cannot scatter copies. And `.gitignore` gained **path-independent**
rules — `**/*.copy`, `**/*.copy-wal`, `**/*.copy-shm`, `**/history-shape-domains-*.md` —
named after the *file* rather than the directory it lands in, because a history copy is a
person's browsing wherever it lands. Verified both ways: a probe file in `research/data/` is
ignored, and no currently tracked file became ignored by the new rules.

The general lesson is the one D78 already paid for once and this pays for again: **a
generated artifact's stated reproduction command is part of the artifact.** If following it
does not reproduce the artifact, the provenance is decorative — and here following it also
touched a live profile.

### D99 — Pre-registration: does `visit_engaged` replicate on 2,148 other people?

**Nothing has been fitted to this corpus.** This entry fixes the corpus, the eligibility
gate, the feature sets, the bar, the statistic, the resampling unit, the verdict rule and my
predicted outcome. Then the run happens. Git holds the order, as it did for D94, and for the
same reason: everything below can be checked against what actually happened, and a rule
written afterwards cannot.

**This entry can retire T-A.** A pre-registration that cannot lose is not one. D97 adopted
`visit_engaged` on **one person** — Akash, two browsers — and his own objection is the right
one: *"data of one person does not give a larger picture of our model."* If the model does not
replicate here, the honest conclusion is that T-A was a property of his browsing, and that
gets published as loudly as the adoption did.

#### The corpus

Kulshrestha, Oliveira, Karacalik, Bonnay & Wagner (2021), *Web Routineness and Limits of
Predictability* — Zenodo **10.5281/zenodo.4757574**, data supplied by Respondi AG.
**2,148 consenting German panelists, 1–31 October 2018, 9,151,243 visits, 49,918 domains.**
Verified on arrival: MD5 matched Zenodo's published checksum, the archive was listed before
extraction (24 CSVs, no traversal, no symlinks, no executables), and every headline figure
reproduces — 9,151,243 rows, 2,148 panelists, 49,918 domains.

**Why this one and not a generated one.** Akash asked for four invented personas at 2×–5× his
volume. That was declined and the reasoning stands: a model scored on data I generate
measures my generator. Whatever skill it showed would be structure I planted, so the number
would be meaningless — and SPEC already forbids synthetic data as a benchmark. The best
published synthetic alternative (Nature *Sci Data* 2025, 50 countries) additionally has **no
duration field**, so it cannot express this target at all, and descends from a single real
history, so it would not have fixed "one person" either.

**Why this corpus can express the target, where nothing else could.** It records
`active_seconds` per visit — **idle-excluded** attention, not tab-open time. That is not
merely equal to what D97 used, it is **better**: D35's duration trap and D93's standing
caveat both concern `visit_duration` counting a tab left open overnight as engagement. This
corpus does not have that defect, so the caveat stops being a limitation and becomes a
measurement.

It also carries `panelist_id`, `used_at`, `domain`, and — from `users.csv` — **self-reported
gender (1,049 male / 1,097 female) and age band**. The `url` column is already redacted to
`0` by the publishers, so SPEC invariant 2 holds at the source and not merely in our reader.

#### The unit is the person, and so is the cluster

**One analysis per panelist. Corpora are never pooled** (D18) — a model trained across people
describes someone who does not exist, which is the same mistake as merging two browsers.

**The cluster for the population claim is therefore the panelist.** One Brier difference per
person, then a bootstrap across people. This is the D94 insight arriving where it always
belonged: every interval this project published before T-A was built from 9–12 categories,
T-A's was built from 27 and 155 sessions, and this one is built from **over a thousand
people**. Width scales with one over the square root of the cluster count, so for the first
time the binding constraint is not the interval.

It is also far cheaper — no within-person bootstrap is needed for the population claim — which
is what makes running every eligible panelist feasible at all.

#### Fixed before the run

**Eligibility, declared on quantities that carry no score information.** A panelist is
analysable if they have **≥ 1,000 visits** (1,395 of 2,148 qualify, measured before this entry
was written), **≥ 20 sessions**, and produce **≥ 200 labels**. Visits and sessions are
descriptive; label counts are a property of the data and not of any model. Ineligible
panelists are **counted and reported**, never silently dropped — D26's rule, applied to people
instead of categories.

**Sample: every eligible panelist.** If measured runtime makes that infeasible, a seeded
random draw of **500** using `BOOTSTRAP_SEED = 20260828`, drawn **before any score is
computed**, and the switch to a subsample is recorded as its own decision rather than done
quietly.

**Categories: theirs, not ours.** The 43 published categories are used as the subject
directly. Tise's own 15-category taxonomy is *not* mapped onto them, because a mapping I
invent is exactly the researcher degree of freedom D81 exists to remove — I would be choosing
it, and I would be choosing it knowing what it is for. A domain listing several categories
(e.g. `"information-tech,media-sharing"`) takes the **first listed**; that rule is arbitrary,
declared here, and not revisited after seeing results. Unmapped domains become
`uncategorized`.

**Feature sets: `as_1n` and `as_2n`.** The corpus has **no transition column**, so
`arrivedTyped`, `arrivedBookmark` and `arrivedLink` cannot be computed. They are **not**
filled with zero: "no transition recorded" is an absence, not "arrived by none of these", and
zero-filling is the defect D51 forbids. The two sets are therefore `as_1` and `as_2` minus
those three, and **this is a different model from the one D97 adopted** — every report must
say so rather than quote the two side by side as though they were the same thing.
`arrivedLink` was not a negligible coefficient on either of Akash's corpora (−0.245, −0.278),
so this is a real difference and not a formality.

**Constants do not move.** `DWELL_SCALE_SECONDS = 30`, trailing window 20, minimum prior 10,
session timeout 1800s — all as shipped. Their median dwell is 8s against a scale declared for
a 30s page read, and the scale still stays fixed: a declared constant that is re-tuned per
corpus is a fitted one (D81), and the transform is monotone, so ordering is preserved either
way.

**The bar is a constant** (`global_base_rate`), per panelist, exactly as in D97 — not the
per-category rate, which a per-category median split makes ~50% by construction (D93).

**The statistic** is the pooled per-panelist Brier difference, `reference − challenger`, so
**positive favours the model**, on rolling-origin test folds with the same fold machinery.

**Reported alongside, never inside the verdict:** `domain_base_rate` (the per-domain rate
table that on Edge nearly matched D93's whole model, and on Chrome did nothing), and the
breakdown by **gender** and **age band**. Promoting any of these to the bar after seeing
results would be choosing the rule from the result.

#### The verdict rule

`visit_engaged` **replicates** if the mean per-panelist Brier difference against the constant,
bootstrapped over panelists at 95%, **excludes zero in the model's favour**.

It **does not replicate** otherwise — and in that case D97's adoption is withdrawn to
"single-person result, did not generalise", `SPEC.md` and `README.md` are corrected, and the
failure becomes the headline. There is no third option, and no re-run with a different gate,
a different bar, or "outlier" panelists removed. **One primary analysis.**

#### Predictions, written down first

1. The population interval **excludes zero** in the model's favour. With >1,000 clusters even
   a small effect resolves — this is the prediction I hold most confidently, and it is
   mostly a statement about the cluster count rather than about the model.
2. The **median per-panelist difference is positive but smaller than Edge's +0.0112**, because
   one month gives thinner per-category history and their median dwell is 8s against Akash's.
3. The **fraction of panelists with a positive difference lands between 55% and 80%.** Near
   50% would mean T-A was a property of Akash's browsing, whatever the pooled interval says —
   so this number, not the interval, is the one that actually answers his question.
4. `as_2n` beats `as_1n` on a **majority** of panelists: the domain features carry across
   people rather than being a quirk of his.
5. `domain_base_rate` beats the constant on **most** panelists — repeating Edge, not Chrome.
6. The per-panelist difference is **positively correlated with visit count.** If it holds, it
   is the answer to "how much browsing does Tise need before it can say anything", which is
   the question Akash actually asked.
7. **No meaningful difference by gender.** Recorded because gender was the axis originally
   proposed, and because "we found a gender difference" discovered after the fact across 43
   categories and six age bands would be fishing. Predicting the null in advance is what makes
   a finding either way worth anything.

#### Known limitations, before any result

**Germany, 2018, desktop, one month.** Not India, not the US — neither has a public dataset
with per-visit dwell, and this was checked rather than assumed. A paid panel is
self-selecting. Seven years old.

**Zero-dwell visits appear to have been filtered upstream** — not one of 9,151,243 rows has
`active_seconds` of 0, missing, or negative, which is not what a raw capture looks like. The
dwell distribution is therefore biased upward and short glances are probably absent. This
affects the label's threshold and cannot be corrected from here.

**One month is short for this label.** A category needs 10 prior visits before its first
label, so slow categories may never qualify. The eligibility gate is what keeps that honest;
the count of excluded panelists is part of the result.

**T-D remains untestable.** No tab data here, as everywhere else.

#### The licence gate

The dataset is **CC BY-NC 4.0**. Tise is free and open source but demonstrates a commercial
advisory, so whether our use is "non-commercial" is genuinely ambiguous and not mine to rule
on. Akash chose to ask: `docs/gesis-permission-request.md` is drafted for him to send.

**Until a reply arrives, nothing derived from this corpus enters `docs/benchmarks/` or any
public artifact.** Results stay in `data/`, which is gitignored. If permission is refused, the
local copy is deleted and the refusal is recorded — and the fact that the only public dataset
carrying per-visit dwell could not be used is itself worth publishing.

### D100 — `visit_engaged` replicates on 1,326 other people. Six of seven predictions held; the one that failed, failed upward

D99's rule, fixed before the run: replicate if the mean per-panelist Brier difference
against a constant, bootstrapped over panelists, excludes zero in the model's favour.

**+0.0091 [+0.0086, +0.0097]**, 95%, **n = 1,326 panelists**. It excludes zero.

**D97's adoption stands, and it no longer rests on one person.**

| | |
|---|---|
| panelists analysed | **1,326** of 2,148 |
| excluded — under 1,000 visits | 753 |
| excluded — under 20 sessions | 69 |
| excluded — under 200 labels | **0** |
| labels | **8,586,879** |
| rows dropped, panelists erroring | **0**, **0** |
| **share of people the model beats a constant for** | **88.6%** |
| median per-panelist difference | +0.0092 |

#### The prediction that failed

**Prediction 3 said 55–80% of panelists would be positive. The answer is 88.6%.** D99 named
that as the number that actually answers Akash's question, on the grounds that a pooled
interval can exclude zero while most individuals see nothing. It was the right number to
watch and the estimate was wrong — in the direction that flatters the result, which is worth
saying plainly rather than filing under "6 of 7 held". A pre-registration where every
prediction lands is usually evidence the predictions were too cautious to be worth making.

| D99 prediction | Held | Measured |
|---|---|---|
| 1. Interval excludes zero, model's favour | yes | +0.0091 [+0.0086, +0.0097] |
| 2. Median positive but under Edge's +0.0112 | yes | +0.0092 |
| 3. Share positive in 55–80% | **NO** | **88.6%** |
| 4. `as_2n` beats `as_1n` for a majority | yes | 83.2% |
| 5. Domain table beats the constant for most | yes | 59.4% |
| 6. Effect correlates with visit count | yes | Spearman ρ = **+0.348** |
| 7. No meaningful gender difference | yes | \|male − female\| = **0.0002** |

#### What "88.6% of people" does and does not mean

It counts panelists whose **point estimate** is positive. It is not 88.6% of people for whom
the effect is *established* — a person whose difference is +0.0001 counts the same as one at
+0.05, and no per-person interval was computed. The population claim is the interval; this
number describes how one-sided the distribution is, which is a different and useful thing.
Both are reported because either alone would mislead.

#### What this settles that a bigger sample of Akash could not

**The measurement itself.** D93 named a caveat that could account for T-A's entire effect:
`visit_duration` counts how long a tab held a URL, so a tab left open overnight reads as deep
engagement. This corpus records `active_seconds` — **idle-excluded**. The effect survives the
better measurement, so that caveat is now answered rather than outstanding.

**The person.** Every number this project published before today came from one person and
10,502 labels. This is 1,326 people and 8.59 million.

**The width.** The interval is **0.0011 wide** against T-A's 0.0091 on Edge, because it is
built from 1,326 clusters rather than 155. That is the arc from D93 completing: the binding
constraint was never data volume, it was how many independent things the interval was
resampling — and for the first time the interval is not the limiting factor in anything.

#### Volume, and Akash's own question

**Spearman ρ = +0.348 between visit count and the per-panelist difference.** The effect is
real across the range and larger for heavier browsers. This is the answer to *how much
browsing does Tise need before it can say anything* — a gradient, not a threshold.

Akash proposed running 100 heavy users and 100 median users as separate batches. That was
declined and the reasoning holds: browsing volume is the very variable predicted to correlate
with the effect, so "the heaviest 100" is the most favourable subset by construction, and two
batches of 100 would have produced two underpowered numbers that cannot be compared. Running
everyone gives the same comparison as a **slope**, measured across 1,326 people.

#### Gender: a null predicted in advance, and measured

Female **+0.0093** (638 people, 88.7% positive); male **+0.0090** (688, 88.5%). A gap of
**0.0002**. This is the only reason the statement is worth anything: D99 predicted the null
*before* the run, precisely so a difference found afterwards could not be dressed up as a
discovery. Akash's original proposal was to model imaginary people by nationality and gender;
the real answer, from real people, is that gender does not matter here.

#### Age is a gradient nobody predicted, and is therefore not a finding

75.8% of 18–24s (n=157) through to **95.4% of 64–80s** (n=65), rising monotonically, with the
mean difference more than doubling across the range. It is striking and it was **not
pre-registered**, so under this project's own rules it is a hypothesis for a future test and
must not be reported as a result. Recorded here so that if it is ever tested, the fact that
it was noticed post hoc is on the record too.

#### What it does not settle

**Germany, October 2018, desktop, one month, a paid panel.** Not India, not the US — checked,
and no public dataset with per-visit dwell exists for either.

**Zero-dwell visits were filtered upstream.** Not one of 9,151,243 rows has `active_seconds`
of zero, missing or negative, which is not what a raw capture looks like. Short glances are
probably absent and the dwell distribution is biased upward.

**This is not the model D97 adopted.** `as_1n`/`as_2n` drop the three arrival flags because
the corpus has no transition column, and `arrivedLink` was not a negligible coefficient on
Akash's data. The replicated model is a near neighbour, not the same one.

**Adopted and replicated is still not shipped.** T-G is unchanged: `as_2` needs live
attention spans, has no TypeScript twin, and the parity contract is unmet. The extension
still trains `return_24h` and still shows nothing.

#### Provenance

Kulshrestha, Oliveira, Karaçalık, Bonnay & Wagner (2021), ICWSM — Zenodo
10.5281/zenodo.4757574, data supplied by Respondi AG, CC BY-NC 4.0. Akash sought and reports
receiving permission for this use; `docs/gesis-permission-request.md` holds the request and
still needs the reply pasted into it, so the record names a person and a date. The report
stays in gitignored `data/` until it does.

761 Python tests, 356 TypeScript, both linters clean, builds.

### D101 — Attention collection never collected anything. Three defects in D96, found by a screenshot

D96 shipped attention spans and reported them tested, linted and building. They were. The
feature was still completely inert, and stayed that way for two days while every entry since
described it as running.

**The collector was gated on a permission nothing could grant.** `attentionEnabled()` ends
with `chrome.permissions.contains({ permissions: ["tabs", "idle"] })`. Both are
**optional** permissions, so Chrome does not grant them at install — something must call
`permissions.request()` from a user gesture, and D96 built no such thing. The popup has done
exactly that for `history` since T7. The gate could therefore never open, `beginSpan` never
ran, and the store stayed empty.

**Nothing failed.** No test broke, nothing threw, no counter went negative. The only symptom
was a number that never moved, and nothing in the extension displayed that number either. It
surfaced because Akash was asked to read a row count out of DevTools and sent a screenshot
showing `Total entries: 0`. Had he not, the next step would have been to wait for spans to
accumulate — indefinitely, on a feature that could not run.

**The export omitted spans, which is worse than it sounds.** `export.ts` says the file
"contains everything Tise holds" and that omitting part of the store would be "the visible
half of the truth". D96 added a store and did not extend the export, so it was. And because
the research tier reads *only* that file — there is no server, by design — **live dwell could
not reach research at all**. `as_2` could have shipped with no way to check the model that
runs against the model the benchmarks describe. Export is now **v3**, additive, with v1 and
v2 frozen and still loading (D76).

**Retention never expired spans, though D96 said it did.** That is not a stale comment. A
span records when attention began, how long it lasted and which navigation it belongs to —
raw browsing data — and the README promises raw data is deleted after 30 days. An unbounded
span store was a **broken privacy promise**. Spans now expire on the same boundary as the
events they describe, in a separate transaction so a failure there cannot roll back the event
deletion and silently disable retention entirely.

All three share one cause: **D96 wrote spans and built nothing that could read them.** No
accessor meant no export, no retention sweep, no count to display, and no way for any test to
observe that the store was empty. The lesson is not "write more tests" — D96 had tests, and
they passed. It is that a store with no reader cannot be observed to be wrong.

#### The guard, and why the first version of it was worthless

`manifest.test.ts` now asserts that **every permission in `optional_permissions` appears in
the arguments of a `permissions.request` call**. A declared permission with no request path
is a promise the extension cannot keep.

The first version checked whether the permission's *name* appeared anywhere in the popup
source. It was tested by reintroducing the bug, and **it passed** — because `tabs` and `idle`
appear in the `contains` call that reads the gate. It was a test that pinned the bug rather
than catching it, which is the exact defect D87 recorded when a test asserted a hardcoded
model name. The version that ships parses only `permissions.request(...)` arguments, and was
verified the same way: reintroduce the bug, watch it fail with the reason stated, restore,
watch it pass.

#### What the same screenshot settled

**The `fs_3` migration works on a real profile** — 334 labels against 5,366 events, exactly
the 334 D64 recorded there. Nothing stranded, nothing reset to the 30-day window. That check
has been owed since D83 and every claim about the migration until now came from synthetic
corpora. The `attention` store also exists with both indexes, so the DB v5 upgrade ran.

The extension was also simply **paused**, which would have stopped collection regardless.
Both facts came from one screenshot, and neither was reachable from the repository.

#### What ships

A permission block in the popup, hidden until consent for the same reason the import block is
— asking to watch which tab is in front, before the person has agreed Tise may store
anything, is asking for the larger thing first. It states what the permission buys, shows the
live span count once granted, and treats a refusal as a valid answer that changes nothing
else.

370 TypeScript tests, 766 Python, both linters clean, builds.

### D102 — T-C clears its bar, and the bar turns out not to have been worth clearing

`next_category` is the shipped transition table's first benchmark. It has existed in both
languages since T10 and drives the "what's next" surface, and nothing had ever scored it.

**It clears its pre-registered bar on Edge**: `transition_table` 52.9% against
`global_mode` 43.1%, **+0.0987 [+0.0202, +0.1725]**, session-clustered over 124 sessions,
excluding zero in the model's favour. That is D94's rule, written before any of this
existed, evaluated exactly as written. Firefox clears it too (+0.1311 [+0.0526, +0.2065]);
Chrome does not (+0.0112 [+0.0000, +0.0246]).

**And the result is worth much less than that sentence makes it sound**, for a reason
pre-registration did not protect against.

#### The bar was wrong before it started on a third of the rows

A T-C label is a category **change** — D94's own words — so the answer can never equal the
category just finished. `global_mode` does not know that. It predicts one category
regardless, and on every row whose source *is* the global mode it is guaranteed wrong before
it looks at anything. That is **31.9% of Edge's test rows**, 26.0% of Chrome's, 27.0% of
Firefox's. The transition table makes that mistake on **0.0%**, because a source's row holds
no self-count and the smoothing never overcomes it.

So the table starts with a third of the bar's rows handed to it by the label definition,
before any counting happens.

#### `constrained_mode`, and the confession that it is post-hoc

`constrained_mode` is the global mode with the source category removed. It knows the one
thing the label guarantees and **nothing else** — no counts, no conditioning, no fitting
beyond the marginal ordering. Whatever the table beats it by is what the counts are actually
worth.

| Corpus | `global_mode` (the bar) | `constrained_mode` | `transition_table` | Table − constrained |
|---|---:|---:|---:|---|
| `history-chrome` | 57.3% | 58.9% | 58.4% | −0.0056 [−0.0362, +0.0162] |
| `history-edge` | 43.1% | 57.1% | 52.9% | −0.0420 [−0.0990, +0.0050] |
| `history-firefox` | 50.0% | 65.6% | 63.1% | −0.0246 [−0.0556, +0.0000] |

**On all three corpora the point estimate favours the two-line rule, and on none of them
does the interval exclude zero.** The fitted table has not been shown to beat "the answer is
never what you just did" anywhere. On Edge the constraint alone is worth +14.0 points over
the bar and the whole fitted table is worth +9.9.

**This was added after seeing the result, and that is stated wherever it appears.** D94's
comparison stands exactly as written and `constrained_mode` cannot change the verdict — the
bar was named before anything was fitted and a bar replaced afterwards is not a bar. But a
page that printed +0.0987 and stopped would have been true and misleading, which is the
failure D24 exists to prevent. It was found by asking why the floor was so low, not by
shopping for a number.

#### `bounce_back` was declared in advance, and it beats the table too

`bounce_back` predicts the category you were on *before* the one just finished. It was
committed as a rival before the script was run — git holds that order — on the argument that
A→B→A is a real pattern and a two-line rule matching a fitted table is worth knowing.

It beats the table on Chrome by an interval that **excludes zero** (the table is
−0.0642 [−0.1244, −0.0070] against it), and leads on point estimate on Edge
(57.6% vs 52.9%, interval includes zero). Firefox is the one corpus where the table wins
outright (+0.0984 [+0.0286, +0.1650]).

So on the primary corpus the shipped transition table is beaten on point estimate by *both*
rules that read almost nothing, and establishes an advantage over neither.

#### The two units disagree, which D94 said would be a finding

D94: *"both the declared unit and the category unit are reported side by side. If they
disagree, that disagreement is the finding."* On Edge they do. Session-clustered
**+0.0987 [+0.0202, +0.1725]** excludes zero over 124 clusters; source-category-clustered
**+0.0987 [−0.1845, +0.3018]** does not, over 13. Same point estimate, three times the
width — which is exactly the arithmetic D94 predicted when it changed the unit, and the
first time the two have been printed side by side on a target that clears.

**The session unit is the declared one and the verdict stands on it.** But 13 clusters
cannot resolve this effect and never could, and that is a property of the old unit rather
than of this result.

#### What was decided before the run, and where it landed

- **The rule was pre-registered; the 33.2% was not the number.** T19 measured that figure
  for the always-the-mode rule over one primary category per session with self-transitions
  permitted. T-C's labels are changes, so the same rule scores differently and its value is
  measured here — 43.1% / 57.3% / 50.0%. Fixing the *number* would also have made D94's
  adoption rule inapplicable: a paired bootstrap needs the reference's prediction on every
  row and a constant has none. Both figures are printed so they cannot be confused.
- **A label is a change, and that costs labels.** Consecutive same-category visits collapse
  into one run, so a session boundary with no change produces no label — 130 of them on
  Edge. The count is printed rather than asserted small.
- **`unknown` is excluded from the answer, not from the question (D27).** No surface can
  show a chip reading *unknown*; conditioning on it is kept. Edge: 905 changes, 792 after
  the exclusion. The all-labels variant is printed for every corpus and the verdict does not
  move (+0.0866 [+0.0171, +0.1514]).
- **D94 predicted "T-C's within-session supply exceeds 1,500 labels per corpus."**
  **It failed.** Within-session labels are **797** on Edge, **710** on Chrome and **192**
  on Firefox — roughly half the predicted floor, and Firefox an eighth. The prediction was
  made against T19's 238 between-session transitions and assumed an order of magnitude;
  run-collapsing is why it is not there, and run-collapsing is what D94's own label
  definition requires. Three of D94's four predictions have now been scored — 1 and 2 held
  in D97 — and this is the first to miss.

#### What this does not decide

`block_volume` is the primary target and D91 fixed the only circumstance in which
`next_category` can replace it: `block_volume` failing its gate on a real profile, **never**
by scoring better. That exception was written down precisely to stop this fork, and nothing
here touches it.

Nor does this retire the transition table. It is a *displayed* surface, not a scored claim,
and D88's replacement for abstention — show everything with its denominator — is what it
would ship behind. What this entry establishes is that **the counts are not currently
earning their place**: a rule that knows only "you will do something different" matches or
beats them on every corpus. If the "what's next" chip ships, it should ship as
`constrained_mode` until the table can be shown to beat it, and that is a smaller and more
honest claim than the one this page could have made.

#### The method note worth keeping

Pre-registration stopped the bar being chosen after the fact. It did **not** stop the bar
being structurally handicapped by the label definition, and that is a failure mode this
project had not seen. D94 registered a bar and a label in the same entry without checking
that the bar could satisfy the label's own constraint. **A floor should be asked one
question before it is registered: can it produce a legal answer on every row?** `global_mode`
cannot, and nothing in the process caught it until the numbers were strange enough to ask.

`analysis/next_category.py` writes `docs/benchmarks/next-category.md`. New plumbing:
`features/transitions.py`, `eval/multiclass.py` (paired clustered bootstrap on accuracy,
with the sign convention inverted against `intervals.py` because accuracy is a score),
`expanding_windows` extracted so both targets cut identical folds, `fit_transition_pairs`
so the benchmarked table is the shipped one.

**828 Python tests, 381 TypeScript, both linters clean.**

### D103 — Tise shows a person something about themselves, for the first time

Until now the extension collected, imported, sessionised, computed features, trained,
predicted, resolved, retained and exported — and displayed **nothing**. Three independent
reasons, all recorded in D101 and the product-state review: the shipped target was retired,
abstention withheld everything by design, and the adopted target was not wired.

This entry closes the second reason and routes around the other two.

#### The card, and why it is counts rather than a model

**"After `news`, you usually go to… `video` 41% — 9 of 22."**

That is the whole surface. It reads the event stream, collapses it into runs, counts what
followed what, and shows each answer with the denominator behind it. **No model is loaded,
no target is adopted, nothing is trained, and no dwell is needed** — which is why it can
ship today rather than after T-G4.

**D102 is the reason it is not the fitted table.** That entry benchmarked
`TransitionTable` for the first time in the project's life. It cleared its pre-registered
bar on Edge, and a rule knowing only that you will not resume what you just stopped scored
**higher** — 57.1% against 52.9% — with the table's point estimate losing on all three
corpora and its interval excluding zero against that rule on none of them. A card showing
the table's smoothed probability would have been presenting a number whose skill is not
established.

What *is* established is what the person did. A frequency shown with its denominator is
either true of their data or it is not; it claims no skill, so it cannot overclaim.

**Smoothing is therefore deliberately absent**, unlike the shipped table it sits beside.
Smoothing is right for a model and wrong here: **the percentage shown must equal the
fraction shown**, or the denominator stops being evidence and becomes decoration.

#### D88's replacement, implemented on both halves

D88 retired abstention and replaced it with *show everything, always with its denominator —
one floor only, a minimum number of prior observations*. The card is the "denominator" half.
The other half was owed and was found by checking what the product actually shows rather
than by any test failing.

`predict.ts` still called `shouldAnswer(model.policy, …)`. D70 had certified **no confidence
threshold on any fold** — the margin needed >12,800 answered rows against calibration slices
of 61-133 — so the policy reported `targetMet: false` and the extension withheld *every*
prediction, permanently and by construction. That call is gone. **`abstained` is now always
false on new rows.**

The field stays rather than being renamed, and that is a deliberate call about a schema this
project treats as expensive to change. It is a true record of rows written under the old
policy, so it is not overloaded — it counts down into history rather than up, and the popup
says which rule wrote them.

**`abstain.ts` and `abstain.py` are kept, not deleted.** D88 explicitly keeps the
accuracy-versus-coverage curve as a published result; it is no longer a gate.
`selectThreshold` still runs at training time so the trade stays measurable, and the model
panel now reports what a threshold *would* buy instead of announcing that it predicts
nothing. Both modules carry a header saying so, because every mention of "showing" and
"answering" in them now describes a curve rather than the UI.

#### Two floors, both declared, both on evidence

The one gate D88 permits. Neither is fitted, and both have the same status as the 30-minute
session timeout (D17) — declared, arguable, and written down.

- **`MIN_TOTAL_CHANGES = 20`.** Below this the card shows nothing and says how many more
  changes are needed, rather than a confident-looking 2 of 3.
- **`MIN_CONDITIONAL_CHANGES = 10`.** Below this the conditional counts are too thin to
  lead with, so the card falls back to the overall rates **and says which it used**. Ten is
  the smallest denominator at which one more observation moves the displayed percentage by
  less than ten points.

The difference from what it replaced is the whole point: this withholds a number for having
**too little behind it**, never for being insufficiently confident. Twenty changes that all
went the same way would have been withheld by the old rule and are shown by this one.

#### `unknown` is a question and never an answer, and a test caught the second half

D27's rule applied to a surface: no chip can read *unknown*, and roughly a fifth of visits
land there by design, because the public category map excludes employer, school, council and
neighbourhood domains — a domain list is a profile. Conditioning **on** it is kept, because
"you were on something uncategorised, next you went to X" is answerable.

**It also does not count toward the evidence floor**, and that was not in the first
implementation. A test written to check the display rule failed for the other reason, which
exposed it: forty changes into `unknown` are forty changes nothing can display, so counting
them would have unlocked a card resting on ten real observations while telling the reader it
rested on fifty.

#### Parity, and breaking it on purpose

`extension/src/features/transitions.ts` mirrors the `features/transitions.py` that D102
built, and the oracle grew a `transitions` section. The TypeScript key-set guard **failed
the moment Python grew it**, which is the second time that guard has done its job.

Session ids are absent from the oracle: D36 makes them locally assigned and opaque, so
comparing them would pin an implementation detail rather than a behaviour.
`withinSession` survives, because it compares two ids inside one language.

The suite was **broken deliberately once** — `previousCategory` re-pointed one run forward —
and it failed on transition 1 with the expected value named. A parity suite that has never
failed has never been tested.

#### What this does not claim

- **No target is adopted or shipped by this.** `predict.ts` still trains `return_24h`, which
  D88 retired; `visit_engaged` is adopted (D97) and replicated (D100) and still not wired,
  because it needs live attention spans (T-G4). The card sidesteps all of that by not being
  a prediction.
- **The card is TypeScript only.** There is no Python twin, deliberately: nothing scores it,
  so a mirror would have no consumer and would rot. `transitions.ts` — the part that feeds
  research — *is* mirrored and is in the oracle.
- **It has not been seen in a browser.** T5, T7 and T11 each had a documented-looking claim
  fail on contact with Chrome, and the D101 defect ran for two days behind a gate that could
  never open. **Owed by Akash: load the build and open the popup.** With 5,371 events on his
  profile the card should render immediately, and if it does not, that is the finding.

403 TypeScript tests, 831 Python, both linters clean, builds.

### D104 — The dashboard, and the shape of real browsing that it exposed

T14 built. `ui/dashboard/` is a full page registered as the extension's options page and
opened from the popup; the popup stays the developer surface it has always said it is.

Four panels, every number traced to something stored: **what comes next** (a card per topic
with enough history to answer for itself), **what Tise has to work with**, **your topics**,
and **the scorecard**. Then a fifth that is the point of the whole page — **what Tise claims
and what it does not**, listing every target this project has taken seriously with its real
state and the awkward part spelled out.

The arithmetic lives in `src/model/overview.ts` and the DOM lives in `ui/dashboard/`. That
split is not tidiness: the suite runs in Node with no DOM, so anything computed inside a
render function is untestable by construction, and a dashboard is where a wrong number is
least likely to be noticed and most likely to be believed.

#### The finding, and it was found by pointing the code at a real profile

On Akash's 5,371 events — 856 category changes, 640 of them showable — ten topics have
enough history for their own card. **Nine of the ten lead most often to `search`.** Two of
them at 100%: after `travel` and after `news`, he searches, every recorded time.

A board of ten cards mostly saying one word looks like a broken page. It is not broken. It is
the **hub-and-spoke shape of real browsing**, where a search engine sits between everything
else, and it is invisible in any synthetic fixture because nobody writes a fixture that
boring.

**It also explains a published result.** D102 found that `constrained_mode` — which ignores
what you just left and only knows you will not resume it — beat the fitted transition table
on all three corpora, and nobody could say *why*. A hub is exactly the shape that produces
that: when the answer is the same regardless of the question, conditioning on the question
buys nothing. D102's number was right and its mechanism was unexplained; this is the
mechanism.

**This is post-hoc and is labelled post-hoc.** It explains a result that was already
measured under a pre-registered rule; it does not revise it, and no bar moves. What it
changes is what a future target should be: "what comes next" is close to answered by naming
one topic, and the interesting question is the one card that differs — *after `search`,
where do you go?* (travel 20%, dev 19%, government 14% — the only topic on the board with a
spread). That is a candidate, not a decision, and it is not registered.

#### What the page does about it

`hubTopic` names the hub when a **strict majority** of topics lead there, and the board's
opening line says so: "9 of your 10 topics lead back to search more often than to anything
else, so the rows worth reading are the ones that do not."

The majority rule is declared, not tuned. Below half there is no hub, the board already tells
its own story, and a sentence would be inventing a pattern out of the largest of several
small numbers. **It never hides a card** — every topic is still listed with its own counts.
It adds a sentence, and turns nine repetitive rows into one fact plus the row that differs.

#### Three deliberate departures from what T14 asked for

T14 was written when `return_24h` was the target and abstention still gated. Each departure
follows a decision taken since, and each is stated rather than quietly dropped.

- **It does not list predictions.** T14: *"every prediction shows probability, window and
  evidence"*. Those predictions belong to `return_24h`, retired by D88. Showing them would
  put a retired question in front of a person as though it were advice. They are kept and
  scored and the scorecard says exactly that.
- **Nothing is hidden for being unconfident.** T14: *"abstained predictions are absent, not
  greyed out"*. D88 retired abstention and D103 implemented the replacement, so the only
  thing withheld anywhere is a number with too little behind it — and the page says how much
  is missing rather than going quiet.
- **Purchase intent is absent, not labelled "not evaluated".** T14 and D6 both wanted it
  displayed with a visible label. That is worse than leaving it out. Confirming purchase
  intent means reading checkout pages, which the privacy design forbids outright, so it
  could **never** move off that label — and a permanent placeholder beside measured numbers
  teaches the reader that the labels are decorative. The reason is printed on the page
  instead, which is the more useful thing to have said.

#### The honesty panel is pinned to the code, not to my memory

`src/model/status.ts` holds the target list and `SHIPPED_TARGET`, and a test asserts it
equals `TARGET` in `predict.ts`. `research/tise_research/reports.py` anchors to the same
file from the other language, so a change to the shipped target has to break something in
both.

**This defect has already happened once.** Between D88 and D97 `reports.py` said the project
predicted `block_volume`, which D92 had retired, and eight generated reports told readers so
— right numbers, wrong frame, inside the module written to prevent it. Those were benchmark
pages read by a handful of people. This page says the same kind of thing to whoever installs
the extension.

Three of the panel's claims are asserted rather than written: exactly one target is
`adopted`, it is not the shipped one, and **nothing is `shipped` yet**. When that last test
starts failing, T-G4 has landed and the panel needs rewriting rather than the test relaxing.

#### What is not done

**It has not been seen in a browser.** The logic was checked against the real export and
predicts ten cards, so it will render — but T5, T7 and T11 each had a documented-looking
claim fail on contact with Chrome, and D101 ran two days behind a gate that could never open.
**Owed by Akash: reload the extension and open the dashboard.**

437 TypeScript tests, 831 Python, both linters clean, builds.

### D105 — T14 verified in Chrome, and the prediction outage the screenshots found

Akash reloaded the extension and sent five screenshots. Four show the work of D103 and D104
running on his real profile. The fifth is an error page, and it is the reason this entry
exists.

#### What works, seen rather than asserted

- **The card renders in the popup.** *"After search, you usually go to… dev 31% (34 of 110),
  travel 31% (34 of 110), ai 14% (15 of 110), video 7% (8 of 110). Counted from the 110
  times you have left search. 7 other topics not shown."*
- **The dashboard renders.** Topic cards with bars and denominators, the hub sentence
  computed live — *"5 of your 6 topics lead back to search more often than to anything
  else"* — the scorecard, and the claims panel with its six targets and their real states.
- **Attention collection is working.** **60 spans over 44 pages, 107 minutes**, against the
  5 spans and two and a half minutes D101 left it at. T-G4's gate is no longer theoretical.
- The hub held on live data at a different corpus size than the export it was checked
  against, which is the first independent confirmation of D104's finding.

#### The bug: every prediction had been failing since T-G1

```
Uncaught (in promise) Error: row is fs_3 and this preprocessor was fitted on undefined;
nothing downstream would notice.
```

T-G1 added `Preprocessor.featureSet` and a check in `transform`, and the check is right:
two feature sets can have the same width, so an `fs_3` row transforms cleanly through an
`as_2` preprocessor and every coefficient after the first differing column lands on the
wrong feature, silently. **What T-G1 did not add was the migration.** The model already in
IndexedDB had been written before the field existed, so it carried no `featureSet`,
`transform` threw on every call, and the extension stopped predicting entirely.

**D83 got this exactly right and D97 forgot it.** The `fs_2 → fs_3` migration exists
precisely because a version bump would otherwise strand every stored row; `migrate.ts` runs
inside `refreshDataset` and a test asserts a migrated row is identical to a recomputed one.
Then T-G1 versioned the *preprocessor* and shipped no migration for it. The rule that was
learned once did not transfer to the next thing that acquired a version.

**Why no test caught it.** Every test in the suite trains its own model, so every
preprocessor in the suite was written by the current build and none of them could be
missing the field. The suite could not construct the failing state, which means it was not
testing storage compatibility at all — it was testing one build against itself.
`tests/stale-model.test.ts` writes the old shape deliberately, and was mutation-checked: with
the fix reverted, two of its eight cases fail.

#### The fix discards rather than guesses

`readModel` treats a preprocessor with no feature set as **stale** and returns `undefined`.
Every caller already handles "no model", and none of them handled a throw from deep inside
`transform`.

**Stamping it with today's feature set was the tempting fix and is the wrong one.** It would
usually be right — a stored model was fitted on whatever was current then, and that was
`fs_3`. When it was wrong the result would not be an error; it would be a wrong probability
produced silently, which is the precise failure the check was added to prevent. A retrain
costs under a minute on a real profile. The guarantee costs more than that.

The stale model is **not deleted**, so the popup can name the state: *"Model needs
retraining — a model trained by an earlier build did not record which feature set it was
fitted on, so it cannot be used safely and was set aside rather than guessed at."* Deleting
it would leave a person reading "no model yet" after months of browsing, which reads as a
bug rather than as a one-off.

#### The pattern worth naming, because this is now four for four

T5, T7, T11 and now T-G1 each shipped a documented-looking claim that failed on contact with
Chrome, and D101 ran two days behind a gate that could never open. **Every defect this
project has found in the extension was found by looking at a browser, and none by a test.**
That is not an argument against the tests — 445 of them hold real invariants — it is a
statement about what they cover. They test one build against itself, and every one of these
five bugs lived in the seam between a build and the state a previous build left behind.

**What follows from it:** a stored shape that acquires a version needs a migration and a
test that writes the *old* shape, in the same commit. `Preprocessor` now has both. The
export schema, `FeatureRow` and `Prediction` already have theirs. Nothing else in storage is
versioned, and if something acquires a version, this is the rule.

445 TypeScript tests, 831 Python, both linters clean, builds.

### D106 — The retrain worked, and found the next defect in the same seam

The stale-model fix landed and Akash retrained. The popup now reports a real model:

> 362 labels, 74% positive. feature set `fs_3`. final gradient 5.8e-6. platt `cal_1`, slope
> 0.77 on 109 held-out rows. no confidence threshold reached 90% on held-out data, which is
> a measurement rather than a reason to say nothing.

Three things confirmed at once: D105's discard-and-retrain works end to end, the model
**converged** (5.8e-6), and there was enough held-out data to calibrate for once — slope 0.77
on 109 rows, not the identity calibrator that D64's run fell back to. The last sentence is
D103's rewording, running: the abstention curve is reported as a measurement instead of
announcing that Tise predicts nothing.

**And the panel underneath still said "No predictions yet."**

#### The alarm path used the model. The button did not.

`background.ts` has two ways to train. The **alarm** advances one chunk per wake-up and then
calls `updateRegistry` — predict for newly closed sessions, resolve what has come due. The
**`tise:train` message**, which is what "Train now" sends, runs chunks back to back until
the job finishes and then stops.

So pressing the button produced a fresh model, no predictions, and a wait of up to
`TRAINING_PERIOD_MINUTES` — **six hours** — before anything used it, with nothing on screen
explaining the wait.

**The module's own docstring asserted the opposite**, and its reasoning is the interesting
part: *"Both go through the same `runTrainingChunk`, so the model this produces is the model
the alarm would have produced, arrived at sooner."* That sentence is true and it is not the
claim that matters. **Producing the same model is not reaching the same state.** The comment
established equivalence on the step the two paths shared and said nothing about the step only
one of them had.

`updateRegistry` is idempotent by design — no cursor, no partial progress — which is exactly
why calling it from the second path costs nothing and was safe to add.

#### The test is a source guard, and says why

The service worker registers its listeners against the real `chrome` object at module load,
so there is nothing to call from a test. What can be checked is the wiring, and the wiring is
what was wrong. `tests/registry.test.ts` now slices `background.ts` at the train listener and
asserts `updateRegistry` appears inside it, asserts it still appears on the alarm path, and
asserts there are **at least two** call sites — because a single call in the shared prefix
would satisfy the first two while leaving one path broken. That third assertion exists
because D101's first manifest guard passed with the bug reintroduced.

#### The seam, again

D105 named the pattern: every extension defect this project has found was found by looking at
a browser, and each lived in the seam between a build and the state a previous build left
behind. **This one is the same shape rotated ninety degrees** — not the seam between builds
but the seam between two code paths that were assumed equivalent because they shared their
expensive step.

The generalisation worth keeping: **when two paths are documented as equivalent, the
documentation names what they share. Check what only one of them does.** A shared subroutine
is evidence about the subroutine, never about the callers.

#### What is now true on a real profile

Collection, import, sessions, features, attention (60 spans / 44 pages / 107 minutes),
training, calibration, retention, export, parity, the card, the dashboard — and, after this,
prediction. **Nothing here changes what Tise claims:** `return_24h` is still the retired
target the extension trains, `visit_engaged` is still adopted and unwired, and the dashboard
still says so.

448 TypeScript tests, 831 Python, both linters clean, builds.

### D107 — The loop closed, and the first number it produced was wrong

The registry fix landed and the full loop ran end to end for the first time in the project's
life: **248 predictions — 192 hit, 1 miss, 7 pending, 48 expired.** Collection, import,
sessions, features, training, calibration, prediction, resolution, scoring, all on a real
profile, with "nothing withheld — every prediction is kept and scored" underneath it, which
is D103 working.

**192 hit against 1 miss is 99.5%, and it is wrong.**

The same target measured on the same browsing has a base rate of **73.2%** — 265 of 362
labels, computed by `analysis` code that has been stable since T2. A scored set that
disagrees with its own base rate by twenty-six points is not a good model. It is a broken
denominator.

#### Resolution could not produce a `miss` on imported history

`resolveOutcome` scanned for a recurrence **first** and checked coverage **afterwards**:

```
for (event of events) if (matches && inWindow) return "hit";   // no coverage check
if (now <= end) return "pending";
if (!isFullyCovered(...)) return "expired";                    // only the negative
...
return "miss";
```

`isFullyCovered` returns false for any window opening before `consentGrantedAt`, which is all
of a 90-day imported history. So every historical window could resolve **`hit`** — from
imported evidence — or **`expired`** when nothing recurred, and **never `miss`**. The
negative branch was unreachable for exactly the rows that dominate the store.

That is D88's rule broken in the direction nobody questions: *an import may set the yardstick,
only live collection may score*.

**The file's own docstring names the mirror image of this mistake.** It says counting an
unwatched window as a miss "is the tempting shortcut, looks conservative, and manufactures a
negative". Scanning for hits first manufactures a *positive* — the same error pointing the
other way, and the one that flatters the project. The reasoning was written down, and only
half of it was applied.

#### The test that pinned it had a real argument

`registry.test.ts` asserted the old behaviour, with a stated reason: *"a return that was
observed is evidence regardless of what was missed around it; only the negative needs full
coverage to be trustworthy."*

That holds for **one row** and fails for any **rate** computed over rows. If a hit scores
under partial coverage and a miss does not, the scored set is biased toward positives by
construction and its accuracy means nothing. Since the scorecard is a rate, and the
reliability curve in SPEC.md is a rate, symmetry is required.

It also conflated two cases. Under a *partial* gap, a return seen in a covered stretch really
was observed and the old argument applies. A window lying entirely **before consent** observed
nothing at all. Every one of the 192 was the second case.

**What the fix gives up is real and is paid knowingly:** a genuinely observed return inside a
partially covered window is now discarded rather than scored. The alternative is a scored set
whose rate cannot be read.

Coverage is now decided **before** any outcome, on the *elapsed* part of the window — a gap
that has already happened can never be filled, so an open window with a hole in it is
unscoreable now rather than at its close. Early hits survive: the scan still runs before the
`pending` check, but only for a window Tise actually watched.

#### The stored outcomes had to be discarded, and that is a migration

Resolution never revisits a settled outcome — by design, and it is the property that makes
idempotence structural. So 192 wrong hits would have stayed on the scorecard forever.

`RESOLUTION_RULE = 2` with a marker in `meta`. On the next pass, outcomes written by rule 1
are **dropped and rebuilt**: a prediction is fully regenerable from the events and the
coverage log, so nothing that was ever *measured* is lost — only what a rule now known to be
wrong wrote down. The marker is written **after** the clear, so an interrupted run repeats it;
repeating costs a rebuild, skipping leaves wrong numbers on screen.

**This is D105's rule applied on the day it was written** — a stored shape that acquires a
version needs a migration *and* a test that writes the old shape, in the same commit. Both
are here.

#### What this says about the last three entries

D105 was a stale shape from an earlier build. D106 was two paths assumed equivalent. D107 is
an ordering inside one function. Different mechanisms, one pattern: **each was invisible until
something real ran, and each was caught by a number that looked wrong rather than by a test
that failed.**

The number that caught this one was 99.5%, and it only looked wrong because 73.2% had been
measured, published and remembered. **A result is checkable to the extent that something else
has already been measured to compare it against.** Every base rate this project has recorded
since T2 was, in the end, a tripwire.

**Nothing here changes any published result.** No benchmark in `docs/benchmarks/` reads the
prediction registry; every one is computed from labels by `analysis/` scripts. The wrong
number reached the popup and this entry, and nowhere else.

454 TypeScript tests, 831 Python, both linters clean, builds.

### D108 — The fix worked, and revealed that the scorecard was measuring the wrong thing

D107's migration ran. The registry rebuilt under rule 2:

| | before | after |
|---|---:|---:|
| hit | 192 | **19** |
| miss | 1 | **1** |
| expired | 48 | **221** |
| scored | 193 | **20** |

Exactly the predicted shape. 221 windows are `expired` because Tise genuinely was not
watching during the imported history, and 20 remain that it did watch. The numbers got much
worse and became correct, which is the outcome D107 said to expect.

**And then the remaining number was still wrong, for a different reason.**

#### `hit` is not "Tise was right"

`resolveOutcome` never reads `probability`. A `hit` means the topic came back inside the
window, whatever the model said about it — a prediction of 0.2 on a window that recurred is a
`hit` and the model was **wrong**.

So `hit / (hit + miss)` is the **base rate of the target over the scored windows**, and the
dashboard printed it under the heading **"Right / wrong"**, with the row beneath it labelled
**"Accuracy on what has resolved"**. It read 95%.

That is my own defect from D104, four days after D102 spent an entire entry on the difference
between a target being easy and a model being good. The same confusion, in the same project,
this time rendered for a person instead of into a benchmark table — where it is worse, because
a dashboard is read by someone with no way to check it.

`abstain.ts` has had the correct rule since T12: `probability > 0.5 === outcome`. It was sitting
in the repository the whole time.

**Both numbers now appear, and they answer different questions:**

- *Topic came back / did not* → **19 / 1**, "…so it happened this often" → the base rate.
- *Tise called it correctly* → the model's calls against those outcomes.

Exactly one half calls **against** a recurrence, the same tie-break `abstain.ts` uses, so a
model outputting 0.5 everywhere cannot inherit a high base rate and look competent.

#### The scored twenty are not a fair sample, and the page now says so

A window only scores if Tise watched **all 24 hours** of it without interruption. That requires
the browser open and collection on for a full day, which selects for the days someone browsed
most — and those are exactly the days a topic is most likely to recur.

The arithmetic agrees that something is being selected: at the measured base rate of 73.2%, 20
windows would be expected to yield **14.6** recurrences, and 19 or more has probability
**0.0162**. That is not a second bug; it is the selection effect, visible. The dashboard now
states it beside the expired count rather than leaving the reader to infer it.

#### What this run establishes

The loop is closed and honest: 248 predictions, 221 of them correctly refusing to score, 20
scored from windows Tise actually watched, a base rate and an accuracy reported as the separate
things they are, and a stated caveat about which days those twenty came from.

**Nothing here is a claim about the model.** `return_24h` remains the target D88 retired, twenty
scored windows support no conclusion whatever, and every published benchmark is still computed
from labels by `analysis/` scripts that never touch this registry.

#### Four entries, four defects, one property

D105 stale shape, D106 two paths assumed equivalent, D107 an ordering inside one function, D108
a label on a number. Every one surfaced from a real run and a number that looked wrong, and
every one was checkable only because something else had been measured first. The last two were
caught against **73.2%**, recorded in T2 and never since touched.

457 TypeScript tests, 831 Python, both linters clean, builds.

### D109 — 100% of 20, and the baseline that was missing beside it

The dashboard rendered D108's separation and produced the first honest accuracy this project
has ever displayed:

| | |
|---|---:|
| Predictions made | 248 |
| Topic came back / did not | 19 / 1 |
| …so it happened this often | 95% of 20 |
| **Tise called it correctly** | **100% — 20 of 20** |
| Still open | 7 |
| Expired — Tise was not watching | 221 |

**100% of 20, printed with nothing to compare it against.** A reader concludes the model is
perfect. The correct reading is on the line above it, and no reader will make the connection.

#### Always guessing "came back" scores 95% of the same twenty

That is what `outcomeRate` is: a predictor that says yes to everything gets every recurrence
right and every non-recurrence wrong, so its accuracy *is* the base rate. The model scored
100%. **The whole of its contribution is one row** — the single non-recurrence it called
negative.

D24 has required a baseline in every report since T2. The dashboard shipped without one,
which is D92 and D102's finding arriving at the interface: both entries concluded that a
base-rate table matches or beats the fitted model, and a panel printing accuracy alone hides
precisely the comparison they exist to make.

The scorecard now prints the baseline underneath, in rows rather than points — *"against
always guessing 'came back': 95% — the model is ahead by 1 of 20"*. Rows because a percentage
difference of five points sounds like a margin and one row out of twenty does not, and the
second description is the true one.

**Always-positive rather than the majority class**, deliberately. The majority class is
chosen after seeing the outcomes and would be in-sample, the defect D91 named when it refused
the 44.5% per-category mode. This target's base rate has been measured at 65-72% since T1, so
"mostly yes" is knowable in advance, and it is what a model has to beat.

The lead can go **negative**, and it renders. A model behind the trivial baseline is the
single most important thing a scorecard can say, and a display that could only show a lead
would be unable to say it.

#### What 20 of 20 is worth

Nothing yet, and the page should not imply otherwise. Twenty rows, all from days Tise watched
without interruption — which D108 recorded are the days with the most browsing and therefore
the most recurrence — on a target D88 retired. The model beat the trivial baseline by one row
of twenty.

That is not a disappointing result. It is the fourth time in this project that a
model-versus-baseline comparison has come back "not distinguishable" (D80, D92, D102, and
now), and the consistency is itself the finding: **`return_24h` was retired for being
measurable and uninteresting, and its own scorecard now says so on the extension's front
page.**

#### Five entries in one day

D105 a stale shape, D106 two paths assumed equivalent, D107 an ordering inside one function,
D108 a label on a number, D109 a number without its baseline. Each surfaced from a real run
and a number that looked wrong. **Each fix made the displayed numbers worse and the page more
honest**, which is the direction this project has committed to and the reason the sequence was
worth publishing rather than squashing.

461 TypeScript tests, 831 Python, both linters clean, builds.

### D110 — The seam audit: three defects, one latent hazard, and a list of what is not covered

Akash's call, after five defects in one day all lived in the same place: the seam between a
build and the state a previous build left behind. This is the deliberate pass over that
class rather than waiting for the next screenshot.

**The rule of the audit, and the reason the existing suite could never do this:** every one
of the 461 tests already here writes its own state with the current build and reads it back
with the current build. They test one build against itself, so the seam is invisible from
inside. `tests/seams.test.ts` does the opposite — it writes the **old** shape directly into
storage and then uses the current code on it. Nothing in it goes through the normal API,
because going through the normal API is precisely what hides the problem.

#### What was audited

Everything Tise persists, enumerated rather than sampled: five object stores (`events`,
`features`, `labels`, `predictions`, `attention`) and the nine unrelated shapes stored under
nine keys in `meta` (settings, coverage log, session cursor, import progress, rejection
counts, training job, trained model, resolution rule, and the two attention keys).

#### Three real defects

**1. A settings object from an older build could erase a default.** `loadSettings` returned
`{ ...DEFAULT_SETTINGS, ...stored }`. An own property whose value is `undefined` **overwrites**
rather than falls back, and IndexedDB preserves `undefined` through structured clone. A build
that ever wrote `overrides: undefined` would leave it undefined here, and every
`settings.overrides[domain]` lookup downstream throws. Fixed by dropping undefined values
before the merge.

**2. A coverage gap with no end read as *closed*.** `gap.to === null ? now : Date.parse(gap.to)`
— a gap written without a `to` at all takes the second branch, `Date.parse(undefined)` is NaN,
and every comparison against NaN is false, so the gap silently stops disqualifying anything.

**That is D107 again, in a second place.** D107 was about resolution scoring windows Tise
never watched; this is the coverage log failing to report that it wasn't watching. Same
consequence, different function, found three hours later by looking rather than by waiting.
`== null` now catches both.

**3. `assertStorable` checked for unexpected fields and never for missing ones.** Only half
the guard existed, and it was the half that stops a *new* field getting in rather than the
half that stops an *old* row being incomplete.

#### The latent hazard that made #3 worth fixing properly

`occurredAt` is the `events` index. **IndexedDB omits a row from an index it has no key for.**
So a row written without a timestamp sits in the store — counted by `countEvents`, which reads
the store — while being invisible to `allEvents`, absent from every export, and unreachable by
`enforceRetention`, which walks the same index.

Such a row would **survive "delete everything older than 30 days" forever and never appear
anywhere**. On a project whose first invariant is about what it stores, a permanently
undeletable invisible row is the worst shape a bug can have.

No build has ever written one, so this is a hazard rather than an incident. It is closed at
the write guard rather than papered over at the readers, and the test asserts both halves:
that the store really does hide such a row, and that `assertStorable` now refuses to make one.

#### What passed, and is now pinned

- **A database left at v4 upgrades to v5**, gains `attention`, and **keeps every event and
  setting the older version wrote**. `openTiseDb` creates only stores it does not find, so
  this was always true — but nothing had ever opened a database that was actually at an
  earlier version, so "it upgrades" was a reading of the code and not a result. An upgrade
  that recreated a store would have deleted a person's entire history silently, on the update
  that introduced it.
- The upgraded database is still **writable**, which a read-only test would not have noticed.
- Settings written before a field existed fill from defaults, and `saveSettings` writes the
  complete object back so the gap does not persist.
- Absent meta keys read as absence rather than as a value: no import, no rejections, no job,
  no model, no coverage.
- An event missing `source` is counted as **imported, not live** — D88's rule holds even for a
  row that predates the field, and guessing "live" would move it to the side allowed to score.

#### What this audit did **not** cover, said plainly

- **Export v1 and v2 read by the current loader.** The extension never imports its own export;
  `research/tests/test_export_load.py` covers that from the Python side, and it stays there.
- **A `features` row from before `fs_2`.** `migrate.ts` handles `fs_2 → fs_3` and is tested.
  Anything older predates the feature store itself.
- **Labels.** The shape has never changed and has no version. If one is ever added, D105's
  rule applies and this file is where the test goes.
- **Two Chrome profiles, or a profile restored from a backup mid-upgrade.** Out of scope, and
  named so that "we checked the seams" is not read as more than it is.

#### The rule this makes permanent

D105 wrote it and D107 applied it the same day: **a stored shape that acquires a version needs
a migration and a test that writes the old shape, in the same commit.** `tests/seams.test.ts`
is now where that test goes, and its docstring enumerates what is covered so the next person
can see the gaps rather than infer them.

Six defects in one day, and the ratio worth recording: five were found by a person looking at
a real browser, one by deliberately going to look. **The audit cost about an hour and found
three. That is a better rate than the screenshots.**

480 TypeScript tests, 831 Python, both linters clean, builds.

### D111 — T-B's feature set, declared and committed unrun

D94 fixed T-B's label, subject, cluster unit, bar and adoption rule before any of it existed.
**It did not fix the feature set**, and that gap is the one this entry closes. Choosing
features after seeing what scores is the forking path pre-registration exists to shut, so
`pr_1` is declared here and the code is committed **before it is run** — the same order D81
used for `fs_3` and D99 for the replication.

#### The label, restated because the details decide the base rate

One label per clock hour boundary `t`: positive if any visit falls in `[t, t + 1h)`.

**Both boundary hours are excluded.** The first labelled hour of a corpus holds the first
visit and the last holds the last visit, so each is positive *by where the data was cut*
rather than by anything the person did. Scoring them would put two free correct answers into
every corpus.

**An empty hour is a label, not a gap.** It is most of this target — a person sleeps — and
dropping empty hours is the T19b defect in a new place, where a block nobody browsed vanished
and lifted every median after it. It is also why D94 made the bar the rhythm: on a target
where a third of the rows are hours somebody was asleep, beating a constant proves nothing.

**The subject is the hour of day *being predicted*.** That is what makes `category_base_rate`
the per-hour rate with no new baseline code, which D94 chose the subject for. Keyed on the
hour Tise stands *in*, the bar would be a rhythm lagged by an hour — a different and weaker
baseline wearing the same name.

**`session_id` carries the calendar day**, because `run_backtest` clusters on that field and
D94's unit is the day. A session is meaningless here: a label exists for 3am whether or not
anyone was awake. Every interval built from it prints `unit="day"`, so the name on the number
is the thing that was resampled — D86 and D87 are both about a right number under a wrong
label.

#### `pr_1` — eight features, and where the model is allowed to win

The set **has to contain the rhythm**. The bar *is* the rhythm, so a model denied the hour of
day could not beat it even in principle, and a test rigged that way is worth nothing in
either direction. `hourSin`/`hourCos` are the cyclic encoding D86 established a plain integer
cannot represent, first used in `bs_1`.

What the model has that the per-hour bar does not, and the only three places it can win:

* **The week** — `isWeekend`. The bar pools every Tuesday 10am with every Sunday 10am.
* **Right now** — `minutesSinceLast`, `visitsLastHour`, `visitsLastSixHours`. Whether the
  person is *at the machine* is the one fact a rhythm cannot hold, and it is the entire
  reason this target is worth asking rather than reading off a clock.
* **Their own recent rhythm** — `sameHourRate7d`, `activeHourShare7d`. A trailing seven-day
  version of the bar, which moves when a routine does. **This is the feature most likely to
  make the fitted model redundant rather than better, and it is in the set for that reason:
  if it carries everything, that is the finding.**

Every scale declared and not fitted (D81); everything unbounded saturated. Only
`sameHourRate7d` is nullable, and its absence is one of *corpus* rather than of behaviour —
in a corpus's first day none of the previous seven days was observed, and filling it with
zero would say the person was reliably absent then, which is the opposite of unknown (D51).
The visit counts are measured zeros: a quiet hour was counted and found empty.

**All `history` compat class.** Unlike `as_2` this needs no dwell and no permission, so it is
shippable the day it clears a bar rather than blocked on T-G. **No TypeScript twin** — the
parity contract binds features the extension computes, and nothing ships until a target is
adopted. Same position `bs_1` was left in at D91.

#### One rival, declared in advance rather than found afterwards

`rhythm_7d` predicts this hour's trailing seven-day rate directly, with no parameters. It is
the two-line-rule version of the whole model.

**This is D102's correction, applied.** D92 and D102 both ended with a simple rule matching or
beating the fitted model, and in D102 `constrained_mode` was only constructed *after* seeing
the result, so it was labelled post-hoc and could not touch the verdict. Writing this one down
first means that if it wins, the win counts.

It is **not** the bar. D94 fixed the bar before anything was fitted, and promoting a rival
afterwards would be choosing the rule from the result.

#### Predictions, recorded now

1. **The model separates from a flat rate on all three corpora**, by day-clustered intervals
   excluding zero. D94 said this half is easy, which is why it is not the bar.
2. **It does not clear the bar on Edge.** This is D94's prediction 3 restated so this run
   scores it automatically. D94 also named it as the prediction most likely to embarrass.
3. **`rhythm_7d` is not distinguishable from the fitted model on any corpus.** That would be
   the fifth time a model-versus-simple-rule comparison came back not distinguishable (D80,
   D92, D102, D109's scorecard, this) — and the consistency has become the project's most
   replicated finding.
4. **`minutesSinceLast` is the largest single coefficient, larger than either hour term.**
   This is the risky one. If the rhythm terms dominate, the target is a clock and the model is
   decoration; if recency dominates, the model is measuring presence and the interesting
   question is why that is not enough to clear the bar.
5. **The base rate lands between 25% and 45% on every corpus.** A sanity check on the span
   rather than a claim: much higher and empty hours are being dropped somewhere.

#### What this cannot decide

T-B is not a route around D94's stopping rule. **T-A already separated**, so the rule is not
triggered either way, and a T-B failure is published as a failure exactly as D92 and D102's
were. Nothing here changes what Tise ships: the extension trains `return_24h` and shows a
descriptive card.

25 tests, and the leakage guard was broken deliberately once — widening the count window past
the boundary — and confirmed failing before it was reverted.

### D112 — T-B clears its bar, and 79% of the rows say otherwise

`analysis/browsing_next_hour.py` ran against the three corpora. Report at
`docs/benchmarks/browsing-next-hour.md`.

**Edge, the adoption corpus D94 named before anything was fitted: +0.0546 [+0.0383,
+0.0724]**, day-clustered, n=55, 5 of 5 folds. The interval excludes zero in the model's
favour, which is D94's rule verbatim. Chrome clears it too (+0.0190 [+0.0063, +0.0341],
n=35). Firefox does not (+0.0023 [-0.0034, +0.0078], n=24), and on Firefox the model does
not separate from *anything*, including a flat rate — 915 events over 38 days is a browser
barely used.

**So D94's third prediction is wrong**, and D94 named it as the one most likely to
embarrass: *"circadian rhythm is nearly all of the signal, and a model that adds
recent-activity features on top of it will find little left."*

#### Then the slice, and it changes what the number means

`minutesSinceLast` came out at **-1.312 on Edge, three times the next largest weight**, so
the report asks the question that invites: *isn't this just "were you browsing a minute
ago"?* Two post-hoc checks answer it, both labelled post-hoc, neither able to touch the
verdict — D102's rule, applied.

**`previous_hour`, a two-cell rate table** — the rate given the previous hour held a visit,
and given it did not — **beats the 24-cell rhythm on all three corpora**, and beats the
fitted model on Firefox. The model separates from it on Edge alone, and the margin collapses
from **+0.0546 against the bar to +0.0109 against two cells**.

**And splitting the test rows says where the rest of it lives.** 276 of Edge's 1,290 pooled
test rows follow an hour that already held a visit: the person is mid-session and the
per-hour rate has no way to know. On the **other 1,014 — where *will you be here?* is a real
question — the model does not separate from the bar at all:** -0.0018 [-0.0052, +0.0016].
The entire pre-registered margin is earned on the 21% of hours whose answer was already
obvious.

**D94's prediction is therefore wrong on the letter and right on the substance.** Circadian
rhythm plus *are you here right now* is the whole signal, and the second half is the half
that answers itself.

#### The method note, and it is the one this run is worth keeping for

D102 left one: *ask a floor one question before registering it — can it produce a legal
answer on every row?* This run adds its sibling:

**Ask whether the rows a bar is scored over include rows where the question answers
itself.** A bar is beaten either by being better on hard rows or by there being enough easy
ones, and a single pooled interval cannot tell those apart. Both bars this project has now
registered were sound as *definitions* and wrong about **which rows would decide them** —
D94's floor was handicapped by the label definition, and this one is diluted by the row
population. Registering the bar is not enough; the slice has to be registered with it.

#### The declared two-line rule lost, and that is informative

`rhythm_7d` — this clock hour's trailing seven-day rate, declared in D111 *before* the run
specifically because D92 and D102 both ended with a simple rule winning — **lost, on all
three corpora, and lost to the bar as well.** Seven binary observations per estimate against
the bar's ninety days: it is a noisier version of the same rhythm, not a smarter one.

That is the argument for declaring rivals in advance rather than constructing them
afterwards. A post-hoc rival is only ever built when it looks like it will win, so a
project that only builds them post-hoc learns nothing on the runs where the simple rule is
bad. This is the first such run, and it is only visible because the rule was written down
first.

#### D111's five predictions: none held cleanly, one held on the adoption corpus

1. **Failed.** Separation from a flat rate on all three — Firefox includes zero.
2. **Failed.** It cleared the bar on Edge.
3. **Failed.** `rhythm_7d` was not merely distinguishable, it was beaten decisively.
4. **Held on Edge, failed elsewhere.** `minutesSinceLast` is the largest weight on Edge
   (-1.312); on Chrome and Firefox the two hour terms are larger and recency is third. The
   risky prediction, and the corpus split is itself a finding: the browser he uses most is
   the one where presence beats rhythm.
5. **Failed.** Base rates are **16.3% / 13.0% / 11.2%**, against a predicted 25-45%. A
   sanity check on the span rather than a claim, and it says the span is being labelled
   correctly — most hours of most days hold no browsing at all in any single browser.

D100 recorded that a pre-registration where everything lands is evidence the predictions
were too cautious. This is the opposite case and the same lesson: five wrong predictions
bought a sharper result than five right ones would have.

#### What ships: nothing

`pr_1` is `history` compat — no dwell, no permission — so unlike `as_2` it is shippable the
day it is worth shipping. **It is not worth shipping.** The surface a person would want is
*"you'll be back around 9"* after a quiet stretch, which is exactly the slice where the
model does not beat a per-hour rate that needs no training at all. If any of this reaches
the extension it should be the rhythm table, for the same reason D103 shipped counts rather
than the fitted transition table.

**D94's stopping rule is not triggered and was not going to be** — T-A separated at D97, so
the rule retired before T-B ran. T-B is recorded as an adoption under the rule as written,
with this entry as what the adoption is worth. Nothing about what Tise trains or shows
changes.

#### Machinery

`BacktestResult` gains `pooled_label_ids`, aligned with `pooled_outcomes`. Without it a
pooled row could not be mapped back to the feature that produced it, so any analysis could
score every test row and never an interesting *slice* of them — which is the number this
entry turns on. Empty for emitters that supply no id.

Also worth recording: `same_as_last` scores **0.2932 on Chrome against a 0.1377 flat rate**,
its worst showing in the project. D92 found the same baseline failing at the daily-block
level and concluded "above your usual" is close to independent day to day. At the hourly
level persistence is enormous — `previous_hour` is the second-best model on every corpus.
**Same mechanism, opposite sign, one timescale apart**, and `same_as_last` fails here for a
third reason: it is keyed on the subject, which for this target is the hour of day, so it
repeats what happened at 3pm *yesterday* rather than what happened an hour ago.

858 Python tests, 480 TypeScript, both linters clean.

### D113 — T-E and T-F: one real split that is not a type, and one clean absence

Both were adopted in D95 from an outside plan, both **descriptive**, and neither has a
prediction bar to clear — which D95 named as the point of them, given D92's finding that a
per-topic rate table is very hard to beat. **D24 still applies**, and most of the work in both
was building the baseline an unsupervised method needs, because neither has an obvious one.

Reports: `docs/benchmarks/session-types.md`, `docs/benchmarks/domain-associations.md`.

---

#### T-E — the sessions do split, and the split is size, not kind

**All three corpora give the same two clusters at k=2**, with the same story: brief
single-domain check-ins against long multi-domain sittings.

| | Chrome | Edge | Firefox |
|---|---|---|---|
| Check-ins | 2 visits, 1 domain, 0 min (52%) | 3 visits, 1 domain, 1 min (47%) | 2 visits, 1 domain, 0 min (61%) |
| Sittings | 20 visits, 4 domains, 24 min (48%) | 26 visits, 3 domains, 46 min (53%) | 14 visits, 4 domains, 17 min (39%) |

**Stability 0.90-0.97** — the same sessions land together again across subsamples, which is
the property the word *recurring* asserts and a silhouette does not test.

**But it is a magnitude split, and the script computes that rather than leaving it to a
reader.** Every separating feature moves the same way at once: the cluster with more visits
also has more domains, runs longer, revisits more and spreads across more categories. That is
one behaviour at two scales. D95's outside plan guessed the types would be *research, routine
checking, entertainment, exploration* — differences of **kind**, in what the person was
doing. **Nothing here distinguishes kind.** The report names no cluster, deliberately: a name
printed beside a measurement reads as part of it.

**And they happen at the same times.** Evening shares differ by 1-6 points and weekend shares
disagree in direction across corpora. Time of day was **held out of the clustering on purpose**
so that this question could be asked at all — a clustering handed the clock recovers
morning-versus-evening and presents it as a discovery about session types. Holding it out
converted an input into a question, and the answer is no.

#### The first null was too weak, and every k passing it is what exposed it

The obvious baseline permutes each feature column independently: every marginal kept, every
correlation destroyed. **Every k from 2 to 8 cleared it on every corpus**, which is not a
finding, it is a warning. Visits, domains and duration all move together, and correlated
features concentrate the points near a lower-dimensional surface — that **raises the
silhouette on its own, with no discrete groups anywhere**. Clearing that band says the
features are related, which was never in doubt.

So `gaussian_null_band` was added: draws from a **single** multivariate normal matching the
observed mean and covariance — one mode, same shape, same correlations, via a hand-written
Cholesky. Excess above *that* is evidence of more than one group, which is the claim a
"type" makes. Edge k=2 is 0.346 against a one-mode band of [0.238, 0.297]. Both bands are
printed, because they answer different questions and one number would conflate them.

**The remaining confound is stated on the page**: the one-mode null matches the covariance,
not the marginal shapes, and session features are skewed and partly discrete — a one-visit
session has a repeat rate of exactly zero, so there is a real point mass in a corner. Some
excess may be skewness rather than a second mode. **Stability has no such assumption and is
the sturdier number.**

---

#### T-F — nothing co-occurs more than independence predicts, anywhere

**No corpus beats chance, at either level.** Chrome 8 domain rules against a chance band of
[1, 9]; Edge **2 against [2, 12]** — fewer than chance; Firefox 4 against [0, 4].

**Categories are the cleaner result because they are the level with enough data.** Strongest
lift at any confidence: **1.37 / 1.24 / 1.00**. Not a near miss against the 1.5 threshold — an
absence. Category co-occurrence inside a session is essentially independent.

**That is D104's hub finding arriving from a second direction.** D104 found 9 of 10 topics
lead most often to `search`. An item present in most sessions co-occurs with everything at
roughly its own base rate, which is lift 1.0 by definition. A hub does not merely make
conditioning useless for *prediction* (D102's mechanism); it flattens co-occurrence
*structure* too. Two analyses, different methods, same shape underneath.

**The domain level is starved rather than negative, and the report says which.** 226 domains
over 88 multi-domain sessions leaves **15 pairs** dense enough to judge at all. The high lifts
there (up to 9.6 on Chrome) are ratios of small integers, and the count sits inside the chance
band. Coverage is the number that settles it: rules speak to **7-51%** of sessions, and on
Edge to 7%.

#### The privacy split is the design of T-F, not a caveat on it

A ranked list of a person's domains **is a profile of that person** (invariant 2, D22), and
this repository is public. So the committed report carries counts, spreads, coverage and the
comparison against chance, plus **category rules in full** — the fifteen categories are a
public vocabulary shipped in `domains.json`, not a fact about anyone. The domain rules
themselves go to gitignored `data/domain-rules.md`, the split D100 used for the replication
report. `test_published_reports.py` passes on both new reports, and the committed pages were
grepped for host-shaped strings by hand as well.

The public half is also the half that generalises: *how much co-occurrence structure does one
person's browsing contain* is answerable without naming a single site.

---

#### What both have in common, and it is the transferable part

**Neither method can fail on its own.** k-means always returns k clusters and gives noise a
positive silhouette; a rule miner always returns rules and confidence is high for free
whenever the consequent is common. Both would have produced a page of confident-looking
output on data containing nothing. **The entire value of both analyses is in the null**, and
in T-E's case the first null was wrong and only the implausibility of the result — every k
clearing on every corpus — said so.

**A method that cannot come back empty has not been tested; it has been run.** Every test file
here therefore asserts both directions: the null is beaten when structure was planted, and
*not* beaten when it was not. Writing the second half caught a bad fixture immediately — an
arithmetic pairing meant as "unstructured" pairs each item with exactly one other, and the
null correctly found 16 rules against a band topping out at 2. The fixture was wrong and the
baseline was right, which is the outcome that pair of tests exists to be able to produce.

#### Nothing ships from either

T-E's split is real and is "long sessions are long". T-F found nothing above chance. Neither
needs a permission, both are `history`-class, and neither is worth a surface. **D95's two
candidates are now measured and closed**, which is the result: the outside plan's remaining
untested recommendations should be read against these two before any of them is adopted.

893 Python tests, 480 TypeScript, both linters clean.

### D114 — T15: the disclosure is generated from the manifest, because this project has shipped the alternative twice

Onboarding and privacy settings. The interesting decision is not that a welcome page exists;
it is that **nothing derivable on it is typed**.

#### The defect this is built to prevent, which has already happened twice

T18b found the README describing a `service/ Local Python service` that does not exist and
was explicitly rejected — so a reader auditing the privacy claim saw a local server in the
layout. D98 found `reports.py` labelling twelve benchmarks with a target D92 had retired two
decisions earlier. Both were hand-written statements about a system that had moved out from
under them, and both were caught late by someone reading rather than by anything failing.

**An onboarding page is the worst possible place for that failure**, because it is the one
artifact whose entire job is to be believed *before* the reader can check anything. Everyone
else in this repository can go and look at the code; the person deciding whether to install
cannot.

So `src/model/disclosure.ts` holds the permission explanations as data, and
`disclosure.test.ts` checks them against `manifest.json` **in both directions**:

* a permission the manifest requests with no plain-language entry **fails the build**;
* an entry for a permission no longer requested fails too — a stale paragraph claims access
  the extension does not have, which is the mirror of the dangerous case and still false.

The same rule covers what is stored: `STORED_FIELDS` is checked against `EVENT_FIELDS`, so a
new field on `TiseEvent` cannot reach the database without reaching this page. And the
never-requested list is pinned to `manifest.test.ts`'s own forbidden list, so a capability
cannot be added to the guard while the page carries on not mentioning it.

**Broken deliberately**: adding `bookmarks` to `optional_permissions` failed 4 of 14 tests,
including *"names nothing the manifest actually requests"* — the assertion that catches a
page telling a reader Tise does not do something it does.

#### What is not derivable, and how it is guarded instead

"Tise never transmits anything" is not a property of the manifest — no permission is needed
to call `fetch`. It cannot be derived, so it is stated and pinned by the existing source scan.
The file says which of its claims are generated and which are asserted, rather than presenting
both as one kind of promise.

#### Three smaller decisions inside it

**Every permission says what it does *not* allow.** Every Chrome permission grants more than
any one extension uses, and the gap between what the permission can do and what Tise does
with it is exactly what a careful reader wants and almost never gets.

**Every optional permission says what declining costs.** D33 measured that Chrome focuses
**Deny** on its dialog. A page that only argues for "yes" is a sales pitch, and someone
deciding needs the price of "no" as plainly as the price of "yes". The test asserts each
optional capability carries one and each required capability does not — there is no choice to
describe for a permission granted at install.

**The page stays reachable after consent, and does not replace itself with a success screen.**
Someone who has just agreed to something is exactly the person most likely to want to re-read
what they agreed to.

#### Nothing is written before consent, and that included the obvious flag

The install state has to be genuinely empty, not merely unused. The obvious way to open a
welcome page once is to write down that you have opened it — **and that flag would be a stored
fact about a person who has not agreed to Tise storing facts about them**, indistinguishable
from consent to anyone reading the database.

Chrome's `onInstalled` reason does the job for free. `reason === "install"` only: an update
must not reopen it, because reopening a consent page every release trains a person to dismiss
it, which is the opposite of informed. `onboarding.test.ts` asserts no marker is written, that
updates cannot reopen it, and — driving the real storage layer through the real gate — that
after a refused navigation there is **no settings row at all**, not a settings row saying no.

That last one is stronger than what was previously asserted. "Nothing is stored before consent"
has been a claim since D37, and the tests behind it were about the collector refusing an event.

#### The settings panel, and a field that had been dead since T6

Retention (0 = forever), the session gap in minutes, pause, export, delete-everything, and the
**site-override editor**. `overrides` has been on `Settings` since T6, is carried by the export
(D45), and had **no way to set it** — so "the user is always right about their own browsing"
was a comment rather than a feature.

**`settingsError` validates at the choke point rather than in the UI.** A page that forgot to
check would write a one-second session gap, and every session-derived feature in the project
would silently start describing something else — D17 declared that timeout a hyperparameter,
and D97 made it load-bearing a second way by clustering intervals on sessions. A URL in an
override is refused for the same reason: settings ride in the export, and invariant 2 has no
exception for a path someone typed themselves.

Retention above ten years is refused rather than accepted, so "keep forever" keeps exactly one
representation. Two ways to say almost the same thing drift apart in every place that
special-cases zero.

#### And the popup was lying

*"Developer view — the real interface arrives at T14"* was the first sentence anyone installing
Tise would read, and it stayed there for two days after T14 shipped the dashboard. Same defect
class as the two above, in the smallest possible form. It is derived from state now.

**Owed by Akash: install on a fresh profile.** T15's own verification is a real install. The
automated half proves the store is empty; only a browser can show the welcome tab opening.

509 TypeScript tests, 893 Python, both linters clean, builds.

---

### D115 — T17: a green suite is not evidence the parity suite ran

CI. Both suites, both linters and the build, on every push and pull request. That part is
unremarkable and is not what this entry is about.

#### The parity suite has been CI-blocking since T3, in a repository with no CI

`pyproject.toml` has said so in writing since T3: *"parity: TypeScript/Python feature parity.
CI-blocking from T17."* For fourteen tasks the enforcement was **someone remembering to run
it**, and it held — the suite has been green every time it was checked. Habit is not a
control, though. It is a control that happens to be working.

So the obvious workflow would be `npm test` and `uv run pytest`, and the parity tests are
inside both. That is enough for the failure everyone pictures — a feature drifts, assertions
fail, the build goes red — and it is not enough for the failure that actually threatens this
project.

**A green suite proves the tests that ran passed. It does not prove the parity tests were
among them.** Deselected, skipped or deleted, they leave a build that is green and a claim
that is unsupported, and the pressure points that way: when a parity test fails, the cheapest
route to green is to stop asking the question. That is not hypothetical laziness, it is what
`.skip` is *for*.

Measured, not asserted. Marking one TypeScript parity test `.skip`:

* `npm test` — **`508 passed | 1 skipped (509)`, exit 0.** Green. The count is even printed,
  in yellow, and it is the sort of thing a person scrolls past on a passing build.
* The parity step — **fails**, because it reads the run's own report and refuses a non-zero
  skip count.

So parity runs a second time as its own step in each language, against a committed floor on
how many tests it contains: **18 in Python, 57 in TypeScript**. A floor, not a fixture —
growth is free, and shrinkage has to survive a diff someone reads. The TypeScript step also
refuses any skipped test outright, which is the standing rule (*never mark a parity test
`skip` or `xfail`*) enforced for the first time by something other than the rule.

**Broken deliberately**, as the parity contract requires. Relaxing the leakage guard in
`features/recency.ts` from `>=` to `>` — one character, the difference between filtering
strictly before `windowEnd` and including it — fails 12 of the 57.

#### "Secret scanning" is the wrong name for what this repository can leak

T17's acceptance criteria say secret scanning, and the generic kind is here because it costs
nothing: AWS ids, GitHub tokens, private-key headers, and a test that plants one to prove the
scanner can match. Tise has no credentials, and a repository that never holds a secret is
exactly the one where a stray token would sit unnoticed, because nobody is looking.

But that is not the exposure. What this repository can leak is **a copy of one person's
browsing**, and invariant 5 has been enforced by `.gitignore` and by care.

`.gitignore` is a list of patterns someone thought of in advance, and D97 recorded the time
nobody had: running `analysis/history_shape.py` from `research/` wrote a fresh copy of the
live Chrome history to `research/data/`, which the anchored `/data/` rule did not cover. It
was never committed. Nothing except noticing stood in the way.

`test_repository.py` asks the other question. Not *is it ignored* but **is it tracked** —
because `git ls-files` is the truth about what would be published, where an ignore rule is
only a prediction about it. Every forbidden shape carries the reason it is forbidden, and it
runs on every local `uv run pytest`, not only at push, so it bites while the mistake is still
a working-tree file.

**The first draft of that guard was wrong in the exact way the file it protects warns about.**
An unanchored `data/` pattern flagged seven source files under `research/tise_research/data/`
— the Chrome, Firefox and corpus loaders — and the cheapest way to silence that noise is to
weaken the rule guarding the real directory. `.gitignore` carries a comment about this trap
because it fell into it once already. The anchoring now has its own test, so the lesson does
not have to be learnt a third time.

#### Audit what ships, not what builds

`npm audit` reports five advisories, all reaching back to one root: esbuild's development
server, through vite, through vitest. None of it ships — the extension's `dependencies` is
one package — and Tise never runs that server: `npm run dev` is `vite build --watch`.
Clearing them means vite 8, a breaking change to the build.

A gate that is red for a reason nobody can act on is a gate people learn to pass with
`--force`. So the blocking audit is `--omit=dev`, which is the code that would actually reach
a browser, and the full audit runs beside it reporting and not blocking. Dependabot handles
the rest weekly — on GitHub's side, so checking for vulnerable dependencies does not itself
add a dependency, and an advisory arrives as a pull request that has to pass CI rather than
as a red build on unrelated work.

#### What CI does not check, stated rather than implied

* **T2's coverage criterion does not run.** `TestCoverageAgainstRealBrowsing` is parametrised
  over `data/history-*.copy`, which invariant 5 forbids committing, so it collects zero tests
  there. **908 locally, 905 in CI**, and the gap is exactly that. It is the shape of this
  project: the strongest evidence is the least publishable.
* **"Never transmits" is still a source scan**, not a property of the manifest (D114). No
  permission is needed to call `fetch`. CI runs that scan; it does not upgrade it.
* **A real install is still owed.** CI can prove the store is empty on a fresh database. Only
  a browser shows the welcome tab opening.

#### Two things deliberately not done

**No formatter.** Prettier would rewrite 67 files and `ruff format` 76. Adopting one is a
reasonable decision and it is not this one; folding it in would make a single commit that
both adds CI and rewrites the repository, and neither half would be reviewable.

**Ubuntu only.** Windows is where this is developed and where the suites run many times a
day. Linux is the platform nothing has ever checked, and it is where anyone cloning this
will run it.

#### Owed by Akash

**There is no remote.** T17's stated verification — *a pull request with a deliberate parity
break is blocked* — needs one, and every command in the workflow has been run locally in the
order the workflow runs them, with the break confirmed. What remains unproven is that GitHub
runs them, which is a push away.

With the remote: turn on branch protection for `main` requiring both jobs, turn on secret
scanning and push protection (repository settings, not a workflow), and the README gets its
badge — deliberately not written yet, because a badge URL guessed at a repository that does
not exist is the hand-typed claim about a system that moved, which D114 is entirely about.

908 Python tests, 509 TypeScript, both linters clean, builds.

---

### D116 — T-G4: the gate is measurable for the first time, and it does not pass

The first export carrying real attention arrived. T-G's gate has been *"enough live spans to
train on — not a date, a count"* since D96, and the count was never fixed. It is fixed now,
and this entry is mostly about where it came from, because that is the part that could
easily have gone wrong.

#### The gate is D99's, and choosing it today would have been the failure

D99 declared an eligibility rule before the D100 replication ran: **at least 1,000 visits, 20
sessions and 200 labels** for one person to be worth fitting this model on. It was declared
on 2,148 strangers, months before this profile recorded a single span, and **822 of those
people were excluded by it**.

Reusing it means the threshold this profile is measured against was chosen by someone who
could not have seen this profile's numbers. Inventing a fresh one now, with the answer
already on screen, is precisely what pre-registration exists to stop — and it would have been
easy, because the honest-sounding version ("enough to train on") has no defence against being
quietly set at whatever today happens to be.

`analysis/engagement_gate.py` **fits nothing**. It counts and stops, which is D88's rule for a
data-sufficiency gate: measured from quantities that carry no score information, so there is
nothing available to bias it with. Every number it prints would be identical if the model did
not exist.

#### Two translations, both of which would have passed a criterion that should fail

The rule was written for a corpus where **every** visit carries a duration. This profile is
not that, and the two places the difference hides are named in both mirrors:

* **Visits means dwell-carrying visits.** Imported history has no dwell and never will (D35,
  the duration trap). Counting all 3,918 stored events would clear a 1,000-visit bar on data
  that cannot answer the question. The honest count is **192**.
* **Sessions means sessions holding a label.** The bootstrap clusters on sessions and a
  cluster with no rows in it is not a cluster. All sessions is **107**; sessions holding a
  label is **18**.

Both looser readings pass. Both are wrong. Neither would have looked wrong in a report.

#### Where the profile stands

```
  no    dwell-carrying visits         192 / 1,000   (19%)
  no    sessions holding a label       18 / 20      (90%)
  no    labels                        134 / 200     (67%)
```

**The gate does not pass on any of the three.** At 49 dwell-carrying visits a day over the
3.9 days attention has been collected, the binding criterion is about **16 days** away.
Labels are deliberately *not* projected: they arrive faster than linearly while categories
are still crossing their ten-visit threshold, and a straight line through that is a forecast,
not a count.

The composition is the more interesting half. Of 134 labels, 53 are `unknown` — excluded from
headlines by D27 — and of the 81 that remain, **75 are `search`**. **93% of the usable labels
are one category.** A model trained on this would be a model about one topic wearing the name
of a general one, and no count-based gate would have said so; only looking at the split does.

#### A correction, because it changed the conclusion

The first reading of this export reported "six categories clear ten dwelled visits" and
treated the gate as met. That counted **spans**, not visits. There are 367 spans across 192
visits — 1.9 each, because a revisited page opens a new span and D96 sums them deliberately.
Per *visit*, only `search` (85) and `unknown` (63) exceed ten; `travel` has 15 and `learning`
11, and everything else is under ten and produces nothing at all.

The corrected count is what the labeller actually consumes, and it moves the answer from
"ready" to "19% of the way there". Recorded because a gate that was reported as passing on a
miscount is the same defect as one that was set after seeing the data.

#### What was built, and the one thing deliberately not built

`src/model/engagement.ts` computes the same gate **in the extension**, over the real store.
Not for convenience. D101: attention collection shipped gated on a permission Chrome never
grants at install, the span store stayed empty for two days, every note described collection
as running, and the count that would have exposed it existed nowhere a person could see. **A
gate whose progress is invisible is indistinguishable from a gate that is broken.**

It also means the label path is *exercised*. `attachDwell` and `attentionExamples` now run
every time the popup opens, weeks before anything is trained on their output. Both languages
were run over the same real export and agree exactly — **192 / 18 / 134**, and the same
per-category split — which is a stronger check than the fixture, because the fixture was
built to be agreed on.

**The popup was lying, in the same way the popup was lying at D114.** *"Predictions need
roughly ten measured visits per topic before they begin"* shipped in D101. Ten per topic is
when a **label** becomes possible; it says nothing about when a model may be trusted, and it
was wrong by more than an order of magnitude. It is derived from the gate now, and
`engagement.test.ts` reads the Python constants and fails if the two sides drift — verified
by lowering `MIN_LABELS` on one side, which failed 2 of 10.

**Training and prediction were not built.** They are the rest of T-G4 and they stay unbuilt
on purpose. The gate is at 19% of its binding criterion, so a training path written today
could not run against real data for a fortnight — and a path that cannot be exercised until
the day it matters, while every record describes it as ready, is D101 exactly. The gate is
the part that can be watched working today, so the gate is the part that shipped.

**T-G4 is not done.** It is gated, by a rule fixed before the data existed, on a count that
is now measured, visible on the device, and roughly two weeks out.

917 Python tests, 519 TypeScript, both linters clean, builds.

---

### D117 — Icons, generated rather than drawn, and honest about being placeholders

Tise had no icons at all. `extension/icons/` held a `.gitkeep` and the manifest had no
`icons` key, so Chrome fell back to what it always does — a grey tile with the first letter
of the name. That is what has been in every screenshot of this project since T5.

Four PNGs is a small thing. Two decisions inside it are not.

#### They are produced by a committed script, not drawn once

Four binaries nobody can regenerate are four binaries nobody can change: the day the accent
colour moves or a fifth size is wanted, the only options are to redraw by hand or to live
with the drift. `extension/icons/generate.py` writes them, and `test_icons.py` asserts that
**regenerating reproduces the committed bytes**.

That is the same guard as `test_parity_fixture.py` and it is here for the same reason.
Without it the generator becomes a comment: someone opens a PNG in an editor, nudges it,
and the file on disk and the script that supposedly produces it describe different marks
with nothing to say so. **Broken deliberately** — one byte flipped in `icon48.png` failed
the 48 case and nothing else, which is the resolution wanted.

**No new dependency.** Neither toolchain has an image library and this is not a good enough
reason to add one, so the PNGs are written with `zlib` and `struct` from the standard
library. Flat shapes, six-by-six supersampling for the edges, deterministic compression
level so the bytes are stable across runs.

#### The palette is the product's, and a test says so

`#1f6feb` is `--accent` from `ui/popup/popup.html` and the mark is `--bg`. An icon in
colours nothing else uses is a second brand.

The generator's docstring *claims* that. A claim about a value in another file is exactly
the kind that stops being true silently, so `test_icons.py` reads `popup.html` and compares.
**Broken deliberately**: changing the accent by one hex digit failed 5 of 13 — the palette
pin, and all four regeneration cases, because the rendered bytes moved too.

#### The mark says what Tise actually is

Three ascending bars, the third at 42% opacity. It is a chart, which is what Tise is, and
the faded bar is the part Tise does not claim to know.

That is not decoration. It is the honest description of where this project stands: what it
shows a person today is descriptive — counts with their denominators — and the one target
that earned adoption is not switched on, because D116 measured its gate at 19%. If that
changes, the last bar can fill in.

#### Checked in both directions, like the disclosure

`manifest.test.ts` asserts every icon the manifest names exists, carries the PNG magic, and
declares the size it is named for — read out of the IHDR, so a 32px file renamed to
`icon128.png` fails. It also asserts the reverse: **no PNG on disk that the manifest does
not name**, which is how a half-wired fifth size would announce itself.

And one more, because the manifest can name a path that only exists in the repository:
Chrome loads `dist/`, so the test reads `vite.config.ts` and requires every icon to be in
the copy list. An icon the build forgets is missing exactly where it matters and nowhere
that would fail.

#### They are placeholders and the record should keep saying so

Tise is a showcase for Holy Cow Studios, and what represents the company in the Chrome Web
Store is a branding decision rather than a rendering one. **A placeholder that ships is a
placeholder forever**, and the only defence against that is writing down that it is one.
Replacing them changes no code: the manifest names the files, and `generate.py` can be
deleted the day real artwork exists.

930 Python tests, 524 TypeScript, both linters clean, builds with the icons in `dist/`.

---

### D118 — No screenshot is published, and the rule that allowed eleven is the finding

Akash, 2026-09-03: *"no screenshot gets on github. no credential or secret goes on github.
delete the screenshot folder in tise."*

Eleven screenshots were tracked. They are gone from the working tree, gone from every
commit, and the folder has been moved out of the repository entirely.

#### The old rule was an allow-list, and it had already passed review

`.gitignore` ignored `Screenshots/**` and re-admitted the eleven T5 spike files one pattern
at a time. That scheme was itself a fix: an earlier version named files to *exclude*, which
meant every new screenshot was publishable unless someone remembered to add a pattern, and
a T11 export of 5,105 real domains once sat untracked-but-publishable under it.

The replacement was better and still wrong, because it kept the same dependency: **a person
correctly classifying each image.** The eleven were classified as safe on the reasoning that
the spike ran in a throwaway profile. The *profile* was throwaway. The *browsing* was not.

`ss_checkgain3.png` and `ss_checkagain3.2.png` are the spike panel photographed over a live
Booking.com hotel search — a named hotel, a destination, a map — and the first carries a
**full URL with tracking parameters in the address bar**, in the repository whose headline
claim is that no full URL is ever stored. Nine of the eleven were genuinely fine, which is
the problem: the rule worked nine times out of eleven and that is not a rule.

**Nothing leaked.** There is no remote yet. The finding is about the rule, not the damage,
and it was caught by looking rather than by anything failing — the same way D101 and T18b
surfaced.

#### Moved out of the repository, not merely ignored

The folder now lives at `../Tise-evidence/`. A `.gitignore` entry is a promise that every
future rule in that file will stay correct; a file that is not in the working tree cannot
be committed by any mistake in it. The images are kept rather than destroyed because
`docs/permissions.md` and `DECISIONS.md` cite them by name, and deleting the evidence for a
published claim to protect it is the wrong trade.

`docs/permissions.md` now says they are held outside the repository, lists what each showed,
and says why they are not here. It also records the thing that makes their absence cheap:
**every verdict in that document is reproducible from `spike/permissions/` in about fifteen
minutes**, which was always the stronger evidence. A screenshot shows what happened once on
one machine; the spike shows it happening on yours.

#### The rule that replaced it, and the shape it deliberately avoids

`.gitignore` ignores `Screenshots/` and **does not ignore `*.png`.** Tise's own icons (D117)
are product assets and must ship. A blanket image rule with an exception carved out for them
would be the identical allow-list shape that just failed — and its failure mode is worse in
one way: a silently missing icon, where nothing says anything went wrong.

So the rule lives in `test_repository.py` instead, and it is an allow-list of four exact
paths rather than a pattern:

* **no tracked image except the four icons** — anything else is a screenshot until proven
  otherwise, and this entry is what "proven otherwise" cost last time;
* **those four are still tracked** — the mirror, because a guard against publishing images
  is one bad rule away from an extension that ships with no icon, and `manifest.json` names
  all four.

A test fails loudly and prints the offending paths. An ignore rule fails by quietly dropping
a file, which is how the icons would have gone missing.

#### History, purged

The eleven were in all 78 commits, so removing them from `HEAD` would have published them
anyway on the first push. `git filter-branch` over every ref removes the blobs from history.

Cheap, and checked before doing it rather than after: **no committed file cites a commit
SHA**, so rewriting every hash costs nothing that this project relies on. A backup tag was
taken first.

#### The other two instructions were already enforced

*No credential or secret* — `test_repository.py` has scanned every tracked text file for
AWS ids, GitHub tokens, private-key headers, Slack and Google keys since D115, with a test
that plants one to prove the scanner matches. *No screenshot* is now the same kind of rule:
enforced by something that fails, not by remembering.

932 Python tests, 524 TypeScript, both linters clean, builds with the icons in `dist/`.

---

### D119 — The published identity: one address, in all 81 commits, decided before the first push

Akash, 2026-09-03: the repository goes public, private first to watch CI go green once, and
the commits carry **`office@holycowstudios.in`**.

Every commit permanently records an author and a committer. All 81 carried
`Akash <akashnavet@outlook.com>`, which on a public repository is a personal address in
machine-readable form — scraped for spam, and the project's default contact route forever.

**Why it had to be settled before the first push and not after.** The address is an input to
each commit's hash. Rewriting 81 commits costs seventy seconds today; after publication,
clones and forks keep the old one regardless of what this repository later says. It is one
of the few decisions here that is genuinely irreversible in one direction only.

`office@holycowstudios.in` rather than a GitHub noreply address, because Tise is a showcase
for Holy Cow Studios and the Web Store developer account goes under the company identity
(D13). A company address makes the repository, the listing and the privacy policy agree, and
it keeps the project contactable — a noreply address is more private and closes the only
route a reader has to ask a question.

The author name was set to **Akash Navet** in the same pass, matching the LICENSE (D47).
`Akash` alone was what git happened to be configured with.

**One step is owed on GitHub's side and it is not cosmetic**: `office@holycowstudios.in`
has to be added and verified on the account. GitHub links a commit to a profile by matching
its email against the account's verified addresses, so without it all 81 commits render as
an unlinked name with no avatar and count toward nothing. *Keep my email addresses private*
and *Block command line pushes that expose my email* belong in the same visit — the second
is a hard stop against a future commit carrying the personal address again, which is exactly
the kind of thing that comes back after being fixed once.

Local git config in this repository now carries the same identity, so no future commit has
to remember.

932 Python tests, 524 TypeScript, both linters clean, builds.

---

### D120 — CI's first run found two bugs, and one was in the parity suite

The repository was pushed to `holycowprojects/tise`, private. CI ran for the first time and
**the research job failed**. That is T17 paying for itself on the first attempt: both
failures are real, both are Linux-only, and both had been passing on Windows for months.

#### The parity oracle was not reproducible across platforms

`test_regenerating_the_expected_output_reproduces_the_committed_file` compared the
regenerated oracle to the committed one with `==`. On Ubuntu it produced
`-0.3226722826296328` where Windows produced `-0.32267228262963277` — the same number to
sixteen significant figures, differing in the seventeenth.

**The cause is `libm`.** `logreg.py` is hand-written gradient descent over `math.exp`, and
`exp` comes from the platform's C library — glibc on Linux, the CRT on Windows — which are
each permitted to be out by a unit in the last place. Gradient descent carries that through
every iteration. Nothing about the model, the features or the fixture is wrong.

**The parity contract itself was never in danger.** Its tolerance is 1e-9 and this noise is
~1e-16. What could not survive a platform change was the *freeze* test's exact equality —
a check written on a machine where exactness happened to be free.

So the freeze comparison is now **exact on structure and 1e-12 on floats**: keys, lengths,
ordering, strings and `null`-versus-zero all still fail on any difference at all, and only
float magnitude gets a tolerance. 1e-12 is four orders above the libm noise and **three
orders below the 1e-9 the parity contract allows**, so the freeze check remains strictly the
tighter of the two — a drift small enough to pass it could not reach TypeScript comparison
either.

**That is a weakening and it is treated as one.** `TestTheFreezeComparisonStillBites` is
seven tests that a renamed key, a dropped element, a reordered list, a changed string,
`null` where zero was expected, and **a 1e-9 float change** all still fail. Verified against
the real artefact too: nudging `model.predictions[0]` by 1e-9 fails and names the path.

The path reporting is a side benefit worth keeping. The old `==` printed two truncated
dictionaries; this prints `.model.predictions[0]`.

#### A SQL literal that only one SQLite would parse

`test_corpus.py` wrote `visit_duration = 4_000_000` inside a SQL string. The underscore is
**Python's** digit separator; SQLite only accepts separators from 3.46, so the library
bundled with Windows Python parsed it and Ubuntu's did not. A Python habit that reads
correctly and is not Python.

#### What this says about the eighteen tasks before it

Both bugs were latent for months in a suite run many times a day, and neither could ever
have been found on the machine it was written on. The value of CI here was not "run the
tests" — the tests were already being run — it was **running them somewhere else**.

D115 chose Ubuntu-only on the reasoning that Windows is covered by daily habit and Linux is
what nothing had ever checked. That reasoning is now measured rather than argued.

939 Python tests, 524 TypeScript, both linters clean, builds.

---

### D121 — `unknown` is a head, not a tail: T10b re-registered as asking rather than discovering

T10b has said since D42: *cluster domains by session co-occurrence and time-of-day, name each
cluster by its most frequent member.* D89 measured that and found **zero clusters at every
threshold from 0.3 to 0.7**, and concluded the bucket "is a long tail of domains visited once
or twice".

`analysis/unknown_shape.py` measures the same question on every corpus this project has. It
**fits nothing** — it counts, and every number would be identical if no model existed, which
is what lets a bar be set from it (D88).

#### D89's first half holds. Its second half read the wrong column.

The clustering verdict is right and load-bearing: **77 of 121 unknown domains are seen exactly
once**, and only **8** appear in three or more sessions. A domain seen once has no co-visit
signal at any threshold, so no amount of tuning reaches it. That is settled, twice now, and
T10b's stated mechanism is dead.

But "a long tail of domains visited once or twice" describes the **domain count** and not the
**event mass**, and the two say opposite things about the same data:

```
  top  1 domains    76.6% of unknown events
  top  3 domains    80.4%
  top 10 domains    85.8%
  seen exactly once   77 of 121 domains (64%)
```

**One domain is three quarters of `unknown`.** Both facts were in the corpus D89 examined; it
looked at the tail, found it hopeless, and generalised to the bucket. Recorded as a
misreading rather than a superseded result, because the measurement was correct and only the
sentence drawn from it was wrong.

#### It mostly generalises, and the exception is stated rather than buried

| corpus | top-1 | top-10 | seen once |
|---|---|---|---|
| live export | **76.6%** | 85.8% | 64% |
| Chrome (imported) | **58.1%** | 71.5% | 62% |
| Edge (imported) | **58.4%** | 78.6% | 53% |
| Firefox (imported) | **13.9%** | 55.7% | 47% |

Three of four corpora have a dominant head. **Firefox does not** — 13.9%, and no domain
carries the bucket. It is also by far the smallest at 115 unknown events, so it is weak
evidence either way, and it is here because a table showing only the three that agree would
be a different claim.

#### The head is institutional, and the privacy design is what put it there

The largest unknown domain on the live profile is the author's own employer. D26 and D88 keep
employer, school, council and neighbourhood domains **out of the shipped map on purpose**,
because a published list of workplaces is a profile of the people who work at them.

So the head of `unknown` is not a gap in the map. It is the map behaving as designed, and
adding those domains would be the privacy violation rather than the fix. **The head can only
ever be resolved on the device, by the person.** The clustering plan was, in retrospect, an
attempt to avoid admitting that.

`overrides` and the editor for it shipped in D114. The storage exists, the interface exists,
the export carries it (D45). What does not exist is anything that tells a person *which*
domain is costing them — the editor is a blank form, and nobody fills in a blank form.

**So T10b is not a discovery problem. It is a prompting problem.**

---

#### Pre-registration — written before any of the mechanism exists

**The mechanism.** A panel that ranks unknown domains and asks the person to assign the top
ones to a category. Ranked **by event count**, declared here rather than chosen later: events
are what the dashboard's "unknown share" means and what a person recognises about their own
browsing. Dwelled visits are the quantity that produces labels and they rank the head
differently on this profile, which is exactly why the choice has to be fixed in advance.

**The bar**, all three, measured after the top **3** are answered:

1. `unknown` share of events falls **below 10%**, from 29.9%.
2. D27-eligible labels rise by **at least 20%**.
3. The number of categories grows by **no more than the number of prompts answered** — D88's
   "the goal is shrinking `unknown`, never multiplying categories", as a check rather than an
   intention.

**Measured at the pessimistic end.** The script brackets the counterfactual rather than
guessing which category a person would pick: `merged` puts the named domains into an
established category, where they clear the ten-prior-visit rule at once; `separate` gives each
its own, starting from zero. **The bar must be met at `separate`.**

**Predicted outcomes, and which of them are honest predictions.**

| # | Prediction | Status |
|---|---|---|
| 1 | Unknown event share falls below 10% | **arithmetic, not a prediction** — top-3 is 80.4% |
| 2 | Named labels rise ≥20% at `separate` | **already observed at +20%**, not independent |
| 3 | Largest-category share falls below 80% | **already observed at 77%**, not independent |
| 4 | Categories grow by ≤3 | genuine |
| 5 | The head is institutional on every corpus that has one | genuine, and the one worth being wrong about |

**Two and three are marked because I ran the counterfactual before writing this bar, and a
bar drawn at a number already seen is not a bar.** The thresholds are set below the observed
values on purpose — 20% against 20%, 80% against 77% — so they are slack rather than
hindsight, and the entry says so instead of presenting five clean predictions.

Prediction 5 is the interesting one. If the head is institutional for everyone, the design
follows: the public map should never learn these domains, and the prompt is the only correct
mechanism. If some people's heads are ordinary public sites the map simply missed, then part
of this is a map-coverage problem and should be fixed there instead.

**A design finding already, worth testing rather than assuming**: routing an answer into an
*established* category produced more labels than creating a new one, because a new category
produces nothing until its eleventh dwelled visit. But merging into the *largest* category
made concentration worse, not better — 95% against today's 93%. Where an answer routes
changes which half of the bar it helps, and the panel should not quietly default to either.

**Not blocking, and not next.** T-G is two weeks of data away and this changes what those
labels look like, so the order matters: measure first, prompt second, and re-run the gate
after. Nothing here is implemented and nothing should be until the bar above has survived
being read again.

939 Python tests, 524 TypeScript.

---

### D122 — The repository stays private until the product is ready, which ties it to submission

Akash, 2026-09-03: *"We would make repo public once full product is ready."*

Sound, and it costs nothing that has already been done. The work that had to happen before
the **first push** — purging screenshots from all 81 commits (D118), settling the published
identity (D119) — is unaffected: those were irreversible only once the repository left this
machine, and it has left it, privately. Nothing was premature.

**But repository visibility and Web Store submission are not independent, and the coupling
runs through the privacy policy.** `docs/privacy-policy.md` says:

> You can read the source. Tise is open source, and the code that would have to exist for
> data to be transmitted does not exist — its absence is enforced by an automated test that
> fails the build if anyone adds it.

That sentence is the load-bearing one in the whole document. Everything else in the policy is
a promise; this is the part that turns "trust us" into "go and check". **If the repository is
private when the extension is listed, it is false to every person who reads the policy** —
and false about precisely the claim they would most want to verify.

`SPEC.md` carries the same assumption in its success criteria ("a public repository someone
can read and believe") and in its opening description. Those are goals rather than statements
of current fact, so they are not yet wrong; the privacy policy is written in the present tense
and would be.

**So the constraint is: public no later than Web Store submission.** Not before, if the
product is not ready — the repository being private today makes nothing untrue, because
nothing is listed and nobody has been told to go and read anything.

The alternative is to ship with a private repository and rewrite that paragraph. It is
available and it is worse: the privacy argument would rest entirely on assertion, in a product
whose entire pitch is that its claims can be checked. Recorded so that the choice is made
deliberately if it is ever made at all, rather than discovered during a listing review.

**Branch protection moves with it.** Deferred by Akash today, and on a private
single-contributor repository the exposure is close to nil. The moment it stops being close
to nil is the moment someone else can fork or open a pull request, which is the same moment.

---

### D123 — The gate is re-measured, does not pass, and is not going to

Eighteen days of browsing later, a fresh export (`2026-09-21`). D116 left T-G4 gated on
D99's eligibility rule at 19% of its binding criterion, about sixteen days out. This is the
re-read, and it does three things: it reports the number, it withdraws a projection, and it
records a proposal that was made and should not have been.

#### Where the profile stands

```
  no    dwell-carrying visits         497 / 1,000   (50%)
  PASS  sessions holding a label       62 / 20      (310%)
  PASS  labels                        413 / 200     (206%)
```

**Two of the three criteria now pass, and neither is the one that binds.** On 2026-09-03 all
three failed; sessions and labels have since cleared by 3x and 2x. The visit criterion has
moved 192 -> 497.

Composition has improved and is still lopsided. Of 413 labels, 126 are `unknown` (D27), and
of the 287 that remain **205 are `search` — 71%, against 93% at D116**. Four categories now
carry labels where two did. The base rate is **49.2%**, which is what a median split is
supposed to produce and the first time this project has measured one that close to its own
premise.

#### The export shrank by 40%, and the reason is not a fault

3,918 events -> 871. **Imported Chrome history aged out of the 30-day retention window
(D11).** The oldest surviving event is 2026-08-24. Nothing was reset and nothing was lost
that was not meant to expire: attention spans went **367 -> 860** over the same period, which
is live collection working exactly as D96 intended.

Worth recording because the innocent explanation and the alarming one look identical in a
file size, and the alarming one — a store wiped by a reinstall — was live until the window
was actually checked.

#### The projection was wrong, and withdrawing it is the point of this entry

`engagement_gate.py` printed *"503 short of the visit criterion -> about 23 days"*. That
sentence assumes the count is cumulative. **It is not.** Events expire at 30 days, and the
gate counts dwell-carrying visits — events joined to spans — so it counts what fits in the
window, not what has ever happened.

Measured over the 22.7 days attention has been collected: **21.9 dwelled visits a day**.
Against a 30-day window:

```
  21.9/day x 30-day window  ->  about 656 at saturation, against 1,000
```

So the count rises to roughly 650 by the end of September and **then stops**. Nothing has
expired yet — the union of dwelled visits across all four exports is 497, exactly today's
count, because the oldest is 2026-08-29 and expiry begins around 2026-09-28. After that the
number is flat. **It is a ceiling, not a countdown, and the script said "23 days" anyway.**

Reaching 1,000 needs about **33 dwelled visits a day, sustained** — half again the observed
rate, forever, and not a thing to plan a product on.

#### The proposal that was wrong, recorded because it was nearly acted on

The first reading of that ceiling was that **the unit was defective**: D99 counted visits
over unbounded history, T-G4 counts them inside a retention window, so the bar could not
transfer and the honest repair was a cumulative counter surviving raw-event expiry — which
D11 permits, since derived features do not expire. It came with a deadline, because the true
cumulative count is only recoverable while nothing has expired.

**It was wrong, and checking rather than asserting is the only reason it did not ship.**
`analysis/replication.py` computes `visits = len(events)` over a corpus that is **1-31
October 2018 — one month** (D99, D100). D99's rule is *1,000 visits in a month*. A 30-day
window is not a distortion of that comparison; it **is** that comparison. D116's translation
was right.

So the repair would have replaced a faithful unit with an unfaithful one, and it would have
done so immediately after watching the faithful one fail. **That is the exact move
pre-registration exists to stop** — D81's lesson, D102's, D112's — and it arrived dressed as
a fidelity argument, which is the only form in which it would ever be persuasive. The
deadline attached to it made it worse: urgency is a poor reason to change a bar and an
excellent reason to skip checking one.

#### The verdict is robust to the translation, which is what makes it a finding

If the unit were loosened to **every stored event** — imported history included, though it
carries no dwell and can never produce a label — the profile still fails. The script prints
both, because a verdict that survives the loose reading is a finding about the profile rather
than about the translation:

```
  dwell-carrying visits (D116's unit)   21.9/day x 30  ->  about 656
  every stored event                    31.0/day x 30  ->  about 931
```

**Every live event carries a span** — dwell-carrying visits and live events are both 497 — so
the gap between the two rows is entirely imported history, which is mid-expiry and gone
within days. The loosest available reading is 931 and falls short of 1,000 on its own,
*before* accounting for the fact that it is inflated by data about to vanish.

No reading of the rule passes. That is a much stronger statement than the strict reading
failing alone.

**That line was wrong on its first run and the error is worth keeping.** It divided every
stored event by the *dwell* collection window rather than the stored one, mixing a 29-day
span with a 22.7-day span, and printed **1,150 — a pass** — in the one line whose purpose is
to show the verdict survives a generous reading. Two spans are now measured separately and a
test pins the arithmetic in both directions.

#### What this actually means: the gate is working

**D99 excluded 822 of 2,148 panelists on this criterion.** 38% of real people did not browse
enough, in a month, for this model to be worth fitting for them.

**Akash is one of them.** At roughly 656 dwell-carrying visits a month against a bar of
1,000, this profile is not a marginal case; it is inside the excluded group by a wide margin,
and it would have been excluded from the D100 replication had it been in that panel.

That is not a failure of the gate. It is the gate doing the one thing it was built to do, to
the person who built it. The uncomfortable part is that a rule declared on strangers, chosen
specifically because nobody could tune it after seeing this profile, has now returned a
verdict about this profile that its author does not want — which is the only circumstance in
which such a rule is worth anything at all.

#### What is not decided here

Whether D99's rule is the right rule for **shipping** is a separate question from whether it
was the right rule for **replication**, and it has never been asked. D99 answered *"is this
person worth including in a measurement of a population effect?"*. Shipping asks *"should
this person be shown a prediction?"*. Those are not obviously the same question, and a rule
built for the first was reused for the second in D116 without the distinction being raised.

**The distinction may be real. The timing is not innocent**, and it is recorded that way: it
was noticed after the gate failed, by the person the gate excluded. It is a hypothesis
needing its own pre-registered argument, not a licence to reinterpret a bar that has just
returned an unwelcome answer. Nothing is changed on the strength of it today.

Three options exist and none is taken in this entry:

1. **Wait.** Does not work — the count saturates below the bar. Only a sustained change in
   browsing volume (33/day against 21.9) reaches 1,000, and that is not a thing to plan on.
2. **Ship descriptive.** D94's stopping rule in a different costume: Tise shows what it has
   measured, `visit_engaged` stays adopted and unshipped, and the honest headline is that a
   model was validated on 1,326 people and withheld from the one person it could not be
   validated for.
3. **Ask whether shipping needs its own bar.** Legitimate, tainted by timing, and requires
   the argument to be written before any number is looked at again.

**T-G4 remains gated, and the gate has now returned a real answer rather than a wait.**
`SPEC.md` criterion #7 is not met and, on the current reading, will not be met by patience.

**No threshold moved and nothing was fitted.** The only code change is that
`engagement_gate.py` now checks the ceiling before dividing a shortfall by a rate, and says
so when the window cannot hold the bar — a projection corrected, not a bar rewritten. It was
broken deliberately once and 4 of 13 tests failed. 953 Python tests, 524 TypeScript, both
linters clean.

---

### D124 — Ship descriptive: the model is good, the data is not, and the product says so

Akash's call, given D123's three options: **ship descriptive.** `visit_engaged` stays
adopted, stays replicated, and does not switch on. Tise ships what it has measured.

This is D94's stopping rule arriving by a route nobody planned for. That rule said: if no
target separates from its declared bar, the finding is that this data does not support a
model and Tise ships descriptive. **T-A did separate** — it is the one target that cleared a
pre-registered bar (D97) and held on 1,326 other people (D100). The stopping rule still
fires, one layer down: the model earned its place and the *person* does not clear the data
gate that was declared for it.

#### What changes, and it is less than it sounds

Nothing about the engine. Collection, sessions, features, attention, training, calibration,
retention, export, parity, the card, the dashboard, resolution — all of it stays, all of it
works, and the research is unretracted. What changes is that three surfaces stop describing
a switch-on that is not coming.

**`status.ts` gains a state.** `visit_engaged` moves from `adopted` to **`withheld`**, and
the distinction is the point: `adopted` describes a *wait*, and this is a *decision*. A state
that means "queued to ship" applied to something that will not ship is the exact defect this
file was written to prevent — D88 to D97 had one constant meaning both a goal and a shipped
fact, and one of the two was always wrong. The note now carries the argument rather than a
pointer to a progress bar.

**The popup stops counting down.** `gateSentence` ended *"so 503 to go"*. A shortfall phrased
as a remainder is a promise of arrival, and D123 established there is none at this rate. It
now reports what was measured and says prediction stays off, with the gap and the reason.
**The counts stay on screen**, because D101's argument for putting them there is untouched: a
store whose progress is invisible is indistinguishable from one that is broken, and these
numbers remain the only thing that would expose collection silently stopping. What was
withdrawn is the promise attached to them, not the measurement. Third time the popup has
shipped a hand-written claim that outlived its system (D101, D114, now).

**`SPEC.md`'s T-A heading** said "not yet shipped". "Not yet" is the same promise in two
words.

#### The headline is the withholding, not an apology for it

The honest framing, and the one worth putting in front of a reader: **a model was validated
on 1,326 people, and withheld from the one person it could not be validated for.** A
capability showcase that demonstrates a team will not ship an unvalidated model against its
own interest is showing something harder to fake than a working model — every ML project
claims a gate and very few can point at the run where it fired against them.

D123's numbers are what make it checkable rather than a posture: 497 of 1,000, a ceiling near
656, and 822 of 2,148 strangers excluded by the same rule years earlier.

#### Checkpoint E: there are five criteria, not twelve, and there never were

Acting on this decision meant reading Checkpoint E, which says *"All twelve spec success
criteria met"*, and `tasks/todo.md`, which says *"the twelve `SPEC.md` criteria. Only #7 is
outstanding, and #7 **is** T-G4."*

**`SPEC.md` has listed five since the scaffold commit.** Checked against `git log`, not
memory: the five items in "What success looks like" are byte-identical to `1e0c26d`, the
first commit in the repository. There has never been a seventh criterion, so "only #7 is
outstanding" was a claim about an item that did not exist — and D122 made that sentence the
definition of "product ready". The planning documents have been carrying it since the
scaffold, and this session repeated it in conversation before checking.

**This is the project's own recurring defect, in its own planning documents.** D98:
`reports.py` labelled twelve benchmarks with a retired target. D105, D106, D108, D114, D116:
a surface asserting something the system had moved past. Every one was caught by looking at a
real artefact rather than a record of it. The records were never audited the same way,
because nothing renders them and nothing tests them.

Checkpoint E now **spells the criteria out instead of counting them**, because a count is
precisely what let an unverifiable number stand in for a checkable list.

Where they stand: **4 and 5 are met** (`docs/benchmarks/`; six documented failures — D80,
D92, D102, D109, D112, D123). **1 and 2 are visibility and T18**, neither blocked by this
decision. **3 needs reading carefully**, below.

#### Criterion 3 is ticked with its qualification attached, not quietly

*"A reliability curve, computed from real browsing, showing that stated probabilities are
approximately correct."*

The curve exists at `docs/benchmarks/calibration.md`, computed on real browsing (D110). It
scores `return_24h` — retired by D88 — so it is a research result about a target nothing
shows.

The shipped surface does not state model probabilities at all. D103 chose counts with their
denominators (*"after `news`, you usually go to `video` 41% — 9 of 22"*) precisely so that
what is displayed is either true of the person's own data or it is not, and **smoothing was
deliberately left out so the percentage equals the fraction**. There is nothing on screen
whose calibration could be wrong.

So the criterion is met in the sense it was written, and **the qualification travels with the
tick wherever it appears** rather than being argued once and forgotten. Recorded plainly
because reinterpreting a success criterion in the same session that abandoned the feature it
was written for is exactly the shape D123 refused a day earlier, and the defence is not that
this reading is convenient — it is that D103 chose the non-probabilistic surface in August,
for stated reasons, long before anything failed.

#### What is explicitly not decided

**The extension still trains `return_24h`.** It is retired, its predictions are kept and
scored and shown to nobody as advice, and it is what keeps the prediction and resolution loop
exercised end to end. Ripping it out is a separate change with its own risk and no user
visible in it either way. `SHIPPED_TARGET` still names it, truthfully.

**D99's rule is not re-opened.** D123's third option — asking whether shipping deserves a
different bar from replication — remains available, untaken, and still carries its timing
problem. Choosing to ship descriptive is not an argument that the gate was wrong; it is
accepting the gate's answer.

**`visit_engaged` switches on by itself if the gate is ever met.** Nothing about the rule was
weakened, and `engagementGate` still runs on every popup open. If Akash's browsing volume
changes, the gate passes and the entry above becomes wrong in the good direction.

953 Python tests, **526 TypeScript** (two added: the popup must not phrase the gap as a wait,
and a withheld target must carry its reason). Both linters clean, builds.

---

### D125 — The claims panel was wrong about a target, and the README buried the only thing worth reading

Two findings from reading the repository as a stranger would, before making it public.

#### `browsing_next_hour` said "nothing fitted" for thirteen entries

`status.ts` carried it as **`registered`** — *"Bar and rule fixed in advance, nothing fitted
… the pre-registered prediction is that this one fails."*

**D112 fitted it.** It cleared D94's bar on the adoption corpus: **+0.0546 [+0.0383,
+0.0724]**, day-clustered, 5 of 5 folds. So the dashboard told every reader that nothing had
been fitted, and that the expectation was failure, about a target that had been measured and
had passed — for thirteen decision entries.

**This is the defect that file exists to prevent, inside that file.** Its own docstring opens
with D88–D97: `reports.py` said the project predicted `block_volume` after D92 retired it,
and eight generated reports told readers so. The lesson recorded there was that a constant
asked to mean two things will be wrong about one of them. `registered` was asked to mean
"declared in advance" — which stayed true — and "not yet measured", which stopped being true
at D112. Nothing updated it, because nothing had to.

It is **`measured`** now, and the note says the thing worth saying: it cleared its bar, and
then the result came apart on the 79% of rows where the question is a real question.

#### The guard: a state that claims nothing was fitted, beside a report of the fitting

The states are judgements and cannot be derived. **One contradiction can be**, and it is the
one that actually happened: `docs/benchmarks/browsing-next-hour.md` has existed since D112.
A report on disk is the artefact of a run, so its presence is checkable in a way that "is
this description still true?" is not.

`status.test.ts` now fails if any `registered` target has a benchmark report named after it.
Broken deliberately by restoring the old state: it fails with the diagnostic naming the
target and the file. **This is D110's seam-audit shape** — the existing tests pinned
`status.ts` against `predict.ts`, which is one build checked against itself, and could never
see a claim that had gone stale against a *document*.

It would have caught this on the day D112 landed.

#### The README opened with a product pitch and buried the argument

A stranger decides in about fifteen seconds, and the first line offered *"a Chrome extension
that learns your browsing habits"* — which is what every browsing extension says, including
the ones that exfiltrate everything. The thing no other repository can say sat at **line 188
of 283**.

Restructured rather than rewritten; the plain-language explanation Akash asked for is intact
and still first in the body. What changed:

* **The opening states the claim**: a prediction validated on 1,326 people, switched off
  because its author's own data did not clear a threshold fixed in advance, which nobody was
  watching and nobody would have known was lowered.
* **Six targets, in a table, none of them shown to the user.** The old text said *"four
  prediction ideas have been tested and two were thrown away"* — stale since D102 and D112,
  and it undercounted the work. The honest line is that six were taken seriously and **not
  one is shown as a prediction**.
* **A path for the reader who came for the method**, at the top: `DECISIONS.md` pointed at
  D123–D124, the benchmark directory, and the parity suite.
* **The withholding is told once, properly.** It had been told twice, 130 lines apart, and
  the first telling arrived before the reader knew what `visit_engaged` was — so "switched
  off" read as a missing feature rather than a decision.

Every number in it was verified against the repository rather than carried over: 124
decision entries, 22 benchmark reports, and every link resolves.

#### The pattern this session

Four stale records found in one day, none by a failing test: three copies of a Checkpoint E
criterion count that never existed (D124), and this one. **The planning documents and the
honesty panel were the least verified artefacts in a project whose entire discipline is
verification**, because nothing renders them and, until now, nothing read them.

953 Python tests, **527 TypeScript** (+1). Both linters clean, builds.
