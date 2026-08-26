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

## Run

Do this **once per variant**, and please use a throwaway Chrome profile rather than your
main one — this is unreviewed spike code and it should not sit alongside your real
browsing.

1. `chrome://extensions` → enable **Developer mode**
2. **Load unpacked** → pick one variant folder from `spike/permissions/build/`
3. **Screenshot the install prompt.** The exact wording is what goes into the store
   listing later, and paraphrasing it is how listings become inaccurate.
4. Browse five or six ordinary sites in a new tab
5. Click the extension's toolbar icon

The popup states each verdict directly — YES, NO, or `—` for "no events seen".

6. Tell me what it says for each variant

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
