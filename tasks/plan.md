# Implementation Plan: Tise V1

Implements [`SPEC.md`](../SPEC.md). Decisions in [`DECISIONS.md`](../DECISIONS.md).
Task checklist in [`todo.md`](todo.md).

**Author writes the code (D12).** Every verification step below is a command Akash can
run. **No deadline (D4, D14)** — so every task leaves the repository working and
committable, and no task assumes context carried over from the previous session.

---

## Overview

Eighteen tasks in six phases. The ordering is unusual on purpose: **the research tier is
built before the extension.**

Chrome already holds roughly 90 days of browsing history. That is a real dataset,
available today, requiring no extension. So Phase 0 answers the question the whole
project depends on — *does enough signal exist to predict anything?* — before a line of
product code is written. If the answer is no, four small Python tasks have been spent
instead of six weeks.

It also front-loads the payoff: the reliability curve that the showcase rests on can
exist before the extension does.

## Architecture Decisions

- **Research before product.** Phase 0 uses existing Chrome history and can kill or
  redirect the project cheaply.
- **Python defines the feature contract; TypeScript mirrors it.** Parity is symmetric, so
  whichever comes first sets the reference. Python is first, so the fixture generated in
  Phase 0 becomes the parity oracle in Phase 2.
- **The riskiest unknowns are Tasks 1 and 5.** Task 1 can invalidate the premise. Task 5
  can invalidate the manifest. Both are early and both are cheap to fail.
- **Privacy plumbing is a Phase 1 task, not a Phase 5 one.** Export is how data reaches
  the research tier, so it must exist early regardless of its privacy value.

### The duration trap

Chrome's history **file** (`visits.visit_duration`) records dwell time. Chrome's history
**API** (`chrome.history.getVisits`) does not — it returns only `visitTime`,
`transition` and `referringVisitId`.

Analysis on the file can therefore measure something the shipped extension can never
compute. Every analysis task produces two results: `full` (with duration) and `history`
(without). **The `history` variant is the one that constrains the product.** If a model
only works in the `full` variant, it does not work.

---

## Dependency Graph

```
T1 history shape ──┬── T2 category set ── T3 resolver+labels ── T4 baselines/backtest
                   │                            │                        │
                   │                            └────────┬───────────────┘
                   │                                     │
                   │                          (fixture + feature contract)
                   │                                     │
T5 permission spike ── T6 collector ── T7 import ── T8 privacy core
                                                         │
                                              T9 features in TS + parity
                                                         │
                                                    T10 full feature set
                                                         │
                                    T11 training ── T12 calibration ── T13 registry
                                                         │
                                              T14 dashboard ── T15 onboarding
                                                         │
                                    T16 benchmarks ── T17 CI ── T18 store prep
```

---

## Phase 0 — Does the signal exist?

Python only. No extension. Uses existing Chrome history.

### Task 1: Measure the shape of real browsing history

**Description:** Copy the Chrome history database, parse it, and measure what Tise would
actually have to work with. This decides the session timeout, the category count, and
whether the primary prediction target is viable at all.

Chrome locks `History` while running, so the script copies it first. Timestamps are
microseconds since 1601-01-01 UTC, not Unix epoch. Default profile path on Windows:
`%LOCALAPPDATA%\Google\Chrome\User Data\Default\History`.

**Acceptance criteria:**
- [ ] Reports: visits/day distribution, inter-visit gap distribution, unique registrable
      domains, top 100 domains by visit count, and history span in days.
- [ ] Plots the inter-visit gap histogram, and identifies the natural session boundary
      empirically rather than assuming 30 minutes.
- [ ] Estimates achievable `return_24h` labels per week at 3 candidate category counts
      (e.g. 8, 15, 25).
- [ ] Produces both `full` and `history` variants; states plainly which fields exist in
      the API and which do not.
- [ ] Writes `docs/benchmarks/history-shape.md` with the numbers and a one-paragraph
      verdict.

