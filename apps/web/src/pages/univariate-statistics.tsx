
import { Fragment, useEffect, useState } from "react";
import { loadQuoteRun, loadWorkflow, postJson, requestJson } from "../api/client";
import { Button } from "../components/button";
import { LoadingState } from "../components/loading-state";
import { Panel } from "../components/panel";
import type { ApiPage, ApiQuoteFetch, ApiResearchRun, ApiUnivariateRow } from "../contracts";
import { useResource } from "../hooks/use-resource";

type MetricDefinition = Readonly<{ group: string; metric: string; label: string; description: string; equation: string }>;
type DividendFrequency = "accumulating" | "monthly" | "quarterly" | "semiannual" | "annual" | "unknown" | "irregular";

const dividendFrequencyOptions: readonly Readonly<{ value: DividendFrequency; label: string }>[] = [
  { value: "accumulating", label: "None" },
  { value: "monthly", label: "Monthly" },
  { value: "quarterly", label: "Quarterly" },
  { value: "semiannual", label: "Semi-annual" },
  { value: "annual", label: "Annual" },
  { value: "unknown", label: "Unknown" },
  { value: "irregular", label: "Irregular" },
];

const metricDefinitions: readonly MetricDefinition[] = [
  { group: "History Coverage", metric: "quote_observation_count", label: "Quote observations", description: "Number of adjusted-close observations.", equation: "n" },
  { group: "History Coverage", metric: "return_observation_count", label: "Return observations", description: "Number of daily returns used.", equation: "n - 1" },
  { group: "Return Level", metric: "total_return", label: "Total return", description: "Change across the full price history.", equation: "P_T / P_0 - 1" },
  { group: "Return Level", metric: "cagr", label: "CAGR", description: "Annualized compound growth rate.", equation: "(P_T / P_0)^{1/y} - 1" },
  { group: "Return Level", metric: "annualized_return", label: "Annualized log return", description: "Mean daily log return annualized to 252 trading days.", equation: "252 · mean(r_log)" },
  { group: "Return Level", metric: "annualized_geometric_return", label: "Annualized geometric return", description: "Compounded annualized log return.", equation: "e^{252 · mean(r_log)} - 1" },
  { group: "Return Distribution", metric: "mean_log_return", label: "Mean log return", description: "Average daily log return.", equation: "mean(ln(P_t / P_{t-1}))" },
  { group: "Return Distribution", metric: "median_log_return", label: "Median log return", description: "Median daily log return.", equation: "median(r_log)" },
  { group: "Return Distribution", metric: "min_log_return", label: "Minimum log return", description: "Worst observed daily log return.", equation: "min(r_log)" },
  { group: "Return Distribution", metric: "max_log_return", label: "Maximum log return", description: "Best observed daily log return.", equation: "max(r_log)" },
  { group: "Return Distribution", metric: "positive_day_ratio", label: "Positive-day ratio", description: "Share of days with positive log return.", equation: "count(r_log > 0) / n" },
  { group: "Volatility And Downside Risk", metric: "daily_log_return_std", label: "Daily log-return deviation", description: "Sample deviation of daily log returns.", equation: "std(r_log)" },
  { group: "Volatility And Downside Risk", metric: "annualized_volatility", label: "Annualized volatility", description: "Daily log-return deviation annualized to 252 days.", equation: "std(r_log) · sqrt(252)" },
  { group: "Volatility And Downside Risk", metric: "downside_deviation", label: "Downside deviation", description: "Deviation of negative daily log returns.", equation: "sqrt(mean(min(r_log, 0)^2)) · sqrt(252)" },
  { group: "Risk-Adjusted Performance", metric: "sharpe_ratio", label: "Sharpe ratio", description: "Annualized return per unit of total volatility.", equation: "R_ann / sigma_ann" },
  { group: "Risk-Adjusted Performance", metric: "sortino_ratio", label: "Sortino ratio", description: "Annualized return per unit of downside deviation.", equation: "R_ann / downside_deviation" },
  { group: "Tail Risk", metric: "var", label: "Value at Risk", description: "Historical loss quantile at the configured confidence level.", equation: "-Q_{1-c}(r_log)" },
  { group: "Tail Risk", metric: "expected_shortfall", label: "Expected shortfall", description: "Mean loss beyond historical Value at Risk.", equation: "-mean(r_log | r_log <= Q_{1-c})" },
  { group: "Tail Risk", metric: "tail_observation_count", label: "Tail observations", description: "Returns included in the expected-shortfall tail.", equation: "count(r_log <= Q_{1-c})" },
  { group: "Drawdown And Trend", metric: "max_drawdown", label: "Maximum drawdown", description: "Largest peak-to-trough adjusted-close decline.", equation: "min(P_t / max(P_{0..t}) - 1)" },
  { group: "Drawdown And Trend", metric: "log_price_slope", label: "Log-price slope", description: "Linear trend slope of log adjusted closes.", equation: "slope(ln(P_t), t)" },
  { group: "Drawdown And Trend", metric: "trend_r_squared", label: "Trend R-squared", description: "Fit quality of the log-price trend.", equation: "R^2(ln(P_t), t)" },
  { group: "Income Distribution", metric: "distribution_events_per_year", label: "Distribution events per year", description: "Annualized frequency of positive distributions.", equation: "events / elapsed_years" },
  { group: "Income Distribution", metric: "distribution_observation_count", label: "Distribution observations", description: "Number of positive distribution events.", equation: "count(distributions > 0)" },
  { group: "Data Quality And Production Readiness", metric: "quarantined_price_count", label: "Quarantined prices", description: "Price observations excluded by quality validation.", equation: "count(quarantined prices)" },
];

