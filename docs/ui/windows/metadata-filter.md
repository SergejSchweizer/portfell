# Metadata Filter page

- Route: `/metadata-filter`
- Page ID: `metadata_filter`
- Component: `apps/web/src/pages/metadata-filter.tsx`

## Purpose

Create a server-owned project selection from listing metadata, then fetch historical quotes for that selection.

## Inputs and actions

The page exposes exchange, instrument type, country, currency, and name filters. `Apply metadata filter` creates the selection through the server. After a valid project exists, the page shows quote-fetch progress, status text, and a right-aligned `Fetch quotes` action beneath the progress indicator.

The persistent header fetches listing metadata. While that request is active, it
shows a narrow determinate progress bar directly below the EODHD key input. The
browser polls the metadata-run status endpoint and renders its real completed
exchange count and percentage.

`Fetch quotes` calls `/api/quote-runs` with the persisted metadata selection id. The server returns
`total`, `completed`, `failed`, and `percent` progress values. Duplicate submission is disabled while
the operation is running. The page polls the quote-run status endpoint and renders those values as a determinate progress bar and provider-task count.

## States

Idle, filtering, selection-ready, quote-running, quote-complete, quote-failed, metadata-empty, and metadata-unavailable states must be explicit. A metadata refresh invalidates and reloads the available filter options.

The selected project is shown in the persistent sidebar. A project switch clears
the transient project/selection ids and quote progress before this page requests
replacement server-owned state; entered filter values remain available for the
next project-specific submission.

## Acceptance

The progress indicator precedes the quote action in document order. The action remains disabled until a project selection exists. All fields have visible labels, status changes use `aria-live`, and no filtering or ingestion business logic is implemented in the browser.
