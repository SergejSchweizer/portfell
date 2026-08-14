/** Univariate Statistics' complete browser-to-API contract. */

import { postJson, requestJson } from "./client";
import type {
  ApiAnalyticalPageView,
  ApiLazyPage,
  ApiPage,
  ApiResearchRun,
  ApiUnivariateRow,
  ApiUnivariateSelectionSettings,
} from "../contracts";

export type UnivariateRunRequest = Readonly<{
  metadata_selection_id: string;
}>;

export const univariateStatisticsApi = {
  startRun: (request: UnivariateRunRequest): Promise<ApiResearchRun> => (
    postJson<ApiResearchRun>("/api/univariate-statistics/runs", request)
  ),
  loadRun: (runId: string): Promise<ApiResearchRun> => (
    requestJson<ApiResearchRun>(`/api/univariate-statistics/runs/${encodeURIComponent(runId)}`)
  ),
  loadPageView: (projectId: string, signal?: AbortSignal): Promise<ApiAnalyticalPageView> => (
    requestJson<ApiAnalyticalPageView>(
      `/api/projects/${encodeURIComponent(projectId)}/views/univariate-statistics`,
      { signal },
    )
  ),
  loadResultsSection: (
    projectId: string,
    cursor?: string,
    signal?: AbortSignal,
  ): Promise<ApiLazyPage<ApiUnivariateRow>> => {
    const path = `/api/projects/${encodeURIComponent(projectId)}/views/univariate_statistics/sections/results`;
    return requestJson<ApiLazyPage<ApiUnivariateRow>>(
      cursor === undefined ? path : `${path}?cursor=${encodeURIComponent(cursor)}`,
      { signal },
    );
  },
  loadResults: (runId: string, limit: number, offset: number): Promise<ApiPage<ApiUnivariateRow>> => (
    requestJson<ApiPage<ApiUnivariateRow>>(
      `/api/univariate-statistics/runs/${encodeURIComponent(runId)}/results?limit=${limit}&offset=${offset}`,
    )
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
};
