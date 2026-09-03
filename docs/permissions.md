# Permissions

Every permission Tise requests, why it is needed, and the evidence that it is needed.

> **Status: spike complete, 2026-08-26.** Five variants loaded, backfill probe run.
> One claim was disproved and the design changed as a result. One question could not be
> answered on a clean profile and is recorded as unresolved rather than assumed.

## Evidence classes

This file deliberately distinguishes two kinds of knowing, because conflating them is how
a listing ends up inaccurate:

- **documented** — stated in Chrome's official API reference, with a link. Reliable for
  design, insufficient for a claim about *this* extension.
- **observed** — seen happening in a browser, with the extension loaded. Required before
  anything is written into a store listing or a privacy policy.

## The decision this file records

Two routes reach the same data at wildly different cost to the user:

| Route | Permission | Install-time warning |
|---|---|---|
| `chrome.history.onVisited` | `history` | *"Read and change your browsing history on all signed-in devices"* |
| `chrome.webNavigation` + hosts | `webNavigation` + `<all_urls>` | *"Read and change all your data on all websites"* |

If the first route works, Tise requests **no host permissions at all** — and can state
something it is able to prove rather than promise: *it cannot read the content of any
page you visit, because Chrome never grants it the ability.*

That is the difference between a privacy claim and a privacy guarantee, and it is worth
more to this project than any feature.

## Proposed manifest

```jsonc
{
  "manifest_version": 3,
  "permissions": ["history", "alarms", "offscreen"],
  // No host_permissions. No optional_host_permissions. Deliberately absent.
}
```

## Claims and their evidence

Observed 2026-08-26 on Chrome, five variants, throwaway profile.

| # | Claim | Verdict |
|---|---|---|
| 1 | `VisitItem` is `id, isLocal, referringVisitId, transition, visitId, visitTime` | **observed** — exactly as documented |
| 2 | **No dwell-time field exists** anywhere in the history API | **observed** — the duration trap, now proven rather than believed |
| 3 | `history.onVisited` yields a URL with **no host permissions** | **observed** — 36 events, variants A and D |
| 4 | `HistoryItem` is `id, lastVisitTime, title, typedCount, url, visitCount` — **no transition** | **observed** — see finding 2 below |
| 5 | ~~`webNavigation` cannot collect a URL without host permissions~~ | **FALSE** — see correction below |
| 6 | `webNavigation.onCommitted` yields a URL with **no host permissions** | **observed** — 26 events, variant B |
| 7 | `<all_urls>` adds nothing to `webNavigation` | **observed** — B and C identical, 26 events each |
| 8 | IndexedDB works with no `storage` permission | **observed** — all five variants |
| 9 | `alarms` and `offscreen` appear only when requested, silently | **observed** — variants D and E |
| 10 | `history` works as an **optional** permission, granted at runtime | **observed** — variant E |
| 11 | `permissions.onAdded` fires and listeners re-attach **without reloading** | **observed** — variant E |
| 12 | Removing a permission breaks collection | **observed** — A has no webNavigation and saw 0 nav events; B has no history and saw 0 history events |
| 13 | Backfill fan-out is cheap: **0.7 ms** per `getVisits` call | **observed** — variant E |
| 14 | `visitCount` from `search` matches what `getVisits` returns | **observed** — 22 = 22 |
| 15 | `search` defaults truncate to 24h / 100 rows | **documented, NOT observed** — see below |

## Correction: audit finding 7 was half right

The original documents' manifest could not have collected anything. That stands — it
declared neither `webNavigation` nor `history`, and had no service worker.

But the **reason** recorded for it was wrong. This document previously asserted, from a
web search, that `webNavigation` needs host permissions to see URLs. **It does not.**
Variant B requested `webNavigation` and nothing else, and received 26 navigation events
with full URLs. Variant C added `<all_urls>` and received exactly the same 26 events.

