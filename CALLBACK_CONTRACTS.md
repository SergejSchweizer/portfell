# Callback Contracts

## Table of Contents

- [Purpose](#purpose)
- [Metadata Page Contract](#metadata-page-contract)
- [Callback Inventory](#callback-inventory)
- [Update Sequence](#update-sequence)
- [Acceptance Criteria](#acceptance-criteria)

## Purpose

This sidecar specifies the callback boundaries for the Metadata page. The page and
sidebar must be rendered from one browser-state snapshot and must use one canonical
metadata row per ISIN.

## Metadata Page Contract

The page exposes four filters:

```text
Exchange | Instrument type | Country | Currency
```

Each filter change persists the complete four-field selection in the local
`pf-browser-state` store and rerenders all dependent UI from that selection:

```text
dropdown change
      |
      v
complete metadata filter state
      +--> page selected-count KPI
      +--> sidebar Metadata count
      +--> cascading option counts
      +--> listing preview
      +--> full-universe distributions (unchanged)
```

All counts, options, previews, universes, and downstream inputs use unique ISINs;
listing aliases for the same ISIN are never counted separately. Distribution plots
describe the complete downloaded universe and intentionally remain independent of
transient dropdown filters.

## Callback Inventory

| Callback | Inputs | Contract |
| --- | --- | --- |
| Metadata filter update | Four `metadata-filter-*.value` inputs | Persist all four values and recalculate the unique selected-ISIN count. |
| State refresh | `pf-location.pathname` | Reload durable workflow state, preserve persisted filters, and recompute the same count. |
| Route renderer | `pf-location.pathname`, `pf-browser-state.data` | Render page and sidebar from one state snapshot. |
| Project selection (compatibility input) | `sidebar-project-selection.value` | Switch the opaque universe id and clear incompatible filters. |

The filter callback only reads the active-listing service view. It does not create a
universe, start an analysis job, or mutate project definitions.

## Update Sequence

1. Dash receives a filter value change.
2. The callback normalizes all four values, preserving the other dimensions.
3. The complete selection and unique-ISIN count are written to browser state.
4. The route renderer rebuilds the page and sidebar from that state.
5. Cascading options and filtered rows use the same canonical ISIN set.
6. Full-universe distributions remain unchanged.

## Acceptance Criteria

- The Metadata-page selected count and sidebar `Metadata` count are identical.
- Every ISIN appears at most once in all Metadata-page counts and previews.
- Dropdown option counts are unique-ISIN counts and include previous selections.
- Clearing one filter restores only that dimension to “all” and preserves the others.
- Filter changes do not alter full-universe distribution plots.
- Reloading the page preserves filters and reproduces the same counts.
- Callbacks do not create projects or start computation jobs.
- A callback failure preserves the last coherent browser state.
