import type { ChangeEvent, MouseEvent } from "react";
import type { ApiProjectContext, ApiWorkflow, WorkflowStatus } from "../contracts";
import { projectWorkflowPath, workflowPages, type WorkflowPageId } from "../routes";

export type ProjectSidebarProps = Readonly<{
  currentPage: WorkflowPageId;
  context: ApiProjectContext | null;
  workflow: ApiWorkflow | null;
  loading: boolean;
  switching: boolean;
  error: string | null;
  drawerOpen: boolean;
  onCloseDrawer: () => void;
  onProjectChange: (projectId: string) => Promise<boolean>;
  onWorkflowPageChange: (path: string) => void;
  onWorkflowPageIntent: (pageId: WorkflowPageId) => void;
}>;

const workflowStatusLabel: Readonly<Record<WorkflowStatus, string>> = {
  locked: "Locked",
  ready: "Ready",
  running: "Running",
  complete: "Complete",
  failed: "Failed",
  stale: "Stale",
};

export function ProjectSidebar({
  currentPage,
  context,
  workflow,
  loading,
  switching,
  error,
  drawerOpen,
  onCloseDrawer,
  onProjectChange,
  onWorkflowPageChange,
  onWorkflowPageIntent,
}: ProjectSidebarProps) {
  const currentProjectId = context?.current_project_id ?? "";
  const currentProject = context?.current_project ?? null;
  const noProjects = !loading && context?.projects.length === 0;

  async function changeProject(event: ChangeEvent<HTMLSelectElement>) {
    if (event.target.value && await onProjectChange(event.target.value)) onCloseDrawer();
  }

  function navigateWorkflowPage(event: MouseEvent<HTMLAnchorElement>, path: string) {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    onWorkflowPageChange(path);
    onCloseDrawer();
  }

  return (
    <aside id="project-navigation-drawer" className="project-sidebar" data-open={drawerOpen} aria-label="Project navigation">
      <div className="project-sidebar__project">
        <label htmlFor="current-project">Project</label>
        <select
          id="current-project"
          value={currentProjectId}
          title={context?.current_project?.name}
          disabled={loading || switching || noProjects}
          onChange={changeProject}
        >
          {noProjects ? <option value="">No projects yet</option> : null}
          {context?.projects.map((project) => (
            <option key={project.project_id} value={project.project_id}>
              {project.name}
            </option>
          ))}
        </select>
      </div>

      <nav className="project-sidebar__workflow" aria-label="Workflow">
        <p>Workflow</p>
        <ol>
          {workflowPages.map((page, index) => {
            const status = workflow?.stages[page.stageId].status ?? (index === 0 ? "ready" : "locked");
            const locked = status === "locked";
            const contents = <><span className="project-sidebar__step">{index + 1}</span><span className="project-sidebar__stage"><span>{page.title}</span><small>{workflowStatusLabel[status]}</small></span></>;
            const path = currentProject ? projectWorkflowPath(currentProject, page) : page.path;
            return (
              <li key={page.id} data-status={status}>
                {locked ? <span aria-disabled="true">{contents}</span> : <a href={path} aria-current={page.id === currentPage ? "page" : undefined} onMouseEnter={() => onWorkflowPageIntent(page.id)} onFocus={() => onWorkflowPageIntent(page.id)} onClick={(event) => navigateWorkflowPage(event, path)}>{contents}</a>}
              </li>
            );
          })}
        </ol>
      </nav>

      {loading ? <p className="project-sidebar__message" aria-live="polite">Loading projects</p> : null}
      {error ? <p className="project-sidebar__message" role="alert">{error}</p> : null}
    </aside>
  );
}
