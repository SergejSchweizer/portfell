
import type { ApiCredentialStatus, ApiCredentialValue, ApiInitialFill, ApiMetadataFetch, ApiProjectContext, ApiProjectMetadataBuilder, ApiWorkflow } from "../contracts";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
  ) {
    super(code);
  }
}

function createIdempotencyKey(): string {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }

  const bytes = new Uint8Array(16);
  if (typeof globalThis.crypto?.getRandomValues === "function") {
    globalThis.crypto.getRandomValues(bytes);
  } else {
    for (let index = 0; index < bytes.length; index += 1) {
      bytes[index] = Math.floor(Math.random() * 256);
    }
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method || "GET").toUpperCase();
  const response = await fetch(path, {
    ...init,
    headers: {
      accept: "application/json",
      ...(method === "GET" || method === "HEAD" ? {} : { "content-type": "application/json" }),
      ...(init.headers || {}),
    },
  });

  const payload = (await response.json().catch(() => ({}))) as {
    detail?: string | { code?: string };
  };
  if (!response.ok) {
    const code = typeof payload.detail === "string" ? payload.detail : payload.detail?.code;
    throw new ApiError(response.status, code || `request_failed_${response.status}`);
  }
  return payload as T;
}

export function postJson<TResponse>(path: string, body: unknown): Promise<TResponse> {
  return requestJson<TResponse>(path, {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Idempotency-Key": createIdempotencyKey() },
  });
}

export function loadWorkflow(): Promise<ApiWorkflow> {
  return requestJson<ApiWorkflow>("/api/workflow");
}

export function loadEodhdCredentialStatus(): Promise<ApiCredentialStatus> {
  return requestJson<ApiCredentialStatus>("/api/credentials/eodhd");
}

export function loadEodhdCredentialValue(): Promise<ApiCredentialValue> {
  return requestJson<ApiCredentialValue>("/api/credentials/eodhd/value");
}

export function loadMetadataFetchRun(metadataRunId: string): Promise<ApiMetadataFetch> {
  return requestJson<ApiMetadataFetch>(`/api/metadata/fetch-all/${encodeURIComponent(metadataRunId)}`);
}

export function loadProjectContext(): Promise<ApiProjectContext> {
  return requestJson<ApiProjectContext>("/api/project-context");
}

export function loadProjectMetadataBuilder(projectId: string): Promise<ApiProjectMetadataBuilder> {
  return requestJson<ApiProjectMetadataBuilder>(`/api/projects/${encodeURIComponent(projectId)}/metadata-builder`);
}

export function loadProjectInitialFill(projectId: string): Promise<ApiInitialFill> {
  return requestJson<ApiInitialFill>(`/api/projects/${encodeURIComponent(projectId)}/initial-fill`);
}

export function selectCurrentProject(projectId: string): Promise<ApiProjectContext> {
  return requestJson<ApiProjectContext>("/api/project-context/current-project", {
    method: "PUT",
    body: JSON.stringify({ project_id: projectId }),
  });
}

export function loadProjectWorkflow(projectId: string): Promise<ApiWorkflow> {
  return requestJson<ApiWorkflow>(`/api/projects/${encodeURIComponent(projectId)}/workflow`);
}
