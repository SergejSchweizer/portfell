# Univariate Statistics page

- Route: `/univariate-statistics`
- Page ID: `univariate_statistics`
- Component: `apps/web/src/pages/univariate-statistics.tsx`

## Purpose

Download historical data, then run and present server-computed univariate statistics for the active project.

## Module boundary

Univariate Statistics consumes the persisted metadata selection and quote-run IDs from Metadata
Builder. It owns per-ISIN results, per-project statistic selections, and the optional filtered
selection consumed by Bivariate Statistics. It must not create metadata selections or calculate
pairwise relationships.

## Contract

The first white panel owns quote fetch progress and starts `POST /api/quote-runs` with the persisted metadata selection id. Each project download computes independent deltas for Quotes, Dividends, and Splits; all three datasets are merged into the server-owned Bronze lake only for the selected project's listings. It polls `GET /api/quote-runs/{id}` and renders the server-provided `total`, `completed`, `failed`, and `percent` values before its action.

The statistics panel loads `GET /api/workflow`, starts `POST /api/univariate-statistics/runs` with the
immutable metadata selection and quote run ids, and loads bounded results from
`GET /api/univariate-statistics/runs/{run_id}/results`. It renders server progress and returned
statistics without recomputing them in React.

The univariate-statistics action uses the same progress, status, and right-aligned action layout as
the historical-data download block. The Dividends univariate-statistic block is not rendered before
a completed computation has loaded its result payload, matching the result-driven bivariate
statistic windows. It provides a payout-frequency selection and an accessible
histogram that counts ISINs by none/unknown, monthly, quarterly, semiannual, annual, and
irregular schedules. The selected schedules are saved per project.

The page currently exposes only these quantitative statistic cards, each with a formula, notation,
dividend-type facts, a project-persisted multi-selection, and a histogram derived from completed
server-returned rows:

| Statistic | Returned field | Unit |
| --- | --- | --- |
| Annual Return | `annualized_geometric_return` | % |
| Value at Risk | `var` | % |
| Sortino Ratio | `sortino_ratio` | ratio |
| Expected Shortfall | `expected_shortfall` | % |
| Tail Observations | `tail_observation_count` | observations |
| Sharpe Ratio | `sharpe_ratio` | ratio |
| Maximum Drawdown | `max_drawdown` | % |
| Trend R-squared | `trend_r_squared` | ratio |

Other cached Gold fields remain technical implementation data and are not presented as univariate
statistics in the UI at this time.

The persistent project sidebar supplies the active project and its workflow
status. A project with a persisted metadata selection activates this page so
its quote-fetch action is available; a completed quote run remains required
before statistics can be computed. After a project switch, local run,
result-table, and status-message state are cleared before the project-scoped
workflow is reloaded. Once the univariate run completes, the server creates the automatic all-results
selection and unlocks Bivariate Statistics directly. There is no standalone filter module or route in
the browser workflow.

## Acceptance

The quote panel is first in document order and its `Download Historical Data` action is disabled without a metadata selection or while a download is active. A failed download displays the server-provided safe error code. The statistics action is disabled when prerequisites are missing or a run is active. No Dividends window is present before completed univariate results are loaded; it appears with the other completed-result statistics, including when the returned result set is empty. Results use typed contracts, accessible table semantics, stable loading feedback, bounded pagination, and a clear upstream-data requirement.

The stateful two-project browser journey exercises historical-data and compute
actions, every project-persisted portfolio-selection field, histogram hover
content, and restoration of saved selections after switching projects.