**Verification:**
- [ ] `uv run python analysis/history_shape.py --out docs/benchmarks/`
- [ ] Manual: the reported session boundary is defensible from the histogram.
- [ ] `data/` contains the copied database and nothing is committed.

**Gate — the project depends on this:** if fewer than ~300 `return_24h` labels are
reachable within 8 weeks of browsing at any sensible category count, stop. Either change
the target or reconsider the project. Record the outcome in `DECISIONS.md` either way.

**Dependencies:** None.
**Files:** `analysis/history_shape.py`, `docs/benchmarks/history-shape.md`
**Scope:** M

---

### Task 2: Define the category set and seed the domain map

**Description:** Derive the category taxonomy from Task 1's actual top domains rather
than inventing one. Build the shipped JSON map covering the domains that account for the
bulk of real traffic.

**Acceptance criteria:**
- [ ] `domains.json` maps registrable domains to categories and covers ≥ 80% of the
      author's visits by count.
- [ ] The category count matches the option Task 1 showed produces enough labels per class.
- [ ] Every category has a one-line written definition; ambiguous cases documented.
- [ ] `unknown` is a valid category, not an error.

**Verification:**
- [ ] `uv run pytest research/tests/test_categories.py`
- [ ] Coverage percentage printed by the test and recorded in the file header.

**Dependencies:** T1
**Files:** `extension/src/categories/domains.json`, `research/tests/test_categories.py`
**Scope:** S

---

### Task 3: Category resolver, sessioniser, and the label generator

**Description:** Turn raw history into the labelled dataset. Resolver applies the map,
then keyword rules, then `unknown`. Sessioniser groups visits using the Task 1 boundary.
The label generator emits one `return_24h` example per (topic, day).

This task also produces the **parity fixture** — a frozen JSON file of events and their
expected feature values that TypeScript must later reproduce exactly.

**Acceptance criteria:**
- [ ] Resolver is a pure function; unknown rate is reported, not hidden.
- [ ] Sessioniser is a pure function of events and a timeout parameter.
- [ ] Every label carries an explicit `window_end`; no label uses data at or after it.
- [ ] `research/fixtures/parity_events.json` and `parity_expected.json` are committed.
- [ ] Label counts match Task 1's estimate within ~20%; investigate if not.

**Verification:**
- [ ] `uv run pytest research/tests/test_sessions.py research/tests/test_labels.py`
- [ ] Leakage test passes: injecting an event after `window_end` changes no feature.

**Dependencies:** T2
**Files:** `research/tise_research/features/{resolver,sessions,labels}.py`, fixtures, tests
**Scope:** M

---

### Task 4: Baselines and the first honest backtest

**Description:** Implement the three baselines and a rolling-origin backtest, and produce
the first real numbers from real browsing. No machine learning yet — the point is to know
what must be beaten.

**Acceptance criteria:**
- [ ] Baselines: marginal frequency, "same as last time", time-of-day prior.
- [ ] Rolling-origin backtest with chronological folds; no shuffling anywhere.
- [ ] Reports Brier score, log loss and base rate per fold.
- [ ] Runs on both `full` and `history` feature variants and reports both.
- [ ] `docs/benchmarks/baselines.md` generated by the script, not written by hand.

**Verification:**
- [ ] `uv run python -m tise_research.eval.backtest --target return_24h`
- [ ] `uv run pytest research/tests/test_backtest.py`
- [ ] Determinism: two runs with the same seed produce identical output.

**Dependencies:** T3
**Files:** `research/tise_research/models/baselines.py`,
`research/tise_research/eval/backtest.py`, `docs/benchmarks/baselines.md`
**Scope:** M

### Checkpoint A — after Tasks 1–4

- [ ] Real numbers exist from real browsing, produced by committed scripts.
- [ ] The gate in Task 1 was passed, or the project was redirected.
- [ ] Parity fixture is committed and stable.
- [ ] `DECISIONS.md` records the session timeout, category set and label volume actually
      measured.
- [ ] **Review before continuing.** Everything after this point is product engineering;
      this is the last cheap exit.

