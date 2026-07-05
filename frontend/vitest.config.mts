import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Vitest setup for the Next.js App Router frontend (#121). Mirrors the official
// Next.js guide: @vitejs/plugin-react for the JSX transform + jsdom for a DOM.
// tsconfig path aliases (@/*) resolve via Vite's native support.
export default defineConfig({
  plugins: [react()],
  resolve: { tsconfigPaths: true },
  test: {
    environment: "jsdom",
    globals: false,
    setupFiles: ["./vitest.setup.ts"],
    include: ["__tests__/**/*.{test,spec}.{ts,tsx}"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      include: ["app/**/*.{ts,tsx}"],
      // Layout / route shells are thin wiring; the logic under test lives in the
      // helpers and client components exercised above.
      exclude: ["app/**/layout.tsx", "app/**/*.d.ts"],
    },
  },
});
