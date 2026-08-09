
export type ApiFieldOptions = Readonly<{
  exchange: readonly string[];
  instrument_type: readonly string[];
  country: readonly string[];
  currency: readonly string[];
}>;

export type WorkflowStageId =
  | "metadata_builder"
  | "univariate_statistics"
  | "bivariate_statistics"
  | "multivariate_statistics";

export type WorkflowStatus = "locked" | "ready" | "running" | "complete" | "failed" | "stale";

export type ApiWorkflow = Readonly<{
  stages: Readonly<Record<WorkflowStageId, Readonly<{
    status: WorkflowStatus;
    metadata_revision_id?: string;
    metadata_selection_id?: string;
    quote_run_id?: string;
    univariate_run_id?: string;
    univariate_selection_id?: string;
    bivariate_run_id?: string;
    multivariate_run_id?: string;
  }>>>;
  process_overview?: Readonly<{
    metadata_downloaded_isins: number;
    metadata_builder_isins?: number;
    univariate_statistics_isins?: number | null;
  }>;
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
  started_at?: number;
  selected_listing_count?: number;
  quote_successes?: number;
  quote_errors?: number;
  silver_quote_rows?: number;
  error_code?: string;
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

export type ApiProjectMetadataBuilder = Readonly<{
  project_id: string;
  selection_id: string;
  selected_count: number;
  exchange: string;
  instrument_type: string;
  country: string;
  currency: string;
  name: string;
}>;

export type ApiResearchRun = Readonly<{
  run_id: string;
  status: "running" | "complete" | "failed";
  total: number;
  completed: number;
  failed: number;
  percent: number;
}>;

export type ApiMultivariateRun = Readonly<{
  run_id: string;
  project_id: string;
  bivariate_run_id: string;
  input_snapshot_id: string | null;
  status: WorkflowStatus;
  phase: string;
  completed_units: number;
  total_units: number;
  estimated_remaining_seconds: number | null;
  settings: Readonly<{ selected_candidate_ids?: readonly string[] }>;
  warnings: readonly string[];
  failure_reason: string | null;
}>;

export type ApiMultivariateSummary = Readonly<{
  input_snapshot_id?: string;
  risk_model_id?: string;
  candidate_etf_count?: number;
  aligned_period?: Readonly<{ date_start: string; date_end: string; observation_count: number }>;
  availability_reasons?: readonly string[];
}>;

export type ApiMultivariateStructure = Readonly<{
  risk_cluster_count?: number;
  dominant_component_share?: number | null;
  effective_rank?: number;
  effective_independent_drivers?: number;
  period?: Readonly<{ date_start: string; date_end: string; observation_count: number }>;
}>;

export type ApiMultivariateCandidate = Readonly<{
  candidate_id: string;
  method: string;
  baseline: boolean;
  status: string;
  reasons: readonly string[];
  weights: readonly Readonly<{ isin: string; exchange: string; code: string; weight: number }>[];
  variance: number | null;
  volatility: number | null;
  cvar: number | null;
  gross_ttm_distribution_yield: number | null;
  gross_monthly_distribution: number | null;
  total_return: number | null;
  max_drawdown: number | null;
  diversification_ratio: number | null;
}>;

export type ApiMultivariateCandidates = Readonly<{ items: readonly ApiMultivariateCandidate[] }>;
export type ApiMultivariateValidation = Readonly<{ items: readonly Readonly<Record<string, unknown>>[] }>;

export type ApiMultivariateRiskContribution = Readonly<{
  candidate_id: string;
  method: string;
  isin: string;
  exchange: string;
  code: string;
  weight: number;
  marginal_risk_contribution: number;
  absolute_risk_contribution: number;
  percent_risk_contribution: number;
}>;

export type ApiMultivariateRiskContributions = Readonly<{
  items: readonly ApiMultivariateRiskContribution[];
}>;

export type ApiMultivariateIncomeEvidence = Readonly<{
  isin: string;
  exchange: string;
  code: string;
  currency: string | null;
  event_count: number;
  observed_month_count: number;
  gross_ttm_distribution_amount: number | null;
  gross_ttm_distribution_yield: number | null;
  mean_observed_monthly_distribution: number | null;
  median_observed_monthly_distribution: number | null;
  lower_percentile_monthly_distribution: number | null;
  coefficient_of_variation: number | null;
  cut_count: number | null;
  largest_cut: number | null;
  longest_falling_sequence: number | null;
  availability_reasons: readonly string[];
  warnings: readonly string[];
}>;

export type ApiMultivariateIncomeEvidenceList = Readonly<{
  items: readonly ApiMultivariateIncomeEvidence[];
}>;

export type ApiMultivariateComponent = Readonly<{
  component_id: string;
  isin: string;
  exchange: string;
  code: string;
  loading: number;
  explained_variance: number;
  cluster: string | null;
}>;

export type ApiMultivariateComponents = Readonly<{
  items: readonly ApiMultivariateComponent[];
  total: number;
  limit: number;
  offset: number;
}>;

export type ApiMultivariateArtifacts = Readonly<Record<string, unknown>>;

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
} & Record<string, string | number | boolean | null | undefined>>;

