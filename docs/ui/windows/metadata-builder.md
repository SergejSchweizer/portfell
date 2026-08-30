Each non-empty exchange, instrument type, country, and currency option includes its server-computed
count of unique catalog ISINs.
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

Create a server-owned project selection from the read-only market catalogue. This is the Metadata
Builder module's only browser page; its output is the persisted selection consumed by Univariate
Statistics.

## Inputs and actions

The Metadata Builder panel exposes exchange, instrument type, country, currency, and name filters from
the server-owned, read-only market catalogue. Its `Create new project` action persists the frozen
selection. Statistical calculations read the selected market data directly in later modules.

## States

Filtering, selection-ready, metadata-empty, and metadata-unavailable states must be explicit.

The selected project is shown in the persistent sidebar. A project switch, or
opening this page after a switch, loads the saved server-owned filter values and listing count.

## Acceptance

The metadata action panel precedes the filter dropdowns. Metadata refresh displays its exchange progress and remains disabled from the initial request until the fetch reaches a terminal state. The project action is disabled before metadata is available, then shows project creation, planning, and quote-loading status and remains disabled from submission through the initial historical-data fill. The required real-stack gate proves the XETRA, ETF, Germany, EUR, and `UCITS ETF` selection can complete this hand-off before the user continues through all three statistics modules. All fields have visible labels, status changes use `aria-live`, and no filtering or ingestion business logic is implemented in the browser.

The stateful two-project browser journey creates two selections through this
form and verifies that their saved metadata builders are restored after a
project switch.
