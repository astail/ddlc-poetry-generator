import { describe, expect, it } from "vitest";

import { THEME_POOL, langName, pickThemeSuggestions, type StringKey } from "../app/i18n";

describe("pickThemeSuggestions", () => {
  it("returns the requested number of distinct themes", () => {
    const picks = pickThemeSuggestions("en", 10);
    expect(picks).toHaveLength(10);
    expect(new Set(picks).size).toBe(10);
  });

  it("only returns members of the requested language pool", () => {
    const pool = new Set(THEME_POOL.ja);
    for (const p of pickThemeSuggestions("ja", 8)) {
      expect(pool.has(p)).toBe(true);
    }
  });

  it("clamps the count to the pool size instead of looping forever", () => {
    const picks = pickThemeSuggestions("en", 10_000);
    expect(picks).toHaveLength(THEME_POOL.en.length);
    expect(new Set(picks).size).toBe(THEME_POOL.en.length);
  });
});

describe("THEME_POOL", () => {
  it("keeps the en / ja arrays index-aligned (same length)", () => {
    expect(THEME_POOL.en).toHaveLength(THEME_POOL.ja.length);
  });

  it("has no duplicate words within a language", () => {
    expect(new Set(THEME_POOL.en).size).toBe(THEME_POOL.en.length);
    expect(new Set(THEME_POOL.ja).size).toBe(THEME_POOL.ja.length);
  });
});

describe("langName", () => {
  const t = (k: StringKey): string => (k === "poem.langJa" ? "日本語" : "English");

  it("names the content language in the active UI language", () => {
    expect(langName(t, "ja")).toBe("日本語");
    expect(langName(t, "en")).toBe("English");
  });

  it("treats an unknown content language as English", () => {
    expect(langName(t, "fr")).toBe("English");
  });
});
