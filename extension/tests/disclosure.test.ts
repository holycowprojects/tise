/**
 * T15 — the privacy disclosure cannot drift from the extension it describes.
 *
 * This project has shipped the "right words about a system that has moved" defect twice:
 * T18b found the README listing a local Python service that was explicitly rejected, and
 * D98 found `reports.py` labelling twelve benchmarks with a target retired two decisions
 * earlier. An onboarding page is the worst place for it, because its whole job is to be
 * believed *before* the reader can check anything.
 *
 * So every assertion here runs in **both directions**. A permission with no explanation
 * fails; an explanation for a permission no longer requested fails too. A one-directional
 * check would let a removed permission keep its paragraph, which reads as an extension
 * asking for more than it does — the mirror of the dangerous case, and still a lie.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  CAPABILITIES,
  NEVER_REQUESTED,
  NEVER_STORED,
  STORED_FIELDS,
  describeCapabilities,
  storedFields,
} from "../src/model/disclosure";
import { EVENT_FIELDS } from "../src/types";

const manifest = JSON.parse(
  readFileSync(fileURLToPath(new URL("../manifest.json", import.meta.url)), "utf8"),
) as { permissions: string[]; optional_permissions: string[] };

const declared = [...manifest.permissions, ...manifest.optional_permissions];

describe("capabilities are explained, both ways", () => {
  it("explains every permission the manifest actually requests", () => {
    for (const permission of declared) {
      expect(
        CAPABILITIES[permission],
        `the manifest requests "${permission}" and no explanation exists for it`,
      ).toBeDefined();
    }
  });

  it("explains nothing the manifest does not request", () => {
    for (const permission of Object.keys(CAPABILITIES)) {
      expect(
        declared,
        `"${permission}" is explained but no longer requested — a stale paragraph claims ` +
          "access the extension does not have",
      ).toContain(permission);
    }
  });

  it("splits required from optional exactly as the manifest does", () => {
    const described = describeCapabilities(manifest);
    expect(described.required.map((c) => c.permission)).toEqual(manifest.permissions);
    expect(described.optional.map((c) => c.permission)).toEqual(
      manifest.optional_permissions,
    );
  });

  it("throws rather than skipping a permission it has no words for", () => {
    // The behaviour that matters. Silently omitting an unknown permission would produce a
    // disclosure with a hole in it, invisible precisely where it counts.
    expect(() => describeCapabilities({ permissions: ["cookies"] })).toThrow(
      /no plain-language explanation/,
    );
  });

  it("tells an optional permission's decliner what saying no costs", () => {
    // D33: Chrome focuses Deny. A person deciding needs the price of "no", not only of
    // "yes", and required permissions have no such choice to describe.
    for (const capability of describeCapabilities(manifest).optional) {
      expect(capability.costOfDeclining.length, capability.permission).toBeGreaterThan(20);
    }
    for (const capability of describeCapabilities(manifest).required) {
      expect(capability.costOfDeclining, capability.permission).toBe("");
    }
  });

  it("says what each permission does *not* allow, which is the part that reassures", () => {
    for (const capability of Object.values(CAPABILITIES)) {
      expect(capability.allows.length, capability.permission).toBeGreaterThan(20);
      expect(capability.doesNotAllow.length, capability.permission).toBeGreaterThan(20);
      expect(capability.title.length, capability.permission).toBeGreaterThan(5);
    }
  });
});

describe("the not-requested list is enforced, not decorative", () => {
  it("names nothing the manifest actually requests", () => {
    // If this ever fails, the page is telling the reader Tise does not do something it
    // does. That is the one failure mode worse than saying nothing.
    for (const [permission] of NEVER_REQUESTED) {
      expect(declared, `"${permission}" is both promised-absent and requested`).not.toContain(
        permission,
      );
    }
  });

  it("covers every permission `manifest.test.ts` asserts absent", () => {
    // The two lists are the same claim in two places, and only one of them is shown to a
    // person. This pins them together so a permission cannot be added to the guard while
    // the page carries on not mentioning it.
    const guard = readFileSync(
      fileURLToPath(new URL("./manifest.test.ts", import.meta.url)),
      "utf8",
    );
    const forbidden = guard
      .slice(guard.indexOf("for (const forbidden of ["))
      .slice(0, guard.slice(guard.indexOf("for (const forbidden of [")).indexOf("]"));

    const named = new Set(NEVER_REQUESTED.map(([permission]) => permission));
    for (const match of forbidden.matchAll(/"([a-zA-Z]+)"/g)) {
      expect(
        named.has(match[1] ?? ""),
        `manifest.test.ts asserts "${match[1]}" is absent and the disclosure never says so`,
      ).toBe(true);
    }
  });

  it("gives a reason a person can act on, not just a permission name", () => {
    // Not "must not contain the permission name" — `bookmarks` and `topSites` are ordinary
    // English and "your bookmarks" is the right phrasing. What is forbidden is the entry
    // that restates the name and stops, which tells a reader nothing they did not have.
    for (const [permission, why] of NEVER_REQUESTED) {
      expect(why.length, permission).toBeGreaterThan(10);
      expect(why.trim().toLowerCase(), permission).not.toBe(permission.toLowerCase());
    }
  });
});

describe("stored fields are explained, both ways", () => {
  it("describes every field a stored event actually carries", () => {
    for (const field of EVENT_FIELDS) {
      expect(STORED_FIELDS[field], `TiseEvent carries "${field}" unexplained`).toBeDefined();
    }
  });

  it("describes no field an event does not carry", () => {
    for (const field of Object.keys(STORED_FIELDS)) {
      expect(EVENT_FIELDS as readonly string[], `"${field}" is not stored`).toContain(field);
    }
  });

  it("returns them in the canonical order, so the page cannot reorder the truth", () => {
    expect(storedFields().map(([field]) => field)).toEqual([...EVENT_FIELDS]);
  });

  it("never claims a URL, page content or credential is stored", () => {
    // The invariants, read back off the page that promises them.
    const promises = NEVER_STORED.join(" ").toLowerCase();
    expect(promises).toContain("address");
    expect(promises).toContain("contents");
    expect(promises).toContain("credential");
    expect(NEVER_STORED.length).toBeGreaterThanOrEqual(4);
  });

  it("does not describe `domain` as anything more than a bare site name", () => {
    // Invariant 2 in the words the reader sees. If `domain` ever starts carrying a path,
    // this sentence becomes false and someone has to change it deliberately.
    expect(STORED_FIELDS["domain"]).toMatch(/bare site name/);
    expect(STORED_FIELDS["domain"]).toMatch(/never the page/);
  });
});
