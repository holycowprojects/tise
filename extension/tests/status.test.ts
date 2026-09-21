/**
 * The honesty panel, pinned to the code it describes.
 *
 * **This defect has already happened once.** Between D88 and D97 `reports.py` said the
 * project predicted `block_volume`, which D92 had retired, and eight generated reports told
 * readers so — right numbers, wrong frame, inside the module written to prevent exactly
 * that. Those were benchmark pages read by a handful of people. The dashboard says the same
 * kind of thing to whoever installs this, so the claim is pinned to `predict.ts` rather than
 * to my memory of what `predict.ts` says.
 *
 * `research/tise_research/reports.py` anchors to the same file from the other language, so
 * a change to the shipped target has to break something in both.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { TARGET } from "../src/model/predict";
import {
  PURCHASE_INTENT_NOTE,
  SHIPPED_TARGET,
  TARGET_STATUS,
  statusFor,
} from "../src/model/status";

const MANIFEST = JSON.parse(
  readFileSync(fileURLToPath(new URL("../manifest.json", import.meta.url)), "utf8"),
) as { options_ui?: { page?: string; open_in_tab?: boolean } };

describe("what the page says Tise ships", () => {
  it("matches what the extension actually trains", () => {
    expect(SHIPPED_TARGET).toBe(TARGET);
  });

  it("describes the shipped target rather than leaving it off the list", () => {
    // The awkward one: what ships is a target D88 retired. Omitting it would make the
    // page tidier and would be the single most misleading edit available.
    const shipped = statusFor(SHIPPED_TARGET);
    expect(shipped).not.toBeNull();
    expect(shipped?.state).toBe("retired");
  });

  it("claims exactly one withheld target, and it is not the shipped one", () => {
    // D124 moved `visit_engaged` from `adopted` to `withheld`. `adopted` describes a wait
    // and this is a decision: the model cleared its bar, the person's data does not clear
    // the data gate, and that gate is not closing (D123). Nothing is `adopted` any more,
    // because nothing is queued to ship.
    const withheld = TARGET_STATUS.filter((entry) => entry.state === "withheld");
    expect(withheld.map((entry) => entry.name)).toEqual(["visit_engaged"]);
    expect(withheld[0]?.name).not.toBe(SHIPPED_TARGET);
    expect(TARGET_STATUS.some((entry) => entry.state === "adopted")).toBe(false);
  });

  it("says why a withheld target is withheld, not merely that it is", () => {
    // A state with no reason beside it is the shape that lets a page claim something the
    // records have retired (D88-D97). The note has to carry the argument.
    const withheld = TARGET_STATUS.find((entry) => entry.state === "withheld");
    expect(withheld?.note).toMatch(/switched off|not reach|stays there/);
    expect(withheld?.note).toContain("D123");
  });

  it("claims nothing is both adopted and shipped yet", () => {
    // The state the whole page is honest about. When this test starts failing because
    // something is genuinely `shipped`, that is T-G4 landing, and the panel needs
    // rewriting rather than the test relaxing.
    expect(TARGET_STATUS.some((entry) => entry.state === "shipped")).toBe(false);
  });
});

describe("the list itself", () => {
  it("names every target without duplicates", () => {
    const names = TARGET_STATUS.map((entry) => entry.name);
    expect(new Set(names).size).toBe(names.length);
  });

  it("gives every target a question a person would actually ask", () => {
    for (const entry of TARGET_STATUS) {
      expect(entry.question.endsWith("?"), `${entry.name} question`).toBe(true);
      // Long enough to say the awkward part. A one-line note is how the frame goes wrong.
      expect(entry.note.length, `${entry.name} note`).toBeGreaterThan(60);
    }
  });

  it("returns null for a target nobody registered, rather than inventing one", () => {
    expect(statusFor("purchase_intent")).toBeNull();
  });

  it("keeps purchase intent off the list and explains the absence", () => {
    // D6 and T14 wanted it displayed with a "not evaluated" label. It is left out
    // instead: it could never move off that label, because confirming it means reading
    // checkout pages the privacy design forbids, and a permanent placeholder beside
    // measured numbers teaches the reader that the labels are decorative.
    expect(TARGET_STATUS.some((entry) => entry.name.includes("purchase"))).toBe(false);
    expect(PURCHASE_INTENT_NOTE).toContain("checkout");
  });
});

describe("the dashboard is reachable", () => {
  it("is registered as the options page and opens in a tab", () => {
    // Without this the page builds, ships and can only be reached by typing its URL.
    expect(MANIFEST.options_ui?.page).toBe("dashboard.html");
    expect(MANIFEST.options_ui?.open_in_tab).toBe(true);
  });
});
