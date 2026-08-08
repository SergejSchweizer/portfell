# Univariate Statistics page

- Route: `/univariate-statistics`
- Page ID: `univariate_statistics`
- Component: `apps/web/src/pages/univariate-statistics.tsx`

## Purpose

Download historical data, then run and present server-computed univariate statistics for the active project.

## Contract

The first white panel owns quote fetch progress and starts `POST /api/quote-runs` with the persisted metadata selection id. Each project download computes independent deltas for Quotes, Dividends, and Splits; all three datasets are merged into the server-owned Bronze lake only for the selected project's listings. It polls `GET /api/quote-runs/{id}` and renders the server-provided `total`, `completed`, `failed`, and `percent` values before its action.

The statistics panel loads `GET /api/workflow`, starts `POST /api/univariate-statistics/runs` with the
immutable metadata selection and quote run ids, and loads bounded results from
`GET /api/univariate-statistics/runs/{run_id}/results`. It renders server progress and returned
statistics without recomputing them in React.

The univariate-statistics action uses the same progress, status, and right-aligned action layout as
the historical-data download block. After a completed computation, the page first presents a
Dividends univariate-statistic block. It provides a payout-frequency selection and an accessible
histogram that counts ISINs by no payout, monthly, quarterly, semiannual, annual, unknown, and
irregular schedules. The selected schedule is visually emphasized in the histogram.

The quantitative metrics remain in their existing univariate-statistic groups. Their five-column
table contains the statistic name, description, equation, histogram across the computed project
listings, and a draft filter-value input. Histograms are derived only from the completed
server-returned result rows.

The persistent project sidebar supplies the active project and its workflow
status. A project with a persisted metadata selection activates this page so
its quote-fetch action is available; a completed quote run remains required
before statistics can be computed. After a project switch, local run,
result-table, and status-message state are cleared before the project-scoped
workflow is reloaded.

## Acceptance

The quote panel is first in document order and its `Download Historical Data` action is disabled without a metadata selection or while a download is active. A failed download displays the server-provided safe error code. The statistics action is disabled when prerequisites are missing or a run is active. Results use typed contracts, accessible table semantics, stable loading feedback, bounded pagination, and a clear upstream-data requirement.
