import { expect, test } from "@playwright/test";

const workflow = {
  stages: {
    metadata_filter: { status: "complete", metadata_selection_id: "metadata-1", quote_run_id: "quote-1" },
    univariate_statistics: { status: "complete", univariate_run_id: "univariate-1" },
    univariate_filter: { status: "complete", univariate_filter_selection_id: "filter-1" },
    bivariate_statistics: { status: "ready" },
  },
};

async function installWorkflowApi(page: import("@playwright/test").Page) {
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body: unknown) => route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    if (request.method() === "GET" && path === "/api/project-context") return json({ current_project_id: "project-1", current_project: { project_id: "project-1", name: "Workflow test" }, projects: [{ project_id: "project-1", name: "Workflow test", selected_count: 2, data_loaded: true }] });
    if (request.method() === "GET" && (path === "/api/workflow" || path === "/api/projects/project-1/workflow")) return json(workflow);
    if (request.method() === "GET" && path === "/api/metadata-filter/options") return json({ exchange: ["XETRA"], instrument_type: ["ETF"], country: ["IE"], currency: ["EUR"] });
    if (request.method() === "GET" && path === "/api/univariate-filter/metrics") return json({ items: [{ metric: "annualized_volatility", label: "Annualized volatility" }] });
    if (request.method() === "POST" && path === "/api/credentials/eodhd") return json({ status: "active" });
    if (request.method() === "POST" && path === "/api/metadata/fetch-all") return json({ status: "succeeded", row_count: 2, exchange_count: 1, requested_exchange_count: 1, skipped_exchange_count: 0, skipped_exchanges: [] });
    if (request.method() === "POST" && path === "/api/metadata-filter") return json({ project: { project_id: "project-1" }, selection: { selection_id: "metadata-1" }, selected_count: 2 });
    if (request.method() === "POST" && path === "/api/quote-runs") return json({ status: "complete", quote_successes: 2, quote_errors: 0, selected_listing_count: 2 });
    if (request.method() === "POST" && path === "/api/univariate-statistics/runs") return json({ run_id: "univariate-1", status: "complete", percent: 100 });
    if (request.method() === "GET" && path.includes("/univariate-statistics/runs/")) return json({ items: [], total: 0 });
    if (request.method() === "POST" && path === "/api/univariate-filter") return json({ selection_id: "filter-1", input_count: 2, selected_count: 2, excluded_count: 0 });
    if (request.method() === "GET" && path.includes("/univariate-filter/filter-1/results")) return json({ items: [], total: 0 });
    if (request.method() === "POST" && path === "/api/bivariate-statistics/plan") return json({ allowed: true, theoretical_pair_count: 1, pair_limit: 100 });
    if (request.method() === "POST" && path === "/api/bivariate-statistics/runs") return json({ run_id: "bivariate-1", status: "complete", percent: 100 });
    if (request.method() === "GET" && path.includes("/bivariate-statistics/runs/")) return json({ items: [], total: 0 });
    throw new Error(`Unhandled UI request: ${request.method()} ${path}`);
  });
}

test("research workflow exercises every current field and action sequentially", async ({ page }) => {
  await installWorkflowApi(page);
  await page.goto("/metadata-filter");
  await page.getByLabel("EODHD key").fill("test-key");
  await page.getByRole("button", { name: "Fetch all metadata" }).click();
  await page.getByLabel("Exchange").selectOption("XETRA");
  await page.getByLabel("Instrument type").selectOption("ETF");
  await page.getByLabel("Country").selectOption("IE");
  await page.getByLabel("Currency").selectOption("EUR");
  await page.getByLabel("Name contains").fill("UCITS");
  await page.getByRole("button", { name: "Apply metadata filter" }).click();
  await page.getByRole("button", { name: "Fetch quotes" }).click();

  await page.goto("/univariate-statistics");
  await page.getByRole("button", { name: "Compute univariate statistics" }).click();

  await page.goto("/univariate-filter");
  await page.getByLabel("Metric").selectOption("annualized_volatility");
  await page.getByLabel("Operator").selectOption("<=");
  await page.getByLabel("Value").fill("0.2");
  await page.getByRole("button", { name: "Add predicate" }).click();
  await page.getByRole("button", { name: "Remove" }).last().click();
  await page.getByRole("button", { name: "Apply filter" }).click();

  await page.goto("/bivariate-statistics");
  await page.getByRole("button", { name: "Plan pairs" }).click();
  await page.getByRole("button", { name: "Compute bivariate statistics" }).click();
  await expect(page.getByText("1 pair rows computed.")).toBeVisible();
});