The host permission buys nothing here, and would have cost the broadest warning Chrome
shows. This is precisely why T5 exists as an empirical task rather than a reading task.

## Finding 1: `webNavigation` is the better collector, and its warning is milder

| | `history` | `webNavigation` |
|---|---|---|
| Install warning | *"Read and change your browsing history on all signed-in devices"* | *"Read your browsing history"* |
| Host permissions | none | none |
| Gives transition inline | **no** | **yes** — `transitionType` + `transitionQualifiers` |
| Frame id (subframe filter) | no | **yes** |
| Can read existing history | **yes** | no |

`webNavigation.onCommitted` delivers `documentId, documentLifecycle, frameId, frameType,
parentFrameId, processId, tabId, timeStamp, transitionQualifiers, transitionType, url`.

That is everything the research pipeline needs — the redirect and subframe filters built
at T1 map straight onto `transitionQualifiers` and `frameId` — with **no extra API call
per visit**.

## Finding 2: the two routes are not interchangeable

`history.onVisited` passes a `HistoryItem`, which has **no transition field**. Filtering
redirects and subframes live would need a `getVisits()` call per visit purely to recover
what `webNavigation` hands over for free.

But `webNavigation` only sees the future. Only `history.search()` can read what the user
already browsed, which D10's first-run import depends on.

**So they do different jobs**, and the proposed manifest below reflects that.

## Revised proposal

```jsonc
{
  "manifest_version": 3,
  "permissions": ["webNavigation", "alarms", "offscreen"],
  "optional_permissions": ["history"],
  // No host_permissions. Deliberately absent, and proven unnecessary.
}
```

- **`webNavigation`** — required. Live collection, milder warning, richer data.
- **`history`** — optional, requested at runtime from a button click, for the one-time
  backfill only. Declining it costs the user their history import and nothing else.
- **No host permissions.** Observed to be unnecessary for both routes.

Variant E proved the consent flow end to end: the extension installed holding only
`alarms` and `offscreen`, `chrome.history` was genuinely absent, and after one click the
permission was granted, `permissions.onAdded` fired, and the listeners re-attached with
no reload.

That is the strongest version of the argument: at install, Tise **cannot read anything**.
Not by policy — by capability.

## Justifications for the store listing

Draft. Each becomes final only when its supporting claim above reads **observed**.

**`history`**
> Tise reads your browsing history to learn which topics you return to, so it can predict
> what you are likely to do next. All analysis happens on your device. Your history is
> never transmitted anywhere, and only the domain of each page is stored — never the full
> address, page content, or anything you type.

**`alarms`**
> Tise schedules periodic background work: deleting raw browsing events once they pass
> your retention setting, and retraining its model. Alarms are used instead of a
> continuously running process so the extension consumes nothing while idle.

**`offscreen` — withdrawn at T11, no longer requested (D63)**

~~*Model training runs in an offscreen document because Chrome terminates extension
service workers during long computations.*~~

The justification above was written at T5 and was sound when written. T11 built training
as a chunked, alarm-driven job instead: each wake-up advances a fixed number of gradient
steps and writes a complete resumable state, so **no single call is long enough for the
worker's lifetime to matter**. That removed the premise, and the permission with it.

Kept here struck through rather than deleted, because the point of this file is the record
of what was justified and why — including the parts that stopped being true.

**Host permissions — none requested**
> Tise does not request access to any website. It cannot read the content of the pages
> you visit, fill in forms, or observe anything you type. This is not a policy choice: the
> extension is never granted the capability in the first place.

## Rejected

**`webNavigation` + `<all_urls>`.** It would provide navigation events with transition
types directly, which is marginally more convenient than `history.onVisited`. It costs
*"Read and change all your data on all websites"* — the broadest warning Chrome shows —
in exchange for data Tise can get another way. For a project whose entire argument is
that it takes the minimum, requesting the maximum to save an API call would be
self-defeating.

**`tabs`.** Not needed. It would grant access to tab URLs and titles across the browser
for no capability Tise lacks.

