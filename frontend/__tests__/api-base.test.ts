import { afterEach, describe, expect, it, vi } from "vitest";

// API_BASE is computed once at module load from NEXT_PUBLIC_* + window, so each
// case stubs the environment and re-imports the module fresh.
async function loadApiBase(): Promise<string> {
  const mod = await import("../app/api-base");
  return mod.API_BASE;
}

describe("API_BASE resolution", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("uses an explicit NEXT_PUBLIC_API_BASE when set", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE", "https://api.example.test:9000");
    vi.resetModules();
    expect(await loadApiBase()).toBe("https://api.example.test:9000");
  });

  it("derives from the page host when no base is set (LAN access)", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE", "");
    vi.stubEnv("NEXT_PUBLIC_API_PORT", "8000");
    vi.stubGlobal("window", {
      location: { protocol: "http:", hostname: "192.168.10.200" },
    });
    vi.resetModules();
    expect(await loadApiBase()).toBe("http://192.168.10.200:8000");
  });

  it("falls back to localhost during SSR (no window)", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE", "");
    vi.stubGlobal("window", undefined);
    vi.resetModules();
    expect(await loadApiBase()).toBe("http://localhost:8000");
  });
});
