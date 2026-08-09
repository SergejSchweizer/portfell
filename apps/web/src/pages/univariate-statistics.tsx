
import { useEffect, useState } from "react";
import { loadProjectContext, loadQuoteRun, loadWorkflow } from "../api/client";
import { univariateStatisticsApi } from "../api/univariate-statistics";
import { Button } from "../components/button";
import { LoadingState } from "../components/loading-state";
import { Panel } from "../components/panel";
import type { ApiDividendFrequency, ApiQuoteFetch, ApiResearchRun, ApiUnivariateRow, ApiUnivariateSelectionSettings } from "../contracts";
import { useResource } from "../hooks/use-resource";
import { historicalDataUpdateLabel } from "../quote-progress";

type MetricDefinition = Readonly<{ group: string; metric: string; label: string; description: string; equation: string; notation: string; unit?: string }>;
type UnivariateStatisticTab = "dividends" | MetricDefinition["metric"];
type DividendFrequency = ApiDividendFrequency;
type SelectionRange = Readonly<{ minimum: number; maximum: number }>;
type UnivariateSelectionSettings = ApiUnivariateSelectionSettings;

const dividendFrequencyOptions: readonly Readonly<{ value: DividendFrequency; label: string }>[] = [
  { value: "accumulating", label: "None / unknown" },
  { value: "monthly", label: "Monthly" },
  { value: "quarterly", label: "Quarterly" },
  { value: "semiannual", label: "Semi-annual" },
  { value: "annual", label: "Annual" },
  { value: "irregular", label: "Irregular" },
];

const metricDefinitions: readonly MetricDefinition[] = [
  { group: "Data coverage", metric: "quote_observation_count", label: "Duration", description: "Available daily quote observations per ISIN in the persisted historical-data store.", equation: "N₍quotes₎ = Σₜ 𝟙{Pₜ observed}", notation: "N₍quotes₎: available quote observations · Pₜ: adjusted close at time t · 𝟙: indicator", unit: "trading days" },
  { group: "Return", metric: "annualized_geometric_return", label: "Annual Return", description: "Compound annual return derived from daily log returns.", equation: "Rₐₙₙ = e^(252 · 𝔼[rₜ]) − 1", notation: "Rₐₙₙ: annual return · rₜ: daily log return · 𝔼: expected value · 252: trading days", unit: "%" },
  { group: "Risk", metric: "var", label: "Value at Risk", description: "Historical loss quantile at the configured confidence level.", equation: "VaRα = −Q₁₋α(rₜ)", notation: "α: confidence level · Q: return quantile · rₜ: log return at time t", unit: "%" },
  { group: "Risk", metric: "sortino_ratio", label: "Sortino ratio", description: "Annualized return per unit of downside deviation.", equation: "Sortino = (Rₐₙₙ − rƒ) / σd", notation: "Rₐₙₙ: annualized return · rƒ: risk-free rate · σd: downside deviation", unit: "ratio" },
  { group: "Risk", metric: "expected_shortfall", label: "Expected shortfall", description: "Mean loss beyond historical Value at Risk.", equation: "ESα = −𝔼[rₜ | rₜ ≤ Q₁₋α(rₜ)]", notation: "α: confidence level · 𝔼: expected value · Q: return quantile · rₜ: log return", unit: "%" },
  { group: "Risk", metric: "tail_observation_count", label: "Tail observations", description: "Returns included in the expected-shortfall tail.", equation: "Ntail = Σ 𝟙{rₜ ≤ Q₁₋α(rₜ)}", notation: "Σ: sum · 𝟙: indicator · α: confidence level · Q: quantile · rₜ: log return", unit: "observations" },
  { group: "Risk", metric: "sharpe_ratio", label: "Sharpe ratio", description: "Annualized return per unit of total volatility.", equation: "Sharpe = (Rₐₙₙ − rƒ) / σₐₙₙ", notation: "Rₐₙₙ: annualized return · rƒ: risk-free rate · σₐₙₙ: annualized volatility", unit: "ratio" },
  { group: "Risk", metric: "max_drawdown", label: "Maximum drawdown", description: "Largest peak-to-trough adjusted-close decline.", equation: "MDD = minₜ(Pₜ / maxᵤ≤ₜ Pᵤ − 1)", notation: "Pₜ: price at time t · Pᵤ: prior price · min/max: worst peak-to-trough change", unit: "%" },
  { group: "Trend", metric: "trend_r_squared", label: "Trend R-squared", description: "Fit quality of the log-price trend.", equation: "R² = 1 − SSE / SST,  ln(Pₜ) = β₀ + β₁t + εₜ", notation: "SSE: residual error · SST: total error · β₀/β₁: trend coefficients · εₜ: residual", unit: "ratio" },
];

