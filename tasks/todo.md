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
  - **Confidence intervals are the gate on every T11 claim.** "Wins 2 of 5 folds" on ~55
    test labels a fold may be indistinguishable from noise, and until intervals exist that
    sentence is the honest summary rather than the Brier score (D60)
  - **Cumulative features extrapolate** — 77.5% of Edge test rows sit outside the fitted
    range of `hoursSinceFirstSeen`. Any transform must be chosen without looking at the
    current scores, or it is fitted to the test set (D60)
  - **Corpus comparability is broken and the benchmarks depend on it** (D65). The research
    view and the extension disagree on 7.7% of events — matching totals hid it. Decide
    one view, re-run every number in `docs/benchmarks/`, do not argue it

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
