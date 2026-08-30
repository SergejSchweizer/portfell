
import type { ComponentType } from "react";
import type { ApiProjectSummary, WorkflowStageId } from "./contracts";
import { BivariateStatisticsPage } from "./pages/bivariate-statistics";
import { MetadataBuilderPage } from "./pages/metadata-builder";
import { MultivariateStatisticsPage } from "./pages/multivariate-statistics";
import { UnivariateStatisticsPage } from "./pages/univariate-statistics";

export type WorkflowPageId =
  | "metadata_builder"
  | "univariate_statistics"
  | "bivariate_statistics"
  | "multivariate_statistics";

export type WorkflowModuleId = WorkflowPageId;

export type WorkflowPage = Readonly<{
  id: WorkflowPageId;
  moduleId: WorkflowModuleId;
  stageId: WorkflowStageId;
  title: string;
  path: string;
  component: ComponentType;
}>;

export type WorkflowModule = Readonly<{
  id: WorkflowModuleId;
  title: string;
  boundary: string;
}>;

export const workflowModules: readonly WorkflowModule[] = [
  {
    id: "metadata_builder",
    title: "Metadata",
    boundary: "Builds the current workspace metadata selection; it does not calculate financial statistics.",
  },
  {
    id: "univariate_statistics",
    title: "Univariate",
    boundary: "Calculates and filters per-instrument statistics from the current workspace selection.",
  },
  {
    id: "bivariate_statistics",
    title: "Bivariate",
    boundary: "Calculates pairwise statistics from the persisted univariate selection.",
  },
  {
    id: "multivariate_statistics",
    title: "Multivariate",
    boundary: "Consumes the completed bivariate universe for portfolio-level analysis.",
  },
];

export const workflowPages: readonly WorkflowPage[] = [
  {
    id: "metadata_builder",
    moduleId: "metadata_builder",
    stageId: "metadata_builder",
    title: "Metadata",
    path: "/metadata",
    component: MetadataBuilderPage,
  },
  {
    id: "univariate_statistics",
    moduleId: "univariate_statistics",
    stageId: "univariate_statistics",
    title: "Univariate",
    path: "/univariate",
    component: UnivariateStatisticsPage,
  },
  {
    id: "bivariate_statistics",
    moduleId: "bivariate_statistics",
    stageId: "bivariate_statistics",
    title: "Bivariate",
    path: "/bivariate",
    component: BivariateStatisticsPage,
  },
  {
    id: "multivariate_statistics",
    moduleId: "multivariate_statistics",
    stageId: "multivariate_statistics",
    title: "Multivariate",
    path: "/multivariate",
    component: MultivariateStatisticsPage,
  },
];

/** Transitional compatibility helper: project identity no longer changes browser routing. */
export function projectWorkflowPath(
  _project: Pick<ApiProjectSummary, "project_id" | "name">,
  page: WorkflowPage,
): string {
  return page.path;
}

/** Project slugs are retired from the canonical single-workspace browser routes. */
export function projectSlugFromPath(_pathname: string): string | null {
  return null;
}

/** Retained only for callers compiled during the legacy-UI freeze; it is not a route authority. */
export function projectSlug(name: string): string {
  const slug = name
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return slug || "project";
}

export function currentWorkflowPage(pathname: string): WorkflowPage {
  return workflowPages.find((page) => page.path === pathname) ?? workflowPages[0];
}
