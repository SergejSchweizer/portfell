import { expect, test, type Page, type Route } from "@playwright/test";

type Project = {
  id: string;
  name: string;
  criteria: { exchange: string; instrument_type: string; country: string; currency: string; name: string };
  univariateRunId?: string;
  bivariateRunId?: string;
  multivariateRunId?: string;
  selectedCandidateIds?: string[];
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

function selectedUnivariateIsinCount(project: Project): number {
  const frequencies = project.settings.dividend_frequencies;
  return frequencies.length === 0
    ? univariateRows.length
    : univariateRows.filter((row) => frequencies.includes(row.distribution_frequency)).length;
}

function workflow(project: Project | undefined) {
  if (!project) {
    return {
      stages: {
        metadata_builder: { status: "ready" },
        univariate_statistics: { status: "locked" },
        bivariate_statistics: { status: "locked" },
        multivariate_statistics: { status: "locked" },
      },
      process_overview: { metadata_downloaded_isins: 4 },
    };
  }
  const univariateReady = Boolean(project.univariateRunId);
  return {
    stages: {
      metadata_builder: { status: "complete", metadata_selection_id: `selection-${project.id}` },
      univariate_statistics: { status: univariateReady ? "complete" : "ready", univariate_run_id: project.univariateRunId, univariate_selection_id: univariateReady ? `univariate-selection-${project.id}` : undefined },
      bivariate_statistics: univariateReady ? { status: project.bivariateRunId ? "complete" : "ready", bivariate_run_id: project.bivariateRunId } : { status: "locked" },
      multivariate_statistics: project.bivariateRunId ? {
        status: project.multivariateRunId ? "complete" : "ready",
        bivariate_run_id: project.bivariateRunId,
        univariate_selection_id: `univariate-selection-${project.id}`,
        multivariate_run_id: project.multivariateRunId,
      } : { status: "locked" },
    },
    process_overview: { metadata_downloaded_isins: 4, metadata_builder_isins: 3, univariate_statistics_isins: univariateReady ? selectedUnivariateIsinCount(project) : null },
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

function multivariateRun(project: Project, status: "running" | "complete") {
  return { run_id: project.multivariateRunId, project_id: project.id, bivariate_run_id: project.bivariateRunId, input_snapshot_id: status === "complete" ? `snapshot-${project.id}` : null, status, phase: status === "complete" ? "complete" : "resolve_inputs", completed_units: status === "complete" ? 6 : 0, total_units: 6, elapsed_seconds: 0, estimated_remaining_seconds: status === "complete" ? 0 : 10, settings: { selected_candidate_ids: project.selectedCandidateIds ?? [] }, warnings: [], failure_reason: null };
}

function multivariateSummary() { return { input_snapshot_id: "snapshot", risk_model_id: "risk", candidate_etf_count: 3, aligned_period: { date_start: "2024-01-01", date_end: "2025-01-01", observation_count: 252 }, availability_reasons: [] }; }
function multivariateStructure() { return { risk_cluster_count: 2, dominant_component_share: 0.6, effective_rank: 1.8, effective_independent_drivers: 1.8, period: { date_start: "2024-01-01", date_end: "2025-01-01", observation_count: 252 }, thresholds: { components_for_80pct: 2, components_for_90pct: 2, components_for_95pct: 3 }, strongest_common_driver: { isin: "IE00ALPHA01", exchange: "XETRA", code: "ALPHA" }, largest_redundancy_warning: { left: { isin: "IE00ALPHA01", exchange: "XETRA", code: "ALPHA" }, right: { isin: "IE00ALPHA02", exchange: "XETRA", code: "BETA" }, correlation: 0.7 }, availability_reasons: [] }; }
function multivariateCandidates() { return { items: [{ candidate_id: "candidate-equal", method: "equal_weight", baseline: true, status: "feasible", reasons: [], weights: [{ isin: "IE00ALPHA01", exchange: "XETRA", code: "ALPHA", weight: 1 / 3 }, { isin: "IE00ALPHA02", exchange: "XETRA", code: "BETA", weight: 1 / 3 }, { isin: "IE00ALPHA03", exchange: "XETRA", code: "GAMMA", weight: 1 / 3 }], variance: 0.02, volatility: 0.14, var: 0.03, cvar: 0.04, maximum_weight: 1 / 3, herfindahl_index: 1 / 3, effective_holding_count: 3, gross_ttm_distribution_yield: 0.03, gross_monthly_distribution: 0.2, total_return: 0.1, average_monthly_return: 0.01, average_annual_return: 0.12, max_drawdown: -0.12, diversification_ratio: 1.2 }] }; }
function multivariateComponents() { return { items: [{ component_id: "Component 1", isin: "IE00ALPHA01", exchange: "XETRA", code: "ALPHA", loading: 0.7, explained_variance: 0.6, cluster: "Cluster 1" }], total: 1, limit: 25, offset: 0 }; }
function multivariateContributions() { return { items: [{ candidate_id: "candidate-equal", method: "equal_weight", isin: "IE00ALPHA01", exchange: "XETRA", code: "ALPHA", weight: 1 / 3, marginal_risk_contribution: 0.02, absolute_risk_contribution: 0.006, percent_risk_contribution: 0.34 }] }; }
function multivariateIncome() { return { items: [{ isin: "IE00ALPHA01", exchange: "XETRA", code: "ALPHA", currency: "EUR", event_count: 12, observed_month_count: 12, observed_payment_coverage: 1, gross_ttm_distribution_amount: 2.4, gross_ttm_distribution_yield: 0.03, mean_observed_monthly_distribution: 0.2, median_observed_monthly_distribution: 0.2, lower_percentile_monthly_distribution: 0.18, coefficient_of_variation: 0.1, cut_count: 0, largest_cut: null, longest_falling_sequence: 0, distribution_trend: 0.01, price_return: 0.08, total_return: 0.1, distribution_to_total_return_gap: 0.02, market_price_capital_change: 0.08, availability_reasons: [], warnings: [] }] }; }
function multivariatePerformance() { return { instrument_series: [{ isin: "IE00ALPHA01", exchange: "XETRA", code: "ALPHA", values: [{ date: "2023-06-01", return: 0.5 }, { date: "2024-01-02", return: 0.01 }, { date: "2024-01-03", return: 0.03 }] }, { isin: "IE00ALPHA02", exchange: "XETRA", code: "BETA", values: [{ date: "2024-01-02", return: -0.01 }, { date: "2024-01-03", return: 0.02 }] }], portfolio_series: [{ candidate_id: "candidate-equal", method: "equal_weight", values: [{ date: "2024-01-02", return: 0 }, { date: "2024-01-03", return: 0.025 }] }, { candidate_id: "candidate-minimum-variance", method: "minimum_variance", values: [{ date: "2024-01-02", return: 0.005 }, { date: "2024-01-03", return: 0.027 }] }], period_returns: [{ candidate_id: "candidate-equal", method: "equal_weight", period: "monthly", label: "2024-01", return: 0.025 }, { candidate_id: "candidate-equal", method: "equal_weight", period: "annual", label: "2024", return: 0.025 }, { candidate_id: "candidate-minimum-variance", method: "minimum_variance", period: "monthly", label: "2024-01", return: 0.027 }, { candidate_id: "candidate-minimum-variance", method: "minimum_variance", period: "annual", label: "2024", return: 0.027 }] }; }

async function installTwoProjectApi(
  page: Page,
  initialFillStatus: "ready" | "running" = "ready",
  omitSelectionIdFromContext = false,
  bivariateCompletesAfterPoll = false,
  multivariateCompletesAfterPoll = false,
  unavailableMultivariateEvidence = false,
): Promise<WorkflowFixture> {
  const projects = new Map<string, Project>();
  const settingsWrites = new Map<string, number>();
  const calls: string[] = [];
  let currentProjectId: string | null = null;
  let metadataPolls = 0;
  let bivariatePolls = 0;
  let multivariatePolls = 0;
  const initialFillStartedAt = Math.floor(Date.now() / 1_000) - 60;
  const initialFillRow = (projectId: string) => ({
    bootstrap_id: `bootstrap-${projectId}`,
    job_id: `job-${projectId}`,
    status: initialFillStatus,
    completed_units: initialFillStatus === "running" ? 1 : 3,
    total_units: 3,
    selected_listing_count: 3,
    terminal_code: null,
    started_at: initialFillStartedAt,
  });

  const current = () => currentProjectId ? projects.get(currentProjectId) : undefined;
  const context = () => {
    const summary = (project: Project) => {
      const value = projectSummary(project);
      if (!omitSelectionIdFromContext) return value;
      const { selection_id: _selectionId, ...withoutSelectionId } = value;
      return withoutSelectionId;
    };
    return {
      current_project_id: currentProjectId,
      current_project: currentProjectId ? summary(projects.get(currentProjectId)!) : null,
      projects: [...projects.values()].map(summary),
    };
  };

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
    if (method === "GET" && path === "/api/metadata-builder/options") return response(route, { exchange: [{ value: "XETRA", isin_count: 3 }, { value: "LSE", isin_count: 1 }], instrument_type: [{ value: "ETF", isin_count: 3 }, { value: "FUND", isin_count: 1 }], country: [{ value: "IE", isin_count: 3 }, { value: "LU", isin_count: 1 }], currency: [{ value: "EUR", isin_count: 3 }, { value: "USD", isin_count: 1 }] });
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
    const initialFill = path.match(/^\/api\/projects\/([^/]+)\/initial-fill$/);
    if (method === "GET" && initialFill) {
      return response(route, initialFillRow(initialFill[1]));
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
      return response(route, { project: { project_id: id, name: project.name }, selection: { selection_id: `selection-${id}`, name: project.name }, selected_count: 3, initial_fill: initialFillRow(id) });
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
      return response(route, { run_id: project.bivariateRunId, status: bivariateCompletesAfterPoll ? "running" : "complete", total: 3, completed: bivariateCompletesAfterPoll ? 0 : 3, failed: 0, percent: bivariateCompletesAfterPoll ? 0 : 100 });
    }
    if (method === "GET" && /^\/api\/bivariate-statistics\/runs\/[^/]+$/.test(path)) {
      bivariatePolls += 1;
      const running = bivariateCompletesAfterPoll && bivariatePolls === 1;
      return response(route, { run_id: path.split("/").at(-1), status: running ? "running" : "complete", total: 3, completed: running ? 0 : 3, failed: 0, percent: running ? 0 : 100 });
    }
    if (method === "GET" && path.includes("/bivariate-statistics/runs/") && path.endsWith("/results")) return response(route, { items: [{ left_isin: labels[0].isin, left_exchange: "XETRA", left_code: "ALPHA", right_isin: labels[1].isin, right_exchange: "XETRA", right_code: "BETA", n_observations: 252, covariance: 0.12, pearson_correlation: 0.6, spearman_correlation: 0.5, downside_correlation: 0.7, lower_tail_dependence: 0.12, tail_coexceedance_rate: 0.08 }], total: 1, limit: 50, offset: 0 });
    if (method === "GET" && path.endsWith("/covariance-matrix")) return response(route, { labels, values: matrix, observation_count: 252, diagnostics: { listing_count: 3, pair_count: 3, observation_count: 252, average_pairwise_covariance: 0.09, average_pairwise_correlation: 0.4, equal_weight_volatility: 0.12, minimum_variance_volatility: 0.1, diversification_ratio: 1.2, effective_number_of_bets: 2.4, largest_equal_weight_risk_contribution: 0.4 } });
    if (method === "GET" && path.includes("/bivariate-statistics/") && path.endsWith("/summary")) return response(route, bivariateSummary());
    if (method === "GET" && path.endsWith("/tail-risk-scatter")) return response(route, { points: [{ left_isin: labels[0].isin, left_exchange: "XETRA", left_code: "ALPHA", right_isin: labels[1].isin, right_exchange: "XETRA", right_code: "BETA", tail_dependence: 0.12, coexceedance_rate: 0.08 }], pair_count: 1, observation_count: 252, date_start: "2024-01-02", date_end: "2024-12-31", tail_dependence_median: 0.12, coexceedance_rate_median: 0.08 });
    if (method === "GET" && path.endsWith("/correlation-matrix")) return response(route, { labels, values: matrix, observation_count: 252 });
    if (method === "POST" && path === "/api/multivariate-statistics/runs") {
      const project = current()!;
      project.multivariateRunId = `multivariate-${project.id}`;
      return response(route, multivariateRun(project, "running"));
    }
    if (method === "GET" && /^\/api\/multivariate-statistics\/runs\/[^/]+$/.test(path)) {
      multivariatePolls += 1;
      const running = multivariateCompletesAfterPoll && multivariatePolls <= 5;
      return response(route, multivariateRun(current()!, running ? "running" : "complete"));
    }
    if (method === "GET" && path.endsWith("/summary")) return response(route, unavailableMultivariateEvidence ? { ...multivariateSummary(), availability_reasons: ["insufficient_common_history"] } : multivariateSummary());
    if (method === "GET" && path.endsWith("/structure")) return response(route, unavailableMultivariateEvidence ? { ...multivariateStructure(), effective_rank: 0, effective_independent_drivers: 0, risk_cluster_count: 0, availability_reasons: ["risk_model_unavailable"] } : multivariateStructure());
    if (method === "GET" && path.endsWith("/candidates")) return response(route, multivariateCandidates());
    if (method === "GET" && path.endsWith("/components")) return response(route, multivariateComponents());
    if (method === "GET" && path.endsWith("/risk-contributions")) return response(route, multivariateContributions());
    if (method === "GET" && path.endsWith("/income-evidence")) return response(route, multivariateIncome());
    if (method === "GET" && path.endsWith("/performance")) return response(route, multivariatePerformance());
    if (method === "GET" && path.endsWith("/validation")) return response(route, { items: [{ kind: "scorecard", method: "equal_weight", status: "available", reason: null }] });
    if (method === "GET" && path.endsWith("/artifacts")) return response(route, { risk_model: unavailableMultivariateEvidence ? { estimator: "ledoit_wolf", shrinkage_intensity: null, minimum_eigenvalue: null, condition_number: null, is_positive_semidefinite: false, observation_count: 100, availability_reasons: ["insufficient_common_history"] } : { estimator: "ledoit_wolf", shrinkage_intensity: 0.2, minimum_eigenvalue: 0.01, condition_number: 12.5, is_positive_semidefinite: true, observation_count: 252, availability_reasons: [] } });
    if (method === "PATCH" && path.endsWith("/settings")) {
      const project = current()!;
      project.selectedCandidateIds = body.selected_candidate_ids as string[];
      return response(route, multivariateRun(project, "complete"));
    }
    throw new Error(`Unhandled UI request: ${method} ${path}`);
  });

  return { calls, projects, settingsWrites };
}

function projectSummary(project: Project) {
  return { project_id: project.id, name: project.name, selection_id: `selection-${project.id}`, selected_count: 3, data_loaded: true };
}

async function createProject(page: Page, filter: { exchange: string; instrumentType: string; country: string; currency: string; name: string }) {
  await page.getByLabel("Exchange").selectOption(filter.exchange);
  await page.getByLabel("Instrument type").selectOption(filter.instrumentType);
  await page.getByLabel("Country").selectOption(filter.country);
  await page.getByLabel("Currency").selectOption(filter.currency);
  await page.getByLabel("Name contains").fill(filter.name);
  await page.getByRole("button", { name: "Create new project" }).click();
  await expect(page.getByText("3 unique ISINs selected.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Quotes ready - Create new project" })).toBeVisible();
}

