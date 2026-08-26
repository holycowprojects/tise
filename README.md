# Tise

**Status: pre-alpha. No working code yet.**

A privacy-first personal behavioural forecasting system. Tise learns patterns from your
own browsing, predicts what you are likely to do next, shows you the evidence behind
every prediction, and then measures whether it was right.

Everything runs on your machine. Nothing is transmitted anywhere.

---

## The principle

> Statistical and machine-learning models decide what is likely.
> The interface explains why.
> Actual outcomes decide whether Tise was right.

Tise does not hand your browsing history to a language model and print whatever number
comes back. Probabilities come from models that are backtested, calibrated and scored
against what actually happened.

## Privacy

- Raw browsing data never leaves your device.
- No accounts, no sync, no telemetry, no analytics.
- No passwords, cookies, form fields, keystrokes or page content are collected.
- Raw events are deleted after 30 days by default; only aggregated behavioural features
  are kept longer.
- You can pause collection, export everything, or delete everything at any time.

The author cannot see your data. There is no server that could receive it.

## Honest limitations

Written down here rather than discovered later:

- **All published benchmark numbers come from one person's browsing** — the author's.
  Because nothing is collected from users, no larger evaluation is possible.
- **Predictions about rare events are not measured.** Purchase prediction is included as
  a demonstration and is labelled as unvalidated. Only frequent events that confirm
  themselves from the event stream are scored.
- **New users start with a cold model.** Existing browser history is imported on first
  run to reduce this, but imported history lacks dwell time and is therefore weaker than
  live data.

## Repository layout

```
extension/   Chrome MV3 extension — collection and user interface
service/     Local Python service — features, models, prediction, evaluation
ml/          Experiments, baselines, benchmark notebooks
analysis/    One-off analysis scripts
data/        Local data (never committed)
docs/        Design history and specifications
```

## Documents

- [`DECISIONS.md`](DECISIONS.md) — every non-obvious choice, why it was made, and what
  was rejected. Includes the audit of the original design documents.
- [`docs/design-history/`](docs/design-history) — the original design documents, kept
  unchanged. Superseded, but preserved because the decision log refers to them.

## Benchmarks

Not yet available. This section will be filled in with measured results as data
accumulates. No numbers will be published that were not actually measured.

## Licence

MIT — see [`LICENSE`](LICENSE).
