import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EmptyState } from "../../src/components/empty-state";
import { Field } from "../../src/components/field";
import { InlineNotice } from "../../src/components/inline-notice";
import { LoadingState } from "../../src/components/loading-state";
import { Panel } from "../../src/components/panel";
import { StatusBadge } from "../../src/components/status-badge";
import { initialFillStatusMessage } from "../../src/pages/metadata-builder";
import { univariateProgress } from "../../src/pages/univariate-statistics";

describe("shared React components", () => {
  it("renders optional empty-state, panel, loading, and field content", () => {
    const { rerender } = render(<EmptyState title="No projects" description="Create one" action={<span>Start</span>} />);
    expect(screen.getByRole("region", { name: "No projects" })).toHaveTextContent("Create one");
    expect(screen.getByText("Start")).toBeVisible();

    rerender(<><Panel title="Panel title"><span>Body</span></Panel><Panel><span>Untitled</span></Panel><LoadingState label="Fetching"><span>Details</span></LoadingState><Field label="Limit" htmlFor="limit" hint="Optional"><input id="limit" /></Field></>);
    expect(screen.getByRole("heading", { name: "Panel title" })).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Untitled" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Fetching")).toHaveTextContent("Details");
    expect(screen.getByText("Optional")).not.toHaveAttribute("role", "alert");

    rerender(<Field label="Limit" htmlFor="limit"><input id="limit" /></Field>);
    expect(screen.getByLabelText("Limit").parentElement?.querySelector("small")).toBeInTheDocument();

    rerender(<Field label="Limit" htmlFor="limit" error="Required"><input id="limit" /></Field>);
    expect(screen.getByRole("alert")).toHaveTextContent("Required");
  });

  it("renders notice and status semantics", () => {
    render(<><InlineNotice>Saved</InlineNotice><InlineNotice tone="error">Failed</InlineNotice><StatusBadge>Idle</StatusBadge><StatusBadge tone="running">Running</StatusBadge></>);

    expect(screen.getByRole("status")).toHaveTextContent("Saved");
    expect(screen.getByRole("alert")).toHaveTextContent("Failed");
    expect(screen.getByText("Idle")).toHaveClass("portfell-status-badge--neutral");
    expect(screen.getByText("Running")).toHaveClass("portfell-status-badge--running");
  });

  it("adds failed ISINs to a terminal initial-fill status", () => {
    const fill = {
      bootstrap_id: "bootstrap-1",
      job_id: "job-1",
      status: "failed" as const,
      completed_units: 2,
      total_units: 2,
      selected_listing_count: 2,
      failed_listing_count: 1,
      terminal_code: "initial_fill_failed",
      started_at: null,
      last_progress_at: null,
    };

    expect(initialFillStatusMessage("2 unique ISINs selected.", fill)).toBe(
      "2 unique ISINs selected. 1 ISIN failed to load.",
    );
    expect(initialFillStatusMessage("2 unique ISINs selected.", { ...fill, status: "running" })).toBe(
      "2 unique ISINs selected.",
    );
  });

  it("uses processed listings as the univariate progress bar scale", () => {
    expect(univariateProgress({
      run_id: "run-1",
      status: "running",
      total: 1_752,
      completed: 18,
      failed: 2,
      percent: 1,
    })).toEqual({ max: 1_752, value: 20 });
    expect(univariateProgress(null)).toEqual({ max: 1, value: 0 });
  });
});
