import { describe, expect, it } from "vitest";
import { normaliseNavigation, type NavigationDetails } from "../src/collect/normalise";

function nav(overrides: Partial<NavigationDetails> = {}): NavigationDetails {
  return {
    url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    frameId: 0,
    timeStamp: Date.parse("2026-08-26T09:15:00.000Z"),
    transitionType: "link",
    transitionQualifiers: [],
    ...overrides,
  };
}

const ids = () => "fixed-id";

describe("normaliseNavigation", () => {
  it("builds an event with a domain, a category and nothing else", () => {
    const result = normaliseNavigation(nav(), { newId: ids });
    expect(result.ok).toBe(true);
    if (!result.ok) return;

    expect(result.event).toEqual({
      eventId: "fixed-id",
      occurredAt: "2026-08-26T09:15:00.000Z",
      source: "live",
      domain: "youtube.com",
      category: "video",
      transition: "link",
      dwellSeconds: null,
    });
  });

  it("never measures dwell, in either direction (D35)", () => {
    const result = normaliseNavigation(nav(), { newId: ids });
    expect(result.ok && result.event.dwellSeconds).toBeNull();
  });

  it("drops subframes — an iframe is not a navigation the person chose", () => {
    expect(normaliseNavigation(nav({ frameId: 3 }))).toEqual({
      ok: false,
      reason: "subframe",
    });
  });

  it("drops redirect hops, exactly as T1 dropped them from the history database", () => {
    expect(
      normaliseNavigation(nav({ transitionQualifiers: ["server_redirect"] })),
    ).toEqual({ ok: false, reason: "redirect" });
    expect(
      normaliseNavigation(nav({ transitionQualifiers: ["client_redirect"] })),
    ).toEqual({ ok: false, reason: "redirect" });
  });

  it("keeps a navigation that merely came from the address bar", () => {
    const result = normaliseNavigation(
      nav({ transitionType: "typed", transitionQualifiers: ["from_address_bar"] }),
      { newId: ids },
    );
    expect(result.ok).toBe(true);
    expect(result.ok && result.event.transition).toBe("typed");
  });

  it("drops anything that is not web browsing", () => {
    expect(normaliseNavigation(nav({ url: "chrome://settings" }))).toEqual({
      ok: false,
      reason: "not-web",
    });
    expect(normaliseNavigation(nav({ url: "file:///C:/Users/a/notes.txt" }))).toEqual({
      ok: false,
      reason: "not-web",
    });
  });

  it("applies user overrides while normalising", () => {
    const result = normaliseNavigation(nav(), {
      newId: ids,
      overrides: { "youtube.com": "learning" },
    });
    expect(result.ok && result.event.category).toBe("learning");
  });

  it("resolves an unmapped domain to unknown rather than dropping the event", () => {
    const result = normaliseNavigation(nav({ url: "https://a-site-nobody-mapped.example/x" }), {
      newId: ids,
    });
    expect(result.ok && result.event.category).toBe("unknown");
    expect(result.ok && result.event.domain).toBe("a-site-nobody-mapped.example");
  });
});
