# Univariate Statistics page

- Route: `/univariate-statistics`
- Page ID: `univariate_statistics`
- Component: `apps/web/src/pages/univariate-statistics.tsx`

## Purpose

Run and present server-computed univariate statistics for the active project after quote data is available.

## Contract

The page loads `GET /api/workflow`, starts `POST /api/univariate-statistics/runs` with the
immutable metadata selection and quote run ids, and loads bounded results from
`GET /api/univariate-statistics/runs/{run_id}/results`. It renders server progress and returned
statistics without recomputing them in React.

The persistent project sidebar supplies the active project and its workflow
status. After a project switch, local run, result-table, and status-message
state are cleared before the project-scoped workflow is reloaded.

## Acceptance

The primary action is disabled when prerequisites are missing or a run is active. Locked state links
to Metadata Filter. Results use typed contracts, accessible table semantics, stable loading feedback,
bounded pagination, and a clear upstream-data requirement.
