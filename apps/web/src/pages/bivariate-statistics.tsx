
import { useEffect, useRef, useState } from "react";
import { loadWorkflow } from "../api/client";
import { bivariateStatisticsApi, type BivariateRunData } from "../api/bivariate-statistics";
import { Button } from "../components/button";
import { LoadingState } from "../components/loading-state";
import { Panel } from "../components/panel";
import type { ApiBivariateMetricSummary, ApiBivariateRow, ApiBivariateSummary, ApiCovarianceMatrix, ApiPage, ApiPairMetricMatrix, ApiPairPlan, ApiResearchRun, ApiTailRiskScatter } from "../contracts";
import { useResource } from "../hooks/use-resource";

type PairwiseMatrixMetric = "covariance" | "pearson" | "spearman" | "downside" | "lower_tail_dependence" | "tail_coexceedance_rate" | "rolling_stability" | "drawdown_overlap" | "tail_risk_scatter";

const pairwiseMatrixTabs: readonly Readonly<{ metric: PairwiseMatrixMetric; label: string }>[] = [
  { metric: "covariance", label: "Covariance" },
  { metric: "pearson", label: "Pearson" },
  { metric: "spearman", label: "Spearman" },
  { metric: "downside", label: "Downside" },
  { metric: "lower_tail_dependence", label: "Tail Dependence" },
  { metric: "tail_coexceedance_rate", label: "Co-exceedance" },
  { metric: "rolling_stability", label: "Rolling-Correlation" },
  { metric: "drawdown_overlap", label: "Drawdown Overlap" },
  { metric: "tail_risk_scatter", label: "Tail-Risk Scatter" },
];

function metric(value: number | null | undefined): string {
  return value == null ? "—" : value.toFixed(4);
}

function covarianceColor(value: number, extent: number): string {
  if (extent === 0) return "#f1f5f9";
  const intensity = Math.min(1, Math.abs(value) / extent);
  const lightness = 96 - intensity * 42;
  return value >= 0 ? `hsl(152 58% ${lightness}%)` : `hsl(8 74% ${lightness}%)`;
}

function percent(value: number | null | undefined): string {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}

function dataPeriod(dateStart: string | undefined, dateEnd: string | undefined): string {
  return dateStart && dateEnd ? `${dateStart} to ${dateEnd}` : "—";
}

function BivariateMetricWindow({
  title, description, equation, notation, primary, secondary, primaryLabel, secondaryLabel,
  dateStart, dateEnd,
}: {
  title: string; description: string; equation: string; notation: string;
  primary: ApiBivariateMetricSummary | undefined; secondary?: ApiBivariateMetricSummary | undefined;
  primaryLabel: string; secondaryLabel?: string;
  dateStart?: string; dateEnd?: string;
}) {
  const histogram = primary?.histogram ?? [];
  const maximum = Math.max(1, ...histogram.map((bucket) => bucket.count));
  return <section className="bivariate-statistic bivariate-statistic--metric" aria-label={title}>
    <div className="bivariate-statistic__facts">
      <h3>{title}</h3>
      <p>{description}</p>
      <p className="univariate-equation">{equation}</p>
      <p className="univariate-notation">{notation}</p>
      <dl>
        <div><dt>Aligned data period</dt><dd>{dataPeriod(dateStart, dateEnd)}</dd></div>
        <div><dt>Pairs analysed</dt><dd>{primary ? "All computed pairs" : "—"}</dd></div>
        <div><dt>Average {primaryLabel}</dt><dd>{percent(primary?.mean)}</dd></div>
        <div><dt>Median {primaryLabel}</dt><dd>{percent(primary?.median)}</dd></div>
        <div><dt>Range</dt><dd>{primary ? `${percent(primary.minimum)} to ${percent(primary.maximum)}` : "—"}</dd></div>
        {secondary && <><div><dt>Average {secondaryLabel}</dt><dd>{percent(secondary.mean)}</dd></div><div><dt>Median {secondaryLabel}</dt><dd>{percent(secondary.median)}</dd></div></>}
      </dl>
    </div>
    <div className="bivariate-statistic__results">
      {primary ? <>
        <p className="bivariate-statistic__matrix-caption">Distribution across ISIN pairs · bar height: pair count</p>
        <div className="bivariate-histogram" role="img" aria-label={`${title} distribution`}>
          {histogram.map((bucket, index) => <div className="bivariate-histogram__bucket" key={`${bucket.lower}:${bucket.upper}`} title={`${(bucket.lower * 100).toFixed(2)}% to ${(bucket.upper * 100).toFixed(2)}%: ${bucket.count.toLocaleString()} ISIN pairs`}>
            <span className="bivariate-histogram__count">{bucket.count}</span>
            <span className="bivariate-histogram__bar" style={{ height: `${Math.max(5, bucket.count / maximum * 100)}%` }} />
            <span className="bivariate-histogram__label">{(bucket.lower * 100).toFixed(1)}%</span>
          </div>)}
        </div>
        <p className="bivariate-histogram__axis">{primaryLabel} (%)</p>
      </> : <p className="status-line">Compute bivariate statistics to populate this distribution.</p>}
    </div>
  </section>;
}

function PairMatrix({
  matrix, title, hoveredCell, setHoveredCell,
}: {
  matrix: ApiPairMetricMatrix | null; title: string;
  hoveredCell: { row: number; column: number } | null;
  setHoveredCell: (value: { row: number; column: number } | null) => void;
}) {
  const extent = Math.max(0, ...(matrix?.values.flat().flatMap((value) => value === null ? [] : [Math.abs(value)]) ?? []));
  const highlightedRow = (index: number): boolean => hoveredCell?.row === index;
  const highlightedColumn = (index: number): boolean => hoveredCell?.column === index;
  return <div className="bivariate-statistic__results">
    {matrix === null ? <p className="status-line">Compute bivariate statistics to populate the {title.toLowerCase()} matrix.</p> : matrix.labels.length > 0 ? <>
      <p className="bivariate-statistic__matrix-caption">{title} matrix · {dataPeriod(matrix.date_start, matrix.date_end)} · {matrix.observation_count.toLocaleString()} shared observations</p>
      <table className="covariance-matrix" onMouseLeave={() => setHoveredCell(null)}>
        <thead><tr><th scope="col">ISIN</th>{matrix.labels.map((label, index) => <th scope="col" key={label.isin} className={highlightedColumn(index) ? "is-hovered-column" : undefined} title={`${label.label} · ${label.isin}`} onMouseEnter={() => setHoveredCell({ row: index, column: index })}>{label.label}</th>)}</tr></thead>
        <tbody>{matrix.labels.map((label, rowIndex) => <tr key={label.isin}><th scope="row" className={highlightedRow(rowIndex) ? "is-hovered-row" : undefined} title={`${label.label} · ${label.isin}`} onMouseEnter={() => setHoveredCell({ row: rowIndex, column: rowIndex })}>{label.label}</th>{matrix.values[rowIndex].map((value, columnIndex) => { const column = matrix.labels[columnIndex]; return <td key={`${label.isin}:${column.isin}`} className={`${value === null ? "covariance-matrix__empty" : ""} ${highlightedRow(rowIndex) ? "is-hovered-row" : ""} ${highlightedColumn(columnIndex) ? "is-hovered-column" : ""}`.trim() || undefined} title={value === null ? `Row: ${label.label} (${label.isin})\nColumn: ${column.label} (${column.isin})\nDuplicate or self relation omitted` : `Row: ${label.label} (${label.isin})\nColumn: ${column.label} (${column.isin})\n${title}: ${metric(value)}`} style={value === null ? undefined : { backgroundColor: covarianceColor(value, extent) }} onMouseEnter={() => setHoveredCell({ row: rowIndex, column: columnIndex })}>{metric(value)}</td>})}</tr>)}</tbody>
      </table>
      <p className="covariance-matrix__legend"><span className="covariance-matrix__legend-negative" /> Lower values <span className="covariance-matrix__legend-neutral" /> Near zero <span className="covariance-matrix__legend-positive" /> Higher values</p>
    </> : <p className="status-line">No common log-return observations are available.</p>}
  </div>;
}

