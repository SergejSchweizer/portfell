import { expect, test, type Page, type Route } from "@playwright/test";

type Project = {
  id: string;
  name: string;
  criteria: { exchange: string; instrument_type: string; country: string; currency: string; name: string };
  quoteRunId?: string;
  univariateRunId?: string;
  bivariateRunId?: string;
  settings: { dividend_frequencies: string[]; statistic_labels: Record<string, string[]>; statistic_ranges: Record<string, { minimum: number; maximum: number }[]> };
};

type WorkflowFixture = {
  calls: string[];
  projects: Map<string, Project>;
  settingsWrites: Map<string, number>;
};

const univariateRows = [
  { isin: "IE00ALPHA01", exchange: "XETRA", code: "ALPHA", quote_observation_count: 252, distribution_frequency: "monthly", annual_dividend_yield: 0.03, annualized_geometric_return: 0.09, annualized_volatility: 0.14, var: 0.02, sortino_ratio: 1.5, expected_shortfall: 0.03, tail_observation_count: 13, sharpe_ratio: 1.2, max_drawdown: -0.11, trend_r_squared: 0.82 },
  { isin: "IE00ALPHA02", exchange: "XETRA", code: "BETA", quote_observation_count: 252, distribution_frequency: "quarterly", annual_dividend_yield: 0.02, annualized_geometric_return: 0.07, annualized_volatility: 0.11, var: 0.015, sortino_ratio: 1.3, expected_shortfall: 0.025, tail_observation_count: 12, sharpe_ratio: 1.1, max_drawdown: -0.09, trend_r_squared: 0.78 },
  { isin: "IE00ALPHA03", exchange: "XETRA", code: "GAMMA", quote_observation_count: 252, distribution_frequency: "annual", annual_dividend_yield: 0.04, annualized_geometric_return: 0.11, annualized_volatility: 0.18, var: 0.03, sortino_ratio: 1.7, expected_shortfall: 0.04, tail_observation_count: 14, sharpe_ratio: 1.4, max_drawdown: -0.16, trend_r_squared: 0.88 },
] as const;

const labels = univariateRows.map((row) => ({ isin: row.isin, exchange: row.exchange, code: row.code, label: row.code }));
const matrix = [
  [null, 0.12, 0.08],
  [0.12, null, 0.06],
  [0.08, 0.06, null],
] as const;

function response(route: Route, body: unknown) {
  return route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
}

function workflow(project: Project | undefined) {
  if (!project) {
    return {
      stages: {
        metadata_builder: { status: "ready" },
        univariate_statistics: { status: "locked" },
        bivariate_statistics: { status: "locked" },
      },
      process_overview: { metadata_downloaded_isins: 4 },
    };
  }
  const quoteReady = Boolean(project.quoteRunId);
  const univariateReady = Boolean(project.univariateRunId);
  return {
    stages: {
      metadata_builder: { status: "complete", metadata_selection_id: `selection-${project.id}`, quote_run_id: project.quoteRunId },
      univariate_statistics: { status: univariateReady ? "complete" : quoteReady ? "ready" : "ready", univariate_run_id: project.univariateRunId, univariate_selection_id: univariateReady ? `univariate-selection-${project.id}` : undefined },
      bivariate_statistics: univariateReady ? { status: project.bivariateRunId ? "complete" : "ready", bivariate_run_id: project.bivariateRunId } : { status: "locked" },
    },
    process_overview: { metadata_downloaded_isins: 4, metadata_builder_isins: 3, univariate_statistics_isins: univariateReady ? 3 : null },
  };
}

function bivariateSummary() {
  const metric = { mean: 0.4, median: 0.4, minimum: 0.1, maximum: 0.7, histogram: [{ lower: 0, upper: 1, count: 3 }] };
  const diagnostics = { high_70_pairs: 1, high_90_pairs: 0, low_30_pairs: 1, negative_pairs: 0, percentile_10: 0.1, percentile_50: 0.4, percentile_90: 0.7, most_correlated_listing: "ALPHA", most_correlated_average: 0.6, best_diversifier_listing: "GAMMA", best_diversifier_average: 0.2 };
  return {
    pair_count: 3,
    observation_count: 252,
    metrics: { pearson_correlation: metric, spearman_correlation: metric, downside_correlation: metric, lower_tail_dependence: metric, tail_coexceedance_rate: metric, rolling_correlation_stability: metric, drawdown_overlap_rate: metric },
    pearson_diagnostics: diagnostics,
    spearman_diagnostics: { ...diagnostics, average_pearson_gap: 0.02, large_pearson_gap_pairs: 0, average_rolling_stability: 0.04, cluster_count: 1, largest_cluster_size: 3 },
    downside_diagnostics: { ...diagnostics, average_pearson_gap: 0.03, large_pearson_gap_pairs: 1, worst_pair: "ALPHA / BETA", worst_pair_correlation: 0.7, median_joint_negative_days: 28, minimum_joint_negative_days: 21, average_rolling_stability: 0.05, cluster_count: 1, largest_cluster_size: 3 },
  };
}

