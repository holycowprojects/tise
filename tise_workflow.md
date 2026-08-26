# Tise Workflow

## 1. Overview

**Tise** is a privacy-first personal behavioral intelligence system.

Its core workflow is:

> **Observe → Normalize → Protect → Learn → Detect → Predict → Explain → Verify → Improve**

Tise does not simply collect a user's data and ask an LLM to predict what the user will do. It builds a structured behavioral model from explicitly permitted activity, uses statistical and machine-learning models for measurable predictions, uses an LLM primarily for explanation and interaction, and then compares predictions with actual outcomes to continuously evaluate and improve the system.

---

# 2. Complete Workflow

```text
                         USER
                           │
                           ▼
                 ┌──────────────────┐
                 │  CONSENT MANAGER │
                 └────────┬─────────┘
                          │
                          ▼
                ┌───────────────────┐
                │  DATA CONNECTORS  │
                └─────────┬─────────┘
                          │
             ┌────────────┼────────────┐
             ▼            ▼            ▼
         Browser       App Usage    Imports/APIs
             │            │            │
             └────────────┼────────────┘
                          ▼
                 ┌─────────────────┐
                 │ EVENT NORMALIZER│
                 └────────┬────────┘
                          ▼
                 ┌─────────────────┐
                 │ PRIVACY FILTER  │
                 └────────┬────────┘
                          ▼
                 ┌─────────────────┐
                 │ LOCAL DATA STORE│
                 └────────┬────────┘
                          ▼
                 ┌─────────────────┐
                 │ FEATURE ENGINE  │
                 └────────┬────────┘
                          ▼
             ┌────────────┼────────────┐
             ▼            ▼            ▼
         Patterns      Interests     Intent
             │            │            │
             └────────────┼────────────┘
                          ▼
                 ┌─────────────────┐
                 │ PREDICTION ENGINE│
                 └────────┬────────┘
                          │
             ┌────────────┼────────────┐
             ▼            ▼            ▼
          XGBoost       TS Models   Survival
          LightGBM      Chronos      Models
             │            │            │
             └────────────┼────────────┘
                          ▼
                 ┌─────────────────┐
                 │ MODEL SELECTION │
                 └────────┬────────┘
                          ▼
                 ┌─────────────────┐
                 │   PREDICTION    │
                 │  + PROBABILITY  │
                 │  + TIME WINDOW  │
                 └────────┬────────┘
                          ▼
                 ┌─────────────────┐
                 │ LLM EXPLANATION │
                 └────────┬────────┘
                          ▼
                    USER DASHBOARD
                          │
                          ▼
                   ACTUAL OUTCOME
                          │
                          ▼
                 ┌─────────────────┐
                 │ MODEL EVALUATION│
                 └────────┬────────┘
                          │
                          ▼
                    MODEL IMPROVES
```

---

# 3. Step 1 — User Consent

Tise must begin with explicit user consent.

The user chooses which data sources Tise can access.

Example:

```text
                    TISE

What would you like Tise to learn from?

☑ Browser activity
☐ Application usage
☐ Shopping data
☐ Calendar
☐ Music
☐ Fitness
☐ Other integrations

                 [Continue]
```

Each connector should have its own permission.

### Principle

Tise should never attempt to bypass operating-system or application security controls.

It should use:

- official APIs
- approved permissions
- user-authorized integrations
- user-provided imports

---

# 4. Step 2 — Data Collection

Tise receives events from permitted sources.

For the MVP, the primary source can be browser activity.

Example user activity:

```text
Google
   ↓
"best laptop under ₹80,000"
   ↓
YouTube review
   ↓
Manufacturer website
   ↓
Shopping website
   ↓
Compare another laptop
   ↓
Read reviews
```

Tise converts these activities into events.

Example:

```text
10:01 — Search
10:08 — Product research
10:21 — Review/video
10:35 — Product comparison
10:51 — Price check
11:02 — Product research
```

The objective is to capture **behavioral signals**, not unnecessarily capture the entire contents of the user's digital life.

---

# 5. Step 3 — Event Normalization

Different sources produce different data.

For example:

