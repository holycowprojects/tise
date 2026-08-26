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
import { clearEvents, countsByCategory, countEvents, recentEvents } from "../../src/storage/events";
import { isCollecting, loadSettings, saveSettings } from "../../src/storage/settings";

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

element("clear").addEventListener("click", async () => {
  await clearEvents();
  await render();
});

void render();
