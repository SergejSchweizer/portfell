# Multivariate

Route: `/multivariate`

Subtitle: `Optimize candidate portfolios and select the final portfolio from out-of-sample evidence.`

Multivariate is the only optimizer page/stage. The final page is Plotly Dash backed by persisted service/artifact contracts; rendering never reruns optimization and callbacks execute no SQL.

## Objectives

The v1 objective IDs are exactly:

- `return_risk` — default;
- `return_drawdown`;
- `minimum_risk`.

No additional objective is a UI-only invention. Changing the objective marks a previously displayed winner stale until a matching completed run is selected/executed according to the shared state contract.

## Layout

The page contains:

- `PageHeader` with the frozen title/subtitle;
- one `ControlBar` with the frozen objective selector and `Optimize portfolio`;
- KPI cards `Winner OOS return`, `Winner OOS risk`, `Winner max drawdown`, `Production eligibility`;
- `ChartCard` `Portfolio Candidate OOS Return / Risk`;
- `ChartCard` `Cumulative Performance`;
- `ChartCard` `Drawdown`;
- `ChartCard` `Allocation` when the persisted artifact is available;
- `ChartCard` `Risk Contribution` when the persisted artifact is available;
- `TableCard` `Final Portfolio` with full listing identity, final weight, and other winner-artifact fields only;
- `Decision` evidence card with objective, winning candidate ID, requested/actual method, source snapshot short ID, algorithm version, availability, production eligibility, and persisted explanation/reason;
- `HistoryCard` `Universe & History` with upstream stage identities and Multivariate run history;
- `StageFooter` showing final readiness/eligibility without creating a fifth workflow stage.

## Analytical contract

Winner selection is driven by out-of-sample ranking; in-sample best is never silently substituted. Requested and actual optimizer/risk-model methods are read from persisted artifacts rather than inferred from controls. Equal Weight is never a hidden solver-failure fallback.

OOS return/risk, cumulative performance, drawdown, allocation, risk contribution, final weights, and KPI values render from backend artifacts only. Missing optional allocation/risk-contribution evidence uses the shared unavailable state rather than disappearing or becoming zero. The persisted DecisionArtifact explains the winner and production eligibility.

Restart restores the completed run, winner, plots, final table, decision evidence, KPI values, and history from `portfell_dash`.

## Responsive/accessibility contract

Mobile renders cards sequentially with responsive Plotly figures, stacked controls/KPIs, and no page-level horizontal overflow. Typed unavailable/error/status states and supported actions remain keyboard reachable.