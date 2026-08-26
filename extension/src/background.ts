/**
 * The service worker. Deliberately thin.
 *
 * MV3 terminates service workers aggressively, so listeners must be registered at the
 * top level — Chrome reads the registration to know which events should wake the worker
 * at all. That means they exist whether or not the user has consented, and the consent
 * check lives one layer down. It is checked before the URL is even parsed.
 *
 * Nothing here is scheduled, cached in memory, or held across invocations. Any state the
 * collector needs is read from IndexedDB on each event, because a variable in this file
 * survives exactly as long as Chrome feels like keeping the worker alive.
 */
import { collect } from "./collect/collector";
import { chromeHistoryApi, runImport } from "./collect/import";
import { isCollecting, loadSettings } from "./storage/settings";

chrome.webNavigation.onCommitted.addListener(
  (details) => {
    void collect(details);
  },
  // Chrome filters before waking the worker. `chrome://`, `file://` and extension pages
  // are rejected by `registrableDomain` anyway; this just avoids the wake-up.
  { url: [{ schemes: ["http", "https"] }] },
);

interface ImportMessage {
  readonly type: "tise:import";
  readonly days?: number;
}

function isImportMessage(message: unknown): message is ImportMessage {
  return (
    typeof message === "object" &&
    message !== null &&
    (message as { type?: unknown }).type === "tise:import"
  );
}

/**
 * The import runs here rather than in the popup, so closing the popup does not kill it.
 *
 * The worker stays alive while an async listener holds the response channel open, and
 * T5 measured the whole pass at about 3.5 seconds for 5,000 pages — well inside the
 * budget. Progress is written to storage as it goes, so a popup that closes and reopens
 * picks the state back up rather than starting again.
 */
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!isImportMessage(message)) return false;

  void (async () => {
    const settings = await loadSettings();

    // The Chrome permission dialog is one consent; agreeing to let Tise store anything
    // at all is the other. An import needs both.
    if (!isCollecting(settings) && settings.consentGrantedAt === null) {
      sendResponse({ ok: false, reason: "not-consented" });
      return;
    }

    const progress = await runImport({
      api: chromeHistoryApi(),
      now: Date.now(),
      sessionTimeoutSeconds: settings.sessionTimeoutSeconds,
      overrides: settings.overrides,
      ...(message.days !== undefined ? { days: message.days } : {}),
    });
    sendResponse({ ok: progress.state === "done", progress });
  })();

  return true; // keep the message channel open for the async reply
});
