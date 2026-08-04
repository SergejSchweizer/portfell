
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { loadProjectContext, loadProjectWorkflow, postJson, selectCurrentProject } from "../api/client";
import { Button } from "../components/button";
import type { ApiMetadataFetch, ApiProjectContext, ApiWorkflow } from "../contracts";
import { useResource } from "../hooks/use-resource";
import { workflowPages, type WorkflowPageId } from "../routes";
import { ProjectSidebar } from "./project-sidebar";

export type ShellFrameProps = Readonly<{
  currentPage: WorkflowPageId;
  children: ReactNode;
}>;

const emptyWorkflow: ApiWorkflow = {
  stages: {
    metadata_filter: { status: "ready" },
    univariate_statistics: { status: "locked" },
    univariate_filter: { status: "locked" },
    bivariate_statistics: { status: "locked" },
  },
};

export function ShellFrame({ currentPage, children }: ShellFrameProps) {
  const [providerKey, setProviderKey] = useState("");
  const [fetching, setFetching] = useState(false);
  const [status, setStatus] = useState("Enter an EODHD key to refresh listing metadata.");
  const [contextRevision, setContextRevision] = useState(0);
  const [workflowRevision, setWorkflowRevision] = useState(0);
  const [switching, setSwitching] = useState(false);
  const [switchError, setSwitchError] = useState<string | null>(null);
  const context = useResource(loadProjectContext, [contextRevision]);
  const projectId = context.status === "ready" ? context.data.current_project_id : null;
  const workflow = useResource(
    () => projectId ? loadProjectWorkflow(projectId) : Promise.resolve(emptyWorkflow),
    [projectId, workflowRevision],
  );

  useEffect(() => {
    const refresh = () => {
      setContextRevision((value) => value + 1);
      setWorkflowRevision((value) => value + 1);
    };
    window.addEventListener("portfell:workflow-updated", refresh);
    return () => window.removeEventListener("portfell:workflow-updated", refresh);
  }, []);

  async function fetchMetadata(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!providerKey.trim() || fetching) return;
    setFetching(true);
    setStatus("Saving key and fetching metadata…");
    try {
      await postJson("/api/credentials/eodhd", { provider_key: providerKey.trim() });
      setProviderKey("");
      const result = await postJson<ApiMetadataFetch>(
        "/api/metadata/fetch-all",
        {},
      );
      setStatus(`${result.row_count.toLocaleString()} metadata rows from ${result.exchange_count} exchanges loaded.`);
      window.dispatchEvent(new Event("portfell:metadata-updated"));
      window.dispatchEvent(new Event("portfell:workflow-updated"));
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Metadata fetch failed.");
    } finally {
      setFetching(false);
    }
  }

  async function changeProject(nextProjectId: string) {
    if (!projectId || nextProjectId === projectId || switching) return;
    setSwitching(true);
    setSwitchError(null);
    try {
      const nextContext = await selectCurrentProject(nextProjectId);
      const nextWorkflow = await loadProjectWorkflow(nextProjectId);
      const target = workflowPages.find((page) => nextWorkflow.stages[page.id].status !== "locked") ?? workflowPages[0];
      window.dispatchEvent(new CustomEvent<ApiProjectContext>("portfell:project-updated", { detail: nextContext }));
      window.history.pushState({}, "", target.path);
      window.dispatchEvent(new Event("portfell:navigation"));
      setContextRevision((value) => value + 1);
      setWorkflowRevision((value) => value + 1);
    } catch (error) {
      setSwitchError(error instanceof Error ? error.message : "Project switch failed.");
    } finally {
      setSwitching(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <strong className="brand">Portfell</strong>
          <span className="brand-subtitle">Four-stage statistics workflow</span>
        </div>
        <form className="metadata-fetch" onSubmit={fetchMetadata}>
          <label>
            EODHD key
            <input
              type="password"
              autoComplete="off"
              value={providerKey}
              onChange={(event) => setProviderKey(event.target.value)}
              placeholder="Enter provider key"
            />
          </label>
          <Button type="submit" variant="primary" disabled={!providerKey.trim() || fetching}>
            {fetching ? "Fetching…" : "Fetch all metadata"}
          </Button>
          <output className="metadata-fetch__status" aria-live="polite">{status}</output>
        </form>
      </header>

      <div className="app-workspace">
        <ProjectSidebar
          currentPage={currentPage}
          context={context.status === "ready" ? context.data : null}
          workflow={workflow.status === "ready" ? workflow.data : null}
          loading={context.status === "idle" || context.status === "loading"}
          switching={switching}
          error={context.status === "error" ? context.error.message : switchError}
          onProjectChange={(nextProjectId) => void changeProject(nextProjectId)}
        />
        <main className="page-content">{children}</main>
      </div>
    </div>
  );
}
