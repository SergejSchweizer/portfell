
import { useEffect, useState } from "react";
import { loadWorkflow, postJson, requestJson } from "../api/client";
import { Button } from "../components/button";
import { LoadingState } from "../components/loading-state";
import { Panel } from "../components/panel";
import type { ApiBivariateRow, ApiPage, ApiPairPlan, ApiResearchRun } from "../contracts";
import { useResource } from "../hooks/use-resource";

function metric(value: number | null | undefined): string {
  return value == null ? "—" : value.toFixed(4);
}

export function BivariateStatisticsPage() {
  const [workflowRevision, setWorkflowRevision] = useState(0);
  const workflow = useResource(loadWorkflow, [workflowRevision]);
  const [plan, setPlan] = useState<ApiPairPlan | null>(null);
  const [run, setRun] = useState<ApiResearchRun | null>(null);
  const [results, setResults] = useState<ApiPage<ApiBivariateRow> | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    const resetProjectState = () => {
      setPlan(null);
      setRun(null);
      setResults(null);
      setMessage("");
      setWorkflowRevision((value) => value + 1);
    };
    window.addEventListener("portfell:project-updated", resetProjectState);
    return () => window.removeEventListener("portfell:project-updated", resetProjectState);
  }, []);

  if (workflow.status === "loading" || workflow.status === "idle") return <LoadingState label="Loading bivariate statistics" />;
  if (workflow.status === "error") return <p>Workflow state is unavailable.</p>;
  const selectionId = workflow.data.stages.univariate_filter.univariate_filter_selection_id;
  if (!selectionId) {
    return <Panel title="Bivariate Statistics"><p>Complete a non-empty <a href="/univariate-filter">Univariate Filter</a> selection first.</p></Panel>;
  }

  async function createPlan() {
    const nextPlan = await postJson<ApiPairPlan>("/api/bivariate-statistics/plan", { univariate_filter_selection_id: selectionId });
    setPlan(nextPlan);
    setMessage(nextPlan.allowed ? `${nextPlan.theoretical_pair_count} pairs are ready.` : `Pair count exceeds the ${nextPlan.pair_limit} limit or has fewer than two listings.`);
  }

  async function compute() {
    setMessage("Computing pair statistics…");
    try {
      const nextRun = await postJson<ApiResearchRun>("/api/bivariate-statistics/runs", { univariate_filter_selection_id: selectionId });
      setRun(nextRun);
      const page = await requestJson<ApiPage<ApiBivariateRow>>(`/api/bivariate-statistics/runs/${nextRun.run_id}/results?limit=50&offset=0`);
      setResults(page);
      setMessage(`${page.total} pair rows computed.`);
      window.dispatchEvent(new Event("portfell:workflow-updated"));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Bivariate computation failed.");
    }
  }

  return (
    <Panel title="Bivariate Statistics">
      <Button type="button" onClick={() => void createPlan()}>Plan pairs</Button>
      <Button type="button" variant="primary" disabled={!plan?.allowed || run?.status === "running"} onClick={() => void compute()}>Compute bivariate statistics</Button>
      <p aria-live="polite">{message}</p>
      {run && <progress max={100} value={run.percent} aria-label="Bivariate progress" />}
      {results && results.items.length > 0 ? <table><thead><tr><th>Left</th><th>Right</th><th>Observations</th><th>Pearson</th><th>Spearman</th><th>Covariance</th><th>β L→R</th><th>β R→L</th></tr></thead><tbody>{results.items.map((row) => <tr key={`${row.left_isin}:${row.left_exchange}:${row.left_code}:${row.right_isin}:${row.right_exchange}:${row.right_code}`}><td>{row.left_code}.{row.left_exchange}</td><td>{row.right_code}.{row.right_exchange}</td><td>{row.n_observations}</td><td>{metric(row.pearson_correlation)}</td><td>{metric(row.spearman_correlation)}</td><td>{metric(row.covariance)}</td><td>{metric(row.left_beta_to_right)}</td><td>{metric(row.right_beta_to_left)}</td></tr>)}</tbody></table> : results ? <p>No pair rows are available.</p> : null}
    </Panel>
  );
}