function TailRiskScatter({ scatter }: { scatter: ApiTailRiskScatter | null }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const layout = useRef<{ x: (value: number) => number; y: (value: number) => number } | null>(null);
  const [hoveredPoint, setHoveredPoint] = useState<ApiTailRiskScatter["points"][number] | null>(null);
  useEffect(() => {
    const element = canvas.current;
    if (!element || !scatter || scatter.points.length === 0) return;
    const context = element.getContext("2d");
    if (!context) return;
    const width = element.width;
    const height = element.height;
    const padding = { left: 68, right: 28, top: 30, bottom: 58 };
    const plotWidth = width - padding.left - padding.right;
    const plotHeight = height - padding.top - padding.bottom;
    const domain = (values: readonly number[]) => {
      const minimum = Math.min(...values);
      const maximum = Math.max(...values);
      const spread = Math.max(maximum - minimum, 0.02);
      const margin = Math.max(spread * 0.14, 0.01);
      return { minimum: Math.max(0, minimum - margin), maximum: Math.min(1, maximum + margin) };
    };
    const xDomain = domain(scatter.points.map((point) => point.tail_dependence));
    const yDomain = domain(scatter.points.map((point) => point.coexceedance_rate));
    const x = (value: number) => padding.left + (value - xDomain.minimum) / (xDomain.maximum - xDomain.minimum) * plotWidth;
    const y = (value: number) => padding.top + (1 - (value - yDomain.minimum) / (yDomain.maximum - yDomain.minimum)) * plotHeight;
    layout.current = { x, y };
    const xMedian = scatter.tail_dependence_median ?? 0.5;
    const yMedian = scatter.coexceedance_rate_median ?? 0.5;
    const xEnd = x(xDomain.maximum);
    const yEnd = y(yDomain.minimum);

    context.clearRect(0, 0, width, height);
    context.fillStyle = "#edf8f1";
    context.fillRect(padding.left, y(yMedian), x(xMedian) - padding.left, yEnd - y(yMedian));
    context.fillStyle = "#fff0ef";
    context.fillRect(x(xMedian), padding.top, xEnd - x(xMedian), y(yMedian) - padding.top);
    context.strokeStyle = "#e1e6eb";
    context.lineWidth = 1;
    context.font = "12px system-ui";
    context.fillStyle = "#667085";
    for (let index = 0; index <= 4; index += 1) {
      const xTick = xDomain.minimum + (xDomain.maximum - xDomain.minimum) * index / 4;
      const yTick = yDomain.minimum + (yDomain.maximum - yDomain.minimum) * index / 4;
      context.beginPath();
      context.moveTo(x(xTick), padding.top);
      context.lineTo(x(xTick), yEnd);
      context.moveTo(padding.left, y(yTick));
      context.lineTo(xEnd, y(yTick));
      context.stroke();
      context.fillText(`${(xTick * 100).toFixed(1)}%`, x(xTick) - 14, height - 35);
      context.fillText(`${(yTick * 100).toFixed(1)}%`, 8, y(yTick) + 4);
    }
    context.strokeStyle = "#98a2b3";
    context.beginPath();
    context.moveTo(padding.left, padding.top);
    context.lineTo(padding.left, yEnd);
    context.lineTo(xEnd, yEnd);
    context.stroke();
    context.setLineDash([4, 4]);
    context.beginPath();
    context.moveTo(x(xMedian), padding.top);
    context.lineTo(x(xMedian), yEnd);
    context.moveTo(padding.left, y(yMedian));
    context.lineTo(xEnd, y(yMedian));
    context.stroke();
    context.setLineDash([]);
    context.font = "600 12px system-ui";
    context.fillStyle = "#137333";
    context.fillText("Best diversifiers", padding.left + 8, yEnd - 10);
    context.fillStyle = "#b3261e";
    context.fillText("Tail-risk concentration", x(xMedian) + 8, padding.top + 16);
    for (const point of scatter.points) {
      const isBestDiversifier = point.tail_dependence <= xMedian && point.coexceedance_rate <= yMedian;
      const isDangerous = point.tail_dependence > xMedian && point.coexceedance_rate > yMedian;
      const isHovered = hoveredPoint === point;
      context.fillStyle = isDangerous ? "rgba(211, 47, 47, .78)" : isBestDiversifier ? "rgba(19, 115, 51, .78)" : "rgba(23, 105, 224, .62)";
      context.beginPath();
      context.arc(x(point.tail_dependence), y(point.coexceedance_rate), isHovered ? 6 : 4, 0, Math.PI * 2);
      context.fill();
      if (isHovered) {
        context.strokeStyle = "#101828";
        context.lineWidth = 2;
        context.stroke();
      }
    }
    context.fillStyle = "#344054";
    context.font = "600 13px system-ui";
    context.save();
    context.translate(16, padding.top + plotHeight / 2);
    context.rotate(-Math.PI / 2);
    context.fillText("Co-exceedance Rate", 0, 0);
    context.restore();
    context.fillText("Tail Dependence", padding.left + plotWidth / 2 - 48, height - 10);
  }, [hoveredPoint, scatter]);

  if (!scatter) return <div className="bivariate-statistic__results"><p className="status-line">Compute bivariate statistics to populate the tail-risk scatterplot.</p></div>;
  return <div className="bivariate-statistic__results">
    <p className="bivariate-statistic__matrix-caption">One point per ISIN pair · {dataPeriod(scatter.date_start, scatter.date_end)} · {scatter.observation_count.toLocaleString()} shared observations</p>
    <div className="tail-risk-scatter__frame">
      <canvas ref={canvas} className="tail-risk-scatter" width={840} height={460} role="img" aria-label={`Tail dependence against co-exceedance rate for ${scatter.pair_count.toLocaleString()} ISIN pairs`} onMouseLeave={() => setHoveredPoint(null)} onMouseMove={(event) => {
        const element = event.currentTarget;
        if (!layout.current) return;
        const bounds = element.getBoundingClientRect();
        const pointerX = (event.clientX - bounds.left) * element.width / bounds.width;
        const pointerY = (event.clientY - bounds.top) * element.height / bounds.height;
        const nearest = scatter.points.reduce<{ point: ApiTailRiskScatter["points"][number] | null; distance: number }>((current, point) => {
          const distance = Math.hypot(layout.current!.x(point.tail_dependence) - pointerX, layout.current!.y(point.coexceedance_rate) - pointerY);
          return distance < current.distance ? { point, distance } : current;
        }, { point: null, distance: 14 });
        setHoveredPoint(nearest.point);
      }} />
      {hoveredPoint && <div className="tail-risk-scatter__tooltip" role="tooltip"><strong>{hoveredPoint.left_code}.{hoveredPoint.left_exchange} ↔ {hoveredPoint.right_code}.{hoveredPoint.right_exchange}</strong><span>{hoveredPoint.left_isin} ↔ {hoveredPoint.right_isin}</span><span>Tail dependence: {(hoveredPoint.tail_dependence * 100).toFixed(2)}%</span><span>Co-exceedance rate: {(hoveredPoint.coexceedance_rate * 100).toFixed(2)}%</span></div>}
    </div>
    <p className="tail-risk-scatter__legend"><span className="tail-risk-scatter__legend-good" /> Best diversifiers <span className="tail-risk-scatter__legend-neutral" /> Mixed tail profile <span className="tail-risk-scatter__legend-bad" /> Tail-risk concentration</p>
  </div>;
}

