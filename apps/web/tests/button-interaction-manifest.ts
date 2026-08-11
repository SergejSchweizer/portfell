export type ButtonInteraction = Readonly<{
  route: string;
  state: "ready" | "complete" | "mobile-closed" | "mobile-open";
  role: "button" | "tab";
  name: string;
  effect: "request" | "tab" | "drawer";
}>;

/** Semantic interaction inventory exercised on every Playwright viewport. */
export const buttonInteractionManifest: readonly ButtonInteraction[] = [
  { route: "/metadata-builder", state: "ready", role: "button", name: "Fetch all metadata", effect: "request" },
  { route: "/metadata-builder", state: "ready", role: "button", name: "Create new project", effect: "request" },
  { route: "/univariate-statistics", state: "ready", role: "button", name: "Compute univariate statistics", effect: "request" },
  { route: "/univariate-statistics", state: "complete", role: "tab", name: "Dividends", effect: "tab" },
  ...["Duration", "Annual Return", "Value at Risk", "Sortino ratio", "Expected shortfall", "Tail observations", "Sharpe ratio", "Maximum drawdown", "Trend R-squared"].map((name) => ({ route: "/univariate-statistics", state: "complete" as const, role: "tab" as const, name, effect: "tab" as const })),
  { route: "/bivariate-statistics", state: "ready", role: "button", name: "Compute Bivariate Statistics", effect: "request" },
  ...["Covariance", "Pearson", "Spearman", "Downside", "Tail Dependence", "Co-exceedance", "Rolling-Correlation", "Drawdown Overlap", "Tail-Risk Scatter"].map((name) => ({ route: "/bivariate-statistics", state: "ready" as const, role: "tab" as const, name, effect: "tab" as const })),
  { route: "/multivariate-statistics", state: "ready", role: "button", name: "Compute multivariate statistics", effect: "request" },
  ...["Overview", "Risk Structure", "Portfolio Candidates", "Risk Contributions", "Income Evidence", "Validation"].map((name) => ({ route: "/multivariate-statistics", state: "complete" as const, role: "tab" as const, name, effect: "tab" as const })),
  { route: "*", state: "mobile-closed", role: "button", name: "Open project navigation", effect: "drawer" },
  { route: "*", state: "mobile-open", role: "button", name: "Close project navigation", effect: "drawer" },
];
