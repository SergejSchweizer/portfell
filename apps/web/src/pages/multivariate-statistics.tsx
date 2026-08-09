import { loadWorkflow } from "../api/client";
import { LoadingState } from "../components/loading-state";
import { Panel } from "../components/panel";
import { useResource } from "../hooks/use-resource";

export function MultivariateStatisticsPage() {
  const workflow = useResource(loadWorkflow, []);

  if (workflow.status === "idle" || workflow.status === "loading") {
    return <LoadingState label="Loading multivariate statistics" />;
  }
  if (workflow.status === "error") {
    return <p role="alert">Workflow state is unavailable.</p>;
  }

  const stage = workflow.data.stages.multivariate_statistics;
  const bivariate = workflow.data.stages.bivariate_statistics;
  if (stage.status === "locked") {
    return <Panel title="Multivariate Statistics">
      <p>Complete bivariate statistics before starting portfolio-level analysis.</p>
    </Panel>;
  }

  return <section className="multivariate-statistics-page" data-route="multivariate-statistics-page">
    <Panel title="Multivariate Statistics">
      <p>Portfolio-level analysis is ready for the ISIN universe used by the completed bivariate run.</p>
      <dl className="multivariate-statistics-page__inputs">
        <div><dt>Bivariate run</dt><dd>{bivariate.bivariate_run_id ?? "—"}</dd></div>
        <div><dt>Univariate selection</dt><dd>{stage.univariate_selection_id ?? "—"}</dd></div>
      </dl>
      <p className="status-line" aria-live="polite">Multivariate portfolio calculations will be shown here when they are configured for this project.</p>
    </Panel>
  </section>;
}
