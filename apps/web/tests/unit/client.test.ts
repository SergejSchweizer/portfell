import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  loadEodhdCredentialStatus,
  loadMetadataFetchRun,
  loadProjectContext,
  loadProjectInitialFill,
  loadProjectMetadataBuilder,
  loadProjectWorkflow,
  loadWorkflow,
  postJson,
  requestJson,
  selectCurrentProject,
} from "../../src/api/client";
import { metadataBuilderApi } from "../../src/api/metadata-builder";
import { univariateStatisticsApi } from "../../src/api/univariate-statistics";
import { bivariateStatisticsApi } from "../../src/api/bivariate-statistics";
import { multivariateStatisticsApi } from "../../src/api/multivariate-statistics";
import type { ApiUnivariateSelectionSettings } from "../../src/contracts";

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
      loadWorkflow(), loadEodhdCredentialStatus(), loadMetadataFetchRun("run/a"), loadProjectContext(), loadProjectMetadataBuilder("project/a"), loadProjectInitialFill("project/a"), selectCurrentProject("project/a"), loadProjectWorkflow("project/a"),
    ]);

    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([
      "/api/workflow", "/api/credentials/eodhd", "/api/metadata/fetch-all/run%2Fa", "/api/project-context", "/api/projects/project%2Fa/metadata-builder", "/api/projects/project%2Fa/initial-fill", "/api/project-context/current-project", "/api/projects/project%2Fa/workflow",
    ]);
  });

  it("keeps every workflow module facade within its published API contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({}));
    vi.stubGlobal("fetch", fetchMock);
    const metadataRequest = { exchange: "XETRA", name: "fund", instrument_type: "ETF", country: "DE", currency: "EUR" };
    const univariateRequest = { metadata_selection_id: "selection/a", quote_run_id: "quote/a" };
    const settings: ApiUnivariateSelectionSettings = { dividend_frequencies: ["monthly"], statistic_labels: {}, statistic_ranges: {} };
    const bivariateRequest = { univariate_selection_id: "selection/a" };
    const multivariateRequest = { project_id: "project/a", bivariate_run_id: "run/a", settings: { target: "monthly-income" } };

    await Promise.all([
      metadataBuilderApi.loadCredentialStatus(), metadataBuilderApi.loadFetchRun("run/a"),
      metadataBuilderApi.loadProjectCriteria("project/a"), metadataBuilderApi.loadPageView("project/a"), metadataBuilderApi.loadFieldOptions(), metadataBuilderApi.saveCredential("key"),
      metadataBuilderApi.fetchAll(), metadataBuilderApi.createProject(metadataRequest), metadataBuilderApi.loadInitialFill("project/a"),
      univariateStatisticsApi.startRun(univariateRequest), univariateStatisticsApi.loadRun("run/a"), univariateStatisticsApi.loadResults("run/a", 10, 5),
      univariateStatisticsApi.loadPageView("project/a"), univariateStatisticsApi.loadResultsSection("project/a", "cursor/a"),
      univariateStatisticsApi.loadSelectionSettings("project/a"),
      univariateStatisticsApi.saveSelectionSettings("project/a", settings),
      bivariateStatisticsApi.plan(bivariateRequest), bivariateStatisticsApi.startRun(bivariateRequest), bivariateStatisticsApi.loadRun("run/a"), bivariateStatisticsApi.loadPageView("project/a"),
      bivariateStatisticsApi.loadRunData("run/a"),
      bivariateStatisticsApi.loadSection("project/a", "summary"),
      bivariateStatisticsApi.loadSection("project/a", "correlation_matrix", "downside"),
      multivariateStatisticsApi.startRun(multivariateRequest), multivariateStatisticsApi.loadRun("run/a"),
      multivariateStatisticsApi.loadPageView("project/a"), multivariateStatisticsApi.loadSection("project/a", "summary"),
      multivariateStatisticsApi.loadSummary("run/a"), multivariateStatisticsApi.loadStructure("run/a"),
      multivariateStatisticsApi.loadCandidates("run/a"), multivariateStatisticsApi.loadValidation("run/a"),
      multivariateStatisticsApi.loadArtifacts("run/a"), multivariateStatisticsApi.loadPerformance("run/a"), multivariateStatisticsApi.loadComponents("run/a", 10, 5),
      multivariateStatisticsApi.loadRiskContributions("run/a"), multivariateStatisticsApi.loadRiskContributions("run/a", "candidate/a"),
      multivariateStatisticsApi.loadIncomeEvidence("run/a"),
    ]);

    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual(expect.arrayContaining([
      "/api/metadata-builder/options", "/api/metadata-builder", "/api/projects/project%2Fa/views/metadata-builder", "/api/projects/project%2Fa/initial-fill", "/api/univariate-statistics/runs",
      "/api/univariate-statistics/runs/run%2Fa/results?limit=10&offset=5", "/api/bivariate-statistics/plan", "/api/projects/project%2Fa/views/bivariate-statistics",
      "/api/projects/project%2Fa/views/univariate-statistics",
      "/api/projects/project%2Fa/views/univariate_statistics/sections/results?cursor=cursor%2Fa",
      "/api/bivariate-statistics/runs/run%2Fa/covariance-matrix",
      "/api/bivariate-statistics/runs/run%2Fa/correlation-matrix?metric=downside",
      "/api/bivariate-statistics/runs/run%2Fa/correlation-matrix?metric=lower_tail_dependence",
      "/api/bivariate-statistics/runs/run%2Fa/correlation-matrix?metric=tail_coexceedance_rate",
      "/api/bivariate-statistics/runs/run%2Fa/correlation-matrix?metric=rolling_stability",
      "/api/bivariate-statistics/runs/run%2Fa/correlation-matrix?metric=drawdown_overlap",
      "/api/bivariate-statistics/runs/run%2Fa/tail-risk-scatter",
      "/api/projects/project%2Fa/views/bivariate_statistics/sections/summary",
      "/api/projects/project%2Fa/views/bivariate_statistics/sections/correlation_matrix?metric=downside",
      "/api/multivariate-statistics/runs",
      "/api/multivariate-statistics/runs/run%2Fa",
      "/api/projects/project%2Fa/views/multivariate-statistics",
      "/api/projects/project%2Fa/views/multivariate_statistics/sections/summary",
      "/api/multivariate-statistics/runs/run%2Fa/summary",
      "/api/multivariate-statistics/runs/run%2Fa/structure",
      "/api/multivariate-statistics/runs/run%2Fa/candidates",
      "/api/multivariate-statistics/runs/run%2Fa/validation",
      "/api/multivariate-statistics/runs/run%2Fa/artifacts",
      "/api/multivariate-statistics/runs/run%2Fa/performance",
      "/api/multivariate-statistics/runs/run%2Fa/components?limit=10&offset=5",
      "/api/multivariate-statistics/runs/run%2Fa/risk-contributions",
      "/api/multivariate-statistics/runs/run%2Fa/risk-contributions?candidate_id=candidate%2Fa",
      "/api/multivariate-statistics/runs/run%2Fa/income-evidence",
    ]));
  });
});
