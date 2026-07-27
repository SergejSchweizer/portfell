import { test, expect } from "@playwright/test";

test("login gate renders deterministically", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Sign in to continue" })).toBeVisible();
});

test("fixture preview exposes deterministic scenario catalog", async ({ page }) => {
  await page.goto("/fixtures?fixture=statistics-complete");
  await expect(page.getByRole("heading", { name: "Fixture preview" })).toBeVisible();
  await expect(page.getByText("statistics-complete")).toBeVisible();
});

test("component catalogue renders shared component states", async ({ page }) => {
  await page.goto("/catalogue");
  await expect(page.getByRole("heading", { name: "Component catalogue" })).toBeVisible();
});

test("authenticated shell renders a route frame and session boundary", async ({ page }) => {
  await page.goto("/shell?fixture=free-key");
  await expect(page.getByRole("heading", { name: "Authenticated Shell" })).toBeVisible();
  await expect(page.getByText("API boundary remains server-owned while React takes the shell.")).toBeVisible();
});

test("data metadata and univariate routes render shell pages", async ({ page }) => {
  await page.goto("/data?fixture=free-key");
  await expect(page.getByRole("heading", { name: "Load data" })).toBeVisible();

  await page.goto("/metadata?fixture=free-key");
  await expect(page.getByRole("heading", { name: "Project definition" })).toBeVisible();

  await page.goto("/univariate?fixture=statistics-complete");
  await expect(page.getByRole("heading", { name: "Univariate statistics" })).toBeVisible();
});

test("stress and recommendation placeholders are available", async ({ page }) => {
  await page.goto("/stress?fixture=stress-warning");
  await expect(page.getByRole("heading", { name: "Stress" })).toBeVisible();

  await page.goto("/recommendation?fixture=recommendation-ready");
  await expect(page.getByRole("heading", { name: "Recommendation" })).toBeVisible();
});