async function computeUnivariate(page: Page) {
  await expect(page.getByRole("heading", { name: "Dividends" })).not.toBeVisible();
  await page.getByRole("button", { name: "Compute univariate statistics" }).click();
  await expect(page.getByText("3 listings computed.")).toBeVisible();
  await expect(page.getByRole("img", { name: "Annual dividend yield distribution for 3 ISINs" })).toBeVisible();
}

async function switchProject(page: Page, projectId: string) {
  const navigation = page.getByLabel("Open project navigation");
  if (await navigation.isVisible()) await navigation.click();
  await page.getByLabel("Project", { exact: true }).selectOption(projectId);
}

test("workflow URLs are canonical, project-scoped, and persist across every page", async ({ page }) => {
  await installTwoProjectApi(page);
  await page.goto("/metadata-builder");
  await createProject(page, { exchange: "XETRA", instrumentType: "ETF", country: "IE", currency: "EUR", name: "Alpha income" });
  await expect(page).toHaveURL(/\/projects\/project-1\/alpha-income\/metadata-builder$/);

  await page.goto("/univariate-statistics");
  await expect(page).toHaveURL(/\/projects\/project-1\/alpha-income\/univariate-statistics$/);
  await computeUnivariate(page);

  await createProject(page, { exchange: "LSE", instrumentType: "FUND", country: "LU", currency: "USD", name: "Beta growth" });
  await expect(page).toHaveURL(/\/projects\/project-2\/beta-growth\/metadata-builder$/);

  await page.goto("/projects/project-1/anything-goes-here/univariate-statistics");
  await expect(page).toHaveURL(/\/projects\/project-1\/alpha-income\/univariate-statistics$/);
  await page.getByRole("tab", { name: "Dividends" }).click();
  await expect(page.getByRole("img", { name: "Annual dividend yield distribution for 3 ISINs" })).toBeVisible();
});