```text
Browser:
"visited shopping website"

YouTube:
"watched laptop review"

Shopping:
"viewed product"

Calendar:
"meeting"

Fitness:
"workout"
```

Tise converts these into a common event format.

Example:

```json
{
  "event_id": "evt_123",
  "timestamp": "2026-08-19T14:32:00Z",
  "source": "browser",
  "event_type": "product_research",
  "category": "electronics",
  "session_id": "session_42",
  "duration_seconds": 183,
  "metadata": {}
}
```

This creates a common language for the intelligence layer.

---

# 6. Step 4 — Privacy Filtering

Before behavioral analysis, Tise applies a privacy filter.

The question is:

> **Do we actually need this data to perform the prediction?**

For example:

```text
RAW:

https://shopping-site.com/product/ABC123?customer=...

                  ↓

Tise keeps:

category = electronics
event = product_research
timestamp = ...
```

Tise should avoid collecting unnecessary information such as:

```text
Passwords
Authentication cookies
Payment credentials
Private messages
Sensitive form fields
Unnecessary page contents
```

### Privacy principle

> **Collect the minimum data required to produce the desired intelligence.**

---

# 7. Step 5 — Local Data Storage

The preferred architecture is local-first.

```text
User Device
     │
     ├── Raw events
     ├── Features
     ├── Behavioral memory
     └── Predictions
```

For the MVP:

```text
SQLite
```

is sufficient.

Raw behavioral data should remain on the user's device whenever practical.

Cloud services should only receive data when:

- the user explicitly permits it, and
- the feature actually requires it.

---

# 8. Step 6 — Sessionization

Raw events are noisy.

Tise groups related events into sessions.

Example:

```text
14:01 Google search
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

This makes behavioral patterns easier to model.

---

# 9. Step 7 — Feature Engineering

Raw events are transformed into numerical and categorical features.

## Temporal features

```text
hour
day_of_week
is_weekend
days_since_last_event
days_since_last_purchase
time_since_previous_session
```

## Frequency features

```text
events_1h
events_6h
events_24h
events_7d
events_30d
```

## Trend features

```text
category_count_7d
category_count_previous_7d
growth_rate
rolling_mean
rolling_std
```

## Behavioral features

```text
research_duration
comparison_count
repeat_visits
price_check_count
review_count
category_switch_rate
```

## Sequence features

```text
previous_event
previous_3_events
previous_5_events
transition_probability
```

These features become the input to the predictive models.

---

# 10. Step 8 — Behavioral Pattern Detection

Tise continuously searches for recurring behavioral sequences.

For example:

```text
Research
   ↓
Comparison
   ↓
Reviews
   ↓
Price checking
   ↓
Purchase
```

Suppose this pattern appears repeatedly.

Tise may learn:

```text
When this user:

1. researches a product,
2. compares several options,
3. watches reviews,
4. repeatedly checks prices,

a purchase frequently follows within several days.
```

The system stores this as a behavioral pattern.

---

# 11. Step 9 — Build the Personal Behavioral Model

Tise gradually builds a representation of the user's behavioral tendencies.

Example:

```text
                    USER
                     │
       ┌─────────────┼─────────────┐
       │             │             │
   Interests       Habits       Patterns
       │             │             │
       ▼             ▼             ▼
    AI/Tech       Evening use    Research →
    Fitness       Weekend use    Compare →
    Electronics   Long sessions  Review →
                                  Purchase
```

The model may learn:

```text
Typical research duration: 4.8 days
Typical comparison count: 3.7
Most active shopping period: evening

