
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Menu } from "lucide-react";
import {
  loadProjectContext,
  loadProjectWorkflow,
  selectCurrentProject,
} from "../api/client";
import type { ApiProjectContext, ApiWorkflow } from "../contracts";
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
  const [contextRevision, setContextRevision] = useState(0);
  const [workflowRevision, setWorkflowRevision] = useState(0);
  const [switching, setSwitching] = useState(false);
  const [switchError, setSwitchError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
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

  async function changeProject(nextProjectId: string): Promise<boolean> {
    if (!projectId || nextProjectId === projectId || switching) return false;
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
      return true;
    } catch (error) {
      setSwitchError(error instanceof Error ? error.message : "Project switch failed.");
      return false;
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
        />
        <main className="page-content">{children}</main>
      </div>
    </div>
  );
}
