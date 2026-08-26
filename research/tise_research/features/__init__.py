"""Feature construction — the parity-critical half of the codebase.

Everything in this package exists twice: here in Python for research, and in
`extension/src/features/` in TypeScript for the product. If the two ever disagree, every
published benchmark describes a model that was never shipped. The parity suite (T9) is
what stops that, and it is the most important test in the repository.

Two rules hold throughout:

* **Every function that looks at time takes `window_end` explicitly and filters strictly
  before it.** Not a convention — it is what makes the leakage test possible at all.
* **Behaviour lives in data where it can.** Category rules are JSON, not code, so there is
  one definition rather than two implementations that have to be kept in step by hand.
"""
