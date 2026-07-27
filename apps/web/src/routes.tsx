import type { ReactNode } from "react";
import { ComponentCatalogue } from "./catalogue";
import { LegacyShellAdapter } from "./compat/legacy-shell";
import { AuthenticatedShellPage } from "./pages/authenticated-shell";
import { AccountPage } from "./pages/account";
import { DataPage } from "./pages/data";
import { DiversificationPage } from "./pages/diversification";
import { FilterPage } from "./pages/filter";
import { HealthPage } from "./pages/health";
import { MetadataPage } from "./pages/metadata";
import { PortfolioPage } from "./pages/portfolio";
import { ReportPage } from "./pages/report";
import { LoginGatePage } from "./pages/login-gate";
import { FixturePreviewPage } from "./pages/fixture-preview";
import { RecommendationPage } from "./pages/recommendation";
import { SettingsPage } from "./pages/settings";
import { StressPage } from "./pages/stress";
import { UnivariatePage } from "./pages/univariate";
import { ValidationPage } from "./pages/validation";

export type RouteDefinition = Readonly<{
  path: string;
  title: string;
  shell?: boolean;
  element: () => ReactNode;
}>;

export const routes: readonly RouteDefinition[] = [
  { path: "/health", title: "Health", element: () => <HealthPage /> },
  { path: "/", title: "Camovar Research", element: () => <LoginGatePage /> },
  {
    path: "/shell",
    title: "Authenticated Shell",
    shell: true,
    element: () => <AuthenticatedShellPage />,
  },
  {
    path: "/compat/legacy",
    title: "Legacy Shell Compatibility",
    shell: true,
    element: () => <LegacyShellAdapter />,
  },
  {
    path: "/catalogue",
    title: "Component Catalogue",
    shell: true,
    element: () => <ComponentCatalogue />,
  },
  {
    path: "/fixtures",
    title: "Fixture Preview",
    shell: true,
    element: () => <FixturePreviewPage />,
  },
  { path: "/data", title: "Data", shell: true, element: () => <DataPage /> },
  { path: "/metadata", title: "Metadata", shell: true, element: () => <MetadataPage /> },
  { path: "/univariate", title: "Univariate", shell: true, element: () => <UnivariatePage /> },
  { path: "/filter", title: "Filter", shell: true, element: () => <FilterPage /> },
  {
    path: "/diversification",
    title: "Diversification",
    shell: true,
    element: () => <DiversificationPage />,
  },
  { path: "/portfolio", title: "Portfolio", shell: true, element: () => <PortfolioPage /> },
  { path: "/validation", title: "Validation", shell: true, element: () => <ValidationPage /> },
  { path: "/report", title: "Report", shell: true, element: () => <ReportPage /> },
  { path: "/stress", title: "Stress", shell: true, element: () => <StressPage /> },
  {
    path: "/recommendation",
    title: "Recommendation",
    shell: true,
    element: () => <RecommendationPage />,
  },
  { path: "/settings", title: "Settings", shell: true, element: () => <SettingsPage /> },
  { path: "/account", title: "Account", shell: true, element: () => <AccountPage /> },
];

export function matchRoute(pathname: string): RouteDefinition {
  return routes.find((route) => route.path === pathname) ?? routes[1];
}

export function routeTitle(pathname: string): string {
  return matchRoute(pathname).title;
}
