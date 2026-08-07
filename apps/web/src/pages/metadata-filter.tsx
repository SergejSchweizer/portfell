
import { useEffect, useState, type FormEvent } from "react";
import { loadProjectContext, loadProjectMetadataFilter, loadQuoteRun, postJson, requestJson } from "../api/client";
import { Button } from "../components/button";
import { EmptyState } from "../components/empty-state";
import { LoadingState } from "../components/loading-state";
import { Panel } from "../components/panel";
import type { ApiFieldOptions, ApiMetadataProject, ApiProjectSummary, ApiQuoteFetch } from "../contracts";
import { useResource } from "../hooks/use-resource";

async function loadFieldOptions(): Promise<ApiFieldOptions> {
  return requestJson<ApiFieldOptions>("/api/metadata-filter/options");
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

export function MetadataFilterPage() {
  const [metadataRevision, setMetadataRevision] = useState(0);
  const options = useResource(loadFieldOptions, [metadataRevision]);
  const [exchange, setExchange] = useState("");
  const [instrumentType, setInstrumentType] = useState("");
  const [country, setCountry] = useState("");
  const [currency, setCurrency] = useState("");
  const [name, setName] = useState("");
  const [projectId, setProjectId] = useState("");
  const [metadataSelectionId, setMetadataSelectionId] = useState("");
  const [selectionStatus, setSelectionStatus] = useState("Choose at least one metadata filter.");
  const [quoteStatus, setQuoteStatus] = useState<"idle" | "running" | "complete" | "failed">("idle");
  const [quoteProgress, setQuoteProgress] = useState(0);
  const [quoteMessage, setQuoteMessage] = useState("Quotes have not been fetched for this selection.");
  const [quoteRunId, setQuoteRunId] = useState<string | null>(null);

  useEffect(() => {
    const refresh = () => setMetadataRevision((value) => value + 1);
    window.addEventListener("portfell:metadata-updated", refresh);
    return () => window.removeEventListener("portfell:metadata-updated", refresh);
  }, []);

  useEffect(() => {
    let cancelled = false;

    const resetProjectState = () => {
      setProjectId("");
      setMetadataSelectionId("");
      setSelectionStatus("Choose at least one metadata filter.");
      setQuoteStatus("idle");
      setQuoteProgress(0);
      setQuoteMessage("Quotes have not been fetched for this selection.");
      setQuoteRunId(null);
    };

    const loadProjectFilter = async (project: ApiProjectSummary | null) => {
      if (!project?.selection_id) {
        resetProjectState();
        return;
      }
      setSelectionStatus("Loading saved metadata filter…");
      setQuoteStatus("idle");
      setQuoteProgress(0);
      setQuoteRunId(null);
      try {
        const filter = await loadProjectMetadataFilter(project.project_id);
        if (cancelled) return;
        setExchange(filter.exchange);
        setInstrumentType(filter.instrument_type);
        setCountry(filter.country);
        setCurrency(filter.currency);
        setName(filter.name);
        setProjectId(filter.project_id);
        setMetadataSelectionId(filter.selection_id);
        setSelectionStatus(`${filter.selected_count.toLocaleString()} listings selected.`);
        setQuoteMessage(project.data_loaded ? "Quotes are available for this selection." : "Selection ready. Fetch historical quotes to continue.");
      } catch (error) {
        if (cancelled) return;
        resetProjectState();
        setSelectionStatus(error instanceof Error ? error.message : "Saved metadata filter could not be loaded.");
      }
    };

    const restoreCurrentProject = () => {
      void loadProjectContext().then((context) => loadProjectFilter(context.current_project));
    };
    const handleProjectUpdate = (event: Event) => {
      const context = (event as CustomEvent<{ current_project: ApiProjectSummary | null }>).detail;
      void loadProjectFilter(context.current_project);
    };

    restoreCurrentProject();
    window.addEventListener("portfell:project-updated", handleProjectUpdate);
    return () => {
      cancelled = true;
      window.removeEventListener("portfell:project-updated", handleProjectUpdate);
    };
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
          setQuoteMessage(
            `${completed.toLocaleString()} of ${total.toLocaleString()} quote-fetch tasks completed${estimatedRemainingTime(result.started_at, completed, total)}.`,
          );
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
        setQuoteMessage(
          `${(result.quote_successes ?? result.selected_listing_count ?? 0).toLocaleString()} listings fetched; ${failed.toLocaleString()} provider tasks failed.`,
        );
        window.dispatchEvent(new Event("portfell:workflow-updated"));
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

  async function applyFilter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSelectionStatus("Applying metadata filter…");
    setProjectId("");
    setMetadataSelectionId("");
    setQuoteStatus("idle");
    setQuoteProgress(0);
    setQuoteRunId(null);
    try {
      const result = await postJson<ApiMetadataProject>("/api/metadata-filter", {
        exchange,
        name,
        instrument_type: instrumentType,
        country,
        currency,
      });
      setProjectId(result.project.project_id);
      setMetadataSelectionId(result.selection.selection_id);
      setSelectionStatus(`${result.selected_count.toLocaleString()} listings selected.`);
      setQuoteMessage("Selection ready. Fetch historical quotes to continue.");
      window.dispatchEvent(new Event("portfell:workflow-updated"));
    } catch (error) {
      setSelectionStatus(error instanceof Error ? error.message : "Metadata filter failed.");
    }
  }

  async function fetchQuotes() {
    if (!metadataSelectionId || quoteStatus === "running") return;
    setQuoteStatus("running");
    setQuoteProgress(0);
    setQuoteMessage("Fetching quotes and building the Silver dataset…");
    try {
      const result = await postJson<ApiQuoteFetch>("/api/quote-runs", {
        metadata_selection_id: metadataSelectionId,
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

  if (options.status === "loading" || options.status === "idle") {
    return <LoadingState label="Loading metadata options" />;
  }

  if (options.status === "error") {
    return (
      <EmptyState
        title="Metadata unavailable"
        description="Use the EODHD key field in the header and fetch all metadata first."
      />
    );
  }

  return (
    <section data-route="metadata-filter-page">
      <Panel title="Metadata Filter">
        <form className="metadata-filter-form" onSubmit={applyFilter}>
          <label>
            Exchange
            <select value={exchange} onChange={(event) => setExchange(event.target.value)}>
              <option value="">Any</option>
              {options.data.exchange.map((value) => <option key={value}>{value}</option>)}
            </select>
          </label>
          <label>
            Instrument type
            <select value={instrumentType} onChange={(event) => setInstrumentType(event.target.value)}>
              <option value="">Any</option>
              {options.data.instrument_type.map((value) => <option key={value}>{value}</option>)}
            </select>
          </label>
          <label>
            Country
            <select value={country} onChange={(event) => setCountry(event.target.value)}>
              <option value="">Any</option>
              {options.data.country.map((value) => <option key={value}>{value}</option>)}
            </select>
          </label>
          <label>
            Currency
            <select value={currency} onChange={(event) => setCurrency(event.target.value)}>
              <option value="">Any</option>
              {options.data.currency.map((value) => <option key={value}>{value}</option>)}
            </select>
          </label>
          <label className="metadata-filter-form__name">
            Name contains
            <input value={name} onChange={(event) => setName(event.target.value)} placeholder="UCITS ETF" />
          </label>
          <div className="metadata-filter-form__apply">
            <Button type="submit" variant="primary">Apply metadata filter</Button>
          </div>
        </form>
        <p className="status-line" aria-live="polite">{selectionStatus}</p>

        <div className="quote-fetch">
          <label htmlFor="quote-progress">Quote fetch progress</label>
          <progress
            id="quote-progress"
            max={100}
            value={quoteProgress}
          />
          <p className="status-line" aria-live="polite">{quoteMessage}</p>
          <div className="quote-fetch__action">
            <Button
              type="button"
              variant="primary"
              disabled={!projectId || !metadataSelectionId || quoteStatus === "running"}
              onClick={() => void fetchQuotes()}
            >
              {quoteStatus === "running" ? "Fetching quotes…" : "Fetch quotes"}
            </Button>
          </div>
        </div>
      </Panel>
    </section>
  );
}
