/** Univariate Statistics' browser-to-API contract, including its filter sub-flow. */

import { postJson, requestJson } from "./client";
import type {
  ApiFilterSelection,
  ApiMetricList,
  ApiPage,
  ApiQuoteFetch,
  ApiResearchRun,
  ApiUnivariateRow,
  ApiUnivariateSelectionSettings,
} from "../contracts";

export type UnivariateRunRequest = Readonly<{
  metadata_selection_id: string;
  quote_run_id: string;
}>;

export type QuoteRunRequest = Readonly<{
  metadata_selection_id: string;
}>;

export type UnivariateFilterRequest = Readonly<{
  source_run_id: string;
  predicates: readonly Readonly<{ metric: string; operator: string; value: number }>[];
}>;

export const univariateStatisticsApi = {
  startRun: (request: UnivariateRunRequest): Promise<ApiResearchRun> => (
    postJson<ApiResearchRun>("/api/univariate-statistics/runs", request)
  ),
  loadRun: (runId: string): Promise<ApiResearchRun> => (
    requestJson<ApiResearchRun>(`/api/univariate-statistics/runs/${encodeURIComponent(runId)}`)
  ),
  loadResults: (runId: string, limit: number, offset: number): Promise<ApiPage<ApiUnivariateRow>> => (
    requestJson<ApiPage<ApiUnivariateRow>>(
      `/api/univariate-statistics/runs/${encodeURIComponent(runId)}/results?limit=${limit}&offset=${offset}`,
    )
  ),
  startQuoteRun: (request: QuoteRunRequest): Promise<ApiQuoteFetch> => (
    postJson<ApiQuoteFetch>("/api/quote-runs", request)
  ),
  loadSelectionSettings: (projectId: string): Promise<ApiUnivariateSelectionSettings> => (
    requestJson<ApiUnivariateSelectionSettings>(
      `/api/projects/${encodeURIComponent(projectId)}/univariate-selection-settings`,
    )
  ),
  saveSelectionSettings: (
    projectId: string,
    settings: ApiUnivariateSelectionSettings,
  ): Promise<ApiUnivariateSelectionSettings> => requestJson<ApiUnivariateSelectionSettings>(
    `/api/projects/${encodeURIComponent(projectId)}/univariate-selection-settings`,
    { method: "PUT", body: JSON.stringify(settings) },
  ),
  loadFilterMetrics: (): Promise<ApiMetricList> => requestJson<ApiMetricList>("/api/univariate-filter/metrics"),
  applyFilter: (request: UnivariateFilterRequest): Promise<ApiFilterSelection> => (
    postJson<ApiFilterSelection>("/api/univariate-filter", request)
  ),
  loadFilterResults: (selectionId: string, limit: number, offset: number): Promise<ApiPage<ApiUnivariateRow>> => (
    requestJson<ApiPage<ApiUnivariateRow>>(
      `/api/univariate-filter/${encodeURIComponent(selectionId)}/results?limit=${limit}&offset=${offset}`,
    )
  ),
};
