
import type { ApiProjectContext, ApiWorkflow } from "../contracts";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
  ) {
    super(code);
  }
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

  const payload = (await response.json().catch(() => ({}))) as { detail?: string };
  if (!response.ok) {
    throw new ApiError(response.status, payload.detail || `request_failed_${response.status}`);
  }
  return payload as T;
}

export function postJson<TResponse>(path: string, body: unknown): Promise<TResponse> {
  return requestJson<TResponse>(path, {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Idempotency-Key": crypto.randomUUID() },
  });
}

export function loadWorkflow(): Promise<ApiWorkflow> {
  return requestJson<ApiWorkflow>("/api/workflow");
}

export function loadProjectContext(): Promise<ApiProjectContext> {
  return requestJson<ApiProjectContext>("/api/project-context");
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
