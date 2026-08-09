/** Typed transport facade for persisted Multivariate Statistics results. */

import { postJson, requestJson } from "./client";
import type {
  ApiMultivariateCandidates,
  ApiMultivariateRun,
  ApiMultivariateStructure,
  ApiMultivariateSummary,
  ApiMultivariateValidation,
} from "../contracts";

export type MultivariateRunRequest = Readonly<{
  project_id: string;
  bivariate_run_id: string;
  settings?: Readonly<Record<string, unknown>>;
}>;

export const multivariateStatisticsApi = {
  startRun: (request: MultivariateRunRequest): Promise<ApiMultivariateRun> => (
    postJson<ApiMultivariateRun>("/api/multivariate-statistics/runs", request)
  ),
  loadRun: (runId: string): Promise<ApiMultivariateRun> => (
    requestJson<ApiMultivariateRun>(`/api/multivariate-statistics/runs/${encodeURIComponent(runId)}`)
  ),
  loadSummary: (runId: string): Promise<ApiMultivariateSummary> => (
    requestJson<ApiMultivariateSummary>(`/api/multivariate-statistics/runs/${encodeURIComponent(runId)}/summary`)
  ),
  loadStructure: (runId: string): Promise<ApiMultivariateStructure> => (
    requestJson<ApiMultivariateStructure>(`/api/multivariate-statistics/runs/${encodeURIComponent(runId)}/structure`)
  ),
  loadCandidates: (runId: string): Promise<ApiMultivariateCandidates> => (
    requestJson<ApiMultivariateCandidates>(`/api/multivariate-statistics/runs/${encodeURIComponent(runId)}/candidates`)
  ),
  loadValidation: (runId: string): Promise<ApiMultivariateValidation> => (
    requestJson<ApiMultivariateValidation>(`/api/multivariate-statistics/runs/${encodeURIComponent(runId)}/validation`)
  ),
};
