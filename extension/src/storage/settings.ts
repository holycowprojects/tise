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
