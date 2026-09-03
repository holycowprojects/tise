# Tise

**Status: working, not yet released.** The extension builds, collects, trains and predicts
on a real profile. It is not on the Chrome Web Store, and the prediction target changed in
August 2026 — see [Where this is](#where-this-is).

A privacy-first personal behavioural forecasting system. Tise learns patterns from your own
browsing, predicts what you are likely to do next, shows you the evidence behind every
prediction, and then measures whether it was right.

Everything runs on your machine. Nothing is transmitted anywhere.

---

## The principle

> Statistical and machine-learning models decide what is likely.
> The interface explains why.
> Actual outcomes decide whether Tise was right.

Tise does not hand your browsing history to a language model and print whatever number
comes back. Probabilities come from models that are backtested, calibrated and scored
against what actually happened — trained **in your browser**, on your own history.

## Privacy

- Raw browsing data never leaves your device.
- **No full URL is ever stored.** Every page is reduced to its registrable domain before an
  event object is constructed — no path, query string, fragment, page content, form value,
  cookie, credential or keystroke.
- No accounts, no sync, no telemetry, no analytics.
- Raw events are deleted after 30 days by default; only aggregated behavioural features
  are kept longer.
- You can pause collection, export everything, or delete everything at any time.
- Nothing is collected before you consent. The extension installs with no capability to
  read anything.

The author cannot see your data. **There is no server that could receive it** — no backend,
no API, no hosted component of any kind. The repository layout below is the whole system.

## Honest limitations

Written down here rather than discovered later:

- **Most published benchmark numbers come from one person's browsing** — the author's,
  across three browsers, measured separately and never merged. Because Tise collects nothing
  from its users, no evaluation on *its own* users is possible or wanted. Between-browser
  results vary by nearly 2×, which is a lower bound on how much they would vary between
  people. The **one exception** is the current target, which was additionally tested on 1,326
  consenting participants in a published research panel (never pooled, one analysis each) —
  and that panel is German, desktop-only, and from October 2018, so it is a check on
  generalisation rather than a claim about everyone.
- **Tise has no dwell time, and cannot have any.** Chrome's history *database* records how
  long you spent on a page; the `chrome.history` API does not expose it, and neither does
  live navigation monitoring. Research run against the database file can measure things the
  shipped extension can never compute, so every analysis reports both variants and only the
  achievable one constrains the product.
- **Predictions about rare events are not measured.** Purchase prediction is included as a
  demonstration and is labelled unvalidated. Only frequent events that confirm themselves
  from the event stream are scored.
- **New users start with a cold model.** Existing browser history is imported on first run
  to reduce this, but imported history is reconstructed from the history database through an
  approximation, where live collection observes navigations directly. The size of that
  difference has not yet been measured.

## Where this is

**Two prediction targets were built, benchmarked and retired before the third one worked.**

`return_24h` — "will you return to this topic within 24 hours?" — was retired because it
turned out to be measurable and uninteresting: a ~70% base rate meant a constant answer was
already most of the way right, and a single browsing session is not a unit anyone cares
about.

`block_volume` — "will a topic's activity in the coming day be above its own usual level?" —
was retired because the model **lost to a single constant** on all three corpora, and
"same as last time" was far worse still, which says daily activity is close to independent
day to day.

That work is kept, not deleted. Those reports in [`docs/benchmarks/`](docs/benchmarks) stand
as superseded results and carry banners saying so — they are the evidence that justified the
changes, and removing them would remove the reason.

**The current target is `visit_engaged`.** It is the first one to clear a bar that was
written down before it was measured — and the first result in this project that does not rest
on a single person:

> At the moment a page opens: will you stay on it longer than you usually stay on pages of
> this topic?

One label per **visit** — the finest unit the data contains, and thousands of them where the
retired targets had hundreds. Its definition, features, baseline, resampling unit and
adoption rule were all fixed in advance and committed before a model was fitted; git holds
the order. See [`docs/benchmarks/visit-engaged.md`](docs/benchmarks/visit-engaged.md).

**Then it was tested on 1,326 other people.** Everything above was measured on the author's
own browsing, which says little about whether it generalises. So the same model was run
separately for each of 1,326 consenting participants in a published research panel — never
pooled — and it beats its baseline for **88.6% of them individually**. The rule for what would
count as replication, and seven predicted outcomes, were committed before that run; six held,
and the one that missed had **underestimated** how consistently it works.

That panel measures attention with idle time excluded, which is a *better* measurement than
the author's own data could provide — so the largest known caveat on the original result is
now closed rather than outstanding.

**Adopted is not shipped.** It needs how long you actually looked at a page, which the
`chrome.history` API cannot supply — so the extension collects that itself, from the day the
permission was granted, and there is not yet enough of it to train on. Until there is, the
extension keeps training the old target and the UI keeps showing nothing. Nothing gets wired
in before it is built end to end.

## Repository layout

```
extension/   Chrome MV3 extension — collection, features, training, prediction, UI
research/    Python research tier — features mirrored, backtests, calibration, evaluation
analysis/    One-off measurement scripts that write the benchmark reports
docs/        Benchmarks, design history, privacy policy draft
tasks/       Plan and task list
.github/     Continuous integration and dependency updates
data/        Local data — never committed
```

The extension is the product; **`research/` runs only on the author's machine** and is fed
by the extension's own export file, so the privacy feature and the research pipeline are
the same mechanism. There is no service to run.

Features are implemented **twice** — TypeScript for the product, Python for research — and a
parity suite asserts the two agree to 1e-9 against a committed oracle. Without it, every
published benchmark could describe a model that was never shipped.

## Checks

```
uv run pytest             Research suite
uv run pytest -m parity   The parity suite — TypeScript and Python must agree
uv run ruff check .
npm test                  Extension suite, from extension/
npm run lint
npm run build             Typechecks and produces the loadable unpacked extension
```

All of it runs on every push and pull request, and the parity suite runs a second time on
its own **against a committed floor on how many tests it contains**. A green suite proves
the tests that ran passed; it does not prove the parity tests were among them, and deleting
one is the quietest way to make a parity failure stop happening.

The same job asserts that nothing under `data/`, no history database, no export and no
credential-shaped string is tracked by git — `git ls-files` being the truth about what would
be published, where `.gitignore` is only a prediction about it.

## Documents

- [`DECISIONS.md`](DECISIONS.md) — every non-obvious choice, why it was made, and what was
  rejected. Includes the audit of the original design documents, every correction to a
  claim made here, and the reasoning behind the target change. It is append-only.
- [`SPEC.md`](SPEC.md) — data contracts, boundaries, success criteria.
- [`docs/benchmarks/`](docs/benchmarks) — every published number, each generated by a
  committed script and regenerable from it.
- [`docs/design-history/`](docs/design-history) — the original design documents, kept
  unchanged. Superseded, but preserved because the decision log refers to them.

## Benchmarks

Available in [`docs/benchmarks/`](docs/benchmarks). The current target's report is
[`visit-engaged.md`](docs/benchmarks/visit-engaged.md); the replication on 1,326 other people
is not published there, because that corpus is licensed non-commercially and its report stays
local. Reports describing a **retired** target carry a banner saying so, generated rather than
typed, so they cannot quietly go stale. Reports that measure the browsing itself — session
boundaries, domain concentration, how visits reach the extension — are unaffected and stand.

**No number is published that a committed script did not produce.** No hand-written
benchmarks, and no synthetic data used as a benchmark — synthetic data appears only in unit
tests, where it proves the arithmetic rather than the model.

The most useful thing in there may be the negative results. Confidence intervals withdrew
the project's own flagship claim; a tournament against XGBoost could not separate it from a
hand-written logistic regression; and the abstention machinery, working exactly as designed,
concluded there was not enough evidence to say anything at all.

## Development

```
cd extension && npm install && npm test && npm run build   # loads unpacked from dist/
uv sync && uv run pytest                                    # research tier
uv run pytest -m parity                                     # the suite that matters most
```

## Licence

MIT — see [`LICENSE`](LICENSE). Copyright Akash Navet and Holy Cow Studios Private Limited.
