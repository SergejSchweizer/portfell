/** Univariate Statistics' complete browser-to-API contract. */

import { postJson, requestJson } from "./client";
import type {
  ApiPage,
  ApiResearchRun,
  ApiUnivariateRow,
  ApiUnivariateSelectionSettings,
} from "../contracts";

export type UnivariateRunRequest = Readonly<{
  metadata_selection_id: string;
  quote_run_id: string;
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
