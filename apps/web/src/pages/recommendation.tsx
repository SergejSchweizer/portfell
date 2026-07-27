import { Panel } from "../components/panel";
import { LoadingState } from "../components/loading-state";
import { requestJson } from "../api/client";
import { useResource } from "../hooks/use-resource";
import type { ApiProgress } from "../contracts";

async function loadRecommendationProgress(): Promise<ApiProgress> {
  return requestJson<ApiProgress>("/api/statistics/univariate/compute", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ project_id: "project-001" }),
  });
}

export function RecommendationPage() {
  const progress = useResource(loadRecommendationProgress);

  if (progress.status === "loading" || progress.status === "idle") {
    return <LoadingState label="Loading recommendation view" />;
  }

  return (
    <section data-route="recommendation-page">
      <Panel title="Recommendation">
        <p>Recommendation-ready and report-ready shell surfaces.</p>
        <p>Progress: {progress.status === "ready" ? String(progress.data.progress ?? 0) : "0"}%</p>
      </Panel>
    </section>
  );
}
