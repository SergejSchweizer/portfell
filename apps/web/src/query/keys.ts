type ProjectId = string;
type RunId = string;

export const queryKeys = {
  projectContext: () => ["project-context"] as const,
  metadataOptions: () => ["metadata-builder", "field-options"] as const,
  workflowRoot: () => ["workflow"] as const,
  workflow: (projectId?: ProjectId) => ["workflow", projectId ?? "current"] as const,
  pageView: (projectId: ProjectId, module: string) => ["page-view", projectId, module] as const,
  section: (projectId: ProjectId, module: string, section: string, revision?: string) => (
    ["section", projectId, module, section, revision ?? "current"] as const
  ),
  run: (module: string, runId: RunId) => ["run", module, runId] as const,
};
