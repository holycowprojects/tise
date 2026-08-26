/**
 * Turn one `webNavigation.onCommitted` event into a `TiseEvent`, or reject it.
 *
 * The filters mirror the ones T1 applied to the history database, because the research
 * corpus and the live stream have to be the same population. T1 found that counting
 * redirect hops as navigations pushed the median inter-visit gap down to a second and
 * inflated the domain count from 133 to 236 — the shape of every session-derived feature
 * depends on getting this right, in both places, identically.
 *
 * Rejections are returned with a reason rather than swallowed. The reason is a fixed
 * string, never a URL: a diagnostic that logs what it rejected would defeat the point.
 */
import type { TiseEvent } from "../types";
import { registrableDomain } from "./domain";
import { resolve } from "./resolver";

/**
 * The subset of `chrome.webNavigation.WebNavigationFramedCallbackDetails` we use.
 *
 * Declared structurally so the normaliser is testable without a browser, and so the
 * exact fields Tise reads are visible in one place to anyone auditing the extension.
 */
export interface NavigationDetails {
  readonly url: string;
  readonly frameId: number;
  readonly timeStamp: number;
  readonly transitionType: string;
  readonly transitionQualifiers?: readonly string[];
}

export type RejectionReason = "subframe" | "redirect" | "not-web";

export type NormaliseResult =
  | { readonly ok: true; readonly event: Omit<TiseEvent, "sessionId"> }
  | { readonly ok: false; readonly reason: RejectionReason };

/** Chrome's qualifiers for a hop the person did not choose to make. */
const REDIRECT_QUALIFIERS: ReadonlySet<string> = new Set([
  "client_redirect",
  "server_redirect",
]);

export interface NormaliseOptions {
  readonly overrides?: Readonly<Record<string, string>>;
  /** Injected so tests do not depend on a global. Production passes `crypto.randomUUID`. */
  readonly newId?: () => string;
}

export function normaliseNavigation(
  details: NavigationDetails,
  options: NormaliseOptions = {},
): NormaliseResult {
  // A page's iframes are not navigations the person chose to make.
  if (details.frameId !== 0) return { ok: false, reason: "subframe" };

  for (const qualifier of details.transitionQualifiers ?? []) {
    if (REDIRECT_QUALIFIERS.has(qualifier)) return { ok: false, reason: "redirect" };
  }

  // The privacy boundary: after this line no URL exists anywhere in the pipeline.
  const domain = registrableDomain(details.url);
  if (domain === null) return { ok: false, reason: "not-web" };

  const newId = options.newId ?? (() => crypto.randomUUID());

  return {
    ok: true,
    event: {
      eventId: newId(),
      occurredAt: new Date(details.timeStamp).toISOString(),
      source: "live",
      domain,
      category: resolve(domain, options.overrides).category,
      transition: details.transitionType,
      dwellSeconds: null, // D35 — never measured, in either direction
    },
  };
}
