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

async function render(): Promise<void> {
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

element("clear").addEventListener("click", async () => {
  await clearEvents();
  await render();
});

void render();
