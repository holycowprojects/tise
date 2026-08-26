# Tise — privacy policy

> **Not part of the published text.** This file is the source for the Tise section of the
> Holy Cow Studios privacy policy page. Two things must happen before it goes live:
>
> 1. **Re-check every claim against the shipped build.** This describes V1 as specified.
>    Anything not implemented at submission must be cut, not softened — a policy that
>    describes an intention is a policy that is false on the day it is published.
> 2. **Confirm the contact address exists.** `privacy@holycowstudios.in` is a suggestion,
>    not a fact. Do not substitute a personal address without deciding to publish it.
>
> The Chrome Web Store requires this at a public URL before submission (T18). Everything
> below is written to be pasted as-is.

---

**Last updated:** 26 August 2026

Tise is a browser extension that learns from your browsing and predicts what you are
likely to do next. It does this entirely on your own device.

## The short version

**Nothing you browse ever leaves your computer.** Tise makes no network requests of any
kind. There is no server, no account, no sign-in, no analytics, no telemetry, no crash
reporting, no advertising, and no third-party service of any kind. There is no opt-in that
changes this, because there is nothing to opt into.

You can read the source. Tise is open source, and the code that would have to exist for
data to be transmitted does not exist — its absence is enforced by an automated test that
fails the build if anyone adds it.

## What Tise stores

When you visit a page, Tise records:

| What | Example |
|---|---|
| The site's registrable domain | `wikipedia.org` |
| The time you visited | `2026-08-26T09:15:00Z` |
| A category, worked out on your device | `reference` |
| How you got there | `link`, `typed`, `reload` |
| Which browsing session it belonged to | a local identifier |

That is the complete list.

## What Tise never stores

Tise **never** records:

- the full web address — the path, the query string or the fragment are discarded
- the page title or any page content
- anything you type, including form values, searches and messages
- cookies, passwords, payment details or any credential
- your IP address, your location, or any device identifier
- who you are

A web address is reduced to its domain **before** any record is created. There is no later
stage at which the rest of the address could be stored by mistake, because by then it no
longer exists.

So `https://www.example.com/health/results?id=48291` becomes `example.com`, and nothing
else about that visit is kept.

## Where it is stored

In your browser's own storage, on your own device, in your browser profile. It is not
synced between your devices, and it is not backed up anywhere.

If you use Tise in more than one browser, each one keeps its own separate record. They are
never combined.

## Nothing happens until you say so

When you install Tise it stores nothing at all. It cannot begin until you turn it on, and
turning it on is a deliberate action you take in the extension itself.

You can pause it at any time. While paused, nothing new is written. A period you paused
through is never filled in later — that is what pausing means.

## Permissions, and why each one exists

| Permission | Why |
|---|---|
| **Read your browsing history** (`webNavigation`) | To see that a navigation happened, so a domain and a time can be recorded. This is how Tise observes anything at all. |
| **Alarms** | To run the scheduled clean-up that deletes records older than your retention setting. |
| **Offscreen** | To train the prediction model in the background without slowing down your browsing. Training happens on your device. |
| **History** — *optional* | Only if you ask for it, and only once. Reads the browsing history your browser already has, so Tise has something to learn from on day one. You are asked separately, by your browser, and refusing costs you nothing but that first import. |

Tise requests **no access to the content of any website.** It cannot read pages you visit.

## How long it is kept

Individual browsing records are deleted after **30 days** by default. You can change this,
including setting it to keep everything indefinitely.

What Tise has *learned* — the patterns, not the visits — is kept beyond that, which is how
it can still make predictions from a period whose records have already been deleted.

## Getting your data out

One click exports everything Tise holds about you as a readable JSON file: the records,
your settings, and your own category corrections. Nothing is withheld and nothing is
summarised.

## Deleting it

One click deletes everything: every record, every setting, your consent, and Tise's
permission to read your history. Afterwards Tise is in exactly the state it was in when
you installed it — unable to store anything until you ask it to again.

There is no copy anywhere else, so there is nothing else to delete and no request you need
to make of us.

## Children

Tise is not directed at children and does not knowingly collect anything from them. Since
it collects nothing that identifies anyone, and transmits nothing, it holds no information
about any user, of any age.

## Changes to this policy

If this policy changes, the updated version will be published here with a new date. A
change that affected what Tise collects would also require a new version of the extension,
which your browser would tell you about.

## Contact

Questions about this policy, or about Tise: **privacy@holycowstudios.in**

Tise is published by **Holy Cow Studios Private Limited**. The source code is public, and
the claims on this page can be checked against it.