export type ApiMetric = Readonly<{
  metric: string;
  label: string;
  unit: string;
  operators: readonly string[];
}>;

export type ApiMetricList = Readonly<{
  items: readonly ApiMetric[];
}>;

export type ApiDividendFrequency = "accumulating" | "monthly" | "quarterly" | "semiannual" | "annual" | "irregular";

export type ApiUnivariateSelectionSettings = Readonly<{
  dividend_frequencies: ApiDividendFrequency[];
  statistic_labels: Record<string, string[]>;
  statistic_ranges: Record<string, Readonly<{ minimum: number; maximum: number }>[]>;
}>;

export type ApiUnivariateSelection = Readonly<{
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
  date_start: string;
  date_end: string;
  n_observations: number;
  pearson_correlation?: number | null;
  spearman_correlation?: number | null;
  covariance?: number | null;
  downside_correlation?: number | null;
  lower_tail_dependence?: number | null;
  tail_coexceedance_rate?: number | null;
  rolling_correlation_stability?: number | null;
  drawdown_overlap_rate?: number | null;
  left_beta_to_right?: number | null;
  right_beta_to_left?: number | null;
}>;

export type ApiBivariateMetricSummary = Readonly<{
  mean: number | null;
  median: number | null;
  minimum: number | null;
  maximum: number | null;
  histogram: readonly Readonly<{ lower: number; upper: number; count: number }>[];
}>;

export type ApiBivariateSummary = Readonly<{
  pair_count: number;
  observation_count: number;
  date_start: string;
  date_end: string;
  metrics: Readonly<Record<string, ApiBivariateMetricSummary>>;
  pearson_diagnostics: Readonly<{
    high_70_pairs: number;
    high_90_pairs: number;
    low_30_pairs: number;
    negative_pairs: number;
    percentile_10?: number | null;
    percentile_50?: number | null;
    percentile_90?: number | null;
    most_correlated_listing?: string | null;
    most_correlated_average?: number | null;
    best_diversifier_listing?: string | null;
    best_diversifier_average?: number | null;
  }>;
  spearman_diagnostics: Readonly<{
    high_70_pairs: number;
    high_90_pairs: number;
    low_30_pairs: number;
    negative_pairs: number;
    percentile_10?: number | null;
    percentile_50?: number | null;
    percentile_90?: number | null;
    average_pearson_gap?: number | null;
    large_pearson_gap_pairs?: number;
    most_correlated_listing?: string | null;
    most_correlated_average?: number | null;
    best_diversifier_listing?: string | null;
    best_diversifier_average?: number | null;
    average_rolling_stability?: number | null;
    cluster_count?: number;
    largest_cluster_size?: number;
  }>;
  downside_diagnostics: Readonly<{
    high_70_pairs: number;
    high_90_pairs: number;
    low_30_pairs: number;
    negative_pairs: number;
    percentile_10?: number | null;
    percentile_50?: number | null;
    percentile_90?: number | null;
    average_pearson_gap?: number | null;
    large_pearson_gap_pairs?: number;
    most_correlated_listing?: string | null;
    most_correlated_average?: number | null;
    best_diversifier_listing?: string | null;
    best_diversifier_average?: number | null;
    worst_pair?: string | null;
    worst_pair_correlation?: number | null;
    median_joint_negative_days?: number | null;
    minimum_joint_negative_days?: number | null;
    average_rolling_stability?: number | null;
    cluster_count?: number;
    largest_cluster_size?: number;
  }>;
  tail_dependence_diagnostics: Readonly<{
    percentile_90?: number | null;
    high_30_pairs: number;
    high_50_pairs: number;
    worst_pair?: string | null;
    worst_pair_tail_dependence?: number | null;
    best_diversifier_pair?: string | null;
    best_diversifier_tail_dependence?: number | null;
    best_diversifier_coexceedance_rate?: number | null;
    most_tail_exposed_listing?: string | null;
    most_tail_exposed_average?: number | null;
    average_joint_loss_severity?: number | null;
    median_joint_tail_events?: number | null;
    minimum_joint_tail_events?: number | null;
    average_rolling_stability?: number | null;
    cluster_threshold?: number;
    cluster_count?: number;
    largest_cluster_size?: number;
  }>;
  coexceedance_diagnostics: Readonly<{
    percentile_90?: number | null;
    independence_baseline: number;
    average_independence_multiple?: number | null;
    high_1_pairs: number;
    high_25_pairs: number;
    high_5_pairs: number;
    worst_pair?: string | null;
    worst_pair_rate?: number | null;
    worst_pair_annual_events?: number | null;
    worst_pair_tail_dependence?: number | null;
    best_diversifier_pair?: string | null;
    best_diversifier_rate?: number | null;
    best_diversifier_tail_dependence?: number | null;
    most_coexposed_listing?: string | null;
    most_coexposed_average?: number | null;
    median_joint_tail_events?: number | null;
    minimum_joint_tail_events?: number | null;
    average_rolling_stability?: number | null;
    cluster_threshold?: number;
    cluster_count?: number;
    largest_cluster_size?: number;
  }>;
  rolling_correlation_diagnostics: Readonly<{
    percentile_90?: number | null;
    high_threshold_pairs: number;
    high_20_pairs: number;
    high_30_pairs: number;
    worst_pair?: string | null;
    worst_value?: number | null;
    best_pair?: string | null;
    best_value?: number | null;
    most_exposed_listing?: string | null;
    most_exposed_average?: number | null;
    window_length: number;
    median_shared_observations?: number | null;
    minimum_shared_observations?: number | null;
    median_window_count?: number | null;
    average_rolling_correlation?: number | null;
    average_correlation_trend?: number | null;
    regime_switch_pairs: number;
    average_regime_switches?: number | null;
    average_stress_correlation?: number | null;
    average_pearson_gap?: number | null;
    average_worst_window_correlation?: number | null;
    worst_window_pair?: string | null;
    worst_window_correlation?: number | null;
    cluster_count: number;
    largest_cluster_size: number;
  }>;
  drawdown_overlap_diagnostics: Readonly<{
    percentile_90?: number | null;
    high_threshold_pairs: number;
    high_25_pairs: number;
    high_50_pairs: number;
    worst_pair?: string | null;
    worst_value?: number | null;
    best_pair?: string | null;
    best_value?: number | null;
    most_exposed_listing?: string | null;
    most_exposed_average?: number | null;
    median_joint_drawdown_days?: number | null;
    minimum_joint_drawdown_days?: number | null;
    average_joint_drawdown_severity?: number | null;
    average_rolling_stability?: number | null;
    average_pearson_correlation?: number | null;
    average_downside_correlation?: number | null;
    high_overlap_low_pearson_pairs: number;
    high_overlap_low_downside_pairs: number;
    cluster_count: number;
    largest_cluster_size: number;
  }>;
}>;

