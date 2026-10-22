import { describe, expect, it } from "vitest";

import { FAQS, FEATURES, NAV, PHOTOS, ROLES, SECTION_IDS, unsplash } from "./content";

describe("unsplash", () => {
  it("builds an Unsplash address with the size and the keywords", () => {
    const url = new URL(unsplash("123-abc", "doctor-phone", 800));
    expect(url.origin).toBe("https://images.unsplash.com");
    expect(url.pathname).toBe("/photo-123-abc");
    expect(url.searchParams.get("w")).toBe("800");
    expect(url.searchParams.get("keywords")).toBe("doctor-phone");
  });
});

describe("site content", () => {
  it("only links the menu to sections that exist", () => {
    const ids: readonly string[] = SECTION_IDS;
    for (const item of NAV) {
      expect(ids).toContain(item.href.slice(1));
    }
  });

  it("describes every photo for screen readers", () => {
    const photos = [...Object.values(PHOTOS), ...ROLES.map((role) => role.photo)];
    for (const photo of photos) {
      expect(photo.alt.trim()).not.toBe("");
      // next.config.js only allows this host
      expect(new URL(photo.src).hostname).toBe("images.unsplash.com");
    }
  });

  it("has no repeated feature titles or questions", () => {
    expect(new Set(FEATURES.map((f) => f.title)).size).toBe(FEATURES.length);
    expect(new Set(FAQS.map((f) => f.question)).size).toBe(FAQS.length);
  });
});
