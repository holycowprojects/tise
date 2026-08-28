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