test("selecting a project restores its Metadata Builder fields", async ({ page }) => {
  await installTwoProjectApi(page);
  await page.goto("/metadata-builder");
  await createProject(page, { exchange: "XETRA", instrumentType: "ETF", country: "IE", currency: "EUR", name: "Alpha income" });
  await createProject(page, { exchange: "LSE", instrumentType: "FUND", country: "LU", currency: "USD", name: "Beta growth" });

  await switchProject(page, "project-1");
  await page.goto("/metadata-builder");

  await expect(page.getByLabel("Exchange")).toHaveValue("XETRA");
  await expect(page.getByLabel("Instrument type")).toHaveValue("ETF");
  await expect(page.getByLabel("Country")).toHaveValue("IE");
  await expect(page.getByLabel("Currency")).toHaveValue("EUR");
  await expect(page.getByLabel("Name contains")).toHaveValue("Alpha income");
});

test("workflow sidebar colors complete, ready, and locked statuses", async ({ page }) => {
  await installTwoProjectApi(page);
  await page.goto("/metadata-builder");
  await createProject(page, { exchange: "XETRA", instrumentType: "ETF", country: "IE", currency: "EUR", name: "Workflow status colors" });

  const sidebar = page.locator(".project-sidebar__workflow");
  await expect(sidebar.locator('li[data-status="complete"] small')).toHaveCSS("color", "rgb(19, 115, 51)");
  await expect(sidebar.locator('li[data-status="ready"] small')).toHaveCSS("color", "rgb(11, 87, 208)");
  await expect(sidebar.locator('li[data-status="locked"] small').first()).toHaveCSS("color", "rgb(109, 114, 120)");
});

