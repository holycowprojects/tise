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
  - Owed before any number reaches the README: confidence intervals (T16)

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
