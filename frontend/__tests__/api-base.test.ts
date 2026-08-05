import { afterEach, describe, expect, it, vi } from "vitest";

// API_BASE is computed once at module load from NEXT_PUBLIC_API_BASE, so each
// case stubs the environment and re-imports the module fresh.
async function loadApiBase(): Promise<string> {
  const mod = await import("../app/api-base");
  return mod.API_BASE;
}

describe("API_BASE resolution", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("is same-origin by default (this server proxies /api/* to the api service)", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE", "");
    vi.resetModules();
    // Relative URLs: they follow whatever host the page was loaded from
    // (localhost, a LAN IP, a hostname, a tunnel domain) with no CORS involved.
    expect(await loadApiBase()).toBe("");
  });

  it("uses an explicit NEXT_PUBLIC_API_BASE when set (bypasses the proxy)", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE", "https://api.example.test:9000");
    vi.resetModules();
    expect(await loadApiBase()).toBe("https://api.example.test:9000");
  });
});