test("Bivariate compute button polls through completion without a terminal failure", async ({ page }) => {
  const fixture = await installTwoProjectApi(page, "ready", false, true);
  await page.goto("/metadata-builder");
  await createProject(page, { exchange: "XETRA", instrumentType: "ETF", country: "IE", currency: "EUR", name: "Bivariate lifecycle" });
  await page.goto("/univariate-statistics");
  await computeUnivariate(page);
  await page.goto("/bivariate-statistics");

  const action = page.getByRole("button", { name: "Compute Bivariate Statistics" });
  await action.click();
  await expect(page.getByRole("button", { name: "Computing…" })).toBeDisabled();
  await expect(page.getByText("0 of 3 pair statistics computed.")).toBeVisible();
  await expect(page.getByText("1 pair statistics computed.")).toBeVisible();
  await expect(action).toBeEnabled();
  await expect(page.getByRole("tab", { name: "Covariance" })).toBeVisible();
  await expect(page.getByText("Bivariate computation failed. Please try again.")).not.toBeVisible();
  expect(fixture.calls).toEqual(expect.arrayContaining([
    "POST /api/bivariate-statistics/plan",
    "POST /api/bivariate-statistics/runs",
    "GET /api/bivariate-statistics/runs/bivariate-project-1",
  ]));
});

