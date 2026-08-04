
import { Panel } from "../components/panel";
import { LoadingState } from "../components/loading-state";
import { requestJson } from "../api/client";
import type { ApiUnivariateSummary } from "../contracts";
import { useResource } from "../hooks/use-resource";

async function loadSummary(): Promise<ApiUnivariateSummary> {
  return requestJson<ApiUnivariateSummary>("/api/statistics/univariate/summary");
}

export function UnivariateStatisticsPage() {
  const summary = useResource(loadSummary);
  if (summary.status === "loading" || summary.status === "idle") {
    return <LoadingState label="Loading univariate statistics" />;
  }
  return (
    <Panel title="Univariate Statistics">
      {summary.status === "error" ? (
        <p>No univariate statistics are available yet.</p>
      ) : (
        <table>
          <thead><tr><th>Statistic</th><th>Mean</th><th>Median</th><th>±3σ range</th></tr></thead>
          <tbody>
            {summary.data.items.map((row) => (
              <tr key={row.name}>
                <td>{row.name}</td><td>{String(row.mean ?? "—")}</td>
                <td>{String(row.median ?? "—")}</td><td>{String(row.three_std_range ?? "—")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Panel>
  );
}
