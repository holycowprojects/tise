/**
 * The toolbar popup: status, the card, and the way into everything else.
 *
 * **It stopped being a developer-only surface at T14 and said otherwise until T15.** The
 * subtitle read "Developer view — the real interface arrives at T14" for two days after
 * T14 shipped the dashboard, which is the first sentence anyone installing Tise would
 * read. Same defect class as T18b's README and D98's report banners: a hand-written
 * sentence about a system that had moved. It is now derived from the actual state.
 *
 * The lower half — categories, most recent, filtered out — is still a developer surface
 * and is still here on purpose: it is how T6 was verified by hand, and it is the cheapest
 * way to see that collection is working at all.
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
import { allEvents, countsByCategory, countEvents, recentEvents } from "../../src/storage/events";
import { sessionise } from "../../src/features/sessions";
import { categoryTransitions } from "../../src/features/transitions";
import { currentCategory, nextCategoryCard } from "../../src/model/nextCategory";
import { isCollecting, loadSettings, saveSettings } from "../../src/storage/settings";
import { countLabels } from "../../src/storage/labels";
import { allSpans } from "../../src/storage/spans";
import { engagementGate, gateSentence } from "../../src/model/engagement";
import {
  isStaleModel,
  readJob,
  readModel,
  readModelIncludingStale,
} from "../../src/model/train";
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
 * The attention block. **The reason this exists is a bug worth naming.**
 *
 * D96 shipped attention collection gated on `chrome.permissions.contains(["tabs","idle"])`
 * and never built anything that could *request* them. They are optional permissions, so
 * Chrome does not grant them at install — meaning the gate could never open, the span
 * store stayed empty, and the only symptom was a number that never moved. It surfaced
 * because Akash sent a screenshot of an empty store, not because anything failed.
 *
 * Hidden until consent, for the same reason the import block is: asking to watch which tab
 * is in front before the person has agreed Tise may store anything is asking for the
 * larger thing first.
 */
async function renderAttention(consented: boolean): Promise<void> {
  const block = element("attention-block");
  block.hidden = !consented;
  if (!consented) return;

  const granted = await chrome.permissions.contains({ permissions: ["tabs", "idle"] });
  const status = element("attention-status");
  const detail = element("attention-detail");
  const button = element("attention") as HTMLButtonElement;

  if (granted) {
    const spans = await allSpans();
    // Distinct events, counted from the spans alone rather than by loading every event:
    // D96 forbids inventing a span, so every `eventId` here belongs to a real navigation.
    const pages = new Set(spans.map((span) => span.eventId)).size;

    status.textContent = "Attention measured";
    if (spans.length === 0) {
      // The state that hid a two-day bug: collection looked enabled and recorded nothing,
      // and nothing displayed the number that would have shown it (D101).
      detail.textContent =
        "Granted, but nothing recorded yet. A span appears for each page you actually " +
        "look at, so browse for a minute and reopen this.";
    } else {
      const total = spans.reduce((sum, span) => sum + span.activeSeconds, 0);
      // The gate is computed rather than described. The sentence this replaced —
      // "Predictions need roughly ten measured visits per topic before they begin" — was
      // written by hand in D101 and wrong by more than an order of magnitude: ten per topic
      // is when a *label* becomes possible, not when a model may be trusted. D99's rule is
      // 1,000 visits, 20 sittings and 200 labels, and now this line reads it.
      const settings = await loadSettings();
      const gate = engagementGate(
        await allEvents(),
        spans,
        settings.sessionTimeoutSeconds,
      );
      detail.textContent =
        `${spans.length.toLocaleString()} span${spans.length === 1 ? "" : "s"} over ` +
        `${pages.toLocaleString()} page${pages === 1 ? "" : "s"}, ` +
        `${Math.round(total / 60).toLocaleString()} minutes of attention. ` +
        gateSentence(gate);
    }
    button.hidden = true;
    return;
  }

  status.textContent = "Attention not measured";
  detail.textContent =
    "Tise can measure how long you actually look at a page, rather than how long a tab sat open. " +
    "That needs permission to see which tab is in front and whether you are idle. " +
    "No page content is read, and nothing new is stored about where you go.";
  button.hidden = false;
  button.disabled = false;
}

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
    // A stale model reads as "no model" everywhere else on purpose, so every caller
    // already handles it. Here — the one place offering the fix — it is named, because
    // "no model yet" after a year of browsing would read as a bug rather than a retrain.
    if (isStaleModel(await readModelIncludingStale())) {
      status.textContent = "Model needs retraining";
      detail.textContent =
        `A model trained by an earlier build did not record which feature set it was ` +
        `fitted on, so it cannot be used safely and was set aside rather than guessed at. ` +
        `${labels.toLocaleString()} labels ready — press the button.`;
      return;
    }
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

  // The accuracy-versus-coverage curve is still measured and still published (D88); it no
  // longer decides whether anything is shown. Reporting it as a gate — which this panel
  // did until the D88 replacement was finally implemented — described a rule the shipped
  // path had stopped applying.
  const policy = model.policy;
  if (policy !== null && policy.targetMet) {
    facts.push(
      `at ${policy.threshold.toFixed(2)} confidence it would answer ` +
        `${(policy.coverage * 100).toFixed(0)}% of cases at ` +
        `${(policy.accuracy * 100).toFixed(0)}% on validation`,
    );
  } else {
    facts.push(
      `no confidence threshold reached ` +
        `${((policy?.targetAccuracy ?? 0.9) * 100).toFixed(0)}% on held-out data, which is ` +
        `a measurement rather than a reason to say nothing`,
    );
  }

  detail.textContent = `${facts.join(". ")}. Trained ${new Date(model.trainedAt).toLocaleString()}.`;
}

