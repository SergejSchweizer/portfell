
import { useEffect, useState } from "react";
import { loadWorkflow } from "../api/client";
import { univariateStatisticsApi } from "../api/univariate-statistics";
import { Button } from "../components/button";
import { LoadingState } from "../components/loading-state";
import { Panel } from "../components/panel";
import type { ApiFilterSelection, ApiPage, ApiUnivariateRow } from "../contracts";
import { useResource } from "../hooks/use-resource";

type PredicateDraft = { metric: string; operator: string; value: string };

export function UnivariateFilterPage() {
  const [workflowRevision, setWorkflowRevision] = useState(0);
  const workflow = useResource(loadWorkflow, [workflowRevision]);
  const metrics = useResource(univariateStatisticsApi.loadFilterMetrics);
  const [predicates, setPredicates] = useState<PredicateDraft[]>([
    { metric: "annualized_volatility", operator: "<=", value: "0.25" },
  ]);
  const [selection, setSelection] = useState<ApiFilterSelection | null>(null);
  const [results, setResults] = useState<ApiPage<ApiUnivariateRow> | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    const resetProjectState = () => {
      setSelection(null);
      setResults(null);
      setMessage("");
      setWorkflowRevision((value) => value + 1);
    };
    window.addEventListener("portfell:project-updated", resetProjectState);
    return () => window.removeEventListener("portfell:project-updated", resetProjectState);
  }, []);

  if (workflow.status === "loading" || workflow.status === "idle" || metrics.status === "loading" || metrics.status === "idle") {
    return <LoadingState label="Loading univariate filter" />;
  }
  if (workflow.status === "error" || metrics.status === "error") return <p>Filter inputs are unavailable.</p>;
  const stage = workflow.data.stages.univariate_filter;
  const sourceRunId = workflow.data.stages.univariate_statistics.univariate_run_id;
  if (stage.status === "locked" || !sourceRunId) {
    return <Panel title="Univariate Filter"><p>Complete <a href="/univariate-statistics">Univariate Statistics</a> first.</p></Panel>;
  }

  function updatePredicate(index: number, update: Partial<PredicateDraft>) {
    setSelection(null);
    setResults(null);
    setPredicates((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, ...update } : item));
  }

  async function apply() {
    const univariateRunId = sourceRunId;
    if (!univariateRunId) return;
    setMessage("Applying predicates…");
    try {
      const nextSelection = await univariateStatisticsApi.applyFilter({
        source_run_id: univariateRunId,
        predicates: predicates.map((predicate) => ({ ...predicate, value: Number(predicate.value) })),
      });
      setSelection(nextSelection);
      const page = await univariateStatisticsApi.loadFilterResults(nextSelection.selection_id, 50, 0);
      setResults(page);
      setMessage(`${nextSelection.selected_count} selected; ${nextSelection.excluded_count} excluded.`);
      window.dispatchEvent(new Event("portfell:workflow-updated"));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Filtering failed.");
    }
  }

  return (
    <Panel title="Univariate Filter">
      <div className="predicate-editor">
        {predicates.map((predicate, index) => (
          <div className="predicate-row" key={index}>
            <label>Metric<select value={predicate.metric} onChange={(event) => updatePredicate(index, { metric: event.target.value })}>{metrics.data.items.map((item) => <option key={item.metric} value={item.metric}>{item.label}</option>)}</select></label>
            <label>Operator<select value={predicate.operator} onChange={(event) => updatePredicate(index, { operator: event.target.value })}>{["=", "!=", ">", ">=", "<", "<="].map((operator) => <option key={operator}>{operator}</option>)}</select></label>
            <label>Value<input type="number" step="any" value={predicate.value} onChange={(event) => updatePredicate(index, { value: event.target.value })} /></label>
            <Button type="button" disabled={predicates.length === 1} onClick={() => { setPredicates((current) => current.filter((_, itemIndex) => itemIndex !== index)); setSelection(null); }}>Remove</Button>
          </div>
        ))}
      </div>
      <Button type="button" onClick={() => { setPredicates((current) => [...current, { metric: metrics.data.items[0]?.metric ?? "annualized_return", operator: ">=", value: "0" }]); setSelection(null); setResults(null); }}>Add predicate</Button>
      <Button type="button" variant="primary" disabled={predicates.some((item) => item.value.trim() === "" || !Number.isFinite(Number(item.value)))} onClick={() => void apply()}>Apply filter</Button>
      <p aria-live="polite">{message}</p>
      {selection && <p>{selection.input_count} input listings, {selection.selected_count} selected, {selection.excluded_count} excluded.</p>}
      {results && results.items.length > 0 ? <table><thead><tr><th>ISIN</th><th>Symbol</th><th>Exchange</th></tr></thead><tbody>{results.items.map((row) => <tr key={`${row.isin}:${row.exchange}:${row.code}`}><td>{row.isin}</td><td>{row.code}</td><td>{row.exchange}</td></tr>)}</tbody></table> : results ? <p>No listings satisfy all predicates.</p> : null}
    </Panel>
  );
}
