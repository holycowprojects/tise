/**
 * Settings, stored in the `meta` store rather than `chrome.storage.local`, so that the
 * manifest needs no `storage` permission (see `db.ts`).
 *
 * Consent and pause are separate fields on purpose. Consent is a one-time decision the
 * user makes knowingly (T15); pause is a switch they flip whenever they like. Collapsing
 * them into one boolean would make "I paused it for an hour" indistinguishable from
 * "I never agreed to this", and only one of those should survive a reinstall.
 */
import { readMeta, writeMeta } from "./db";
import { recordCollectionStarted, recordCollectionStopped } from "./coverage";

const SETTINGS_KEY = "settings";

/** D17: a declared hyperparameter. T1 looked for an empirical trough and found none. */
export const DEFAULT_SESSION_TIMEOUT_SECONDS = 1800;

/** D11: raw events expire, derived features do not. `0` means keep raw events forever. */
export const DEFAULT_RAW_RETENTION_DAYS = 30;

export interface Settings {
  /** ISO 8601, or `null` when the user has never agreed. Nothing is stored while null. */
  consentGrantedAt: string | null;
  paused: boolean;
  sessionTimeoutSeconds: number;
  rawRetentionDays: number;
  /** Registrable domain -> category. The user is always right about their own browsing. */
  overrides: Record<string, string>;
}

export const DEFAULT_SETTINGS: Readonly<Settings> = Object.freeze({
  consentGrantedAt: null,
  paused: false,
  sessionTimeoutSeconds: DEFAULT_SESSION_TIMEOUT_SECONDS,
  rawRetentionDays: DEFAULT_RAW_RETENTION_DAYS,
  overrides: {},
});

/**
 * Bounds for the two numbers T15 lets a person edit. **Declared, and stated on the page.**
 *
 * The upper bound on retention exists so "keep forever" has exactly one representation.
 * `0` means forever (D11); 4,000 days would be a second way to say almost the same thing
 * and the two would drift apart in every place that special-cases zero.
 *
 * The session timeout's floor is not cosmetic. Every session-derived feature in the project
 * rests on this number — D17 declared 30 minutes a hyperparameter because T1 looked for an
 * empirical trough and found none — and D97 made it load-bearing a second way by clustering
 * intervals on sessions. A one-second timeout would make every visit its own session and
 * quietly invalidate the lot, so the field is editable and cannot be set to nonsense.
 */
export const RETENTION_MAX_DAYS = 3650;
export const TIMEOUT_MIN_SECONDS = 60;
export const TIMEOUT_MAX_SECONDS = 86_400;

/**
 * Why a patch is not acceptable, or `null`.
 *
 * Returns a message rather than throwing: this runs behind a text field, where the answer
 * to bad input is to say so next to the field, not to break the page.
 */
export function settingsError(patch: Partial<Settings>): string | null {
  const retention = patch.rawRetentionDays;
  if (retention !== undefined) {
    if (!Number.isInteger(retention) || retention < 0) {
      return "Retention must be a whole number of days, or 0 to keep everything.";
    }
    if (retention > RETENTION_MAX_DAYS) {
      return `Retention above ${RETENTION_MAX_DAYS} days is not a limit — use 0 for “keep everything”.`;
    }
  }

  const timeout = patch.sessionTimeoutSeconds;
  if (timeout !== undefined) {
    if (!Number.isInteger(timeout)) return "The session gap must be a whole number of seconds.";
    if (timeout < TIMEOUT_MIN_SECONDS || timeout > TIMEOUT_MAX_SECONDS) {
      return (
        `The session gap must be between ${TIMEOUT_MIN_SECONDS / 60} and ` +
        `${TIMEOUT_MAX_SECONDS / 3600} hours. Everything Tise measures is grouped by it.`
      );
    }
  }

  const overrides = patch.overrides;
  if (overrides !== undefined) {
    for (const [domain, category] of Object.entries(overrides)) {
      // A path or a scheme here would put a URL fragment into settings, and settings are
      // carried by the export (D45). Invariant 2 has no exception for a field a person
      // typed themselves.
      if (domain.includes("/") || domain.includes(":") || domain.includes("?")) {
        return `“${domain}” is not a bare site name. Use example.com, with no https:// and no path.`;
      }
      if (domain.trim() === "" || category.trim() === "") {
        return "A site override needs both a site and a topic.";
      }
    }
  }
  return null;
}

export async function loadSettings(): Promise<Settings> {
  const stored = await readMeta<Partial<Settings>>(SETTINGS_KEY);
  // **Spreading the stored object directly is not enough.** An own property whose value is
  // `undefined` overwrites the default rather than falling back to it, and IndexedDB
  // preserves `undefined` values through structured clone — so a build that ever wrote
  // `overrides: undefined` would leave it undefined here and every `overrides[domain]`
  // lookup downstream would throw. Found by the D110 seam audit, which wrote the old
  // shape rather than going through `saveSettings`.
  const present = Object.fromEntries(
    Object.entries(stored ?? {}).filter(([, value]) => value !== undefined),
  ) as Partial<Settings>;
  return { ...DEFAULT_SETTINGS, ...present };
}

/**
 * The single choke point for changing settings, and therefore the place coverage is
 * recorded.
 *
 * Every route into pausing or resuming — the popup button, revoking consent, delete-all —
 * comes through here, so hooking it once catches all of them. Recording the transition in
 * the caller instead would mean remembering to do it at every future call site, and the
 * failure would be silent: predictions would resolve to `miss` for windows nobody watched.
 */
export async function saveSettings(patch: Partial<Settings>): Promise<Settings> {
  // The choke point validates too, rather than trusting each caller. A UI that forgot to
  // check would otherwise write a one-second session timeout into the store, and every
  // feature in the project would silently start describing something else.
  const error = settingsError(patch);
  if (error !== null) throw new Error(error);

  const previous = await loadSettings();
  const next = { ...previous, ...patch };
  await writeMeta(SETTINGS_KEY, next);

  const was = isCollecting(previous);
  const is = isCollecting(next);
  if (was !== is) {
    const now = Date.now();
    await (is ? recordCollectionStarted(now) : recordCollectionStopped(now));
  }
  return next;
}

/**
 * Whether an event may be written at all.
 *
 * The single gate. The navigation listener is registered unconditionally — MV3 requires
 * top-level registration for the service worker to be woken at all — so this function,
 * not the listener, is what makes "installed but not collecting" a real state.
 */
export function isCollecting(settings: Settings): boolean {
  return settings.consentGrantedAt !== null && !settings.paused;
}
