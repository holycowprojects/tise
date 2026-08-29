# Spec: Tise V1

**Status:** built and working, not released. The extension collects, imports, trains,
predicts, expires and exports; 675 Python and 338 TypeScript tests pass. **No prediction
target is adopted** — two have been retired and four are pre-registered and unfitted.
**Decisions this spec implements:** D1–D95 in [`DECISIONS.md`](DECISIONS.md), which is
authoritative wherever this file disagrees with it.

---

## Objective

Tise is a Chrome extension that learns behavioural patterns from a person's own browsing
and predicts what they are likely to do next, showing the evidence behind every prediction
and measuring whether it was right. Everything runs on the user's machine and nothing is
transmitted.

It exists to demonstrate that Holy Cow Studios builds rigorously evaluated machine
learning, not only chatbots and automations (D1). It is published open source and listed
on the Chrome Web Store, where the listing itself — an extension that transmits nothing,
backed by readable source — is part of the argument.

**Primary user:** the author, whose browsing produces every published number (D2).
**Secondary user:** anyone who installs it, whose data the author never sees.

### What success looks like

1. A public repository someone can read and believe.
2. A Web Store listing that truthfully declares zero data transmission.
3. A reliability curve, computed from real browsing, showing that stated probabilities
   are approximately correct.
4. A benchmark table where every number was actually measured (D3).
5. A documented case where the model failed and why.

### Non-goals for V1

No LLM (D8). No server, no accounts, no sync, no telemetry. No mobile. No application or
OS-level monitoring. No automated actions taken on the user's behalf. No purchase
prediction as an evaluated claim (D6).

---

## Architecture

The single most important structural decision: **the product and the research are
separate tiers that share a data format, not a runtime.**

```
  ┌──────────────────────── USER'S BROWSER ────────────────────────┐
  │                                                                │
  │   Chrome history import ──┐                                    │
  │                           ├──> Event Normaliser                │
  │   webNavigation events ───┘          │                         │
  │                                      ▼                         │
  │                              Category Resolver                 │
  │                                      │                         │
  │                                      ▼                         │
  │                          IndexedDB (raw, 30 days)              │
  │                                      │                         │
  │                                      ▼                         │
  │                          Sessioniser + Features                │
  │                                      │                         │
  │                         ┌────────────┴────────────┐            │
  │                         ▼                         ▼            │
  │              IndexedDB (features, kept)      Online Model      │
  │                                                   │            │
  │                                                   ▼            │
  │                                          Prediction + Evidence │
  │                                                   │            │
  │                                                   ▼            │
  │                                          Extension UI          │
  └────────────────────────────┬───────────────────────────────────┘
                               │
                     "Export my data" (JSON)
                               │  manual, author only
                               ▼
  ┌──────────────────────── AUTHOR'S MACHINE ──────────────────────┐
  │   research/  Python: backtests, model tournament, calibration   │
  │   Produces the benchmark numbers published in the README.       │
  └────────────────────────────────────────────────────────────────┘
```

There is **no API, no server and no local service.** The export feature required by the
privacy controls is the same mechanism that feeds the research tier. This removes
authentication, CORS, rate limiting, Docker and deployment from V1 entirely.

**Consequence, accepted:** the shipped model is limited to what can be trained in
JavaScript — transition tables and logistic regression. Gradient boosting lives in the
research tier only, to quantify what the in-browser constraint costs. That gap is
reported honestly rather than hidden.

---

## Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Extension | TypeScript 5.x, Chrome Manifest V3 | Service worker only (D63) |
| Extension build | Vite | Outputs to `extension/dist/` |
| Extension UI | Vanilla TS + CSS | No framework — D5 caps polish deliberately |
| Extension storage | IndexedDB via `idb` | SQLite is not practical in an extension |
| Extension tests | Vitest | |
| Research | Python 3.12, `uv` | |
| Research data | pandas, pyarrow | Parquet for intermediate data |
| Research models | scikit-learn, XGBoost, statsmodels | Research tier only |
| Research tests | pytest | |
| Lint/format | ESLint + Prettier, Ruff | |