Common sequence:
research → reviews → comparison → purchase
```

These are learned patterns, not hard-coded assumptions.

---

# 12. Step 10 — Intent Detection

Tise can derive intent scores from behavioral features.

Examples:

```text
research_intent
purchase_intent
learning_intent
entertainment_intent
travel_intent
```

A purchase-intent score could incorporate:

```text
Search frequency
+
Repeated product visits
+
Comparison activity
+
Review consumption
+
Price checking
+
Historical behavior
```

The initial version should use transparent feature combinations and later test more advanced models.

---

# 13. Step 11 — Prediction Engine

Tise now asks:

> **Given the user's current behavior and historical behavior, what is likely to happen next?**

Different prediction problems require different models.

## Next-event prediction

```text
P(next_event | behavioral_history)
```

Candidate models:

- Markov models
- logistic regression
- XGBoost
- LightGBM
- sequence models

## Event-within-window prediction

Example:

```text
P(purchase_category_X <= 7 days)
```

Candidate models:

- logistic regression
- XGBoost
- LightGBM

## Time-to-event prediction

Example:

```text
How long until the next purchase?
```

Candidate models:

- Cox proportional hazards
- Weibull/AFT
- gradient-boosted survival models

## Activity forecasting

Example:

```text
How much shopping activity is likely tomorrow?
```

Candidate models:

- seasonal naive
- exponential smoothing
- ARIMA/SARIMA
- gradient boosting
- modern time-series foundation models

---

# 14. Step 12 — Model Tournament

Tise should not automatically assume that the newest model is the most accurate.

It should benchmark multiple approaches.

```text
Historical data
       │
       ├── Seasonal Naive
       ├── ETS
       ├── ARIMA/SARIMA
       ├── XGBoost
       ├── LightGBM
       ├── Chronos
       ├── TimesFM
       └── Other suitable models
              │
              ▼
         Backtesting
              │
              ▼
       Compare performance
              │
              ▼
        Select model
```

Each model must use the same:

- training data
- validation period
- test period
- features
- forecast horizon
- evaluation metrics

---

# 15. Step 13 — Leakage-Safe Backtesting

This is critical.

The model must never see future information while making a historical prediction.

Incorrect:

```text
Prediction date = Day 20

Features contain:
Day 1 → Day 30
```

Correct:

```text
Prediction date = Day 20

Features contain:
Day 1 → Day 20

Target:
Day 21 onward
```

Use chronological rolling-origin evaluation.

Example:

```text
Fold 1:
Jan → Mar | Apr

Fold 2:
Jan → Apr | May

Fold 3:
Jan → May | Jun
```

---

# 16. Step 14 — Modern Statistical and ML Models

Tise should maintain a model registry.

Example:

```python
MODEL_REGISTRY = {
    "seasonal_naive": SeasonalNaive(),
    "ets": ETSModel(),
    "arima": ARIMAModel(),
    "xgb": XGBoostModel(),
    "lightgbm": LightGBMModel(),
    "chronos": ChronosModel(),
    "timesfm": TimesFMModel()
}
```

Potential modern time-series foundation-model candidates can include current versions of:

- Chronos
- TimesFM
- MOIRAI
- other actively maintained forecasting foundation models

The system should select models based on measured performance, calibration, latency, resource use, and cost.

---

# 17. Step 15 — Generate a Probabilistic Prediction

Tise should not say:

> "You will buy a laptop."

It should produce a probabilistic forecast.

Example:

```text
┌──────────────────────────────────────┐
│              PREDICTION              │
│                                      │
│ Laptop purchase                      │
│                                      │
│ Probability: 74%                     │
│                                      │
│ Expected window: 2–7 days            │
│                                      │
│ Confidence: Medium-High              │
└──────────────────────────────────────┘
```

The probability must originate from an evaluated and calibrated model.

It should not be invented by the LLM.

---

# 18. Step 16 — Uncertainty and Calibration

A probability is only useful if it is reasonably calibrated.

If the system repeatedly predicts:

```text
80%
```

then roughly 80% of comparable events should occur.

Tise should monitor:

- Brier score
- log loss
- reliability curves
- Expected Calibration Error
- prediction intervals where appropriate

The interface should communicate uncertainty.

Example:

```text
Likely purchase

Probability: 72%

Expected:
2–7 days

Confidence:
Medium
```

If uncertainty is high:

```text
Possible purchase

Probability: 43%

