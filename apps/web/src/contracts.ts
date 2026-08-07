
export type ApiFieldOptions = Readonly<{
  exchange: readonly string[];
  instrument_type: readonly string[];
  country: readonly string[];
  currency: readonly string[];
}>;

export type WorkflowStageId =
  | "metadata_filter"
  | "univariate_statistics"
  | "univariate_filter"
  | "bivariate_statistics";

export type WorkflowStatus = "locked" | "ready" | "running" | "complete" | "failed" | "stale";

export type ApiWorkflow = Readonly<{
  stages: Readonly<Record<WorkflowStageId, Readonly<{
    status: WorkflowStatus;
    metadata_revision_id?: string;
    metadata_selection_id?: string;
    quote_run_id?: string;
    univariate_run_id?: string;
    univariate_filter_selection_id?: string;
    bivariate_run_id?: string;
  }>>>;
}>;

export type ApiMetadataFetch = Readonly<{
  metadata_run_id: string;
  status: "running" | "succeeded" | "failed";
  total: number;
  completed: number;
  percent: number;
  row_count?: number;
  exchange_count?: number;
  requested_exchange_count?: number;
  skipped_exchange_count?: number;
  skipped_exchanges?: readonly string[];
  error_code?: string;
}>;

export type ApiCredentialStatus = Readonly<{
  credential_id: string;
  provider: "eodhd";
  status: "active" | "revoked" | "deleted";
  key_version: string;
  masked_label: string;
}>;

export type ApiCredentialValue = Readonly<{
  provider_key: string;
}>;

export type ApiMetadataProject = Readonly<{
  project: Readonly<{ project_id: string; name: string }>;
  selection: Readonly<{ selection_id: string; name: string }>;
  selected_count: number;
}>;

export type ApiQuoteFetch = Readonly<{
  download_run_id: string;
  status: "running" | "succeeded" | "partial" | "failed";
  total?: number;
  completed?: number;
  failed?: number;
  percent?: number;
  progress?: number;
  selected_listing_count?: number;
  quote_successes?: number;
  quote_errors?: number;
  silver_quote_rows?: number;
}>;

export type ApiProjects = Readonly<{
  items: readonly ApiProjectSummary[];
}>;

export type ApiProjectSummary = Readonly<{
  project_id: string;
  name: string;
  selection_id?: string;
  selected_count: number;
  data_loaded: boolean;
}>;

export type ApiProjectContext = Readonly<{
  current_project_id: string | null;
  current_project: ApiProjectSummary | null;
  projects: readonly ApiProjectSummary[];
}>;

export type ApiResearchRun = Readonly<{
  run_id: string;
  status: "running" | "complete" | "failed";
  total: number;
  completed: number;
  failed: number;
  percent: number;
}>;

export type ApiPage<T> = Readonly<{
  items: readonly T[];
  total: number;
  limit: number;
  offset: number;
}>;

export type ApiUnivariateRow = Readonly<{
  isin: string;
  exchange: string;
  code: string;
  quote_observation_count: number;
  annualized_return?: number | null;
  annualized_volatility?: number | null;
  sharpe_ratio?: number | null;
  max_drawdown?: number | null;
  expected_shortfall?: number | null;
}>;

export type ApiMetric = Readonly<{
  metric: string;
  label: string;
  unit: string;
  operators: readonly string[];
}>;

export type ApiFilterSelection = Readonly<{
  selection_id: string;
  source_run_id: string;
  input_count: number;
  selected_count: number;
  excluded_count: number;
  predicates: readonly Readonly<{ metric: string; operator: string; value: number }>[];
}>;

export type ApiPairPlan = Readonly<{
  selected_listing_count: number;
  theoretical_pair_count: number;
  pair_limit: number;
  allowed: boolean;
}>;

export type ApiBivariateRow = Readonly<{
  left_isin: string;
  left_exchange: string;
  left_code: string;
  right_isin: string;
  right_exchange: string;
  right_code: string;
  n_observations: number;
  pearson_correlation?: number | null;
  spearman_correlation?: number | null;
  covariance?: number | null;
  left_beta_to_right?: number | null;
  right_beta_to_left?: number | null;
}>;