async function installTwoProjectApi(page: Page): Promise<WorkflowFixture> {
  const projects = new Map<string, Project>();
  const settingsWrites = new Map<string, number>();
  const calls: string[] = [];
  let currentProjectId: string | null = null;
  let metadataPolls = 0;

  const current = () => currentProjectId ? projects.get(currentProjectId) : undefined;
  const context = () => ({
    current_project_id: currentProjectId,
    current_project: currentProjectId ? projectSummary(projects.get(currentProjectId)!) : null,
    projects: [...projects.values()].map(projectSummary),
  });

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    calls.push(`${method} ${path}`);
    const body = method === "GET" ? {} : request.postDataJSON() as Record<string, unknown>;

    if (method === "GET" && path === "/api/credentials/eodhd") return response(route, { credential_id: "credential-1", provider: "eodhd", status: "active", key_version: "1", masked_label: "dummy…key" });
    if (method === "GET" && path === "/api/credentials/eodhd/value") return response(route, { provider_key: "" });
    if (method === "POST" && path === "/api/credentials/eodhd") return response(route, { status: "active" });
    if (method === "POST" && path === "/api/metadata/fetch-all") return response(route, { metadata_run_id: "metadata-run", status: "running", total: 1, completed: 0, percent: 0 });
    if (method === "GET" && path === "/api/metadata/fetch-all/metadata-run") {
      metadataPolls += 1;
      return response(route, { metadata_run_id: "metadata-run", status: metadataPolls === 1 ? "running" : "succeeded", total: 1, completed: metadataPolls === 1 ? 0 : 1, percent: metadataPolls === 1 ? 0 : 100, row_count: 4, exchange_count: 1, requested_exchange_count: 1, skipped_exchange_count: 0, skipped_exchanges: [] });
    }
    if (method === "GET" && path === "/api/metadata-builder/options") return response(route, { exchange: ["XETRA", "LSE"], instrument_type: ["ETF", "FUND"], country: ["IE", "LU"], currency: ["EUR", "USD"] });
    if (method === "GET" && path === "/api/project-context") return response(route, context());
    if (method === "PUT" && path === "/api/project-context/current-project") {
      currentProjectId = String(body.project_id);
      return response(route, context());
    }
    if (method === "GET" && path === "/api/workflow") return response(route, workflow(current()));
    const projectWorkflow = path.match(/^\/api\/projects\/([^/]+)\/workflow$/);
    if (method === "GET" && projectWorkflow) return response(route, workflow(projects.get(projectWorkflow[1])));
    const projectCriteria = path.match(/^\/api\/projects\/([^/]+)\/metadata-builder$/);
    if (method === "GET" && projectCriteria) {
      const project = projects.get(projectCriteria[1])!;
      return response(route, { project_id: project.id, selection_id: `selection-${project.id}`, selected_count: 3, ...project.criteria });
    }
    if (method === "POST" && path === "/api/metadata-builder") {
      const id = `project-${projects.size + 1}`;
      const project: Project = {
        id,
        name: String(body.name),
        criteria: { exchange: String(body.exchange), instrument_type: String(body.instrument_type), country: String(body.country), currency: String(body.currency), name: String(body.name) },
        settings: { dividend_frequencies: [], statistic_labels: {}, statistic_ranges: {} },
      };
      projects.set(id, project);
      currentProjectId = id;
      return response(route, { project: { project_id: id, name: project.name }, selection: { selection_id: `selection-${id}`, name: project.name }, selected_count: 3 });
    }
    const selectionSettings = path.match(/^\/api\/projects\/([^/]+)\/univariate-selection-settings$/);
    if (selectionSettings) {
      const project = projects.get(selectionSettings[1])!;
      if (method === "GET") return response(route, project.settings);
      if (method === "PUT") {
        project.settings = body as Project["settings"];
        settingsWrites.set(project.id, (settingsWrites.get(project.id) ?? 0) + 1);
        return response(route, project.settings);
      }
    }
    if (method === "POST" && path === "/api/quote-runs") {
      const project = current()!;
      project.quoteRunId = `quote-${project.id}`;
      return response(route, { download_run_id: project.quoteRunId, status: "running", total: 3, completed: 0, failed: 0, percent: 0, selected_listing_count: 3 });
    }
    if (method === "GET" && path.startsWith("/api/quote-runs/")) return response(route, { download_run_id: path.split("/").at(-1), status: "succeeded", total: 3, completed: 3, failed: 0, percent: 100, selected_listing_count: 3, quote_successes: 3, quote_errors: 0 });
    if (method === "POST" && path === "/api/univariate-statistics/runs") {
      const project = current()!;
      project.univariateRunId = `univariate-${project.id}`;
      return response(route, { run_id: project.univariateRunId, status: "running", total: 3, completed: 0, failed: 0, percent: 0 });
    }
    if (method === "GET" && /^\/api\/univariate-statistics\/runs\/[^/]+$/.test(path)) return response(route, { run_id: path.split("/").at(-1), status: "complete", total: 3, completed: 3, failed: 0, percent: 100 });
    if (method === "GET" && path.includes("/univariate-statistics/runs/") && path.endsWith("/results")) return response(route, { items: univariateRows, total: univariateRows.length, limit: 200, offset: 0 });
    if (method === "POST" && path === "/api/bivariate-statistics/plan") return response(route, { selected_listing_count: 3, theoretical_pair_count: 3, pair_limit: 100, allowed: true });
    if (method === "POST" && path === "/api/bivariate-statistics/runs") {
      const project = current()!;
      project.bivariateRunId = `bivariate-${project.id}`;
      return response(route, { run_id: project.bivariateRunId, status: "complete", total: 3, completed: 3, failed: 0, percent: 100 });
    }
    if (method === "GET" && /^\/api\/bivariate-statistics\/runs\/[^/]+$/.test(path)) return response(route, { run_id: path.split("/").at(-1), status: "complete", total: 3, completed: 3, failed: 0, percent: 100 });
    if (method === "GET" && path.includes("/bivariate-statistics/runs/") && path.endsWith("/results")) return response(route, { items: [{ left_isin: labels[0].isin, left_exchange: "XETRA", left_code: "ALPHA", right_isin: labels[1].isin, right_exchange: "XETRA", right_code: "BETA", n_observations: 252, covariance: 0.12, pearson_correlation: 0.6, spearman_correlation: 0.5, downside_correlation: 0.7, lower_tail_dependence: 0.12, tail_coexceedance_rate: 0.08 }], total: 1, limit: 50, offset: 0 });
    if (method === "GET" && path.endsWith("/covariance-matrix")) return response(route, { labels, values: matrix, observation_count: 252, diagnostics: { listing_count: 3, pair_count: 3, observation_count: 252, average_pairwise_covariance: 0.09, average_pairwise_correlation: 0.4, equal_weight_volatility: 0.12, minimum_variance_volatility: 0.1, diversification_ratio: 1.2, effective_number_of_bets: 2.4, largest_equal_weight_risk_contribution: 0.4 } });
    if (method === "GET" && path.endsWith("/summary")) return response(route, bivariateSummary());
    if (method === "GET" && path.endsWith("/tail-risk-scatter")) return response(route, { points: [{ left_isin: labels[0].isin, left_exchange: "XETRA", left_code: "ALPHA", right_isin: labels[1].isin, right_exchange: "XETRA", right_code: "BETA", tail_dependence: 0.12, coexceedance_rate: 0.08 }], pair_count: 1, observation_count: 252, date_start: "2024-01-02", date_end: "2024-12-31", tail_dependence_median: 0.12, coexceedance_rate_median: 0.08 });
    if (method === "GET" && path.endsWith("/correlation-matrix")) return response(route, { labels, values: matrix, observation_count: 252 });
    throw new Error(`Unhandled UI request: ${method} ${path}`);
  });

  return { calls, projects, settingsWrites };
}

