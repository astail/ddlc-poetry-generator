import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@testing-library/jest-dom/vitest";

import Gallery from "../app/gallery/page";
import { LangProvider } from "../app/i18n";

type Init = { method?: string } | undefined;

const SAMPLE = [
  {
    id: 1,
    character: "monika",
    title: "Reality",
    title_ja: "現実",
    mood: "calm",
    image_status: "done",
    image_url: "/api/assets/images/1.png",
  },
  {
    id: 2,
    character: "sayori",
    title: "Sunshine",
    title_ja: "陽だまり",
    mood: null,
    image_status: "pending",
    image_url: null,
  },
];

function renderGallery() {
  return render(
    <LangProvider initialLang="en">
      <Gallery />
    </LangProvider>,
  );
}

describe("Gallery delete flow", () => {
  beforeEach(() => {
    // List returns the two sample poems; DELETE succeeds (204).
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_input: unknown, init: Init) => {
        if (init?.method === "DELETE") return { ok: true, status: 204 };
        return { ok: true, status: 200, json: async () => SAMPLE };
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("removes a card after the user confirms deletion", async () => {
    vi.stubGlobal("confirm", vi.fn(() => true));
    renderGallery();

    expect(await screen.findByText("Reality")).toBeInTheDocument();
    expect(screen.getByText("Sunshine")).toBeInTheDocument();

    const delButtons = screen.getAllByRole("button", { name: /delete/i });
    fireEvent.click(delButtons[0]);

    await waitFor(() => {
      expect(screen.queryByText("Reality")).not.toBeInTheDocument();
    });
    // The un-deleted poem stays on the page.
    expect(screen.getByText("Sunshine")).toBeInTheDocument();
  });

  it("keeps the card when the user cancels the confirm dialog", async () => {
    const confirmMock = vi.fn(() => false);
    vi.stubGlobal("confirm", confirmMock);
    renderGallery();

    expect(await screen.findByText("Reality")).toBeInTheDocument();

    const delButtons = screen.getAllByRole("button", { name: /delete/i });
    fireEvent.click(delButtons[0]);

    expect(confirmMock).toHaveBeenCalledOnce();
    // Cancelled → still present.
    expect(screen.getByText("Reality")).toBeInTheDocument();
  });
});
