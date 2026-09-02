# Bivariate

Route: `/bivariate`

Subtitle: `Inspect pairwise diversification evidence for the persisted Univariate selection.`

The final Bivariate page is a Plotly Dash page backed by the persisted Univariate selection and typed application services. It never analyzes a browser-only row subset and callbacks execute no SQL.

## Layout

The page contains:

- `PageHeader` with the frozen title/subtitle;
- one `ControlBar` with `Compute bivariate statistics` and only backend-supported pair-result controls;
- KPI cards `Multivariate Selected ISINs`, `Candidate pairs`, `Eligible pairs`, `Unavailable pairs`;
- `ChartCard` `Bivariate Return / Diversification Universe` using backend/service values and full pair identities;
- point colour encodes lower-tail dependence: green/blue indicates lower shared extreme risk and red indicates higher shared extreme risk; the same value is shown in hover details;
- no content after the Plotly chart; pair tables, history, and continuation controls are intentionally omitted.

## Analytical contract

Common-calendar, minimum-observation, pair-eligibility, and same-ISIN rules remain backend-authoritative. Candidate/eligible/unavailable counts must reconcile exactly with persisted evidence. Missing covariance/correlation is unavailable and is never encoded or plotted as zero. Full `(isin, exchange, code)` identity remains visible wherever an ISIN alone would be ambiguous.

Dash does not recompute financial pair metrics for plotting/sorting unless the frozen service contract explicitly defines a presentation-only transformation. Run state/history/readiness persist across application restart.

## Responsive/accessibility contract

Tablet/mobile stack shared controls/KPIs/charts according to the common visual contract; the page itself has no horizontal overflow. Unavailable and disabled states remain visible and keyboard reachable.
