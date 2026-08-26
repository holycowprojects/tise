// Tise permission spike — THROWAWAY CODE. Deleted at the end of T5.
// Reads what probe.js recorded and states each verdict in plain language.

const DB_NAME = "tise-spike";
const STORE = "observations";

function openDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: "id", autoIncrement: true });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function readAll() {
  const db = await openDb();
  const rows = await new Promise((resolve, reject) => {
    const request = db.transaction(STORE, "readonly").objectStore(STORE).getAll();
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
  db.close();
  return rows;
}

function verdict(label, state, detail) {
  const cls = state === true ? "yes" : state === false ? "no" : "none";
  const mark = state === true ? "YES" : state === false ? "NO" : "—";
  return `<div class="verdict ${cls}"><strong>${mark}</strong> ${label}${
    detail ? `<pre>${detail}</pre>` : ""
  }</div>`;
}

async function render() {
  const rows = await readAll();
  const manifest = rows.find((r) => r.kind === "manifest");
  const live = chrome.runtime.getManifest();
  document.getElementById("variant").textContent = live.name;

  const granted = await chrome.permissions.getAll();
  const hasHistory = (granted.permissions ?? []).includes("history");

  document.getElementById("grant").hidden =
    !(live.optional_permissions ?? []).includes("history") || hasHistory;
  document.getElementById("import").hidden = !hasHistory;

  const visited = rows.filter((r) => r.kind === "history.onVisited");
  const visits = rows.filter((r) => r.kind === "history.getVisits");
  const nav = rows.filter((r) => r.kind === "webNavigation.onCommitted");
  const added = rows.filter((r) => r.kind === "permissions.onAdded");
  const imports = rows.filter((r) => r.kind === "import.probe");

  const lastVisit = visits[visits.length - 1];
  const lastImport = imports[imports.length - 1];
  const parts = [];

  parts.push(
    verdict(
      `history.onVisited yields a URL <em>(${visited.length} events)</em>`,
      visited.length === 0 ? null : visited.some((r) => r.urlPresent),
      visited.length ? `fields: ${visited[visited.length - 1].fields.join(", ")}` : "",
    ),
  );

  parts.push(
    verdict(
      `webNavigation.onCommitted yields a URL <em>(${nav.length} events)</em>`,
      nav.length === 0 ? null : nav.some((r) => r.urlPresent),
      nav.length ? `fields: ${nav[nav.length - 1].fields.join(", ")}` : "",
    ),
  );

  if (lastVisit) {
    parts.push(
      verdict(
        "getVisits returns a duration field",
        lastVisit.hasAnyDurationField,
        `VisitItem: ${lastVisit.visitItemFields.join(", ")}`,
      ),
    );
  }

  if ((live.optional_permissions ?? []).includes("history")) {
    parts.push(
      verdict(
        `history granted at runtime, not at install${
          added.length ? " — and listeners re-attached" : ""
        }`,
        hasHistory,
        added.length ? `onAdded fired: ${added[added.length - 1].granted}` : "",
      ),
    );
  }

  if (lastImport) {
    const table = lastImport.results
      .map((r) =>
        r.error
          ? `${r.label.padEnd(26)} ERROR ${r.error}`
          : `${r.label.padEnd(26)} ${String(r.count).padStart(7)} rows  ${r.spanDays.toFixed(
              1,
            )}d  oldest ${r.oldest?.slice(0, 10) ?? "?"}`,
      )
      .join("\n");
    const best = Math.max(...lastImport.results.map((r) => r.count ?? 0));
    const defaults = lastImport.results.find((r) => r.label === "defaults");
    parts.push(
      verdict(
        "reading the WHOLE history needs explicit startTime + maxResults",
        defaults ? defaults.count < best : null,
        table,
      ),
    );
  }

  parts.push(verdict("IndexedDB works with no storage permission", rows.length > 0, ""));

  document.getElementById("out").innerHTML =
    parts.join("") +
    `<table>
      <tr><td class="k">permissions</td><td>${JSON.stringify(live.permissions ?? [])}</td></tr>
      <tr><td class="k">optional</td><td>${JSON.stringify(live.optional_permissions ?? [])}</td></tr>
      <tr><td class="k">hosts</td><td>${JSON.stringify(live.host_permissions ?? [])}</td></tr>
      <tr><td class="k">granted now</td><td>${JSON.stringify(granted.permissions ?? [])}</td></tr>
      <tr><td class="k">observations</td><td>${rows.length}</td></tr>
      <tr><td class="k">APIs</td><td>${JSON.stringify(manifest?.apisPresent ?? {})}</td></tr>
    </table>`;
}

document.getElementById("grant").addEventListener("click", async () => {
  // Must be inside a click handler: Chrome requires a user gesture.
  const ok = await chrome.permissions.request({ permissions: ["history"] });
  document.getElementById("out").innerHTML = ok
    ? "Granted. Browse a few sites, then reopen this popup."
    : "Denied. That is a valid outcome — the extension must still work, doing nothing.";
  setTimeout(render, 1200);
});

document.getElementById("import").addEventListener("click", async () => {
  document.getElementById("out").textContent = "Reading history…";
  await chrome.runtime.sendMessage({ type: "runImportProbe" });
  render();
});

document.getElementById("clear").addEventListener("click", async () => {
  const db = await openDb();
  await new Promise((resolve) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).clear();
    tx.oncomplete = resolve;
  });
  db.close();
  render();
});

render();
