
import { useEffect, useState } from "react";
import { loadWorkflow, postJson, requestJson } from "../api/client";
import { Button } from "../components/button";
import { LoadingState } from "../components/loading-state";
import { Panel } from "../components/panel";
import type { ApiBivariateMetricSummary, ApiBivariateRow, ApiBivariateSummary, ApiCovarianceMatrix, ApiPage, ApiPairMetricMatrix, ApiPairPlan, ApiResearchRun } from "../contracts";
import { useResource } from "../hooks/use-resource";

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

function BivariateMetricWindow({
  title, description, equation, notation, primary, secondary, primaryLabel, secondaryLabel,
}: {
  title: string; description: string; equation: string; notation: string;
  primary: ApiBivariateMetricSummary | undefined; secondary?: ApiBivariateMetricSummary | undefined;
  primaryLabel: string; secondaryLabel?: string;
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
      <p className="bivariate-statistic__matrix-caption">Daily log-return {title.toLowerCase()} matrix · {matrix.observation_count.toLocaleString()} shared observations</p>
      <table className="covariance-matrix" onMouseLeave={() => setHoveredCell(null)}>
        <thead><tr><th scope="col">ISIN</th>{matrix.labels.map((label, index) => <th scope="col" key={label.isin} className={highlightedColumn(index) ? "is-hovered-column" : undefined} title={`${label.label} · ${label.isin}`} onMouseEnter={() => setHoveredCell({ row: index, column: index })}>{label.label}</th>)}</tr></thead>
        <tbody>{matrix.labels.map((label, rowIndex) => <tr key={label.isin}><th scope="row" className={highlightedRow(rowIndex) ? "is-hovered-row" : undefined} title={`${label.label} · ${label.isin}`} onMouseEnter={() => setHoveredCell({ row: rowIndex, column: rowIndex })}>{label.label}</th>{matrix.values[rowIndex].map((value, columnIndex) => { const column = matrix.labels[columnIndex]; return <td key={`${label.isin}:${column.isin}`} className={`${value === null ? "covariance-matrix__empty" : ""} ${highlightedRow(rowIndex) ? "is-hovered-row" : ""} ${highlightedColumn(columnIndex) ? "is-hovered-column" : ""}`.trim() || undefined} title={value === null ? `Row: ${label.label} (${label.isin})\nColumn: ${column.label} (${column.isin})\nDuplicate or self relation omitted` : `Row: ${label.label} (${label.isin})\nColumn: ${column.label} (${column.isin})\n${title}: ${metric(value)}`} style={value === null ? undefined : { backgroundColor: covarianceColor(value, extent) }} onMouseEnter={() => setHoveredCell({ row: rowIndex, column: columnIndex })}>{metric(value)}</td>})}</tr>)}</tbody>
      </table>
      <p className="covariance-matrix__legend"><span className="covariance-matrix__legend-negative" /> Negative <span className="covariance-matrix__legend-neutral" /> Near zero <span className="covariance-matrix__legend-positive" /> Positive</p>
    </> : <p className="status-line">No common log-return observations are available.</p>}
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
  const [summary, setSummary] = useState<ApiBivariateSummary | null>(null);
  const [hoveredMatrixCell, setHoveredMatrixCell] = useState<{ row: number; column: number } | null>(null);
  const [activePairwiseMetric, setActivePairwiseMetric] = useState<"covariance" | "pearson" | "spearman" | "downside">("covariance");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const resetProjectState = () => {
      setRun(null);
      setResults(null);
      setCovarianceMatrix(null);
      setPearsonMatrix(null);
      setSpearmanMatrix(null);
      setDownsideMatrix(null);
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
        const current = await requestJson<ApiResearchRun>(`/api/bivariate-statistics/runs/${activeRunId}`);
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
        const [page, matrix, nextSummary, nextPearsonMatrix, nextSpearmanMatrix, nextDownsideMatrix] = await Promise.all([
          requestJson<ApiPage<ApiBivariateRow>>(`/api/bivariate-statistics/runs/${current.run_id}/results?limit=50&offset=0`),
          requestJson<ApiCovarianceMatrix>(`/api/bivariate-statistics/runs/${current.run_id}/covariance-matrix`),
          requestJson<ApiBivariateSummary>(`/api/bivariate-statistics/runs/${current.run_id}/summary`),
          requestJson<ApiPairMetricMatrix>(`/api/bivariate-statistics/runs/${current.run_id}/correlation-matrix?metric=pearson`),
          requestJson<ApiPairMetricMatrix>(`/api/bivariate-statistics/runs/${current.run_id}/correlation-matrix?metric=spearman`),
          requestJson<ApiPairMetricMatrix>(`/api/bivariate-statistics/runs/${current.run_id}/correlation-matrix?metric=downside`),
        ]);
        if (cancelled) return;
        setResults(page);
        setCovarianceMatrix(matrix);
        setSummary(nextSummary);
        setPearsonMatrix(nextPearsonMatrix);
        setSpearmanMatrix(nextSpearmanMatrix);
        setDownsideMatrix(nextDownsideMatrix);
        setMessage(`${page.total.toLocaleString()} pair statistics computed.`);
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

  if (workflow.status === "loading" || workflow.status === "idle") return <LoadingState label="Loading bivariate statistics" />;
  if (workflow.status === "error") return <p>Workflow state is unavailable.</p>;
  const selectionId = workflow.data.stages.univariate_filter.univariate_filter_selection_id;
  if (!selectionId) {
    return <Panel title="Bivariate Statistics"><p>Complete univariate statistics and select at least two ISINs first.</p></Panel>;
  }

  async function compute() {
    setMessage("Planning bivariate statistics…");
    try {
      const nextPlan = await postJson<ApiPairPlan>("/api/bivariate-statistics/plan", { univariate_filter_selection_id: selectionId });
      if (!nextPlan.allowed) {
        setMessage(`Pair count exceeds the ${nextPlan.pair_limit} limit or has fewer than two selected ISINs.`);
        return;
      }
      setMessage("Computing bivariate statistics…");
      const nextRun = await postJson<ApiResearchRun>("/api/bivariate-statistics/runs", { univariate_filter_selection_id: selectionId });
      setRun(nextRun);
      if (nextRun.status === "complete") {
        const [page, matrix, nextSummary, nextPearsonMatrix, nextSpearmanMatrix, nextDownsideMatrix] = await Promise.all([
          requestJson<ApiPage<ApiBivariateRow>>(`/api/bivariate-statistics/runs/${nextRun.run_id}/results?limit=50&offset=0`),
          requestJson<ApiCovarianceMatrix>(`/api/bivariate-statistics/runs/${nextRun.run_id}/covariance-matrix`),
          requestJson<ApiBivariateSummary>(`/api/bivariate-statistics/runs/${nextRun.run_id}/summary`),
          requestJson<ApiPairMetricMatrix>(`/api/bivariate-statistics/runs/${nextRun.run_id}/correlation-matrix?metric=pearson`),
          requestJson<ApiPairMetricMatrix>(`/api/bivariate-statistics/runs/${nextRun.run_id}/correlation-matrix?metric=spearman`),
          requestJson<ApiPairMetricMatrix>(`/api/bivariate-statistics/runs/${nextRun.run_id}/correlation-matrix?metric=downside`),
        ]);
        setResults(page);
        setCovarianceMatrix(matrix);
        setSummary(nextSummary);
        setPearsonMatrix(nextPearsonMatrix);
        setSpearmanMatrix(nextSpearmanMatrix);
        setDownsideMatrix(nextDownsideMatrix);
        setMessage(`${page.total.toLocaleString()} pair statistics computed.`);
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Bivariate computation failed.");
    }
  }

  const diagnostics = covarianceMatrix?.diagnostics;
  const activeCorrelation = activePairwiseMetric === "pearson"
    ? summary?.metrics.pearson_correlation
    : activePairwiseMetric === "spearman"
      ? summary?.metrics.spearman_correlation
      : summary?.metrics.downside_correlation;
  const activeMatrix = activePairwiseMetric === "covariance"
    ? covarianceMatrix
    : activePairwiseMetric === "pearson"
      ? pearsonMatrix
      : activePairwiseMetric === "spearman"
        ? spearmanMatrix
        : downsideMatrix;
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
          {(["covariance", "pearson", "spearman", "downside"] as const).map((metricName) => <button key={metricName} type="button" role="tab" aria-selected={activePairwiseMetric === metricName} className={activePairwiseMetric === metricName ? "is-active" : undefined} onClick={() => setActivePairwiseMetric(metricName)}>{metricName === "covariance" ? "Covariance" : metricName === "pearson" ? "Pearson" : metricName === "spearman" ? "Spearman" : "Downside"}</button>)}
        </div>
        <div className="bivariate-statistic__facts">
          <h3 id="pairwise-dependence-title">{activePairwiseMetric === "covariance" ? "Covariance" : activePairwiseMetric === "pearson" ? "Pearson Correlation" : activePairwiseMetric === "spearman" ? "Spearman Correlation" : "Downside Correlation"}</h3>
          {activePairwiseMetric === "covariance" ? <><p>Joint variation of return series for every pair in the filtered ISIN universe.</p><p className="univariate-equation">Cov(Rᵢ, Rⱼ) = 𝔼[(Rᵢ − μᵢ)(Rⱼ − μⱼ)]</p><p className="univariate-notation">Rᵢ, Rⱼ: paired returns · μ: mean return · 𝔼: expected value</p><dl><div><dt>ISINs analysed</dt><dd>{diagnostics?.listing_count.toLocaleString() ?? "—"}</dd></div><div><dt>Unique pairs</dt><dd>{diagnostics?.pair_count.toLocaleString() ?? "—"}</dd></div><div><dt>Shared observations</dt><dd>{diagnostics?.observation_count.toLocaleString() ?? "—"}</dd></div><div><dt>Average covariance</dt><dd>{metric(diagnostics?.average_pairwise_covariance)}</dd></div><div><dt>Average correlation</dt><dd>{metric(diagnostics?.average_pairwise_correlation)}</dd></div><div><dt>Equal-weight volatility</dt><dd>{metric(diagnostics?.equal_weight_volatility)}</dd></div><div><dt>Minimum-variance volatility</dt><dd>{metric(diagnostics?.minimum_variance_volatility)}</dd></div><div><dt>Diversification ratio</dt><dd>{metric(diagnostics?.diversification_ratio)}</dd></div><div><dt>Effective number of bets</dt><dd>{metric(diagnostics?.effective_number_of_bets)}</dd></div><div><dt>Largest risk contribution</dt><dd>{diagnostics?.largest_equal_weight_risk_contribution == null ? "—" : `${(diagnostics.largest_equal_weight_risk_contribution * 100).toFixed(1)}%`}</dd></div></dl></> : <><p>{activePairwiseMetric === "pearson" ? "Linear co-movement of daily log returns for every filtered ISIN pair." : activePairwiseMetric === "spearman" ? "Rank-based co-movement of daily log returns for every filtered ISIN pair." : "Co-movement on days when both ISINs have negative daily log returns."}</p><p className="univariate-equation">{activePairwiseMetric === "pearson" ? "ρᵢⱼ = Cov(Rᵢ, Rⱼ) / (σᵢσⱼ)" : activePairwiseMetric === "spearman" ? "ρˢᵢⱼ = Corr(rank(Rᵢ), rank(Rⱼ))" : "ρ⁻ᵢⱼ = Corr(Rᵢ, Rⱼ | Rᵢ < 0, Rⱼ < 0)"}</p><p className="univariate-notation">{activePairwiseMetric === "pearson" ? "R: daily log return · σ: return standard deviation · ρ: Pearson correlation" : activePairwiseMetric === "spearman" ? "R: daily log return · rank: ordinal return rank · ρˢ: Spearman correlation" : "R: daily log return · ρ⁻: conditional downside correlation"}</p><dl><div><dt>Pairs analysed</dt><dd>{summary?.pair_count.toLocaleString() ?? "—"}</dd></div><div><dt>Shared observations</dt><dd>{summary?.observation_count.toLocaleString() ?? "—"}</dd></div><div><dt>Average correlation</dt><dd>{percent(activeCorrelation?.mean)}</dd></div><div><dt>Median correlation</dt><dd>{percent(activeCorrelation?.median)}</dd></div><div><dt>Minimum correlation</dt><dd>{percent(activeCorrelation?.minimum)}</dd></div><div><dt>Maximum correlation</dt><dd>{percent(activeCorrelation?.maximum)}</dd></div>{activePairwiseMetric === "pearson" && <><div><dt>Pairs ≥ 0.70</dt><dd>{summary ? `${summary.pearson_diagnostics.high_70_pairs.toLocaleString()} (${(summary.pearson_diagnostics.high_70_pairs / Math.max(1, summary.pair_count) * 100).toFixed(1)}%)` : "—"}</dd></div><div><dt>Pairs ≥ 0.90</dt><dd>{summary ? `${summary.pearson_diagnostics.high_90_pairs.toLocaleString()} (${(summary.pearson_diagnostics.high_90_pairs / Math.max(1, summary.pair_count) * 100).toFixed(1)}%)` : "—"}</dd></div><div><dt>Pairs ≤ 0.30</dt><dd>{summary ? `${summary.pearson_diagnostics.low_30_pairs.toLocaleString()} (${(summary.pearson_diagnostics.low_30_pairs / Math.max(1, summary.pair_count) * 100).toFixed(1)}%)` : "—"}</dd></div><div><dt>Negative pairs</dt><dd>{summary ? `${summary.pearson_diagnostics.negative_pairs.toLocaleString()} (${(summary.pearson_diagnostics.negative_pairs / Math.max(1, summary.pair_count) * 100).toFixed(1)}%)` : "—"}</dd></div><div><dt>10th / 90th percentile</dt><dd>{summary ? `${percent(summary.pearson_diagnostics.percentile_10)} / ${percent(summary.pearson_diagnostics.percentile_90)}` : "—"}</dd></div><div><dt>Most correlated ISIN</dt><dd title={summary?.pearson_diagnostics.most_correlated_listing ?? undefined}>{summary?.pearson_diagnostics.most_correlated_listing ? `${summary.pearson_diagnostics.most_correlated_listing} (${percent(summary.pearson_diagnostics.most_correlated_average)})` : "—"}</dd></div><div><dt>Best diversifier</dt><dd title={summary?.pearson_diagnostics.best_diversifier_listing ?? undefined}>{summary?.pearson_diagnostics.best_diversifier_listing ? `${summary.pearson_diagnostics.best_diversifier_listing} (${percent(summary.pearson_diagnostics.best_diversifier_average)})` : "—"}</dd></div></>}{activePairwiseMetric === "spearman" && <><div><dt>Pairs ≥ 0.70</dt><dd>{summary ? `${summary.spearman_diagnostics.high_70_pairs.toLocaleString()} (${(summary.spearman_diagnostics.high_70_pairs / Math.max(1, summary.pair_count) * 100).toFixed(1)}%)` : "—"}</dd></div><div><dt>Pairs ≥ 0.90</dt><dd>{summary ? `${summary.spearman_diagnostics.high_90_pairs.toLocaleString()} (${(summary.spearman_diagnostics.high_90_pairs / Math.max(1, summary.pair_count) * 100).toFixed(1)}%)` : "—"}</dd></div><div><dt>Pairs ≤ 0.30 / negative</dt><dd>{summary ? `${summary.spearman_diagnostics.low_30_pairs.toLocaleString()} / ${summary.spearman_diagnostics.negative_pairs.toLocaleString()}` : "—"}</dd></div><div><dt>10th / 90th percentile</dt><dd>{summary ? `${percent(summary.spearman_diagnostics.percentile_10)} / ${percent(summary.spearman_diagnostics.percentile_90)}` : "—"}</dd></div><div><dt>Average Pearson gap</dt><dd>{percent(summary?.spearman_diagnostics.average_pearson_gap)}</dd></div><div><dt>Large Pearson gaps (≥ 15 pp)</dt><dd>{summary?.spearman_diagnostics.large_pearson_gap_pairs?.toLocaleString() ?? "—"}</dd></div><div><dt>Most rank-linked ISIN</dt><dd title={summary?.spearman_diagnostics.most_correlated_listing ?? undefined}>{summary?.spearman_diagnostics.most_correlated_listing ? `${summary.spearman_diagnostics.most_correlated_listing} (${percent(summary.spearman_diagnostics.most_correlated_average)})` : "—"}</dd></div><div><dt>Best rank diversifier</dt><dd title={summary?.spearman_diagnostics.best_diversifier_listing ?? undefined}>{summary?.spearman_diagnostics.best_diversifier_listing ? `${summary.spearman_diagnostics.best_diversifier_listing} (${percent(summary.spearman_diagnostics.best_diversifier_average)})` : "—"}</dd></div><div><dt>Rolling rank stability</dt><dd>{percent(summary?.spearman_diagnostics.average_rolling_stability)}</dd></div><div><dt>Rank-correlation clusters</dt><dd>{summary ? `${summary.spearman_diagnostics.cluster_count ?? 0} clusters · largest ${summary.spearman_diagnostics.largest_cluster_size ?? 0} ISINs` : "—"}</dd></div></>}</dl></>}
        </div>
        <PairMatrix matrix={activeMatrix} title={activePairwiseMetric === "covariance" ? "Covariance" : `${activePairwiseMetric[0].toUpperCase()}${activePairwiseMetric.slice(1)} correlation`} hoveredCell={hoveredMatrixCell} setHoveredCell={setHoveredMatrixCell} />
      </section>
      <BivariateMetricWindow
        title="Tail Dependence and Co-exceedance Rate"
        description="Joint lower-tail behaviour: simultaneous returns in each ISIN's worst 5% of observations."
        equation="λᴸᵢⱼ = P(Rⱼ ≤ q₀.₀₅ⱼ | Rᵢ ≤ q₀.₀₅ᵢ)"
        notation="q₀.₀₅: 5th-percentile return · λᴸ: lower-tail dependence"
        primary={summary?.metrics.lower_tail_dependence} secondary={summary?.metrics.tail_coexceedance_rate}
        primaryLabel="tail dependence" secondaryLabel="co-exceedance rate"
      />
      <BivariateMetricWindow
        title="Rolling-correlation Stability"
        description="Variation in sampled 60-observation rolling Pearson correlations; lower values are more stable."
        equation="sᵨ = √(Σ(ρₜ − ρ̄)² / (n − 1))"
        notation="ρₜ: rolling correlation · ρ̄: mean rolling correlation · sᵨ: its standard deviation"
        primary={summary?.metrics.rolling_correlation_stability} primaryLabel="rolling correlation standard deviation"
      />
      <BivariateMetricWindow
        title="Drawdown Overlap"
        description="Share of observations where both ISINs are at least 5% below their preceding cumulative-return peak."
        equation="Oᵢⱼ = (1/T) Σ 𝟙(DDᵢ ≤ −5%, DDⱼ ≤ −5%)"
        notation="DD: drawdown · T: shared observations · 𝟙: indicator function"
        primary={summary?.metrics.drawdown_overlap_rate} primaryLabel="drawdown overlap rate"
      />
    </Panel>
  );
}
