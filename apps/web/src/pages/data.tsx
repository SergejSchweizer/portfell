import { EmptyState } from "../components/empty-state";
import { LoadingState } from "../components/loading-state";
import { Panel } from "../components/panel";
import { ProgressStepper } from "../components/progress-stepper";
import { requestJson } from "../api/client";
import { useResource } from "../hooks/use-resource";
import type { ApiProjects } from "../contracts";

async function loadProjects(): Promise<ApiProjects> {
  return requestJson<ApiProjects>("/api/projects");
}

const steps = [
  { id: "load", label: "Load Data", current: true },
  { id: "univariate", label: "Univariate", disabled: true },
] as const;

export function DataPage() {
  const projects = useResource(loadProjects);

  if (projects.status === "loading" || projects.status === "idle") {
    return <LoadingState label="Loading projects" />;
  }

  return (
    <section data-route="data-page">
      <Panel title="Load data">
        <ProgressStepper steps={steps} />
        {projects.status === "ready" ? <p>{projects.data.items.length} project(s) available.</p> : null}
      </Panel>
      <EmptyState
        title="No data loaded"
        description="Select a project before loading ISIN data."
      />
    </section>
  );
}