Status:
Too uncertain for a strong prediction
```

---

# 19. Step 17 — Prediction Registry

Every prediction should be stored with enough metadata to reproduce and evaluate it.

Example:

```json
{
  "prediction_id": "pred_001",
  "created_at": "2026-08-19T14:00:00Z",
  "target": "purchase_running_shoes",
  "probability": 0.78,
  "time_window_days": [2, 6],
  "model_name": "xgboost",
  "model_version": "v4",
  "feature_version": "v7",
  "data_cutoff": "2026-08-19T14:00:00Z",
  "evidence": [
    "7 related searches",
    "3 product comparisons",
    "2 review sessions"
  ],
  "status": "active"
}
```

This enables reproducibility, debugging, and model evaluation.

---

# 20. Step 18 — LLM Explanation

The LLM is an explanation and interaction layer.

It receives structured results such as:

```json
{
  "prediction": "purchase_running_shoes",
  "probability": 0.78,
  "time_window": "2–6 days",
  "evidence": [
    "7 related searches",
    "3 comparisons",
    "2 reviews"
  ]
}
```

The LLM can produce:

> You appear likely to purchase running shoes within the next week. The model estimates a 78% probability based on repeated research, comparisons, and review activity. Similar historical sequences have often preceded purchases.

The LLM should not arbitrarily change the numerical prediction.

The architecture is:

```text
Behavioral data
      ↓
Statistical/ML model
      ↓
Numerical forecast
      ↓
LLM
      ↓
Human-readable explanation
```

Not:

```text
Behavioral data
      ↓
LLM
      ↓
Made-up probability
```

---

# 21. Step 19 — User Dashboard

The dashboard presents:

## Overview

```text
Today's activity
Emerging interests
Behavioral changes
Active predictions
```

## Prediction card

```text
Likely next action

Running shoe purchase

Probability: 78%

Expected:
2–6 days

Why?

• 7 related searches
• 3 product comparisons
• 2 review sessions
• Similar historical behavior
```

## Timeline

```text
08:10  Research
09:20  Shopping
10:05  AI
11:40  Shopping
```

## Behavioral trends

```text
AI interest       ↑ 34%
Shopping          ↑ 21%
Fitness           ↑ 18%
Entertainment     ↓ 11%
```

---

# 22. Step 20 — Wait for the Actual Outcome

This is what closes the prediction loop.

Example:

```text
August 19

Prediction:
Running shoe purchase
Probability: 78%
```

Later:

```text
August 23

Actual:
Running shoes purchased
```

Tise records:

```text
Prediction = Correct
```

If the user does not purchase:

```text
Prediction = Incorrect
```

This creates ground truth for future evaluation.

---

# 23. Step 21 — Model Evaluation

Tise compares predictions against reality.

For classification/event prediction:

```text
Accuracy
Precision
Recall
F1
Brier score
Log loss
Calibration
```

For numerical forecasting:

```text
MAE
RMSE
MASE
sMAPE
Pinball loss
CRPS
```

The system can maintain rolling performance:

```text
Model             Recent performance

Seasonal Naive       0.58
Logistic Regression  0.64
XGBoost              0.72
Chronos              0.69
TimesFM              0.67
```

These are example values only. Tise must use actual measured results.

---

# 24. Step 22 — Continuous Improvement

The complete learning loop becomes:

```text
        OBSERVE
           │
           ▼
       NORMALIZE
           │
           ▼
        PROTECT
           │
           ▼
         STORE
           │
           ▼
        FEATURES
           │
           ▼
        PATTERNS
           │
           ▼
        PREDICT
           │
           ▼
        EXPLAIN
           │
           ▼
          WAIT
           │
           ▼
      ACTUAL OUTCOME
           │
           ▼
        EVALUATE
           │
           ▼
        RETRAIN/
        RECALIBRATE
           │
           └──────────────► PREDICT AGAIN
```

This feedback loop is the heart of Tise.

---

# 25. Example: Laptop Purchase

Consider a real sequence.

## Monday

```text
Search:
"best laptop under ₹80,000"
```

Tise detects:

```text
Interest:
Electronics

Intent:
Research
```

## Tuesday

```text
3 laptop review videos
```

Tise detects:

```text
Research intensity ↑
```

## Wednesday

```text
Compare:

Laptop A
Laptop B
Laptop C
```

Tise detects:

```text
Comparison intensity ↑↑
```

## Thursday

```text
Multiple price checks
```

Tise detects:

```text
Purchase intent ↑↑↑
```

## Thursday prediction

```text
Likely next action:

Laptop purchase

Probability:
74%

