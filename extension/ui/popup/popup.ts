/**
 * A developer surface, not the product. T14 builds the dashboard and T15 builds real
 * onboarding; this exists so T6 can be verified by hand — browse ten sites, open this,
 * see ten events with the right domains and categories.
 *
 * It reads IndexedDB directly. A popup runs in the extension's own origin, so it opens
 * the same database the service worker writes to; there is no message passing to get
 * wrong. Every value is written with `textContent`, never `innerHTML` — the T5 spike
 * rendered `<all_urls>` as an HTML tag and reported its own configuration wrongly.
 */
import { rejectionCounts } from "../../src/collect/collector";
import { DEFAULT_IMPORT_DAYS, importProgress } from "../../src/collect/import";
import { deleteEverything } from "../../src/storage/delete";
import { buildExport, exportFilename, serialiseExport } from "../../src/storage/export";
import { countsByCategory, countEvents, recentEvents } from "../../src/storage/events";
import { isCollecting, loadSettings, saveSettings } from "../../src/storage/settings";
import { countLabels } from "../../src/storage/labels";
import { readJob, readModel } from "../../src/model/train";
import { isIdentity } from "../../src/model/calibrate";
import { allPredictions, predictionCounts } from "../../src/storage/predictions";

function element(id: string): HTMLElement {
  const found = document.getElementById(id);
  if (!found) throw new Error(`missing element: ${id}`);
  return found;
}

function replace(host: HTMLElement, node: Node | null, emptyText: string): void {
  host.textContent = "";
  if (node === null) {
    const p = document.createElement("p");
    p.className = "empty";
    p.textContent = emptyText;
    host.append(p);
    return;
  }
  host.append(node);
}

function table(rows: ReadonlyArray<readonly [string, string]>, rightClass: string): HTMLElement {
  const el = document.createElement("table");
  for (const [left, right] of rows) {
    const tr = el.insertRow();
    const a = tr.insertCell();
    a.textContent = left;
    const b = tr.insertCell();
    b.className = rightClass;
    b.textContent = right;
  }
  return el;
}

function clockTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

let pollTimer: ReturnType<typeof setTimeout> | null = null;

/**
 * The import block.
 *
 * Hidden until the user has agreed to Tise storing anything at all — offering to read
 * their whole history before that would be asking for the larger thing first.
 */
async function renderImport(consented: boolean): Promise<void> {
  const block = element("import-block");
  block.hidden = !consented;
  if (!consented) return;

  const granted = await chrome.permissions.contains({ permissions: ["history"] });
  const progress = await importProgress();
  const status = element("import-status");
  const detail = element("import-detail");
  const button = element("import") as HTMLButtonElement;

  button.disabled = false;
  button.hidden = false;

  if (progress?.state === "running") {
    status.textContent = "Importing…";
    detail.textContent = progress.pagesTotal
      ? `${progress.pagesDone.toLocaleString()} of ${progress.pagesTotal.toLocaleString()} pages read, ${progress.eventsWritten.toLocaleString()} events written.`
      : "Reading your history…";
    button.disabled = true;
    button.textContent = "Importing…";
    // The worker owns the import; the popup only watches, and may be closed meanwhile.
    pollTimer = setTimeout(() => void render(), 500);
    return;
  }

  if (progress?.state === "failed") {
    status.textContent = "Import failed";
    detail.textContent = progress.error ?? "Unknown error.";
    button.textContent = "Try again";
    return;
  }

  if (progress?.state === "done") {
    const skipped = Object.entries(progress.skipped)
      .map(([reason, count]) => `${count.toLocaleString()} ${reason}`)
      .join(", ");
    const stopped = progress.stoppedAt
      ? ` Stopped at ${new Date(progress.stoppedAt).toLocaleDateString()}, where Tise's own collection begins.`
      : "";
    status.textContent = "History imported";
    detail.textContent =
      `${progress.eventsWritten.toLocaleString()} events from the last ${progress.windowDays} days` +
      (skipped ? `, ${skipped} filtered out.` : ".") +
      stopped;
    button.textContent = "Import again";
    return;
  }

  status.textContent = granted ? "History import" : "History import — needs permission";
  detail.textContent = granted
    ? `Reads the last ${DEFAULT_IMPORT_DAYS} days from this browser, once. Nothing leaves the device.`
    : `Chrome will ask first. Declining costs you the import and nothing else — Tise keeps working, collecting from here on.`;
  button.textContent = "Import my history";
}

/**
 * The model panel. A developer surface, like the rest of this popup — T14 replaces it.
 *
 * It shows what training has produced and what it was produced from, because a
 * coefficient vector with no row count beside it is not something anyone can judge. The
 * button runs the chunks back to back; the alarm does one at a time and needs no button.
 */
