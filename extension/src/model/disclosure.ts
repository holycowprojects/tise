/**
 * What Tise can reach, what it stores, and what it never does — as **data derived from the
 * manifest**, not as prose typed onto a page.
 *
 * ## Why this is a module and not a paragraph in the HTML
 *
 * This project has shipped the same defect twice, in the two places a reader trusts most.
 * T18b found the README describing a `service/ Local Python service` that does not exist
 * and was explicitly rejected — a reader auditing the privacy claim saw a local server in
 * the layout. D98 found `reports.py` labelling twelve benchmarks with a target retired two
 * decisions earlier. Both were hand-written statements about the system that the system had
 * moved out from under.
 *
 * **An onboarding page is the worst possible place for that failure**, because it is the one
 * artifact whose entire job is to be believed before the person can check anything. So the
 * permission list is not typed: `describeCapabilities` reads the manifest, and
 * `disclosure.test.ts` fails if a permission exists with no explanation **or** an explanation
 * exists for a permission that is no longer requested. Adding a permission without telling
 * the user about it breaks the build, which is the only guarantee worth having.
 *
 * The same rule covers what is stored: `STORED_FIELDS` is checked against `EVENT_FIELDS`, so
 * a new field on `TiseEvent` cannot appear in the database without appearing on this page.
 *
 * ## What is *not* derivable, and how it is guarded instead
 *
 * "Tise never transmits anything" is not a property of the manifest — no permission is
 * needed to call `fetch`. It cannot be derived, so it is stated here and pinned by
 * `no-network.test.ts` scanning the shipped source. The honest position is that the two
 * halves are guarded differently, and this file says which is which rather than presenting
 * them as one kind of promise.
 */
import { EVENT_FIELDS } from "../types";

/** One capability Tise asks for, in the words a person would use. */
export interface Capability {
  readonly permission: string;
  /** What Chrome calls it is not what it does. This is the second one. */
  readonly title: string;
  readonly allows: string;
  /** The boundary. Every permission grants more than Tise uses; this says what is unused. */
  readonly doesNotAllow: string;
  /**
   * What declining costs, for optional permissions. Empty for required ones, which are
   * granted at install and cannot be declined separately.
   *
   * Present because D33 measured that Chrome focuses **Deny** on the permission dialog: the
   * page has to have done the persuading before the dialog appears, and a person deciding
   * needs to know the price of "no" rather than only the price of "yes".
   */
  readonly costOfDeclining: string;
}

/**
 * Every permission this extension may ever hold, keyed by its manifest name.
 *
 * A permission missing from here fails `disclosure.test.ts`. An entry here for a permission
 * the manifest does not request fails it too — a stale explanation is worse than none,
 * because it describes access the extension does not have and cannot be checked against.
 */
export const CAPABILITIES: Readonly<Record<string, Capability>> = Object.freeze({
  webNavigation: {
    permission: "webNavigation",
    title: "Know when you move to a new page",
    allows:
      "Tise is told the address of each page you navigate to, so it can reduce that " +
      "address to a bare site name and count it.",
    doesNotAllow:
      "It cannot read the page, its text, its forms, or anything you type. The full " +
      "address is discarded before anything is written down.",
    costOfDeclining: "",
  },
  alarms: {
    permission: "alarms",
    title: "Wake up on a schedule",
    allows:
      "Tise wakes itself every few hours to train, to delete old data, and to score its " +
      "own past predictions.",
    doesNotAllow: "It reaches nothing and reads nothing. It is a timer.",
    costOfDeclining: "",
  },
  history: {
    permission: "history",
    title: "Read your existing browser history, once",
    allows:
      "A single pass over the sites you have already visited, so Tise has something to " +
      "learn from on day one instead of in two months.",
    doesNotAllow:
      "It is one pass that you start by pressing a button. Tise does not watch your " +
      "history afterwards, and it stores site names only — never the pages themselves.",
    costOfDeclining:
      "Tise starts from nothing and takes a few weeks to have anything to say. Everything " +
      "else works exactly the same.",
  },
  tabs: {
    permission: "tabs",
    title: "See which tab is in front",
    allows:
      "Tise can tell a page you actually read from a tab you left open behind six others, " +
      "which is the difference between measuring attention and measuring nothing.",
    doesNotAllow:
      "It does not read tab contents. The tab's identifier is used to attribute a span " +
      "and is never stored — a test fails if it ever reaches the database.",
    costOfDeclining:
      "Tise cannot tell a page you read from a tab you abandoned. Everything else is " +
      "unaffected.",
  },
  idle: {
    permission: "idle",
    title: "Know when you have stepped away",
    allows:
      "Tise stops counting a page as read while you are away from the machine, so a tab " +
      "left open overnight does not record a night of deep attention.",
    doesNotAllow:
      "It reports only that the machine is idle, locked or active. It says nothing about " +
      "what you are doing instead.",
    costOfDeclining:
      "Attention measurements include time you were not at the machine, which makes them " +
      "less useful and nothing worse.",
  },
});