**Not used, deliberately:** FastAPI, Next.js, Postgres, Docker, MLflow, any vector
database, any LLM API. Each was in the original design and each earns nothing in V1.

---

## Commands

```bash
# Extension (from extension/)
npm install
npm run dev                  # Vite watch build; load extension/dist/ unpacked
npm run build                # Production build
npm run test                 # Vitest
npm run test -- --coverage
npm run lint                 # ESLint
npm run format               # Prettier --write
npm run package              # Zip extension/dist/ for Web Store upload

# Research (from research/)
uv sync
uv run pytest
uv run pytest -m parity      # TS/Python feature parity suite
uv run ruff check .
uv run ruff format .

uv run python -m tise_research.data.load    --export ../data/export.json
uv run python -m tise_research.eval.backtest --with-model      # superseded target
uv run python -m tise_research.eval.calibrate --model logreg   # superseded target
uv run python -m tise_research.eval.tournament                 # superseded target
uv run python analysis/day_of_week.py

# Analysis (from repo root)
uv run python analysis/history_shape.py --db "<path to Chrome History>" --out data/
```

---

## Project Structure

```
extension/
  src/
    collect/      webNavigation listeners, history import, event normaliser
    categories/   domain -> category resolver + shipped map + user overrides
    storage/      IndexedDB schema, retention enforcement, export, delete
    features/     sessioniser, feature computation  [PARITY-CRITICAL]
    model/        transition table, logistic regression, calibration, abstention
    background.ts service worker entry
  ui/             popup, dashboard page, onboarding, privacy settings
  icons/
  tests/
  manifest.json

research/
  tise_research/
    data/         loaders for exported JSON, synthetic generator
    features/     Python mirror of extension features  [PARITY-CRITICAL]
    models/       baselines, logreg, XGBoost, survival
    eval/         backtest, calibration, tournament, reports
  fixtures/       shared golden fixtures for the parity suite
  tests/

analysis/         one-off scripts; not part of the product
data/             local only, never committed
docs/
  design-history/ the three original design documents, unchanged
  benchmarks/     generated benchmark output
tasks/            plan.md and todo.md
```

**`[PARITY-CRITICAL]`** marks the two directories that implement the same logic twice, in
two languages. See Testing Strategy.

---

## Data Contracts

### Event

Emitted by the collector, stored raw, deleted after `raw_retention_days`.

```ts
interface TiseEvent {
  eventId: string;          // uuid
  occurredAt: string;       // ISO 8601, UTC
  source: "live" | "import";
  domain: string;           // registrable domain only, e.g. "amazon.in"
  category: string;         // from the resolver; "unknown" is a valid value
  transition: string;       // Chrome transition type: link | typed | reload | ...
  dwellSeconds: number | null;  // null for imported history — see D10
  sessionId: string;
  titleTokens?: string[];   // optional, category resolution only, never persisted raw
}
```

**Never present in this type, by design:** full URL with query string or path, page
content, form values, cookies, credentials. The collector reduces a URL to its
registrable domain before the event is constructed — the full URL never reaches storage.

### Feature Row

Survives raw deletion (D11), so this schema is effectively permanent.

```ts
interface FeatureRow {
  computedAt: string;
  windowEnd: string;        // data cutoff — no feature may use data after this
  featureSet: string;       // e.g. "fs_1" — bumped on any change
  compat: "history" | "full";  // "history" excludes dwell-dependent features (D10)
  values: Record<string, number>;
}
```

### Prediction

