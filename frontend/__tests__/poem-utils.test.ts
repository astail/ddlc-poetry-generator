import { describe, expect, it } from "vitest";

import { canVoiceLang, hasPendingAssets, isTerminal } from "../app/poem-utils";

describe("isTerminal", () => {
  it("treats done / failed as terminal", () => {
    expect(isTerminal("done")).toBe(true);
    expect(isTerminal("failed")).toBe(true);
  });

  it("treats queued / running / pending as non-terminal", () => {
    expect(isTerminal("queued")).toBe(false);
    expect(isTerminal("running")).toBe(false);
    expect(isTerminal("pending")).toBe(false);
  });
});

describe("hasPendingAssets", () => {
  it("is false when every asset is terminal", () => {
    expect(hasPendingAssets([{ status: "done" }, { status: "failed" }])).toBe(false);
  });

  it("is true when any asset is still in flight", () => {
    expect(hasPendingAssets([{ status: "done" }, { status: "running" }])).toBe(true);
  });

  it("is false for an empty asset list (nothing to poll)", () => {
    expect(hasPendingAssets([])).toBe(false);
  });
});

describe("canVoiceLang", () => {
  it("allows a language the backend reported as supported", () => {
    expect(canVoiceLang(["en", "ja"], "ja")).toBe(true);
    expect(canVoiceLang(["en"], "en")).toBe(true);
  });

  it("blocks a language the backend can't voice (e.g. ja on Piper)", () => {
    expect(canVoiceLang(["en"], "ja")).toBe(false);
    expect(canVoiceLang([], "en")).toBe(false);
  });
});
