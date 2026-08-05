import { afterEach, describe, expect, it, vi } from "vitest";

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

// The browser calls /api/* on this server, which proxies to the api service —
// that is what keeps requests same-origin (no CORS) and lets the api container
// stay unpublished.
describe("next.config /api proxy", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  async function rewritesWith(apiOrigin?: string) {
    if (apiOrigin === undefined) {
      vi.stubEnv("API_ORIGIN", "");
    } else {
      vi.stubEnv("API_ORIGIN", apiOrigin);
    }
    vi.resetModules();
    const mod = await import("../next.config.mjs");
    const rules = (await mod.default.rewrites?.()) ?? [];
    // rewrites() may return the beforeFiles/afterFiles/fallback form; ours is a
    // plain list, and asserting that also narrows the union for TypeScript.
    if (!Array.isArray(rules)) throw new Error("expected a flat rewrite list");
    return rules;
  }

  it("proxies every /api path to the API, query strings included", async () => {
    const rules = await rewritesWith("http://api:8000");
    expect(rules).toHaveLength(1);
    expect(rules[0].source).toBe("/api/:path*");
    // :path* also covers nested asset paths (/api/assets/images/x.png).
    expect(rules[0].destination).toBe("http://api:8000/api/:path*");
  });

  it("takes the API origin by name from API_ORIGIN (read at build time)", async () => {
    const rules = await rewritesWith("http://some-other-api:9000");
    expect(rules[0].destination).toBe("http://some-other-api:9000/api/:path*");
  });

  it("falls back to localhost when API_ORIGIN is unset (local dev)", async () => {
    const rules = await rewritesWith();
    expect(rules[0].destination).toBe("http://localhost:8000/api/:path*");
  });

  it("allows a slow POST /api/generate to outlive the default proxy timeout", async () => {
    // Next cuts the upstream connection after 30s by default, which a poem
    // generation (synchronous Claude call + retries) exceeds — the API finishes
    // but the browser sees a 500 "socket hang up".
    expect(nextConfig.experimental?.proxyTimeout ?? 30_000).toBeGreaterThan(120_000);
  });
});
