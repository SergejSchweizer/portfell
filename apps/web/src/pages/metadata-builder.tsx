
import { useEffect, useState, type FormEvent } from "react";
import { loadProjectContext } from "../api/client";
import { metadataBuilderApi } from "../api/metadata-builder";
import { Button } from "../components/button";
import { EmptyState } from "../components/empty-state";
import { LoadingIndicator, LoadingState } from "../components/loading-state";
import { Panel } from "../components/panel";
import type { ApiProjectSummary } from "../contracts";
import { queryClient, queryTiming } from "../query/client";
import { queryKeys } from "../query/keys";
import { useQueryResource } from "../query/use-query-resource";
import { projectWorkflowPath, workflowPages } from "../routes";

export function MetadataBuilderPage() {
  const options = useQueryResource(
    queryKeys.metadataOptions(),
    metadataBuilderApi.loadFieldOptions,
    queryTiming.completed,
  );
  const [exchange, setExchange] = useState("");
  const [instrumentType, setInstrumentType] = useState("");
  const [country, setCountry] = useState("");
  const [currency, setCurrency] = useState("");
  const [name, setName] = useState("");
  const [selectionStatus, setSelectionStatus] = useState("Choose at least one Metadata Builder criterion.");
  const [creatingProject, setCreatingProject] = useState(false);

  useEffect(() => {
    const refresh = () => { void queryClient.invalidateQueries({ queryKey: queryKeys.metadataOptions() }); };
    window.addEventListener("portfell:metadata-updated", refresh);
    return () => window.removeEventListener("portfell:metadata-updated", refresh);
  }, []);

  useEffect(() => {
    let cancelled = false;

    const resetProjectState = () => {
      setSelectionStatus("Choose at least one Metadata Builder criterion.");
      setCreatingProject(false);
    };

    const loadProjectCriteria = async (project: ApiProjectSummary | null) => {
      if (!project) {
        resetProjectState();
        return;
      }
      setSelectionStatus("Loading saved Metadata Builder criteria…");
      try {
        const pageView = await queryClient.fetchQuery({
          queryKey: queryKeys.pageView(project.project_id, "metadata_builder"),
          queryFn: ({ signal }) => metadataBuilderApi.loadPageView(project.project_id, signal),
          staleTime: queryTiming.volatile,
        });
        if (cancelled) return;
        const criteria = pageView.summary.criteria;
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
    if (creatingProject) return;
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
      window.history.pushState({}, "", projectWorkflowPath(result.project, workflowPages[0]));
      window.dispatchEvent(new Event("portfell:navigation"));
      window.dispatchEvent(new Event("portfell:workflow-updated"));
    } catch (error) {
      setSelectionStatus(error instanceof Error ? error.message : "Metadata Builder could not create the project.");
    } finally {
      setCreatingProject(false);
    }
  }

  if (options.status !== "ready") {
    return options.status === "error" ? (
      <EmptyState
        title="Metadata unavailable"
        description="The server-side market catalogue is not available."
      />
    ) : <LoadingState label="Loading metadata options" />;
  }
  const optionData = options.data;

  return (
    <section className="metadata-builder-page" data-route="metadata-builder-page">
      {options.refreshing ? <LoadingIndicator label="Refreshing metadata options" compact /> : null}
      <Panel title="Metadata Builder">
        <form className="metadata-builder-form" onSubmit={createProject}>
          <label>
            Exchange
            <select value={exchange} onChange={(event) => setExchange(event.target.value)}>
              <option value="">Any</option>
              {optionData.exchange.map((option) => <option key={option.value} value={option.value}>{fieldOptionLabel(option.value, option.isin_count)}</option>)}
            </select>
          </label>
          <label>
            Instrument type
            <select value={instrumentType} onChange={(event) => setInstrumentType(event.target.value)}>
              <option value="">Any</option>
              {optionData.instrument_type.map((option) => <option key={option.value} value={option.value}>{fieldOptionLabel(option.value, option.isin_count)}</option>)}
            </select>
          </label>
          <label>
            Country
            <select value={country} onChange={(event) => setCountry(event.target.value)}>
              <option value="">Any</option>
              {optionData.country.map((option) => <option key={option.value} value={option.value}>{fieldOptionLabel(option.value, option.isin_count)}</option>)}
            </select>
          </label>
          <label>
            Currency
            <select value={currency} onChange={(event) => setCurrency(event.target.value)}>
              <option value="">Any</option>
              {optionData.currency.map((option) => <option key={option.value} value={option.value}>{fieldOptionLabel(option.value, option.isin_count)}</option>)}
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
              disabled={!optionData.metadata_ready || creatingProject}
              aria-busy={creatingProject}
              aria-live="polite"
            >
              {creatingProject ? "Creating project..." : "Create new project"}
            </Button>
          </div>
        </form>
        <p className="status-line" aria-live="polite">
          {optionData.metadata_ready
            ? selectionStatus
            : "The server-side market catalogue is not available."}
        </p>
      </Panel>
    </section>
  );
}

function fieldOptionLabel(value: string, isinCount: number): string {
  return `${value} (${isinCount.toLocaleString()} ${isinCount === 1 ? "ISIN" : "ISINs"})`;
}
