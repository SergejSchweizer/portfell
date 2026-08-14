import { useEffect, useMemo, useRef, useState } from "react";
import Plotly from "plotly.js-dist-min";
import type { Data, Layout, PlotMouseEvent, PlotlyHTMLElement } from "plotly.js";
import { loadProjectContext } from "../api/client";
import { multivariateStatisticsApi } from "../api/multivariate-statistics";
import { Button } from "../components/button";
import { nextProgressSnapshot, progressPercent, type ProgressSnapshot } from "../computation-progress";
import { LoadingIndicator } from "../components/loading-state";
import { Panel } from "../components/panel";
import type {
  ApiMultivariateArtifacts,
  ApiAnalyticalPageView,
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
import { useDebouncedSave } from "../hooks/use-debounced-save";
import { queryClient, queryTiming } from "../query/client";
import { queryKeys } from "../query/keys";

type Tab = "overview" | "risk-structure" | "portfolio-candidates" | "risk-contributions" | "income-evidence" | "performance" | "validation";

const tabs: readonly Readonly<{ id: Tab; label: string }>[] = [
  { id: "overview", label: "Overview" },
  { id: "portfolio-candidates", label: "Portfolio Candidates" },
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

export function relativePerformanceValues(
  values: ApiMultivariatePerformance["instrument_series"][number]["values"],
  start: number,
  end: number,
): ApiMultivariatePerformance["instrument_series"][number]["values"] {
  const selected = values.filter((value) => {
    const time = Date.parse(value.date);
    return time >= start && time <= end;
  });
  const baseline = selected[0];
  if (!baseline) return [];
  const baselineGrowth = 1 + baseline.return;
  return selected.map((value) => ({
    ...value,
    return: baselineGrowth > 0 ? (1 + value.return) / baselineGrowth - 1 : value.return - baseline.return,
  }));
}

type PerformanceSeries = Readonly<{
  id: string;
  index: number;
  label: string;
  values: ApiMultivariatePerformance["instrument_series"][number]["values"];
}>;

const portfolioSeriesColors = ["#1769e0", "#137333", "#b06000", "#6b4fbb", "#007c91"];

function PlotlyPerformanceChart({
  instruments, portfolios, timeline, setHoveredIndex,
}: Readonly<{
  instruments: readonly PerformanceSeries[];
  portfolios: readonly PerformanceSeries[];
  timeline: ApiMultivariatePerformance["instrument_series"][number]["values"];
  setHoveredIndex: (index: number | null) => void;
}>) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = container.current;
    if (!element) return;
    const lineTrace = (series: PerformanceSeries, color: string, width: number): Data => ({
      type: "scatter",
      mode: "lines",
      name: series.label,
      x: series.values.map((value) => value.date),
      y: series.values.map((value) => value.return * 100),
      customdata: series.values.map((value) => value.date),
      hoverinfo: "none",
      line: { color, width },
    });
    const data = [
      ...instruments.map((series) => lineTrace(series, "#c7cdd4", 2)),
      ...portfolios.map((series) => lineTrace(series, portfolioSeriesColors[series.index % portfolioSeriesColors.length], 3)),
    ];
    const layout: Partial<Layout> = {
      autosize: true,
      height: 300,
      margin: { l: 58, r: 16, t: 16, b: 48 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      showlegend: false,
      hovermode: "x",
      xaxis: { type: "date", tickformat: "%b %Y", showgrid: false, zeroline: false },
      yaxis: {
        title: { text: "Cumulative relative gain (%)" },
        ticksuffix: "%",
        gridcolor: "#dfe3e8",
        zeroline: true,
        zerolinecolor: "#c7cdd4",
        zerolinewidth: 1,
      },
    };
    const config = { displayModeBar: false, responsive: true };
    const onHover = (event: PlotMouseEvent) => {
      const date = String(event.points[0]?.customdata ?? "");
      const index = timeline.findIndex((value) => value.date === date);
      if (index >= 0) setHoveredIndex(index);
    };
    let plot: PlotlyHTMLElement | null = null;
    void Plotly.react(element, data, layout, config).then((nextPlot) => {
      plot = nextPlot;
      nextPlot.on("plotly_hover", onHover);
    });
    return () => {
      plot?.removeAllListeners("plotly_hover");
      Plotly.purge(element);
    };
  }, [instruments, portfolios, setHoveredIndex, timeline]);

  return <div ref={container} className="performance-chart__plotly" aria-hidden="true" />;
}

