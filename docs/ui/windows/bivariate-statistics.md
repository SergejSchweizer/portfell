# Bivariate Statistics page

- Route: `/bivariate-statistics`
- Page ID: `bivariate_statistics`
- Component: `apps/web/src/pages/bivariate-statistics.tsx`

## Purpose

Run and present server-computed pairwise statistics for the automatic all-results selection produced
when univariate statistics complete. The server's automatic all-results selection is an internal
persistence hand-off, not a separate browser filter module.

## Module boundary

Bivariate Statistics consumes the persisted selected-ISIN set from Univariate Statistics and owns
pairwise rows and matrices. It must not modify the metadata or univariate selections, and portfolio
construction remains a later module.

## Contract

The page preflights through `POST /api/bivariate-statistics/plan`, starts
`POST /api/bivariate-statistics/runs`, reports server progress, and loads bounded results from
`GET /api/bivariate-statistics/runs/{run_id}/results`. Pair construction, limits, calculations,
storage, and ranking remain backend responsibilities.

The persistent project sidebar identifies the active project and four-stage
workflow hierarchy. A project switch clears the local pair plan, run, results,
and status message before this page loads the replacement project workflow.

## Acceptance

The page blocks execution when upstream filtering is incomplete, empty, stale, or over the configured
pair limit. It prevents duplicate runs, represents empty and partial results explicitly, and provides
accessible tabular output on desktop and a usable responsive representation on narrow screens.

The stateful two-project browser journey computes the active project's pair
statistics and selects every pairwise-dependence tab.
