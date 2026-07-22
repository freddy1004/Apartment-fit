// Optional browser end-to-end test (Playwright).
//
// Requires the full stack running:
//   docker compose up          # or backend on :8000 + `npm run dev` on :3000
//   npx playwright install chromium
//   npx playwright test
//
// It is intentionally not part of `npm test` (which runs fast unit tests) so the
// unit suite stays hermetic. This validates the real UI journey end to end.
import { expect, test } from "@playwright/test";

const BASE = process.env.E2E_BASE_URL || "http://localhost:3000";

test("seed demo, analyze, and see qualifying areas", async ({ page }) => {
  await page.goto(BASE);
  await page.getByRole("button", { name: /Seed Seattle demo/i }).first().click();

  // Analysis summary appears once the run completes.
  await expect(page.getByText(/search zones/i)).toBeVisible({ timeout: 30000 });
  await expect(page.getByText(/Which criteria eliminate/i)).toBeVisible();

  // Switch to listings and add one by address.
  await page.getByText("Listings", { exact: true }).click();
  await page.getByPlaceholder(/Green Lake/i).fill("Green Lake, Seattle");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await expect(page.getByText(/Green Lake/i)).toBeVisible({ timeout: 15000 });
});
