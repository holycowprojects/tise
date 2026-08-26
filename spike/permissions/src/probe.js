// Tise permission spike — THROWAWAY CODE. Deleted at the end of T5.
//
// It answers one question: what is the smallest permission set that lets Tise observe
// a navigation and learn its URL? The original design documents shipped a manifest that
// could not have collected anything (audit finding 7), so nothing here is assumed.
//
// Everything is recorded to IndexedDB rather than chrome.storage, which also settles a
// question T6 depends on: whether IndexedDB works with no storage permission at all.

const DB_NAME = "tise-spike";
const STORE = "observations";

const MANIFEST = chrome.runtime.getManifest();

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

async function record(entry) {
  const db = await openDb();
  await new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).add({ at: new Date().toISOString(), ...entry });
    tx.oncomplete = resolve;
    tx.onerror = () => reject(tx.error);
  });
  db.close();
}

// --- what the manifest actually asked for -------------------------------------------
record({
  kind: "manifest",
  variant: MANIFEST.name,
  permissions: MANIFEST.permissions ?? [],
  hostPermissions: MANIFEST.host_permissions ?? [],
  optionalHostPermissions: MANIFEST.optional_host_permissions ?? [],
  apisPresent: {
    history: typeof chrome.history !== "undefined",
    webNavigation: typeof chrome.webNavigation !== "undefined",
    tabs: typeof chrome.tabs !== "undefined",
    alarms: typeof chrome.alarms !== "undefined",
    offscreen: typeof chrome.offscreen !== "undefined",
  },
});

// --- chrome.history.onVisited --------------------------------------------------------
// Hypothesis: fires with a usable URL under the "history" permission alone, with no host
// permissions. If true, Tise never needs to be able to read a page.
if (chrome.history?.onVisited) {
  chrome.history.onVisited.addListener(async (item) => {
    await record({
      kind: "history.onVisited",
      urlPresent: typeof item.url === "string" && item.url.length > 0,
      // Host only. The spike must not persist a full URL any more than the product would.
      host: item.url ? new URL(item.url).host : null,
      titlePresent: typeof item.title === "string",
      fields: Object.keys(item).sort(),
    });

    // The duration trap, tested rather than recalled: dump the exact keys the API
    // returns for a visit and confirm no duration field is among them.
    if (chrome.history.getVisits && item.url) {
      try {
        const visits = await chrome.history.getVisits({ url: item.url });
        const last = visits[visits.length - 1];
        if (last) {
          await record({
            kind: "history.getVisits",
            visitItemFields: Object.keys(last).sort(),
            hasTransition: "transition" in last,
            hasAnyDurationField: Object.keys(last).some((k) =>
              /duration|dwell|elapsed/i.test(k),
            ),
            transition: last.transition ?? null,
          });
        }
      } catch (error) {
        await record({ kind: "history.getVisits.error", message: String(error) });
      }
    }
  });
}

// --- chrome.webNavigation.onCommitted -------------------------------------------------
// Hypothesis: without host permissions the event may not fire, or may arrive with the
// URL redacted. This is the claim audit finding 7 rests on, so it gets measured.
if (chrome.webNavigation?.onCommitted) {
  chrome.webNavigation.onCommitted.addListener(async (details) => {
    if (details.frameId !== 0) return; // top-level navigations only
    await record({
      kind: "webNavigation.onCommitted",
      urlPresent: typeof details.url === "string" && details.url.length > 0,
      host: details.url ? new URL(details.url).host : null,
      transitionType: details.transitionType ?? null,
      transitionQualifiers: details.transitionQualifiers ?? null,
      fields: Object.keys(details).sort(),
    });
  });
}
