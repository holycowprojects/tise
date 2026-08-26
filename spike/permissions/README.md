# T5 — permission spike

**Throwaway code.** The deliverable is `docs/permissions.md`, written from what this
experiment observes. This directory is deleted once that file exists.

Only you can run this: it needs a browser with an extension loaded into it, and the
result has to be *observed* rather than reasoned about. The original design documents
shipped a manifest that could not have collected anything — the whole reason this task
exists is that nobody had checked.

## Why it matters

Two routes reach the same data, and they cost wildly different things at the store:

| Route | Permission | What the user is shown at install |
|---|---|---|
| `chrome.history.onVisited` | `history` | *"Read and change your browsing history on all signed-in devices"* |
| `chrome.webNavigation` + hosts | `webNavigation` + `<all_urls>` | *"Read and change all your data on all websites"* |

Chrome's documentation says `history` alone yields the URL and needs **no host
permissions**. If that holds in practice, Tise can make a claim it can actually prove:
it cannot read the content of any page, because Chrome never grants it the ability.
That is a far stronger statement than a promise not to.

**This experiment decides whether that claim is true.** Everything downstream — the
manifest, the store listing, the privacy policy — depends on the answer.

## Build

```
uv run python spike/permissions/build.py
```

Produces four unpacked extensions under `spike/permissions/build/`, identical except for
their manifest permissions:

| Variant | Permissions | Question |
|---|---|---|
| `A-history-only` | `history` | Does `history` alone yield URLs? |
| `B-webnavigation-only` | `webNavigation` | Can `webNavigation` collect anything unaided? |
| `C-webnavigation-all-urls` | `webNavigation` + `<all_urls>` | The expensive route, for comparison |
| `D-proposed-shipping-set` | `history`, `alarms`, `offscreen` | The set Tise intends to ship |
| `E-optional-consent-flow` | `alarms`, `offscreen` + **optional** `history` | Install with no capability; user grants by clicking |

### Why E may be the best design

Chrome allows `history` to be an **optional** permission — it is not among the nine that
cannot be. So Tise can install requesting *nothing that carries a warning*, explain
itself, and only then ask, from a button click.

That inverts the usual bargain. The extension has **no ability to read anything** until
the user deliberately grants it, and they can revoke it at any time from
`chrome://extensions` — at which point Tise must keep working and do nothing. It also
means the privacy claim stops being a promise: at install there is no capability to
misuse.

The cost is that a user who declines gets an extension that does nothing, so the empty
state has to be honest and obvious rather than nagging.

## Run — exact steps

Use a **throwaway Chrome profile**, not your main one. This is unreviewed spike code and
should not sit alongside your real browsing.

### Once, at the start

1. Open Chrome. Click your profile avatar (top right) → **Add** → **Continue without an
   account** → name it `tise-spike` → **Done**. A new Chrome window opens. **Do all the
   steps below in that window.**
2. In it, go to `chrome://extensions`
3. Turn on **Developer mode** (toggle, top right)

### For each variant, in order: A, B, C, D, E

4. Click **Load unpacked**
5. Navigate to
   `C:\Users\akash\Documents\Work-Projects\Tise\spike\permissions\build\` and select the
   variant folder — start with `A-history-only`. Click **Select Folder**.
6. **Screenshot whatever Chrome shows you**, including the card that appears on the
   extensions page. Note whether it warned you about anything at all. The exact wording
   becomes store-listing copy later, and paraphrasing it is how listings go wrong.
7. Open a new tab and visit five or six ordinary sites — a news site, a search, a
   shopping page. Click through a couple of links on each.
8. Click the **puzzle-piece icon** in the toolbar → click **Tise spike …** to open the
   popup.
9. Write down every YES / NO / — line it shows.
10. Click **Remove** on that variant's card in `chrome://extensions` before loading the
    next one. Running two at once makes the results ambiguous.

### Variant E has two extra steps

E installs with **no history access at all** — this is the consent flow.

11. After loading E, open the popup. Click **Grant history access**. Screenshot the
    Chrome dialog that appears, then accept it.
12. Reopen the popup and click **Read my whole history**. It prints a four-row table
    comparing ways of calling `chrome.history.search`. Copy that table out — it decides
    how T7's import is written.

### When you are done

13. Tell me what each variant reported. Then delete the `tise-spike` profile (profile
    avatar → gear icon → three dots next to it → **Delete**).

## What each variant should settle

- **A** — if `history.onVisited` yields URLs here, no host permission is ever needed.
- **B** — expected to yield **no usable URL**. That is audit finding 7, tested.
- **C** — expected to work, at the cost of the worst warning in the store. Run it only
  to confirm the trade-off is real.
- **D** — the proposed shipping set. Must behave exactly like A, plus `alarms` and
  `offscreen` present and silent at install.

The popup also reports whether **IndexedDB works with no `storage` permission**, which
T6 depends on and which is otherwise easy to assume.

## Removing a permission must break it

The acceptance criterion is that no permission is present without being load-bearing.
Variants A and B are that test: A has no `webNavigation`, B has no `history`. If both
collect URLs, one of them is not needed and must not be requested.

## Recording the result

Nothing goes into `docs/permissions.md` that was not observed here. If a variant behaves
unexpectedly, that is the finding — write down what happened rather than what should
have.

**No URL is ever stored by this spike.** It records hosts and field names only, the same
reduction the product performs, because a debugging tool is not an exemption from the
rule it exists to support.
