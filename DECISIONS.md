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
