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
import { endOpenSpan, registerAttentionListeners } from "./collect/attention";
import { chromeHistoryApi, runImport } from "./collect/import";
import {
  enforceRetention,
  RETENTION_ALARM,
  RETENTION_PERIOD_MINUTES,
} from "./storage/retention";
import { isCollecting, loadSettings } from "./storage/settings";
import { DEFAULT_HORIZON_HOURS } from "./features/labels";
import {
  readJob,
  readModel,
  refreshDataset,
  runTrainingChunk,
  TRAINING_ALARM,
  TRAINING_PERIOD_MINUTES,
} from "./model/train";
import { updateRegistry } from "./model/registry";

chrome.webNavigation.onCommitted.addListener(
  (details) => {
    void collect(details);
  },
  // Chrome filters before waking the worker. `chrome://`, `file://` and extension pages
  // are rejected by `registrableDomain` anyway; this just avoids the wake-up.
  { url: [{ schemes: ["http", "https"] }] },
);

/**
 * Retention runs on an alarm, not a timer.
 *
 * The alarm is created on install and on browser startup, and **not** at the top level
 * of this file. Re-creating an alarm resets its schedule, and a service worker that wakes
 * for every navigation would reset it constantly — the alarm would then never fire, and
 * raw events would never expire. That failure is silent, which is the worst kind.
 */
function scheduleAlarms(): void {
  chrome.alarms.create(RETENTION_ALARM, { periodInMinutes: RETENTION_PERIOD_MINUTES });
  chrome.alarms.create(TRAINING_ALARM, { periodInMinutes: TRAINING_PERIOD_MINUTES });
}

chrome.runtime.onInstalled.addListener(scheduleAlarms);
chrome.runtime.onStartup.addListener(scheduleAlarms);

/**
 * Open the welcome page once, on a genuine first install (T15).
 *
 * **The reason this is not left to the popup.** Tise installs able to store nothing and
 * stays that way until someone consents, so an install with no onboarding is an extension
 * that silently does nothing until the person happens to open a 340-pixel popup and press
 * a button whose consequences it has no room to explain. D33 measured that Chrome focuses
 * **Deny** on its permission dialog — the argument has to be made before the dialog, and
 * a popup is not where you make an argument.
 *
 * `reason === "install"` only. An update must not reopen it: the person consented once and
 * reopening a consent page every release trains them to dismiss it, which is the opposite
 * of informed. `onInstalled` also fires for `"update"` and `"chrome_update"`.
 *
 * **Nothing is written here.** No "seen the welcome page" flag, because that would be a
 * stored fact about someone who has not yet agreed to Tise storing facts about them — the
 * install state has to remain genuinely empty, and `zero-writes.test.ts` asserts it.
 */
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason !== "install") return;
  void chrome.tabs.create({ url: chrome.runtime.getURL("welcome.html") });
});

/**
 * Attention listeners, registered at the top level for the same reason the navigation
 * listener is: MV3 reads the registration to decide which events wake the worker, so one
 * added inside a callback would stop firing after the first termination.
 *
 * They no-op until the person has consented *and* granted `tabs` and `idle` — the
 * permission being present is not taken as consent.
 */
registerAttentionListeners();

/**
 * A browser restart leaves whatever span was open unfinished. It is closed as `shutdown`
 * rather than extended to now: the person may have been away for a week, and the gap is
 * unobserved rather than long.
 */
chrome.runtime.onStartup.addListener(() => {
  void endOpenSpan("shutdown");
});

/**
 * Training advances one chunk per alarm, and the alarm keeps firing until the job is
 * done — so a full run takes several wake-ups rather than one long one. That is the
 * point: no single call is long enough for MV3 to have an opinion about it, and the state
 * is on disk before the worker is allowed to die.
 *
 * Nothing here retries or backs off. A chunk that fails leaves the job exactly as it was,
 * and the next alarm picks up from the last state that was written.
 */
chrome.alarms.onAlarm.addListener((alarm) => {
  void (async () => {
    const settings = await loadSettings();
    if (alarm.name === RETENTION_ALARM) {
      await enforceRetention(settings, Date.now());
      return;
    }
    if (alarm.name !== TRAINING_ALARM) return;

    // Nothing was consented to, so there is nothing to learn from. Checked here rather
    // than inside the trainer so the storage layer is never touched at all.
    if (settings.consentGrantedAt === null) return;

    await refreshDataset({
      timeoutSeconds: settings.sessionTimeoutSeconds,
      horizonHours: DEFAULT_HORIZON_HOURS,
    });
    await runTrainingChunk({ timeoutSeconds: settings.sessionTimeoutSeconds });

    // Predict for newly closed sessions and resolve whatever has come due. Both halves
    // are idempotent, so running this on every alarm — including ones where training did
    // nothing — costs a pass and cannot corrupt anything.
    await updateRegistry({ now: Date.now() });
  })();
});

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

interface TrainMessage {
  readonly type: "tise:train" | "tise:train-status";
}

function isTrainMessage(message: unknown): message is TrainMessage {
  const type = (message as { type?: unknown } | null)?.type;
  return type === "tise:train" || type === "tise:train-status";
}

/**
 * Training on demand, so it can be watched rather than only inferred from an alarm.
 *
 * `tise:train` runs chunks back to back until the job finishes, which is what a developer
 * surface needs and **not** how the alarm path works — the alarm advances one chunk and
 * lets the worker die. Both go through the same `runTrainingChunk`, so the model this
 * produces is the model the alarm would have produced, arrived at sooner.
 *
 * **And then it updates the registry, which it used not to.** Producing the same model is
 * not the same as reaching the same state: the alarm path predicts and resolves after
 * training, so a button that only trained left the person with a fresh model, no
 * predictions, and a six-hour wait for the next alarm to use it.
 */
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!isTrainMessage(message)) return false;

  void (async () => {
    const settings = await loadSettings();
    if (settings.consentGrantedAt === null) {
      sendResponse({ ok: false, reason: "not-consented" });
      return;
    }

    if (message.type === "tise:train-status") {
      sendResponse({ ok: true, job: await readJob(), model: await readModel() });
      return;
    }

    await refreshDataset({
      timeoutSeconds: settings.sessionTimeoutSeconds,
      horizonHours: DEFAULT_HORIZON_HOURS,
    });

    const started = Date.now();
    let outcome = await runTrainingChunk({
      timeoutSeconds: settings.sessionTimeoutSeconds,
    });
    while (outcome.state === "training") {
      outcome = await runTrainingChunk({ timeoutSeconds: settings.sessionTimeoutSeconds });
    }

    // **The alarm path does this and this path did not**, so pressing the button produced
    // a model and no predictions, and the popup said "No predictions yet" until the next
    // training alarm — up to six hours later, with nothing on screen explaining the wait.
    // Found in a screenshot immediately after the retrain D105 required.
    //
    // The docstring above claimed the two paths were equivalent because both go through
    // `runTrainingChunk`. They produced the same *model*; only one of them then used it.
    // `updateRegistry` is idempotent by design, so running it here costs nothing when
    // there is nothing new.
    const registry =
      outcome.state === "done" ? await updateRegistry({ now: Date.now() }) : undefined;

    sendResponse({
      ok: outcome.state === "done",
      outcome,
      registry,
      elapsedMs: Date.now() - started,
    });
  })();

  return true; // keep the message channel open for the async reply
});