function histogram(values: readonly number[]): readonly number[] {
  if (values.length === 0) return [];
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  if (minimum === maximum) return [values.length];
  const buckets = Array.from({ length: 12 }, () => 0);
  for (const value of values) buckets[Math.min(11, Math.floor(((value - minimum) / (maximum - minimum)) * 12))] += 1;
  return buckets;
}

function dividendFrequency(value: ApiUnivariateRow): DividendFrequency {
  const frequency = value.distribution_frequency;
  return dividendFrequencyOptions.some((option) => option.value === frequency)
    ? frequency as DividendFrequency
    : "unknown";
}

async function loadUnivariateResults(runId: string): Promise<readonly ApiUnivariateRow[]> {
  const firstPage = await requestJson<ApiPage<ApiUnivariateRow>>(
    `/api/univariate-statistics/runs/${runId}/results?limit=200&offset=0`,
  );
  const pages = await Promise.all(
    Array.from({ length: Math.ceil(firstPage.total / 200) - 1 }, (_, index) => requestJson<ApiPage<ApiUnivariateRow>>(
      `/api/univariate-statistics/runs/${runId}/results?limit=200&offset=${(index + 1) * 200}`,
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
  const [filterValues, setFilterValues] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const [quoteStatus, setQuoteStatus] = useState<"idle" | "running" | "complete" | "failed">("idle");
  const [quoteProgress, setQuoteProgress] = useState(0);
  const [quoteMessage, setQuoteMessage] = useState("Fetch historical quotes for this selection.");
  const [quoteRunId, setQuoteRunId] = useState<string | null>(null);
  const workflowQuoteRunId = workflow.status === "ready"
    ? workflow.data.stages.metadata_filter.quote_run_id ?? null
    : null;
  const workflowUnivariateRunId = workflow.status === "ready"
    ? workflow.data.stages.univariate_statistics.univariate_run_id ?? null
    : null;

  useEffect(() => {
    const resetProjectState = () => {
      setRun(null);
      setUnivariateStartedAt(undefined);
      setResults(null);
      setFilterValues({});
      setMessage("");
      setQuoteStatus("idle");
      setQuoteProgress(0);
      setQuoteMessage("Fetch historical quotes for this selection.");
      setQuoteRunId(null);
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
        setQuoteMessage(`${(result.quote_successes ?? result.selected_listing_count ?? 0).toLocaleString()} listings fetched; ${failed.toLocaleString()} provider tasks failed.`);
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
          requestJson<ApiResearchRun>(`/api/univariate-statistics/runs/${restoredRunId}`),
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
    if (!run || run.status !== "running") return;
    const activeRunId = run.run_id;
    let cancelled = false;
    let timeoutId: number | undefined;
    async function pollUnivariateRun() {
      try {
        const current = await requestJson<ApiResearchRun>(`/api/univariate-statistics/runs/${activeRunId}`);
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
  }, [run, univariateStartedAt]);

  if (workflow.status === "loading" || workflow.status === "idle") {
    return <LoadingState label="Loading univariate statistics" />;
  }
  if (workflow.status === "error") return <p>Workflow state is unavailable.</p>;
  const stage = workflow.data.stages.univariate_statistics;
  const metadata = workflow.data.stages.metadata_filter;
  const dividendFrequencyCounts = dividendFrequencyOptions.map((option) => ({
    ...option,
    count: results?.filter((row) => dividendFrequency(row) === option.value).length ?? 0,
  }));
  const annualDividendYields = results?.flatMap((row) => {
    const value = Number(row.annual_dividend_yield ?? 0) * 100;
    return Number.isFinite(value) && value >= 0 ? [value] : [];
  }) ?? [];
  const annualDividendYieldMaximum = Math.max(...annualDividendYields, 1);
  const annualDividendHistogram = Array.from({ length: 8 }, (_, index) => {
    const lower = (index / 8) * annualDividendYieldMaximum;
    const upper = ((index + 1) / 8) * annualDividendYieldMaximum;
    const count = annualDividendYields.filter((value) => index === 7
      ? value >= lower && value <= upper
      : value >= lower && value < upper).length;
    return { label: `${lower.toFixed(1)}–${upper.toFixed(1)}%`, count };
  });
  const annualDividendHistogramMaximum = Math.max(...annualDividendHistogram.map(({ count }) => count), 1);

  async function compute() {
    if (!metadata.metadata_selection_id || !metadata.quote_run_id) return;
    setMessage("Computing univariate statistics…");
    try {
      const nextRun = await postJson<ApiResearchRun>("/api/univariate-statistics/runs", {
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
      const result = await postJson<ApiQuoteFetch>("/api/quote-runs", {
        metadata_selection_id: metadata.metadata_selection_id,
      });
      setQuoteRunId(result.download_run_id);
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

  return (
    <section className="univariate-statistics-page" data-route="univariate-statistics-page">
      <Panel title="Download Historical Data">
        <div className="quote-fetch quote-fetch--panel">
          <label htmlFor="quote-progress">Quote fetch progress</label>
          <progress id="quote-progress" max={100} value={quoteProgress} />
          <p className="status-line" aria-live="polite">{quoteMessage}</p>
          <div className="quote-fetch__action">
            <Button type="button" variant="primary" disabled={!metadata.metadata_selection_id} onClick={() => void fetchQuotes()}>
              {quoteStatus === "running" ? "Refresh Historical Download Status" : "Download Historical Data"}
            </Button>
          </div>
        </div>
      </Panel>
      <Panel title="Univariate Statistics">
        {stage.status === "locked" ? <p>Download historical data above to unlock univariate statistics.</p> : <>
          <div className="quote-fetch quote-fetch--panel univariate-compute">
            <label htmlFor="univariate-progress">Univariate statistics progress</label>
            <progress id="univariate-progress" max={100} value={run?.percent ?? 0} />
            <p className="status-line" aria-live="polite">{message || "Compute statistics for the downloaded historical data."}</p>
            <div className="quote-fetch__action">
              <Button type="button" variant="primary" disabled={!metadata.metadata_selection_id || !metadata.quote_run_id || run?.status === "running"} onClick={() => void compute()}>
                {run?.status === "running" ? "Computing…" : "Compute univariate statistics"}
              </Button>
            </div>
          </div>
          <section className="dividend-statistic" aria-labelledby="dividend-statistic-title">
            <div className="dividend-statistic__details">
              <div>
                <h3 id="dividend-statistic-title">Dividends</h3>
                <p>Distribution frequency and trailing annual dividend yield by ISIN.</p>
              </div>
              <ul className="dividend-frequency-list" aria-label="Dividend payout frequencies">
                {dividendFrequencyCounts.map(({ value, label, count }) => <li key={value}>
                  <span>{label}</span><strong>{results && results.length > 0 ? `${((count / results.length) * 100).toFixed(1)}%` : "0.0%"}</strong><small>{count} ISINs</small>
                </li>)}
              </ul>
            </div>
            {results === null ? <p className="status-line">Compute univariate statistics to populate this histogram.</p> : <div className="dividend-histogram" role="img" aria-label={`Annual dividend yield distribution for ${results.length} ISINs`}>
              {annualDividendHistogram.map(({ label, count }) => <div className="dividend-histogram__bar" key={label}>
                <span className="dividend-histogram__count">{count}</span>
                <span className="dividend-histogram__column" style={{ height: `${count === 0 ? 4 : Math.max(12, (count / annualDividendHistogramMaximum) * 100)}%` }} />
                <span className="dividend-histogram__label">{label}</span>
              </div>)}
            </div>}
          </section>
          {results && results.length > 0 ? (
            <>
              <div className="univariate-metric-table">
                <table>
                  <thead><tr><th>Statistic</th><th>Description</th><th>Equation</th><th>Distribution</th><th>Filter value</th></tr></thead>
                  <tbody>
                    {metricDefinitions.map((definition, index) => {
                      const values = results.flatMap((row) => typeof row[definition.metric] === "number" && Number.isFinite(row[definition.metric]) ? [row[definition.metric] as number] : []);
                      const buckets = histogram(values);
                      const maximum = Math.max(...buckets, 1);
                      const priorGroup = metricDefinitions[index - 1]?.group;
                      return <Fragment key={definition.metric}>
                        {definition.group !== priorGroup ? <tr className="univariate-metric-table__group"><th colSpan={5}>{definition.group}</th></tr> : null}
                        <tr>
                          <th scope="row">{definition.label}</th><td>{definition.description}</td><td><code>{definition.equation}</code></td>
                          <td><div className="univariate-histogram" aria-label={`${definition.label} distribution from ${values.length} listings`}>{buckets.map((count, bucket) => <span key={bucket} style={{ height: `${Math.max(8, (count / maximum) * 100)}%` }} />)}</div></td>
                          <td><input type="number" step="any" value={filterValues[definition.metric] ?? ""} onChange={(event) => setFilterValues((current) => ({ ...current, [definition.metric]: event.target.value }))} aria-label={`${definition.label} filter value`} /></td>
                        </tr>
                      </Fragment>;
                    })}
                  </tbody>
                </table>
              </div>
            </>
          ) : results ? <p>No univariate rows matched the pinned selection.</p> : null}
        </>}
      </Panel>
    </section>
  );
}
