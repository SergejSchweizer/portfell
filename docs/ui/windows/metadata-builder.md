# Metadata Builder page


## Table Of Contents

- [Purpose](#purpose)
- [Inputs and actions](#inputs-and-actions)
- [States](#states)
- [Acceptance](#acceptance)

- Route: `/metadata-builder`
- Page ID: `metadata_builder`
- Component: `apps/web/src/pages/metadata-builder.tsx`

## Purpose

Download listing metadata, create a server-owned project selection, and perform that project's
initial historical-data download. This is the Metadata Builder module's only browser page; its
output is the persisted selection and completed quote run consumed by Univariate Statistics.

## Inputs and actions

The persistent header owns the EODHD key and saved-key state. The first white panel owns `Fetch all metadata`, its determinate exchange progress, and all metadata-fetch status messages. Metadata rows and completed-exchange coverage persist in the server-owned lake; later automatic refreshes query the exchange registry and download only exchange listings not yet covered. The Metadata Builder panel follows it and exposes exchange, instrument type, country, currency, and name filters. Its `Create new project` action starts the server-owned quotes, dividends, splits, and Silver-data run for the current project's selection.

After a successful `Create new project` response, that action button becomes the initial-fill status surface. It restores an existing run after reload or project switch, disables duplicate starts while running, and polls the server-provided progress. While running it shows completed listings and a client-side estimate derived from the server `started_at`, `last_progress_at`, `completed`, and `total` fields. When server-side listing progress is stale, it shows a stable provider-wait state instead of increasing the estimate. Statistical calculations belong to later modules.

When an initial fill fails, the action changes to `Quote load failed - Retry quote load`. Submitting the
unchanged selection requeues that project's failed server-owned job, resets visible progress, and resumes
the normal planning and running states. It does not create a second project or duplicate the frozen
selection.

## States

Idle, metadata-fetching, metadata-fetch-failed, filtering, selection-ready, historical-download-running, historical-download-failed, metadata-empty, and metadata-unavailable states must be explicit. A metadata refresh invalidates and reloads the available filter options.

The selected project is shown in the persistent sidebar. A project switch, or
opening this page after a switch, loads the saved server-owned filter values and listing count.

## Acceptance

The metadata action panel precedes the filter dropdowns. Metadata refresh remains disabled without an entered or saved header key; the project action is disabled while its initial historical-data fill is active. All fields have visible labels, status changes use `aria-live`, and no filtering or ingestion business logic is implemented in the browser.

The stateful two-project browser journey creates two selections through this
form and verifies that their saved metadata builders are restored after a
project switch.
