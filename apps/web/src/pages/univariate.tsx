import { Panel } from "../components/panel";
import { LoadingState } from "../components/loading-state";
import { StatusBadge } from "../components/status-badge";
import { requestJson } from "../api/client";
import { useResource } from "../hooks/use-resource";
import type { ApiUnivariateSummary } from "../contracts";

async function loadSummary(): Promise<ApiUnivariateSummary> {
  return requestJson<ApiUnivariateSummary>("/api/statistics/univariate/summary");
}

export function UnivariatePage() {
  const summary = useResource(loadSummary);

  if (summary.status === "loading" || summary.status === "idle") {
    return <LoadingState label="Loading univariate statistics" />;
  }

  if (summary.status === "error") {
    return (
      <Panel title="Univariate statistics">
        <p>Statistics summary is not available.</p>
      </Panel>
    );
  }

  return (
    <section data-route="univariate-page">
      <Panel title="Univariate statistics">
        <StatusBadge tone="running">loading summary</StatusBadge>
        <p>Compute univariate statistics to populate this table.</p>
        <ul>
          {summary.data.items.map((row) => (
            <li key={row.name}>
              {row.name}: {String(row.mean)}
            </li>
          ))}
        </ul>
      </Panel>
    </section>
  );
}
