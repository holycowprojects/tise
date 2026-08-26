// Tise permission spike — THROWAWAY CODE. Deleted at the end of T5.
// Reads what probe.js recorded and states the verdict in plain language.

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

function row(key, value) {
  return `<tr><td class="k">${key}</td><td>${value}</td></tr>`;
}

async function render() {
  const rows = await readAll();
  const manifest = rows.find((r) => r.kind === "manifest");
  document.getElementById("variant").textContent =
    manifest?.variant ?? chrome.runtime.getManifest().name;

  const visited = rows.filter((r) => r.kind === "history.onVisited");
  const visits = rows.filter((r) => r.kind === "history.getVisits");
  const nav = rows.filter((r) => r.kind === "webNavigation.onCommitted");

  const historyUrls = visited.filter((r) => r.urlPresent).length;
  const navUrls = nav.filter((r) => r.urlPresent).length;
  const lastVisit = visits[visits.length - 1];

  const parts = [];

  parts.push(
    verdict(
      `chrome.history.onVisited yields a URL &nbsp;<em>(${visited.length} events)</em>`,
      visited.length === 0 ? null : historyUrls > 0,
      visited.length ? `fields: ${visited[visited.length - 1].fields.join(", ")}` : "",
    ),
  );

  parts.push(
    verdict(
      `chrome.webNavigation.onCommitted yields a URL &nbsp;<em>(${nav.length} events)</em>`,
      nav.length === 0 ? null : navUrls > 0,
      nav.length ? `fields: ${nav[nav.length - 1].fields.join(", ")}` : "",
    ),
  );

  if (lastVisit) {
    parts.push(
      verdict(
        "getVisits returns a duration field",
        lastVisit.hasAnyDurationField,
        `VisitItem fields: ${lastVisit.visitItemFields.join(", ")}\ntransition: ${
          lastVisit.transition
        }`,
      ),
    );
  }

  parts.push(
    verdict("IndexedDB works with no storage permission", rows.length > 0, ""),
  );

  const table = [
    row("permissions", JSON.stringify(manifest?.permissions ?? [])),
    row("host_permissions", JSON.stringify(manifest?.hostPermissions ?? [])),
    row("APIs present", JSON.stringify(manifest?.apisPresent ?? {}, null, 0)),
    row("observations", rows.length),
  ].join("");

  document.getElementById("out").innerHTML =
    parts.join("") + `<table>${table}</table>`;
}

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
