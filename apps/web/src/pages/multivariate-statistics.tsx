import { useEffect, useRef, useState } from "react";
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
  ApiMultivariatePerformance,
  ApiMultivariateRiskContributions,
  ApiMultivariateRun,
  ApiMultivariateStructure,
  ApiMultivariateSummary,
  ApiMultivariateValidation,
} from "../contracts";
import { useResource } from "../hooks/use-resource";

type Tab = "overview" | "risk-structure" | "portfolio-candidates" | "risk-contributions" | "income-evidence" | "performance" | "validation";

const tabs: readonly Readonly<{ id: Tab; label: string }>[] = [
  { id: "overview", label: "Overview" },
  { id: "risk-structure", label: "Risk Structure" },
  { id: "portfolio-candidates", label: "Portfolio Candidates" },
  { id: "risk-contributions", label: "Risk Contributions" },
  { id: "income-evidence", label: "Income Evidence" },
  { id: "performance", label: "Performance" },
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

function portfolioMethod(method: string | null | undefined): string {
  if (!method) return "Unavailable";
  const label = method.replaceAll("_", " ");
  return label[0].toUpperCase() + label.slice(1);
}

function historyRequirement(reasons: readonly string[] | undefined): string | null {
  return reasons?.includes("insufficient_common_history")
    ? "This analysis needs at least 100 shared daily returns. In Univariate Statistics, select Duration > 6 months, recompute Bivariate Statistics, then compute this run again."
    : null;
}

function performancePoints(values: ApiMultivariatePerformance["instrument_series"][number]["values"], minimum: number, maximum: number, start: number, end: number): string {
  const width = 760;
  const height = 220;
  return values.filter((value) => {
    const time = Date.parse(value.date);
    return time >= start && time <= end;
  }).map((value) => {
    const time = Date.parse(value.date);
    const x = 20 + (time - start) / Math.max(1, end - start) * width;
    const y = 20 + (maximum - value.return) / Math.max(0.000001, maximum - minimum) * height;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
}

function PerformanceChart({ performance, alignedPeriod }: Readonly<{ performance: ApiMultivariatePerformance; alignedPeriod?: Readonly<{ date_start: string; date_end: string }> }>) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const portfolios = performance.portfolio_series;
  const series = [...performance.instrument_series, ...portfolios];
  const values = series.flatMap((item) => item.values);
  if (values.length === 0) return <p role="status">Performance data is unavailable for this run.</p>;
  const minimum = Math.min(0, ...values.map((item) => item.return));
  const maximum = Math.max(0, ...values.map((item) => item.return));
  const times = values.map((item) => Date.parse(item.date));
  // The x-axis shows only the server-aligned analysis period, not each instrument's full individual history.
  const start = alignedPeriod ? Date.parse(alignedPeriod.date_start) : Math.min(...times);
  const end = alignedPeriod ? Date.parse(alignedPeriod.date_end) : Math.max(...times);
  const timeline = (portfolios[0]?.values ?? performance.instrument_series[0]?.values ?? []).filter((item) => {
    const time = Date.parse(item.date);
    return time >= start && time <= end;
  });
  const axisLabels = Array.from({ length: Math.min(6, timeline.length) }, (_, index) => {
    const point = timeline[Math.round(index / Math.max(1, Math.min(6, timeline.length) - 1) * (timeline.length - 1))];
    const time = Date.parse(point.date);
    return {
      label: new Intl.DateTimeFormat("en", { month: "short", year: "numeric", timeZone: "UTC" }).format(time),
      x: 20 + (time - start) / Math.max(1, end - start) * 760,
    };
  });
  const hoveredDate = hoveredIndex == null ? undefined : timeline[hoveredIndex]?.date;
  const hoverPosition = hoveredIndex == null || timeline.length < 2 ? 20 : 20 + hoveredIndex / (timeline.length - 1) * 760;
  const hoveredValues = hoveredDate == null ? [] : [
    ...performance.instrument_series.flatMap((item) => {
      const value = item.values.find((point) => point.date === hoveredDate);
      return value ? [{ label: `${item.code}.${item.exchange}`, value: value.return, className: "performance-chart__tooltip-instrument" }] : [];
    }),
    ...portfolios.flatMap((item, index) => {
      const value = item.values.find((point) => point.date === hoveredDate);
      return value ? [{ label: portfolioMethod(item.method), value: value.return, className: `performance-chart__tooltip-portfolio performance-chart__tooltip-portfolio--${index % 5}` }] : [];
    }),
  ];

  function inspectAt(clientX: number, bounds: DOMRect) {
    const chartX = Math.max(20, Math.min(780, (clientX - bounds.left) / bounds.width * 800));
    const nextIndex = Math.round((chartX - 20) / 760 * Math.max(0, timeline.length - 1));
    setHoveredIndex(nextIndex);
  }

  return <>
    <p className="performance-chart__legend">Relative cumulative monthly returns for every input instrument and feasible portfolio method.</p>
    <div className="performance-chart" role="group" aria-label="Relative cumulative monthly return comparison for all instruments and feasible portfolios. Hover or use arrow keys to inspect a month." tabIndex={0} onMouseLeave={() => setHoveredIndex(null)} onMouseMove={(event) => inspectAt(event.clientX, event.currentTarget.getBoundingClientRect())} onKeyDown={(event) => {
      if (timeline.length === 0) return;
      if (event.key === "Home") setHoveredIndex(0);
      else if (event.key === "End") setHoveredIndex(timeline.length - 1);
      else if (event.key === "ArrowLeft") setHoveredIndex((index) => Math.max(0, (index ?? timeline.length - 1) - 1));
      else if (event.key === "ArrowRight") setHoveredIndex((index) => Math.min(timeline.length - 1, (index ?? -1) + 1));
      else return;
      event.preventDefault();
    }}>
      <svg viewBox="0 0 800 280" preserveAspectRatio="none" aria-hidden="true">
        <line className="performance-chart__zero" x1="20" x2="780" y1={20 + (maximum - 0) / Math.max(0.000001, maximum - minimum) * 220} y2={20 + (maximum - 0) / Math.max(0.000001, maximum - minimum) * 220} />
        {performance.instrument_series.map((item, index) => <polyline key={`${item.isin}:${item.exchange}:${item.code}`} className={`performance-chart__instrument performance-chart__instrument--${index % 5}`} points={performancePoints(item.values, minimum, maximum, start, end)} />)}
        {portfolios.map((item, index) => <polyline key={item.candidate_id} className={`performance-chart__portfolio performance-chart__portfolio--${index % 5}`} points={performancePoints(item.values, minimum, maximum, start, end)} />)}
        {axisLabels.map((item) => <text className="performance-chart__axis-label" key={`${item.label}:${item.x}`} x={item.x} y="265" textAnchor="middle">{item.label}</text>)}
        {hoveredDate && <line className="performance-chart__cursor" x1={hoverPosition} x2={hoverPosition} y1="20" y2="240" />}
      </svg>
      {hoveredDate && <div className="performance-chart__tooltip" role="tooltip"><strong>{hoveredDate}</strong>{hoveredValues.map((item) => <span className={item.className} key={item.label}>{item.label}: {percent(item.value)}</span>)}</div>}
    </div>
    <ul className="performance-chart__series" aria-label="Performance series">{performance.instrument_series.map((item, index) => <li key={`${item.isin}:${item.exchange}:${item.code}`}><span className={`performance-chart__swatch performance-chart__instrument--${index % 5}`} />{item.code}.{item.exchange}</li>)}{portfolios.map((item, index) => <li key={item.candidate_id}><span className={`performance-chart__swatch performance-chart__portfolio performance-chart__portfolio--${index % 5}`} />{portfolioMethod(item.method)}</li>)}</ul>
  </>;
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
  const [performance, setPerformance] = useState<ApiMultivariatePerformance | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [message, setMessage] = useState("");
  const projectVersion = useRef(0);

  const bivariateRunId = workflow.status === "ready" ? workflow.data.stages.bivariate_statistics.bivariate_run_id : undefined;
  const projectId = projects.status === "ready" ? projects.data.current_project_id : null;
  const stage = workflow.status === "ready" ? workflow.data.stages.multivariate_statistics : null;

  async function loadRun(runId: string, version = projectVersion.current) {
    const [nextRun, nextSummary, nextStructure, nextCandidates, nextComponents, nextContributions, nextIncome, nextValidation, nextArtifacts, nextPerformance] = await Promise.all([
      multivariateStatisticsApi.loadRun(runId), multivariateStatisticsApi.loadSummary(runId), multivariateStatisticsApi.loadStructure(runId),
      multivariateStatisticsApi.loadCandidates(runId), multivariateStatisticsApi.loadComponents(runId), multivariateStatisticsApi.loadRiskContributions(runId),
      multivariateStatisticsApi.loadIncomeEvidence(runId), multivariateStatisticsApi.loadValidation(runId), multivariateStatisticsApi.loadArtifacts(runId), multivariateStatisticsApi.loadPerformance(runId),
    ]);
    if (version !== projectVersion.current) return;
    setRun(nextRun); setSummary(nextSummary); setStructure(nextStructure); setCandidates(nextCandidates);
    setComponents(nextComponents); setContributions(nextContributions); setIncome(nextIncome); setValidation(nextValidation); setArtifacts(nextArtifacts); setPerformance(nextPerformance);
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
      setPerformance(null);
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
      {activeTab === "overview" && <>{performance && <PerformanceChart performance={performance} alignedPeriod={summary?.aligned_period} />}<table className="multivariate-facts"><caption>Multivariate overview facts</caption><thead><tr><th>Fact</th><th>Value</th></tr></thead><tbody><tr><th>Candidate ETFs</th><td>{summary?.candidate_etf_count ?? "Unavailable"}</td></tr><tr><th>Portfolio candidates</th><td>{candidates?.items.length ?? "Unavailable"}</td></tr><tr><th>Aligned period</th><td>{summary?.aligned_period ? `${summary.aligned_period.date_start} to ${summary.aligned_period.date_end} (${summary.aligned_period.observation_count} observations)` : "Unavailable"}</td></tr><tr><th>Risk clusters</th><td>{structureAvailable ? structure?.risk_cluster_count ?? "Unavailable" : "Unavailable"}</td></tr><tr><th>Independent drivers</th><td>{structureAvailable ? number(structure?.effective_independent_drivers) : "Unavailable"}</td></tr><tr><th>Dominant component share</th><td>{structureAvailable ? percent(structure?.dominant_component_share) : "Unavailable"}</td></tr><tr><th>Estimator</th><td>{artifactRisk?.estimator ?? "Unavailable"}</td></tr><tr><th>Shrinkage</th><td>{riskModelAvailable ? number(artifactRisk?.shrinkage_intensity) : "Unavailable"}</td></tr></tbody></table>{summary?.availability_reasons?.length ? <p role="status">Unavailable evidence: {summary.availability_reasons.join(", ")}</p> : null}{historyRequirement(summary?.availability_reasons) ? <p role="status">{historyRequirement(summary?.availability_reasons)}</p> : null}</>}
      {activeTab === "risk-structure" && <><table className="multivariate-facts"><caption>Multivariate risk structure facts</caption><thead><tr><th>Fact</th><th>Value</th></tr></thead><tbody><tr><th>Effective rank</th><td>{structureAvailable ? number(structure?.effective_rank) : "Unavailable"}</td></tr><tr><th>Dominant component share</th><td>{structureAvailable ? percent(structure?.dominant_component_share) : "Unavailable"}</td></tr><tr><th>Components for 80%</th><td>{structureAvailable ? structure?.thresholds?.components_for_80pct ?? "Unavailable" : "Unavailable"}</td></tr><tr><th>Components for 90%</th><td>{structureAvailable ? structure?.thresholds?.components_for_90pct ?? "Unavailable" : "Unavailable"}</td></tr><tr><th>Components for 95%</th><td>{structureAvailable ? structure?.thresholds?.components_for_95pct ?? "Unavailable" : "Unavailable"}</td></tr><tr><th>Strongest common driver</th><td>{structureAvailable ? listing(structure?.strongest_common_driver) : "Unavailable"}</td></tr><tr><th>Minimum eigenvalue</th><td>{riskModelAvailable ? number(artifactRisk?.minimum_eigenvalue) : "Unavailable"}</td></tr><tr><th>Condition number</th><td>{riskModelAvailable ? number(artifactRisk?.condition_number) : "Unavailable"}</td></tr><tr><th>Positive semidefinite</th><td>{!riskModelAvailable || artifactRisk?.is_positive_semidefinite == null ? "Unavailable" : artifactRisk.is_positive_semidefinite ? "Yes" : "No"}</td></tr><tr><th>Largest redundancy</th><td>{structureAvailable && structure?.largest_redundancy_warning ? `${listing(structure.largest_redundancy_warning.left)} and ${listing(structure.largest_redundancy_warning.right)} (${percent(structure.largest_redundancy_warning.correlation)} correlation)` : "Unavailable"}</td></tr></tbody></table>{structure?.availability_reasons?.length ? <p role="status">Structure unavailable: {structure.availability_reasons.join(", ")}</p> : null}<table><caption>Component loadings and empirical clusters</caption><thead><tr><th>Component</th><th>Listing</th><th>Loading</th><th>Explained variance</th><th>Cluster</th></tr></thead><tbody>{components?.items.map((item) => <tr key={`${item.component_id}:${item.isin}:${item.exchange}:${item.code}`}><td>{item.component_id}</td><td>{item.code}.{item.exchange}</td><td>{number(item.loading)}</td><td>{percent(item.explained_variance)}</td><td>{item.cluster ?? "Unavailable"}</td></tr>)}</tbody></table></>}
      {activeTab === "portfolio-candidates" && <div className="multivariate-candidates">{candidates?.items.map((candidate) => <article key={candidate.candidate_id}><h3>{portfolioMethod(candidate.method)}{candidate.baseline ? " · Baseline" : ""}</h3><p>{candidate.status}{candidate.reasons.length ? ` · ${candidate.reasons.join(", ")}` : ""}</p><p>Volatility: {percent(candidate.volatility)} · VaR: {percent(candidate.var)} · CVaR: {percent(candidate.cvar)}</p><p>Total return: {percent(candidate.total_return)} · Maximum drawdown: {percent(candidate.max_drawdown)}</p><p>Average monthly return: {percent(candidate.average_monthly_return)} · Average annual return: {percent(candidate.average_annual_return)}</p><p>Maximum weight: {percent(candidate.maximum_weight)} · Effective holdings: {number(candidate.effective_holding_count)}</p><p>Herfindahl concentration: {number(candidate.herfindahl_index)} · Diversification ratio: {number(candidate.diversification_ratio)}</p><p>Gross historical yield: {percent(candidate.gross_ttm_distribution_yield)} · Gross monthly distribution: {number(candidate.gross_monthly_distribution)}</p><ul>{candidate.weights.map((weight) => <li key={`${weight.isin}:${weight.exchange}:${weight.code}`}>{weight.code}.{weight.exchange}: {percent(weight.weight)}</li>)}</ul></article>)}</div>}
      {activeTab === "risk-contributions" && <table><caption>Capital weights and percent risk contributions for every portfolio candidate</caption><thead><tr><th>Portfolio</th><th>Listing</th><th>Capital weight</th><th>Marginal contribution</th><th>Percent risk contribution</th></tr></thead><tbody>{contributions?.items.map((item) => <tr key={`${item.candidate_id}:${item.isin}:${item.exchange}:${item.code}`}><td>{portfolioMethod(item.method)}</td><td>{item.code}.{item.exchange}</td><td>{percent(item.weight)}</td><td>{number(item.marginal_risk_contribution)}</td><td>{percent(item.percent_risk_contribution)}</td></tr>)}</tbody></table>}
      {activeTab === "income-evidence" && <><p>All income values are gross historical observations. Net, sustainable, tax, and cost claims remain unavailable unless a verified source is present. Capital change uses the quoted market-price proxy.</p><table><caption>Monthly-distribution evidence</caption><thead><tr><th>Listing</th><th>Observed months</th><th>Coverage</th><th>Gross TTM yield</th><th>Trend</th><th>Cuts</th><th>Total return</th><th>Market-price capital change (NAV proxy)</th><th>Warnings</th></tr></thead><tbody>{income?.items.map((item) => <tr key={`${item.isin}:${item.exchange}:${item.code}`}><td>{item.code}.{item.exchange}</td><td>{item.observed_month_count}</td><td>{percent(item.observed_payment_coverage)}</td><td>{percent(item.gross_ttm_distribution_yield)}</td><td>{number(item.distribution_trend)}</td><td>{item.cut_count ?? "Unavailable"}</td><td>{percent(item.total_return)}</td><td>{percent(item.market_price_capital_change)}</td><td>{[...item.warnings, ...item.availability_reasons].join(", ") || "None"}</td></tr>)}</tbody></table></>}
      {activeTab === "performance" && performance && <><h3>Monthly portfolio returns</h3><table><caption>Compounded monthly return for every feasible portfolio</caption><thead><tr><th>Portfolio</th><th>Month</th><th>Return</th></tr></thead><tbody>{performance.period_returns.filter((item) => item.period === "monthly").map((item) => <tr key={`${item.candidate_id}:${item.period}:${item.label}`}><td>{portfolioMethod(item.method)}</td><td>{item.label}</td><td>{percent(item.return)}</td></tr>)}</tbody></table><h3>Annual portfolio returns</h3><table><caption>Compounded calendar-year return for every feasible portfolio</caption><thead><tr><th>Portfolio</th><th>Year</th><th>Return</th></tr></thead><tbody>{performance.period_returns.filter((item) => item.period === "annual").map((item) => <tr key={`${item.candidate_id}:${item.period}:${item.label}`}><td>{portfolioMethod(item.method)}</td><td>{item.label}</td><td>{percent(item.return)}</td></tr>)}</tbody></table></>}
      {activeTab === "validation" && <table><caption>Persisted walk-forward, stress, and scorecard evidence</caption><thead><tr><th>Type</th><th>Method</th><th>Status</th><th>Reason</th></tr></thead><tbody>{validation?.items.map((item, index) => <tr key={`${String(item.kind)}:${String(item.candidate_id)}:${index}`}><td>{String(item.kind ?? "validation")}</td><td>{String(item.method ?? "Unavailable")}</td><td>{String(item.status ?? "available")}</td><td>{String(item.reason ?? item.availability_reasons ?? "None")}</td></tr>)}</tbody></table>}
    </Panel>}
  </section>;
}
