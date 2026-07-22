import { defineConfig } from "@playwright/test";

// Optional E2E config. Install with: npm i -D @playwright/test && npx playwright install chromium
export default defineConfig({
  testDir: "./e2e",
  timeout: 60000,
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:3000",
    headless: true,
  },
});
