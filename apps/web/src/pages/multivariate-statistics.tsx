import { useEffect, useMemo, useRef, useState } from "react";
import { loadProjectContext, loadWorkflow } from "../api/client";
import { multivariateStatisticsApi } from "../api/multivariate-statistics";
import { Button } from "../components/button";
import { LoadingState } from "../components/loading-state";
import { Panel } from "../components/panel";
import type {
  ApiMultivariateArtifacts,
  ApiMultivariateCandidates,
  ApiMultivariateComponents,
  ApiMultivariateIncomeEvidenceList,
  ApiMultivariateRiskContributions,
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

function number(value: number | null | undefined): string {
  return value == null ? "Unavailable" : value.toFixed(2);
}

function listing(value: Readonly<{ code: string; exchange: string }> | null | undefined): string {
  return value ? `${value.code}.${value.exchange}` : "Unavailable";
}

function historyRequirement(reasons: readonly string[] | undefined): string | null {
  return reasons?.includes("insufficient_common_history")
    ? "This analysis needs at least 100 shared daily returns. In Univariate Statistics, select Duration > 6 months, recompute Bivariate Statistics, then compute this run again."
    : null;
}

export function MultivariateStatisticsPage() {
  const [revision, setRevision] = useState(0);
  const workflow = useResource(loadWorkflow, [revision]);
  const projects = useResource(loadProjectContext, [revision]);
  const [run, setRun] = useState<ApiMultivariateRun | null>(null);
  const [summary, setSummary] = useState<ApiMultivariateSummary | null>(null);
  const [structure, setStructure] = useState<ApiMultivariateStructure | null>(null);
  const [candidates, setCandidates] = useState<ApiMultivariateCandidates | null>(null);
  const [components, setComponents] = useState<ApiMultivariateComponents | null>(null);
  const [contributions, setContributions] = useState<ApiMultivariateRiskContributions | null>(null);
  const [income, setIncome] = useState<ApiMultivariateIncomeEvidenceList | null>(null);
  const [validation, setValidation] = useState<ApiMultivariateValidation | null>(null);
  const [artifacts, setArtifacts] = useState<ApiMultivariateArtifacts | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [message, setMessage] = useState("");
  const projectVersion = useRef(0);

  const bivariateRunId = workflow.status === "ready" ? workflow.data.stages.bivariate_statistics.bivariate_run_id : undefined;
  const projectId = projects.status === "ready" ? projects.data.current_project_id : null;
  const stage = workflow.status === "ready" ? workflow.data.stages.multivariate_statistics : null;
  const selectedCandidateIds = run?.settings.selected_candidate_ids ?? [];
  const selectedCandidateId = selectedCandidateIds[0] ?? candidates?.items[0]?.candidate_id;
  const selectedContributions = useMemo(
    () => contributions?.items.filter((item) => item.candidate_id === selectedCandidateId) ?? [],
    [contributions, selectedCandidateId],
  );

  async function loadRun(runId: string, version = projectVersion.current) {
    const [nextRun, nextSummary, nextStructure, nextCandidates, nextComponents, nextContributions, nextIncome, nextValidation, nextArtifacts] = await Promise.all([
      multivariateStatisticsApi.loadRun(runId), multivariateStatisticsApi.loadSummary(runId), multivariateStatisticsApi.loadStructure(runId),
      multivariateStatisticsApi.loadCandidates(runId), multivariateStatisticsApi.loadComponents(runId), multivariateStatisticsApi.loadRiskContributions(runId),
      multivariateStatisticsApi.loadIncomeEvidence(runId), multivariateStatisticsApi.loadValidation(runId), multivariateStatisticsApi.loadArtifacts(runId),
    ]);
    if (version !== projectVersion.current) return;
    setRun(nextRun); setSummary(nextSummary); setStructure(nextStructure); setCandidates(nextCandidates);
    setComponents(nextComponents); setContributions(nextContributions); setIncome(nextIncome); setValidation(nextValidation); setArtifacts(nextArtifacts);
  }

  useEffect(() => {
    const resetProjectState = () => {
      projectVersion.current += 1;
      setRun(null);
      setSummary(null);
      setStructure(null);
      setCandidates(null);
      setComponents(null);
      setContributions(null);
      setIncome(null);
      setValidation(null);
      setArtifacts(null);
      setActiveTab("overview");
      setMessage("");
      setRevision((value) => value + 1);
    };
    window.addEventListener("portfell:project-updated", resetProjectState);
    return () => window.removeEventListener("portfell:project-updated", resetProjectState);
  }, []);

  useEffect(() => {
    const runId = stage?.multivariate_run_id;
    const version = projectVersion.current;
    if (runId) void loadRun(runId, version).catch(() => {
      if (version === projectVersion.current) setMessage("Multivariate results are unavailable.");
    });
  }, [stage?.multivariate_run_id]);

  useEffect(() => {
    if (!run || run.status !== "running") return;
    const activeRunId = run.run_id;
    let cancelled = false;
    let timeoutId: number | undefined;
    async function pollMultivariateRun() {
      try {
        const current = await multivariateStatisticsApi.loadRun(activeRunId);
        if (cancelled) return;
        setRun(current);
        if (current.status === "running") {
          timeoutId = window.setTimeout(() => void pollMultivariateRun(), 750);
          return;
        }
        if (current.status === "failed") {
          setMessage(current.failure_reason || "Multivariate calculation failed. Please try again.");
          return;
        }
        await loadRun(current.run_id);
        if (cancelled) return;
        setRevision((value) => value + 1);
        window.dispatchEvent(new Event("portfell:workflow-updated"));
      } catch (error) {
        if (!cancelled) setMessage(error instanceof Error ? error.message : "Could not retrieve multivariate calculation status.");
      }
    }
    void pollMultivariateRun();
    return () => {
      cancelled = true;
      if (timeoutId !== undefined) window.clearTimeout(timeoutId);
    };
  }, [run?.run_id]);

  async function compute() {
    if (!projectId || !bivariateRunId) return;
    setMessage("");
    try {
      const next = await multivariateStatisticsApi.startRun({ project_id: projectId, bivariate_run_id: bivariateRunId });
      setRun(next);
      await loadRun(next.run_id);
      setRevision((value) => value + 1);
    } catch { setMessage("Multivariate calculation could not be started."); }
  }

  async function toggleCandidate(candidateId: string, selected: boolean) {
    if (!run) return;
    const next = selected ? [...selectedCandidateIds, candidateId] : selectedCandidateIds.filter((item) => item !== candidateId);
    try { setRun(await multivariateStatisticsApi.saveSelectedCandidates(run.run_id, next)); }
    catch { setMessage("Portfolio candidate selection could not be saved."); }
  }

  if (workflow.status === "idle" || workflow.status === "loading" || projects.status === "idle" || projects.status === "loading") return <LoadingState label="Loading multivariate statistics" />;
  if (workflow.status === "error" || projects.status === "error") return <p role="alert">Multivariate workflow state is unavailable.</p>;
  if (stage?.status === "locked") return <Panel title="Multivariate Statistics"><p>Complete the matching bivariate run before portfolio-level analysis.</p></Panel>;

  const progress = run ? run.total_units === 0 ? 0 : run.completed_units / run.total_units * 100 : 0;
  const artifactRisk = artifacts?.risk_model;
  const structureAvailable = !structure?.availability_reasons?.length;
  const riskModelAvailable = !artifactRisk?.availability_reasons?.length;
  return <section className="multivariate-statistics-page" data-route="multivariate-statistics-page">
    <Panel title="Multivariate Statistics">
      <div className="quote-fetch quote-fetch--panel bivariate-compute">
        <label htmlFor="multivariate-progress">Multivariate statistics progress</label>
        <progress id="multivariate-progress" value={progress} max={100} />
        <p className="status-line" aria-live="polite">{run ? `${run.phase} · ${run.completed_units} of ${run.total_units} phases complete · ${run.elapsed_seconds}s elapsed${run.estimated_remaining_seconds == null ? "" : ` · about ${run.estimated_remaining_seconds}s remaining`}` : "Ready to compute."}</p>
        <div className="quote-fetch__action">
          <Button type="button" variant="primary" onClick={() => void compute()} disabled={!projectId || !bivariateRunId || run?.status === "running"}>
            {run?.status === "running" ? "Computing…" : "Compute multivariate statistics"}
          </Button>
        </div>
      </div>
      {stage?.status === "stale" && <p role="status">The prior multivariate result is stale because its bivariate input changed. Compute a new run to refresh it.</p>}
      {message && <p role="alert">{message}</p>}{run?.failure_reason && <p role="alert">{run.failure_reason}</p>}
    </Panel>
    {run?.status === "complete" && <Panel title="Multivariate results">
      <div className="statistics-tabs" role="tablist" aria-label="Multivariate statistics views">{tabs.map((tab) => <button key={tab.id} role="tab" aria-selected={activeTab === tab.id} onClick={() => setActiveTab(tab.id)}>{tab.label}</button>)}</div>
      {activeTab === "overview" && <><dl className="multivariate-facts"><div><dt>Candidate ETFs</dt><dd>{summary?.candidate_etf_count ?? "Unavailable"}</dd></div><div><dt>Portfolio candidates</dt><dd>{candidates?.items.length ?? "Unavailable"}</dd></div><div><dt>Aligned period</dt><dd>{summary?.aligned_period ? `${summary.aligned_period.date_start} to ${summary.aligned_period.date_end} (${summary.aligned_period.observation_count} observations)` : "Unavailable"}</dd></div><div><dt>Risk clusters</dt><dd>{structureAvailable ? structure?.risk_cluster_count ?? "Unavailable" : "Unavailable"}</dd></div><div><dt>Independent drivers</dt><dd>{structureAvailable ? number(structure?.effective_independent_drivers) : "Unavailable"}</dd></div><div><dt>Dominant component share</dt><dd>{structureAvailable ? percent(structure?.dominant_component_share) : "Unavailable"}</dd></div><div><dt>Estimator</dt><dd>{artifactRisk?.estimator ?? "Unavailable"}</dd></div><div><dt>Shrinkage</dt><dd>{riskModelAvailable ? number(artifactRisk?.shrinkage_intensity) : "Unavailable"}</dd></div></dl>{summary?.availability_reasons?.length ? <p role="status">Unavailable evidence: {summary.availability_reasons.join(", ")}</p> : null}{historyRequirement(summary?.availability_reasons) ? <p role="status">{historyRequirement(summary?.availability_reasons)}</p> : null}</>}
      {activeTab === "risk-structure" && <><dl className="multivariate-facts"><div><dt>Effective rank</dt><dd>{structureAvailable ? number(structure?.effective_rank) : "Unavailable"}</dd></div><div><dt>Dominant component share</dt><dd>{structureAvailable ? percent(structure?.dominant_component_share) : "Unavailable"}</dd></div><div><dt>Components for 80%</dt><dd>{structureAvailable ? structure?.thresholds?.components_for_80pct ?? "Unavailable" : "Unavailable"}</dd></div><div><dt>Components for 90%</dt><dd>{structureAvailable ? structure?.thresholds?.components_for_90pct ?? "Unavailable" : "Unavailable"}</dd></div><div><dt>Components for 95%</dt><dd>{structureAvailable ? structure?.thresholds?.components_for_95pct ?? "Unavailable" : "Unavailable"}</dd></div><div><dt>Strongest common driver</dt><dd>{structureAvailable ? listing(structure?.strongest_common_driver) : "Unavailable"}</dd></div><div><dt>Minimum eigenvalue</dt><dd>{riskModelAvailable ? number(artifactRisk?.minimum_eigenvalue) : "Unavailable"}</dd></div><div><dt>Condition number</dt><dd>{riskModelAvailable ? number(artifactRisk?.condition_number) : "Unavailable"}</dd></div><div><dt>Positive semidefinite</dt><dd>{!riskModelAvailable || artifactRisk?.is_positive_semidefinite == null ? "Unavailable" : artifactRisk.is_positive_semidefinite ? "Yes" : "No"}</dd></div></dl>{structureAvailable && structure?.largest_redundancy_warning ? <p role="status">Largest redundancy: {listing(structure.largest_redundancy_warning.left)} and {listing(structure.largest_redundancy_warning.right)} ({percent(structure.largest_redundancy_warning.correlation)} correlation).</p> : null}{structure?.availability_reasons?.length ? <p role="status">Structure unavailable: {structure.availability_reasons.join(", ")}</p> : null}<table><caption>Component loadings and empirical clusters</caption><thead><tr><th>Component</th><th>Listing</th><th>Loading</th><th>Explained variance</th><th>Cluster</th></tr></thead><tbody>{components?.items.map((item) => <tr key={`${item.component_id}:${item.isin}:${item.exchange}:${item.code}`}><td>{item.component_id}</td><td>{item.code}.{item.exchange}</td><td>{number(item.loading)}</td><td>{percent(item.explained_variance)}</td><td>{item.cluster ?? "Unavailable"}</td></tr>)}</tbody></table></>}
      {activeTab === "portfolio-candidates" && <div className="multivariate-candidates">{candidates?.items.map((candidate) => <article key={candidate.candidate_id}><label><input type="checkbox" checked={selectedCandidateIds.includes(candidate.candidate_id)} onChange={(event) => void toggleCandidate(candidate.candidate_id, event.target.checked)} /> Portfolio selection</label><h3>{candidate.method}{candidate.baseline ? " · Baseline" : ""}</h3><p>{candidate.status}{candidate.reasons.length ? ` · ${candidate.reasons.join(", ")}` : ""}</p><p>Volatility: {percent(candidate.volatility)} · VaR: {percent(candidate.var)} · CVaR: {percent(candidate.cvar)}</p><p>Total return: {percent(candidate.total_return)} · Maximum drawdown: {percent(candidate.max_drawdown)}</p><p>Maximum weight: {percent(candidate.maximum_weight)} · Effective holdings: {number(candidate.effective_holding_count)}</p><p>Herfindahl concentration: {number(candidate.herfindahl_index)} · Diversification ratio: {number(candidate.diversification_ratio)}</p><p>Gross historical yield: {percent(candidate.gross_ttm_distribution_yield)} · Gross monthly distribution: {number(candidate.gross_monthly_distribution)}</p><ul>{candidate.weights.map((weight) => <li key={`${weight.isin}:${weight.exchange}:${weight.code}`}>{weight.code}.{weight.exchange}: {percent(weight.weight)}</li>)}</ul></article>)}</div>}
      {activeTab === "risk-contributions" && <table><caption>Capital weights and percent risk contributions for the selected candidate</caption><thead><tr><th>Listing</th><th>Capital weight</th><th>Marginal contribution</th><th>Percent risk contribution</th></tr></thead><tbody>{selectedContributions.map((item) => <tr key={`${item.candidate_id}:${item.isin}:${item.exchange}:${item.code}`}><td>{item.code}.{item.exchange}</td><td>{percent(item.weight)}</td><td>{number(item.marginal_risk_contribution)}</td><td>{percent(item.percent_risk_contribution)}</td></tr>)}</tbody></table>}
      {activeTab === "income-evidence" && <><p>All income values are gross historical observations. Net, sustainable, tax, and cost claims remain unavailable unless a verified source is present. Capital change uses the quoted market-price proxy.</p><table><caption>Monthly-distribution evidence</caption><thead><tr><th>Listing</th><th>Observed months</th><th>Coverage</th><th>Gross TTM yield</th><th>Trend</th><th>Cuts</th><th>Total return</th><th>Market-price capital change (NAV proxy)</th><th>Warnings</th></tr></thead><tbody>{income?.items.map((item) => <tr key={`${item.isin}:${item.exchange}:${item.code}`}><td>{item.code}.{item.exchange}</td><td>{item.observed_month_count}</td><td>{percent(item.observed_payment_coverage)}</td><td>{percent(item.gross_ttm_distribution_yield)}</td><td>{number(item.distribution_trend)}</td><td>{item.cut_count ?? "Unavailable"}</td><td>{percent(item.total_return)}</td><td>{percent(item.market_price_capital_change)}</td><td>{[...item.warnings, ...item.availability_reasons].join(", ") || "None"}</td></tr>)}</tbody></table></>}
      {activeTab === "validation" && <table><caption>Persisted walk-forward, stress, and scorecard evidence</caption><thead><tr><th>Type</th><th>Method</th><th>Status</th><th>Reason</th></tr></thead><tbody>{validation?.items.map((item, index) => <tr key={`${String(item.kind)}:${String(item.candidate_id)}:${index}`}><td>{String(item.kind ?? "validation")}</td><td>{String(item.method ?? "Unavailable")}</td><td>{String(item.status ?? "available")}</td><td>{String(item.reason ?? item.availability_reasons ?? "None")}</td></tr>)}</tbody></table>}
    </Panel>}
  </section>;
}