async function renderTraining(consented: boolean): Promise<void> {
  const block = element("train-block");
  block.hidden = !consented;
  if (!consented) return;

  const status = element("train-status");
  const detail = element("train-detail");
  const button = element("train") as HTMLButtonElement;
  button.disabled = false;
  button.textContent = "Train now";

  const [job, model] = await Promise.all([readJob(), readModel()]);

  if (job !== undefined) {
    const done = job.state.iterationsDone;
    status.textContent = "Training";
    detail.textContent = `${done.toLocaleString()} of ${job.spec.iterations.toLocaleString()} steps, ${job.rowCount.toLocaleString()} labels.`;
    return;
  }

  if (model === undefined) {
    const labels = await countLabels();
    status.textContent = "No model yet";
    detail.textContent =
      labels === 0
        ? "Nothing to learn from. Browse or import some history first."
        : `${labels.toLocaleString()} labels ready. Training runs on a schedule, or press the button.`;
    return;
  }

  const positives = model.positiveCount / model.rowCount;
  status.textContent = "Trained";

  // The gradient norm is here rather than hidden because an unconverged fit is not wrong
  // in any way a score reveals — it is just quietly worse.
  const facts = [
    `${model.rowCount.toLocaleString()} labels, ${(positives * 100).toFixed(0)}% positive`,
    `feature set ${model.featureSet}`,
    `final gradient ${model.state.gradientNorm.toExponential(1)}`,
  ];

  // Calibration is reported as its own claim. An identity calibrator means the raw
  // numbers were left alone because there was too little held-out data to do better,
  // which is a different statement from "calibrated".
  facts.push(
    isIdentity(model.calibrator)
      ? `uncalibrated (only ${model.nCalibration} held-out rows)`
      : `${model.calibrator.method} ${model.calibrator.version}, slope ` +
        `${model.calibrator.a.toFixed(2)} on ${model.nCalibration} held-out rows`,
  );

  const policy = model.policy;
  if (policy !== null && policy.targetMet) {
    facts.push(
      `answers above ${policy.threshold.toFixed(2)} confidence — ` +
        `${(policy.coverage * 100).toFixed(0)}% of cases at ` +
        `${(policy.accuracy * 100).toFixed(0)}% on validation`,
    );
  } else {
    // The branch the author's own browsing takes. Saying so plainly is the point: a
    // prediction shown anyway would be a promise the measurement did not support.
    facts.push(
      `predicts nothing — no confidence threshold reached the ` +
        `${((policy?.targetAccuracy ?? 0.9) * 100).toFixed(0)}% target on held-out data`,
    );
  }

  detail.textContent = `${facts.join(". ")}. Trained ${new Date(model.trainedAt).toLocaleString()}.`;
}

/**
 * The registry panel. Counts only — no prediction is shown here.
 *
 * That is not a placeholder for T14. On this data every prediction is abstained (D70), so
 * a panel listing "what Tise thinks you will do next" would be listing things the
 * measurement said not to claim. What can honestly be shown today is how many predictions
 * exist and how they resolved, including how many were withheld.
 */
async function renderRegistry(consented: boolean): Promise<void> {
  const block = element("registry-block");
  block.hidden = !consented;
  if (!consented) return;

  const status = element("registry-status");
  const detail = element("registry-detail");
  const predictions = await allPredictions();

  if (predictions.length === 0) {
    status.textContent = "No predictions yet";
    detail.textContent =
      "Predictions are made for sessions that have closed, once a model exists.";
    return;
  }

  const counts = await predictionCounts();
  const withheld = predictions.filter((p) => p.abstained).length;
  const scoreable = (counts["hit"] ?? 0) + (counts["miss"] ?? 0);

  status.textContent = `${predictions.length.toLocaleString()} predictions`;
  const parts = [
    `${counts["hit"] ?? 0} hit, ${counts["miss"] ?? 0} miss, ` +
      `${counts["pending"] ?? 0} pending, ${counts["expired"] ?? 0} expired`,
    // `expired` is called out rather than folded in, because a reader who assumes it is a
    // miss will read a fabricated negative into the score.
    `${scoreable} scored — expired means Tise was not watching, so it counts as nothing`,
    `${withheld} withheld below the confidence threshold, kept so it can be checked later`,
  ];
  detail.textContent = parts.join(". ") + ".";
}

