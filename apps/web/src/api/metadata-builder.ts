/** Metadata Builder's complete browser-to-API contract. */

import {
  loadEodhdCredentialStatus,
  loadMetadataBuilderPageView,
  loadProjectMetadataBuilder,
  postJson,
  requestJson,
} from "./client";
import type {
  ApiCredentialStatus,
  ApiFieldOptions,
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
  loadProjectCriteria: (projectId: string): Promise<ApiProjectMetadataBuilder> => (
    loadProjectMetadataBuilder(projectId)
  ),
  loadPageView: (projectId: string, signal?: AbortSignal): Promise<ApiMetadataBuilderPageView> => (
    loadMetadataBuilderPageView(projectId, signal)
  ),
  loadFieldOptions: (): Promise<ApiFieldOptions> => requestJson<ApiFieldOptions>("/api/metadata-builder/options"),
  saveCredential: (providerKey: string): Promise<ApiCredentialStatus> => (
    postJson<ApiCredentialStatus>("/api/credentials/eodhd", { provider_key: providerKey })
  ),
  createProject: (request: MetadataBuilderCriteriaRequest): Promise<ApiMetadataProject> => (
    postJson<ApiMetadataProject>("/api/metadata-builder", request)
  ),
};
