
import { useEffect, useState } from "react";
import { loadQuoteRun, loadWorkflow, postJson, requestJson } from "../api/client";
import { Button } from "../components/button";
import { LoadingState } from "../components/loading-state";
import { Panel } from "../components/panel";
import type { ApiPage, ApiQuoteFetch, ApiResearchRun, ApiUnivariateRow } from "../contracts";
import { useResource } from "../hooks/use-resource";

function metric(value: number | null | undefined): string {
  return value == null ? "—" : value.toFixed(4);
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
  const [results, setResults] = useState<ApiPage<ApiUnivariateRow> | null>(null);
  const [message, setMessage] = useState("");
  const [quoteStatus, setQuoteStatus] = useState<"idle" | "running" | "complete" | "failed">("idle");
  const [quoteProgress, setQuoteProgress] = useState(0);
  const [quoteMessage, setQuoteMessage] = useState("Fetch historical quotes for this selection.");
  const [quoteRunId, setQuoteRunId] = useState<string | null>(null);

  useEffect(() => {
    const resetProjectState = () => {
      setRun(null);
      setResults(null);
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
          setQuoteMessage("Quote fetch failed. Retry the run after checking the selected listings.");
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

  if (workflow.status === "loading" || workflow.status === "idle") {
    return <LoadingState label="Loading univariate statistics" />;
  }
  if (workflow.status === "error") return <p>Workflow state is unavailable.</p>;
  const stage = workflow.data.stages.univariate_statistics;
  const metadata = workflow.data.stages.metadata_filter;

  async function compute() {
    if (!metadata.metadata_selection_id || !metadata.quote_run_id) return;
    setMessage("Computing univariate statistics…");
    try {
      const nextRun = await postJson<ApiResearchRun>("/api/univariate-statistics/runs", {
        metadata_selection_id: metadata.metadata_selection_id,
        quote_run_id: metadata.quote_run_id,
      });
      setRun(nextRun);
      const page = await requestJson<ApiPage<ApiUnivariateRow>>(
        `/api/univariate-statistics/runs/${nextRun.run_id}/results?limit=50&offset=0`,
      );
      setResults(page);
      setMessage(`${page.total.toLocaleString()} listings computed.`);
      window.dispatchEvent(new Event("portfell:workflow-updated"));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Univariate computation failed.");
    }
  }

  async function fetchQuotes() {
    if (!metadata.metadata_selection_id || quoteStatus === "running") return;
    setQuoteStatus("running");
    setQuoteProgress(0);
    setQuoteMessage("Fetching quotes and building the Silver dataset…");
    try {
      const result = await postJson<ApiQuoteFetch>("/api/quote-runs", {
        metadata_selection_id: metadata.metadata_selection_id,
      });
      setQuoteRunId(result.download_run_id);
      setQuoteProgress(result.percent ?? 0);
      setQuoteMessage("Quote fetch started. Waiting for the first completed provider task…");
    } catch (error) {
      setQuoteStatus("failed");
      setQuoteProgress(0);
      setQuoteMessage(error instanceof Error ? error.message : "Quote fetch failed.");
    }
  }

  return (
    <section className="univariate-statistics-page" data-route="univariate-statistics-page">
      <Panel title="Fetch Historical Quotes">
        <div className="quote-fetch quote-fetch--panel">
          <label htmlFor="quote-progress">Quote fetch progress</label>
          <progress id="quote-progress" max={100} value={quoteProgress} />
          <p className="status-line" aria-live="polite">{quoteMessage}</p>
          <div className="quote-fetch__action">
            <Button type="button" variant="primary" disabled={!metadata.metadata_selection_id || quoteStatus === "running"} onClick={() => void fetchQuotes()}>
              {quoteStatus === "running" ? "Fetching quotes…" : "Fetch quotes"}
            </Button>
          </div>
        </div>
      </Panel>
      <Panel title="Univariate Statistics">
        {stage.status === "locked" ? <p>Fetch quotes above to unlock univariate statistics.</p> : <>
          <Button type="button" variant="primary" disabled={run?.status === "running"} onClick={() => void compute()}>
            {run?.status === "running" ? "Computing…" : "Compute univariate statistics"}
          </Button>
          <p aria-live="polite">{message}</p>
          {run && <progress max={100} value={run.percent} aria-label="Univariate progress" />}
          {results && results.items.length > 0 ? (
            <table>
              <thead><tr><th>Listing</th><th>ISIN</th><th>Observations</th><th>Return</th><th>Volatility</th><th>Sharpe</th><th>Drawdown</th><th>Expected shortfall</th></tr></thead>
              <tbody>
                {results.items.map((row) => (
                  <tr key={`${row.isin}:${row.exchange}:${row.code}`}>
                    <td>{row.code}.{row.exchange}</td><td>{row.isin}</td>
                    <td>{row.quote_observation_count}</td><td>{metric(row.annualized_return)}</td>
                    <td>{metric(row.annualized_volatility)}</td><td>{metric(row.sharpe_ratio)}</td>
                    <td>{metric(row.max_drawdown)}</td><td>{metric(row.expected_shortfall)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : results ? <p>No univariate rows matched the pinned selection.</p> : null}
        </>}
      </Panel>
    </section>
  );
}
