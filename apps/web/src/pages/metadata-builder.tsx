
import { useEffect, useState, type FormEvent } from "react";
import { loadProjectContext } from "../api/client";
import { metadataBuilderApi } from "../api/metadata-builder";
import { Button } from "../components/button";
import { EmptyState } from "../components/empty-state";
import { LoadingIndicator, LoadingState } from "../components/loading-state";
import { Panel } from "../components/panel";
import type { ApiInitialFill, ApiProjectSummary } from "../contracts";
import { useResource } from "../hooks/use-resource";
import { projectWorkflowPath, workflowPages } from "../routes";
import { useMetadataFetch } from "../shell/metadata-fetch-context";

export function MetadataBuilderPage() {
  const [metadataRevision, setMetadataRevision] = useState(0);
  const options = useResource(metadataBuilderApi.loadFieldOptions, [metadataRevision]);
  const { fetchMetadata, fetching, canFetchMetadata, metadataProgress, metadataStatus } = useMetadataFetch();
  const [exchange, setExchange] = useState("");
  const [instrumentType, setInstrumentType] = useState("");
  const [country, setCountry] = useState("");
  const [currency, setCurrency] = useState("");
  const [name, setName] = useState("");
  const [selectionStatus, setSelectionStatus] = useState("Choose at least one Metadata Builder criterion.");
  const [initialFill, setInitialFill] = useState<ApiInitialFill | null>(null);
  const [creatingProject, setCreatingProject] = useState(false);

  useEffect(() => {
    const refresh = () => setMetadataRevision((value) => value + 1);
    window.addEventListener("portfell:metadata-updated", refresh);
    return () => window.removeEventListener("portfell:metadata-updated", refresh);
  }, []);

  useEffect(() => {
    let cancelled = false;

    const resetProjectState = () => {
      setSelectionStatus("Choose at least one Metadata Builder criterion.");
      setInitialFill(null);
      setCreatingProject(false);
    };

    const loadProjectCriteria = async (project: ApiProjectSummary | null) => {
      if (!project) {
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
        try {
          const fill = await metadataBuilderApi.loadInitialFill(project.project_id);
          if (cancelled) return;
          setInitialFill(fill);
        } catch (error) {
          if (!cancelled) {
            setSelectionStatus(error instanceof Error ? error.message : "Initial historical-data status could not be loaded.");
          }
        }
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

  useEffect(() => {
    if (!initialFill || !["planning", "running"].includes(initialFill.status)) return;
    let cancelled = false;
    let timeoutId: number | undefined;

    const poll = async () => {
      try {
        const context = await loadProjectContext();
        if (!context.current_project) return;
        const nextFill = await metadataBuilderApi.loadInitialFill(context.current_project.project_id);
        if (cancelled) return;
        setInitialFill(nextFill);
        if (["planning", "running"].includes(nextFill.status)) {
          timeoutId = window.setTimeout(() => void poll(), 750);
        } else {
          window.dispatchEvent(new Event("portfell:workflow-updated"));
        }
      } catch (error) {
        if (!cancelled) {
          setSelectionStatus(error instanceof Error ? error.message : "Initial historical-data status could not be loaded.");
        }
      }
    };

    void poll();
    return () => {
      cancelled = true;
      if (timeoutId !== undefined) window.clearTimeout(timeoutId);
    };
  }, [initialFill]);

  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (creatingProject || initialFillIsActive(initialFill)) return;
    setCreatingProject(true);
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
      setInitialFill(result.initial_fill ?? null);
      window.history.pushState({}, "", projectWorkflowPath(result.project, workflowPages[0]));
      window.dispatchEvent(new Event("portfell:navigation"));
      window.dispatchEvent(new Event("portfell:workflow-updated"));
    } catch (error) {
      setSelectionStatus(error instanceof Error ? error.message : "Metadata Builder could not create the project.");
    } finally {
      setCreatingProject(false);
    }
  }

  if (options.status === "loading" || options.status === "idle") {
    return <LoadingState label="Loading metadata options" />;
  }

  if (options.status === "error") {
    return (
      <EmptyState
        title="Metadata unavailable"
        description="Fetch all metadata to load the shared catalogue first."
      />
    );
  }

  return (
    <section className="metadata-builder-page" data-route="metadata-builder-page">
      {options.refreshing ? <LoadingIndicator label="Refreshing metadata options" compact /> : null}
      <Panel title="Download Metadata">
        <div className="quote-fetch quote-fetch--panel metadata-download">
          <label htmlFor="metadata-progress">Metadata download progress</label>
          <progress id="metadata-progress" max={100} value={metadataProgress} />
          <output className="status-line" aria-live="polite">{metadataStatus}</output>
          <div className="quote-fetch__action">
          <Button type="button" variant="primary" disabled={fetching || !canFetchMetadata} onClick={() => void fetchMetadata()}>
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
              {options.data.exchange.map((option) => <option key={option.value} value={option.value}>{fieldOptionLabel(option.value, option.isin_count)}</option>)}
            </select>
          </label>
          <label>
            Instrument type
            <select value={instrumentType} onChange={(event) => setInstrumentType(event.target.value)}>
              <option value="">Any</option>
              {options.data.instrument_type.map((option) => <option key={option.value} value={option.value}>{fieldOptionLabel(option.value, option.isin_count)}</option>)}
            </select>
          </label>
          <label>
            Country
            <select value={country} onChange={(event) => setCountry(event.target.value)}>
              <option value="">Any</option>
              {options.data.country.map((option) => <option key={option.value} value={option.value}>{fieldOptionLabel(option.value, option.isin_count)}</option>)}
            </select>
          </label>
          <label>
            Currency
            <select value={currency} onChange={(event) => setCurrency(event.target.value)}>
              <option value="">Any</option>
              {options.data.currency.map((option) => <option key={option.value} value={option.value}>{fieldOptionLabel(option.value, option.isin_count)}</option>)}
            </select>
          </label>
          <label className="metadata-builder-form__name">
            Name contains
            <input value={name} onChange={(event) => setName(event.target.value)} placeholder="UCITS ETF" />
          </label>
          <div className="metadata-builder-form__apply">
            <Button
              type="submit"
              variant="primary"
              disabled={!options.data.metadata_ready || creatingProject || initialFillIsActive(initialFill)}
              aria-busy={creatingProject || initialFillIsActive(initialFill)}
              aria-live="polite"
            >
              {creatingProject ? "Creating project..." : initialFillButtonLabel(initialFill)}
            </Button>
          </div>
        </form>
        <p className="status-line" aria-live="polite">
          {options.data.metadata_ready
            ? initialFillStatusMessage(selectionStatus, initialFill)
            : "Download metadata successfully before building a project."}
        </p>
      </Panel>
    </section>
  );
}

function fieldOptionLabel(value: string, isinCount: number): string {
  return `${value} (${isinCount.toLocaleString()} ${isinCount === 1 ? "ISIN" : "ISINs"})`;
}

function initialFillIsActive(fill: ApiInitialFill | null): boolean {
  return fill !== null && ["not_started", "planning", "running"].includes(fill.status);
}

function initialFillButtonLabel(fill: ApiInitialFill | null): string {
  if (fill === null) return "Create new project";
  if (fill.status === "not_started" || fill.status === "planning") {
    return "Preparing historical data...";
  }
  if (fill.status === "running") {
    return `Loading quotes: ${fill.completed_units.toLocaleString()} / ${fill.total_units.toLocaleString()}${initialFillRemainingTime(fill)}`;
  }
  if (fill.status === "ready") return "Quotes ready - Create new project";
  if (fill.status === "partial") return "Quotes partially loaded - Create new project";
  return "Quote load failed - Retry quote load";
}

export function initialFillStatusMessage(selectionStatus: string, fill: ApiInitialFill | null): string {
  if (fill === null || !["partial", "failed"].includes(fill.status)) return selectionStatus;
  const failedIsins = `${fill.failed_listing_count.toLocaleString()} ${fill.failed_listing_count === 1 ? "ISIN" : "ISINs"}`;
  return `${selectionStatus} ${failedIsins} failed to load.`;
}

function initialFillRemainingTime(fill: ApiInitialFill): string {
  if (fill.started_at === null || fill.completed_units <= 0 || fill.total_units <= fill.completed_units) {
    return " - estimating time...";
  }
  if (fill.last_progress_at !== null && Date.now() - fill.last_progress_at * 1_000 > 60_000) {
    return " - waiting for provider progress...";
  }
  const elapsedSeconds = (Date.now() - fill.started_at * 1_000) / 1_000;
  if (elapsedSeconds <= 0) return " - estimating time...";
  const remainingSeconds = Math.ceil((elapsedSeconds / fill.completed_units) * (fill.total_units - fill.completed_units));
  if (remainingSeconds < 60) return " - less than 1 min remaining";
  const hours = Math.floor(remainingSeconds / 3_600);
  const minutes = Math.ceil((remainingSeconds % 3_600) / 60);
  return hours > 0 ? ` - about ${hours}h ${minutes}m remaining` : ` - about ${minutes} min remaining`;
}
