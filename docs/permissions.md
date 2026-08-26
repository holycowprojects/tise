# Permissions

Every permission Tise requests, why it is needed, and the evidence that it is needed.

> **Status: awaiting empirical verification.**
> The rows below marked *observed: pending* have not been run yet. The spike that settles
> them is `spike/permissions/README.md`. Nothing here becomes a store-listing claim until
> its evidence column says **observed**.

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

| # | Claim | Evidence |
|---|---|---|
| 1 | `chrome.history.getVisits` returns `VisitItem` with fields `id`, `isLocal`, `referringVisitId`, `transition`, `visitId`, `visitTime` | **documented** — [history API reference](https://developer.chrome.com/docs/extensions/reference/api/history) |
| 2 | **No dwell-time or duration field exists** on `VisitItem` or `HistoryItem` | **documented** — same reference. This is the duration trap, confirmed at source |
| 3 | `chrome.history.onVisited` passes a `HistoryItem` including `url` | **documented** — same reference |
| 4 | The `history` permission alone is sufficient; no host permissions required | **documented** · *observed: pending* (variant A) |
| 5 | `chrome.webNavigation` **cannot** collect a usable URL without host permissions | *observed: pending* (variant B) — this is audit finding 7 |
| 6 | `alarms` and `offscreen` produce no install-time warning | **documented** — [permissions list](https://developer.chrome.com/docs/extensions/reference/permissions-list) · *observed: pending* |
| 7 | IndexedDB works with no `storage` permission | *observed: pending* (any variant) |
| 8 | Removing any requested permission demonstrably breaks collection | *observed: pending* (A vs B) |

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

**`offscreen`**
> Model training runs in an offscreen document because Chrome terminates extension
> service workers during long computations. This keeps training on your own machine
> rather than moving it to a server.

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