export type ApiPairMetricMatrix = Readonly<{
  labels: readonly Readonly<{ isin: string; exchange: string; code: string; label: string }>[];
  values: readonly (readonly (number | null)[])[];
  observation_count: number;
  date_start: string;
  date_end: string;
}>;

export type ApiTailRiskScatter = Readonly<{
  points: readonly Readonly<{
    left_isin: string;
    left_exchange: string;
    left_code: string;
    right_isin: string;
    right_exchange: string;
    right_code: string;
    tail_dependence: number;
    coexceedance_rate: number;
  }>[];
  pair_count: number;
  observation_count: number;
  date_start: string;
  date_end: string;
  tail_dependence_median: number | null;
  coexceedance_rate_median: number | null;
  diagnostics: Readonly<{
    best_diversifiers: number;
    tail_concentration: number;
    high_tail_only: number;
    high_coexceedance_only: number;
    pareto_best_pair_count: number;
    best_pareto_pair?: string | null;
    worst_tail_risk_pair?: string | null;
    worst_tail_risk_score?: number | null;
    tail_independence_baseline: number;
    coexceedance_independence_baseline: number;
    average_tail_independence_multiple?: number | null;
    average_coexceedance_independence_multiple?: number | null;
    most_concentrated_isin?: string | null;
    upper_right_links: number;
    upper_right_cluster_count: number;
    largest_upper_right_cluster_size: number;
    average_tail_stability?: number | null;
    average_coexceedance_stability?: number | null;
    median_joint_tail_events?: number | null;
    minimum_joint_tail_events?: number | null;
  }>;
}>;

export type ApiCovarianceMatrix = Readonly<{
  labels: readonly Readonly<{ isin: string; exchange: string; code: string; label: string }>[];
  values: readonly (readonly (number | null)[])[];
  observation_count: number;
  date_start: string;
  date_end: string;
  diagnostics: Readonly<{
    listing_count: number;
    pair_count: number;
    observation_count: number;
    average_pairwise_covariance?: number | null;
    average_pairwise_correlation?: number | null;
    equal_weight_volatility?: number | null;
    minimum_variance_volatility?: number | null;
    diversification_ratio?: number | null;
    effective_number_of_bets?: number | null;
    largest_equal_weight_risk_contribution?: number | null;
  }>;
}>;
