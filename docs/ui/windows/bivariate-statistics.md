# Bivariate Statistics page

- Route: `/bivariate-statistics`
- Page ID: `bivariate_statistics`
- Component: `apps/web/src/pages/bivariate-statistics.tsx`

## Purpose

Run and present server-computed pairwise statistics for the selection produced by the univariate filter.

## Contract

The page starts the bivariate workflow, reports progress and failures, and renders returned pairwise results using typed API contracts. Pair construction, correlation calculations, storage layout, and ranking remain backend responsibilities.

## Acceptance

The page blocks execution when upstream filtering is incomplete, prevents duplicate runs, represents empty and partial results explicitly, and provides accessible tabular output on desktop and a usable responsive representation on narrow screens.
