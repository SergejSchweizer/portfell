# Metadata Filter page

- Route: `/metadata-filter`
- Page ID: `metadata_filter`
- Component: `apps/web/src/pages/metadata-filter.tsx`

## Purpose

Refresh listing metadata and create a server-owned project selection from it.

## Inputs and actions

The first white panel owns listing-metadata refresh: EODHD key, saved-key state, determinate exchange progress, status text, and `Fetch all metadata`. The Metadata Filter panel follows it and exposes exchange, instrument type, country, currency, and name filters.

After a successful `Apply metadata filter` response, the browser dispatches the server-owned workflow refresh and navigates to `/univariate-statistics`. Quote fetching belongs to that next stage.

## States

Idle, metadata-fetching, metadata-fetch-failed, filtering, selection-ready, metadata-empty, and metadata-unavailable states must be explicit. A metadata refresh invalidates and reloads the available filter options.

The selected project is shown in the persistent sidebar. A project switch, or
opening this page after a switch, loads the saved server-owned filter values and listing count.

## Acceptance

The metadata panel precedes the filter dropdowns in document order. Metadata refresh remains disabled without an entered or saved key. All fields have visible labels, status changes use `aria-live`, and no filtering or ingestion business logic is implemented in the browser.
