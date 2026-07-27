import type {
  ApiCredentialStatus,
  ApiFieldOptions,
  ApiProject,
  ApiProjects,
  ApiProgress,
  ApiSession,
  ApiUnivariateSummary,
} from "../contracts";

export type FixtureScenarioName =
  | "empty-user"
  | "missing-credential"
  | "invalid-credential"
  | "free-key"
  | "paid-key"
  | "empty-project"
  | "partial-data"
  | "statistics-running"
  | "statistics-complete"
  | "stale-analysis"
  | "provider-error"
  | "authorization-error"
  | "portfolio-comparison"
  | "stress-warning"
  | "recommendation-ready"
  | "slow-api"
  | "offline-recovery";

export type FixtureScenario = Readonly<{
  name: FixtureScenarioName;
  description: string;
  session: ApiSession;
  credential: ApiCredentialStatus;
  projects: ApiProjects;
  fieldOptions: ApiFieldOptions;
  loadData: ApiProgress;
  summary: ApiUnivariateSummary;
}>;

export const fixtureScenarioNames: readonly FixtureScenarioName[] = [
  "empty-user",
  "missing-credential",
  "invalid-credential",
  "free-key",
  "paid-key",
  "empty-project",
  "partial-data",
  "statistics-running",
  "statistics-complete",
  "stale-analysis",
  "provider-error",
  "authorization-error",
  "portfolio-comparison",
  "stress-warning",
  "recommendation-ready",
  "slow-api",
  "offline-recovery",
] as const;

const emptySession: ApiSession = {
  authenticated: false,
  user_id: "fixture-user",
  email: "fixture-user@example.test",
  display_name: "fixture user",
  auth_provider: "fixture",
};

const baseProjects: ApiProjects = {
  items: [
    {
      project_id: "project-001",
      name: "Synthetic Growth ETF",
      selected_count: 42,
      data_loaded: true,
    },
  ],
};

const baseFieldOptions: ApiFieldOptions = {
  exchange: ["XETRA", "LSE"],
  instrument_type: ["ETF", "ETN"],
  country: ["DE", "GB"],
  currency: ["EUR", "GBP"],
};

const baseSummary: ApiUnivariateSummary = {
  items: [
    {
      name: "annualized_return",
      category: "performance",
      mean: "0.104",
      median: "0.101",
      three_std_range: "[-0.024, 0.232]",
      filter_options: [{ value: "top-quartile", label: "Top quartile" }],
    },
  ],
};

