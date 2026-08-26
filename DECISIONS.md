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
