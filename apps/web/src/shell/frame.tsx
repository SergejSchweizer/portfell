
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Menu } from "lucide-react";
import {
  loadProjectContext,
  loadProjectWorkflow,
  selectCurrentProject,
} from "../api/client";
import type { ApiProjectContext, ApiWorkflow } from "../contracts";
import { queryClient, queryTiming } from "../query/client";
import { queryKeys } from "../query/keys";
import { useQueryResource } from "../query/use-query-resource";
import { projectSlug, projectSlugFromPath, projectWorkflowPath, workflowPages, type WorkflowPageId } from "../routes";
import { MetadataFetchProvider, useMetadataFetch } from "./metadata-fetch-context";
import { ProjectSidebar } from "./project-sidebar";

export type ShellFrameProps = Readonly<{
  currentPage: WorkflowPageId;
  children: ReactNode;
}>;

const emptyWorkflow: ApiWorkflow = {
  stages: {
    metadata_builder: { status: "ready" },
    univariate_statistics: { status: "locked" },
    bivariate_statistics: { status: "locked" },
    multivariate_statistics: { status: "locked" },
  },
};

export function ShellFrame({ currentPage, children }: ShellFrameProps) {
  return (
    <MetadataFetchProvider>
      <ShellFrameContent currentPage={currentPage}>{children}</ShellFrameContent>
    </MetadataFetchProvider>
  );
}

