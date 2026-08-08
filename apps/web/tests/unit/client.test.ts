import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  loadEodhdCredentialStatus,
  loadEodhdCredentialValue,
  loadMetadataFetchRun,
  loadProjectContext,
  loadProjectMetadataFilter,
  loadProjectWorkflow,
  loadQuoteRun,
  loadWorkflow,
  postJson,
  requestJson,
  selectCurrentProject,
} from "../../src/api/client";

function response(payload: unknown, ok = true, status = 200): Response {
  return { ok, status, json: vi.fn().mockResolvedValue(payload) } as unknown as Response;
}

describe("API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("serializes GET and non-GET requests with the expected headers", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ value: 1 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(requestJson<{ value: number }>("/api/example")).resolves.toEqual({ value: 1 });
    await requestJson("/api/example", { method: "PATCH", headers: { "X-Test": "yes" } });

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/example", expect.objectContaining({ headers: { accept: "application/json" } }));
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/example", expect.objectContaining({ headers: { accept: "application/json", "content-type": "application/json", "X-Test": "yes" } }));
  });

  it("maps every safe API error representation", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ detail: "missing_project" }, false, 404))
      .mockResolvedValueOnce(response({ detail: { code: "forbidden" } }, false, 403))
      .mockResolvedValueOnce({ ok: false, status: 502, json: vi.fn().mockRejectedValue(new Error("invalid json")) });
    vi.stubGlobal("fetch", fetchMock);

    await expect(requestJson("/one")).rejects.toMatchObject({ status: 404, code: "missing_project" } satisfies Partial<ApiError>);
    await expect(requestJson("/two")).rejects.toMatchObject({ status: 403, code: "forbidden" } satisfies Partial<ApiError>);
    await expect(requestJson("/three")).rejects.toMatchObject({ status: 502, code: "request_failed_502" } satisfies Partial<ApiError>);
  });

  it("adds idempotency keys from randomUUID and both random-byte fallbacks", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ created: true }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", { randomUUID: () => "00000000-0000-4000-8000-000000000000" });

    await postJson("/api/create", { name: "UUID" });
    vi.stubGlobal("crypto", { getRandomValues: (bytes: Uint8Array) => bytes.fill(7) });
    await postJson("/api/create", { name: "Bytes" });
    vi.stubGlobal("crypto", {});
    vi.spyOn(Math, "random").mockReturnValue(0.5);
    await postJson("/api/create", { name: "Math" });

    expect(fetchMock).toHaveBeenCalledWith("/api/create", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ name: "Math" }),
      headers: expect.objectContaining({ "Idempotency-Key": expect.stringMatching(/^[0-9a-f-]{36}$/) }),
    }));
  });

  it("maps each typed endpoint to its canonical route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({}));
    vi.stubGlobal("fetch", fetchMock);

    await Promise.all([
      loadWorkflow(), loadEodhdCredentialStatus(), loadEodhdCredentialValue(), loadMetadataFetchRun("run/a"), loadProjectContext(), loadProjectMetadataFilter("project/a"), selectCurrentProject("project/a"), loadProjectWorkflow("project/a"), loadQuoteRun("quote/a"),
    ]);

    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([
      "/api/workflow", "/api/credentials/eodhd", "/api/credentials/eodhd/value", "/api/metadata/fetch-all/run%2Fa", "/api/project-context", "/api/projects/project%2Fa/metadata-filter", "/api/project-context/current-project", "/api/projects/project%2Fa/workflow", "/api/quote-runs/quote%2Fa",
    ]);
  });
});
