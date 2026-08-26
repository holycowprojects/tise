# Tise — Privacy-First Personal Behavioral Intelligence

**Project goal:** Build a low-cost, portfolio-grade system that learns behavioral patterns from explicitly consented digital activity and predicts likely next actions using strong statistical/ML forecasting models, while keeping raw personal data on-device wherever practical.

> **Important:** Tise is a defensive, consent-driven analytics product. It must not bypass OS/application sandboxing, collect data secretly, steal credentials, read private app databases without permission, or defeat security controls.

---

## 1. Executive Summary

Tise turns permitted digital activity into a sequence of behavioral events, derives privacy-preserving features, detects patterns, and predicts likely future actions.

Example:

```text
Browser activity
      ↓
Product research
      ↓
Multiple comparisons
      ↓
Review watching
      ↓
Repeated price checking
      ↓
Prediction:
Purchase likely within 2–6 days
Probability: 0.78
```

The key engineering principle is:

> **Use statistical/ML models for numerical prediction and an LLM only for explanation and interaction.**

Do not ask an LLM to invent probabilities.

---

# 2. Product Definition

## Working name

**Tise**

## One-line pitch

> A privacy-first personal behavioral intelligence agent that learns from consented digital activity and forecasts likely next actions with calibrated uncertainty.

## Target users

Initially:

- developers
- AI/ML engineers
- researchers
- privacy-conscious power users
- people interested in quantified-self systems

## Portfolio positioning

The project should demonstrate:

- event-driven architecture
- data engineering
- behavioral modeling
- time-series forecasting
- probabilistic prediction
- model evaluation
- uncertainty calibration
- privacy engineering
- local inference
- LLM/tool integration
- observability
- responsible AI

---

# 3. MVP Scope

Do not attempt universal access to every app in V1.

Build:

1. Chrome/Chromium extension
2. Local Python agent
3. Local SQLite database
4. Feature-engineering pipeline
5. Baseline forecasting models
6. Modern time-series model experiments
7. Behavioral pattern engine
8. Prediction registry
9. Dashboard
10. Evidence/explanation layer

Chrome extensions must declare permissions and host access in their Manifest V3 configuration. Chrome explicitly recommends requesting the minimum permissions necessary and using optional permissions where possible. See the official documentation:

- https://developer.chrome.com/docs/extensions/develop/concepts/declare-permissions
- https://developer.chrome.com/docs/extensions/develop/security-privacy/user-privacy

The MVP should therefore use narrow permissions and make data collection transparent.

---

# 4. Product Requirements

## Functional requirements

### FR-01 — Consent

The user must explicitly enable each data source.

### FR-02 — Data collection

The system must collect only the minimum fields needed for a feature.

### FR-03 — Normalization

All sources must be converted into a common event schema.

### FR-04 — Local storage

Raw events should be stored locally by default.

### FR-05 — Feature generation

The system must transform raw events into behavioral features.

### FR-06 — Prediction

The system must generate:

- predicted event
- probability
- expected time window
- confidence/calibration information
- supporting evidence

### FR-07 — Explainability

Every prediction must answer:

- What is predicted?
- Why?
- What evidence was used?
- How confident is the model?
- What could make the prediction wrong?

### FR-08 — Data controls

The user must be able to:

- pause collection
- delete data
- export data
- disable individual sources

### FR-09 — Model evaluation

Every production model must be compared against simple baselines.

---

# 5. Non-Goals for V1

Do NOT build:

- unrestricted access to all applications
- credential/password collection
- covert monitoring
- keylogging
- private-message scraping
- bank credential access
- bypassing OS security
- browser security bypasses
- invasive background surveillance
- fully autonomous actions such as purchases

These create unnecessary technical, security, platform-policy, and privacy risks.

---

# 6. System Architecture

```text
                         USER
                          │
                          ▼
                 ┌─────────────────┐
                 │ Consent Manager │
                 └────────┬────────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
       Chrome Extension        Manual CSV Import
              │                       │
              └───────────┬───────────┘
                          ▼
                  Event Collector
                          │
                          ▼
                 Privacy Filter
                          │
                          ▼
                  Local Event Store
                          │
                          ▼
                 Feature Pipeline
                          │
             ┌────────────┼─────────────┐
             ▼            ▼             ▼
        Pattern      Event Model    Time Series
        Engine         Engine        Features
             │            │             │
             └────────────┼─────────────┘
                          ▼
                 Forecasting Layer
                          │
             ┌────────────┼─────────────┐
             ▼            ▼             ▼
          Baseline      ML Models      TSFM
          Models        XGBoost       Chronos
                        LightGBM      TimesFM
                          │
                          ▼
                  Model Selection
                          │
                          ▼
                Prediction Registry
                          │
             ┌────────────┴────────────┐
             ▼                         ▼
       Explanation Layer          Dashboard
             │                         │
             ▼                         ▼
            LLM                  User Interface
```