const quoteDurationThresholds: readonly Readonly<{ label: string; minimum: number }>[] = [
  { label: "> 1 month", minimum: 21 },
  { label: "> 2 months", minimum: 42 },
  { label: "> 3 months", minimum: 63 },
  { label: "> 6 months", minimum: 126 },
  { label: "> 12 months", minimum: 252 },
  { label: "> 3 years", minimum: 756 },
  { label: "> 5 years", minimum: 1_260 },
  { label: "> 10 years", minimum: 2_520 },
];


function formatStatistic(value: number, unit?: string): string {
  if (unit === "%") return `${(value * 100).toFixed(2)}%`;
  if (unit === "observations" || unit === "trading days") return `${Math.round(value)} ${unit}`;
  return `${value.toFixed(2)}${unit ? ` ${unit}` : ""}`;
}

function formatHistogramValue(value: number, unit?: string): string {
  if (unit === "%") return (value * 100).toFixed(2);
  if (unit === "observations" || unit === "trading days") return String(Math.round(value));
  return value.toFixed(2);
}

function dividendFrequency(value: ApiUnivariateRow): DividendFrequency {
  const frequency = value.distribution_frequency;
  return dividendFrequencyOptions.some((option) => option.value === frequency)
    ? frequency as DividendFrequency
    : "accumulating";
}

async function loadUnivariateResults(runId: string): Promise<readonly ApiUnivariateRow[]> {
  const firstPage = await univariateStatisticsApi.loadResults(runId, 200, 0);
  const pages = await Promise.all(
    Array.from({ length: Math.ceil(firstPage.total / 200) - 1 }, (_, index) => (
      univariateStatisticsApi.loadResults(runId, 200, (index + 1) * 200)
    )),
  );
  return [...firstPage.items, ...pages.flatMap((page) => page.items)];
}

function estimatedRemainingTime(startedAt: number | undefined, completed: number, total: number): string {
  if (!startedAt || completed <= 0 || total <= completed) return "";
  const elapsedMilliseconds = Date.now() - startedAt * 1_000;
  if (elapsedMilliseconds <= 0) return "";
  const remainingSeconds = Math.ceil((elapsedMilliseconds / 1_000 / completed) * (total - completed));
  if (remainingSeconds < 60) return " (less than 1 min remaining)";
  const hours = Math.floor(remainingSeconds / 3_600);
  const minutes = Math.ceil((remainingSeconds % 3_600) / 60);
  return hours > 0 ? ` (about ${hours}h ${minutes}m remaining)` : ` (about ${minutes} min remaining)`;
}

