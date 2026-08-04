
import { useState } from "react";
import { loadWorkflow, postJson, requestJson } from "../api/client";
import { Button } from "../components/button";
import { LoadingState } from "../components/loading-state";
import { Panel } from "../components/panel";
import type { ApiPage, ApiResearchRun, ApiUnivariateRow } from "../contracts";
import { useResource } from "../hooks/use-resource";

function metric(value: number | null | undefined): string {
  return value == null ? "—" : value.toFixed(4);
}

export function UnivariateStatisticsPage() {
  const workflow = useResource(loadWorkflow);
  const [run, setRun] = useState<ApiResearchRun | null>(null);
  const [results, setResults] = useState<ApiPage<ApiUnivariateRow> | null>(null);
  const [message, setMessage] = useState("");

  if (workflow.status === "loading" || workflow.status === "idle") {
    return <LoadingState label="Loading univariate statistics" />;
  }
  if (workflow.status === "error") return <p>Workflow state is unavailable.</p>;
  const stage = workflow.data.stages.univariate_statistics;
  const metadata = workflow.data.stages.metadata_filter;

  async function compute() {
    if (!metadata.metadata_selection_id || !metadata.quote_run_id) return;
    setMessage("Computing univariate statistics…");
    try {
      const nextRun = await postJson<ApiResearchRun>("/api/univariate-statistics/runs", {
        metadata_selection_id: metadata.metadata_selection_id,
        quote_run_id: metadata.quote_run_id,
      });
      setRun(nextRun);
      const page = await requestJson<ApiPage<ApiUnivariateRow>>(
        `/api/univariate-statistics/runs/${nextRun.run_id}/results?limit=50&offset=0`,
      );
      setResults(page);
      setMessage(`${page.total.toLocaleString()} listings computed.`);
      window.dispatchEvent(new Event("portfell:workflow-updated"));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Univariate computation failed.");
    }
  }

  if (stage.status === "locked") {
    return <Panel title="Univariate Statistics"><p>Complete quote fetching on <a href="/metadata-filter">Metadata Filter</a> first.</p></Panel>;
  }
  return (
    <Panel title="Univariate Statistics">
      <Button type="button" variant="primary" disabled={run?.status === "running"} onClick={() => void compute()}>
        {run?.status === "running" ? "Computing…" : "Compute univariate statistics"}
      </Button>
      <p aria-live="polite">{message}</p>
      {run && <progress max={100} value={run.percent} aria-label="Univariate progress" />}
      {results && results.items.length > 0 ? (
        <table>
          <thead><tr><th>Listing</th><th>ISIN</th><th>Observations</th><th>Return</th><th>Volatility</th><th>Sharpe</th><th>Drawdown</th><th>Expected shortfall</th></tr></thead>
          <tbody>
            {results.items.map((row) => (
              <tr key={`${row.isin}:${row.exchange}:${row.code}`}>
                <td>{row.code}.{row.exchange}</td><td>{row.isin}</td>
                <td>{row.quote_observation_count}</td><td>{metric(row.annualized_return)}</td>
                <td>{metric(row.annualized_volatility)}</td><td>{metric(row.sharpe_ratio)}</td>
                <td>{metric(row.max_drawdown)}</td><td>{metric(row.expected_shortfall)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : results ? <p>No univariate rows matched the pinned selection.</p> : null}
    </Panel>
  );
}