---

# 7. Recommended Tech Stack

## Recommended MVP stack

| Layer | Technology |
|---|---|
| Extension | TypeScript + Chrome Manifest V3 |
| Frontend | Next.js + TypeScript |
| UI | Tailwind CSS |
| Charts | Recharts |
| API | FastAPI |
| ML | Python |
| Data | pandas + NumPy |
| Local DB | SQLite |
| Production DB | PostgreSQL |
| Vector search | pgvector, only if needed |
| ML baseline | scikit-learn |
| Gradient boosting | XGBoost / LightGBM |
| Classical forecasting | statsmodels |
| TS foundation models | Chronos / TimesFM / other current candidates |
| Experiment tracking | MLflow or simple local JSON first |
| Tests | pytest + Playwright |
| Packaging | Docker |
| Hosting | Vercel + low-cost backend |
| LLM | API model or local model |
| Version control | GitHub |

---

# 8. Why SQLite First?

Do not start with:

- Kubernetes
- Kafka
- Redis
- vector databases
- distributed workers
- microservices

They add complexity without helping the MVP.

Start with:

```text
Chrome Extension
      ↓
FastAPI
      ↓
SQLite
      ↓
Python ML
      ↓
Next.js
```

Move to PostgreSQL only after you have a working product.

---

# 9. Event Schema

Create a canonical event format.

```json
{
  "event_id": "evt_123",
  "timestamp": "2026-08-19T14:32:00Z",
  "source": "browser",
  "event_type": "page_visit",
  "category": "shopping",
  "domain": "example.com",
  "object_id": null,
  "session_id": "session_42",
  "duration_seconds": 183,
  "metadata": {}
}
```

Do not put unnecessary raw page content in `metadata`.

---

# 10. Database Schema

## events

```sql
CREATE TABLE events (
    event_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    source TEXT NOT NULL,
    event_type TEXT NOT NULL,
    category TEXT,
    domain TEXT,
    session_id TEXT,
    duration_seconds REAL,
    metadata_json TEXT
);
```

## features

```sql
CREATE TABLE features (
    feature_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    feature_name TEXT NOT NULL,
    feature_value REAL NOT NULL
);
```

## predictions

```sql
CREATE TABLE predictions (
    prediction_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    target TEXT NOT NULL,
    probability REAL NOT NULL,
    expected_start TEXT,
    expected_end TEXT,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    evidence_json TEXT,
    status TEXT
);
```

---

# 11. Browser Extension

Use Manifest V3.

Keep permissions minimal.

Possible MVP permissions should be evaluated carefully; do not request broad host access merely because it might be useful later.

Example concept:

```json
{
  "manifest_version": 3,
  "name": "Tise",
  "version": "0.1.0",
  "permissions": [
    "storage"
  ],
  "optional_permissions": [
    "tabs"
  ]
}
```

Use optional host permissions where appropriate.

Chrome documents that optional permissions allow functionality to be enabled at runtime instead of granting everything at installation. This is preferable for a privacy-sensitive product.

Official references:

- https://developer.chrome.com/docs/extensions/reference/manifest
- https://developer.chrome.com/docs/extensions/reference/api/permissions

---

# 12. Data Collection Strategy

The collector should produce high-level events.

Example:

```text
Google search
       ↓
category = research
       ↓
product research
       ↓
event
```

Avoid:

```text
Capture entire page
Capture passwords
Capture form fields
Capture private messages
Capture cookies
```

The less sensitive data you collect, the smaller your privacy/security attack surface.

---

# 13. Sessionization

Raw browser events are noisy.

Group events into sessions.

Example:

```text
14:01 Google
14:03 Product page
14:07 Review
14:12 Price comparison
14:18 Product page
```

becomes:

```json
{
  "session_id": "s_001",
  "start": "14:01",
  "end": "14:18",
  "category": "shopping",
  "events": 5,
  "duration_minutes": 17
}
```

Use a simple inactivity threshold initially:

```python
SESSION_TIMEOUT_MINUTES = 30
```

Make it configurable.

---

# 14. Feature Engineering

## Temporal

```text
hour
day_of_week
is_weekend
days_since_last_event
days_since_last_purchase
time_since_previous_session
```

## Frequency

```text
events_1h
events_6h
events_24h
events_7d
events_30d
```

## Trend

```text
category_count_7d
category_count_previous_7d
growth_rate
rolling_mean
rolling_std
```

## Behavioral

```text
research_duration
number_of_comparisons
repeat_visits
price_checks
review_count
category_switch_rate
```

## Sequence

```text
previous_event
previous_3_events
previous_5_events
transition_probability
```

---

# 15. Behavioral Intent Detection

Create an intent score.

Example:

```text
research_score
comparison_score
purchase_intent_score
learning_intent_score
entertainment_intent_score
```

A purchase intent score could combine:

```text
search frequency
+
repeat visits
+
comparison activity
+
review consumption
+
price checking
+
historical purchase pattern
```

Do not make the first version overly complicated.

---

# 16. Prediction Problems

Tise contains several prediction tasks.

## Problem A — Next event

```text
P(event_t+1 | history)
```

Start with a transition/Markov baseline.

Then test:

- logistic regression
- XGBoost
- LightGBM
- sequence models

## Problem B — Event within N days

Example:

```text
P(purchase_category_X <= 7 days)
```

Use:

- logistic regression
- XGBoost
- LightGBM

## Problem C — Time until event

Use survival analysis:

- Cox proportional hazards
- Weibull/AFT
- gradient-boosted survival models

## Problem D — Activity volume

Example:

```text
minutes_spent_on_shopping tomorrow
```

Use:

- seasonal naive
- exponential smoothing
- ARIMA/SARIMA
- gradient boosting
- modern TS foundation models

---

# 17. Latest Model Strategy

Do not define "latest" as "automatically best."

Build a model tournament.

Candidate families:

### Baselines

- last value
- moving average
- seasonal naive

### Classical

- exponential smoothing
- ETS
- ARIMA/SARIMA

### ML

- XGBoost
- LightGBM

### Modern time-series foundation models

Evaluate current candidates such as:

- Chronos family
- TimesFM family
- MOIRAI family
- other actively maintained open forecasting foundation models

Recent 2026 research continues to show that time-series foundation models can outperform traditional baselines in some domains, while model strengths vary by dataset and context. Therefore Tise should benchmark them rather than assuming superiority.

Recent research examples:

- https://arxiv.org/abs/2607.20027
- https://arxiv.org/abs/2607.23146

---

# 18. Model Tournament

Every candidate gets exactly the same:

```text
training period
validation period
test period
features
forecast horizon
metrics
```

Example:

```text
Model              MAE     MASE    Brier
-----------------------------------------
Seasonal Naive     12.1    1.00    0.241
ETS                 10.8    0.91    0.229
XGBoost              9.7    0.83    0.201
Chronos              8.9    0.77    0.187
TimesFM              9.2    0.80    0.192
```

Select the winner per task, not globally.

---

# 19. Avoid Data Leakage

This is one of the most important parts of the project.

Never allow future information into training features.

Bad:

```text
event at day 20
feature generated using days 1–30
```

Good:

```text
prediction made at day 20
features use only days <= 20
target uses days 21+
```

Use chronological splits.

Never randomly shuffle a time-series dataset.

---

# 20. Backtesting

Use rolling-origin evaluation.

```text
Train ───────── Validation
      ↓
Train ───────────────── Validation
      ↓
Train ─────────────────────── Validation
```

Example:

```text
Fold 1:
Jan → Mar | Apr

Fold 2:
Jan → Apr | May

Fold 3:
Jan → May | Jun
```

This better represents real-world forecasting.

---

# 21. Metrics

## Point forecasts

Use:

- MAE
- RMSE
- MASE
- sMAPE

MAE should be the easiest primary metric to communicate.

## Probabilistic forecasts

Use:

- Brier score
- log loss
- pinball loss
- CRPS when applicable

## Calibration

If predictions say:

```text
80% probability
```

then approximately 80% of similar predictions should happen.

Measure:

- reliability curves
- Expected Calibration Error
- Brier score

---

# 22. Uncertainty

Never display:

```text
You WILL buy a laptop.
```

Display:

```text
Likely laptop purchase

Probability: 72%

Expected window:
2–7 days

Confidence:
Medium

Why:
...
```

If uncertainty is high:

```text
Prediction:
Possible laptop purchase

Probability:
43%

Status:
Too uncertain to make a strong prediction
```

A good system should know when not to predict.

---

# 23. Prediction Registry

Each prediction should be reproducible.

```json
{
  "prediction_id": "pred_001",
  "target": "purchase_running_shoes",
  "probability": 0.78,
  "time_window_days": [2, 6],
  "model": "xgboost_v4",
  "features_version": "features_7",
  "data_cutoff": "2026-08-19T14:00:00Z",
  "evidence": [
    "7 related visits",
    "3 product comparisons",
    "2 review sessions"
  ]
}
```

This is extremely useful for debugging.

---

# 24. LLM Layer

The LLM receives structured results.

Input:

```json
{
  "prediction": "purchase_running_shoes",
  "probability": 0.78,
  "window": "2-6 days",
  "evidence": [
    "7 related searches",
    "3 comparisons",
    "2 reviews"
  ]
}
```

LLM output:

> You appear likely to purchase running shoes within the next week. The model estimates a 78% probability based on repeated research, comparisons, and review activity.

The LLM must NOT change:

```text
probability
forecast
confidence
time window
```

unless a separate, explicitly evaluated reasoning component is introduced later.

---

# 25. Behavioral Memory

Store derived behavioral summaries.

Example:

```text
User tends to:
- research products for 3–8 days
- compare multiple products
- read reviews before purchase
- purchase after repeated price checks
```

This can be represented as structured records:

```json
{
  "pattern": "purchase_after_research",
  "category": "electronics",
  "estimated_delay_days": 5.2,
  "sample_count": 8,
  "confidence": 0.81
}
```

Avoid building a giant vector database at the beginning.

---

# 26. Privacy Architecture

Preferred:

```text
RAW DATA
   │
   ▼
LOCAL DEVICE
   │
   ├── feature extraction
   ├── prediction
   └── behavioral memory
           │
           ▼
     Optional cloud
           │
           ▼
     LLM explanation
```

Do not send raw browsing history to the cloud unless the user explicitly opts in.

---

# 27. Security Requirements

Implement:

- local encryption where practical
- secure API authentication
- HTTPS
- strict CORS
- input validation
- rate limiting
- secrets outside source control
- dependency scanning
- audit logging
- data deletion
- export functionality

Never store:

- passwords
- authentication cookies
- private keys
- payment credentials

unless a future feature explicitly requires an approved secure integration—and even then, avoid storing credentials yourself.

---

# 28. API Design

## POST /events

```json
{
  "events": []
}
```

## GET /events

Returns paginated normalized events.

## GET /features

Returns derived features.

## GET /predictions

Returns active predictions.

## GET /predictions/{id}

Returns:

- prediction
- evidence
- model
- probability
- time window
- evaluation metadata

## DELETE /data

Deletes user data.

## POST /import

Imports supported CSV data.

---

# 29. Suggested Repository

```text
tise/
│
├── apps/
│   ├── dashboard/
│   └── extension/
│
├── services/
│   ├── api/
│   ├── collector/
│   ├── feature_engine/
│   └── predictor/
│
├── ml/
│   ├── datasets/
│   ├── features/
│   ├── baselines/
│   ├── models/
│   ├── evaluation/
│   └── experiments/
│
├── data/
│   └── .gitkeep
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── ml/
│   └── e2e/
│
├── docs/
│   ├── architecture.md
│   ├── privacy.md
│   └── model-card.md
│
├── docker-compose.yml
├── README.md
└── LICENSE
```

---

# 30. Development Plan

## Day 1 — Foundation

- create repository
- create FastAPI project
- create Next.js project
- create Chrome extension
- create SQLite database
- define event schema
- implement `/events`

Deliverable:

```text
Browser → API → SQLite
```

---

## Day 2 — Collector

Implement:

- extension event capture
- event normalization
- batching
- local queue
- retry handling
- consent UI

Deliverable:

```text
Real browser activity
        ↓
Normalized events
```

---

## Day 3 — Features

Implement:

- sessionization
- daily aggregates
- rolling windows
- category statistics
- sequence features

Deliverable:

```text
Events → behavioral feature table
```

---

## Day 4 — Baseline Prediction

Implement:

- naive baseline
- moving average
- logistic regression
- XGBoost

Create first prediction endpoint.

---

## Day 5 — Modern Forecasting

Add experiments for:

- ETS
- ARIMA/SARIMA where appropriate
- current time-series foundation model candidates

Do not blindly deploy the largest model.

Benchmark them.

---

## Day 6 — Calibration

Implement:

- probability calibration
- Brier score
- reliability curves
- uncertainty thresholds

Example:

```text
probability < 0.50
→ don't display strong prediction

0.50–0.70
→ possible

0.70–0.85
→ likely

>0.85
→ very likely
```

These thresholds are starting points, not scientific truths. Tune them using validation data.

---

## Day 7 — Dashboard

Build:

### Overview

```text
Activity
Intentions
Predictions
Patterns
```

### Prediction card

```text
Likely next action
72%

Expected:
2–6 days

Evidence:
...
```

### Timeline

```text
08:10 Research
09:20 Shopping
10:05 AI
11:40 Shopping
```

---

## Day 8 — LLM explanation

Add structured explanation.

Do not give the LLM raw history.

Send:

```text
prediction
probability
time window
evidence
model metadata
```

---

## Day 9 — Testing

Run:

- unit tests
- integration tests
- extension tests
- API tests
- ML tests
- leakage tests
- privacy tests

---

## Day 10 — Portfolio polish

Create:

- architecture diagram
- model benchmark
- demo video
- README
- model card
- privacy document
- screenshots
- evaluation report

---

# 31. Testing Strategy

## Unit tests

Test:

- event normalization
- timestamp parsing
- sessionization
- feature calculation
- probability calibration
- prediction serialization

Example:

```python
def test_sessionization():
    events = [...]
    sessions = sessionize(events)
    assert len(sessions) == 2
```

---

# 32. ML Tests

## Leakage test

Create a synthetic future event and verify that the feature pipeline cannot access it.

## Determinism

Same:

```text
data
+
model version
+
seed
```

should produce the same prediction within expected numerical tolerance.

## Baseline test

A new model should not be accepted if it performs worse than the required baseline without a documented reason.

---

# 33. Data Quality Tests

Check:

```text
missing timestamps
duplicate events
invalid categories
negative durations
future timestamps
impossible session durations
```

Example:

```python
assert duration_seconds >= 0
assert timestamp <= now
```

---

# 34. Privacy Tests

Verify that:

- passwords are never collected
- cookies are never collected
- page content is not collected by default
- disabled sources stop collecting
- deletion actually removes data
- exports contain only intended fields
- logs do not contain raw sensitive content

---

# 35. Security Tests

Run:

- dependency vulnerability scanning
- static analysis
- secret scanning
- API authorization tests
- malformed input tests
- rate-limit tests

Tools:

- GitHub Dependabot
- Semgrep
- Bandit
- pip-audit
- npm audit

---

# 36. Evaluation Dataset

Initially, create a synthetic dataset.

Example:

```text
Day 1:
search laptop

Day 2:
review laptop

Day 3:
compare laptops

Day 4:
price check

Day 5:
purchase
```

Generate thousands of synthetic sequences with known patterns.

Then evaluate using anonymized/self-generated real activity.

Never use somebody else's private data without appropriate permission.

---

# 37. Synthetic Data Generator

Create patterns such as:

```text
research → compare → review → purchase
```

```text
search → abandon
```

```text
research → repeat research → purchase
```

```text
interest → inactivity → renewed interest
```

This lets you validate the system before collecting large quantities of real data.

---

# 38. Model Selection Policy

Use:

```text
IF new_model MAE < baseline MAE
AND calibration improves
AND latency acceptable
AND resource cost acceptable
THEN candidate for deployment
```

Do not optimize accuracy alone.

Use a weighted decision:

```text
Model Score =
accuracy
+
calibration
+
latency
+
memory
+
privacy
+
cost
```

---

# 39. Minimum-Budget Infrastructure

## Local development

Cost:

```text
$0
```

Use:

- local Python
- SQLite
- local Next.js
- local Chrome extension

## Optional cloud

Use free/low-cost tiers for:

- frontend
- API
- database

