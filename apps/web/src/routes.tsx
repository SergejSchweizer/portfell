
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

export type WorkflowModuleId =
  | "metadata_builder"
  | "univariate_statistics"
  | "bivariate_statistics"
  | "multivariate_statistics";

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
    title: "Metadata Builder",
    boundary: "Builds one project-scoped metadata selection; it does not calculate financial statistics.",
  },
  {
    id: "univariate_statistics",
    title: "Univariate Statistics",
    boundary: "Calculates and filters per-ISIN statistics from the selected project's historical data.",
  },
  {
    id: "bivariate_statistics",
    title: "Bivariate Statistics",
    boundary: "Calculates pairwise statistics from the univariate module's selected ISIN set.",
  },
  {
    id: "multivariate_statistics",
    title: "Multivariate Statistics",
    boundary: "Consumes the completed bivariate ISIN universe for portfolio-level analysis.",
  },
];

export const workflowPages: readonly WorkflowPage[] = [
  {
    id: "metadata_builder",
    moduleId: "metadata_builder",
    stageId: "metadata_builder",
    title: "Metadata Builder",
    path: "/metadata-builder",
    component: MetadataBuilderPage,
  },
  {
    id: "univariate_statistics",
    moduleId: "univariate_statistics",
    stageId: "univariate_statistics",
    title: "Univariate Statistics",
    path: "/univariate-statistics",
    component: UnivariateStatisticsPage,
  },
  {
    id: "bivariate_statistics",
    moduleId: "bivariate_statistics",
    stageId: "bivariate_statistics",
    title: "Bivariate Statistics",
    path: "/bivariate-statistics",
    component: BivariateStatisticsPage,
  },
  {
    id: "multivariate_statistics",
    moduleId: "multivariate_statistics",
    stageId: "multivariate_statistics",
    title: "Multivariate Statistics",
    path: "/multivariate-statistics",
    component: MultivariateStatisticsPage,
  },
];

const projectPathPattern = /^\/projects\/([^/]+)\/[^/]+(\/[^/?#]+)$/;

export function projectSlug(name: string): string {
  const slug = name
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return slug || "project";
}

export function projectWorkflowPath(project: Pick<ApiProjectSummary, "project_id" | "name">, page: WorkflowPage): string {
  return `/projects/${encodeURIComponent(project.project_id)}/${projectSlug(project.name)}${page.path}`;
}

export function projectIdFromPath(pathname: string): string | null {
  const match = pathname.match(projectPathPattern);
  if (!match) return null;
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return null;
  }
}

export function currentWorkflowPage(pathname: string): WorkflowPage {
  const workflowPath = pathname.match(projectPathPattern)?.[2] ?? pathname;
  return workflowPages.find((page) => page.path === workflowPath) ?? workflowPages[0];
}
