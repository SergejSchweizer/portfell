# Bivariate Statistics page

- Route: `/bivariate-statistics`
- Page ID: `bivariate_statistics`
- Component: `apps/web/src/pages/bivariate-statistics.tsx`

## Purpose

Run and present server-computed pairwise statistics for the selection produced by the univariate filter.

## Contract

The page preflights through `POST /api/bivariate-statistics/plan`, starts
`POST /api/bivariate-statistics/runs`, reports server progress, and loads bounded results from
`GET /api/bivariate-statistics/runs/{run_id}/results`. Pair construction, limits, calculations,
storage, and ranking remain backend responsibilities.

## Acceptance

The page blocks execution when upstream filtering is incomplete, empty, stale, or over the configured
pair limit. It prevents duplicate runs, represents empty and partial results explicitly, and provides
accessible tabular output on desktop and a usable responsive representation on narrow screens.
