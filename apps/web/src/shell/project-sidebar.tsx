import type { MouseEvent } from "react";
import type { ApiWorkflow, WorkflowStatus } from "../contracts";
import { workflowPages, type WorkflowPageId } from "../routes";

export type ProjectSidebarProps = Readonly<{
  currentPage: WorkflowPageId;
  workflow: ApiWorkflow | null;
  loading: boolean;
  error: string | null;
  drawerOpen: boolean;
  onCloseDrawer: () => void;
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

function quotePeriodLabel(workflow: ApiWorkflow | null): string | null {
  const start = workflow?.process_overview?.quote_start;
  const end = workflow?.process_overview?.quote_end;
  if (!start || !end) return null;
  const format = (value: string) => {
    const [year, month, day] = value.split("-");
    return year && month && day ? `${day}.${month}.${year}` : value;
  };
  return `${format(start)}-${format(end)}`;
}

export function ProjectSidebar({
  currentPage,
  workflow,
  loading,
  error,
  drawerOpen,
  onCloseDrawer,
  onWorkflowPageChange,
  onWorkflowPageIntent,
}: ProjectSidebarProps) {
  const quotePeriod = quotePeriodLabel(workflow);

  function navigateWorkflowPage(event: MouseEvent<HTMLAnchorElement>, path: string) {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    onWorkflowPageChange(path);
    onCloseDrawer();
  }

  return (
    <aside id="project-navigation-drawer" className="project-sidebar" data-open={drawerOpen} aria-label="Workflow navigation">
      <nav className="project-sidebar__workflow" aria-label="Workflow">
        <p>Workflow</p>
        <ol>
          {workflowPages.map((page, index) => {
            const status = workflow?.stages[page.stageId].status ?? (index === 0 ? "ready" : "locked");
            const locked = status === "locked";
            const contents = <><span className="project-sidebar__step">{index + 1}</span><span className="project-sidebar__stage"><span>{page.title}</span><small>{workflowStatusLabel[status]}</small>{quotePeriod ? <small className="project-sidebar__quote-period">{quotePeriod}</small> : null}</span></>;
            return (
              <li key={page.id} data-status={status}>
                {locked ? <span aria-disabled="true">{contents}</span> : <a href={page.path} aria-current={page.id === currentPage ? "page" : undefined} onMouseEnter={() => onWorkflowPageIntent(page.id)} onFocus={() => onWorkflowPageIntent(page.id)} onClick={(event) => navigateWorkflowPage(event, page.path)}>{contents}</a>}
              </li>
            );
          })}
        </ol>
      </nav>

      {loading ? <p className="project-sidebar__message" aria-live="polite">Loading workspace</p> : null}
      {error ? <p className="project-sidebar__message" role="alert">{error}</p> : null}
    </aside>
  );
}
