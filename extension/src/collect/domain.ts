/**
 * Reduce a URL to its registrable domain.
 *
 * **This is the privacy boundary.** The path, query string and fragment are discarded
 * *here*, before any event object exists, so there is no later stage at which they could
 * be persisted by accident. Everything downstream of this function only ever sees a
 * domain, which is why SPEC.md invariant 2 does not depend on anyone remembering it.
 *
 * PARITY-CRITICAL: `registrable_domain` in
 * `research/tise_research/data/chrome_history.py` must agree on every input. Both read
 * the multi-part suffix list from `../categories/suffixes.json`; neither owns it.
 *
 * One known and accepted divergence: an internationalised host reaches this function
 * already punycode-encoded, because that is what Chrome canonicalises to both in
 * `webNavigation` and in the history database. Neither implementation decodes it.
 */
import suffixData from "../categories/suffixes.json";

const MULTI_PART_SUFFIXES: ReadonlySet<string> = new Set(suffixData.multiPartSuffixes);

const WEB_SCHEMES: ReadonlySet<string> = new Set(["http:", "https:"]);

export const SUFFIX_LIST_VERSION: number = suffixData.version;

function isIpLiteral(host: string): boolean {
  if (host.includes(":")) return true; // an IPv6 literal, brackets already stripped
  const parts = host.split(".");
  return parts.length === 4 && parts.every((p) => p.length > 0 && /^\d+$/.test(p));
}

/**
 * The registrable domain, or `null` if this is not web browsing.
 *
 * `null` for non-web schemes (`chrome://`, `file://`, extension pages), for `localhost`
 * and for IP literals. Those are not browsing behaviour, and a `file://` URL is a
 * private path — the one shape of URL that leaks the most by being stored.
 */
export function registrableDomain(url: string): string | null {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return null;
  }

  if (!WEB_SCHEMES.has(parsed.protocol.toLowerCase())) return null;

  // `hostname` is already lowercased and port-stripped; IPv6 keeps its brackets.
  const host = parsed.hostname.replace(/^\[|\]$/g, "");
  if (!host) return null;
  if (host === "localhost" || host.endsWith(".localhost")) return null;
  if (isIpLiteral(host)) return null;

  const labels = host.replace(/^\.+|\.+$/g, "").split(".");
  if (labels.length < 2) return null;

  const lastTwo = labels.slice(-2).join(".");
  if (MULTI_PART_SUFFIXES.has(lastTwo)) {
    // The two-label suffix is public, so the registrable domain needs a third label.
    return labels.length >= 3 ? labels.slice(-3).join(".") : null;
  }

  return lastTwo;
}
