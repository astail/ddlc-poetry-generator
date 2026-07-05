// Runs before each test file (see vitest.config.mts `setupFiles`).
// - registers @testing-library/jest-dom matchers on Vitest's `expect`
// - unmounts React trees between tests so they don't leak into each other
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import "@testing-library/jest-dom/vitest";

afterEach(() => {
  cleanup();
});
