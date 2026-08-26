/**
 * The service worker. Deliberately thin.
 *
 * MV3 terminates service workers aggressively, so the listener must be registered at the
 * top level — Chrome reads the registration to know which events should wake the worker
 * at all. That means the listener exists whether or not the user has consented, and the
 * consent check lives one layer down in `collect()`. It is checked before the URL is
 * even parsed.
 *
 * Nothing here is scheduled, cached in memory, or held across invocations. Any state the
 * collector needs is read from IndexedDB on each event, because a variable in this file
 * survives exactly as long as Chrome feels like keeping the worker alive.
 */
import { collect } from "./collect/collector";

chrome.webNavigation.onCommitted.addListener(
  (details) => {
    void collect(details);
  },
  // Chrome filters before waking the worker. `chrome://`, `file://` and extension pages
  // are rejected by `registrableDomain` anyway; this just avoids the wake-up.
  { url: [{ schemes: ["http", "https"] }] },
);
