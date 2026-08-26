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
- **Q4 — What is the session timeout?** T1 was supposed to answer this and could not: the
  gap distribution has no clear trough at this volume. Unresolved. Do not adopt 30 minutes
  by default.
- **Q5 — How is a `return_24h` label defined?** One per (category, day) fails the gate at
  163 labels in eight weeks. Per (category, session) or a sliding window would yield
  several times more. Blocks T2.

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
