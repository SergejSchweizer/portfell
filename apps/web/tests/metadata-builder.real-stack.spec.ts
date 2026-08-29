import { expect, test } from "@playwright/test";

test("a user completes the real four-module research workflow", async ({ page }) => {
  test.setTimeout(240_000);

  await page.goto("/metadata-builder");
  const createProject = page.getByRole("button", { name: "Create new project" });
  await expect(createProject).toBeDisabled();

  await page.getByLabel("EODHD key").fill("e2e-operations-token");
  await page.getByRole("button", { name: "Fetch all metadata" }).click();

  await expect(page.getByText("5 metadata rows from 1 exchanges loaded.")).toBeVisible({ timeout: 30_000 });
  await expect(createProject).toBeEnabled();

  await page.getByLabel("Exchange").selectOption("XETRA");
  await page.getByLabel("Instrument type").selectOption("ETF");
  await page.getByLabel("Country").selectOption("Germany");
  await page.getByLabel("Currency").selectOption("EUR");
  await page.getByLabel("Name contains").fill("UCITS ETF");
  await createProject.click();

  await expect(page.getByText("5 unique ISINs selected.")).toBeVisible();
  await expect(page.getByRole("button", { name: /Preparing historical data|Loading quotes:/ })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Quotes ready - Create new project" })).toBeEnabled({ timeout: 90_000 });

  await page.getByRole("link", { name: /Univariate Statistics/ }).click();
  const computeUnivariate = page.getByRole("button", { name: "Compute univariate statistics" });
  await expect(computeUnivariate).toBeEnabled();
  await computeUnivariate.click();
  await expect(page.getByRole("button", { name: "Computing…" })).toBeDisabled();
  await expect(page.getByText("5 listings restored.")).toBeVisible({ timeout: 60_000 });
  await expect(computeUnivariate).toBeEnabled();
  await page.getByRole("tab", { name: "Dividends" }).click();
  const dividendSelection = page.locator(
    ".univariate-statistics-page .portfolio-selection select",
  );
  const selectionSaved = page.waitForResponse((response) => (
    response.request().method() === "PUT"
      && response.url().includes("/univariate-selection-settings")
      && response.ok()
  ));
  await dividendSelection.selectOption(["monthly"]);
  await selectionSaved;
  await expect(dividendSelection).toHaveValues(["monthly"]);

  await page.getByRole("link", { name: /Bivariate Statistics/ }).click();
  const computeBivariate = page.getByRole("button", { name: "Compute Bivariate Statistics" });
  await expect(computeBivariate).toBeEnabled();
  await computeBivariate.click();
  await expect(page.getByRole("button", { name: "Computing…" })).toBeDisabled();
  await expect(page.getByRole("tab", { name: "Covariance" })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole("button", { name: "Recompute Bivariate Statistics" })).toBeEnabled();

  await page.getByRole("link", { name: /Multivariate Statistics/ }).click();
  const computeMultivariate = page.getByRole("button", { name: "Compute multivariate statistics" });
  await expect(computeMultivariate).toBeEnabled();
  await computeMultivariate.click();
  await expect(page.getByRole("button", { name: "Computing…" })).toBeDisabled();
  await expect(page.getByRole("table", { name: "Portfolio overview metrics" })).toBeVisible({ timeout: 90_000 });
  await expect(computeMultivariate).toBeEnabled();
});
