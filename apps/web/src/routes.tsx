
import type { ComponentType } from "react";
import { BivariateStatisticsPage } from "./pages/bivariate-statistics";
import { MetadataFilterPage } from "./pages/metadata-filter";
import { UnivariateFilterPage } from "./pages/univariate-filter";
import { UnivariateStatisticsPage } from "./pages/univariate-statistics";

export type WorkflowPageId =
  | "metadata_filter"
  | "univariate_statistics"
  | "univariate_filter"
  | "bivariate_statistics";

export type WorkflowModuleId = "metadata_builder" | "univariate_statistics" | "bivariate_statistics";

export type WorkflowPage = Readonly<{
  id: WorkflowPageId;
  moduleId: WorkflowModuleId;
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
];

export const workflowPages: readonly WorkflowPage[] = [
  {
    id: "metadata_filter",
    moduleId: "metadata_builder",
    title: "Metadata Builder",
    path: "/metadata-filter",
    component: MetadataFilterPage,
  },
  {
    id: "univariate_statistics",
    moduleId: "univariate_statistics",
    title: "Univariate Statistics",
    path: "/univariate-statistics",
    component: UnivariateStatisticsPage,
  },
  {
    id: "univariate_filter",
    moduleId: "univariate_statistics",
    title: "Univariate Filter",
    path: "/univariate-filter",
    component: UnivariateFilterPage,
  },
  {
    id: "bivariate_statistics",
    moduleId: "bivariate_statistics",
    title: "Bivariate Statistics",
    path: "/bivariate-statistics",
    component: BivariateStatisticsPage,
  },
];

export function currentWorkflowPage(pathname: string): WorkflowPage {
  return workflowPages.find((page) => page.path === pathname) ?? workflowPages[0];
}
