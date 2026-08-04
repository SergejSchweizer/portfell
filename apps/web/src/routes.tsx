
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

export type WorkflowPage = Readonly<{
  id: WorkflowPageId;
  title: string;
  path: string;
  component: ComponentType;
}>;

export const workflowPages: readonly WorkflowPage[] = [
  {
    id: "metadata_filter",
    title: "Metadata Filter",
    path: "/metadata-filter",
    component: MetadataFilterPage,
  },
  {
    id: "univariate_statistics",
    title: "Univariate Statistics",
    path: "/univariate-statistics",
    component: UnivariateStatisticsPage,
  },
  {
    id: "univariate_filter",
    title: "Univariate Filter",
    path: "/univariate-filter",
    component: UnivariateFilterPage,
  },
  {
    id: "bivariate_statistics",
    title: "Bivariate Statistics",
    path: "/bivariate-statistics",
    component: BivariateStatisticsPage,
  },
];

export function currentWorkflowPage(pathname: string): WorkflowPage {
  return workflowPages.find((page) => page.path === pathname) ?? workflowPages[0];
}