```ts
interface Prediction {
  predictionId: string;
  createdAt: string;
  // Shipped today (extension/src/model/prediction.ts): "return_24h" | "next_session_category".
  // The union below is the T21 target state; the TS type changes when T21 lands, not before.
  target: "visit_engaged" | "browsing_next_hour" | "next_category" | "tab_return";
  subject: string;          // the topic or category being predicted about
  probability: number;      // calibrated, 0..1
  windowStart: string;
  windowEnd: string;
  abstained: boolean;       // retained for stored return_24h rows; D88 retired the policy
  modelName: string;
  modelVersion: string;
  featureSet: string;
  dataCutoff: string;
  evidence: string[];
  outcome: "pending" | "hit" | "miss" | "expired";
  resolvedAt: string | null;
}
```

`outcome` is written **automatically** by matching later events against the window. No
user confirmation button exists in the evaluation loop (D6) — this is the resolution of
the contradiction recorded in the audit.

---

## Prediction Targets

**Two targets have been retired. One is adopted; three remain pre-registered and unfitted.**
The authoritative list is D94 in `DECISIONS.md`, and D97 records the adoption.

### T-A — `visit_engaged` (primary, **adopted D97**, not yet shipped)

> At the moment a page opens: will dwell exceed the median dwell for this category over its
> trailing 20 visits?

One label **per visit** — the finest unit the data contains. **The first target in this
project to clear a bar that was written down before it was measured.** D94 fixed the label,
the feature set (`as_2`), the bar, the cluster unit and the adoption rule before the code
existed; git holds the order.

| | `history-chrome` | `history-edge` *(adoption corpus)* |
|---|---|---|
| `logreg_as2` vs the constant, **session-clustered** | +0.0038 [+0.0006, +0.0101] (n=27) | +0.0112 [+0.0068, +0.0159] (n=155) |
| the same, under the old *subject* unit | −0.0005 … +0.0318 (n=9) — includes zero | −0.0054 … +0.0166 (n=11) — includes zero |

**Both halves of D94's change were needed.** Under the old cluster unit the identical point
estimate includes zero on both corpora; with the unit fixed, `as_2` still beats `as_1` by an
interval excluding zero. D93 had neither and missed by 0.0001.

