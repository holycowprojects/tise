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
