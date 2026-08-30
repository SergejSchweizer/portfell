# Univariate

Route: `/univariate`

Subtitle: `Inspect single-instrument return and risk statistics, then persist the downstream selection.`

The final Univariate page is a Plotly Dash page backed by typed application services. Financial formulas, annualization, return semantics, missing-data decisions, and persisted selection identity remain backend-authoritative.

## Layout

The page contains:

- `PageHeader` with the frozen title/subtitle;
- one `ControlBar` with `Compute univariate statistics` and only backend-supported result settings/filters;
- KPI cards `Input instruments`, `Available results`, `Selected instruments`, `Unavailable results`;
- `ChartCard` `Univariate Return / Risk Universe` using service-provided return/risk values and full listing identity in hover;
- `TableCard` `Univariate Statistics` with exact service-provided metrics and downstream selection controls;
- `HistoryCard` `Universe & History` with input Metadata universe/version, run ID/status, source snapshot short ID, algorithm version, persisted selection version/count;
- `StageFooter` with `Save selection` and `Continue to Bivariate`.

Continuation is disabled until a valid persisted Univariate selection exists.

## Analytical contract

`adjusted_close` is authoritative. Missing adjusted close renders typed unavailable evidence and never falls back to raw close or zero. Distribution/income evidence does not alter adjusted-close return calculations. Dash does not recompute annualized return, volatility, drawdown, distribution yield, or other financial metrics solely for display.

KPI counts reconcile with immutable returned/service data. Filtering/selection never mutates the completed run artifact. Persisted selection reloads after restart and restores table selection, KPIs, history, sidebar context, and downstream readiness.

## Responsive/accessibility contract

Controls and KPI cards stack at narrow widths; the Plotly figure remains responsive; table overflow stays inside its card. Unavailable rows remain explainable in table/status regions and actions/status are keyboard reachable. The page has no page-level horizontal overflow.