**`storage`.** Not needed. Tise uses IndexedDB, which requires no permission (claim 7).

## Open

- Does `history.onVisited` fire for redirects and subframes? If so, the filtering already
  built for the research tier (`is_redirect`, `SUBFRAME_TRANSITIONS`) has to run live in
  the extension too, and needs `getVisits` to obtain the transition — an extra call per
  visit. Measured in the spike.
- Confirm the exact install-prompt wording by screenshot. The strings above are from
  documentation; the store listing must match what the user is actually shown.

## Backfill, continuous watching, and stopping

Three separate mechanisms, often confused for one:

**1. Backfill — one pass, everything Chrome still has.**
`chrome.history.search({ text: "", startTime: 0, maxResults: <large> })`. Passing the
parameters explicitly overrides both silent defaults (`startTime` = last 24 hours,
`maxResults` = 100).

`startTime: 0` means the Unix epoch, so this returns everything **Chrome still retains** —
which is not the same as everything that ever happened. Chrome expires history on its own
schedule; measured spans on this machine were 90, 56 and 38 days across three browsers.
The listing must say "your existing history" and never "all your history".

`search` returns **pages** (one row per URL, with `visitCount`), not visits. The label
pipeline is visit-based, so a real import also calls `getVisits()` per URL. That fan-out
decides whether the import runs in one pass or has to be chunked across alarm wake-ups —
measured by the spike, not assumed.

**2. Continuous watching — indefinite, no polling.**
`chrome.history.onVisited` fires for every new visit for as long as the permission is
granted and the extension enabled. Registered at the top level of the service worker, so
Chrome wakes the worker when a visit occurs; nothing runs while idle.

**3. Stopping — four independent ways, all the user's.**

| The user wants | Mechanism | Effect |
|---|---|---|
| A break | Pause toggle in the extension | Writes stop; stored data kept |
| To take the capability back | `chrome.permissions.remove(["history"])`, or `chrome://extensions` | The API disappears entirely; Tise cannot observe anything |
| Their data gone | Delete-all | Every store emptied |
| All of it gone | Uninstall | Chrome discards the extension's IndexedDB |

Revocation is the important one. It is not Tise choosing to stop — the capability is
withdrawn at the browser level, and no code in the extension can undo that. Every code
path must therefore handle `chrome.permissions.contains()` returning false and keep
working while doing nothing (T8, T15).

## One thing the permission warning says that Tise does not do

The `history` permission's warning reads *"Read and change your browsing history on all
signed-in devices."* Two clarifications the listing owes the reader:

- **"on all signed-in devices"** describes Chrome Sync, not Tise. If the user has sync
  enabled, their history is already on Google's servers — that happened before Tise was
  installed and is unaffected by it. Tise's own data lives in IndexedDB, which does not
  sync and never leaves the machine.
- **"and change"** is part of Chrome's fixed warning string for this permission. Tise
  never deletes or modifies browser history. It only reads.

Neither can be reworded — Chrome controls the string — so both are addressed directly in
the listing and in onboarding rather than left to be misread.


## Backfill: measured, with one gap

Run in variant E after granting `history` at runtime.

```
pages (search)          20
visits in 20 sampled    22
visitCount sum          22
getVisits per page      0.7 ms
projected full pass     ~0.014 s
```

**The fan-out is a non-issue.** `getVisits` costs **0.7 ms** per page, and that figure does
not depend on how much history exists. Extrapolated to a real corpus of ~5,000 pages, a
complete visit-level backfill takes **around 3.5 seconds**. T7 can import in a single pass;
no chunking across alarm wake-ups is needed.

`visitCount` from `search` exactly matched the visits `getVisits` returned (22 = 22), so
the two views of history agree and neither needs reconciling against the other.

### The gap: default truncation could not be tested

All four query variations returned **20 rows** — identical:

```
defaults                    20 rows   oldest 2026-08-26
startTime=0                 20 rows   oldest 2026-08-26
startTime=0,maxResults=0    20 rows   oldest 2026-08-26
startTime=0,maxResults=1e6  20 rows   oldest 2026-08-26
```

The popup reported **NO** for "reading the whole history needs explicit parameters". That
verdict is wrong, and the cause is the test rather than Chrome: the spike ran on a
**throwaway profile containing 20 pages, all from that same day**. There was nothing for
the 24-hour window or the 100-row cap to truncate, so every variation returned everything.

**This is a flaw in the experiment, not a finding**, and it is recorded as one. Chrome's
documentation states `startTime` defaults to 24 hours and `maxResults` to 100; that
remains *documented, not observed*.

It does not block T7, because **the mitigation is unconditional**: always pass `startTime`
and `maxResults` explicitly and never rely on a default. Confirming the truncation would
require running the spike against a profile with real history, which buys nothing the
mitigation does not already provide.

## The runtime consent dialog, verbatim

Screenshotted rather than paraphrased:

> **"Tise" has requested additional permissions.**
> It could:
> Read and change your browsing history on all your signed-in devices
> `[Allow]`  `[Deny]`

Two things onboarding has to account for:

- **Deny is the focused button.** Chrome defaults this dialog to refusal. The screen that
  precedes it has to do the persuading, because the dialog itself is designed to be
  declined.
- The wording is *"on all your signed-in devices"*, marginally different from the
  install-time string in Chrome's documentation. The listing must use what the user is
  actually shown.

## Reproducing this

The spike is kept rather than deleted, under `spike/permissions/`, clearly marked
throwaway and with its build output gitignored. The plan allowed either. It is kept
because it produced a design correction, and a reader who doubts these findings should be
able to re-run them in fifteen minutes rather than take them on trust.

## Evidence

Screenshots were taken during the run, and **they are not published** (D118). They are held
outside this repository. Every "observed" verdict above traces to one of them, and the list
below says which, so the record stays checkable by anyone with access to the originals even
though the images are not here.

| Held as | Shows |
|---|---|
| `ss_chrome1.png` | All five variants loaded, Developer mode |
| `ss_chrome2.png` | **Variant A** — `history` alone yields URLs, 36 events, no hosts |
| `ss_chrome3.png` | **Variant B** — `webNavigation` alone yields URLs, 26 events. Disproves the host-permission claim |
| `ss_chrome4.png` | **Variant C** — `webNavigation` + `<all_urls>`, identical 26 events |
| `ss_chrome5.png` | **Variant D** — proposed set; `alarms` and `offscreen` present and silent |
| `ss_chrome6.png` | **Variant E before grant** — `chrome.history` absent, 0 events |
| `ss_chrome7.png` | **Variant E after grant** — `onAdded` fired, listeners re-attached, no reload |
| `ss_againcheck2.png` | The runtime consent dialog verbatim, with **Deny** focused |
| `ss_checkgain3.png` | The four `history.search` variations, all 20 rows |
| `ss_checkagain3.2.png` | Backfill fan-out: 0.7 ms per page, ~0.014 s projected |

**Why they are not here.** These eleven were classified as safe to publish, because the
spike ran in a throwaway profile. The *profile* was throwaway; the *browsing* was not.
`ss_checkgain3.png` and `ss_checkagain3.2.png` are the panel photographed over a live
Booking.com hotel search, and the first carries a full URL with tracking parameters in the
address bar — in the repository whose headline claim is that no full URL is ever stored.

Nothing was leaked: there is no remote yet. The finding is about the rule, not the damage.
A publish-list that depends on someone correctly classifying each image is a rule that
fails on the image nobody looked at twice, and it had already passed review once.

**The verdicts above do not depend on the images.** Each is reproducible in about fifteen
minutes from `spike/permissions/`, which is committed, and that is the stronger evidence
anyway — a screenshot shows what happened once on one machine, and the spike shows it
happening on yours.