/**
 * The card. **The first thing Tise has ever shown a person about their own browsing.**
 *
 * It answers "what comes next?" with counts, not with a model, and every row carries the
 * denominator behind it — D88's replacement for abstention, which was retired because
 * D70 found no confidence threshold that certified the target on any fold and the
 * extension consequently answered nothing at all.
 *
 * **No model is loaded here and that is the point.** D102 benchmarked the fitted
 * transition table for the first time: it cleared its pre-registered bar and still lost,
 * on every corpus, to a rule that knows only that you will not carry on doing what you
 * just stopped. So the card shows what the person actually did — a frequency with its
 * denominator is either true of their data or it is not — and claims no skill it has not
 * established. That also means it works the moment there is history, with no training run,
 * no adopted target and no dwell.
 */
async function renderCard(consented: boolean, timeoutSeconds: number): Promise<void> {
  const block = element("card-block");
  block.hidden = !consented;
  if (!consented) return;

  const status = element("card-status");
  const detail = element("card-detail");
  const answers = element("card-answers");
  const caveat = element("card-caveat");
  caveat.textContent = "";

  const sessions = sessionise(await allEvents(), timeoutSeconds);
  const transitions = categoryTransitions(sessions);
  const from = currentCategory(transitions);

  if (from === null) {
    status.textContent = "What comes next";
    detail.textContent =
      "Nothing yet. This needs at least one change of topic to have something to count.";
    replace(answers, null, "");
    return;
  }

  const card = nextCategoryCard(transitions, from);
  if (card.kind === "not-enough-history") {
    status.textContent = "What comes next";
    detail.textContent =
      `${card.changes} topic ${card.changes === 1 ? "change" : "changes"} so far. ` +
      `${card.needed} more and this starts answering.`;
    replace(answers, null, "");
    // The one gate D88 permits is a floor on evidence, and saying which floor and how far
    // off it is turns waiting into something the person can see the end of.
    caveat.textContent =
      "The only thing held back is a number with too little behind it to be worth showing.";
    return;
  }

  status.textContent = `After ${from}, you usually go to…`;
  const shown = card.answers.slice(0, 4);
  const rows = document.createElement("table");
  for (const answer of shown) {
    const tr = rows.insertRow();
    tr.insertCell().textContent = answer.category;
    const share = tr.insertCell();
    share.className = "share";
    // Whole numbers (D88). A card reading 47.3% invites a precision the denominator
    // underneath it does not support.
    share.textContent = `${Math.round(answer.share * 100)}%`;
    const of = tr.insertCell();
    of.className = "of";
    of.textContent = `${answer.count} of ${answer.denominator}`;
  }
  replace(answers, rows, "");

  const remaining = card.answers.length - shown.length;
  const others = remaining > 0 ? ` ${remaining} other ${remaining === 1 ? "topic" : "topics"} not shown.` : "";
  detail.textContent =
    card.basis === "conditional"
      ? `Counted from the ${card.denominator} times you have left ${from}.` + others
      : `Counted from all ${card.denominator} of your topic changes — you have not left ` +
        `${from} often enough yet for its own count to mean much.` + others;

  caveat.textContent =
    "Measured on your browsing, on this device. These are counts of what you did, not a " +
    "prediction: a model that conditions on what you just left has not been shown to beat " +
    "them.";
}