---

## Phase 1 — Collect

### Task 5: Permission spike

**Description:** Determine experimentally the minimum Chrome permission set that observes
navigation with a URL, and confirms what `chrome.history` returns. The original design's
manifest could not have collected anything (audit finding 7), so nothing here is assumed.

Throwaway code. The deliverable is written findings.

**Acceptance criteria:**
- [ ] Documents whether `webNavigation` alone yields URLs, or host permissions are also
      required, and whether `tabs` is needed at all.
- [ ] Confirms the exact fields `chrome.history.getVisits` returns — specifically that
      duration is absent.
- [ ] Confirms whether the needed host permissions can be optional rather than required
      at install.
- [ ] A justification sentence is written for every permission, ready for the listing.
- [ ] `docs/permissions.md` committed; spike code deleted or clearly marked.

**Verification:**
- [ ] Manual: load unpacked, browse, observe logged URLs with the minimum set.
- [ ] Removing any single permission demonstrably breaks collection.

**Dependencies:** None (can run in parallel with Phase 0)
**Files:** `docs/permissions.md`, throwaway spike directory
**Scope:** S

---

### Task 6: Extension scaffold and live collector

**Description:** Vite + TypeScript + MV3 scaffold, IndexedDB schema, event normaliser,
and the service worker listening to navigation. URLs are reduced to registrable domain
**before** an event object is constructed.

**Acceptance criteria:**
- [ ] `npm run build` produces a loadable unpacked extension.
- [ ] Browsing writes `TiseEvent` rows matching the spec schema.
- [ ] No stored field contains a path, query string or fragment.
- [ ] Uses only the permissions Task 5 justified.
- [ ] Collection can be paused, and pausing stops writes.

**Verification:**
- [ ] `npm run build && npm test`
- [ ] `npm test -- privacy` — forbidden-field assertions pass against a populated store.
- [ ] Manual: browse 10 sites, confirm 10 events with correct domains and categories.

**Dependencies:** T5, T2
**Files:** `extension/manifest.json`, `extension/src/background.ts`,
`extension/src/collect/*`, `extension/src/storage/*`
**Scope:** M

---

### Task 7: First-run history import

**Description:** On first run, import existing history through `chrome.history` so a new
user has predictions immediately (D10). Imported events are marked `source: "import"` and
`dwellSeconds: null`.

**Acceptance criteria:**
- [ ] Import is explicit and consented, never silent.
- [ ] Every imported event has `dwellSeconds: null` and `compat: "history"` downstream.
- [ ] Import is idempotent — running twice creates no duplicates.
- [ ] Progress is shown; import of ~90 days does not block the UI.

**Verification:**
- [ ] `npm test -- import`
- [ ] Manual: import, then compare event count against Task 1's measured visit count.
- [ ] Run twice; row count unchanged.

**Dependencies:** T6
**Files:** `extension/src/collect/import.ts`, tests
**Scope:** M

---

### Task 8: Retention, deletion and export

**Description:** The privacy core, and the pipe that feeds the research tier. Raw events
expire after `raw_retention_days` (default 30, `0` = keep forever). Delete-all removes
everything. Export produces the JSON the Python tier consumes.

**Acceptance criteria:**
- [ ] Retention runs on a `chrome.alarms` schedule and deletes only raw events.
- [ ] `raw_retention_days: 0` retains everything; both settings are tested.
- [ ] `deleteAll()` leaves zero rows in every store.
- [ ] Export validates against the published schema and contains nothing beyond it.
- [ ] Exported file loads into `tise_research.data.load` without transformation.

**Verification:**
- [ ] `npm test -- privacy retention export`
- [ ] `uv run python -m tise_research.data.load --export ../data/export.json`
- [ ] Manual: export, delete all, confirm the UI shows an empty state.

**Dependencies:** T6
**Files:** `extension/src/storage/{retention,export,delete}.ts`, tests
**Scope:** M

### Checkpoint B — after Tasks 5–8

