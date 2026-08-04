
import { useEffect, useState, type FormEvent } from "react";
import { postJson, requestJson } from "../api/client";
import { Button } from "../components/button";
import { EmptyState } from "../components/empty-state";
import { LoadingState } from "../components/loading-state";
import { Panel } from "../components/panel";
import type { ApiFieldOptions, ApiMetadataProject, ApiQuoteFetch } from "../contracts";
import { useResource } from "../hooks/use-resource";

async function loadFieldOptions(): Promise<ApiFieldOptions> {
  return requestJson<ApiFieldOptions>("/api/metadata-filter/options");
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
  const [selectionStatus, setSelectionStatus] = useState("Choose at least one metadata filter.");
  const [quoteStatus, setQuoteStatus] = useState<"idle" | "running" | "complete" | "failed">("idle");
  const [quoteProgress, setQuoteProgress] = useState(0);
  const [quoteMessage, setQuoteMessage] = useState("Quotes have not been fetched for this selection.");

  useEffect(() => {
    const refresh = () => setMetadataRevision((value) => value + 1);
    window.addEventListener("portfell:metadata-updated", refresh);
    return () => window.removeEventListener("portfell:metadata-updated", refresh);
  }, []);

  async function applyFilter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSelectionStatus("Applying metadata filter…");
    setProjectId("");
    setQuoteStatus("idle");
    setQuoteProgress(0);
    try {
      const result = await postJson<ApiMetadataProject>("/api/metadata-filter/projects", {
        exchange,
        name,
        instrument_type: instrumentType,
        country,
        currency,
      });
      setProjectId(result.project.project_id);
      setSelectionStatus(`${result.selected_count.toLocaleString()} listings selected.`);
      setQuoteMessage("Selection ready. Fetch historical quotes to continue.");
    } catch (error) {
      setSelectionStatus(error instanceof Error ? error.message : "Metadata filter failed.");
    }
  }

  async function fetchQuotes() {
    if (!projectId || quoteStatus === "running") return;
    setQuoteStatus("running");
    setQuoteProgress(0);
    setQuoteMessage("Fetching quotes and building the Silver dataset…");
    try {
      const result = await postJson<ApiQuoteFetch>("/api/data/load-selected-isins", {
        project_id: projectId,
      });
      setQuoteProgress(100);
      setQuoteStatus("complete");
      setQuoteMessage(
        `${(result.quote_successes ?? result.selected_listing_count ?? 0).toLocaleString()} listings fetched; ${(result.quote_errors ?? 0).toLocaleString()} failed.`,
      );
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
            value={quoteStatus === "running" ? undefined : quoteProgress}
          />
          <p className="status-line" aria-live="polite">{quoteMessage}</p>
          <div className="quote-fetch__action">
            <Button
              type="button"
              variant="primary"
              disabled={!projectId || quoteStatus === "running"}
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