export function UnivariateStatisticsPage() {
  const [workflowRevision, setWorkflowRevision] = useState(0);
  const workflow = useResource(loadWorkflow, [workflowRevision]);
  const [run, setRun] = useState<ApiResearchRun | null>(null);
  const [univariateStartedAt, setUnivariateStartedAt] = useState<number | undefined>();
  const [results, setResults] = useState<readonly ApiUnivariateRow[] | null>(null);
  const [portfolioDividendFrequencies, setPortfolioDividendFrequencies] = useState<DividendFrequency[]>([]);
  const [portfolioStatisticSelections, setPortfolioStatisticSelections] = useState<Record<string, string[]>>({});
  const [portfolioStatisticRanges, setPortfolioStatisticRanges] = useState<Record<string, SelectionRange[]>>({});
  const [activeStatisticTab, setActiveStatisticTab] = useState<UnivariateStatisticTab>("dividends");
  const [message, setMessage] = useState("");
  const [quoteStatus, setQuoteStatus] = useState<"idle" | "running" | "complete" | "failed">("idle");
  const [quoteProgress, setQuoteProgress] = useState(0);
  const [quoteMessage, setQuoteMessage] = useState("Fetch historical quotes for this selection.");
  const [quoteRunId, setQuoteRunId] = useState<string | null>(null);
  const [quoteRun, setQuoteRun] = useState<ApiQuoteFetch | null>(null);
  const [quoteUpdatedCount, setQuoteUpdatedCount] = useState<number | null>(null);
  const workflowQuoteRunId = workflow.status === "ready"
    ? workflow.data.stages.metadata_builder.quote_run_id ?? null
    : null;
  const workflowUnivariateRunId = workflow.status === "ready"
    ? workflow.data.stages.univariate_statistics.univariate_run_id ?? null
    : null;

  useEffect(() => {
    const resetProjectState = () => {
      setRun(null);
      setUnivariateStartedAt(undefined);
      setResults(null);
      setMessage("");
      setQuoteStatus("idle");
      setQuoteProgress(0);
      setQuoteMessage("Fetch historical quotes for this selection.");
      setQuoteRunId(null);
      setQuoteRun(null);
      setQuoteUpdatedCount(null);
      setWorkflowRevision((value) => value + 1);
    };
    window.addEventListener("portfell:project-updated", resetProjectState);
    return () => window.removeEventListener("portfell:project-updated", resetProjectState);
  }, []);

  useEffect(() => {
    if (!quoteRunId || quoteStatus !== "running") return;
    const activeRunId = quoteRunId;
    let cancelled = false;
    let timeoutId: number | undefined;

    async function pollQuoteRun() {
      try {
        const result = await loadQuoteRun(activeRunId);
        if (cancelled) return;
        const completed = result.completed ?? 0;
        const total = result.total ?? 0;
        const failed = result.failed ?? 0;
        setQuoteRun(result);
        setQuoteProgress(result.percent ?? 0);
        if (result.status === "running") {
          setQuoteMessage(`${completed.toLocaleString()} of ${total.toLocaleString()} quote-fetch tasks completed${estimatedRemainingTime(result.started_at, completed, total)}.`);
          timeoutId = window.setTimeout(() => void pollQuoteRun(), 750);
          return;
        }
        if (result.status === "failed") {
          setQuoteStatus("failed");
          setQuoteMessage(result.error_code || "Historical data download failed.");
          return;
        }
        setQuoteStatus("complete");
        setQuoteProgress(100);
        const updatedCount = result.quote_successes ?? result.selected_listing_count ?? 0;
        setQuoteUpdatedCount(updatedCount);
        setQuoteMessage(`${updatedCount.toLocaleString()} listings fetched; ${failed.toLocaleString()} provider tasks failed.`);
        window.dispatchEvent(new Event("portfell:workflow-updated"));
        setWorkflowRevision((value) => value + 1);
      } catch (error) {
        if (cancelled) return;
        setQuoteStatus("failed");
        setQuoteMessage(error instanceof Error ? error.message : "Quote fetch failed.");
      }
    }

    void pollQuoteRun();
    return () => {
      cancelled = true;
      if (timeoutId !== undefined) window.clearTimeout(timeoutId);
    };
  }, [quoteRunId, quoteStatus]);

  useEffect(() => {
    if (!workflowQuoteRunId || workflowQuoteRunId === quoteRunId) return;
    setQuoteRunId(workflowQuoteRunId);
    setQuoteStatus("running");
    setQuoteMessage("Restoring the current historical-data download status…");
  }, [quoteRunId, workflowQuoteRunId]);

  useEffect(() => {
    if (!workflowUnivariateRunId || results !== null) return;
    const restoredRunId = workflowUnivariateRunId;
    let cancelled = false;

    async function restoreUnivariateResults() {
      try {
        const [restoredRun, restoredResults] = await Promise.all([
          univariateStatisticsApi.loadRun(restoredRunId),
          loadUnivariateResults(restoredRunId),
        ]);
        if (cancelled) return;
        setRun(restoredRun);
        setResults(restoredResults);
        setMessage(`${restoredResults.length.toLocaleString()} listings restored.`);
      } catch (error) {
        if (cancelled) return;
        setMessage(error instanceof Error ? error.message : "Could not restore univariate statistics.");
      }
    }

    void restoreUnivariateResults();
    return () => { cancelled = true; };
  }, [results, workflowUnivariateRunId]);

  useEffect(() => {
    let cancelled = false;
    void loadProjectContext().then(async (context) => {
      const projectId = context.current_project_id;
      if (!projectId || cancelled) return;
      try {
        const saved = await univariateStatisticsApi.loadSelectionSettings(projectId);
        if (cancelled) return;
        setPortfolioDividendFrequencies(saved.dividend_frequencies.filter((value) => dividendFrequencyOptions.some((option) => option.value === value)));
        setPortfolioStatisticSelections(saved.statistic_labels);
        setPortfolioStatisticRanges(saved.statistic_ranges);
      } catch {
        if (!cancelled) {
          setPortfolioDividendFrequencies([]);
          setPortfolioStatisticSelections({});
          setPortfolioStatisticRanges({});
        }
      }
    });
    return () => { cancelled = true; };
  }, [workflowRevision]);

  useEffect(() => {
    if (!run || run.status !== "running") return;
    const activeRunId = run.run_id;
    let cancelled = false;
    let timeoutId: number | undefined;
    async function pollUnivariateRun() {
      try {
        const current = await univariateStatisticsApi.loadRun(activeRunId);
        if (cancelled) return;
        setRun(current);
        if (current.status === "running") {
          setMessage(`${current.completed.toLocaleString()} of ${current.total.toLocaleString()} listings computed${estimatedRemainingTime(univariateStartedAt, current.completed, current.total)}.`);
          timeoutId = window.setTimeout(() => void pollUnivariateRun(), 750);
          return;
        }
        if (current.status === "failed") {
          setMessage("Univariate computation failed. Please try again.");
          return;
        }
        const computedRows = await loadUnivariateResults(current.run_id);
        if (cancelled) return;
        setResults(computedRows);
        setMessage(`${computedRows.length.toLocaleString()} listings computed.`);
        window.dispatchEvent(new Event("portfell:workflow-updated"));
      } catch (error) {
        if (!cancelled) setMessage(error instanceof Error ? error.message : "Could not retrieve univariate computation status.");
      }
    }
    void pollUnivariateRun();
    return () => {
      cancelled = true;
      if (timeoutId !== undefined) window.clearTimeout(timeoutId);
    };
  // Keep the active poll alive while the status changes to complete, otherwise
  // its result request is cancelled by the effect cleanup before cards render.
  }, [run?.run_id, univariateStartedAt]);

  if (workflow.status === "loading" || workflow.status === "idle") {
    return <LoadingState label="Loading univariate statistics" />;
  }
  if (workflow.status === "error") return <p>Workflow state is unavailable.</p>;
  const stage = workflow.data.stages.univariate_statistics;
  const metadata = workflow.data.stages.metadata_builder;
  const dividendFrequencyCounts = dividendFrequencyOptions.map((option) => ({
    ...option,
    count: results?.filter((row) => dividendFrequency(row) === option.value).length ?? 0,
  }));
  const annualDividendYields = results?.flatMap((row) => {
    const value = Number(row.annual_dividend_yield ?? 0) * 100;
    return Number.isFinite(value) && value >= 0 ? [{ value, frequency: dividendFrequency(row) }] : [];
  }) ?? [];
  const annualDividendYieldMaximum = Math.max(...annualDividendYields.map(({ value }) => value), 1);
  const annualDividendHistogram = Array.from({ length: 8 }, (_, index) => {
    const lower = (index / 8) * annualDividendYieldMaximum;
    const upper = ((index + 1) / 8) * annualDividendYieldMaximum;
    const values = annualDividendYields.filter(({ value }) => index === 7
      ? value >= lower && value <= upper
      : value >= lower && value < upper);
    return {
      label: `${lower.toFixed(1)}–${upper.toFixed(1)}`,
      count: values.length,
      frequencies: dividendFrequencyOptions.map((option) => ({
        ...option,
        count: values.filter(({ frequency }) => frequency === option.value).length,
      })),
    };
  });
  const annualDividendHistogramMaximum = Math.max(...annualDividendHistogram.map(({ count }) => count), 1);

  async function saveProjectSelections(
    dividendFrequencies: DividendFrequency[],
    statisticLabels: Record<string, string[]>,
    statisticRanges: Record<string, SelectionRange[]>,
  ) {
    const context = await loadProjectContext();
    if (!context.current_project_id) return;
    await univariateStatisticsApi.saveSelectionSettings(context.current_project_id, {
      dividend_frequencies: dividendFrequencies,
      statistic_labels: statisticLabels,
      statistic_ranges: statisticRanges,
    });
    window.dispatchEvent(new Event("portfell:workflow-updated"));
  }

  function saveStatisticSelection(metric: string, values: string[], ranges: SelectionRange[]) {
    const nextLabels = { ...portfolioStatisticSelections, [metric]: values };
    const nextRanges = { ...portfolioStatisticRanges, [metric]: ranges };
    setPortfolioStatisticSelections(nextLabels);
    setPortfolioStatisticRanges(nextRanges);
    void saveProjectSelections(portfolioDividendFrequencies, nextLabels, nextRanges).catch((error) => {
      setMessage(error instanceof Error ? error.message : "Could not save the project selection.");
    });
  }

  async function compute() {
    if (!metadata.metadata_selection_id || !metadata.quote_run_id) return;
    setMessage("Computing univariate statistics…");
    try {
      const nextRun = await univariateStatisticsApi.startRun({
        metadata_selection_id: metadata.metadata_selection_id,
        quote_run_id: metadata.quote_run_id,
      });
      setRun(nextRun);
      setUnivariateStartedAt(Date.now() / 1_000);
      setResults(null);
      setMessage(`${nextRun.completed.toLocaleString()} of ${nextRun.total.toLocaleString()} listings computed.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Univariate computation failed.");
    }
  }

  async function fetchQuotes() {
    if (!metadata.metadata_selection_id) return;
    setQuoteStatus("running");
    setQuoteMessage(
      quoteRunId ? "Refreshing the current historical-data download status…" : "Fetching quotes and building the Silver dataset…",
    );
    try {
      const result = await univariateStatisticsApi.startQuoteRun({
        metadata_selection_id: metadata.metadata_selection_id,
      });
      setQuoteRunId(result.download_run_id);
      setQuoteRun(result);
      setQuoteProgress(result.percent ?? 0);
      if (result.status === "running") {
        const completed = result.completed ?? 0;
        const total = result.total ?? 0;
        setQuoteMessage(`${completed.toLocaleString()} of ${total.toLocaleString()} quote-fetch tasks completed${estimatedRemainingTime(result.started_at, completed, total)}.`);
      }
    } catch (error) {
      setQuoteStatus("failed");
      setQuoteProgress(0);
      setQuoteMessage(error instanceof Error ? error.message : "Quote fetch failed.");
    }
  }

  const updateHistoricalDataLabel = quoteStatus === "running"
    ? historicalDataUpdateLabel(quoteRun)
    : quoteUpdatedCount !== null
      ? `Update Historical Data · ${quoteUpdatedCount.toLocaleString()} ISINs updated`
      : "Update Historical Data";

  return (
    <section className="univariate-statistics-page" data-route="univariate-statistics-page">
      <Panel title="Univariate Statistics">
        {stage.status === "locked" ? <p>Update historical data to unlock univariate statistics.</p> : <>
          <div className="quote-fetch quote-fetch--panel univariate-compute">
            <label htmlFor="univariate-progress">Univariate statistics progress</label>
            <progress id="univariate-progress" max={100} value={run?.percent ?? 0} />
            <p className="status-line" aria-live="polite">{message || "Compute statistics for the downloaded historical data."}</p>
            <div className="quote-fetch__action quote-fetch__action--dual">
              <Button type="button" variant="secondary" disabled={!metadata.metadata_selection_id || quoteStatus === "running"} onClick={() => void fetchQuotes()} title={quoteMessage}>
                {updateHistoricalDataLabel}
              </Button>
              <Button type="button" variant="primary" disabled={!metadata.metadata_selection_id || !metadata.quote_run_id || run?.status === "running"} onClick={() => void compute()}>
                {run?.status === "running" ? "Computing…" : "Compute univariate statistics"}
              </Button>
            </div>
          </div>
          {results !== null ? <section className="univariate-statistic" aria-labelledby="univariate-statistic-title">
            <div className="univariate-statistic__tabs" role="tablist" aria-label="Univariate statistic">
              <button type="button" role="tab" aria-selected={activeStatisticTab === "dividends"} className={activeStatisticTab === "dividends" ? "is-active" : undefined} onClick={() => setActiveStatisticTab("dividends")}>Dividends</button>
              {metricDefinitions.map((statistic) => <button key={statistic.metric} type="button" role="tab" aria-selected={activeStatisticTab === statistic.metric} className={activeStatisticTab === statistic.metric ? "is-active" : undefined} onClick={() => setActiveStatisticTab(statistic.metric)}>{statistic.label}</button>)}
            </div>
            {activeStatisticTab === "dividends" ? <div className="dividend-statistic">
              <div className="dividend-statistic__details">
              <div>
                <h3 id="univariate-statistic-title">Dividends</h3>
                <p>Distribution frequency and trailing annual dividend yield by ISIN.</p>
              </div>
              <ul className="dividend-frequency-list" aria-label="Dividend payout frequencies">
                {dividendFrequencyCounts.map(({ value, label, count }) => <li key={value}>
                  <span><i className="dividend-frequency-swatch" data-frequency={value} />{label}</span><strong>{results && results.length > 0 ? `${((count / results.length) * 100).toFixed(1)}%` : "0.0%"}</strong><small>{count} ISINs</small>
                </li>)}
              </ul>
              <p className="univariate-equation" aria-label="Annual dividend yield equals annual distributions divided by price times one hundred percent">Dividend yield = Σ Dₜ / P × 100%</p>
              <p className="univariate-notation">Σ: sum of payouts · Dₜ: distribution paid at time t · P: current price</p>
            </div>
            <div className="dividend-statistic__right">
              <label className="portfolio-selection">
                Portfolio selection
                <select multiple size={4} value={portfolioDividendFrequencies} onChange={(event) => {
                  const values = Array.from(event.currentTarget.selectedOptions, (option) => option.value as DividendFrequency);
                  setPortfolioDividendFrequencies(values);
                  void saveProjectSelections(values, portfolioStatisticSelections, portfolioStatisticRanges).catch((error) => {
                    setMessage(error instanceof Error ? error.message : "Could not save the project selection.");
                  });
                }}>
                  {dividendFrequencyOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </label>
            <div className="dividend-histogram" role="img" aria-label={`Annual dividend yield distribution for ${results.length} ISINs`}>
              <span className="dividend-histogram__axis dividend-histogram__axis--y">ISIN count</span>
              <div className="dividend-histogram__plot">
                {annualDividendHistogram.map(({ label, count, frequencies }) => <div className="dividend-histogram__bar" key={label} tabIndex={0} aria-label={`${label}: ${count} ISINs; ${frequencies.filter((frequency) => frequency.count > 0).map((frequency) => `${frequency.label} ${frequency.count}`).join(", ")}`}>
                  <span className="dividend-histogram__count">{count}</span>
                  <span className="dividend-histogram__column" style={{ height: `${(count / annualDividendHistogramMaximum) * 100}%` }}>
                    {frequencies.filter((frequency) => frequency.count > 0).map(({ value, count: frequencyCount }) => <i key={value} data-frequency={value} style={{ flexGrow: frequencyCount }} />)}
                  </span>
                  <span className="dividend-histogram__label">{label}</span>
                  <span className="dividend-histogram__tooltip" role="tooltip">
                    <strong>{label}% annual dividend yield</strong>
                    <span>{count} ISINs</span>
                    {frequencies.filter((frequency) => frequency.count > 0).map((frequency) => <span className="histogram-tooltip__row" key={frequency.value}><i className="dividend-frequency-swatch" data-frequency={frequency.value} />{frequency.label}: {frequency.count}</span>)}
                  </span>
                </div>)}
              </div>
              <span className="dividend-histogram__axis dividend-histogram__axis--x">Annual dividend yield (%)</span>
            </div>
              </div>
            </div> : results.length > 0 ? (() => {
                  const statistic = metricDefinitions.find((definition) => definition.metric === activeStatisticTab)!;
                  const metricValues = results.flatMap((row) => typeof row[statistic.metric] === "number" && Number.isFinite(row[statistic.metric])
                    ? [{ value: row[statistic.metric] as number, frequency: dividendFrequency(row) }]
                    : []);
                  const values = metricValues.map(({ value }) => value);
                  const minimum = values.length > 0 ? Math.min(...values) : 0;
                  const maximumValue = values.length > 0 ? Math.max(...values) : 0;
                  const isQuoteDuration = statistic.metric === "quote_observation_count";
                  const buckets = values.length === 0 ? [] : isQuoteDuration ? quoteDurationThresholds.map(({ label, minimum: threshold }) => {
                    const entries = metricValues.filter(({ value }) => value > threshold);
                    return {
                      label,
                      lower: threshold,
                      upper: Number.MAX_SAFE_INTEGER,
                      count: entries.length,
                      frequencies: dividendFrequencyOptions.map((option) => ({
                        ...option,
                        count: entries.filter(({ frequency }) => frequency === option.value).length,
                      })),
                    };
                  }) : Array.from({ length: 12 }, (_, index) => {
                    const lower = minimum + ((maximumValue - minimum) / 12) * index;
                    const upper = minimum + ((maximumValue - minimum) / 12) * (index + 1);
                    const entries = metricValues.filter(({ value }) => minimum === maximumValue || (index === 11 ? value >= lower && value <= upper : value >= lower && value < upper));
                    return {
                      label: undefined,
                      lower,
                      upper,
                      count: entries.length,
                      frequencies: dividendFrequencyOptions.map((option) => ({
                        ...option,
                        count: entries.filter(({ frequency }) => frequency === option.value).length,
                      })),
                    };
                  });
                  const maximum = Math.max(...buckets.map(({ count }) => count), 1);
                  const statisticValuesByDividendFrequency = dividendFrequencyOptions.map((option) => {
                    const frequencyValues = metricValues.filter(({ frequency }) => frequency === option.value).map(({ value }) => value);
                    return {
                      ...option,
                      count: frequencyValues.length,
                      average: frequencyValues.length === 0 ? null : frequencyValues.reduce((sum, value) => sum + value, 0) / frequencyValues.length,
                    };
                  });
                  const histogramSelectionOptions = isQuoteDuration
                    ? buckets.map(({ label }) => label!)
                    : Array.from(new Set(buckets.map(({ lower, upper }) => minimum === maximumValue
                    ? formatHistogramValue(minimum, statistic.unit)
                    : `${formatHistogramValue(lower, statistic.unit)} – ${formatHistogramValue(upper, statistic.unit)}`)));
                  const histogramSelectionRanges = Object.fromEntries(buckets.map(({ label, lower, upper }) => [
                    isQuoteDuration ? label! :
                    minimum === maximumValue
                      ? formatHistogramValue(minimum, statistic.unit)
                      : `${formatHistogramValue(lower, statistic.unit)} – ${formatHistogramValue(upper, statistic.unit)}`,
                    { minimum: lower, maximum: upper },
                  ]));
                  return <section className="univariate-group-card" aria-labelledby="univariate-statistic-title">
                    <div className="univariate-group-card__facts">
                      <h3 id="univariate-statistic-title">{statistic.label}</h3>
                      <p>{statistic.description}</p>
                      <p className="univariate-group-card__fact-heading">Average {statistic.label} by dividend type</p>
                      <ul className="dividend-frequency-list" aria-label={`Average ${statistic.label} by dividend frequency`}>
                        {statisticValuesByDividendFrequency.map(({ value, label, count, average: frequencyAverage }) => <li key={value}>
                          <span><i className="dividend-frequency-swatch" data-frequency={value} />{label}</span>
                          <strong>{frequencyAverage === null ? "—" : formatStatistic(frequencyAverage, statistic.unit)}</strong>
                          <small>{count} ISINs</small>
                        </li>)}
                      </ul>
                      <p className="univariate-equation" aria-label={`Formula: ${statistic.equation}`}>{statistic.equation}</p>
                      <p className="univariate-notation">{statistic.notation}</p>
                    </div>
                    <div className="univariate-group-card__right">
                      <label className="portfolio-selection">
                        Portfolio selection
                        <select multiple size={4} value={portfolioStatisticSelections[statistic.metric] ?? []} onChange={(event) => {
                          const values = Array.from(event.currentTarget.selectedOptions, (option) => option.value);
                          saveStatisticSelection(
                            statistic.metric,
                            values,
                            values.flatMap((value) => {
                              const range = histogramSelectionRanges[value];
                              return range ? [range] : [];
                            }),
                          );
                        }}>
                          {histogramSelectionOptions.map((range) => <option key={range} value={range}>{range}</option>)}
                        </select>
                      </label>
                      <div className="univariate-group-card__chart" role="img" aria-label={`${statistic.label} distribution across ${values.length} ISINs`}>
                      <span className="univariate-group-card__axis univariate-group-card__axis--y">ISIN count</span>
                      <div className="univariate-group-card__plot">
                        {buckets.length === 0 ? <span className="status-line">No values available.</span> : buckets.map(({ label, lower, upper, count, frequencies }, bucket) => {
                          const range = isQuoteDuration ? label! : minimum === maximumValue ? formatHistogramValue(minimum, statistic.unit) : `${formatHistogramValue(lower, statistic.unit)} – ${formatHistogramValue(upper, statistic.unit)}`;
                          const breakdown = frequencies.filter((frequency) => frequency.count > 0).map((frequency) => `${frequency.label}: ${frequency.count}`).join(", ");
                          return <div className="univariate-group-card__bar" key={bucket} tabIndex={0} aria-label={`${range}: ${count} ISINs${breakdown ? `; ${breakdown}` : ""}`}>
                            <span className="univariate-group-card__column" style={{ height: `${count === 0 ? 2 : (count / maximum) * 100}%` }}>
                              {frequencies.filter((frequency) => frequency.count > 0).map(({ value, count: frequencyCount }) => <i key={value} data-frequency={value} style={{ flexGrow: frequencyCount }} />)}
                            </span>
                            <span className="univariate-group-card__label">{range}</span>
                            <span className="univariate-group-card__tooltip" role="tooltip">
                              <strong>{isQuoteDuration ? `${range} (${lower} trading days)` : `${range} ${statistic.unit}`}</strong>
                              <span>{count} ISINs</span>
                              {frequencies.filter((frequency) => frequency.count > 0).map((frequency) => <span className="histogram-tooltip__row" key={frequency.value}><i className="dividend-frequency-swatch" data-frequency={frequency.value} />{frequency.label}: {frequency.count}</span>)}
                            </span>
                          </div>;
                        })}
                      </div>
                      <span className="univariate-group-card__axis univariate-group-card__axis--x">{isQuoteDuration ? "Minimum quote history" : `${statistic.label} (${statistic.unit ?? "value"})`}</span>
                      </div>
                    </div>
                  </section>;
                })() : <p>No univariate rows matched the pinned selection.</p>}
          </section> : null}
        </>}
        {stage.status === "locked" && <div className="quote-fetch__action quote-fetch__action--dual">
          <Button type="button" variant="primary" disabled={!metadata.metadata_selection_id || quoteStatus === "running"} onClick={() => void fetchQuotes()} title={quoteMessage}>{updateHistoricalDataLabel}</Button>
        </div>}
      </Panel>
    </section>
  );
}
