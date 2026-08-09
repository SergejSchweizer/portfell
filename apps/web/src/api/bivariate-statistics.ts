/** Bivariate Statistics' browser-to-API contract. */

import { postJson, requestJson } from "./client";
import type {
  ApiBivariateRow,
  ApiBivariateSummary,
  ApiCovarianceMatrix,
  ApiPage,
  ApiPairMetricMatrix,
  ApiPairPlan,
  ApiResearchRun,
  ApiTailRiskScatter,
} from "../contracts";

export type BivariateSelectionRequest = Readonly<{
  univariate_selection_id: string;
}>;

export type BivariateRunData = Readonly<{
  results: ApiPage<ApiBivariateRow>;
  covariance: ApiCovarianceMatrix;
  summary: ApiBivariateSummary;
  pearson: ApiPairMetricMatrix;
  spearman: ApiPairMetricMatrix;
  downside: ApiPairMetricMatrix;
  lowerTailDependence: ApiPairMetricMatrix;
  tailCoexceedanceRate: ApiPairMetricMatrix;
  tailRiskScatter: ApiTailRiskScatter;
}>;

export type PairMetricMatrixKind = "pearson" | "spearman" | "downside" | "lower_tail_dependence" | "tail_coexceedance_rate";

export const bivariateStatisticsApi = {
  plan: (request: BivariateSelectionRequest): Promise<ApiPairPlan> => (
    postJson<ApiPairPlan>("/api/bivariate-statistics/plan", request)
  ),
  startRun: (request: BivariateSelectionRequest): Promise<ApiResearchRun> => (
    postJson<ApiResearchRun>("/api/bivariate-statistics/runs", request)
  ),
  loadRun: (runId: string): Promise<ApiResearchRun> => (
    requestJson<ApiResearchRun>(`/api/bivariate-statistics/runs/${encodeURIComponent(runId)}`)
  ),
  loadResults: (runId: string): Promise<ApiPage<ApiBivariateRow>> => (
    requestJson<ApiPage<ApiBivariateRow>>(
      `/api/bivariate-statistics/runs/${encodeURIComponent(runId)}/results?limit=50&offset=0`,
    )
  ),
  loadSummary: (runId: string): Promise<ApiBivariateSummary> => (
    requestJson<ApiBivariateSummary>(`/api/bivariate-statistics/runs/${encodeURIComponent(runId)}/summary`)
  ),
  loadCovariance: (runId: string): Promise<ApiCovarianceMatrix> => (
    requestJson<ApiCovarianceMatrix>(
      `/api/bivariate-statistics/runs/${encodeURIComponent(runId)}/covariance-matrix`,
    )
  ),
  loadCorrelation: (
    runId: string,
    metric: PairMetricMatrixKind,
  ): Promise<ApiPairMetricMatrix> => requestJson<ApiPairMetricMatrix>(
    `/api/bivariate-statistics/runs/${encodeURIComponent(runId)}/correlation-matrix?metric=${metric}`,
  ),
  loadTailRiskScatter: (runId: string): Promise<ApiTailRiskScatter> => requestJson<ApiTailRiskScatter>(
    `/api/bivariate-statistics/runs/${encodeURIComponent(runId)}/tail-risk-scatter`,
  ),
  loadRunData: async (runId: string): Promise<BivariateRunData> => {
    const [results, covariance, summary, pearson, spearman, downside, lowerTailDependence, tailCoexceedanceRate, tailRiskScatter] = await Promise.all([
      bivariateStatisticsApi.loadResults(runId),
      bivariateStatisticsApi.loadCovariance(runId),
      bivariateStatisticsApi.loadSummary(runId),
      bivariateStatisticsApi.loadCorrelation(runId, "pearson"),
      bivariateStatisticsApi.loadCorrelation(runId, "spearman"),
      bivariateStatisticsApi.loadCorrelation(runId, "downside"),
      bivariateStatisticsApi.loadCorrelation(runId, "lower_tail_dependence"),
      bivariateStatisticsApi.loadCorrelation(runId, "tail_coexceedance_rate"),
      bivariateStatisticsApi.loadTailRiskScatter(runId),
    ]);
    return { results, covariance, summary, pearson, spearman, downside, lowerTailDependence, tailCoexceedanceRate, tailRiskScatter };
  },
};
