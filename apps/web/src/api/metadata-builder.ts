/** Metadata Builder's complete browser-to-API contract. */

import {
  loadEodhdCredentialStatus,
  loadEodhdCredentialValue,
  loadMetadataFetchRun,
  loadProjectMetadataBuilder,
  loadQuoteRun,
  postJson,
  requestJson,
} from "./client";
import type {
  ApiCredentialStatus,
  ApiCredentialValue,
  ApiFieldOptions,
  ApiMetadataFetch,
  ApiMetadataProject,
  ApiProjectMetadataBuilder,
  ApiQuoteFetch,
} from "../contracts";

export type MetadataBuilderCriteriaRequest = Readonly<{
  exchange: string;
  name: string;
  instrument_type: string;
  country: string;
  currency: string;
}>;

export type QuoteRunRequest = Readonly<{
  metadata_selection_id: string;
}>;

export const metadataBuilderApi = {
  loadCredentialStatus: (): Promise<ApiCredentialStatus> => loadEodhdCredentialStatus(),
  loadCredentialValue: (): Promise<ApiCredentialValue> => loadEodhdCredentialValue(),
  loadFetchRun: (runId: string): Promise<ApiMetadataFetch> => loadMetadataFetchRun(runId),
  loadProjectCriteria: (projectId: string): Promise<ApiProjectMetadataBuilder> => (
    loadProjectMetadataBuilder(projectId)
  ),
  loadFieldOptions: (): Promise<ApiFieldOptions> => requestJson<ApiFieldOptions>("/api/metadata-builder/options"),
  saveCredential: (providerKey: string): Promise<ApiCredentialStatus> => (
    postJson<ApiCredentialStatus>("/api/credentials/eodhd", { provider_key: providerKey })
  ),
  fetchAll: (): Promise<ApiMetadataFetch> => postJson<ApiMetadataFetch>("/api/metadata/fetch-all", {}),
  createProject: (request: MetadataBuilderCriteriaRequest): Promise<ApiMetadataProject> => (
    postJson<ApiMetadataProject>("/api/metadata-builder", request)
  ),
  startQuoteRun: (request: QuoteRunRequest): Promise<ApiQuoteFetch> => (
    postJson<ApiQuoteFetch>("/api/quote-runs", request)
  ),
  loadQuoteRun: (runId: string): Promise<ApiQuoteFetch> => loadQuoteRun(runId),
};
