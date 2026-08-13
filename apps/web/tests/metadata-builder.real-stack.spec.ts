import { expect, test } from "@playwright/test";

test("Fetch all metadata uses the real API, worker, PostgreSQL, and shared catalogue", async ({ page }) => {
  await page.goto("/metadata-builder");
  await expect(page.getByRole("button", { name: "Create new project" })).toBeDisabled();
  await page.getByLabel("EODHD key").fill("e2e-operations-token");
  await page.getByRole("button", { name: "Fetch all metadata" }).click();

  await expect(page.getByText("1 metadata rows from 1 exchanges loaded.")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("button", { name: "Create new project" })).toBeEnabled();
  await expect(page.getByLabel("Exchange")).toHaveValue("");
  await expect(page.getByLabel("Exchange").locator("option", { hasText: "XETRA" })).toHaveCount(1);
});
