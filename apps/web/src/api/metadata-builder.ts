/** Metadata Builder's complete browser-to-API contract. */

import {
  loadEodhdCredentialStatus,
  loadMetadataBuilderPageView,
  loadMetadataFetchRun,
  loadProjectInitialFill,
  loadProjectMetadataBuilder,
  postJson,
  requestJson,
} from "./client";
import type {
  ApiCredentialStatus,
  ApiFieldOptions,
  ApiInitialFill,
  ApiMetadataFetch,
  ApiMetadataBuilderPageView,
  ApiMetadataProject,
  ApiProjectMetadataBuilder,
} from "../contracts";

export type MetadataBuilderCriteriaRequest = Readonly<{
  exchange: string;
  name: string;
  instrument_type: string;
  country: string;
  currency: string;
}>;

export const metadataBuilderApi = {
  loadCredentialStatus: (): Promise<ApiCredentialStatus> => loadEodhdCredentialStatus(),
  loadFetchRun: (runId: string): Promise<ApiMetadataFetch> => loadMetadataFetchRun(runId),
  loadProjectCriteria: (projectId: string): Promise<ApiProjectMetadataBuilder> => (
    loadProjectMetadataBuilder(projectId)
  ),
  loadInitialFill: (projectId: string): Promise<ApiInitialFill> => loadProjectInitialFill(projectId),
  loadPageView: (projectId: string): Promise<ApiMetadataBuilderPageView> => (
    loadMetadataBuilderPageView(projectId)
  ),
  loadFieldOptions: (): Promise<ApiFieldOptions> => requestJson<ApiFieldOptions>("/api/metadata-builder/options"),
  saveCredential: (providerKey: string): Promise<ApiCredentialStatus> => (
    postJson<ApiCredentialStatus>("/api/credentials/eodhd", { provider_key: providerKey })
  ),
  fetchAll: (): Promise<ApiMetadataFetch> => postJson<ApiMetadataFetch>("/api/metadata/fetch-all", {}),
  createProject: (request: MetadataBuilderCriteriaRequest): Promise<ApiMetadataProject> => (
    postJson<ApiMetadataProject>("/api/metadata-builder", request)
  ),
};