function PerformanceChart({ performance, alignedPeriod }: Readonly<{ performance: ApiMultivariatePerformance; alignedPeriod?: Readonly<{ date_start: string; date_end: string }> }>) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [hiddenPortfolioIds, setHiddenPortfolioIds] = useState<ReadonlySet<string>>(new Set());
  const allValues = [...performance.instrument_series, ...performance.portfolio_series].flatMap(({ values }) => values);
  if (allValues.length === 0) return <p role="status">Performance data is unavailable for this run.</p>;
  const times = allValues.map((item) => Date.parse(item.date));
  const start = alignedPeriod ? Date.parse(alignedPeriod.date_start) : Math.min(...times);
  const end = alignedPeriod ? Date.parse(alignedPeriod.date_end) : Math.max(...times);
  const instruments = useMemo(() => performance.instrument_series.map((item, index) => ({
    id: `instrument:${item.isin}:${item.exchange}:${item.code}`,
    values: relativePerformanceValues(item.values, start, end),
    index,
    label: `${item.code}.${item.exchange}`,
  })), [end, performance.instrument_series, start]);
  const portfolios = useMemo(() => performance.portfolio_series.map((item, index) => ({
    id: `portfolio:${item.candidate_id ?? index}`,
    values: relativePerformanceValues(item.values, start, end),
    index,
    label: portfolioMethod(item.method),
  })), [end, performance.portfolio_series, start]);
  const visibleInstruments = instruments;
  const visiblePortfolios = useMemo(
    () => portfolios.filter(({ id }) => !hiddenPortfolioIds.has(id)),
    [hiddenPortfolioIds, portfolios],
  );
  const values = [...visibleInstruments, ...visiblePortfolios].flatMap((series) => series.values);
  const hasVisibleSeries = values.length > 0;
  const timeline = useMemo(() => (portfolios[0]?.values ?? instruments[0]?.values ?? []).filter((item) => {
    const time = Date.parse(item.date);
    return time >= start && time <= end;
  }), [end, instruments, portfolios, start]);
  const hoveredDate = hoveredIndex == null ? undefined : timeline[hoveredIndex]?.date;
    const hoveredValues = hoveredDate == null ? [] : visiblePortfolios.flatMap((series) => {
      const value = series.values.find((point) => point.date === hoveredDate);
      return value ? [{ label: series.label, value: value.return, className: `performance-chart__tooltip-portfolio performance-chart__tooltip-portfolio--${series.index % 5}` }] : [];
    });

  function togglePortfolio(id: string) {
    setHiddenPortfolioIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return <>
    <p className="performance-chart__legend">Relative cumulative monthly returns for every input instrument and feasible portfolio method.</p>
    <fieldset className="performance-chart__controls"><legend>Visible portfolio series</legend><ul className="performance-chart__series" aria-label="Portfolio series">{portfolios.map(({ id, index, label }) => <li key={id}><label><input type="checkbox" checked={!hiddenPortfolioIds.has(id)} onChange={() => togglePortfolio(id)} /><span className={`performance-chart__swatch performance-chart__portfolio performance-chart__portfolio--${index % 5}`} />{label}</label></li>)}</ul></fieldset>
    {hasVisibleSeries ? <div className="performance-chart" role="group" aria-label="Relative cumulative monthly return comparison for visible instruments and feasible portfolios. Hover or use arrow keys to inspect a month." tabIndex={0} onMouseLeave={() => setHoveredIndex(null)} onKeyDown={(event) => {
      if (timeline.length === 0) return;
      if (event.key === "Home") setHoveredIndex(0);
      else if (event.key === "End") setHoveredIndex(timeline.length - 1);
      else if (event.key === "ArrowLeft") setHoveredIndex((index) => Math.max(0, (index ?? timeline.length - 1) - 1));
      else if (event.key === "ArrowRight") setHoveredIndex((index) => Math.min(timeline.length - 1, (index ?? -1) + 1));
      else return;
      event.preventDefault();
    }}>
      <PlotlyPerformanceChart instruments={visibleInstruments} portfolios={visiblePortfolios} timeline={timeline} setHoveredIndex={setHoveredIndex} />
      {hoveredDate && <div className="performance-chart__tooltip" role="tooltip"><strong>{hoveredDate}</strong>{hoveredValues.map((item) => <span className={item.className} key={item.label}>{item.label}: {percent(item.value)}</span>)}</div>}
    </div> : <p role="status">Select at least one series to show the performance chart.</p>}
  </>;
}