test("Multivariate compute button polls resolve_inputs through completion", async ({ page }) => {
  const fixture = await installTwoProjectApi(page, "ready", false, false, true);
  await page.goto("/metadata-builder");
  await createProject(page, { exchange: "XETRA", instrumentType: "ETF", country: "IE", currency: "EUR", name: "Multivariate lifecycle" });
  await page.goto("/univariate-statistics");
  await computeUnivariate(page);
  await page.goto("/bivariate-statistics");
  await page.getByRole("button", { name: "Compute Bivariate Statistics" }).click();
  await expect(page.getByRole("tab", { name: "Covariance" })).toBeVisible();
  await page.goto("/multivariate-statistics");

  await page.getByRole("button", { name: "Compute multivariate statistics" }).click();
  await expect(page.getByRole("button", { name: "Computing…" })).toBeDisabled();
  await expect(page.getByText("resolve_inputs · 0 of 6 phases complete · 0s elapsed · about 10s remaining")).toBeVisible();
  await expect(page.getByRole("button", { name: "Compute multivariate statistics" })).toBeEnabled();
  await expect(page.getByText("Candidate ETFs")).toBeVisible();
  await expect(page.getByRole("table", { name: "Multivariate overview facts" })).toHaveText(/Candidate ETFs/);
  await page.getByRole("tab", { name: "Risk Structure" }).click();
  await expect(page.getByRole("table", { name: "Multivariate risk structure facts" })).toHaveText(/Largest redundancy/);
  await page.getByRole("tab", { name: "Portfolio Candidates" }).click();
  await expect(page.getByText("Average monthly return: 1.00% · Average annual return: 12.00%")).toBeVisible();
  await page.getByRole("tab", { name: "Performance" }).click();
  await expect(page.getByText("Monthly portfolio returns")).toBeVisible();
  const performanceChart = page.getByRole("group", { name: /Cumulative return comparison/ });
  await expect(performanceChart).toBeVisible();
  await expect(page.getByRole("list", { name: "Performance series" })).toContainText("Minimum variance");
  await performanceChart.hover();
  await expect(page.getByRole("tooltip")).toContainText("ALPHA.XETRA: 3.00%");
  await expect(page.getByRole("tooltip")).toContainText("Equal weight: 2.50%");
  await expect(page.getByRole("tooltip")).toContainText("Minimum variance: 2.70%");
  await expect(page.locator(".performance-chart__tooltip-instrument")).toHaveCount(2);
  await expect(page.locator(".performance-chart__tooltip-portfolio--0")).toContainText("Equal weight: 2.50%");
  await expect(page.locator(".performance-chart__tooltip-portfolio--1")).toContainText("Minimum variance: 2.70%");
  await performanceChart.focus();
  await page.keyboard.press("Home");
  await expect(page.getByRole("tooltip")).toContainText("2024-01-02");
  await expect(page.getByRole("tooltip")).not.toContainText("2023-06-01");
  expect(fixture.calls).toEqual(expect.arrayContaining([
    "POST /api/multivariate-statistics/runs",
    "GET /api/multivariate-statistics/runs/multivariate-project-1",
    "GET /api/multivariate-statistics/runs/multivariate-project-1/performance",
  ]));
});

