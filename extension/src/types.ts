/**
 * The canonical event, mirroring `TiseEvent` in SPEC.md field for field.
 *
 * Note what is **not** here: no URL, no path, no query string, no fragment, no title
 * text. The collector reduces a URL to its registrable domain *before* an event object
 * is constructed, so there is no later stage at which a full URL could be persisted by
 * accident. That is SPEC.md invariant 2 enforced by construction rather than by review.
 *
 * `research/tise_research/features/events.py` is the Python mirror of this type.
 */
export interface TiseEvent {
  eventId: string;
  /** ISO 8601, UTC, from `Date.prototype.toISOString`. Always ends in `Z`. */
  occurredAt: string;
  source: TiseEventSource;
  /** Registrable domain only, e.g. `amazon.in`. Never a host, never a URL. */
  domain: string;
  /** From the resolver. `unknown` is a valid value, not a failure. */
  category: string;
  /** Chrome's `transitionType`: link | typed | reload | auto_bookmark | ... */
  transition: string;
  /**
   * Always `null` in V1 — for live events as well as imported ones (D35).
   * The `chrome.history` API cannot supply dwell time, so measuring it live would make
   * imported and observed events differ in feature space, and a model trained across
   * the boundary would silently degrade. Never invent a value here.
   */
  dwellSeconds: number | null;
  sessionId: string;
}

/** Named `TiseEventSource` rather than `EventSource`: the DOM already has that one. */
export type TiseEventSource = "live" | "import";

/**
 * The complete set of keys a stored event may have.
 *
 * The privacy test asserts that every row in a populated store has exactly these keys,
 * which turns "we would never store a URL" from an intention into an assertion.
 */
export const EVENT_FIELDS = [
  "eventId",
  "occurredAt",
  "source",
  "domain",
  "category",
  "transition",
  "dwellSeconds",
  "sessionId",
] as const satisfies ReadonlyArray<keyof TiseEvent>;

/**
 * One period during which a single navigation held the active tab **and the person was
 * there**. The unit of attention, and the thing `dwellSeconds` could never be.
 *
 * D35 recorded the duration trap as permanent: Chrome's history *file* has
 * `visit_duration`, the `chrome.history` API does not, so `dwellSeconds` is `null` for
 * live events as well as imported ones. `chrome.tabs` and `chrome.idle` lift that — but
 * they measure something *better* than `visit_duration`, not merely the same thing:
 * `visit_duration` counts how long a tab held a URL, so a tab left open overnight records
 * deep engagement that never happened. A span ends when the person looks away.
 *
 * **A span is never invented.** If Tise cannot attribute a period of attention to a
 * specific navigation it records nothing, because a span with a guessed `eventId` is
 * indistinguishable from a measured one afterwards.
 *
 * Spans reference raw events and **expire with them** (30 days). What survives is the
 * feature computed from them, which is D11's rule unchanged.
 */
export interface AttentionSpan {
  /** `eventId` + start instant. Stable, so re-recording a span replaces rather than duplicates. */
  spanId: string;
  /** The navigation this attention belongs to. Never null, never guessed. */
  eventId: string;
  startedAt: string;
  endedAt: string;
  /** Seconds the tab was active, the window focused and the person not idle. */
  activeSeconds: number;
  endReason: AttentionEndReason;
}

/**
 * Why a span closed. Kept because the reasons are not equivalent: `idle` and `blur` mean
 * the person left, `tab-switch` and `navigated` mean they moved on deliberately, and
 * `shutdown` means Tise stopped watching and the span is a lower bound rather than a
 * measurement.
 */
export type AttentionEndReason =
  | "navigated"
  | "tab-switch"
  | "tab-closed"
  | "idle"
  | "blur"
  | "shutdown";

/** The complete set of keys a stored span may have. Asserted on every write. */
export const SPAN_FIELDS = [
  "spanId",
  "eventId",
  "startedAt",
  "endedAt",
  "activeSeconds",
  "endReason",
] as const satisfies ReadonlyArray<keyof AttentionSpan>;

/** Characters that cannot appear in a registrable domain but do appear in a URL. */
const URL_STRUCTURE = /[/?#:@\s]/;

/**
 * Throw if an event carries anything it must not.
 *
 * This runs on every write, not only in tests. A guard that only exists in the test
 * suite protects the test suite; this one protects the user.
 */
export function assertStorable(event: TiseEvent): void {
  const unexpected = Object.keys(event).filter(
    (key) => !(EVENT_FIELDS as readonly string[]).includes(key),
  );
  if (unexpected.length > 0) {
    throw new Error(`refusing to store unexpected fields: ${unexpected.join(", ")}`);
  }
  // **Missing is as dangerous as unexpected, and only one of the two was checked.**
  // `occurredAt` is the `events` index, and IndexedDB simply omits a row from an index it
  // has no key for — so a row written without it is in the store, invisible to
  // `allEvents`, absent from every export, and unreachable by retention, which walks the
  // same index. It would survive "delete everything older than 30 days" forever without
  // ever appearing anywhere. Nothing has written such a row, and now nothing can. Found
  // by the D110 seam audit.
  const missing = EVENT_FIELDS.filter((field) => !(field in event));
  if (missing.length > 0) {
    throw new Error(`refusing to store an event missing: ${missing.join(", ")}`);
  }
  if (!event.domain || URL_STRUCTURE.test(event.domain)) {
    throw new Error(`refusing to store a domain that looks like a URL: ${event.domain}`);
  }
  if (!event.occurredAt.endsWith("Z")) {
    throw new Error(`refusing a non-UTC timestamp: ${event.occurredAt}`);
  }
  if (event.dwellSeconds !== null) {
    throw new Error("dwellSeconds must be null in V1 — see D35");
  }
}

/**
 * Throw if a span carries anything it must not, or claims something it cannot know.
 *
 * Runs on every write, like `assertStorable`. The `activeSeconds` checks matter more than
 * they look: a zero-length span is not a measurement of no attention but the *absence* of
 * a measurement, and an unbounded one is almost always a laptop lid rather than a person.
 * Either would enter the data as if it had been observed.
 */
export function assertStorableSpan(span: AttentionSpan): void {
  const unexpected = Object.keys(span).filter(
    (key) => !(SPAN_FIELDS as readonly string[]).includes(key),
  );
  if (unexpected.length > 0) {
    throw new Error(`refusing to store unexpected fields: ${unexpected.join(", ")}`);
  }
  if (!span.eventId) {
    throw new Error("a span without an eventId is attention attributed to nothing");
  }
  if (!span.startedAt.endsWith("Z") || !span.endedAt.endsWith("Z")) {
    throw new Error("refusing a non-UTC timestamp on a span");
  }
  if (!(span.activeSeconds > 0)) {
    throw new Error(
      `activeSeconds must be positive, got ${span.activeSeconds}: a zero-length span is ` +
        "the absence of a measurement, not a measurement of zero attention",
    );
  }
  if (Date.parse(span.endedAt) < Date.parse(span.startedAt)) {
    throw new Error("refusing a span that ends before it starts");
  }
}
