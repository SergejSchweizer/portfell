/** Typed transport facade for persisted Multivariate Statistics results. */

import { postJson, requestJson } from "./client";
import type {
  ApiMultivariateCandidates,
  ApiMultivariateComponents,
  ApiMultivariateArtifacts,
  ApiMultivariateIncomeEvidenceList,
  ApiMultivariateRiskContributions,
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

function riskContributionsPath(runId: string, candidateId?: string): string {
  const path = `/api/multivariate-statistics/runs/${encodeURIComponent(runId)}/risk-contributions`;
  return candidateId ? `${path}?candidate_id=${encodeURIComponent(candidateId)}` : path;
}

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
  loadArtifacts: (runId: string): Promise<ApiMultivariateArtifacts> => (
    requestJson<ApiMultivariateArtifacts>(`/api/multivariate-statistics/runs/${encodeURIComponent(runId)}/artifacts`)
  ),
  loadComponents: (runId: string, limit = 25, offset = 0): Promise<ApiMultivariateComponents> => (
    requestJson<ApiMultivariateComponents>(
      `/api/multivariate-statistics/runs/${encodeURIComponent(runId)}/components?limit=${limit}&offset=${offset}`,
    )
  ),
  loadRiskContributions: (runId: string, candidateId?: string): Promise<ApiMultivariateRiskContributions> => (
    requestJson<ApiMultivariateRiskContributions>(riskContributionsPath(runId, candidateId))
  ),
  loadIncomeEvidence: (runId: string): Promise<ApiMultivariateIncomeEvidenceList> => (
    requestJson<ApiMultivariateIncomeEvidenceList>(`/api/multivariate-statistics/runs/${encodeURIComponent(runId)}/income-evidence`)
  ),
  saveSelectedCandidates: (runId: string, selectedCandidateIds: readonly string[]): Promise<ApiMultivariateRun> => (
    requestJson<ApiMultivariateRun>(`/api/multivariate-statistics/runs/${encodeURIComponent(runId)}/settings`, {
      method: "PATCH",
      body: JSON.stringify({ selected_candidate_ids: selectedCandidateIds }),
    })
  ),
};
