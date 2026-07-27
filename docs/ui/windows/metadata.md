# Metadata Window

## Identity

- Route: `/projects/:projectId/metadata`
- Funnel stage: Metadata
- Shared layout: authenticated header and footer

## Purpose

Search and filter the user's entitled instrument metadata and create a versioned eligible universe for downstream analysis.

## Server-owned inputs

User Data Snapshot, searchable metadata rows, facets, counts, data-quality eligibility, stable sort keys, pagination cursors, current filter definition, and universe versions.

## Layout and states

Provide snapshot context, search, facets, filter summary, visible-versus-eligible counts, configurable table, bulk selection, quality exclusions, create-universe action, and loading/empty/no-result/error/stale states.

## User actions

Search, combine facets, sort, paginate or virtualize, configure columns, select across pages, inspect exclusions, save a versioned universe, and reopen prior universe versions.

## Acceptance

- [ ] Search, facets, autocomplete, counts, and rows use only the authenticated user's snapshot.
- [ ] Combined filters serialize canonically and produce stable ordered membership.
- [ ] Bulk selection across pages is explicit and reproducible.
- [ ] The UI shows `visible instruments -> eligible instruments` and the exact source snapshot.
- [ ] Reapplying an unchanged filter reuses the same logical universe identity.

## Security

No count, facet, autocomplete result, export, or error message may reveal instruments, dates, revisions, or coverage outside the user's entitlement.

## Components and tests

Use approved SearchField, FacetPanel, FilterChips, DataTable, ColumnSelector, BulkSelectionBar, EligibilityBadge, Pagination, and SaveUniverseDialog components. Cover thousands of rows, no results, combined facets, quality exclusions, and stale snapshot fixtures.
