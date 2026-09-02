# Callback Contracts

## Table Of Contents

- [Purpose](#purpose)
- [Metadata Page Filter Contract](#metadata-page-filter-contract)
- [Update Sequence](#update-sequence)
- [Acceptance Criteria](#acceptance-criteria)

## Purpose

This sidecar defines the UI callback guarantees for Portfell. Callbacks update the
smallest relevant Dash regions while keeping the browser presentation consistent
with the persisted project and its current selections.

## Metadata Page Filter Contract

The Metadata Builder page has four filter dropdowns:

```text
Exchange · Instrument Type · Country · Currency
```

When the user changes any dropdown, the callback must immediately persist the
complete four-field selection in browser state and rerender every dependent region
from that same selection:

```text
dropdown change
      |
      v
complete metadata filter state
      |
      +--> all numeric fields
      +--> Instrument Type / Country / Currency plots
      +--> filtered listings table
```

The numeric fields, plots, and table must all represent the selected project and
the new filter values. A response that updates only one region, mixes old and new
filter values, or displays the unfiltered project is a contract violation.

An empty dropdown value means “all values” for that dimension. Clearing one field
must not clear the other three. Filter options themselves must be derived from the
selected project, not from another project or the global market source.

## Update Sequence

1. Dash receives a dropdown value change.
2. The callback normalizes all four values, retaining unchanged values.
3. The normalized selection is written to `BrowserState.metadata_filters`.
4. The current project is resolved by its opaque project id.
5. Numeric summaries, distributions, and listing rows are recomputed from that
   project plus the normalized filters.
6. One render response updates all dependent UI regions.

Callbacks must not issue market-database reads or mutate project definitions. They
may read the typed application-service view for the selected project. If the update
fails, the UI must retain the last consistent state and show an explicit failure
status rather than partially replacing the page.

## Acceptance Criteria

- Selecting any Exchange, Instrument Type, Country, or Currency value updates all
  numeric fields, all three distribution plots, and the listings table immediately.
- The displayed values are calculated from the selected project and selected
  filters, with no stale values from the previous selection.
- Changing one dropdown preserves the other three selections.
- Clearing a dropdown restores that dimension to “all values” while retaining the
  remaining filters.
- Switching projects resets incompatible filter values and reloads that project's
  numeric fields, plots, table, and available options.
- The callback does not call external market PostgreSQL and does not start a
  computation job.
- A failed callback leaves the last coherent UI state intact and exposes an error
  status.
