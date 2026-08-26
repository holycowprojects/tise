// Tise permission spike — THROWAWAY CODE. Deleted at the end of T5.
//
// Answers three questions:
//   1. What is the smallest permission set that lets Tise learn a navigation's URL?
//   2. Can `history` be requested at runtime, after the user clicks, rather than at
//      install? (If so, Tise installs with no warning and no capability at all.)
//   3. What does it actually take to read a person's WHOLE history — the documented
//      defaults truncate hard and do so silently.
//
// The original design documents shipped a manifest that could not have collected
// anything (audit finding 7), so nothing here is assumed.

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

record({
  kind: "manifest",
  variant: MANIFEST.name,
  permissions: MANIFEST.permissions ?? [],
  optionalPermissions: MANIFEST.optional_permissions ?? [],
  hostPermissions: MANIFEST.host_permissions ?? [],
  apisPresent: {
    history: typeof chrome.history !== "undefined",
    webNavigation: typeof chrome.webNavigation !== "undefined",
    tabs: typeof chrome.tabs !== "undefined",
    alarms: typeof chrome.alarms !== "undefined",
    offscreen: typeof chrome.offscreen !== "undefined",
  },
});

// --- live collection -----------------------------------------------------------------

function attachHistoryListener() {
  if (!chrome.history?.onVisited || attachHistoryListener.done) return;
  attachHistoryListener.done = true;

  chrome.history.onVisited.addListener(async (item) => {
    await record({
      kind: "history.onVisited",
      urlPresent: typeof item.url === "string" && item.url.length > 0,
      // Host only. The spike stores no more than the product would.
      host: item.url ? new URL(item.url).host : null,
      fields: Object.keys(item).sort(),
    });

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

function attachNavigationListener() {
  if (!chrome.webNavigation?.onCommitted || attachNavigationListener.done) return;
  attachNavigationListener.done = true;

  chrome.webNavigation.onCommitted.addListener(async (details) => {
    if (details.frameId !== 0) return;
    await record({
      kind: "webNavigation.onCommitted",
      urlPresent: typeof details.url === "string" && details.url.length > 0,
      host: details.url ? new URL(details.url).host : null,
      transitionType: details.transitionType ?? null,
      fields: Object.keys(details).sort(),
    });
  });
}

attachHistoryListener();
attachNavigationListener();

// Granting an optional permission mid-session should make the API appear. Whether a
// listener can then be attached without reloading the extension is a real unknown, and
// T7's first-run import depends on the answer.
chrome.permissions?.onAdded?.addListener(async (granted) => {
  await record({ kind: "permissions.onAdded", granted: granted.permissions ?? [] });
  attachHistoryListener();
  attachNavigationListener();
});

chrome.permissions?.onRemoved?.addListener(async (removed) => {
  await record({ kind: "permissions.onRemoved", removed: removed.permissions ?? [] });
});

// --- the import probe ----------------------------------------------------------------
// chrome.history.search has two defaults that truncate silently:
//   startTime  -> last 24 hours
//   maxResults -> 100
// Called the obvious way it returns a hundred rows from yesterday and looks like it
// worked. This measures each variation so T7 cannot inherit the mistake.

async function probeImport() {
  if (!chrome.history?.search) {
    await record({ kind: "import.unavailable" });
    return { error: "history API not available" };
  }

  const attempts = [
    { label: "defaults", query: { text: "" } },
    { label: "startTime=0", query: { text: "", startTime: 0 } },
    { label: "startTime=0,maxResults=0", query: { text: "", startTime: 0, maxResults: 0 } },
    {
      label: "startTime=0,maxResults=1e6",
      query: { text: "", startTime: 0, maxResults: 1000000 },
    },
  ];

  const results = [];
  for (const attempt of attempts) {
    try {
      const items = await chrome.history.search(attempt.query);
      const times = items.map((i) => i.lastVisitTime).filter(Boolean);
      results.push({
        label: attempt.label,
        count: items.length,
        oldest: times.length ? new Date(Math.min(...times)).toISOString() : null,
        spanDays: times.length
          ? (Math.max(...times) - Math.min(...times)) / 86400000
          : 0,
      });
    } catch (error) {
      results.push({ label: attempt.label, error: String(error) });
    }
  }

  // `search` returns PAGES, one row per URL with a visitCount. The label pipeline is
  // visit-based — sessions come from individual timestamps — so a real backfill needs
  // getVisits() per URL on top. That fan-out is what decides whether importing a whole
  // history is practical or has to be chunked across many wake-ups, so it is measured
  // rather than guessed at.
  let fanOut = null;
  try {
    const pages = await chrome.history.search({
      text: "",
      startTime: 0,
      maxResults: 1000000,
    });
    const sample = pages.slice(0, 200);
    const started = performance.now();
    let visitTotal = 0;
    for (const page of sample) {
      const visits = await chrome.history.getVisits({ url: page.url });
      visitTotal += visits.length;
    }
    const elapsed = performance.now() - started;

    const claimed = pages.reduce((sum, p) => sum + (p.visitCount ?? 0), 0);
    fanOut = {
      pageCount: pages.length,
      sampled: sample.length,
      visitsInSample: visitTotal,
      msPerPage: sample.length ? elapsed / sample.length : 0,
      // Extrapolated only to show the order of magnitude, never used as a result.
      projectedVisits: sample.length
        ? Math.round((visitTotal / sample.length) * pages.length)
        : 0,
      projectedSeconds: sample.length
        ? Math.round((elapsed / sample.length) * pages.length) / 1000
        : 0,
      visitCountSumFromSearch: claimed,
    };
  } catch (error) {
    fanOut = { error: String(error) };
  }

  await record({ kind: "import.probe", results, fanOut });
  return { results, fanOut };
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "runImportProbe") {
    probeImport().then(sendResponse);
    return true; // async response
  }
  return false;
});
