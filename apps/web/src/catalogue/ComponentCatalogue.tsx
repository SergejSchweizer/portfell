import { Button } from "../components/button";
import { EmptyState } from "../components/empty-state";
import { LoadingState } from "../components/loading-state";
import { Panel } from "../components/panel";
import { ProgressStepper } from "../components/progress-stepper";
import { StatusBadge } from "../components/status-badge";

const steps = [
  { id: "data", label: "Data", current: true },
  { id: "metadata", label: "Metadata" },
  { id: "univariate", label: "Univariate", disabled: true },
] as const;

export function ComponentCatalogue() {
  return (
    <main data-route="component-catalogue">
      <h1>Component catalogue</h1>
      <Panel title="Buttons">
        <Button variant="primary">Primary action</Button>{" "}
        <Button variant="secondary">Secondary action</Button>{" "}
        <Button variant="danger">Danger action</Button>
      </Panel>
      <Panel title="Status">
        <StatusBadge tone="success">complete</StatusBadge>{" "}
        <StatusBadge tone="warning">warning</StatusBadge>{" "}
        <StatusBadge tone="stale">stale</StatusBadge>
      </Panel>
      <Panel title="Workflow">
        <ProgressStepper steps={steps} />
      </Panel>
      <LoadingState label="Loading state preview" />
      <EmptyState
        title="Empty state preview"
        description="No project is selected yet."
      />
    </main>
  );
}
