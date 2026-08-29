import { describe, expect, it } from "vitest";
import { relativePerformanceValues } from "../../src/pages/multivariate-statistics";

describe("relativePerformanceValues", () => {
  it("rebases the selected evaluation interval to zero with compounded returns", () => {
    const values = relativePerformanceValues([
      { date: "2023-12-29", return: 0.5 },
      { date: "2024-01-02", return: 0.1 },
      { date: "2024-02-01", return: 0.32 },
    ], Date.parse("2024-01-01"), Date.parse("2024-12-31"));

    expect(values[0]).toEqual({ date: "2024-01-02", return: 0 });
    expect(values[1]?.date).toBe("2024-02-01");
    expect(values[1]?.return).toBeCloseTo(0.2);
  });
});