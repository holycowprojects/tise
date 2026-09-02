/**
 * T15 — the first thing a person sees, and the only place consent is given knowingly.
 *
 * **Every factual claim on this page is rendered from `disclosure.ts`, not written in the
 * HTML.** The markup holds headings and argument; the lists holding permissions, stored
 * fields and never-requested capabilities are built here from data the test suite pins to
 * the manifest and to `EVENT_FIELDS`. A permission added without a plain-language
 * explanation fails the build rather than quietly going undisclosed.
 *
 * That split is the point. T18b found the README describing a component that never existed
 * and D98 found twelve reports naming a retired target — both hand-written statements about
 * a system that had moved. This page is the one artifact whose whole job is to be believed
 * before the reader can check anything, so nothing on it that can be derived is typed.
 *
 * `textContent` everywhere, never `innerHTML`: the T5 spike rendered `<all_urls>` as an HTML
 * tag and reported its own configuration wrongly.
 */
import { loadSettings, saveSettings } from "../../src/storage/settings";
import {
  NEVER_REQUESTED,
  NEVER_STORED,
  NO_HOST_ACCESS,
  describeCapabilities,
  storedFields,
} from "../../src/model/disclosure";
import type { Capability } from "../../src/model/disclosure";

function element(id: string): HTMLElement {
  const found = document.getElementById(id);
  if (!found) throw new Error(`missing element: ${id}`);
  return found;
}

function bullet(lead: string, rest: string): HTMLLIElement {
  const li = document.createElement("li");
  const strong = document.createElement("strong");
  strong.textContent = lead;
  li.append(strong, document.createTextNode(rest));
  return li;
}

/**
 * One permission, as three sentences: what it is, what it allows, what it does not.
 *
 * The third is not padding. Every Chrome permission grants more than any one extension
 * uses, and the gap between "what this permission can do" and "what Tise does with it" is
 * exactly what a careful reader wants and almost never gets.
 */
function capabilityBlock(capability: Capability, optional: boolean): HTMLElement {
  const wrapper = document.createElement("div");
  wrapper.style.marginTop = "14px";

  const title = document.createElement("h3");
  title.style.fontSize = "14px";
  title.textContent = capability.title;

  const tag = document.createElement("span");
  tag.className = "tag";
  tag.textContent = capability.permission;
  title.append(tag);

  const allows = document.createElement("p");
  allows.textContent = capability.allows;

  const not = document.createElement("p");
  not.className = "no";
  not.textContent = capability.doesNotAllow;

  wrapper.append(title, allows, not);

  if (optional && capability.costOfDeclining) {
    const cost = document.createElement("p");
    // D33 measured that Chrome focuses **Deny** on its permission dialog. Someone deciding
    // needs the price of "no" as plainly as the price of "yes", and an onboarding page that
    // only argues one way is a sales pitch.
    cost.textContent = `If you say no: ${capability.costOfDeclining}`;
    wrapper.append(cost);
  }
  return wrapper;
}

function renderDisclosure(): void {
  const manifest = chrome.runtime.getManifest() as {
    permissions?: string[];
    optional_permissions?: string[];
  };
  const capabilities = describeCapabilities(manifest);

  const required = element("required");
  for (const capability of capabilities.required) {
    required.append(capabilityBlock(capability, false));
  }

  const optional = element("optional");
  for (const capability of capabilities.optional) {
    optional.append(capabilityBlock(capability, true));
  }

  const stored = element("stored");
  for (const [field, description] of storedFields()) {
    stored.append(bullet(field, ` — ${description}`));
  }

  const neverStored = element("never-stored");
  for (const promise of NEVER_STORED) {
    const li = document.createElement("li");
    li.textContent = promise;
    neverStored.append(li);
  }

  element("no-host").textContent = NO_HOST_ACCESS;

  const neverRequested = element("never-requested");
  for (const [permission, why] of NEVER_REQUESTED) {
    neverRequested.append(bullet(permission, ` — ${why}`));
  }
}

/**
 * The state after consent, shown in place rather than by navigating away.
 *
 * Someone who has just agreed to something is exactly the person most likely to want to
 * re-read what they agreed to, and a page that replaces itself with a success screen takes
 * that away.
 */
async function renderState(): Promise<void> {
  const settings = await loadSettings();
  const start = element("start") as HTMLButtonElement;
  const later = element("later") as HTMLButtonElement;
  const done = element("done");
  const note = element("cta-note");

  if (settings.consentGrantedAt === null) {
    done.style.display = "none";
    start.textContent = "Start collecting";
    start.disabled = false;
    later.hidden = false;
    note.textContent = "You can stop, pause, or delete everything at any time.";
    return;
  }

  done.style.display = "block";
  element("done-detail").textContent =
    `Turned on ${new Date(settings.consentGrantedAt).toLocaleString()}. ` +
    "Everything above still applies, and this page stays where it is so you can re-read it.";
  start.textContent = "Already on";
  start.disabled = true;
  later.hidden = true;
  note.textContent =
    "Open Tise from the toolbar to pause it, or from its settings to delete everything.";
}

element("start").addEventListener("click", async () => {
  // The single moment consent is granted. `saveSettings` is the choke point that also
  // records the coverage transition, so nothing here has to remember to (D72).
  await saveSettings({ consentGrantedAt: new Date().toISOString(), paused: false });
  await renderState();
  window.scrollTo({ top: 0, behavior: "smooth" });
});

element("later").addEventListener("click", () => {
  // Closing without consenting leaves the extension exactly as installed: able to store
  // nothing. There is no "ask me later" flag, because a flag would be a stored fact about
  // a person who has not agreed to Tise storing facts about them.
  window.close();
});

renderDisclosure();
void renderState();
