
import { useEffect, useState, type FormEvent } from "react";
import {
  loadEodhdCredentialStatus,
  loadEodhdCredentialValue,
  loadMetadataFetchRun,
  loadProjectContext,
  loadProjectMetadataFilter,
  postJson,
  requestJson,
} from "../api/client";
import { Button } from "../components/button";
import { EmptyState } from "../components/empty-state";
import { LoadingState } from "../components/loading-state";
import { Panel } from "../components/panel";
import type { ApiFieldOptions, ApiMetadataFetch, ApiMetadataProject, ApiProjectSummary } from "../contracts";
import { useResource } from "../hooks/use-resource";

async function loadFieldOptions(): Promise<ApiFieldOptions> {
  return requestJson<ApiFieldOptions>("/api/metadata-filter/options");
}

export function MetadataFilterPage() {
  const [metadataRevision, setMetadataRevision] = useState(0);
  const options = useResource(loadFieldOptions, [metadataRevision]);
  const credential = useResource(loadEodhdCredentialStatus, []);
  const savedProviderKey = useResource(loadEodhdCredentialValue, []);
  const [providerKey, setProviderKey] = useState("");
  const [fetching, setFetching] = useState(false);
  const [metadataRunId, setMetadataRunId] = useState<string | null>(null);
  const [metadataProgress, setMetadataProgress] = useState(0);
  const [metadataStatus, setMetadataStatus] = useState("Enter an EODHD key to refresh listing metadata.");
  const [exchange, setExchange] = useState("");
  const [instrumentType, setInstrumentType] = useState("");
  const [country, setCountry] = useState("");
  const [currency, setCurrency] = useState("");
  const [name, setName] = useState("");
  const [selectionStatus, setSelectionStatus] = useState("Choose at least one metadata filter.");
  const hasSavedCredential = credential.status === "ready" && credential.data.status === "active";

  useEffect(() => {
    const refresh = () => setMetadataRevision((value) => value + 1);
    window.addEventListener("portfell:metadata-updated", refresh);
    return () => window.removeEventListener("portfell:metadata-updated", refresh);
  }, []);

  useEffect(() => {
    if (savedProviderKey.status === "ready") setProviderKey(savedProviderKey.data.provider_key);
  }, [savedProviderKey.status]);

  useEffect(() => {
    if (!metadataRunId || !fetching) return;
    const activeRunId = metadataRunId;
    let cancelled = false;
    let timeoutId: number | undefined;

    async function pollMetadataRun() {
      try {
        const result = await loadMetadataFetchRun(activeRunId);
        if (cancelled) return;
        setMetadataProgress(result.percent);
        if (result.status === "running") {
          setMetadataStatus(`Fetching metadata: ${result.completed.toLocaleString()} of ${result.total.toLocaleString()} exchanges completed.`);
          timeoutId = window.setTimeout(() => void pollMetadataRun(), 750);
          return;
        }
        setFetching(false);
        setMetadataRunId(null);
        if (result.status === "failed") {
          setMetadataStatus(result.error_code ?? "Metadata fetch failed.");
          return;
        }
        setMetadataStatus(`${(result.row_count ?? 0).toLocaleString()} metadata rows from ${result.exchange_count ?? 0} exchanges loaded.`);
        window.dispatchEvent(new Event("portfell:metadata-updated"));
        window.dispatchEvent(new Event("portfell:workflow-updated"));
      } catch (error) {
        if (cancelled) return;
        setFetching(false);
        setMetadataRunId(null);
        setMetadataStatus(error instanceof Error ? error.message : "Metadata fetch failed.");
      }
    }

    void pollMetadataRun();
    return () => {
      cancelled = true;
      if (timeoutId !== undefined) window.clearTimeout(timeoutId);
    };
  }, [fetching, metadataRunId]);

  useEffect(() => {
    let cancelled = false;

    const resetProjectState = () => {
      setSelectionStatus("Choose at least one metadata filter.");
    };

    const loadProjectFilter = async (project: ApiProjectSummary | null) => {
      if (!project?.selection_id) {
        resetProjectState();
        return;
      }
      setSelectionStatus("Loading saved metadata filter…");
      try {
        const filter = await loadProjectMetadataFilter(project.project_id);
        if (cancelled) return;
        setExchange(filter.exchange);
        setInstrumentType(filter.instrument_type);
        setCountry(filter.country);
        setCurrency(filter.currency);
        setName(filter.name);
        setSelectionStatus(`${filter.selected_count.toLocaleString()} listings selected.`);
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

  async function fetchMetadata(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if ((!providerKey.trim() && !hasSavedCredential) || fetching) return;
    setFetching(true);
    setMetadataProgress(0);
    setMetadataStatus(providerKey.trim() ? "Saving key and fetching metadata..." : "Fetching metadata...");
    try {
      if (providerKey.trim()) await postJson("/api/credentials/eodhd", { provider_key: providerKey.trim() });
      const result = await postJson<ApiMetadataFetch>("/api/metadata/fetch-all", {});
      setMetadataRunId(result.metadata_run_id);
      setMetadataProgress(result.percent);
    } catch (error) {
      setMetadataStatus(error instanceof Error ? error.message : "Metadata fetch failed.");
      setFetching(false);
    }
  }

  async function applyFilter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSelectionStatus("Applying metadata filter…");
    try {
      const result = await postJson<ApiMetadataProject>("/api/metadata-filter", {
        exchange,
        name,
        instrument_type: instrumentType,
        country,
        currency,
      });
      setSelectionStatus(`${result.selected_count.toLocaleString()} listings selected.`);
      window.dispatchEvent(new Event("portfell:workflow-updated"));
      window.history.pushState({}, "", "/univariate-statistics");
      window.dispatchEvent(new Event("portfell:navigation"));
    } catch (error) {
      setSelectionStatus(error instanceof Error ? error.message : "Metadata filter failed.");
    }
  }

  if (options.status === "loading" || options.status === "idle") {
    return <LoadingState label="Loading metadata options" />;
  }

  if (options.status === "error") {
    return (
      <EmptyState
        title="Metadata unavailable"
        description="Use the EODHD key field above and fetch all metadata first."
      />
    );
  }

  return (
    <section className="metadata-filter-page" data-route="metadata-filter-page">
      <Panel title="Refresh Listing Metadata">
        <form className="metadata-fetch metadata-fetch--page" onSubmit={fetchMetadata}>
          <div className="metadata-fetch__credential-input">
            <label>
              EODHD key
              <input type="text" autoComplete="off" value={providerKey} onChange={(event) => setProviderKey(event.target.value)} placeholder="Enter provider key" />
            </label>
            {fetching ? <progress className="metadata-fetch__progress" max={100} value={metadataProgress} aria-label={`Fetching metadata: ${metadataProgress}%`} /> : null}
            {hasSavedCredential ? <span className="metadata-fetch__credential">Saved: {credential.data.masked_label}</span> : null}
          </div>
          <Button type="submit" variant="primary" disabled={(!providerKey.trim() && !hasSavedCredential) || fetching}>
            {fetching ? "Fetching…" : "Fetch all metadata"}
          </Button>
          <output className="metadata-fetch__status" aria-live="polite">{metadataStatus}</output>
        </form>
      </Panel>
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
      </Panel>
    </section>
  );
}
