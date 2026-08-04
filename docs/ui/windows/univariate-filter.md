# Univariate Filter page

- Route: `/univariate-filter`
- Page ID: `univariate_filter`
- Component: `apps/web/src/pages/univariate-filter.tsx`

## Purpose

Apply server-owned thresholds to the latest univariate-statistics result and persist the resulting project selection.

## Contract

The page loads available metrics and current values, collects filter thresholds, submits them to the API, and renders the retained and rejected counts returned by the server. It must not implement statistical filtering rules independently in the browser.

## Acceptance

Missing upstream statistics produce a clear empty state. Invalid thresholds are rejected visibly. Submission is idempotent from the user perspective, duplicate running actions are disabled, and stale results are cleared when inputs change.
