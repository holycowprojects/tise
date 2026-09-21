# Tise

[![CI](https://github.com/holycowprojects/tise/actions/workflows/ci.yml/badge.svg)](https://github.com/holycowprojects/tise/actions/workflows/ci.yml)

**A Chrome extension that learns your browsing habits and tells you what it has noticed —
entirely on your own computer.**

There is no account, no server, and no company receiving your data. The learning happens
inside your browser, on your laptop, and the answers stay there.

**Status: working, not yet released.** Not on the Chrome Web Store yet.

---

## What it actually records

Most software says "we respect your privacy". Here is exactly what that means, so you can
check it rather than trust it.

When you visit `youtube.com/watch?v=abc123`, Tise writes down **`youtube.com`** and the time.

That is all. It never stores the page address, what you searched for, what you read, what
you typed, your passwords or your cookies. Not "encrypted" — **not stored at all.** The rest
of the address is discarded before Tise writes anything down.

So what Tise knows about you is roughly *"video, 9:15pm on a Tuesday, arrived from a link"*.
Repeated a few thousand times that is enough to see patterns, and not enough to know what
you were actually doing.

## What it shows you

Your own habits, counted honestly:

- **What tends to follow what** — *"after shopping you usually go to search"*, with the
  number of times that has actually happened.
- **Which topics you really spend time on**, with the real counts underneath.
- **How much attention a page genuinely held** — not how long a tab sat open, but how long
  you were actually looking at it.
- **A scorecard of Tise's own accuracy**, including the times it was wrong.

Every number comes with its denominator. "You do this 70% of the time" means something very
different at 7 times out of 10 than at 700 out of 1,000, and Tise always says which.

## How it helps you

**Today, it mostly helps you see yourself clearly.** Most people are wrong about their own
browsing — where the hours go, what they keep returning to, what they only think they read.
Tise counts it instead of guessing, and it does not flatter you.

The forecasting is real but deliberately slow to arrive. One prediction has genuinely earned
its place — *will this page hold your attention, or will you leave in ten seconds?* It was
tested against a standard written down **before** the answer was known, then checked again on
**1,326 other people's browsing**, where it beat the obvious guess for 88.6% of them
individually.

**And it is switched off.** Tise would only use it on you once it had seen enough of your
browsing to trust it — a threshold fixed in advance, before any of this author's attention
was measured, and one that excluded 822 of those 1,326 people as too light to model.

His own browsing does not reach it either. Tise keeps 30 days at a time, so the count settles
around 650 against a bar of 1,000 and stays there; waiting does not fix it. The bar could
have been quietly lowered — the measurement is in this repository and nobody would have
known. It was not.

**So Tise shows you what it measured instead of what a model guesses.** That is the honest
version of this product, and it is the one you get.

## How and when it works

| When | What happens |
|---|---|
| **You install it** | A page explains what will and will not be recorded. **Nothing is stored until you agree** — the database is genuinely empty, not merely unused. |
| **You agree** | It offers to read your existing Chrome history so it is not starting from nothing. Optional, and you can decline. |
| **Every day, invisibly** | It notes the topic and time of pages you visit, and how long you actually looked. No pop-ups, no interruptions. |
| **Every few hours** | It re-learns from what it now knows, in small pieces so your browser never slows down. |
| **When you open it** | The counts, the patterns, and what Tise does and does not claim — including which predictions are switched off and why. |
| **After 30 days** | Raw records are deleted automatically. Change that, keep everything forever, or delete the lot — all in the settings. |

You can export everything at any time as a readable file. It is your data, in a form you can
actually open and read.

## Why this is unusual

Most tools that claim to predict things show you a confident number and never tell you
whether it was right.

Tise **writes down what it expects before it measures**, keeps the score, and publishes the
failures beside the successes. Four prediction ideas have been tested on real browsing and
**two were thrown away** — because a simple counting rule beat the clever model. Both are
written up in public, in detail, rather than quietly dropped.

That honesty is the point of the project.

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

**Adopted is not shipped, and this one will not be.** It needs how long you actually looked
at a page, which the `chrome.history` API cannot supply — so the extension collects that
itself, from the day the permission was granted. The rule for how much it needed was fixed
before any of it arrived: 1,000 visits Tise actually watched, across 20 sittings, producing
200 labelled visits.

Measured on 2026-09-21: **497 of 1,000**, with the other two criteria passed. And the visit
count does not climb forever — raw events expire after 30 days, so it is a window rather than
a running total, and at this rate the window holds about **656**. The gap does not close by
waiting; it needs roughly 33 attention-carrying visits a day against the 22 observed.

**That is the whole argument for withholding it** (`DECISIONS.md`, D123 and D124). The model
is good and this person's browsing is below the volume it was validated for, which is exactly
what the threshold was written to detect. Reproduce it with
`uv run python analysis/engagement_gate.py`.

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
