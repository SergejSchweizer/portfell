# Bivariate

Route: `/bivariate`

Subtitle: `Inspect pairwise diversification evidence for the persisted Univariate selection.`

The final Bivariate page is a Plotly Dash page backed by the persisted Univariate selection and typed application services. It never analyzes a browser-only row subset and callbacks execute no SQL.

## Layout

The page contains:

- `PageHeader` with the frozen title/subtitle;
- one `ControlBar` with `Compute bivariate statistics` and only backend-supported pair-result controls;
- KPI cards `Input instruments`, `Candidate pairs`, `Eligible pairs`, `Unavailable pairs`;
- `ChartCard` `Bivariate Return / Diversification Universe` using backend/service values and full pair identities;
- `TableCard` `Bivariate Statistics` with both full listing identities and contracted pair metrics/evidence;
- explicit unavailable correlation/covariance/common-calendar evidence with reason where supplied;
- `HistoryCard` `Universe & History` with upstream selection version/count, run ID/status, source snapshot short ID, algorithm version, and pair-result counts;
- `StageFooter` with `Continue to Multivariate`, disabled until Bivariate readiness is satisfied.

## Analytical contract

Common-calendar, minimum-observation, pair-eligibility, and same-ISIN rules remain backend-authoritative. Candidate/eligible/unavailable counts must reconcile exactly with persisted evidence. Missing covariance/correlation is unavailable and is never encoded or plotted as zero. Full `(isin, exchange, code)` identity remains visible wherever an ISIN alone would be ambiguous.

Dash does not recompute financial pair metrics for plotting/sorting unless the frozen service contract explicitly defines a presentation-only transformation. Run state/history/readiness persist across application restart.

## Responsive/accessibility contract

Large pair results remain bounded and the table scrolls/virtualizes inside its card. Tablet/mobile stack shared controls/KPIs/charts according to the common visual contract; the page itself has no horizontal overflow. Unavailable and disabled states remain visible and keyboard reachable.