Expected:
2–7 days
```

## Explanation

The LLM receives the structured forecast and explains:

```text
Your current activity resembles previous product-research
sequences that have often ended in a purchase. You have
repeatedly searched, compared, reviewed, and price-checked
laptops this week.
```

## Outcome

Suppose the user purchases a laptop three days later.

Tise records:

```text
Prediction:
Correct
```

The model's historical evaluation improves.

---

# 26. Tise Can Predict More Than Purchases

The same architecture can predict multiple categories.

## Shopping

```text
Likely next purchase
```

## Entertainment

```text
Likely content category
```

## Learning

```text
Likely next learning topic
```

## Work

```text
Likely upcoming activity
```

## Interests

```text
Emerging interest
```

## Digital habits

```text
Likely evening activity
```

## Re-engagement

```text
Likely return to an abandoned topic
```

---

# 27. The Three Intelligence Layers

Tise can be thought of as having three major "brains."

```text
┌─────────────────────────────────────┐
│              TISE                   │
│                                     │
│  1. MEMORY                          │
│     What has happened?              │
│                                     │
│  2. PREDICTION                      │
│     What is likely to happen?       │
│                                     │
│  3. REASONING                       │
│     Why might it happen?            │
│                                     │
└─────────────────────────────────────┘
```

### Memory

Stores:

- events
- features
- patterns
- historical outcomes
- behavioral summaries

### Prediction

Uses:

- statistical models
- ML
- time-series forecasting
- survival analysis
- sequence modeling

### Reasoning

Uses the LLM for:

- explanation
- natural-language questions
- summarization
- conversational exploration
- what-if interaction

---

# 28. Privacy-First Architecture

The preferred architecture is:

```text
                    USER DEVICE
┌────────────────────────────────────────┐
│                                        │
│  Data Connectors                       │
│        ↓                               │
│  Raw Events                            │
│        ↓                               │
│  Privacy Filter                        │
│        ↓                               │
│  Feature Engineering                   │
│        ↓                               │
│  Prediction Models                     │
│        ↓                               │
│  Behavioral Memory                     │
│                                        │
└──────────────────┬─────────────────────┘
                   │
            Only when necessary
                   │
                   ▼
             Optional LLM
                   │
                   ▼
              Explanation
```

The default should be:

> **Raw behavioral data stays on the user's device.**

---

# 29. Security Boundaries

Tise must never attempt to:

- bypass OS sandboxing
- bypass application permissions
- collect passwords
- collect authentication cookies
- capture keystrokes
- secretly monitor private communications
- defeat browser security
- access protected application databases without authorization

Instead, use:

- official APIs
- explicit permissions
- approved integrations
- user-provided exports
- local processing

---

# 30. Long-Term: Personal Behavioral Twin

The long-term vision is a continuously updated **Personal Behavioral Twin**.

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

The user could eventually ask:

> What am I likely to do tomorrow?

> What am I likely to purchase this month?

> What changed in my behavior this week?

> Which interests are becoming stronger?

> What normally happens after this behavior?

> What would probably happen if I changed this habit?

---

# 31. Final Workflow in One Sentence

> **Tise continuously converts permitted digital activity into privacy-preserving behavioral signals, learns recurring patterns from those signals, uses statistically evaluated and calibrated models to forecast probable next actions, explains the forecasts through an LLM, observes what actually happens, evaluates the prediction, and uses the results to improve future forecasts.**

---

# 32. Core Design Principle

The central architectural separation should remain:

```text
            TISE INTELLIGENCE

                 ┌─────────┐
                 │ MEMORY  │
                 └────┬────┘
                      │
                      ▼
                 ┌─────────┐
                 │ PREDICT │
                 └────┬────┘
                      │
                      ▼
                 ┌─────────┐
                 │ EXPLAIN │
                 └────┬────┘
                      │
                      ▼
                 ┌─────────┐
                 │ VERIFY  │
                 └────┬────┘
                      │
                      ▼
                 ┌─────────┐
                 │ IMPROVE │
                 └─────────┘
```

**ML/statistical models decide what is likely.  
The LLM explains why.  
Actual outcomes determine whether Tise was right.**