/**
 * The registry panel. Counts only — no individual prediction is shown here.
 *
 * Not for the reason it used to be. Until D88's replacement was implemented, every
 * prediction was abstained (D70) and listing them would have meant showing things the
 * measurement said not to claim. Nothing is withheld now — but these rows still belong to
 * `return_24h`, which D88 retired as the product target, so listing them individually
 * would put a retired question in front of the person. The card above is the one Tise
 * actually stands behind. What belongs here is the scorecard: how many exist and how they
 * resolved.
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
    // "hit" is the topic coming back, not Tise being right — `resolveOutcome` never reads
    // the probability. Named here so the popup cannot be read as a score (D108).
    `${counts["hit"] ?? 0} came back, ${counts["miss"] ?? 0} did not, ` +
      `${counts["pending"] ?? 0} pending, ${counts["expired"] ?? 0} expired`,
    // `expired` is called out rather than folded in, because a reader who assumes it is a
    // miss will read a fabricated negative into the score.
    `${scoreable} scored — expired means Tise was not watching, so it counts as nothing`,
    // Non-zero only for rows written before D88's replacement landed. New predictions are
    // never withheld, so this counts down into history rather than up.
    withheld > 0
      ? `${withheld} withheld by the retired confidence rule, kept so they can still be checked`
      : "nothing withheld — every prediction is kept and scored",
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

  const sub = element("sub");
  if (settings.consentGrantedAt === null) {
    status.textContent = "Not collecting";
    detail.textContent =
      "Tise has stored nothing. Read what it would store before turning it on.";
    toggle.textContent = "Start collecting";
    // Before consent the popup is not the place to make the argument — 340 pixels is not
    // where you explain what an extension will record. D33 measured that Chrome focuses
    // Deny on its permission dialog, so the persuading has to happen on a page with room.
    sub.textContent = "Learns from your browsing, on this device only.";
  } else if (settings.paused) {
    status.textContent = "Paused";
    detail.textContent = `${total} events kept. Nothing new is being written.`;
    toggle.textContent = "Resume";
    sub.textContent = "Everything stays on this device.";
  } else {
    status.textContent = "Collecting";
    detail.textContent = `${total} events, session timeout ${settings.sessionTimeoutSeconds / 60} minutes.`;
    toggle.textContent = "Pause";
    sub.textContent = "Everything stays on this device.";
  }
  toggle.disabled = false;
  toggle.dataset["collecting"] = String(collecting);

  await renderCard(settings.consentGrantedAt !== null, settings.sessionTimeoutSeconds);
  await renderImport(settings.consentGrantedAt !== null);
  await renderAttention(settings.consentGrantedAt !== null);
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

element("attention").addEventListener("click", async () => {
  // Inside the handler: Chrome requires a user gesture, and it focuses Deny (D33), so the
  // text above the button has to have done the persuading.
  const granted = await chrome.permissions.request({ permissions: ["tabs", "idle"] });
  if (!granted) {
    element("attention-status").textContent = "Attention not measured";
    element("attention-detail").textContent =
      "That is a valid answer. Everything else works exactly as before; Tise simply cannot " +
      "tell a page you read from a tab you left open.";
    (element("attention") as HTMLButtonElement).hidden = true;
    return;
  }
  // The listeners are registered at the worker's top level and check the permission on
  // every event, so nothing needs restarting — the next tab switch records a span.
  await render();
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

element("welcome").addEventListener("click", () => {
  // The full disclosure lives on its own page, and stays reachable after consent: someone
  // who has just agreed is exactly the person most likely to want to re-read what they
  // agreed to.
  void chrome.tabs.create({ url: chrome.runtime.getURL("welcome.html") });
});

element("dashboard").addEventListener("click", () => {
  // `openOptionsPage` rather than a hand-built URL: it reuses an already-open tab, so
  // clicking twice does not leave two copies of the same page behind.
  void chrome.runtime.openOptionsPage();
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
