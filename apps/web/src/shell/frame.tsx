
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Menu } from "lucide-react";
import { loadProjectContext, loadProjectWorkflow } from "../api/client";
import { bivariateStatisticsApi } from "../api/bivariate-statistics";
import { metadataBuilderApi } from "../api/metadata-builder";
import { multivariateStatisticsApi } from "../api/multivariate-statistics";
import { univariateStatisticsApi } from "../api/univariate-statistics";
import type { ApiWorkflow } from "../contracts";
import { queryClient, queryTiming } from "../query/client";
import { queryKeys } from "../query/keys";
import { useQueryResource } from "../query/use-query-resource";
import { workflowPages, type WorkflowPageId } from "../routes";
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
  const [drawerOpen, setDrawerOpen] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const context = useQueryResource(queryKeys.projectContext(), loadProjectContext, queryTiming.volatile);
  const projectId = context.status === "ready" ? context.data.current_project_id : null;
  const workflow = useQueryResource(
    queryKeys.workflow(projectId ?? undefined),
    (signal) => projectId ? loadProjectWorkflow(projectId, signal) : Promise.resolve(emptyWorkflow),
    queryTiming.volatile,
  );

  useEffect(() => {
    const refreshWorkflow = () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.workflowRoot() });
    };
    const refreshProjectContext = () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.projectContext() });
      void queryClient.invalidateQueries({ queryKey: queryKeys.workflowRoot() });
    };
    window.addEventListener("portfell:workflow-updated", refreshWorkflow);
    window.addEventListener("portfell:project-updated", refreshProjectContext);
    return () => {
      window.removeEventListener("portfell:workflow-updated", refreshWorkflow);
      window.removeEventListener("portfell:project-updated", refreshProjectContext);
    };
  }, []);

  useEffect(() => {
    if (!drawerOpen) return;
    const drawer = document.getElementById("project-navigation-drawer");
    if (!drawer) return;

    const priorOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusable = () => Array.from(drawer.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled])',
    ));
    focusable()[0]?.focus();

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

  function changeWorkflowPage(path: string) {
    window.history.pushState({}, "", path);
    window.dispatchEvent(new Event("portfell:navigation"));
  }

  function prefetchWorkflowPage(pageId: WorkflowPageId): void {
    if (!projectId) return;
    const queryKey = queryKeys.pageView(projectId, pageId);
    const queryFn: (context: Readonly<{ signal: AbortSignal }>) => Promise<unknown> = ({ signal }) => {
      if (pageId === "metadata_builder") return metadataBuilderApi.loadPageView(projectId, signal);
      if (pageId === "univariate_statistics") return univariateStatisticsApi.loadPageView(projectId, signal);
      if (pageId === "bivariate_statistics") return bivariateStatisticsApi.loadPageView(projectId, signal);
      return multivariateStatisticsApi.loadPageView(projectId, signal);
    };
    void queryClient.prefetchQuery<unknown>({ queryKey, queryFn, staleTime: queryTiming.volatile });
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <strong className="brand">Portfell</strong>
          <span className="brand-subtitle">Portfolio Research Engine</span>
          <div className="process-overview" aria-label="Process overview">
            <div className="process-overview__step" data-complete={workflow.status === "ready" && workflow.data.process_overview?.metadata_downloaded_isins ? "true" : "false"}>
              <small>1 · Metadata</small>
              <strong>{workflow.status === "ready" ? workflow.data.process_overview?.metadata_downloaded_isins?.toLocaleString() ?? "—" : "—"} ISINs</strong>
            </div>
            <span className="process-overview__arrow" aria-hidden="true">→</span>
            <div className="process-overview__step" data-complete={workflow.status === "ready" && workflow.data.process_overview?.metadata_builder_isins !== undefined ? "true" : "false"}>
              <small>2 · Metadata selection</small>
              <strong>{workflow.status === "ready" && workflow.data.process_overview?.metadata_builder_isins != null ? workflow.data.process_overview.metadata_builder_isins.toLocaleString() : "—"} ISINs</strong>
            </div>
            <span className="process-overview__arrow" aria-hidden="true">→</span>
            <div className="process-overview__step" data-complete={workflow.status === "ready" && workflow.data.process_overview?.univariate_statistics_isins != null ? "true" : "false"}>
              <small>3 · Univariate</small>
              <strong>{workflow.status === "ready" && workflow.data.process_overview?.univariate_statistics_isins != null ? workflow.data.process_overview.univariate_statistics_isins.toLocaleString() : "—"} ISINs</strong>
            </div>
            <span className="process-overview__arrow" aria-hidden="true">→</span>
            <div className="process-overview__step" data-complete="false">
              <small>4 · Bivariate</small>
              <strong>—</strong>
            </div>
            <span className="process-overview__arrow" aria-hidden="true">→</span>
            <div className="process-overview__step" data-complete="false">
              <small>5 · Multivariate</small>
              <strong>—</strong>
            </div>
          </div>
        </div>
        <button
          ref={menuButtonRef}
          className="project-navigation-toggle"
          type="button"
          aria-label="Open workflow navigation"
          aria-expanded={drawerOpen}
          aria-controls="project-navigation-drawer"
          onClick={() => setDrawerOpen(true)}
        >
          <Menu aria-hidden="true" />
        </button>
      </header>

      <div className="app-workspace">
        {drawerOpen ? <button className="project-navigation-backdrop" type="button" aria-label="Close workflow navigation" tabIndex={-1} onClick={() => setDrawerOpen(false)} /> : null}
        <ProjectSidebar
          currentPage={currentPage}
          workflow={workflow.status === "ready" ? workflow.data : null}
          loading={context.status === "idle" || context.status === "loading"}
          error={context.status === "error" ? context.error.message : null}
          drawerOpen={drawerOpen}
          onCloseDrawer={() => setDrawerOpen(false)}
          onWorkflowPageChange={changeWorkflowPage}
          onWorkflowPageIntent={prefetchWorkflowPage}
        />
        <main className="page-content">{children}</main>
      </div>
    </div>
  );
}