- [ ] Extension collects from real browsing and imports history.
- [ ] Privacy tests pass; deletion and export verified by hand.
- [ ] A real export file loads into the Phase 0 pipeline unchanged.
- [ ] The loop is closed: browser → export → Python → numbers.

---

## Phase 2 — Features, twice

### Task 9: Port sessioniser and one feature to TypeScript, and stand up the parity suite

**Description:** The highest-value infrastructure task. Port the sessioniser and a single
feature to TypeScript, then build the harness that proves both implementations agree on
the committed fixture. One feature is enough to prove the mechanism.

**Acceptance criteria:**
- [ ] TS sessioniser reproduces Python session boundaries exactly on the fixture.
- [ ] The harness runs both implementations over `parity_events.json` and compares
      vectors within 1e-9.
- [ ] A deliberately introduced mismatch fails the suite (verify by breaking it once).
- [ ] Every ported function takes `windowEnd` explicitly and filters strictly before it.

**Verification:**
- [ ] `uv run pytest -m parity`
- [ ] `npm test`
- [ ] Break one constant, watch it fail, revert.

**Dependencies:** T3, T6
**Files:** `extension/src/features/{sessions,recency}.ts`,
`research/tests/test_parity.py`, tests
**Scope:** M

---

### Task 10: Port the remaining features

**Description:** Port the full feature set under the parity suite, in small batches.
Every feature declares whether it belongs to the `history` or `full` compat class.

**Acceptance criteria:**
- [ ] All features implemented in both languages; parity suite green.
- [ ] Each feature is tagged with its compat class.
- [ ] `featureSet` version is set and recorded in `DECISIONS.md`.
- [ ] Feature rows persist beyond raw retention (D11).

**Verification:**
- [ ] `uv run pytest -m parity && npm test`
- [ ] Leakage test passes against the TS implementation too.

**Dependencies:** T9
**Files:** `extension/src/features/*`, `research/tise_research/features/*`
**Scope:** M — split into two tasks if it exceeds 5 files per batch

### Checkpoint C — after Tasks 9–10

- [ ] Parity suite is green and CI-blocking.
- [ ] Both implementations pass the leakage test.
- [ ] Any benchmark produced from here describes the shipped model.

---

## Phase 3 — Predict

### Task 11: In-browser training

**Description:** Transition table and logistic regression trained inside the extension.
MV3 service workers are terminated aggressively, so training runs in an offscreen
document and is chunked and resumable.

**Acceptance criteria:**
- [ ] Training completes on ~90 days of imported history without being killed.
- [ ] Training is chunked and survives interruption.
- [ ] Scheduled via `chrome.alarms`, not a long-lived worker.
- [ ] Model coefficients match the Python implementation on the fixture within tolerance.

**Verification:**
- [ ] `npm test -- model`
- [ ] `uv run pytest -m parity`
- [ ] Manual: import 90 days, train, confirm completion and inspect timing.

**Dependencies:** T10
**Files:** `extension/src/model/{transition,logreg,train}.ts`, offscreen document
**Scope:** M

---

### Task 12: Calibration and abstention

**Description:** Calibrate probabilities and implement the abstention threshold. The
threshold is chosen from validation data, never by intuition.

**Acceptance criteria:**
- [ ] Platt or isotonic calibration applied and version-recorded.
- [ ] Reliability curve, Brier score and ECE computable from stored predictions.
- [ ] Abstention threshold derived from the accuracy-versus-coverage curve.
- [ ] Predictions below threshold are marked `abstained` and are not displayed.

**Verification:**
- [ ] `uv run python -m tise_research.eval.calibrate --model logreg`
- [ ] `npm test -- calibration`
- [ ] Manual: the reliability curve is plotted and defensible.

**Dependencies:** T11
**Files:** `extension/src/model/calibrate.ts`,
`research/tise_research/eval/calibrate.py`
**Scope:** M

---

### Task 13: Prediction registry and automatic outcome resolution

**Description:** Persist every prediction with full reproduction metadata, then resolve
outcomes automatically by matching later events against the prediction window. No user
confirmation button exists in this loop (D6).