test("Multivariate state resets when switching to another project", async ({ page }) => {
  await installTwoProjectApi(page);
  await page.goto("/metadata-builder");
  await createProject(page, { exchange: "XETRA", instrumentType: "ETF", country: "IE", currency: "EUR", name: "First multivariate project" });
  await page.goto("/univariate-statistics");
  await computeUnivariate(page);
  await page.goto("/bivariate-statistics");
  await page.getByRole("button", { name: "Compute Bivariate Statistics" }).click();
  await expect(page.getByRole("tab", { name: "Covariance" })).toBeVisible();
  await page.goto("/multivariate-statistics");
  await page.getByRole("button", { name: "Compute multivariate statistics" }).click();
  await expect(page.getByText("Candidate ETFs")).toBeVisible();

  await page.goto("/metadata-builder");
  await createProject(page, { exchange: "LSE", instrumentType: "FUND", country: "LU", currency: "USD", name: "Second multivariate project" });
  await page.goto("/univariate-statistics");
  await computeUnivariate(page);
  await page.goto("/bivariate-statistics");
  await page.getByRole("button", { name: "Compute Bivariate Statistics" }).click();
  await expect(page.getByRole("tab", { name: "Covariance" })).toBeVisible();
  await page.goto("/multivariate-statistics");

  await expect(page.getByText("Ready to compute.")).toBeVisible();
  await expect(page.getByText("Candidate ETFs")).not.toBeVisible();
  await expect(page.getByRole("button", { name: "Compute multivariate statistics" })).toBeEnabled();
});

test("Multivariate unavailable statistics never render as zero or failed diagnostics", async ({ page }) => {
  await installTwoProjectApi(page, "ready", false, false, false, true);
  await page.goto("/metadata-builder");
  await createProject(page, { exchange: "XETRA", instrumentType: "ETF", country: "IE", currency: "EUR", name: "Unavailable multivariate evidence" });
  await page.goto("/univariate-statistics");
  await computeUnivariate(page);
  await page.goto("/bivariate-statistics");
  await page.getByRole("button", { name: "Compute Bivariate Statistics" }).click();
  await expect(page.getByRole("tab", { name: "Covariance" })).toBeVisible();
  await page.goto("/multivariate-statistics");
  await page.getByRole("button", { name: "Compute multivariate statistics" }).click();

  await expect(page.getByText("Unavailable evidence: insufficient_common_history")).toBeVisible();
  await expect(page.getByText("This analysis needs at least 100 shared daily returns. In Univariate Statistics, select Duration > 6 months, recompute Bivariate Statistics, then compute this run again.")).toBeVisible();
  await page.getByRole("tab", { name: "Risk Structure" }).click();
  for (const label of ["Effective rank", "Minimum eigenvalue", "Condition number", "Positive semidefinite"]) {
    const fact = page.getByRole("table", { name: "Multivariate risk structure facts" }).getByRole("row").filter({ has: page.getByRole("rowheader", { name: label, exact: true }) });
    await expect(fact.getByRole("cell")).toHaveText("Unavailable");
  }
  await expect(page.getByText("Structure unavailable: risk_model_unavailable")).toBeVisible();
});

