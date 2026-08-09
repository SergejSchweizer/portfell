# Metadata Builder page

- Route: `/metadata-builder`
- Page ID: `metadata_builder`
- Component: `apps/web/src/pages/metadata-builder.tsx`

## Purpose

Download listing metadata and create a server-owned project selection from it. This is the
Metadata Builder module's only browser page; its output is the persisted selection consumed by
Univariate Statistics.

## Inputs and actions

The persistent header owns the EODHD key and saved-key state. The first white panel uses the same progress, status, and action layout as Download Historical Data, and owns `Fetch all metadata`, its determinate exchange progress, and all metadata-fetch status messages. Metadata rows and completed-exchange coverage persist in the server-owned lake; later automatic refreshes query the exchange registry and download only exchange listings not yet covered. The Metadata Builder panel follows it and exposes exchange, instrument type, country, currency, and name filters.

After a successful `Create new project` response, the browser dispatches the server-owned workflow refresh and navigates to `/univariate-statistics`. Quote fetching and all statistical calculations belong to later modules.

## States

Idle, metadata-fetching, metadata-fetch-failed, filtering, selection-ready, metadata-empty, and metadata-unavailable states must be explicit. A metadata refresh invalidates and reloads the available filter options.

The selected project is shown in the persistent sidebar. A project switch, or
opening this page after a switch, loads the saved server-owned filter values and listing count.

## Acceptance

The metadata action panel precedes the filter dropdowns in document order. Its progress, status, and action use the same order and controls as Download Historical Data. Metadata refresh remains disabled without an entered or saved header key. All fields have visible labels, status changes use `aria-live`, and no filtering or ingestion business logic is implemented in the browser.

The stateful two-project browser journey creates two selections through this
form and verifies that their saved metadata builders are restored after a
project switch.