function ShellFrameContent({ currentPage, children }: ShellFrameProps) {
  const [switching, setSwitching] = useState(false);
  const [switchError, setSwitchError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const {
    providerKey,
    setProviderKey,
    maskedCredentialLabel,
  } = useMetadataFetch();
  const context = useQueryResource(queryKeys.projectContext(), loadProjectContext, queryTiming.volatile);
  const projectId = context.status === "ready" ? context.data.current_project_id : null;
  const workflow = useQueryResource(
    queryKeys.workflow(projectId ?? undefined),
    () => projectId ? loadProjectWorkflow(projectId) : Promise.resolve(emptyWorkflow),
    queryTiming.volatile,
  );

  useEffect(() => {
    const refresh = () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.projectContext() });
      void queryClient.invalidateQueries({ queryKey: queryKeys.workflowRoot() });
    };
    window.addEventListener("portfell:workflow-updated", refresh);
    return () => window.removeEventListener("portfell:workflow-updated", refresh);
  }, []);

  useEffect(() => {
    if (!drawerOpen) return;
    const drawer = document.getElementById("project-navigation-drawer");
    if (!drawer) return;

    const priorOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusable = () => Array.from(drawer.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), select:not([disabled]), input:not([disabled])',
    ));
    const projectSelector = drawer.querySelector<HTMLSelectElement>("#current-project");
    const initialFocus = projectSelector?.disabled ? focusable()[0] : projectSelector ?? focusable()[0];
    initialFocus?.focus();

    function trapFocus(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setDrawerOpen(false);
        return;
      }
      if (event.key !== "Tab") return;
      const elements = focusable();
      const first = elements[0];
      const last = elements.at(-1);
      if (!first || !last) return;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", trapFocus);
    return () => {
      document.body.style.overflow = priorOverflow;
      document.removeEventListener("keydown", trapFocus);
      menuButtonRef.current?.focus();
    };
  }, [drawerOpen]);

  useEffect(() => {
    setDrawerOpen(false);
  }, [currentPage]);

  useEffect(() => {
    if (context.status !== "ready" || switching) return;
    const requestedProjectSlug = projectSlugFromPath(window.location.pathname);
    const requestedProject = context.data.projects.find((project) => projectSlug(project.name) === requestedProjectSlug);
    const currentProject = context.data.current_project;
    if (requestedProject && requestedProject.project_id !== currentProject?.project_id) {
      setSwitching(true);
      setSwitchError(null);
      void selectCurrentProject(requestedProject.project_id)
        .then((nextContext) => {
          window.dispatchEvent(new CustomEvent<ApiProjectContext>("portfell:project-updated", { detail: nextContext }));
          window.history.replaceState({}, "", projectWorkflowPath(requestedProject, workflowPages.find((page) => page.id === currentPage)!));
          queryClient.setQueryData(queryKeys.projectContext(), nextContext);
          void queryClient.invalidateQueries({ queryKey: queryKeys.workflow(requestedProject.project_id) });
        })
        .catch((error: unknown) => setSwitchError(error instanceof Error ? error.message : "Project switch failed."))
        .finally(() => setSwitching(false));
      return;
    }
    if (currentProject) {
      const canonicalPath = projectWorkflowPath(currentProject, workflowPages.find((page) => page.id === currentPage)!);
      if (window.location.pathname !== canonicalPath) window.history.replaceState({}, "", canonicalPath);
    }
  }, [context.status, context.status === "ready" ? context.data : null, currentPage, switching]);

  async function changeProject(nextProjectId: string): Promise<boolean> {
    if (!projectId || nextProjectId === projectId || switching) return false;
    setSwitching(true);
    setSwitchError(null);
    try {
      const nextContext = await selectCurrentProject(nextProjectId);
      const nextWorkflow = await loadProjectWorkflow(nextProjectId);
      const target = nextWorkflow.stages.univariate_statistics.status !== "locked"
        ? workflowPages.find((page) => page.id === "univariate_statistics")!
        : workflowPages[0];
      const nextProject = nextContext.projects.find((project) => project.project_id === nextProjectId);
      if (!nextProject) throw new Error("Selected project is unavailable.");
      window.dispatchEvent(new CustomEvent<ApiProjectContext>("portfell:project-updated", { detail: nextContext }));
      window.history.pushState({}, "", projectWorkflowPath(nextProject, target));
      window.dispatchEvent(new Event("portfell:navigation"));
      queryClient.setQueryData(queryKeys.projectContext(), nextContext);
      queryClient.setQueryData(queryKeys.workflow(nextProjectId), nextWorkflow);
      return true;
    } catch (error) {
      setSwitchError(error instanceof Error ? error.message : "Project switch failed.");
      return false;
    } finally {
      setSwitching(false);
    }
  }

  function changeWorkflowPage(path: string) {
    window.history.pushState({}, "", path);
    window.dispatchEvent(new Event("portfell:navigation"));
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <strong className="brand">Portfell</strong>
          <span className="brand-subtitle">Portfolio Research Engine</span>
          <div className="process-overview" aria-label="Process overview">
            <div className="process-overview__step" data-complete={workflow.status === "ready" && workflow.data.process_overview?.metadata_downloaded_isins ? "true" : "false"}>
              <small>1 · Metadata download</small>
              <strong>{workflow.status === "ready" ? workflow.data.process_overview?.metadata_downloaded_isins.toLocaleString() ?? "—" : "—"} ISINs</strong>
            </div>
            <span className="process-overview__arrow" aria-hidden="true">→</span>
            <div className="process-overview__step" data-complete={workflow.status === "ready" && workflow.data.process_overview?.metadata_builder_isins !== undefined ? "true" : "false"}>
              <small>2 · Metadata Builder</small>
              <strong>{workflow.status === "ready" && workflow.data.process_overview?.metadata_builder_isins !== undefined ? workflow.data.process_overview.metadata_builder_isins.toLocaleString() : "—"} ISINs</strong>
            </div>
            <span className="process-overview__arrow" aria-hidden="true">→</span>
            <div className="process-overview__step" data-complete={workflow.status === "ready" && workflow.data.process_overview?.univariate_statistics_isins != null ? "true" : "false"}>
              <small>3 · Univariate statistics</small>
              <strong>{workflow.status === "ready" && workflow.data.process_overview?.univariate_statistics_isins != null ? workflow.data.process_overview.univariate_statistics_isins.toLocaleString() : "—"} ISINs</strong>
            </div>
            <span className="process-overview__arrow" aria-hidden="true">→</span>
            <div className="process-overview__step" data-complete="false">
              <small>4 · Bivariate statistics</small>
              <strong>—</strong>
            </div>
            <span className="process-overview__arrow" aria-hidden="true">→</span>
            <div className="process-overview__step" data-complete="false">
              <small>5 · Multivariate statistics</small>
              <strong>—</strong>
            </div>
          </div>
        </div>
        <label className="app-header__project" htmlFor="compact-current-project">
          Current project
          <select
            id="compact-current-project"
            aria-label="Current project"
            value={projectId ?? ""}
            disabled={context.status !== "ready" || switching || context.data.projects.length === 0}
            onChange={(event) => void changeProject(event.target.value)}
          >
            {context.status === "ready" && context.data.projects.length === 0 ? <option value="">No projects yet</option> : null}
            {context.status === "ready" ? context.data.projects.map((project) => (
              <option key={project.project_id} value={project.project_id}>{project.name}</option>
            )) : null}
          </select>
        </label>
        <div className="app-header__metadata">
          <div className="metadata-fetch__credential-input">
            <label>
              EODHD key
              <input
                type="password"
                autoComplete="off"
                value={providerKey}
                onChange={(event) => setProviderKey(event.target.value)}
                placeholder={maskedCredentialLabel ? `Encrypted key: ${maskedCredentialLabel}` : "Enter provider key"}
              />
            </label>
            {maskedCredentialLabel ? <span className="metadata-fetch__credential">Encrypted: {maskedCredentialLabel}</span> : null}
          </div>
        </div>
        <button
          ref={menuButtonRef}
          className="project-navigation-toggle"
          type="button"
          aria-label="Open project navigation"
          aria-expanded={drawerOpen}
          aria-controls="project-navigation-drawer"
          onClick={() => setDrawerOpen(true)}
        >
          <Menu aria-hidden="true" />
        </button>
      </header>

      <div className="app-workspace">
        {drawerOpen ? <button className="project-navigation-backdrop" type="button" aria-label="Close project navigation" tabIndex={-1} onClick={() => setDrawerOpen(false)} /> : null}
        <ProjectSidebar
          currentPage={currentPage}
          context={context.status === "ready" ? context.data : null}
          workflow={workflow.status === "ready" ? workflow.data : null}
          loading={context.status === "idle" || context.status === "loading"}
          switching={switching}
          error={context.status === "error" ? context.error.message : switchError}
          drawerOpen={drawerOpen}
          onCloseDrawer={() => setDrawerOpen(false)}
          onProjectChange={changeProject}
          onWorkflowPageChange={changeWorkflowPage}
        />
        <main className="page-content">{children}</main>
      </div>
    </div>
  );
}