test("every workflow button completes its browser action for two isolated projects", async ({ page }) => {
  const fixture = await installTwoProjectApi(page);
  await page.goto("/metadata-builder");
  await expect(page).toHaveURL(/\/metadata-builder$/);
  await expect(page.getByText("2 · Metadata Builder")).toBeVisible();
  await expect(page.getByLabel("Exchange").locator("option", { hasText: "XETRA (3 ISINs)" })).toHaveCount(1);

  await page.getByRole("button", { name: "Fetch all metadata" }).click();
  await expect(page.getByText("4 metadata rows from 1 exchanges loaded.")).toBeVisible();

  await createProject(page, { exchange: "XETRA", instrumentType: "ETF", country: "IE", currency: "EUR", name: "Alpha income" });
  await page.goto("/univariate-statistics");
  await computeUnivariate(page);

  await expect(page.locator(".univariate-statistic__tabs")).toHaveCSS("display", "grid");
  await expect(page.locator(".univariate-statistic__tabs")).toHaveCSS("overflow-x", "visible");

  const selections = page.locator(".univariate-statistics-page .portfolio-selection select");
  await expect(selections).toHaveCount(1);
  await expect(selections).toHaveAccessibleName("Portfolio selection (3 ISINs)");
  await selections.selectOption(["monthly", "annual"]);
  await expect(selections).toHaveAccessibleName("Portfolio selection (2 ISINs)");
  for (const tab of ["Duration", "Annual Return", "Value at Risk", "Sortino ratio", "Expected shortfall", "Tail observations", "Sharpe ratio", "Maximum drawdown", "Trend R-squared"]) {
    await page.getByRole("tab", { name: tab }).click();
    await expect(selections).toHaveCount(1);
    await expect(selections).toHaveAccessibleName("Portfolio selection (2 ISINs)");
    await selections.selectOption({ index: 0 });
  }
  await page.getByRole("tab", { name: "Duration" }).click();
  await selections.selectOption({ label: "> 2 years" });
  await expect.poll(() => fixture.projects.get("project-1")?.settings.statistic_ranges.quote_observation_count).toEqual([
    { minimum: 505, maximum: Number.MAX_SAFE_INTEGER },
  ]);
  await page.reload();
  await page.getByRole("tab", { name: "Duration" }).click();
  await expect(selections).toHaveValues(["> 2 years"]);
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
  await expect(page.getByRole("tab", { name: "Covariance" })).not.toBeVisible();
  await page.getByRole("button", { name: "Compute Bivariate Statistics" }).click();
  await expect(page.getByText("1 pair statistics computed.")).toBeVisible();
  await expect(page.locator(".bivariate-statistic__tabs")).toHaveCSS("display", "grid");
  await expect(page.locator(".bivariate-statistic__tabs")).toHaveCSS("overflow-x", "visible");
  for (const tab of ["Covariance", "Pearson", "Spearman", "Downside", "Tail Dependence", "Co-exceedance", "Rolling-Correlation", "Drawdown Overlap", "Tail-Risk Scatter"]) {
    await page.getByRole("tab", { name: tab }).click();
    await expect(page.getByRole("tab", { name: tab })).toHaveAttribute("aria-selected", "true");
  }
  await page.reload();
  const viewport = page.viewportSize();
  if (viewport && viewport.width < 768) {
    await page.getByRole("button", { name: "Open project navigation" }).click();
    const backdrop = page.getByRole("button", { name: "Close project navigation" });
    const backdropBox = await backdrop.boundingBox();
    if (!backdropBox) throw new Error("project navigation backdrop has no clickable area");
    await page.mouse.click(backdropBox.x + backdropBox.width - 8, backdropBox.y + backdropBox.height / 2);
    await expect(backdrop).not.toBeVisible();
    await page.getByRole("button", { name: "Open project navigation" }).click();
  }
  await page.getByRole("link", { name: /Multivariate Statistics/ }).click();
  await expect(page).toHaveURL(/\/multivariate-statistics$/);
  await expect(page.getByRole("heading", { name: "Multivariate Statistics" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Overview" })).not.toBeVisible();
  const multivariateCompute = page.locator(".multivariate-statistics-page .bivariate-compute");
  await expect(multivariateCompute.getByLabel("Multivariate statistics progress")).toBeVisible();
  await expect(multivariateCompute.locator("progress")).toHaveCSS("height", "14px");
  await expect(multivariateCompute.locator(".quote-fetch__action")).toHaveCSS("justify-content", "flex-end");
  await page.getByRole("button", { name: "Compute multivariate statistics" }).click();
  await expect(page.getByText("Candidate ETFs")).toBeVisible();
  await expect(page.getByText("Portfolio candidates", { exact: true })).toBeVisible();
  await expect(page.getByText("60.00%")).toBeVisible();
  await expect(page.locator(".statistics-tabs")).toHaveCSS("display", "grid");
  await expect(page.locator(".statistics-tabs")).toHaveCSS("overflow-x", "visible");
  for (const tab of ["Overview", "Risk Structure", "Portfolio Candidates", "Risk Contributions", "Income Evidence", "Validation"]) {
    await page.getByRole("tab", { name: tab }).click();
    await expect(page.getByRole("tab", { name: tab })).toHaveAttribute("aria-selected", "true");
  }
  await page.getByRole("tab", { name: "Risk Structure" }).click();
  await expect(page.getByRole("table", { name: "Multivariate risk structure facts" })).toHaveText(/ALPHA\.XETRA/);
  await expect(page.getByText("12.50", { exact: true })).toBeVisible();
  await expect(page.getByText("Yes", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "Portfolio Candidates" }).click();
  await expect(page.getByText(/VaR: 3.00%/)).toBeVisible();
  await expect(page.getByText(/Maximum weight: 33.33%/)).toBeVisible();
  await expect(page.getByText(/Effective holdings: 3.00/)).toBeVisible();
  await expect(page.getByText(/Herfindahl concentration: 0.33/)).toBeVisible();
  await page.getByLabel("Portfolio selection").click();
  await expect.poll(() => fixture.projects.get("project-2")?.selectedCandidateIds).toEqual(["candidate-equal"]);
  await page.getByRole("tab", { name: "Income Evidence" }).click();
  await expect(page.getByRole("cell", { name: "100.00%" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "8.00%" })).toBeVisible();

  expect([...fixture.projects.values()].map((project) => project.name)).toEqual(["Alpha income", "Beta growth"]);
  expect(fixture.calls).toEqual(expect.arrayContaining([
    "POST /api/metadata/fetch-all",
    "POST /api/metadata-builder",
    "POST /api/univariate-statistics/runs",
    "POST /api/bivariate-statistics/plan",
    "POST /api/bivariate-statistics/runs",
    "POST /api/multivariate-statistics/runs",
    "PATCH /api/multivariate-statistics/runs/multivariate-project-2/settings",
    "PUT /api/project-context/current-project",
  ]));
  expect(fixture.calls).not.toContain("POST /api/quote-runs");
});

test("Create new project displays running historical-data progress and ETA", async ({ page }) => {
  await installTwoProjectApi(page, "running", true);
  await page.goto("/metadata-builder");
  await page.getByLabel("Exchange").selectOption("XETRA");
  await page.getByLabel("Instrument type").selectOption("ETF");
  await page.getByLabel("Country").selectOption("IE");
  await page.getByLabel("Currency").selectOption("EUR");
  await page.getByLabel("Name contains").fill("Progress");
  await page.getByRole("button", { name: "Create new project" }).click();

  const action = page.getByRole("button", { name: /Loading quotes: 1 \/ 3 - about .* remaining/ });
  await expect(action).toBeDisabled();
  await page.reload();
  await expect(page.getByLabel("Exchange")).toHaveValue("XETRA");
  await expect(page.getByLabel("Instrument type")).toHaveValue("ETF");
  await expect(page.getByLabel("Country")).toHaveValue("IE");
  await expect(page.getByLabel("Currency")).toHaveValue("EUR");
  await expect(page.getByLabel("Name contains")).toHaveValue("Progress");
  await expect(action).toBeDisabled();
  await expect(page.getByRole("heading", { name: "Historical Data" })).toHaveCount(0);
});
