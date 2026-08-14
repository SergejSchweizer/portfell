import { describe, expect, it } from "vitest";
import { queryClient, queryTiming } from "../../src/query/client";
import { queryKeys } from "../../src/query/keys";

describe("browser query policy", () => {
  it("uses stable project-scoped keys and bounded memory defaults", () => {
    expect(queryKeys.workflow("project-a")).toEqual(["workflow", "project-a"]);
    expect(queryKeys.workflow("project-b")).not.toEqual(queryKeys.workflow("project-a"));
    expect(queryKeys.section("project-a", "bivariate_statistics", "summary", "revision-1"))
      .toEqual(["section", "project-a", "bivariate_statistics", "summary", "revision-1"]);
    expect(queryClient.getDefaultOptions().queries).toMatchObject({
      gcTime: 15 * 60_000,
      retry: 2,
      staleTime: queryTiming.completed,
    });
    expect(queryClient.getDefaultOptions().mutations).toMatchObject({ retry: false });
  });
});
