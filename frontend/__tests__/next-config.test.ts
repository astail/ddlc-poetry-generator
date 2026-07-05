import { describe, expect, it } from "vitest";

import nextConfig from "../next.config.mjs";

describe("next.config security headers (#118)", () => {
  it("applies the security headers to every route", async () => {
    const rules = (await nextConfig.headers?.()) ?? [];
    expect(rules.length).toBeGreaterThan(0);

    const rule = rules[0];
    expect(rule.source).toBe("/:path*");

    const keys = rule.headers.map((h) => h.key);
    for (const k of [
      "X-Content-Type-Options",
      "X-Frame-Options",
      "Referrer-Policy",
      "Content-Security-Policy",
    ]) {
      expect(keys).toContain(k);
    }

    const nosniff = rule.headers.find((h) => h.key === "X-Content-Type-Options");
    expect(nosniff?.value).toBe("nosniff");
  });
});
