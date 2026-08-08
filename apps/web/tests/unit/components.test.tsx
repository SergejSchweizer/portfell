import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Button } from "../../src/components/button";
import { EmptyState } from "../../src/components/empty-state";
import { Field } from "../../src/components/field";
import { IconButton } from "../../src/components/icon-button";
import { InlineNotice } from "../../src/components/inline-notice";
import { LoadingState } from "../../src/components/loading-state";
import { Panel } from "../../src/components/panel";
import { ProgressStepper } from "../../src/components/progress-stepper";
import { StatusBadge } from "../../src/components/status-badge";

describe("shared React components", () => {
  it("renders button variants, props, and class names", () => {
    const onClick = vi.fn();
    render(<><Button onClick={onClick}>Default</Button><Button variant="primary" className="extra" disabled>Primary</Button></>);

    fireEvent.click(screen.getByRole("button", { name: "Default" }));
    expect(onClick).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "Default" })).toHaveClass("portfell-button--secondary");
    expect(screen.getByRole("button", { name: "Primary" })).toHaveClass("portfell-button--primary", "extra");
    expect(screen.getByRole("button", { name: "Primary" })).toBeDisabled();
  });

  it("renders optional empty-state, panel, loading, and field content", () => {
    const { rerender } = render(<EmptyState title="No projects" description="Create one" action={<Button>Start</Button>} />);
    expect(screen.getByRole("region", { name: "No projects" })).toHaveTextContent("Create one");
    expect(screen.getByRole("button", { name: "Start" })).toBeVisible();

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

  it("renders icon, notice, status, and progress semantics", () => {
    render(<><IconButton label="Close" className="compact"><span aria-hidden="true">×</span></IconButton><InlineNotice>Saved</InlineNotice><InlineNotice tone="error">Failed</InlineNotice><StatusBadge>Idle</StatusBadge><StatusBadge tone="running">Running</StatusBadge><ProgressStepper steps={[{ id: "one", label: "One", current: true }, { id: "two", label: "Two", disabled: true }]}><span>Summary</span></ProgressStepper></>);

    expect(screen.getByRole("button", { name: "Close" })).toHaveAttribute("title", "Close");
    expect(screen.getByRole("button", { name: "Close" })).toHaveClass("compact");
    expect(screen.getByRole("status")).toHaveTextContent("Saved");
    expect(screen.getByRole("alert")).toHaveTextContent("Failed");
    expect(screen.getByText("Idle")).toHaveClass("portfell-status-badge--neutral");
    expect(screen.getByText("Running")).toHaveClass("portfell-status-badge--running");
    expect(screen.getByRole("button", { name: "One" })).toHaveAttribute("aria-current", "step");
    expect(screen.getByRole("button", { name: "Two" })).toBeDisabled();
    expect(screen.getByLabelText("Progress stepper")).toHaveTextContent("Summary");
  });
});
