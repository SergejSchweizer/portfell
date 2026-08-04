# Metadata Filter page

- Route: `/metadata-filter`
- Page ID: `metadata_filter`
- Component: `apps/web/src/pages/metadata-filter.tsx`

## Purpose

Create a server-owned project selection from listing metadata, then fetch historical quotes for that selection.

## Inputs and actions

The page exposes exchange, instrument type, country, currency, and name filters. `Apply metadata filter` creates the selection through the server. After a valid project exists, the page shows quote-fetch progress, status text, and a right-aligned `Fetch quotes` action beneath the progress indicator.

`Fetch quotes` calls `/api/data/load-selected-isins` with the selected `project_id`. Duplicate submission is disabled while the operation is running.

## States

Idle, filtering, selection-ready, quote-running, quote-complete, quote-failed, metadata-empty, and metadata-unavailable states must be explicit. A metadata refresh invalidates and reloads the available filter options.

## Acceptance

The progress indicator precedes the quote action in document order. The action remains disabled until a project selection exists. All fields have visible labels, status changes use `aria-live`, and no filtering or ingestion business logic is implemented in the browser.