function projectSummary(project: Project) {
  return { project_id: project.id, name: project.name, selection_id: `selection-${project.id}`, selected_count: 3, data_loaded: Boolean(project.quoteRunId) };
}

async function createProject(page: Page, filter: { exchange: string; instrumentType: string; country: string; currency: string; name: string }) {
  await page.getByLabel("Exchange").selectOption(filter.exchange);
  await page.getByLabel("Instrument type").selectOption(filter.instrumentType);
  await page.getByLabel("Country").selectOption(filter.country);
  await page.getByLabel("Currency").selectOption(filter.currency);
  await page.getByLabel("Name contains").fill(filter.name);
  await page.getByRole("button", { name: "Create new project" }).click();
  await expect(page.getByText("3 unique ISINs selected.")).toBeVisible();
}

async function computeUnivariate(page: Page) {
  await expect(page.getByRole("heading", { name: "Dividends" })).not.toBeVisible();
  await page.getByRole("button", { name: "Update Historical Data" }).click();
  await expect(page.getByRole("button", { name: "Update Historical Data · 3 ISINs updated" })).toBeVisible();
  await page.getByRole("button", { name: "Compute univariate statistics" }).click();
  await expect(page.getByText("3 listings computed.")).toBeVisible();
  await expect(page.getByRole("img", { name: "Annual dividend yield distribution for 3 ISINs" })).toBeVisible();
}

