# Univariate Filter page

- Route: `/univariate-filter`
- Page ID: `univariate_filter`
- Component: `apps/web/src/pages/univariate-filter.tsx`

## Purpose

Apply server-owned thresholds to the latest univariate-statistics result and persist the resulting project selection.

## Contract

The page loads `GET /api/univariate-filter/metrics`, collects ordered numerical predicates, and submits
them to `POST /api/univariate-filter` with the completed source run id. It renders retained and rejected
counts plus bounded results from `GET /api/univariate-filter/{selection_id}/results`. Statistical
filtering rules remain server-owned.

The persistent project sidebar identifies the active project and canonical
workflow hierarchy. After a project switch, this page clears local persisted
selection, table, and message state before reloading server-owned workflow
status; the in-progress predicate draft remains an interaction-only draft.

## Acceptance

Missing or stale upstream statistics produce a locked state. Invalid thresholds are rejected visibly.
Predicates use AND semantics, submission is idempotent, and stale results are cleared immediately when
an input changes.

The stateful two-project browser journey changes every predicate field, adds
and removes a predicate, submits the filter, and asserts the returned result
summary.
