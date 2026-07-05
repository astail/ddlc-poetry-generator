import { describe, expect, it } from "vitest";

import { DEFAULT_LANG, resolveLang } from "../app/i18n-config";

describe("resolveLang", () => {
  it("passes through supported languages", () => {
    expect(resolveLang("en")).toBe("en");
    expect(resolveLang("ja")).toBe("ja");
  });

  it("falls back to the default for unknown / empty / nullish values", () => {
    expect(resolveLang("fr")).toBe(DEFAULT_LANG);
    expect(resolveLang("")).toBe(DEFAULT_LANG);
    expect(resolveLang(null)).toBe(DEFAULT_LANG);
    expect(resolveLang(undefined)).toBe(DEFAULT_LANG);
  });

  it("defaults to Japanese", () => {
    expect(DEFAULT_LANG).toBe("ja");
  });
});