async function render(): Promise<void> {
  if (pollTimer !== null) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
  const settings = await loadSettings();
  const collecting = isCollecting(settings);
  const total = await countEvents();

  const status = element("status");
  const detail = element("detail");
  const toggle = element("toggle") as HTMLButtonElement;

  if (settings.consentGrantedAt === null) {
    status.textContent = "Not collecting";
    detail.textContent =
      "Tise has stored nothing. It will not begin until you turn it on here.";
    toggle.textContent = "Start collecting";
  } else if (settings.paused) {
    status.textContent = "Paused";
    detail.textContent = `${total} events kept. Nothing new is being written.`;
    toggle.textContent = "Resume";
  } else {
    status.textContent = "Collecting";
    detail.textContent = `${total} events, session timeout ${settings.sessionTimeoutSeconds / 60} minutes.`;
    toggle.textContent = "Pause";
  }
  toggle.disabled = false;
  toggle.dataset["collecting"] = String(collecting);

  await renderImport(settings.consentGrantedAt !== null);
  await renderTraining(settings.consentGrantedAt !== null);
  await renderRegistry(settings.consentGrantedAt !== null);

  const categories = [...(await countsByCategory())].sort((a, b) => b[1] - a[1]);
  replace(
    element("categories"),
    categories.length ? table(categories.map(([c, n]) => [c, String(n)]), "n") : null,
    "Nothing collected yet.",
  );

  const recent = await recentEvents(10);
  replace(
    element("recent"),
    recent.length
      ? table(
          recent.map((e) => [`${clockTime(e.occurredAt)}  ${e.domain}`, e.category] as const),
          "cat",
        )
      : null,
    "Nothing collected yet.",
  );

  const rejected = Object.entries(await rejectionCounts()).sort((a, b) => b[1] - a[1]);
  replace(
    element("rejected"),
    rejected.length ? table(rejected.map(([r, n]) => [r, String(n)]), "n") : null,
    "Nothing filtered yet.",
  );
}

element("toggle").addEventListener("click", async () => {
  const settings = await loadSettings();
  if (settings.consentGrantedAt === null) {
    await saveSettings({ consentGrantedAt: new Date().toISOString(), paused: false });
  } else {
    await saveSettings({ paused: !settings.paused });
  }
  await render();
});

element("import").addEventListener("click", async () => {
  // Must be inside the click handler: Chrome requires a user gesture for this, and it
  // focuses Deny (D33), so the text above the button has to have done the persuading.
  const granted = await chrome.permissions.request({ permissions: ["history"] });
  if (!granted) {
    element("import-status").textContent = "Not imported";
    element("import-detail").textContent =
      "That is a valid answer. Tise collects from here on and never asks again.";
    return;
  }
  void chrome.runtime.sendMessage({ type: "tise:import" });

  // The worker publishes "running" before it calls `search`, but not before this line
  // returns. Give it a moment rather than rendering an idle state over a live import.
  element("import-status").textContent = "Importing…";
  (element("import") as HTMLButtonElement).disabled = true;
  setTimeout(() => void render(), 300);
});

element("train").addEventListener("click", () => {
  const button = element("train") as HTMLButtonElement;
  button.disabled = true;
  button.textContent = "Training…";
  element("train-status").textContent = "Training";
  element("train-detail").textContent =
    "Running every chunk back to back. The scheduled run does one at a time instead.";

  // The worker owns the run, so closing the popup does not stop it.
  void chrome.runtime.sendMessage({ type: "tise:train" }, () => void render());
});

element("export").addEventListener("click", async () => {
  const data = await buildExport({
    now: Date.now(),
    extensionVersion: chrome.runtime.getManifest().version,
  });

  // A blob URL and an anchor: no `downloads` permission, and the file is written by the
  // browser's own save flow rather than by anything Tise controls.
  const blob = new Blob([serialiseExport(data)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = exportFilename(Date.now());
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);

  element("detail").textContent = `Exported ${data.events.length.toLocaleString()} events.`;
});

/**
 * Two clicks, no dialog.
 *
 * "Delete all" wipes every store including consent, so it deserves a confirmation — but
 * a `confirm()` in a popup dismisses the popup on some platforms, and a destructive
 * action whose confirmation can eat itself is worse than no confirmation.
 */
let deleteArmed = false;

element("clear").addEventListener("click", async () => {
  const button = element("clear") as HTMLButtonElement;

  if (!deleteArmed) {
    deleteArmed = true;
    button.textContent = "Really delete everything?";
    element("detail").textContent =
      "This removes every event, your settings, and Tise's permission to read history. It is the install state.";
    setTimeout(() => {
      deleteArmed = false;
      button.textContent = "Delete all";
    }, 6000);
    return;
  }

  deleteArmed = false;
  button.textContent = "Delete all";

  const outcome = await deleteEverything();

  // Hand the capability back too. Keeping a granted permission after "delete everything"
  // would leave Tise able to read a history it has just promised to have forgotten.
  await chrome.permissions.remove({ permissions: ["history"] });

  await render();
  element("detail").textContent = `Deleted ${outcome.eventsDeleted.toLocaleString()} events and every setting.`;
});

void render();
