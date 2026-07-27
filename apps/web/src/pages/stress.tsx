import { Panel } from "../components/panel";
import { LoadingState } from "../components/loading-state";
import { StatusBadge } from "../components/status-badge";
import { requestJson } from "../api/client";
import { useResource } from "../hooks/use-resource";
import type { ApiProgress } from "../contracts";

async function loadStressProgress(): Promise<ApiProgress> {
  return requestJson<ApiProgress>("/api/statistics/multivariate/compute", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ project_id: "project-001" }),
  });
}

export function StressPage() {
  const progress = useResource(loadStressProgress);

  if (progress.status === "loading" || progress.status === "idle") {
    return <LoadingState label="Loading stress view" />;
  }

  return (
    <section data-route="stress-page">
      <Panel title="Stress">
        <StatusBadge tone="warning">warning</StatusBadge>
        <p>Review stress-warning and offline-recovery fixture states.</p>
        <p>Progress: {progress.status === "ready" ? String(progress.data.progress ?? 0) : "0"}%</p>
      </Panel>
    </section>
  );
}