export function BivariateStatisticsPage() {
  const [workflowRevision, setWorkflowRevision] = useState(0);
  const workflow = useResource(loadWorkflow, [workflowRevision]);
  const [run, setRun] = useState<ApiResearchRun | null>(null);
  const [results, setResults] = useState<ApiPage<ApiBivariateRow> | null>(null);
  const [covarianceMatrix, setCovarianceMatrix] = useState<ApiCovarianceMatrix | null>(null);
  const [pearsonMatrix, setPearsonMatrix] = useState<ApiPairMetricMatrix | null>(null);
  const [spearmanMatrix, setSpearmanMatrix] = useState<ApiPairMetricMatrix | null>(null);
  const [downsideMatrix, setDownsideMatrix] = useState<ApiPairMetricMatrix | null>(null);
  const [lowerTailDependenceMatrix, setLowerTailDependenceMatrix] = useState<ApiPairMetricMatrix | null>(null);
  const [tailCoexceedanceRateMatrix, setTailCoexceedanceRateMatrix] = useState<ApiPairMetricMatrix | null>(null);
  const [rollingStabilityMatrix, setRollingStabilityMatrix] = useState<ApiPairMetricMatrix | null>(null);
  const [drawdownOverlapMatrix, setDrawdownOverlapMatrix] = useState<ApiPairMetricMatrix | null>(null);
  const [tailRiskScatter, setTailRiskScatter] = useState<ApiTailRiskScatter | null>(null);
  const [summary, setSummary] = useState<ApiBivariateSummary | null>(null);
  const [hoveredMatrixCell, setHoveredMatrixCell] = useState<{ row: number; column: number } | null>(null);
  const [activePairwiseMetric, setActivePairwiseMetric] = useState<PairwiseMatrixMetric>("covariance");
  const [message, setMessage] = useState("");
  const persistedRunId = workflow.status === "ready"
    ? workflow.data.stages.bivariate_statistics.bivariate_run_id
    : undefined;

  function applyRunData(data: BivariateRunData) {
    setResults(data.results);
    setCovarianceMatrix(data.covariance);
    setSummary(data.summary);
    setPearsonMatrix(data.pearson);
    setSpearmanMatrix(data.spearman);
    setDownsideMatrix(data.downside);
    setLowerTailDependenceMatrix(data.lowerTailDependence);
    setTailCoexceedanceRateMatrix(data.tailCoexceedanceRate);
    setRollingStabilityMatrix(data.rollingStability);
    setDrawdownOverlapMatrix(data.drawdownOverlap);
    setTailRiskScatter(data.tailRiskScatter);
  }

  useEffect(() => {
    const resetProjectState = () => {
      setRun(null);
      setResults(null);
      setCovarianceMatrix(null);
      setPearsonMatrix(null);
      setSpearmanMatrix(null);
      setDownsideMatrix(null);
      setLowerTailDependenceMatrix(null);
      setTailCoexceedanceRateMatrix(null);
      setRollingStabilityMatrix(null);
      setDrawdownOverlapMatrix(null);
      setTailRiskScatter(null);
      setSummary(null);
      setMessage("");
      setWorkflowRevision((value) => value + 1);
    };
    window.addEventListener("portfell:project-updated", resetProjectState);
    return () => window.removeEventListener("portfell:project-updated", resetProjectState);
  }, []);

  useEffect(() => {
    if (!run || run.status !== "running") return;
    const activeRunId = run.run_id;
    let cancelled = false;
    let timeoutId: number | undefined;
    async function pollBivariateRun() {
      try {
        const current = await bivariateStatisticsApi.loadRun(activeRunId);
        if (cancelled) return;
        setRun(current);
        if (current.status === "running") {
          setMessage(`${current.completed.toLocaleString()} of ${current.total.toLocaleString()} pair statistics computed.`);
          timeoutId = window.setTimeout(() => void pollBivariateRun(), 750);
          return;
        }
        if (current.status === "failed") {
          setMessage("Bivariate computation failed. Please try again.");
          return;
        }
        const data = await bivariateStatisticsApi.loadRunData(current.run_id);
        if (cancelled) return;
        applyRunData(data);
        setMessage(`${data.results.total.toLocaleString()} pair statistics computed.`);
        window.dispatchEvent(new Event("portfell:workflow-updated"));
      } catch (error) {
        if (!cancelled) setMessage(error instanceof Error ? error.message : "Could not retrieve bivariate computation status.");
      }
    }
    void pollBivariateRun();
    return () => {
      cancelled = true;
      if (timeoutId !== undefined) window.clearTimeout(timeoutId);
    };
  // Keep the active poll alive while the status changes to complete, otherwise
  // its matrix requests are cancelled by the effect cleanup before they render.
  }, [run?.run_id]);

  useEffect(() => {
    if (!persistedRunId || run?.run_id === persistedRunId) return;
    const restoredRunId = persistedRunId;
    let cancelled = false;
    async function restoreBivariateRun() {
      try {
        const [savedRun, data] = await Promise.all([
          bivariateStatisticsApi.loadRun(restoredRunId),
          bivariateStatisticsApi.loadRunData(restoredRunId),
        ]);
        if (cancelled) return;
        setRun(savedRun);
        applyRunData(data);
        setMessage(`${data.results.total.toLocaleString()} saved pair statistics restored.`);
      } catch (error) {
        if (!cancelled) setMessage(error instanceof Error ? error.message : "Could not restore saved bivariate statistics.");
      }
    }
    void restoreBivariateRun();
    return () => { cancelled = true; };
  }, [persistedRunId, run?.run_id]);

  if (workflow.status === "loading" || workflow.status === "idle") return <LoadingState label="Loading bivariate statistics" />;
  if (workflow.status === "error") return <p>Workflow state is unavailable.</p>;
  const selectionId = workflow.data.stages.univariate_statistics.univariate_selection_id;
  if (!selectionId) {
    return <Panel title="Bivariate Statistics"><p>Complete univariate statistics and select at least two ISINs first.</p></Panel>;
  }

  async function compute() {
    const univariateSelectionId = selectionId;
    if (!univariateSelectionId) return;
    setMessage("Planning bivariate statistics…");
    try {
      const nextPlan = await bivariateStatisticsApi.plan({ univariate_selection_id: univariateSelectionId });
      if (!nextPlan.allowed) {
        setMessage(`Pair count exceeds the ${nextPlan.pair_limit} limit or has fewer than two selected ISINs.`);
        return;
      }
      setMessage("Computing bivariate statistics…");
      const nextRun = await bivariateStatisticsApi.startRun({ univariate_selection_id: univariateSelectionId });
      setRun(nextRun);
      if (nextRun.status === "complete") {
        const data = await bivariateStatisticsApi.loadRunData(nextRun.run_id);
        applyRunData(data);
        setMessage(`${data.results.total.toLocaleString()} pair statistics computed.`);
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Bivariate computation failed.");
    }
  }

  const diagnostics = covarianceMatrix?.diagnostics;
  const activeMetricSummary = activePairwiseMetric === "pearson"
    ? summary?.metrics.pearson_correlation
    : activePairwiseMetric === "spearman"
      ? summary?.metrics.spearman_correlation
      : activePairwiseMetric === "downside"
        ? summary?.metrics.downside_correlation
        : activePairwiseMetric === "lower_tail_dependence"
          ? summary?.metrics.lower_tail_dependence
          : activePairwiseMetric === "rolling_stability"
            ? summary?.metrics.rolling_correlation_stability
            : activePairwiseMetric === "drawdown_overlap"
              ? summary?.metrics.drawdown_overlap_rate
          : summary?.metrics.tail_coexceedance_rate;
  const activeCorrelation = activeMetricSummary;
  const tailDiagnostics = summary?.tail_dependence_diagnostics;
  const coexceedanceDiagnostics = summary?.coexceedance_diagnostics;
  const scatterDiagnostics = tailRiskScatter?.diagnostics;
  const rollingDiagnostics = summary?.rolling_correlation_diagnostics;
  const drawdownDiagnostics = summary?.drawdown_overlap_diagnostics;
  const activeMatrix = activePairwiseMetric === "covariance"
    ? covarianceMatrix
    : activePairwiseMetric === "pearson"
      ? pearsonMatrix
      : activePairwiseMetric === "spearman"
        ? spearmanMatrix
        : activePairwiseMetric === "downside"
          ? downsideMatrix
          : activePairwiseMetric === "lower_tail_dependence"
            ? lowerTailDependenceMatrix
            : activePairwiseMetric === "rolling_stability"
              ? rollingStabilityMatrix
            : activePairwiseMetric === "drawdown_overlap"
              ? drawdownOverlapMatrix
              : tailCoexceedanceRateMatrix;
  const activeMetricLabel = activePairwiseMetric === "lower_tail_dependence"
    ? "tail dependence"
    : activePairwiseMetric === "tail_coexceedance_rate"
      ? "co-exceedance rate"
      : "correlation";
  const activeMatrixTitle = activePairwiseMetric === "covariance"
    ? "Covariance"
    : pairwiseMatrixTabs.find((tab) => tab.metric === activePairwiseMetric)!.label;
  return (
    <Panel title="Bivariate Statistics">
      <div className="quote-fetch quote-fetch--panel bivariate-compute">
        <label htmlFor="bivariate-progress">Bivariate statistics progress</label>
        <progress id="bivariate-progress" max={100} value={run?.percent ?? 0} />
        <p className="status-line" aria-live="polite">{message || "Compute statistics for the ISINs selected in univariate statistics."}</p>
        <div className="quote-fetch__action">
          <Button type="button" variant="primary" disabled={run?.status === "running"} onClick={() => void compute()}>
            {run?.status === "running" ? "Computing…" : "Compute Bivariate Statistics"}
          </Button>
        </div>
      </div>
      <section className="bivariate-statistic" aria-labelledby="pairwise-dependence-title">
        <div className="bivariate-statistic__tabs" role="tablist" aria-label="Pairwise dependence statistic">
          {pairwiseMatrixTabs.map((tab) => <button key={tab.metric} type="button" role="tab" aria-selected={activePairwiseMetric === tab.metric} className={activePairwiseMetric === tab.metric ? "is-active" : undefined} onClick={() => setActivePairwiseMetric(tab.metric)}>{tab.label}</button>)}
        </div>
        <div className="bivariate-statistic__facts">
          <h3 id="pairwise-dependence-title">{activePairwiseMetric === "covariance" ? "Covariance" : activePairwiseMetric === "pearson" ? "Pearson Correlation" : activePairwiseMetric === "spearman" ? "Spearman Correlation" : activePairwiseMetric === "downside" ? "Downside Correlation" : activeMatrixTitle}</h3>
          {activePairwiseMetric === "tail_risk_scatter" ? <>
            <p>Each point compares one ISIN pair's lower-tail dependence with its simultaneous lower-tail event rate. The lower-left quadrant identifies the strongest tail-risk diversifiers; the upper-right quadrant identifies the most concentrated joint-tail exposure.</p>
            <p className="univariate-equation">(λᴸᵢⱼ, Cᵢⱼ)</p>
            <p className="univariate-notation">λᴸ: lower-tail dependence · C: co-exceedance rate · i, j: ISIN pair</p>
            <dl>
              <div><dt>Aligned data period</dt><dd>{dataPeriod(tailRiskScatter?.date_start, tailRiskScatter?.date_end)}</dd></div>
              <div><dt>ISIN pairs plotted</dt><dd>{tailRiskScatter?.pair_count.toLocaleString() ?? "—"}</dd></div>
              <div><dt>Shared observations</dt><dd>{tailRiskScatter?.observation_count.toLocaleString() ?? "—"}</dd></div>
              <div><dt>Tail-dependence median</dt><dd>{percent(tailRiskScatter?.tail_dependence_median)}</dd></div>
              <div><dt>Co-exceedance median</dt><dd>{percent(tailRiskScatter?.coexceedance_rate_median)}</dd></div>
              <div><dt>Best-diversifier quadrant</dt><dd>{scatterDiagnostics ? `${scatterDiagnostics.best_diversifiers.toLocaleString()} pairs (${(scatterDiagnostics.best_diversifiers / Math.max(1, tailRiskScatter?.pair_count ?? 0) * 100).toFixed(1)}%)` : "—"}</dd></div>
              <div><dt>Tail-risk concentration quadrant</dt><dd>{scatterDiagnostics ? `${scatterDiagnostics.tail_concentration.toLocaleString()} pairs (${(scatterDiagnostics.tail_concentration / Math.max(1, tailRiskScatter?.pair_count ?? 0) * 100).toFixed(1)}%)` : "—"}</dd></div>
              <div><dt>Mixed quadrants</dt><dd>{scatterDiagnostics ? `${scatterDiagnostics.high_tail_only.toLocaleString()} high-tail only · ${scatterDiagnostics.high_coexceedance_only.toLocaleString()} high-co-exceedance only` : "—"}</dd></div>
              <div><dt>Pareto-best diversifiers</dt><dd>{scatterDiagnostics ? `${scatterDiagnostics.pareto_best_pair_count.toLocaleString()} pairs` : "—"}</dd></div>
              <div><dt>Leading Pareto pair</dt><dd title={scatterDiagnostics?.best_pareto_pair ?? undefined}>{scatterDiagnostics?.best_pareto_pair ?? "—"}</dd></div>
              <div><dt>Highest tail-risk pair</dt><dd title={scatterDiagnostics?.worst_tail_risk_pair ?? undefined}>{scatterDiagnostics?.worst_tail_risk_pair ? `${scatterDiagnostics.worst_tail_risk_pair} (score ${scatterDiagnostics.worst_tail_risk_score?.toFixed(2) ?? "—"})` : "—"}</dd></div>
              <div><dt>Average λᴸ vs. independence</dt><dd>{scatterDiagnostics?.average_tail_independence_multiple == null ? "—" : `${scatterDiagnostics.average_tail_independence_multiple.toFixed(1)}× (5% baseline)`}</dd></div>
              <div><dt>Average co-exceedance vs. independence</dt><dd>{scatterDiagnostics?.average_coexceedance_independence_multiple == null ? "—" : `${scatterDiagnostics.average_coexceedance_independence_multiple.toFixed(1)}× (0.25% baseline)`}</dd></div>
              <div><dt>Most concentrated ISIN</dt><dd title={scatterDiagnostics?.most_concentrated_isin ?? undefined}>{scatterDiagnostics?.most_concentrated_isin ? `${scatterDiagnostics.most_concentrated_isin} (${scatterDiagnostics.upper_right_links} upper-right links)` : "—"}</dd></div>
              <div><dt>Upper-right clusters</dt><dd>{scatterDiagnostics ? `${scatterDiagnostics.upper_right_cluster_count} clusters · largest ${scatterDiagnostics.largest_upper_right_cluster_size} ISINs` : "—"}</dd></div>
              <div><dt>Rolling stability (λᴸ / co-exceedance)</dt><dd>{scatterDiagnostics ? `${percent(scatterDiagnostics.average_tail_stability)} / ${percent(scatterDiagnostics.average_coexceedance_stability)}` : "—"}</dd></div>
              <div><dt>Joint-tail events (median / min)</dt><dd>{scatterDiagnostics ? `${scatterDiagnostics.median_joint_tail_events ?? "—"} / ${scatterDiagnostics.minimum_joint_tail_events ?? "—"}` : "—"}</dd></div>
            </dl>
          </> : activePairwiseMetric === "rolling_stability" || activePairwiseMetric === "drawdown_overlap" ? <>
            <p>{activePairwiseMetric === "rolling_stability" ? "Variation in sampled 60-observation rolling Pearson correlations; lower values indicate more reliable diversification relationships." : "Share of observations where both ISINs are at least 5% below their preceding cumulative-return peak."}</p>
            <p className="univariate-equation">{activePairwiseMetric === "rolling_stability" ? "sᵨ = √(Σ(ρₜ − ρ̄)² / (n − 1))" : "Oᵢⱼ = (1/T) Σ 𝟙(DDᵢ ≤ −5%, DDⱼ ≤ −5%)"}</p>
            <p className="univariate-notation">{activePairwiseMetric === "rolling_stability" ? "ρₜ: rolling correlation · ρ̄: mean rolling correlation · sᵨ: stability standard deviation" : "DD: drawdown · T: shared observations · 𝟙: indicator function"}</p>
            {activePairwiseMetric === "rolling_stability" ? <dl><div><dt>Aligned data period</dt><dd>{dataPeriod(summary?.date_start, summary?.date_end)}</dd></div><div><dt>Pairs analysed</dt><dd>{summary?.pair_count.toLocaleString() ?? "—"}</dd></div><div><dt>Average / median instability</dt><dd>{percent(activeMetricSummary?.mean)} / {percent(activeMetricSummary?.median)}</dd></div><div><dt>90th percentile</dt><dd>{percent(rollingDiagnostics?.percentile_90)}</dd></div><div><dt>Pairs ≥ 10% / 20% / 30%</dt><dd>{rollingDiagnostics ? `${rollingDiagnostics.high_threshold_pairs.toLocaleString()} / ${rollingDiagnostics.high_20_pairs.toLocaleString()} / ${rollingDiagnostics.high_30_pairs.toLocaleString()}` : "—"}</dd></div><div><dt>Least / most unstable pair</dt><dd>{rollingDiagnostics?.best_pair && rollingDiagnostics.worst_pair ? `${rollingDiagnostics.best_pair} / ${rollingDiagnostics.worst_pair}` : "—"}</dd></div><div><dt>Most unstable ISIN</dt><dd title={rollingDiagnostics?.most_exposed_listing ?? undefined}>{rollingDiagnostics?.most_exposed_listing ? `${rollingDiagnostics.most_exposed_listing} (${percent(rollingDiagnostics.most_exposed_average)})` : "—"}</dd></div><div><dt>Rolling-window coverage</dt><dd>{rollingDiagnostics ? `${rollingDiagnostics.window_length}-day windows · median ${rollingDiagnostics.median_window_count ?? "—"} windows` : "—"}</dd></div><div><dt>Shared observations (median / min)</dt><dd>{rollingDiagnostics ? `${rollingDiagnostics.median_shared_observations ?? "—"} / ${rollingDiagnostics.minimum_shared_observations ?? "—"}` : "—"}</dd></div><div><dt>Average rolling correlation / trend</dt><dd>{percent(rollingDiagnostics?.average_rolling_correlation)} / {percent(rollingDiagnostics?.average_correlation_trend)}</dd></div><div><dt>Regime-switch pairs</dt><dd>{rollingDiagnostics ? `${rollingDiagnostics.regime_switch_pairs.toLocaleString()} pairs · ${rollingDiagnostics.average_regime_switches?.toFixed(1) ?? "—"} switches on average` : "—"}</dd></div><div><dt>Average stress correlation</dt><dd>{percent(rollingDiagnostics?.average_stress_correlation)}</dd></div><div><dt>Average Pearson gap</dt><dd>{percent(rollingDiagnostics?.average_pearson_gap)}</dd></div><div><dt>Worst-window correlation</dt><dd title={rollingDiagnostics?.worst_window_pair ?? undefined}>{rollingDiagnostics?.worst_window_pair ? `${rollingDiagnostics.worst_window_pair} (${percent(rollingDiagnostics.worst_window_correlation)})` : "—"}</dd></div><div><dt>Average worst-window correlation</dt><dd>{percent(rollingDiagnostics?.average_worst_window_correlation)}</dd></div><div><dt>Risk clusters (≥ 10%)</dt><dd>{rollingDiagnostics ? `${rollingDiagnostics.cluster_count} clusters · largest ${rollingDiagnostics.largest_cluster_size} ISINs` : "—"}</dd></div></dl> : <dl><div><dt>Aligned data period</dt><dd>{dataPeriod(summary?.date_start, summary?.date_end)}</dd></div><div><dt>Pairs analysed / shared observations</dt><dd>{summary ? `${summary.pair_count.toLocaleString()} / ${summary.observation_count.toLocaleString()}` : "—"}</dd></div><div><dt>Average / median overlap</dt><dd>{percent(activeMetricSummary?.mean)} / {percent(activeMetricSummary?.median)}</dd></div><div><dt>90th percentile</dt><dd>{percent(drawdownDiagnostics?.percentile_90)}</dd></div><div><dt>Pairs ≥ 10% / 25% / 50%</dt><dd>{drawdownDiagnostics ? `${drawdownDiagnostics.high_threshold_pairs.toLocaleString()} / ${drawdownDiagnostics.high_25_pairs.toLocaleString()} / ${drawdownDiagnostics.high_50_pairs.toLocaleString()}` : "—"}</dd></div><div><dt>Lowest overlap pair</dt><dd title={drawdownDiagnostics?.best_pair ?? undefined}>{drawdownDiagnostics?.best_pair ? `${drawdownDiagnostics.best_pair} (${percent(drawdownDiagnostics.best_value)})` : "—"}</dd></div><div><dt>Largest overlap pair</dt><dd title={drawdownDiagnostics?.worst_pair ?? undefined}>{drawdownDiagnostics?.worst_pair ? `${drawdownDiagnostics.worst_pair} (${percent(drawdownDiagnostics.worst_value)})` : "—"}</dd></div><div><dt>Most exposed ISIN</dt><dd title={drawdownDiagnostics?.most_exposed_listing ?? undefined}>{drawdownDiagnostics?.most_exposed_listing ? `${drawdownDiagnostics.most_exposed_listing} (${percent(drawdownDiagnostics.most_exposed_average)})` : "—"}</dd></div><div><dt>Shared drawdown days (median / min)</dt><dd>{drawdownDiagnostics ? `${drawdownDiagnostics.median_joint_drawdown_days ?? "—"} / ${drawdownDiagnostics.minimum_joint_drawdown_days ?? "—"}` : "—"}</dd></div><div><dt>Average shared drawdown severity</dt><dd>{percent(drawdownDiagnostics?.average_joint_drawdown_severity)}</dd></div><div><dt>Rolling overlap stability</dt><dd>{percent(drawdownDiagnostics?.average_rolling_stability)}</dd></div><div><dt>Average Pearson / downside correlation</dt><dd>{percent(drawdownDiagnostics?.average_pearson_correlation)} / {percent(drawdownDiagnostics?.average_downside_correlation)}</dd></div><div><dt>High overlap with low correlation</dt><dd>{drawdownDiagnostics ? `${drawdownDiagnostics.high_overlap_low_pearson_pairs.toLocaleString()} Pearson · ${drawdownDiagnostics.high_overlap_low_downside_pairs.toLocaleString()} downside` : "—"}</dd></div><div><dt>Drawdown clusters (≥ 10%)</dt><dd>{drawdownDiagnostics ? `${drawdownDiagnostics.cluster_count} clusters · largest ${drawdownDiagnostics.largest_cluster_size} ISINs` : "—"}</dd></div></dl>}
          </> : activePairwiseMetric === "lower_tail_dependence" || activePairwiseMetric === "tail_coexceedance_rate" ? <>
            <p>{activePairwiseMetric === "lower_tail_dependence" ? "Conditional likelihood that one ISIN is in its worst 5% daily-return tail when the paired ISIN is also in its worst 5% tail." : "Share of shared observations where both ISINs are simultaneously in their respective worst 5% daily-return tails."}</p>
            <p className="univariate-equation">{activePairwiseMetric === "lower_tail_dependence" ? "λᴸᵢⱼ = P(Rⱼ ≤ q₀.₀₅ⱼ | Rᵢ ≤ q₀.₀₅ᵢ)" : "Cᵢⱼ = (1 / T) Σ 𝟙(Rᵢ ≤ q₀.₀₅ᵢ, Rⱼ ≤ q₀.₀₅ⱼ)"}</p>
            <p className="univariate-notation">{activePairwiseMetric === "lower_tail_dependence" ? "R: daily log return · q₀.₀₅: 5th-percentile return · λᴸ: lower-tail dependence" : "R: daily log return · q₀.₀₅: 5th-percentile return · T: shared observations · 𝟙: indicator"}</p>
            <dl>
              <div><dt>Aligned data period</dt><dd>{dataPeriod(summary?.date_start, summary?.date_end)}</dd></div>
              <div><dt>Pairs analysed</dt><dd>{summary?.pair_count.toLocaleString() ?? "—"}</dd></div>
              <div><dt>Shared observations</dt><dd>{summary?.observation_count.toLocaleString() ?? "—"}</dd></div>
              <div><dt>Average {activeMetricLabel}</dt><dd>{percent(activeMetricSummary?.mean)}</dd></div>
              <div><dt>Median {activeMetricLabel}</dt><dd>{percent(activeMetricSummary?.median)}</dd></div>
              <div><dt>Minimum {activeMetricLabel}</dt><dd>{percent(activeMetricSummary?.minimum)}</dd></div>
              <div><dt>Maximum {activeMetricLabel}</dt><dd>{percent(activeMetricSummary?.maximum)}</dd></div>
              {activePairwiseMetric === "lower_tail_dependence" && <>
                <div><dt>90th percentile</dt><dd>{percent(tailDiagnostics?.percentile_90)}</dd></div>
                <div><dt>Pairs λᴸ ≥ 30%</dt><dd>{summary ? `${tailDiagnostics?.high_30_pairs.toLocaleString() ?? "—"} (${((tailDiagnostics?.high_30_pairs ?? 0) / Math.max(1, summary.pair_count) * 100).toFixed(1)}%)` : "—"}</dd></div>
                <div><dt>Pairs λᴸ ≥ 50%</dt><dd>{summary ? `${tailDiagnostics?.high_50_pairs.toLocaleString() ?? "—"} (${((tailDiagnostics?.high_50_pairs ?? 0) / Math.max(1, summary.pair_count) * 100).toFixed(1)}%)` : "—"}</dd></div>
                <div><dt>Worst tail-risk pair</dt><dd title={tailDiagnostics?.worst_pair ?? undefined}>{tailDiagnostics?.worst_pair ? `${tailDiagnostics.worst_pair} (${percent(tailDiagnostics.worst_pair_tail_dependence)})` : "—"}</dd></div>
                <div><dt>Best tail diversifier</dt><dd title={tailDiagnostics?.best_diversifier_pair ?? undefined}>{tailDiagnostics?.best_diversifier_pair ? `${tailDiagnostics.best_diversifier_pair} (λᴸ ${percent(tailDiagnostics.best_diversifier_tail_dependence)} · co-exceedance ${percent(tailDiagnostics.best_diversifier_coexceedance_rate)})` : "—"}</dd></div>
                <div><dt>Most tail-exposed ISIN</dt><dd title={tailDiagnostics?.most_tail_exposed_listing ?? undefined}>{tailDiagnostics?.most_tail_exposed_listing ? `${tailDiagnostics.most_tail_exposed_listing} (${percent(tailDiagnostics.most_tail_exposed_average)})` : "—"}</dd></div>
                <div><dt>Average joint-tail loss</dt><dd>{percent(tailDiagnostics?.average_joint_loss_severity)}</dd></div>
                <div><dt>Joint tail events (median / min)</dt><dd>{tailDiagnostics ? `${tailDiagnostics.median_joint_tail_events ?? "—"} / ${tailDiagnostics.minimum_joint_tail_events ?? "—"}` : "—"}</dd></div>
                <div><dt>Rolling tail stability</dt><dd>{percent(tailDiagnostics?.average_rolling_stability)}</dd></div>
                <div><dt>Tail clusters (λᴸ ≥ 30%)</dt><dd>{tailDiagnostics ? `${tailDiagnostics.cluster_count ?? 0} clusters · largest ${tailDiagnostics.largest_cluster_size ?? 0} ISINs` : "—"}</dd></div>
              </>}
              {activePairwiseMetric === "tail_coexceedance_rate" && <>
                <div><dt>90th percentile</dt><dd>{percent(coexceedanceDiagnostics?.percentile_90)}</dd></div>
                <div><dt>Independence baseline</dt><dd>{percent(coexceedanceDiagnostics?.independence_baseline)} (two 5% tails)</dd></div>
                <div><dt>Average vs. independence</dt><dd>{coexceedanceDiagnostics?.average_independence_multiple == null ? "—" : `${coexceedanceDiagnostics.average_independence_multiple.toFixed(1)}×`}</dd></div>
                <div><dt>Pairs ≥ 1% / 2.5% / 5%</dt><dd>{summary ? `${coexceedanceDiagnostics?.high_1_pairs.toLocaleString() ?? "—"} / ${coexceedanceDiagnostics?.high_25_pairs.toLocaleString() ?? "—"} / ${coexceedanceDiagnostics?.high_5_pairs.toLocaleString() ?? "—"}` : "—"}</dd></div>
                <div><dt>Worst co-exceedance pair</dt><dd title={coexceedanceDiagnostics?.worst_pair ?? undefined}>{coexceedanceDiagnostics?.worst_pair ? `${coexceedanceDiagnostics.worst_pair} (${percent(coexceedanceDiagnostics.worst_pair_rate)})` : "—"}</dd></div>
                <div><dt>Expected joint-tail days / year</dt><dd>{coexceedanceDiagnostics?.worst_pair_annual_events == null ? "—" : coexceedanceDiagnostics.worst_pair_annual_events.toFixed(1)}</dd></div>
                <div><dt>Worst-pair tail dependence</dt><dd>{percent(coexceedanceDiagnostics?.worst_pair_tail_dependence)}</dd></div>
                <div><dt>Best joint-tail diversifier</dt><dd title={coexceedanceDiagnostics?.best_diversifier_pair ?? undefined}>{coexceedanceDiagnostics?.best_diversifier_pair ? `${coexceedanceDiagnostics.best_diversifier_pair} (${percent(coexceedanceDiagnostics.best_diversifier_rate)} · λᴸ ${percent(coexceedanceDiagnostics.best_diversifier_tail_dependence)})` : "—"}</dd></div>
                <div><dt>Most co-exposed ISIN</dt><dd title={coexceedanceDiagnostics?.most_coexposed_listing ?? undefined}>{coexceedanceDiagnostics?.most_coexposed_listing ? `${coexceedanceDiagnostics.most_coexposed_listing} (${percent(coexceedanceDiagnostics.most_coexposed_average)})` : "—"}</dd></div>
                <div><dt>Joint tail events (median / min)</dt><dd>{coexceedanceDiagnostics ? `${coexceedanceDiagnostics.median_joint_tail_events ?? "—"} / ${coexceedanceDiagnostics.minimum_joint_tail_events ?? "—"}` : "—"}</dd></div>
                <div><dt>Rolling co-exceedance stability</dt><dd>{percent(coexceedanceDiagnostics?.average_rolling_stability)}</dd></div>
                <div><dt>Co-exceedance clusters (≥ 1%)</dt><dd>{coexceedanceDiagnostics ? `${coexceedanceDiagnostics.cluster_count ?? 0} clusters · largest ${coexceedanceDiagnostics.largest_cluster_size ?? 0} ISINs` : "—"}</dd></div>
              </>}
            </dl>
          </> : <>
          {activePairwiseMetric === "covariance" ? <><p>Joint variation of return series for every pair in the filtered ISIN universe.</p><p className="univariate-equation">Cov(Rᵢ, Rⱼ) = 𝔼[(Rᵢ − μᵢ)(Rⱼ − μⱼ)]</p><p className="univariate-notation">Rᵢ, Rⱼ: paired returns · μ: mean return · 𝔼: expected value</p><dl><div><dt>Aligned data period</dt><dd>{dataPeriod(covarianceMatrix?.date_start, covarianceMatrix?.date_end)}</dd></div><div><dt>ISINs analysed</dt><dd>{diagnostics?.listing_count.toLocaleString() ?? "—"}</dd></div><div><dt>Unique pairs</dt><dd>{diagnostics?.pair_count.toLocaleString() ?? "—"}</dd></div><div><dt>Shared observations</dt><dd>{diagnostics?.observation_count.toLocaleString() ?? "—"}</dd></div><div><dt>Average covariance</dt><dd>{metric(diagnostics?.average_pairwise_covariance)}</dd></div><div><dt>Average correlation</dt><dd>{metric(diagnostics?.average_pairwise_correlation)}</dd></div><div><dt>Equal-weight volatility</dt><dd>{metric(diagnostics?.equal_weight_volatility)}</dd></div><div><dt>Minimum-variance volatility</dt><dd>{metric(diagnostics?.minimum_variance_volatility)}</dd></div><div><dt>Diversification ratio</dt><dd>{metric(diagnostics?.diversification_ratio)}</dd></div><div><dt>Effective number of bets</dt><dd>{metric(diagnostics?.effective_number_of_bets)}</dd></div><div><dt>Largest risk contribution</dt><dd>{diagnostics?.largest_equal_weight_risk_contribution == null ? "—" : `${(diagnostics.largest_equal_weight_risk_contribution * 100).toFixed(1)}%`}</dd></div></dl></> : <><p>{activePairwiseMetric === "pearson" ? "Linear co-movement of daily log returns for every filtered ISIN pair." : activePairwiseMetric === "spearman" ? "Rank-based co-movement of daily log returns for every filtered ISIN pair." : "Co-movement on days when both ISINs have negative daily log returns."}</p><p className="univariate-equation">{activePairwiseMetric === "pearson" ? "ρᵢⱼ = Cov(Rᵢ, Rⱼ) / (σᵢσⱼ)" : activePairwiseMetric === "spearman" ? "ρˢᵢⱼ = Corr(rank(Rᵢ), rank(Rⱼ))" : "ρ⁻ᵢⱼ = Corr(Rᵢ, Rⱼ | Rᵢ < 0, Rⱼ < 0)"}</p><p className="univariate-notation">{activePairwiseMetric === "pearson" ? "R: daily log return · σ: return standard deviation · ρ: Pearson correlation" : activePairwiseMetric === "spearman" ? "R: daily log return · rank: ordinal return rank · ρˢ: Spearman correlation" : "R: daily log return · ρ⁻: conditional downside correlation"}</p><dl><div><dt>Aligned data period</dt><dd>{dataPeriod(summary?.date_start, summary?.date_end)}</dd></div><div><dt>Pairs analysed</dt><dd>{summary?.pair_count.toLocaleString() ?? "—"}</dd></div><div><dt>Shared observations</dt><dd>{summary?.observation_count.toLocaleString() ?? "—"}</dd></div><div><dt>Average correlation</dt><dd>{percent(activeCorrelation?.mean)}</dd></div><div><dt>Median correlation</dt><dd>{percent(activeCorrelation?.median)}</dd></div><div><dt>Minimum correlation</dt><dd>{percent(activeCorrelation?.minimum)}</dd></div><div><dt>Maximum correlation</dt><dd>{percent(activeCorrelation?.maximum)}</dd></div>{activePairwiseMetric === "pearson" && <><div><dt>Pairs ≥ 0.70</dt><dd>{summary ? `${summary.pearson_diagnostics.high_70_pairs.toLocaleString()} (${(summary.pearson_diagnostics.high_70_pairs / Math.max(1, summary.pair_count) * 100).toFixed(1)}%)` : "—"}</dd></div><div><dt>Pairs ≥ 0.90</dt><dd>{summary ? `${summary.pearson_diagnostics.high_90_pairs.toLocaleString()} (${(summary.pearson_diagnostics.high_90_pairs / Math.max(1, summary.pair_count) * 100).toFixed(1)}%)` : "—"}</dd></div><div><dt>Pairs ≤ 0.30</dt><dd>{summary ? `${summary.pearson_diagnostics.low_30_pairs.toLocaleString()} (${(summary.pearson_diagnostics.low_30_pairs / Math.max(1, summary.pair_count) * 100).toFixed(1)}%)` : "—"}</dd></div><div><dt>Negative pairs</dt><dd>{summary ? `${summary.pearson_diagnostics.negative_pairs.toLocaleString()} (${(summary.pearson_diagnostics.negative_pairs / Math.max(1, summary.pair_count) * 100).toFixed(1)}%)` : "—"}</dd></div><div><dt>10th / 90th percentile</dt><dd>{summary ? `${percent(summary.pearson_diagnostics.percentile_10)} / ${percent(summary.pearson_diagnostics.percentile_90)}` : "—"}</dd></div><div><dt>Most correlated ISIN</dt><dd title={summary?.pearson_diagnostics.most_correlated_listing ?? undefined}>{summary?.pearson_diagnostics.most_correlated_listing ? `${summary.pearson_diagnostics.most_correlated_listing} (${percent(summary.pearson_diagnostics.most_correlated_average)})` : "—"}</dd></div><div><dt>Best diversifier</dt><dd title={summary?.pearson_diagnostics.best_diversifier_listing ?? undefined}>{summary?.pearson_diagnostics.best_diversifier_listing ? `${summary.pearson_diagnostics.best_diversifier_listing} (${percent(summary.pearson_diagnostics.best_diversifier_average)})` : "—"}</dd></div></>}{activePairwiseMetric === "spearman" && <><div><dt>Pairs ≥ 0.70</dt><dd>{summary ? `${summary.spearman_diagnostics.high_70_pairs.toLocaleString()} (${(summary.spearman_diagnostics.high_70_pairs / Math.max(1, summary.pair_count) * 100).toFixed(1)}%)` : "—"}</dd></div><div><dt>Pairs ≥ 0.90</dt><dd>{summary ? `${summary.spearman_diagnostics.high_90_pairs.toLocaleString()} (${(summary.spearman_diagnostics.high_90_pairs / Math.max(1, summary.pair_count) * 100).toFixed(1)}%)` : "—"}</dd></div><div><dt>Pairs ≤ 0.30 / negative</dt><dd>{summary ? `${summary.spearman_diagnostics.low_30_pairs.toLocaleString()} / ${summary.spearman_diagnostics.negative_pairs.toLocaleString()}` : "—"}</dd></div><div><dt>10th / 90th percentile</dt><dd>{summary ? `${percent(summary.spearman_diagnostics.percentile_10)} / ${percent(summary.spearman_diagnostics.percentile_90)}` : "—"}</dd></div><div><dt>Average Pearson gap</dt><dd>{percent(summary?.spearman_diagnostics.average_pearson_gap)}</dd></div><div><dt>Large Pearson gaps (≥ 15 pp)</dt><dd>{summary?.spearman_diagnostics.large_pearson_gap_pairs?.toLocaleString() ?? "—"}</dd></div><div><dt>Most rank-linked ISIN</dt><dd title={summary?.spearman_diagnostics.most_correlated_listing ?? undefined}>{summary?.spearman_diagnostics.most_correlated_listing ? `${summary.spearman_diagnostics.most_correlated_listing} (${percent(summary.spearman_diagnostics.most_correlated_average)})` : "—"}</dd></div><div><dt>Best rank diversifier</dt><dd title={summary?.spearman_diagnostics.best_diversifier_listing ?? undefined}>{summary?.spearman_diagnostics.best_diversifier_listing ? `${summary.spearman_diagnostics.best_diversifier_listing} (${percent(summary.spearman_diagnostics.best_diversifier_average)})` : "—"}</dd></div><div><dt>Rolling rank stability</dt><dd>{percent(summary?.spearman_diagnostics.average_rolling_stability)}</dd></div><div><dt>Rank-correlation clusters</dt><dd>{summary ? `${summary.spearman_diagnostics.cluster_count ?? 0} clusters · largest ${summary.spearman_diagnostics.largest_cluster_size ?? 0} ISINs` : "—"}</dd></div></>}{activePairwiseMetric === "downside" && <><div><dt>Pairs ≥ 0.70 / ≥ 0.90</dt><dd>{summary ? `${summary.downside_diagnostics.high_70_pairs.toLocaleString()} / ${summary.downside_diagnostics.high_90_pairs.toLocaleString()}` : "—"}</dd></div><div><dt>Pairs ≤ 0.30 / negative</dt><dd>{summary ? `${summary.downside_diagnostics.low_30_pairs.toLocaleString()} / ${summary.downside_diagnostics.negative_pairs.toLocaleString()}` : "—"}</dd></div><div><dt>10th / 90th percentile</dt><dd>{summary ? `${percent(summary.downside_diagnostics.percentile_10)} / ${percent(summary.downside_diagnostics.percentile_90)}` : "—"}</dd></div><div><dt>Worst joint-loss pair</dt><dd title={summary?.downside_diagnostics.worst_pair ?? undefined}>{summary?.downside_diagnostics.worst_pair ? `${summary.downside_diagnostics.worst_pair} (${percent(summary.downside_diagnostics.worst_pair_correlation)})` : "—"}</dd></div><div><dt>Best downside diversifier</dt><dd title={summary?.downside_diagnostics.best_diversifier_listing ?? undefined}>{summary?.downside_diagnostics.best_diversifier_listing ? `${summary.downside_diagnostics.best_diversifier_listing} (${percent(summary.downside_diagnostics.best_diversifier_average)})` : "—"}</dd></div><div><dt>Average Pearson gap</dt><dd>{percent(summary?.downside_diagnostics.average_pearson_gap)}</dd></div><div><dt>Large Pearson gaps (≥ 15 pp)</dt><dd>{summary?.downside_diagnostics.large_pearson_gap_pairs?.toLocaleString() ?? "—"}</dd></div><div><dt>Joint-negative days (median / min)</dt><dd>{summary ? `${summary.downside_diagnostics.median_joint_negative_days ?? "—"} / ${summary.downside_diagnostics.minimum_joint_negative_days ?? "—"}` : "—"}</dd></div><div><dt>Rolling downside stability</dt><dd>{percent(summary?.downside_diagnostics.average_rolling_stability)}</dd></div><div><dt>Downside clusters</dt><dd>{summary ? `${summary.downside_diagnostics.cluster_count ?? 0} clusters · largest ${summary.downside_diagnostics.largest_cluster_size ?? 0} ISINs` : "—"}</dd></div></>}</dl></>}
          </>}
        </div>
        {activePairwiseMetric === "tail_risk_scatter" ? <TailRiskScatter scatter={tailRiskScatter} /> : <PairMatrix matrix={activeMatrix} title={activeMatrixTitle} hoveredCell={hoveredMatrixCell} setHoveredCell={setHoveredMatrixCell} />}
      </section>
    </Panel>
  );
}
