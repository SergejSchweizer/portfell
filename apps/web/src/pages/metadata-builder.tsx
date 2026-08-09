
import { useEffect, useState, type FormEvent } from "react";
import { loadProjectContext } from "../api/client";
import { metadataBuilderApi } from "../api/metadata-builder";
import { Button } from "../components/button";
import { EmptyState } from "../components/empty-state";
import { LoadingState } from "../components/loading-state";
import { Panel } from "../components/panel";
import type { ApiProjectSummary } from "../contracts";
import { useResource } from "../hooks/use-resource";
import { useMetadataFetch } from "../shell/metadata-fetch-context";

export function MetadataBuilderPage() {
  const [metadataRevision, setMetadataRevision] = useState(0);
  const options = useResource(metadataBuilderApi.loadFieldOptions, [metadataRevision]);
  const { fetchMetadata, fetching, hasSavedCredential, metadataProgress, metadataStatus, providerKey } = useMetadataFetch();
  const [exchange, setExchange] = useState("");
  const [instrumentType, setInstrumentType] = useState("");
  const [country, setCountry] = useState("");
  const [currency, setCurrency] = useState("");
  const [name, setName] = useState("");
  const [selectionStatus, setSelectionStatus] = useState("Choose at least one Metadata Builder criterion.");

  useEffect(() => {
    const refresh = () => setMetadataRevision((value) => value + 1);
    window.addEventListener("portfell:metadata-updated", refresh);
    return () => window.removeEventListener("portfell:metadata-updated", refresh);
  }, []);

  useEffect(() => {
    let cancelled = false;

    const resetProjectState = () => {
      setSelectionStatus("Choose at least one Metadata Builder criterion.");
    };

    const loadProjectCriteria = async (project: ApiProjectSummary | null) => {
      if (!project?.selection_id) {
        resetProjectState();
        return;
      }
      setSelectionStatus("Loading saved Metadata Builder criteria…");
      try {
        const criteria = await metadataBuilderApi.loadProjectCriteria(project.project_id);
        if (cancelled) return;
        setExchange(criteria.exchange);
        setInstrumentType(criteria.instrument_type);
        setCountry(criteria.country);
        setCurrency(criteria.currency);
        setName(criteria.name);
        setSelectionStatus(`${criteria.selected_count.toLocaleString()} unique ISINs selected.`);
      } catch (error) {
        if (cancelled) return;
        resetProjectState();
        setSelectionStatus(error instanceof Error ? error.message : "Saved Metadata Builder criteria could not be loaded.");
      }
    };

    const restoreCurrentProject = () => {
      void loadProjectContext().then((context) => loadProjectCriteria(context.current_project));
    };
    const handleProjectUpdate = (event: Event) => {
      const context = (event as CustomEvent<{ current_project: ApiProjectSummary | null }>).detail;
      void loadProjectCriteria(context.current_project);
    };

    restoreCurrentProject();
    window.addEventListener("portfell:project-updated", handleProjectUpdate);
    return () => {
      cancelled = true;
      window.removeEventListener("portfell:project-updated", handleProjectUpdate);
    };
  }, []);

  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSelectionStatus("Building the project selection…");
    try {
      const result = await metadataBuilderApi.createProject({
        exchange,
        name,
        instrument_type: instrumentType,
        country,
        currency,
      });
      setSelectionStatus(`${result.selected_count.toLocaleString()} unique ISINs selected.`);
      window.dispatchEvent(new Event("portfell:workflow-updated"));
    } catch (error) {
      setSelectionStatus(error instanceof Error ? error.message : "Metadata Builder could not create the project.");
    }
  }

  if (options.status === "loading" || options.status === "idle") {
    return <LoadingState label="Loading metadata options" />;
  }

  if (options.status === "error") {
    return (
      <EmptyState
        title="Metadata unavailable"
        description="Enter an EODHD key in the header and fetch all metadata first."
      />
    );
  }

  return (
    <section className="metadata-builder-page" data-route="metadata-builder-page">
      <Panel title="Download Metadata">
        <div className="quote-fetch quote-fetch--panel metadata-download">
          <label htmlFor="metadata-progress">Metadata download progress</label>
          <progress id="metadata-progress" max={100} value={metadataProgress} />
          <output className="status-line" aria-live="polite">{metadataStatus}</output>
          <div className="quote-fetch__action">
          <Button type="button" variant="primary" disabled={(!providerKey.trim() && !hasSavedCredential) || fetching} onClick={() => void fetchMetadata()}>
            {fetching ? "Fetching…" : "Fetch all metadata"}
          </Button>
          </div>
        </div>
      </Panel>
      <Panel title="Metadata Builder">
        <form className="metadata-builder-form" onSubmit={createProject}>
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
          <label className="metadata-builder-form__name">
            Name contains
            <input value={name} onChange={(event) => setName(event.target.value)} placeholder="UCITS ETF" />
          </label>
          <div className="metadata-builder-form__apply">
            <Button type="submit" variant="primary">Create new project</Button>
          </div>
        </form>
        <p className="status-line" aria-live="polite">{selectionStatus}</p>
      </Panel>
    </section>
  );
}
