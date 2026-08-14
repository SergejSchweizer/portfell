# Univariate Statistics page


## Table Of Contents

- [Purpose](#purpose)
- [Module boundary](#module-boundary)
- [Contract](#contract)
- [Acceptance](#acceptance)

- Route: `/univariate-statistics`
- Page ID: `univariate_statistics`
- Component: `apps/web/src/pages/univariate-statistics.tsx`

## Purpose

Present server-computed univariate statistics for the active project after the central shared-market
refresh covers its selection.

## Module boundary

Univariate Statistics consumes the persisted metadata selection and shared-market readiness from Metadata
Builder. It owns per-ISIN results, per-project statistic selections, and the optional filtered
selection consumed by Bivariate Statistics. It must not create metadata selections or calculate
pairwise relationships.

## Contract

The browser never starts an EODHD download. The central `project-bootstrap-worker`
updates the canonical quotes, dividends, and splits store for the de-duplicated active-project
inventory. Before coverage is available, the page explains that historical data is refreshed
automatically and offers no manual workaround.

The statistics panel loads `GET /api/workflow`, starts `POST /api/univariate-statistics/runs` with the
immutable metadata selection and quote run ids, and loads bounded results from
`GET /api/univariate-statistics/runs/{run_id}/results`. It renders server progress and returned
statistics without recomputing them in React.

The univariate-statistics action owns only computation progress, status, and its right-aligned action.
Its determinate progress bar uses processed listings as its scale, including terminal failed listings;
the server reports each completed listing for both shared-market and pinned quote-run computations.
React keeps the displayed percentage monotonic for the active run so delayed polling responses cannot move the bar backward; starting or switching to another run resets that display.
All workflow progress bars use the shared 10px height.
The Dividends univariate-statistic block and all quantitative-statistic tabs render immediately when
the page opens. Until a result payload is available, their controls and charts show their existing
empty values without implying a completed computation. The block provides a payout-frequency selection and an accessible
histogram that counts ISINs by none/unknown, monthly, quarterly, semiannual, annual, and
irregular schedules. The selected schedules and statistic filters update locally immediately and
persist the latest value per project through one debounced background request. The sidebar workflow
status is revalidated after saving; completed result rows remain in place.

After a completed run, the page presents Dividends and all quantitative statistics in one shared
statistics window. Its responsive multi-row tab grid selects exactly one statistic at a time; the active tab
contains that statistic's formula, notation, dividend-type facts, project-persisted multi-selection,
and histogram derived from completed server-returned rows:

| Statistic | Returned field | Unit |
| --- | --- | --- |
| Duration | `quote_observation_count` | trading days; fixed minimum-history thresholds |
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
status. A project with a persisted metadata selection remains pending until its
shared-market coverage is complete; no project quote run is created. After a project switch, local run,
result-table, and status-message state are cleared before the project-scoped
workflow is reloaded. Once the univariate run completes, the server applies the project-persisted
dividend-frequency and statistic-range filters to create the current deterministic Univariate
selection. Bivariate Statistics receives that selection directly on its next workflow refresh. There
is no standalone filter module or route in the browser workflow.

Every frequency or quantitative filter labels its `Portfolio selection` control with the current
server-owned selected-ISIN count after saving. Duration labels use strict minimum-history thresholds: `> 6 months` persists a minimum
of 127 trading-day observations, so exactly 126 observations do not qualify. `> 2 years` persists
505 observations. `> 6 months` is the minimum filter for a production-eligible Multivariate input,
which requires at least 100 common daily returns across the Bivariate selection.

## Acceptance

No manual historical-data action, quote-run polling state, or quote-run mutation request exists in the
page. The statistics action is disabled when shared coverage or other prerequisites are missing, or a
run is active. One accessible tab panel is present before and after results load; it contains Dividends
and every quantitative statistic with explicit empty fields until data is available. Results use typed contracts, accessible tab semantics, stable
loading feedback, bounded pagination, and a clear upstream-data requirement.

The stateful two-project browser journey observes shared-market readiness and computes both
projects without any browser provider-download request. It exercises every project-persisted
portfolio-selection field, histogram hover content, and restoration of saved selections after
switching projects.