**Acceptance criteria:**
- [ ] Stored predictions match the spec schema exactly.
- [ ] Outcomes resolve to `hit`, `miss` or `expired` with no user involvement.
- [ ] Resolution is idempotent and correct across browser restarts.
- [ ] Resolved outcomes are included in the export.

**Verification:**
- [ ] `npm test -- registry`
- [ ] Manual: force a prediction, browse to satisfy it, confirm `hit` without clicking.
- [ ] Manual: let one expire, confirm `expired`.

**Dependencies:** T12
**Files:** `extension/src/model/registry.ts`, `extension/src/storage/predictions.ts`
**Scope:** M

### Checkpoint D — after Tasks 11–13

- [ ] The extension predicts and scores itself with no human in the loop.
- [ ] Reliability curve exists from real browsing.
- [ ] Success criteria 7 and 8 in the spec are met or a date is set for meeting them.

---

## Phase 4 — Show it

### Task 14: Dashboard

**Description:** Predictions with probability, window, evidence and confidence; a
scorecard of measured accuracy and calibration; emerging-interest trends. Deliberately
capped in scope (D5) — no framework, no animation budget.

**Acceptance criteria:**
- [ ] Every prediction shows probability, window and evidence bullets.
- [ ] Abstained predictions are absent, not shown greyed out.
- [ ] The scorecard shows only measured numbers; unmeasured targets are labelled.
- [ ] Purchase intent appears with a visible "not evaluated" label (D6).

**Verification:**
- [ ] `npm test && npm run build`
- [ ] Manual: every displayed number traces to stored data.

**Dependencies:** T13
**Files:** `extension/ui/dashboard/*`
**Scope:** M

---

### Task 15: Onboarding and privacy settings

**Description:** Consent, source selection, history-import prompt, retention control,
export and delete. The screen must not offer sources V1 does not implement (audit
finding 8).

**Acceptance criteria:**
- [ ] Consent is explicit; nothing is collected before it.
- [ ] Only implemented sources appear.
- [ ] Retention, export and delete are reachable in one click from the popup.
- [ ] Copy states plainly that nothing is ever transmitted.

**Verification:**
- [ ] `npm test -- onboarding`
- [ ] Manual: fresh profile install, complete onboarding, confirm no writes pre-consent.

**Dependencies:** T14
**Files:** `extension/ui/onboarding/*`, `extension/ui/settings/*`
**Scope:** M

---

## Phase 5 — Publish

### Task 16: Model tournament and benchmark report

**Description:** Run the full tournament including research-only models, and generate the
benchmark documents the README links to. Quantify what the in-browser constraint costs.

**Acceptance criteria:**
- [ ] Every model evaluated on identical folds, features, horizon and metrics.
- [ ] The XGBoost-versus-shipped gap is reported explicitly.
- [ ] `docs/benchmarks/*.md` generated by script; no hand-written numbers.
- [ ] At least one documented failure case with its cause (spec criterion 12).
- [ ] Baseline gate enforced in tests.

**Verification:**
- [ ] `uv run python -m tise_research.eval.tournament --target return_24h`
- [ ] `uv run pytest research/tests/test_baseline_gate.py`

**Dependencies:** T13
**Files:** `research/tise_research/eval/tournament.py`, `docs/benchmarks/*`
**Scope:** M

---

### Task 17: CI

**Description:** GitHub Actions running both test suites, with the parity suite blocking.

**Acceptance criteria:**
- [ ] Both suites run on push and pull request.
- [ ] Parity failure fails the build.
- [ ] Secret scanning and dependency audit enabled.
- [ ] Badge in the README.

**Verification:**
- [ ] A pull request with a deliberate parity break is blocked.

**Dependencies:** T10
**Files:** `.github/workflows/ci.yml`
**Scope:** S

---

### Task 18: Web Store preparation

**Description:** Everything the listing needs. Nothing here is code.

