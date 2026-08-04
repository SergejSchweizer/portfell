# Univariate Statistics page

- Route: `/univariate-statistics`
- Page ID: `univariate_statistics`
- Component: `apps/web/src/pages/univariate-statistics.tsx`

## Purpose

Run and present server-computed univariate statistics for the active project after quote data is available.

## Contract

The page requests the active project state, starts the univariate-statistics workflow through the API, renders running, empty, success, and failure states, and displays returned statistics without recomputing them in React.

## Acceptance

The primary action is disabled when prerequisites are missing or a run is active. Results use typed contracts, accessible table semantics, stable loading feedback, and a clear upstream-data requirement.