async function switchProject(page: Page, projectId: string) {
  const navigation = page.getByLabel("Open project navigation");
  if (await navigation.isVisible()) await navigation.click();
  await page.getByLabel("Project", { exact: true }).selectOption(projectId);
}

test("two dummy projects created through the UI preserve every research control and project setting", async ({ page }) => {
  const fixture = await installTwoProjectApi(page);
  await page.goto("/metadata-builder");
  await expect(page).toHaveURL(/\/metadata-builder$/);
  await expect(page.getByText("2 · Metadata Builder")).toBeVisible();

  await page.getByLabel("EODHD key").fill("dummy-eodhd-key");
  await page.getByRole("button", { name: "Fetch all metadata" }).click();
  await expect(page.getByText("4 metadata rows from 1 exchanges loaded.")).toBeVisible();

  await createProject(page, { exchange: "XETRA", instrumentType: "ETF", country: "IE", currency: "EUR", name: "Alpha income" });
  await page.goto("/univariate-statistics");
  await computeUnivariate(page);

  const selections = page.locator(".univariate-statistics-page .portfolio-selection select");
  await expect(selections).toHaveCount(1);
  await selections.selectOption(["monthly", "annual"]);
  for (const tab of ["Duration", "Annual Return", "Value at Risk", "Sortino ratio", "Expected shortfall", "Tail observations", "Sharpe ratio", "Maximum drawdown", "Trend R-squared"]) {
    await page.getByRole("tab", { name: tab }).click();
    await expect(selections).toHaveCount(1);
    await selections.selectOption({ index: 0 });
  }
  await expect.poll(() => fixture.settingsWrites.get("project-1") ?? 0).toBeGreaterThanOrEqual(9);
  await page.getByRole("tab", { name: "Dividends" }).click();
  await page.getByRole("img", { name: "Annual dividend yield distribution for 3 ISINs" }).locator("[tabindex=\"0\"]").first().hover();
  await expect(page.getByRole("tooltip").first()).toBeVisible();

  await page.goto("/metadata-builder");
  await createProject(page, { exchange: "LSE", instrumentType: "FUND", country: "LU", currency: "USD", name: "Beta growth" });
  await page.goto("/univariate-statistics");
  await computeUnivariate(page);

  await switchProject(page, "project-1");
  await expect(page).toHaveURL(/\/univariate-statistics$/);
  await page.getByRole("tab", { name: "Dividends" }).click();
  await expect(selections).toHaveValues(["monthly", "annual"]);
  await page.goto("/metadata-builder");
  await expect(page.getByLabel("Exchange")).toHaveValue("XETRA");
  await expect(page.getByLabel("Instrument type")).toHaveValue("ETF");
  await expect(page.getByLabel("Country")).toHaveValue("IE");
  await expect(page.getByLabel("Currency")).toHaveValue("EUR");
  await expect(page.getByLabel("Name contains")).toHaveValue("Alpha income");

  await switchProject(page, "project-2");
  await page.goto("/bivariate-statistics");
  await page.getByRole("button", { name: "Compute Bivariate Statistics" }).click();
  await expect(page.getByText("1 pair statistics computed.")).toBeVisible();
  for (const tab of ["Covariance", "Pearson", "Spearman", "Downside", "Tail Dependence", "Co-exceedance", "Rolling-Correlation", "Drawdown Overlap", "Tail-Risk Scatter"]) {
    await page.getByRole("tab", { name: tab }).click();
    await expect(page.getByRole("tab", { name: tab })).toHaveAttribute("aria-selected", "true");
  }

  expect([...fixture.projects.values()].map((project) => project.name)).toEqual(["Alpha income", "Beta growth"]);
  expect(fixture.calls).toEqual(expect.arrayContaining([
    "POST /api/credentials/eodhd",
    "POST /api/metadata/fetch-all",
    "POST /api/metadata-builder",
    "POST /api/quote-runs",
    "POST /api/univariate-statistics/runs",
    "POST /api/bivariate-statistics/plan",
    "POST /api/bivariate-statistics/runs",
    "PUT /api/project-context/current-project",
  ]));
});