const scenarioTable: Record<FixtureScenarioName, FixtureScenario> = {
  "empty-user": {
    name: "empty-user",
    description: "Unauthenticated visitor with no persisted shell state.",
    session: { ...emptySession, authenticated: false },
    credential: { status: "inactive" },
    projects: { items: [] },
    fieldOptions: { exchange: [], instrument_type: [], country: [], currency: [] },
    loadData: { status: "failed", progress: 0 },
    summary: { items: [] },
  },
  "missing-credential": {
    name: "missing-credential",
    description: "Authenticated user without a saved EODHD credential.",
    session: { ...emptySession, authenticated: true },
    credential: { status: "inactive" },
    projects: { items: [] },
    fieldOptions: baseFieldOptions,
    loadData: { status: "failed", progress: 0 },
    summary: { items: [] },
  },
  "invalid-credential": {
    name: "invalid-credential",
    description: "Saved key rejected by the provider boundary.",
    session: { ...emptySession, authenticated: true },
    credential: { status: "inactive", masked_label: "•••• 9931" },
    projects: { items: [] },
    fieldOptions: baseFieldOptions,
    loadData: { status: "failed", progress: 0 },
    summary: { items: [] },
  },
  "free-key": {
    name: "free-key",
    description: "Authenticated user with a free synthetic key.",
    session: { ...emptySession, authenticated: true },
    credential: { status: "active", masked_label: "free-key" },
    projects: baseProjects,
    fieldOptions: baseFieldOptions,
    loadData: { status: "succeeded", progress: 100, selected_count: 42 },
    summary: baseSummary,
  },
  "paid-key": {
    name: "paid-key",
    description: "Authenticated user with a paid synthetic key.",
    session: { ...emptySession, authenticated: true },
    credential: { status: "active", masked_label: "paid-key" },
    projects: baseProjects,
    fieldOptions: baseFieldOptions,
    loadData: { status: "succeeded", progress: 100, selected_count: 42 },
    summary: baseSummary,
  },
  "empty-project": {
    name: "empty-project",
    description: "Authenticated user with an empty project shell.",
    session: { ...emptySession, authenticated: true },
    credential: { status: "active", masked_label: "free-key" },
    projects: { items: [] },
    fieldOptions: baseFieldOptions,
    loadData: { status: "succeeded", progress: 100, selected_count: 0 },
    summary: { items: [] },
  },
  "partial-data": {
    name: "partial-data",
    description: "Project with partial progress and incomplete statistics.",
    session: { ...emptySession, authenticated: true },
    credential: { status: "active", masked_label: "free-key" },
    projects: baseProjects,
    fieldOptions: baseFieldOptions,
    loadData: { status: "running", progress: 48, selected_count: 21 },
    summary: baseSummary,
  },
  "statistics-running": {
    name: "statistics-running",
    description: "Statistics step is in-flight with stable progress.",
    session: { ...emptySession, authenticated: true },
    credential: { status: "active", masked_label: "free-key" },
    projects: baseProjects,
    fieldOptions: baseFieldOptions,
    loadData: { status: "running", progress: 63, selected_count: 42 },
    summary: baseSummary,
  },
  "statistics-complete": {
    name: "statistics-complete",
    description: "Loaded project with completed statistics summary.",
    session: { ...emptySession, authenticated: true },
    credential: { status: "active", masked_label: "free-key" },
    projects: baseProjects,
    fieldOptions: baseFieldOptions,
    loadData: { status: "succeeded", progress: 100, selected_count: 42 },
    summary: baseSummary,
  },
  "stale-analysis": {
    name: "stale-analysis",
    description: "Upstream state changed and downstream results are stale.",
    session: { ...emptySession, authenticated: true },
    credential: { status: "active", masked_label: "free-key" },
    projects: {
      items: [
        {
          project_id: "project-001",
          name: "Synthetic Growth ETF",
          selected_count: 42,
          data_loaded: false,
        },
      ],
    },
    fieldOptions: baseFieldOptions,
    loadData: { status: "succeeded", progress: 100, selected_count: 42 },
    summary: baseSummary,
  },
  "provider-error": {
    name: "provider-error",
    description: "Provider request failed with a redacted error state.",
    session: { ...emptySession, authenticated: true },
    credential: { status: "inactive" },
    projects: { items: [] },
    fieldOptions: baseFieldOptions,
    loadData: { status: "failed", progress: 0 },
    summary: { items: [] },
  },
  "authorization-error": {
    name: "authorization-error",
    description: "User lacks authorization for the current resource.",
    session: { ...emptySession, authenticated: true, auth_provider: "google" },
    credential: { status: "inactive" },
    projects: { items: [] },
    fieldOptions: baseFieldOptions,
    loadData: { status: "failed", progress: 0 },
    summary: { items: [] },
  },
  "portfolio-comparison": {
    name: "portfolio-comparison",
    description: "Portfolio comparison fixtures for side-by-side review.",
    session: { ...emptySession, authenticated: true },
    credential: { status: "active", masked_label: "free-key" },
    projects: baseProjects,
    fieldOptions: baseFieldOptions,
    loadData: { status: "succeeded", progress: 100, selected_count: 42 },
    summary: baseSummary,
  },
  "stress-warning": {
    name: "stress-warning",
    description: "Stress view surfaces a warning without failing the shell.",
    session: { ...emptySession, authenticated: true },
    credential: { status: "active", masked_label: "free-key" },
    projects: baseProjects,
    fieldOptions: baseFieldOptions,
    loadData: { status: "succeeded", progress: 100, selected_count: 42 },
    summary: baseSummary,
  },
  "recommendation-ready": {
    name: "recommendation-ready",
    description: "Recommendation/report surfaces are ready to render.",
    session: { ...emptySession, authenticated: true },
    credential: { status: "active", masked_label: "paid-key" },
    projects: baseProjects,
    fieldOptions: baseFieldOptions,
    loadData: { status: "succeeded", progress: 100, selected_count: 42 },
    summary: baseSummary,
  },
  "slow-api": {
    name: "slow-api",
    description: "Deterministic delayed responses for slow-network coverage.",
    session: { ...emptySession, authenticated: true },
    credential: { status: "active", masked_label: "free-key" },
    projects: baseProjects,
    fieldOptions: baseFieldOptions,
    loadData: { status: "running", progress: 25, selected_count: 21 },
    summary: baseSummary,
  },
  "offline-recovery": {
    name: "offline-recovery",
    description: "Offline browser recovery after the API comes back.",
    session: { ...emptySession, authenticated: true },
    credential: { status: "active", masked_label: "free-key" },
    projects: baseProjects,
    fieldOptions: baseFieldOptions,
    loadData: { status: "failed", progress: 0 },
    summary: baseSummary,
  },
};

export function getFixtureScenario(name: string): FixtureScenario | null {
  return (scenarioTable as Record<string, FixtureScenario>)[name] || null;
}

export function listFixtureScenarioNames(): readonly FixtureScenarioName[] {
  return fixtureScenarioNames;
}

export function mockResponseFor(path: string, scenarioName: string, method = "GET") {
  const scenario = getFixtureScenario(scenarioName);
  if (!scenario) return null;
  const normalized = path.replace(/^\/+/, "");
  if (method === "GET" && normalized === "api/session") return scenario.session;
  if (method === "GET" && normalized === "api/credentials/eodhd") return scenario.credential;
  if (method === "GET" && normalized === "api/projects") return scenario.projects;
  if (method === "GET" && normalized === "api/metadata-filter/options") return scenario.fieldOptions;
  if (method === "GET" && normalized === "api/statistics/univariate/summary") return scenario.summary;
  if (method === "POST" && normalized === "api/data/load-selected-isins") return scenario.loadData;
  if (method === "POST" && normalized === "api/statistics/univariate/compute") return scenario.loadData;
  if (method === "POST" && normalized === "api/statistics/bivariate/compute") return scenario.loadData;
  if (method === "POST" && normalized === "api/statistics/multivariate/compute") return scenario.loadData;
  return null;
}