**`domain` carries it, on its first use in the project.** Stored since T1, read by zero
features until `as_2`. `domainDwellLevel` is the second-largest coefficient on both corpora,
and on Edge a plain per-domain rate table (0.2453) nearly matches D93's whole twelve-feature
model (0.2446). On Chrome that table does nothing (0.2499 vs the constant's 0.2500).

**`full` compat class:** it needs dwell time, which the `chrome.history` API cannot supply.
The `tabs` permission (authorised) makes it shippable; `idle` (authorised) fixes its
**labels**, since `visit_duration` records a tab left open overnight as deep engagement.

**Bar: a constant.** D93 established that `category_base_rate` is *worse* than a constant
here, because a per-category median split makes every category ~50% by construction.

**Adopted is not shipped.** There is no TypeScript twin of `as_2`, so the parity contract is
unmet, and the live attention spans it needs began collecting only at D96. The extension
still trains `return_24h` and still shows nothing.

### T-B — `browsing_next_hour` · T-C — `next_category` · T-D — `tab_return`

Pre-registered in D94 with definitions, bars, cluster units and adoption rules fixed before
implementation. T-D needs live tab data and cannot be measured on any existing corpus.

### T-E — session intent clustering · T-F — domain association rules

Descriptive candidates from D95. Neither needs to clear a prediction bar to be useful.

### The cluster unit changed for all of them (D94), and it decided T-A (D97)

Every interval this project published was resampled over **9–12 subject clusters**, because
the subject was always the category. Width scales with 1/√clusters, so no comparison here
could resolve a small effect regardless of data volume. D94 declares **session** clustering
with the category unit reported alongside.

D97 measured what that is worth: T-A's point estimate **includes zero under the old unit and
excludes it under the new one, on both corpora.** `brier_difference_interval` now takes
`unit=` so a printed interval names what it actually resampled.

**A cluster count is not cluster quality.** Chrome's 27 test sessions include one holding
43% of the rows, so most resamples turn on whether that session was drawn. Every report that
clusters now prints the spread beside the count.

### T1-superseded — `block_volume` (retired as product target, D92)

> Will topic *X*'s activity in the next block exceed *X*'s own trailing median?

Retired because the model **lost to a single constant** on all three corpora, and
`same_as_last` was far worse still — so "above your usual" is close to **independent day to
day**. Its per-topic *rate* survives as a shippable card without a model; the model does not.

### T1-superseded — `return_24h` (retired as product target, D88)

> Given activity in topic *X* today, what is the probability of returning to topic *X*
> within 24 hours?

Retired because a session is not a unit a person cares about, and a 65–72% base rate is
nearly all of the answer. **Kept as research**: D15–D87 and every report in
`docs/benchmarks/` stand as a recorded, superseded result — they are the evidence that
justifies the change.

### T2 — `next_session_category` (UI only, reported but not headline)

Multiclass over the category set. Displayed as a top-3 list. Reported as top-1 and top-3
accuracy; calibration is not claimed for it in V1.

### T3 — novelty (candidate, unmeasured)

> Will the next block contain a domain not seen in the prior 30 days?

Resolvable from stored domains alone. Answers "are you exploring or entrenching", which is
information a person does not have about themselves. Base rate unknown; if it is near 100%
the target is dead, and the measurement will say so.

### T4 — dormancy (candidate, unmeasured)

> This topic has not appeared in *N* blocks. Is it finished?

The inverse framing, and it rescues what D26 currently discards: 9 of 15 categories sit
below the label floor, and those sparse ones are exactly where "is this dead?" is both
answerable and interesting. Also the destination for topics failing T1's qualifying rule.

### T5 — purchase intent (demo, explicitly unvalidated)

Shown in the UI with a visible "not enough data to evaluate this" label. Present because
it is the intuitive example; never presented as a measured claim (D6).

---

## Model Strategy

Every target runs a tournament against baselines. **No model ships that does not beat its
baseline**, and the baseline result is published either way.

| Tier | Models | Runs in |
|---|---|---|
| Baseline | marginal frequency, "same as last time", time-of-day prior | both |
| Shipped | transition table, logistic regression + Platt/isotonic calibration | extension |
| Research only | XGBoost, LightGBM, Cox / Weibull survival | Python |

Time-series foundation models are **out of scope for V1.** The audit found they address a
problem shape Tise does not have, and require far more history than a user will have.
If tested later, it will be on activity-volume forecasting only, clearly scoped.

### Showing the evidence, not abstaining (D88)

**Every prediction is shown, and every prediction carries its denominator.**

> **Shopping this weekend · 71%** — *11 of your last 15 weekends.*

One floor remains: a topic needs a minimum number of prior blocks before it appears at
all. Percentages are whole numbers — a decimal place implies 1-in-1000 resolution from
fifteen observations.

This replaces D69/D70's certify-or-stay-silent rule, which is retired with the target it
was built for. That rule was sound and, on real data, silenced everything: no threshold
could certify 90% accuracy because doing so needed >12,800 answered rows against 61–133
available. Thin evidence is now made **visible** rather than hidden behind silence.

The accuracy-versus-coverage curve is still a published result. It is no longer a gate.

---

## Category Resolution

The largest undesigned piece in the original documents (open question Q2). Layered, in
order:

1. **Shipped map** — `extension/src/categories/domains.json`, **264** curated registrable
   domains across 15 categories, plus 24 keyword rules. Human-readable, reviewable in a
   pull request, auditable by anyone. Its being inspectable is a privacy feature.
   Deliberately **generic**: employer, school, local government, neighbourhood businesses
   and personal accounts are excluded on purpose, because this file is public and a domain
   list is a profile.
2. **Keyword rules** — over page title tokens and URL path segments, when the domain is
   unknown. Tokens are used and discarded; never persisted.
3. **Learned clusters (D88)** — domains grouped by session co-occurrence and time of day,
   computed **on-device**, named by the user once a cluster has held together:

   > *We noticed a pattern. 6 sites you visit together, usually weekday mornings.
   > What should we call this?*

   This is the only route that can shrink `unknown`, because what lands there is personal
   by nature — precisely what layer 1 excludes on purpose. **The goal is converting
   `unknown` into named clusters, not multiplying categories:** D26 already finds 9 of 15
   categories below the label floor, so the taxonomy is too fine for the data, not too
   coarse. Versioned as its own taxonomy and benchmarked separately — categories are the
   subject of every prediction, so swapping them silently redefines the target.
4. **`unknown`** — a valid, first-class value, and a tracked quality metric. It currently
   holds ~20% of Chrome labels (79 labels, 92.5% positive), all discarded from published
   numbers because a bucket called "unknown" is unpresentable.
5. **User override** — a local per-domain override, stored locally, never uploaded. Always
   wins.

No LLM, no remote lookup, no network call of any kind. Cluster naming is done by the user
because it is the one part no local model can do.

---

## Code Style

TypeScript: strict mode, no `any`, no default exports, explicit return types on exported
functions. Pure functions for anything parity-critical — no I/O, no clock access, no
randomness inside feature computation.

```ts
// extension/src/features/recency.ts
import type { TiseEvent } from "../types";

/**
 * Hours since the most recent event in `category` strictly before `windowEnd`.
 * Returns null when the category has never been seen.
 *
 * PARITY-CRITICAL: research/tise_research/features/recency.py must match exactly.
 */
export function hoursSinceLastSeen(
  events: readonly TiseEvent[],
  category: string,
  windowEnd: Date,
): number | null {
  let latest: number | null = null;
  for (const event of events) {
    const t = Date.parse(event.occurredAt);
    if (t >= windowEnd.getTime()) continue;   // leakage guard
    if (event.category !== category) continue;
    if (latest === null || t > latest) latest = t;
  }
  return latest === null ? null : (windowEnd.getTime() - latest) / 3_600_000;
}
```

Python mirrors this shape: pure functions, explicit `window_end`, the same leakage guard,
the same null semantics, snake_case names mapping one-to-one to the TypeScript camelCase.

**Every feature function takes `windowEnd` explicitly and filters strictly before it.**
This is the structural defence against leakage — it is not possible to write a leaking
feature without deleting that line, and the leakage test exists to catch exactly that.

---

## Testing Strategy

| Level | Tool | Location | What it protects |
|---|---|---|---|
| Unit | Vitest / pytest | `extension/tests`, `research/tests` | normalisation, sessionising, feature maths |
| Parity | pytest `-m parity` | `research/fixtures/` | TS and Python compute identical features |
| Leakage | pytest | `research/tests` | no feature can see past `windowEnd` |
| Determinism | both | | same data + version + seed → same output |
| Privacy | Vitest | `extension/tests` | forbidden fields never persist; delete really deletes |
| Baseline gate | pytest | `research/tests` | no model ships that loses to its baseline |

### The parity suite is the one that matters

Features are implemented twice — TypeScript in the product, Python in the research tier.
If they drift, every published benchmark describes a model that is not the shipped one.

The suite loads a shared JSON fixture of events, runs both implementations, and asserts
the resulting feature vectors are identical within floating-point tolerance. It runs in
CI on every commit touching either directory. **A parity failure blocks everything.**

### Leakage test

Inject a synthetic event dated after `windowEnd`, recompute all features, assert every
value is unchanged. Any feature that moves is reading the future.

### Privacy tests

Assert, against a populated database: no stored record contains a `?` or `#`, a path
segment, a token resembling a credential, or any field outside the `TiseEvent` schema;
that `deleteAll()` leaves zero rows across every store; that export output validates
against the published schema and contains nothing else; and that disabling collection
stops writes.

Coverage expectation: 90% on `features/` and `model/`, 70% elsewhere. Coverage is a floor
for the parity-critical code and is not treated as a goal in itself.

---

## Boundaries

**Always**
- Run `npm test` and `uv run pytest` before committing.
- Bump `featureSet` on any change to feature computation, and record why in
  `DECISIONS.md`.
- Keep `DECISIONS.md` append-only; supersede entries rather than editing them.
- Write a justification string for every Chrome permission the moment it is added.
- Label any unmeasured number in the UI or README as unmeasured.

**Ask first**
- Adding any Chrome permission or host permission.
- Adding a dependency to either tier.
- Changing the `TiseEvent` or `FeatureRow` schema — feature rows are permanent (D11).
- Anything that makes a network request, for any reason.
- Publishing to the Web Store.

**Never**
- Transmit user data anywhere. There is no exception and no opt-in in V1.
- Store a full URL, page content, form value, cookie, credential or keystroke.
- Publish a benchmark number that was not produced by a committed script.
- Use synthetic data as a benchmark. Fixtures and tests only (audit finding 10).
- Let an LLM produce, adjust or round a probability.
- Commit anything from `data/`.

---

## Success Criteria

Testable conditions for "V1 is done":

1. Extension installs unpacked and records events from real browsing.
2. First-run import ingests existing Chrome history and produces predictions immediately.
3. Raw events older than `raw_retention_days` are provably deleted; feature rows survive.
4. `deleteAll()` leaves zero rows; export validates against the published schema.
5. Parity suite passes: TS and Python features identical on the shared fixture.
6. Leakage test passes.
7. The adopted target clears its data-sufficiency gate on real browsing. **D94 fixes each
   target's gate before it is fitted.** T1's original "≥300 in 8 weeks" was retired with
   `return_24h`, and `block_volume`'s with D92.
8. A reliability curve exists from those outcomes, with Brier score and ECE reported.
9. The shipped model beats all three baselines on the adopted target, or ships with a
   written explanation of why it does not. **Every performance bar is pre-registered before
   any model is fitted** (D91, D94). D94 also fixes the **stopping rule**: if no target
   separates from its declared bar, Tise ships descriptive and that is published as the
   headline.
10. An accuracy-versus-coverage curve is published. It is a result, not a gate — D88
    replaced abstention with showing every prediction alongside its denominator.
11. Every number in the README traces to a committed script.
12. `DECISIONS.md` records at least one documented model failure and its cause.

---

## Risks

| Risk | Mitigation |
|---|---|
| TS/Python feature drift silently invalidates every benchmark | Parity suite, CI-gated, blocking |
| MV3 service worker is killed mid-training | Chunk the work; `chrome.alarms` to resume. Chunking alone was sufficient, so no offscreen document (D63) |
| Bursty browsing yields too few labels | Event-level prediction as well as session-level (D9); history import provides backfill |
| Imported history lacks dwell time, so bootstrap features differ from live | `compat` field on every feature row; models trained per compat class |
| Web Store review rejects the permission set | Minimum permissions verified experimentally before listing; every one justified in writing |
| Category map is wrong and quietly poisons everything | `unknown` rate published as a quality metric; user override; map is reviewable |
| Project stalls between bursts (D4, D14) | Each milestone independently committable and leaves the repo working |

---

## Open Questions

1. **Exact minimum permission set.** The original manifest could not have collected
   anything (audit finding 7). The precise combination of `webNavigation`, `tabs`,
   `history` and host permissions needed to observe navigation with a URL must be
   verified experimentally, not assumed — then each is justified in writing for the
   listing.
2. **Session timeout.** Inherited as 30 minutes from the original document. To be
   measured against real history before being fixed (D9).
3. **Category set.** How many categories, and which. Too few loses signal; too many
   starves each class of examples. Decide from the history-shape analysis.
4. **Copyright holder in `LICENSE`.** Currently "Akash". Pending D13.
5. **Where the privacy policy is hosted** for the Web Store listing. Presumed
   `holycowstudios.in`, not confirmed.