function PortfolioOverviewMetrics({ candidates }: Readonly<{ candidates: ApiMultivariateCandidates["items"] }>) {
  return <table className="portfolio-overview-metrics"><caption>Portfolio overview metrics</caption><thead><tr><th>Portfolio</th><th>Status</th><th>Volatility</th><th>VaR</th><th>CVaR</th><th>Total return</th><th>MD</th><th>Monthly Return</th><th>Annual Return</th><th>Maximum weight</th><th>Holdings</th><th>Deversifikaton</th></tr></thead><tbody>{candidates.map((candidate) => <tr key={candidate.candidate_id}><th>{portfolioMethod(candidate.method)}</th><td>{candidate.status}</td><td>{percent(candidate.volatility)}</td><td>{percent(candidate.var)}</td><td>{percent(candidate.cvar)}</td><td>{percent(candidate.total_return)}</td><td>{percent(candidate.max_drawdown)}</td><td>{percent(candidate.average_monthly_return)}</td><td>{percent(candidate.average_annual_return)}</td><td>{percent(candidate.maximum_weight)}</td><td>{number(candidate.effective_holding_count)}</td><td>{number(candidate.diversification_ratio)}</td></tr>)}</tbody></table>;
}

export function MultivariateStatisticsPage() {
  const [revision, setRevision] = useState(0);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [pageView, setPageView] = useState<ApiAnalyticalPageView | null>(null);
  const [pageViewLoading, setPageViewLoading] = useState(true);
  const [pageViewError, setPageViewError] = useState<string | null>(null);
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
  const [starting, setStarting] = useState(false);
  const projectVersion = useRef(0);
  const progressSnapshot = useRef<ProgressSnapshot | null>(null);
  const candidateSelectionSave = useDebouncedSave<Readonly<{ runId: string; selectedCandidateIds: readonly string[] }>>(
    ({ runId, selectedCandidateIds }) => multivariateStatisticsApi.saveSelectedCandidates(runId, selectedCandidateIds),
    () => setMessage("Portfolio candidate selection could not be saved."),
  );

  const bivariateRunId = pageView?.input.bivariate_run_id ?? undefined;
  const selectedCandidateIds = run?.settings.selected_candidate_ids ?? [];
  const selectedCandidateId = selectedCandidateIds[0] ?? candidates?.items[0]?.candidate_id;
  const selectedContributions = useMemo(
    () => contributions?.items.filter((item) => item.candidate_id === selectedCandidateId) ?? [],
    [contributions, selectedCandidateId],
  );

  useEffect(() => {
    let cancelled = false;
    void loadProjectContext().then((context) => {
      if (!cancelled) setProjectId(context.current_project_id);
    }).catch((error: unknown) => {
      if (!cancelled) setPageViewError(error instanceof Error ? error.message : "Project context is unavailable.");
    });
    return () => { cancelled = true; };
  }, [revision]);

  useEffect(() => {
    if (!projectId) {
      setPageView(null);
      setPageViewLoading(false);
      return;
    }
    const controller = new AbortController();
    setPageViewLoading(true);
    setPageViewError(null);
    void queryClient.fetchQuery({
      queryKey: queryKeys.pageView(projectId, "multivariate_statistics"),
      queryFn: ({ signal }) => multivariateStatisticsApi.loadPageView(projectId, signal),
      staleTime: queryTiming.volatile,
    }).then((view) => {
      if (!controller.signal.aborted) setPageView(view);
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) setPageViewError(error instanceof Error ? error.message : "Multivariate statistics are unavailable.");
    }).finally(() => {
      if (!controller.signal.aborted) setPageViewLoading(false);
    });
    return () => controller.abort();
  }, [projectId, revision]);

  useEffect(() => {
    const resetProjectState = (event: Event) => {
      projectVersion.current += 1;
      candidateSelectionSave.cancel();
      progressSnapshot.current = null;
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
      setStarting(false);
      setMessage("");
      const context = event instanceof CustomEvent ? event.detail as { current_project_id?: string } : undefined;
      if (context?.current_project_id !== undefined) setProjectId(context.current_project_id ?? null);
      setRevision((value) => value + 1);
    };
    window.addEventListener("portfell:project-updated", resetProjectState);
    return () => window.removeEventListener("portfell:project-updated", resetProjectState);
  }, []);

  useEffect(() => {
    const runId = pageView?.run_id;
    const version = projectVersion.current;
    if (!runId || run?.run_id === runId) return;
    let cancelled = false;
    void multivariateStatisticsApi.loadRun(runId).then((nextRun) => {
      if (!cancelled && version === projectVersion.current) setRun(nextRun);
    }).catch(() => {
      if (!cancelled && version === projectVersion.current) setMessage("Multivariate results are unavailable.");
    });
    return () => { cancelled = true; };
  }, [pageView?.run_id, run?.run_id]);

  useEffect(() => {
    if (!projectId || run?.status !== "complete") return;
    const controller = new AbortController();
    const options = { signal: controller.signal };
    const load = async () => {
      if (activeTab === "overview") {
        const [nextSummary, nextCandidates, nextPerformance] = await Promise.all([
          multivariateStatisticsApi.loadSection<ApiMultivariateSummary>(projectId, "summary", options),
          multivariateStatisticsApi.loadSection<ApiMultivariateCandidates>(projectId, "candidates", options),
          multivariateStatisticsApi.loadSection<ApiMultivariatePerformance>(projectId, "performance", options),
        ]);
        if (!controller.signal.aborted) { setSummary(nextSummary.data); setCandidates(nextCandidates.data); setPerformance(nextPerformance.data); }
      } else if (activeTab === "risk-structure") {
        const [nextStructure, nextArtifacts, nextComponents] = await Promise.all([
          multivariateStatisticsApi.loadSection<ApiMultivariateStructure>(projectId, "structure", options),
          multivariateStatisticsApi.loadSection<ApiMultivariateArtifacts>(projectId, "artifacts", options),
          multivariateStatisticsApi.loadSection<ApiMultivariateComponents>(projectId, "components", options),
        ]);
        if (!controller.signal.aborted) { setStructure(nextStructure.data); setArtifacts(nextArtifacts.data); setComponents(nextComponents.data); }
      } else if (activeTab === "portfolio-candidates") {
        const next = await multivariateStatisticsApi.loadSection<ApiMultivariateCandidates>(projectId, "candidates", options);
        if (!controller.signal.aborted) setCandidates(next.data);
      } else if (activeTab === "risk-contributions") {
        const next = await multivariateStatisticsApi.loadSection<ApiMultivariateRiskContributions>(projectId, "risk_contributions", { ...options, candidateId: selectedCandidateId });
        if (!controller.signal.aborted) setContributions(next.data);
      } else if (activeTab === "income-evidence") {
        const next = await multivariateStatisticsApi.loadSection<ApiMultivariateIncomeEvidenceList>(projectId, "income_evidence", options);
        if (!controller.signal.aborted) setIncome(next.data);
      } else if (activeTab === "performance") {
        const next = await multivariateStatisticsApi.loadSection<ApiMultivariatePerformance>(projectId, "performance", options);
        if (!controller.signal.aborted) setPerformance(next.data);
      } else {
        const next = await multivariateStatisticsApi.loadSection<ApiMultivariateValidation>(projectId, "validation", options);
        if (!controller.signal.aborted) setValidation(next.data);
      }
    };
    void load().catch((error: unknown) => {
      if (!controller.signal.aborted) setMessage(error instanceof Error ? error.message : "The selected multivariate result is unavailable.");
    });
    return () => controller.abort();
  }, [activeTab, projectId, run?.run_id, run?.status, selectedCandidateId]);

  useEffect(() => {
    if (!run || run.status !== "running") return;
    const activeRunId = run.run_id;
    let cancelled = false;
    async function refreshMultivariateRun() {
      try {
        const current = await multivariateStatisticsApi.loadRun(activeRunId);
        if (cancelled) return;
        progressSnapshot.current = nextProgressSnapshot(
          progressSnapshot.current, current.run_id, progressPercent(current.completed_units, current.total_units),
        );
        setRun(current);
        if (current.status === "running") {
          return;
        }
        if (current.status === "failed") {
          setMessage(current.failure_reason || "Multivariate calculation failed. Please try again.");
          return;
        }
        setRevision((value) => value + 1);
        window.dispatchEvent(new Event("portfell:workflow-updated"));
      } catch (error) {
        if (!cancelled) setMessage(error instanceof Error ? error.message : "Could not retrieve multivariate calculation status.");
      }
    }
    void refreshMultivariateRun();
    const onStatusEvent = () => void refreshMultivariateRun();
    window.addEventListener("portfell:status-event", onStatusEvent);
    return () => {
      cancelled = true;
      window.removeEventListener("portfell:status-event", onStatusEvent);
    };
  }, [run?.run_id]);

  async function compute() {
    if (!projectId || !bivariateRunId || starting || run?.status === "running") return;
    setStarting(true);
    setMessage("Starting multivariate calculation…");
    try {
      const next = await multivariateStatisticsApi.startRun({ project_id: projectId, bivariate_run_id: bivariateRunId });
      progressSnapshot.current = nextProgressSnapshot(
        progressSnapshot.current, next.run_id, progressPercent(next.completed_units, next.total_units),
      );
      setRun(next);
      setRevision((value) => value + 1);
    } catch {
      setMessage("Multivariate calculation could not be started.");
    } finally {
      setStarting(false);
    }
  }

  function toggleCandidate(candidateId: string, selected: boolean) {
    if (!run) return;
    const next = selected ? [...selectedCandidateIds, candidateId] : selectedCandidateIds.filter((item) => item !== candidateId);
    setRun({ ...run, settings: { ...run.settings, selected_candidate_ids: next } });
    candidateSelectionSave.schedule({ runId: run.run_id, selectedCandidateIds: next });
  }

  const progress = run === null ? 0 : nextProgressSnapshot(
    progressSnapshot.current, run.run_id, progressPercent(run.completed_units, run.total_units),
  ).percent;
  const artifactRisk = artifacts?.risk_model;
  const structureAvailable = !structure?.availability_reasons?.length;
  const riskModelAvailable = !artifactRisk?.availability_reasons?.length;
  return <section className="multivariate-statistics-page" data-route="multivariate-statistics-page">
    {pageViewLoading ? <LoadingIndicator label="Loading selected project" compact /> : null}
    {pageViewError ? <p className="status-line" role="alert">Could not load the selected project. Showing the previous view.</p> : null}
    <Panel title="Multivariate Statistics">
      <div className="quote-fetch quote-fetch--panel bivariate-compute">
        <label htmlFor="multivariate-progress">Multivariate statistics progress</label>
        <progress id="multivariate-progress" value={progress} max={100} />
        <p className="status-line" aria-live="polite">{run ? `${run.phase} · ${run.completed_units} of ${run.total_units} phases complete · ${run.elapsed_seconds}s elapsed${run.estimated_remaining_seconds == null ? "" : ` · about ${run.estimated_remaining_seconds}s remaining`}` : "Ready to compute."}</p>
        <div className="quote-fetch__action">
          <Button type="button" variant="primary" onClick={() => void compute()} disabled={pageViewLoading || !projectId || !bivariateRunId || starting || run?.status === "running"} aria-busy={pageViewLoading || starting || run?.status === "running"}>
            {starting ? "Starting computation…" : run?.status === "running" ? "Computing…" : "Compute multivariate statistics"}
          </Button>
        </div>
      </div>
      {pageView?.status === "stale" && <p role="status">The prior multivariate result is stale because its bivariate input changed. Compute a new run to refresh it.</p>}
      {message && <p role="alert">{message}</p>}{run?.failure_reason && <p role="alert">{run.failure_reason}</p>}
    </Panel>
    <Panel title="Multivariate results">
      <div className="statistics-tabs" role="tablist" aria-label="Multivariate statistics views">{tabs.map((tab) => <button key={tab.id} role="tab" aria-selected={activeTab === tab.id} onClick={() => setActiveTab(tab.id)}>{tab.label}</button>)}</div>
      {activeTab === "overview" && <>{performance && <PerformanceChart performance={performance} alignedPeriod={summary?.aligned_period} />}{candidates && <PortfolioOverviewMetrics candidates={candidates.items} />}{summary?.availability_reasons?.length ? <p role="status">Unavailable evidence: {summary.availability_reasons.join(", ")}</p> : null}{historyRequirement(summary?.availability_reasons) ? <p role="status">{historyRequirement(summary?.availability_reasons)}</p> : null}</>}
      {activeTab === "risk-structure" && <><table className="multivariate-facts"><caption>Multivariate risk structure facts</caption><thead><tr><th>Fact</th><th>Value</th></tr></thead><tbody><tr><th>Effective rank</th><td>{structureAvailable ? number(structure?.effective_rank) : "Unavailable"}</td></tr><tr><th>Dominant component share</th><td>{structureAvailable ? percent(structure?.dominant_component_share) : "Unavailable"}</td></tr><tr><th>Components for 80%</th><td>{structureAvailable ? structure?.thresholds?.components_for_80pct ?? "Unavailable" : "Unavailable"}</td></tr><tr><th>Components for 90%</th><td>{structureAvailable ? structure?.thresholds?.components_for_90pct ?? "Unavailable" : "Unavailable"}</td></tr><tr><th>Components for 95%</th><td>{structureAvailable ? structure?.thresholds?.components_for_95pct ?? "Unavailable" : "Unavailable"}</td></tr><tr><th>Strongest common driver</th><td>{structureAvailable ? listing(structure?.strongest_common_driver) : "Unavailable"}</td></tr><tr><th>Minimum eigenvalue</th><td>{riskModelAvailable ? number(artifactRisk?.minimum_eigenvalue) : "Unavailable"}</td></tr><tr><th>Condition number</th><td>{riskModelAvailable ? number(artifactRisk?.condition_number) : "Unavailable"}</td></tr><tr><th>Positive semidefinite</th><td>{!riskModelAvailable || artifactRisk?.is_positive_semidefinite == null ? "Unavailable" : artifactRisk.is_positive_semidefinite ? "Yes" : "No"}</td></tr><tr><th>Largest redundancy</th><td>{structureAvailable && structure?.largest_redundancy_warning ? `${listing(structure.largest_redundancy_warning.left)} and ${listing(structure.largest_redundancy_warning.right)} (${percent(structure.largest_redundancy_warning.correlation)} correlation)` : "Unavailable"}</td></tr></tbody></table>{structure?.availability_reasons?.length ? <p role="status">Structure unavailable: {structure.availability_reasons.join(", ")}</p> : null}<table><caption>Component loadings and empirical clusters</caption><thead><tr><th>Component</th><th>Listing</th><th>Loading</th><th>Explained variance</th><th>Cluster</th></tr></thead><tbody>{components?.items.map((item) => <tr key={`${item.component_id}:${item.isin}:${item.exchange}:${item.code}`}><td>{item.component_id}</td><td>{item.code}.{item.exchange}</td><td>{number(item.loading)}</td><td>{percent(item.explained_variance)}</td><td>{item.cluster ?? "Unavailable"}</td></tr>)}</tbody></table></>}
      {activeTab === "portfolio-candidates" && <div className="multivariate-candidates">{candidates?.items.map((candidate) => <article key={candidate.candidate_id}><label><input type="checkbox" checked={selectedCandidateIds.includes(candidate.candidate_id)} onChange={(event) => toggleCandidate(candidate.candidate_id, event.target.checked)} /> Portfolio selection</label><h3>{portfolioMethod(candidate.method)}{candidate.baseline ? " · Baseline" : ""}</h3><p>{candidate.status}{candidate.reasons.length ? ` · ${candidate.reasons.join(", ")}` : ""}</p><p>Volatility: {percent(candidate.volatility)} · VaR: {percent(candidate.var)} · CVaR: {percent(candidate.cvar)}</p><p>Total return: {percent(candidate.total_return)} · Maximum drawdown: {percent(candidate.max_drawdown)}</p><p>Average monthly return: {percent(candidate.average_monthly_return)} · Average annual return: {percent(candidate.average_annual_return)}</p><p>Maximum weight: {percent(candidate.maximum_weight)} · Effective holdings: {number(candidate.effective_holding_count)}</p><p>Herfindahl concentration: {number(candidate.herfindahl_index)} · Diversification ratio: {number(candidate.diversification_ratio)}</p><p>Gross historical yield: {percent(candidate.gross_ttm_distribution_yield)} · Gross monthly distribution: {number(candidate.gross_monthly_distribution)}</p><ul>{candidate.weights.map((weight) => <li key={`${weight.isin}:${weight.exchange}:${weight.code}`}>{weight.code}.{weight.exchange}: {percent(weight.weight)}</li>)}</ul></article>)}</div>}
      {activeTab === "risk-contributions" && <table><caption>Capital weights and percent risk contributions for the selected candidate</caption><thead><tr><th>Listing</th><th>Capital weight</th><th>Marginal contribution</th><th>Percent risk contribution</th></tr></thead><tbody>{selectedContributions.map((item) => <tr key={`${item.candidate_id}:${item.isin}:${item.exchange}:${item.code}`}><td>{item.code}.{item.exchange}</td><td>{percent(item.weight)}</td><td>{number(item.marginal_risk_contribution)}</td><td>{percent(item.percent_risk_contribution)}</td></tr>)}</tbody></table>}
      {activeTab === "income-evidence" && <><p>All income values are gross historical observations. Net, sustainable, tax, and cost claims remain unavailable unless a verified source is present. Capital change uses the quoted market-price proxy.</p><table><caption>Monthly-distribution evidence</caption><thead><tr><th>Listing</th><th>Observed months</th><th>Coverage</th><th>Gross TTM yield</th><th>Trend</th><th>Cuts</th><th>Total return</th><th>Market-price capital change (NAV proxy)</th><th>Warnings</th></tr></thead><tbody>{income?.items.map((item) => <tr key={`${item.isin}:${item.exchange}:${item.code}`}><td>{item.code}.{item.exchange}</td><td>{item.observed_month_count}</td><td>{percent(item.observed_payment_coverage)}</td><td>{percent(item.gross_ttm_distribution_yield)}</td><td>{number(item.distribution_trend)}</td><td>{item.cut_count ?? "Unavailable"}</td><td>{percent(item.total_return)}</td><td>{percent(item.market_price_capital_change)}</td><td>{[...item.warnings, ...item.availability_reasons].join(", ") || "None"}</td></tr>)}</tbody></table></>}
      {activeTab === "performance" && performance && <><h3>Monthly portfolio returns</h3><table><caption>Compounded monthly return for every feasible portfolio</caption><thead><tr><th>Portfolio</th><th>Month</th><th>Return</th></tr></thead><tbody>{performance.period_returns.filter((item) => item.period === "monthly").map((item) => <tr key={`${item.candidate_id}:${item.period}:${item.label}`}><td>{portfolioMethod(item.method)}</td><td>{item.label}</td><td>{percent(item.return)}</td></tr>)}</tbody></table><h3>Annual portfolio returns</h3><table><caption>Compounded calendar-year return for every feasible portfolio</caption><thead><tr><th>Portfolio</th><th>Year</th><th>Return</th></tr></thead><tbody>{performance.period_returns.filter((item) => item.period === "annual").map((item) => <tr key={`${item.candidate_id}:${item.period}:${item.label}`}><td>{portfolioMethod(item.method)}</td><td>{item.label}</td><td>{percent(item.return)}</td></tr>)}</tbody></table></>}
      {activeTab === "validation" && <table><caption>Persisted walk-forward, stress, and scorecard evidence</caption><thead><tr><th>Type</th><th>Method</th><th>Status</th><th>Reason</th></tr></thead><tbody>{validation?.items.map((item, index) => <tr key={`${String(item.kind)}:${String(item.candidate_id)}:${index}`}><td>{String(item.kind ?? "validation")}</td><td>{String(item.method ?? "Unavailable")}</td><td>{String(item.status ?? "available")}</td><td>{String(item.reason ?? item.availability_reasons ?? "None")}</td></tr>)}</tbody></table>}
    </Panel>
  </section>;
}
