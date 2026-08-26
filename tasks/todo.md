# Tise V1 — Task List

Full detail in [`plan.md`](plan.md). Spec in [`../SPEC.md`](../SPEC.md).

Tick a task only when its verification commands pass. Each task leaves the repository
working and committable.

---

## Phase 0 — Does the signal exist? (Python only, no extension)

- [x] **T1 · Measure the shape of real browsing history** · M · deps: none
  - Copy Chrome's `History` db, parse it, measure visits/day, gap distribution, top domains
  - Find the session boundary empirically; estimate `return_24h` labels/week at 8 / 15 / 25 categories
  - Report `full` and `history` variants separately — the API has no visit duration
  - Verify: `uv run python analysis/history_shape.py --out docs/benchmarks/` ✓ (68 tests, lint clean)
  - **GATE: FAILED — 163 labels in 8 weeks, needs ~300.** See `DECISIONS.md`.
  - Session boundary **not found** — no clear trough in the gap distribution (Q4)
  - Fixed inside this task: redirect hops counted as navigations; gap-valley left-edge bug

> **STOPPED HERE.** The gate failed, so T2 is blocked until Q5 (the label definition) is
> settled. The cause is the label definition — one per (category, day) — not browsing
> volume. Do not start T2 before that decision.

- [ ] **T2 · Define the category set, seed the domain map** · S · deps: T1
  - `domains.json` covering ≥ 80% of visits; one-line definition per category
  - Verify: `uv run pytest research/tests/test_categories.py`

- [ ] **T3 · Resolver, sessioniser, label generator, parity fixture** · M · deps: T2
  - Pure functions; explicit `window_end` everywhere; commit `parity_events.json`
  - Verify: `uv run pytest research/tests/test_sessions.py research/tests/test_labels.py`

- [ ] **T4 · Baselines and the first honest backtest** · M · deps: T3
  - 3 baselines, rolling-origin folds, Brier + log loss + base rate, both variants
  - Verify: `uv run python -m tise_research.eval.backtest --target return_24h`

- [ ] **CHECKPOINT A** — real numbers from real browsing; gate passed; fixture frozen
  - **Last cheap exit. Review before continuing.**

---

## Phase 1 — Collect

- [ ] **T5 · Permission spike** · S · deps: none *(can run during Phase 0)*
  - Determine the minimum permission set experimentally; confirm what `chrome.history` returns
  - Write a justification sentence for each; output `docs/permissions.md`
  - Verify: removing any one permission demonstrably breaks collection

- [ ] **T6 · Extension scaffold and live collector** · M · deps: T5, T2
  - Vite + TS + MV3, IndexedDB, normaliser; URL reduced to domain before the event exists
  - Verify: `npm run build && npm test -- privacy`

- [ ] **T7 · First-run history import** · M · deps: T6
  - Explicit consent, idempotent, `dwellSeconds: null`, non-blocking
  - Verify: `npm test -- import`; run twice, row count unchanged

- [ ] **T8 · Retention, deletion, export** · M · deps: T6
  - `raw_retention_days` default 30, `0` = forever; delete-all leaves zero rows
  - Verify: `npm test -- privacy retention export` then load the export into Python

- [ ] **CHECKPOINT B** — loop closed: browser → export → Python → numbers

---

## Phase 2 — Features, twice

- [ ] **T9 · Port sessioniser + one feature to TS; stand up the parity suite** · M · deps: T3, T6
  - Compare both implementations on the fixture within 1e-9
  - **Break it deliberately once and confirm the suite fails**
  - Verify: `uv run pytest -m parity && npm test`

- [ ] **T10 · Port the remaining features** · M · deps: T9
  - Tag each with its compat class (`history` / `full`); set `featureSet` version
  - Verify: `uv run pytest -m parity && npm test`

- [ ] **CHECKPOINT C** — parity green and CI-blocking; leakage test passes both sides

---

## Phase 3 — Predict

- [ ] **T11 · In-browser training** · M · deps: T10
  - Transition table + logreg in an offscreen document; chunked, resumable, alarm-driven
  - Verify: `npm test -- model`; train on 90 days without being killed

- [ ] **T12 · Calibration and abstention** · M · deps: T11
  - Threshold from the accuracy-vs-coverage curve, not intuition
  - Verify: `uv run python -m tise_research.eval.calibrate --model logreg`

- [ ] **T13 · Prediction registry and automatic outcome resolution** · M · deps: T12
  - `hit` / `miss` / `expired` resolved with no user confirmation anywhere
  - Verify: force a prediction, satisfy it by browsing, confirm `hit` without clicking

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

- [ ] **T16 · Model tournament and benchmark report** · M · deps: T13
  - Identical folds for every model; report the XGBoost-vs-shipped gap; one documented failure
  - Verify: `uv run pytest research/tests/test_baseline_gate.py`

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

- [ ] Copyright holder for `LICENSE` (currently "Akash") — blocks T18
- [ ] Where the privacy policy is hosted — presumed `holycowstudios.in` — blocks T18
- [ ] Chrome Web Store developer account registered under the company identity (D13)