**Acceptance criteria:**
- [ ] Privacy policy published at a public URL.
- [ ] Justification written for every permission, from Task 5.
- [ ] Data-use disclosures completed: no collection, no transmission.
- [ ] Developer account registered under the company identity (D13).
- [ ] Screenshots, description, icons prepared.
- [ ] README benchmark section populated with measured numbers.

**Verification:**
- [ ] `npm run package` produces an uploadable zip.
- [ ] Manual: fresh-profile install of the packaged build works end to end.

**Dependencies:** T15, T16, T17
**Files:** `docs/privacy-policy.md`, `docs/store-listing.md`, `README.md`
**Scope:** M

### Checkpoint E — complete

**There are five criteria, not twelve.** This line read *"All twelve spec success criteria
met"* from the scaffold commit until D124, and `SPEC.md` has listed **five** since that same
commit — the twelve never existed. `tasks/todo.md` compounded it with *"only #7 is
outstanding, and #7 is T-G4"*, a claim about an item that was never there, and that sentence
was the stated definition of "product ready" (D122). Checked against `git log`, not memory.

They are spelled out here rather than counted, because a count is what allowed a number
nobody could check to stand in for a list anybody could.

- [x] **1. A public repository someone can read and believe.** Public 2026-09-21 (D129),
      after an audit of 271 tracked files and all 99 commits (D126) and the domain question
      settled and guarded (D127, D128). *Read* is verified — unauthenticated fetch returns
      200, `data/` returns 404. **Believe is not a checkbox**: it rests on the decision log
      being checkable, which is why D127 kept the evidence domains and why D128's removal of
      two is recorded as a trade rather than a tidy-up.
- [ ] **2. A Web Store listing that truthfully declares zero data transmission.** T18.
- [x] **3. A reliability curve from real browsing, showing stated probabilities are
      approximately correct.** `docs/benchmarks/calibration.md`, computed on real browsing
      (D110). It scores `return_24h`, which D88 retired — so it is a research result, and
      **the shipped surface states frequencies with their denominators rather than model
      probabilities**, which is D103's design and is why nothing on screen needs this curve
      to be trusted. Read D124 before treating this tick as unqualified.
- [x] **4. A benchmark table where every number was actually measured (D3).**
      `docs/benchmarks/`, every figure produced by a committed script.
- [x] **5. A documented case where the model failed and why.** Six of them: D80, D92, D102,
      D109, D112, D123.
- [ ] Every README number traces to a committed script.
- [ ] `DECISIONS.md` current, including superseded entries.
- [ ] Repository is genuinely readable by a stranger.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Not enough labels in real browsing | **High** — kills the premise | Task 1 gate, before any product code |
| Analysis uses `visit_duration` the API cannot provide | **High** — model untrainable in production | Every analysis reports `full` and `history` separately |
| TS/Python feature drift | **High** — invalidates every benchmark | Parity suite from Task 9, CI-blocking |
| MV3 kills training mid-run | Medium | Offscreen document, chunked and resumable |
| Web Store rejects the permission set | Medium | Task 5 determines the minimum before anything is built on it |
| Category map is wrong | Medium | Unknown rate published; user override; map is reviewable |
| Project stalls between bursts | Medium | Each task independently committable; no cross-session context |
| Feature rows are permanent and get designed wrong | Medium | `featureSet` versioning; compat classes; schema changes are "ask first" |

## Parallelisation

- **Safe in parallel:** Task 5 alongside all of Phase 0 — different languages, no shared
  files.
- **Strictly sequential:** T9 → T10 → T11 → T12 → T13. Each depends on the last being
  correct.
- **Needs the contract first:** anything touching features waits for the Task 3 fixture.

## Open Questions

1. Session timeout — resolved by Task 1, not before.
2. Category count and taxonomy — resolved by Tasks 1 and 2.
3. Exact permission set — resolved by Task 5.
4. `LICENSE` copyright holder — pending D13; blocks Task 18 only.
5. Privacy-policy hosting — presumed `holycowstudios.in`; blocks Task 18 only.
