/** Metadata Builder's complete browser-to-API contract. */

import {
  loadEodhdCredentialStatus,
  loadEodhdCredentialValue,
  loadMetadataFetchRun,
  loadProjectMetadataFilter,
  postJson,
  requestJson,
} from "./client";
import type {
  ApiCredentialStatus,
  ApiCredentialValue,
  ApiFieldOptions,
  ApiMetadataFetch,
  ApiMetadataProject,
  ApiProjectMetadataFilter,
} from "../contracts";

export type MetadataBuilderFilterRequest = Readonly<{
  exchange: string;
  name: string;
  instrument_type: string;
  country: string;
  currency: string;
}>;

export const metadataBuilderApi = {
  loadCredentialStatus: (): Promise<ApiCredentialStatus> => loadEodhdCredentialStatus(),
  loadCredentialValue: (): Promise<ApiCredentialValue> => loadEodhdCredentialValue(),
  loadFetchRun: (runId: string): Promise<ApiMetadataFetch> => loadMetadataFetchRun(runId),
  loadProjectFilter: (projectId: string): Promise<ApiProjectMetadataFilter> => (
    loadProjectMetadataFilter(projectId)
  ),
  loadFieldOptions: (): Promise<ApiFieldOptions> => requestJson<ApiFieldOptions>("/api/metadata-filter/options"),
  saveCredential: (providerKey: string): Promise<ApiCredentialStatus> => (
    postJson<ApiCredentialStatus>("/api/credentials/eodhd", { provider_key: providerKey })
  ),
  fetchAll: (): Promise<ApiMetadataFetch> => postJson<ApiMetadataFetch>("/api/metadata/fetch-all", {}),
  createProject: (request: MetadataBuilderFilterRequest): Promise<ApiMetadataProject> => (
    postJson<ApiMetadataProject>("/api/metadata-filter", request)
  ),
};
