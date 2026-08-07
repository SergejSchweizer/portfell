# Univariate Statistics page

- Route: `/univariate-statistics`
- Page ID: `univariate_statistics`
- Component: `apps/web/src/pages/univariate-statistics.tsx`

## Purpose

Fetch historical quotes, then run and present server-computed univariate statistics for the active project.

## Contract

The first white panel owns quote fetch progress and starts `POST /api/quote-runs` with the persisted metadata selection id. It polls `GET /api/quote-runs/{id}` and renders the server-provided `total`, `completed`, `failed`, and `percent` values before its action.

The statistics panel loads `GET /api/workflow`, starts `POST /api/univariate-statistics/runs` with the
immutable metadata selection and quote run ids, and loads bounded results from
`GET /api/univariate-statistics/runs/{run_id}/results`. It renders server progress and returned
statistics without recomputing them in React.

The persistent project sidebar supplies the active project and its workflow
status. After a project switch, local run, result-table, and status-message
state are cleared before the project-scoped workflow is reloaded.

## Acceptance

The quote panel is first in document order and its action is disabled without a metadata selection or while a fetch is active. The statistics action is disabled when prerequisites are missing or a run is active. Results use typed contracts, accessible table semantics, stable loading feedback, bounded pagination, and a clear upstream-data requirement.