/**
 * Capabilities Tise deliberately does not request, and why anyone should care.
 *
 * **This list is shared with `manifest.test.ts`, which asserts none of them appears in
 * either permission list.** A claim on a privacy page that nothing enforces is decoration;
 * this one fails the build if it stops being true.
 */
export const NEVER_REQUESTED: ReadonlyArray<readonly [string, string]> = Object.freeze([
  ["cookies", "your logged-in sessions, which are credentials"],
  ["webRequest", "every network request your browser makes"],
  ["scripting", "the ability to run code inside the pages you visit"],
  ["declarativeNetRequest", "the ability to change or block what your browser loads"],
  ["browsingData", "the ability to delete your browser's data"],
  ["management", "the other extensions you have installed"],
  ["downloads", "the files you download"],
  ["bookmarks", "your bookmarks"],
  ["topSites", "your most-visited sites"],
  ["storage", "extension storage that other tools can read"],
] as const);

/** No host permissions at any width, which is the broadest warning Chrome can show. */
export const NO_HOST_ACCESS =
  "Tise asks for no site access at all — not “on all sites”, not on one. That is " +
  "the widest permission warning Chrome shows, and Tise's absence of it is checkable in " +
  "the manifest.";

/**
 * Every field Tise writes for one visit, in the words a person would use.
 *
 * Keyed by the actual field name so `disclosure.test.ts` can check this against
 * `EVENT_FIELDS` in both directions. A field added to `TiseEvent` without a line here fails
 * the build, which is what stops the database and this page drifting apart.
 */
export const STORED_FIELDS: Readonly<Record<string, string>> = Object.freeze({
  eventId: "an identifier for the visit, meaningless outside this database",
  occurredAt: "when it happened",
  source: "whether Tise saw it live or read it from your existing history",
  domain: "the bare site name — `example.com`, never the page on it",
  category: "which of fifteen topics that site belongs to",
  transition: "how you arrived: typed, followed a link, or used a bookmark",
  dwellSeconds: "how long the visit lasted, when that can be measured at all",
  sessionId: "which sitting the visit belongs to",
});

/** Stated, and enforced by `assertStorable` throwing on anything not in `EVENT_FIELDS`. */
export const NEVER_STORED: ReadonlyArray<string> = Object.freeze([
  "the full address of any page, including its path and anything after the `?`",
  "the contents of any page, or its title",
  "anything you type, including form fields and search boxes",
  "cookies, passwords, or any credential",
  "your name, your email address, or any account identifier",
]);

export interface Capabilities {
  readonly required: readonly Capability[];
  readonly optional: readonly Capability[];
}

/** The shape `describeCapabilities` reads. A manifest, or the part of one that matters. */
export interface ManifestLike {
  readonly permissions?: readonly string[];
  readonly optional_permissions?: readonly string[];
}

/**
 * The manifest's permissions, explained — or a loud failure.
 *
 * Throwing rather than skipping an unknown permission is the whole point. A page that
 * quietly omitted a capability it had no words for would be a privacy disclosure with a
 * hole in it, and the hole would be invisible precisely where it mattered most.
 */
export function describeCapabilities(manifest: ManifestLike): Capabilities {
  const look = (names: readonly string[]): Capability[] =>
    names.map((name) => {
      const capability = CAPABILITIES[name];
      if (capability === undefined) {
        throw new Error(
          `the manifest requests "${name}" and no plain-language explanation exists for ` +
            "it. Add one to CAPABILITIES before shipping: an undisclosed permission is " +
            "the one thing this page cannot be allowed to have.",
        );
      }
      return capability;
    });

  return {
    required: look(manifest.permissions ?? []),
    optional: look(manifest.optional_permissions ?? []),
  };
}

/** `STORED_FIELDS` in the canonical field order, so the page cannot reorder the truth. */
export function storedFields(): ReadonlyArray<readonly [string, string]> {
  return EVENT_FIELDS.map((field) => {
    const description = STORED_FIELDS[field];
    if (description === undefined) {
      throw new Error(
        `TiseEvent carries "${field}" and this page does not say so. Every stored field ` +
          "needs a line in STORED_FIELDS.",
      );
    }
    return [field, description] as const;
  });
}
