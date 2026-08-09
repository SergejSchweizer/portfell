import { useEffect, useState } from "react";
import { loadProjectContext, loadWorkflow } from "../api/client";
import { multivariateStatisticsApi } from "../api/multivariate-statistics";
import { Button } from "../components/button";
import { LoadingState } from "../components/loading-state";
import { Panel } from "../components/panel";
import type {
  ApiMultivariateCandidates,
  ApiMultivariateRun,
  ApiMultivariateStructure,
  ApiMultivariateSummary,
  ApiMultivariateValidation,
} from "../contracts";
import { useResource } from "../hooks/use-resource";

type Tab = "overview" | "risk-structure" | "portfolio-candidates" | "risk-contributions" | "income-evidence" | "validation";

const tabs: readonly Readonly<{ id: Tab; label: string }>[] = [
  { id: "overview", label: "Overview" },
  { id: "risk-structure", label: "Risk Structure" },
  { id: "portfolio-candidates", label: "Portfolio Candidates" },
  { id: "risk-contributions", label: "Risk Contributions" },
  { id: "income-evidence", label: "Income Evidence" },
  { id: "validation", label: "Validation" },
];

function percent(value: number | null | undefined): string {
  return value == null ? "Unavailable" : `${(value * 100).toFixed(2)}%`;
}

export function MultivariateStatisticsPage() {
  const [revision, setRevision] = useState(0);
  const workflow = useResource(loadWorkflow, [revision]);
  const projects = useResource(loadProjectContext, [revision]);
  const [run, setRun] = useState<ApiMultivariateRun | null>(null);
  const [summary, setSummary] = useState<ApiMultivariateSummary | null>(null);
  const [structure, setStructure] = useState<ApiMultivariateStructure | null>(null);
  const [candidates, setCandidates] = useState<ApiMultivariateCandidates | null>(null);
  const [validation, setValidation] = useState<ApiMultivariateValidation | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [message, setMessage] = useState("");

  const bivariateRunId = workflow.status === "ready"
    ? workflow.data.stages.bivariate_statistics.bivariate_run_id
    : undefined;
  const projectId = projects.status === "ready" ? projects.data.current_project_id : null;
  const stage = workflow.status === "ready" ? workflow.data.stages.multivariate_statistics : null;

  async function loadRun(runId: string) {
    const [nextRun, nextSummary, nextStructure, nextCandidates, nextValidation] = await Promise.all([
      multivariateStatisticsApi.loadRun(runId),
      multivariateStatisticsApi.loadSummary(runId),
      multivariateStatisticsApi.loadStructure(runId),
      multivariateStatisticsApi.loadCandidates(runId),
      multivariateStatisticsApi.loadValidation(runId),
    ]);
    setRun(nextRun); setSummary(nextSummary); setStructure(nextStructure);
    setCandidates(nextCandidates); setValidation(nextValidation);
  }

  useEffect(() => {
    const runId = stage?.multivariate_run_id;
    if (runId) void loadRun(runId).catch(() => setMessage("Multivariate results are unavailable."));
  }, [stage?.multivariate_run_id]);

  async function compute() {
    if (!projectId || !bivariateRunId) return;
    setMessage("");
    try {
      const next = await multivariateStatisticsApi.startRun({ project_id: projectId, bivariate_run_id: bivariateRunId });
      setRun(next);
      await loadRun(next.run_id);
      setRevision((value) => value + 1);
    } catch {
      setMessage("Multivariate calculation could not be started.");
    }
  }

  if (workflow.status === "idle" || workflow.status === "loading" || projects.status === "idle" || projects.status === "loading") return <LoadingState label="Loading multivariate statistics" />;
  if (workflow.status === "error" || projects.status === "error") return <p role="alert">Multivariate workflow state is unavailable.</p>;
  if (stage?.status === "locked") return <Panel title="Multivariate Statistics"><p>Complete the matching bivariate run before portfolio-level analysis.</p></Panel>;

  const progress = run ? run.total_units === 0 ? 0 : run.completed_units / run.total_units * 100 : 0;
  return <section className="multivariate-statistics-page" data-route="multivariate-statistics-page">
    <Panel title="Multivariate Statistics">
      <div className="research-run-header">
        <div><p>Joint risk structure and comparable portfolio candidates for the completed Bivariate universe.</p>
          <p className="status-line" aria-live="polite">{run ? `${run.phase} · ${run.completed_units} of ${run.total_units} phases complete` : "Ready to compute."}</p></div>
        <Button onClick={() => void compute()} disabled={!projectId || !bivariateRunId || run?.status === "running"}>Compute multivariate statistics</Button>
      </div>
      <progress value={progress} max={100} aria-label="Multivariate statistics progress" />
      {message && <p role="alert">{message}</p>}
      {run?.failure_reason && <p role="alert">{run.failure_reason}</p>}
    </Panel>
    {run?.status === "complete" && <Panel title="Multivariate results">
      <div className="statistics-tabs" role="tablist" aria-label="Multivariate statistics views">
        {tabs.map((tab) => <button key={tab.id} role="tab" aria-selected={activeTab === tab.id} onClick={() => setActiveTab(tab.id)}>{tab.label}</button>)}
      </div>
      {activeTab === "overview" && <dl className="multivariate-facts"><div><dt>Candidate ETFs</dt><dd>{summary?.candidate_etf_count ?? "Unavailable"}</dd></div><div><dt>Aligned period</dt><dd>{summary?.aligned_period ? `${summary.aligned_period.date_start} to ${summary.aligned_period.date_end} (${summary.aligned_period.observation_count} observations)` : "Unavailable"}</dd></div><div><dt>Risk clusters</dt><dd>{structure?.risk_cluster_count ?? "Unavailable"}</dd></div><div><dt>Independent drivers</dt><dd>{structure?.effective_independent_drivers?.toFixed(2) ?? "Unavailable"}</dd></div></dl>}
      {activeTab === "risk-structure" && <dl className="multivariate-facts"><div><dt>Effective rank</dt><dd>{structure?.effective_rank?.toFixed(2) ?? "Unavailable"}</dd></div><div><dt>Dominant component share</dt><dd>{percent(structure?.dominant_component_share)}</dd></div><div><dt>Risk model</dt><dd>{summary?.risk_model_id ?? "Unavailable"}</dd></div></dl>}
      {activeTab === "portfolio-candidates" && <div className="multivariate-candidates">{candidates?.items.map((candidate) => <article key={candidate.candidate_id}><h3>{candidate.method}{candidate.baseline ? " · Baseline" : ""}</h3><p>{candidate.status}</p><p>Volatility: {percent(candidate.volatility)}</p><p>Historical CVaR: {percent(candidate.cvar)}</p><p>Gross historical yield: {percent(candidate.gross_ttm_distribution_yield)}</p><ul>{candidate.weights.map((weight) => <li key={`${weight.isin}:${weight.exchange}:${weight.code}`}>{weight.code}.{weight.exchange}: {percent(weight.weight)}</li>)}</ul></article>)}</div>}
      {activeTab === "risk-contributions" && <p>Capital weights and risk contributions are available in the candidate detail when the risk model is feasible.</p>}
      {activeTab === "income-evidence" && <p>Distribution frequency and every yield shown here are observed historical gross values. Net, sustainable, tax, cost, and genuine-NAV claims remain unavailable unless a verified source is present.</p>}
      {activeTab === "validation" && <p>{validation?.items.length ?? 0} persisted walk-forward validation results are available. Results use common out-of-sample slices and explicit transaction-cost assumptions.</p>}
    </Panel>}
  </section>;
}