But the product should remain usable locally.

## LLM

For the MVP:

- use a low-cost API only for explanation

Better:

- make LLM provider configurable
- support a local model later

---

# 40. Cost-Control Strategy

Do not send every event to an LLM.

Bad:

```text
100,000 events
→ 100,000 LLM calls
```

Good:

```text
100,000 events
       ↓
local feature engineering
       ↓
20 behavioral summaries
       ↓
1 explanation request
```

This can reduce API cost dramatically.

---

# 41. Performance Targets

Initial targets:

```text
Event ingestion:
<100 ms local processing

Dashboard:
<2 seconds

Prediction:
<5 seconds

Batch forecasting:
<30 seconds

LLM explanation:
<10 seconds

Raw data:
local by default
```

These are engineering targets, not guarantees.

---

# 42. Model Lifecycle

```text
Data
 ↓
Feature version
 ↓
Train
 ↓
Validate
 ↓
Backtest
 ↓
Calibration
 ↓
Model registry
 ↓
Deploy
 ↓
Monitor
 ↓
Retrain
```

Store:

```text
model_name
model_version
training_cutoff
feature_version
metrics
hyperparameters
```

---

# 43. Monitoring

Track:

### Data drift

```text
category distribution
event frequency
session duration
```

### Prediction drift

```text
average probability
prediction count
prediction acceptance
```

### Accuracy

When actual events become known:

```text
predicted vs actual
```

Calculate rolling performance.

---

# 44. Feedback Loop

After a prediction:

```text
Prediction:
Buy running shoes
Probability:
78%
```

Later:

```text
Actual:
Purchased running shoes
```

Store:

```text
prediction_correct = true
```

Now the model can be evaluated continuously.

---

# 45. Avoid Self-Fulfilling Predictions

Do not automatically perform the predicted action.

Example:

```text
Prediction:
User may buy laptop
```

Tise should not:

```text
open Amazon
add laptop to cart
```

The first version is strictly analytical.

---

# 46. Mobile Roadmap

## Android

Later add a companion app using permitted Android APIs.

Android exposes app usage information through `UsageStatsManager`, subject to the relevant permission/user authorization.

Official documentation:

https://developer.android.com/reference/android/app/usage/UsageStatsManager

## iOS

Later investigate Apple's authorized Screen Time/Family Controls capabilities.

Do not design the system around unrestricted access to other apps.

---

# 47. Version Roadmap

## V0.1

Browser activity.

## V0.2

Behavioral pattern detection.

## V0.3

Purchase-intent prediction.

## V0.4

Modern time-series forecasting.

## V0.5

Prediction explanations.

## V0.6

Android companion.

## V0.7

Optional integrations:

- calendar
- GitHub
- music
- shopping exports
- fitness data

## V1.0

Personal Behavioral Twin.

---

# 48. Future Behavioral Twin

Long-term architecture:

```text
                  PERSONAL TWIN
                       │
       ┌───────────────┼────────────────┐
       │               │                │
   Preferences      Habits          Intentions
       │               │                │
       └───────────────┼────────────────┘
                       │
                 Prediction Engine
                       │
              ┌────────┼────────┐
              ▼        ▼        ▼
           Next       Future   What-if
           action     trend    simulation
```

Example questions:

> What am I likely to do tomorrow?

> What am I likely to purchase this month?

> What behavioral patterns changed this week?

> Which emerging interests are becoming stronger?

> What normally happens after this behavior?

> What would happen if I changed this habit?

---

# 49. What Makes This Project Strong for AI Jobs

The portfolio should emphasize engineering depth rather than the UI.

Show:

### 1. Real ML evaluation

```text
Baseline
vs
XGBoost
vs
Chronos
vs
TimesFM
```

### 2. Calibration

Show:

```text
Predicted probability
vs
actual frequency
```

### 3. Time-series backtesting

Show rolling-origin evaluation.

### 4. Privacy architecture

Show that raw data stays local.

### 5. LLM architecture

Show:

```text
ML → structured forecast → LLM explanation
```

rather than:

```text
LLM → random prediction
```

### 6. Failure analysis

Show examples where the model failed.

This is particularly valuable in interviews.

---

# 50. Interview Demo

The ideal demo:

```text
1. Install extension

2. Browse normally

3. Dashboard collects events

4. Behavioral patterns appear

5. Model trains on historical activity

6. Model predicts next action

7. Prediction includes probability

8. User clicks "Why?"

9. Evidence appears

10. Actual outcome later updates evaluation

11. Model accuracy dashboard updates
```

Then show:

```text
Model benchmark

Seasonal Naive   MAE 1.00
XGBoost          MAE 0.83
Chronos          MAE 0.77
TimesFM          MAE 0.80
```

Use your actual measured numbers in the final project; never fabricate benchmark results.

---

# 51. Recommended First Implementation

Do this exact sequence.

```text
STEP 1
Create GitHub repository

STEP 2
Create FastAPI service

STEP 3
Create SQLite database

STEP 4
Define Event schema

STEP 5
Create Chrome MV3 extension

STEP 6
Collect basic browser events

STEP 7
Send events to local API

STEP 8
Implement sessionization

STEP 9
Generate daily features

STEP 10
Build seasonal-naive baseline

STEP 11
Build XGBoost model

STEP 12
Implement rolling backtest

STEP 13
Add calibration

STEP 14
Test current TSFM candidates

STEP 15
Build prediction registry

STEP 16
Build dashboard

STEP 17
Add LLM explanations

STEP 18
Add privacy controls

STEP 19
Add tests

STEP 20
Publish technical write-up
```

---

# 52. Definition of Done

The MVP is finished when:

- [ ] Browser extension works
- [ ] User explicitly enables collection
- [ ] Events are normalized
- [ ] Raw events are stored locally
- [ ] Sessions are generated
- [ ] Features are generated
- [ ] Baseline model works
- [ ] ML model works
- [ ] Modern forecasting candidate is benchmarked
- [ ] No future leakage exists
- [ ] Rolling backtest exists
- [ ] Probabilities are calibrated
- [ ] Predictions have evidence
- [ ] Predictions have time windows
- [ ] Dashboard displays predictions
- [ ] User can delete data
- [ ] User can export data
- [ ] LLM only explains structured forecasts
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Security checks pass
- [ ] Privacy review is complete
- [ ] README explains architecture
- [ ] Benchmark results are reproducible

---

# 53. Final Architecture Recommendation

For your situation, do **not** over-engineer.

Build:

```text
              Chrome Extension
                     │
                     ▼
                 FastAPI
                     │
                     ▼
                  SQLite
                     │
                     ▼
             Feature Pipeline
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
    XGBoost/LightGBM       Time-Series Models
          │                     │
          └──────────┬──────────┘
                     ▼
              Model Tournament
                     │
                     ▼
             Prediction Registry
                     │
             ┌───────┴────────┐
             ▼                ▼
        Next.js UI       LLM Explainer
```

Then expand only after the MVP proves that the core prediction problem works.

---

# 54. The Most Important Technical Principle

Your claim should **not** be:

> "We use the latest AI model, therefore our predictions are accurate."

Your claim should be:

> **"Tise continuously benchmarks simple statistical baselines, classical ML, and modern time-series foundation models using leakage-safe rolling backtests and calibrated probabilistic evaluation, then selects the model that performs best for each forecasting task under accuracy, latency, cost, and privacy constraints."**

That is a much stronger engineering story.

---

# 55. References

### Chrome extension permissions

https://developer.chrome.com/docs/extensions/develop/concepts/declare-permissions

### Chrome extension security/privacy

https://developer.chrome.com/docs/extensions/develop/security-privacy/user-privacy

### Chrome Manifest

https://developer.chrome.com/docs/extensions/reference/manifest

### Chrome Permissions API

https://developer.chrome.com/docs/extensions/reference/api/permissions

### Android UsageStatsManager

https://developer.android.com/reference/android/app/usage/UsageStatsManager

### Recent time-series foundation-model research

https://arxiv.org/abs/2607.20027

https://arxiv.org/abs/2607.23146

---

# 56. Final Recommendation

Start with **browser behavior → purchase/intent prediction**.

Do not start with:

```text
all apps
all data
mobile
social media
email
finance
LLM agents
```

That will turn a potentially excellent 10-day project into a six-month integration project.

The strongest MVP is:

```text
Observe
   ↓
Normalize
   ↓
Understand
   ↓
Predict
   ↓
Explain
   ↓
Measure whether prediction was correct
```

If you execute that loop well, Tise becomes a serious applied-AI portfolio project rather than another chatbot demo.
