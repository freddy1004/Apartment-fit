import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // Unit tests only; the Playwright browser E2E lives in ./e2e and runs via
    // `npx playwright test`, not vitest.
    include: ["lib/**/*.test.ts", "components/**/*.test.ts"],
    exclude: ["e2e/**", "node_modules/**"],
  },
});
