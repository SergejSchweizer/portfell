import { afterEach, describe, expect, it, vi } from "vitest";
import { canSelectUiFixture, readPublicRuntimeEnv } from "../../src/env";
import { currentWorkflowPage, workflowModules, workflowPages } from "../../src/routes";

describe("runtime environment and routes", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("reads production and fixture runtime modes", () => {
    vi.stubEnv("VITE_PORTFELL_UI_FIXTURE_MODE", "production");
    vi.stubEnv("VITE_PORTFELL_UI_FIXTURE", "saved-fixture");
    vi.stubEnv("VITE_PORTFELL_API_BASE_URL", "https://api.example");
    window.history.pushState({}, "", "/?fixture=query-fixture");
    expect(readPublicRuntimeEnv()).toEqual({ apiBaseUrl: "https://api.example", uiFixture: "", uiFixtureMode: "production" });

    vi.stubEnv("VITE_PORTFELL_UI_FIXTURE_MODE", "test");
    expect(readPublicRuntimeEnv()).toMatchObject({ uiFixture: "saved-fixture", uiFixtureMode: "test" });
    vi.stubEnv("VITE_PORTFELL_UI_FIXTURE", "");
    expect(readPublicRuntimeEnv()).toMatchObject({ uiFixture: "query-fixture" });
  });

  it("allows only test and local development fixture modes", () => {
    expect(canSelectUiFixture("test")).toBe(true);
    expect(canSelectUiFixture("local-dev")).toBe(true);
    expect(canSelectUiFixture("production")).toBe(false);
  });

  it("falls back safely when the location cannot be parsed", () => {
    vi.stubGlobal("URL", class {
      constructor() {
        throw new Error("invalid location");
      }
    });
    vi.stubEnv("VITE_PORTFELL_UI_FIXTURE_MODE", "local-dev");
    vi.stubEnv("VITE_PORTFELL_UI_FIXTURE", "");

    expect(readPublicRuntimeEnv()).toMatchObject({ uiFixture: "", uiFixtureMode: "local-dev" });
  });

  it("registers and resolves every workflow page with a metadata fallback", () => {
    expect(workflowPages.map((page) => page.path)).toEqual([
      "/metadata-builder",
      "/univariate-statistics",
      "/bivariate-statistics",
      "/multivariate-statistics",
    ]);
    for (const page of workflowPages) expect(currentWorkflowPage(page.path)).toBe(page);
    expect(currentWorkflowPage("/not-a-route")).toBe(workflowPages[0]);
  });

  it("assigns every browser page to one explicit workflow module", () => {
    expect(workflowModules.map((module) => module.id)).toEqual([
      "metadata_builder",
      "univariate_statistics",
      "bivariate_statistics",
      "multivariate_statistics",
    ]);
    for (const page of workflowPages) {
      expect(workflowModules.some((module) => module.id === page.moduleId)).toBe(true);
    }
  });
});
