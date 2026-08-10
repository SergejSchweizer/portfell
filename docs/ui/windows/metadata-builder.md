# Metadata Builder page

- Route: `/metadata-builder`
- Page ID: `metadata_builder`
- Component: `apps/web/src/pages/metadata-builder.tsx`

## Purpose

Download listing metadata, create a server-owned project selection, and perform that project's
initial historical-data download. This is the Metadata Builder module's only browser page; its
output is the persisted selection and completed quote run consumed by Univariate Statistics.

## Inputs and actions

The persistent header owns the EODHD key and saved-key state. The first white panel owns `Fetch all metadata`, its determinate exchange progress, and all metadata-fetch status messages. Metadata rows and completed-exchange coverage persist in the server-owned lake; later automatic refreshes query the exchange registry and download only exchange listings not yet covered. The Metadata Builder panel follows it and exposes exchange, instrument type, country, currency, and name filters. The `Download Historical Data` panel follows the builder and starts the server-owned quotes, dividends, splits, and Silver-data run for the current project's selection.

After a successful `Create new project` response, the historical-download panel becomes available. Its action sends only the server-owned selection id, restores an existing run after reload or project switch, disables duplicate starts while running, and polls the server-provided progress. The status line and button show completed listings, percentage, and a client-side estimate derived from the server `started_at`, `completed`, and `total` fields. Statistical calculations belong to later modules.

## States

Idle, metadata-fetching, metadata-fetch-failed, filtering, selection-ready, historical-download-running, historical-download-failed, metadata-empty, and metadata-unavailable states must be explicit. A metadata refresh invalidates and reloads the available filter options.

The selected project is shown in the persistent sidebar. A project switch, or
opening this page after a switch, loads the saved server-owned filter values and listing count.

## Acceptance

The metadata action panel precedes the filter dropdowns, and the historical-download panel follows the Metadata Builder panel, in document order. Metadata refresh remains disabled without an entered or saved header key; the historical download remains disabled until a project selection exists. All fields have visible labels, status changes use `aria-live`, and no filtering or ingestion business logic is implemented in the browser.

The stateful two-project browser journey creates two selections through this
form and verifies that their saved metadata builders are restored after a
project switch.
