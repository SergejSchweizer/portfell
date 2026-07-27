# Projects Window

## Identity

- Route: `/projects`
- Funnel stage: none
- Shared layout: authenticated header and footer

## Purpose

Create, find, inspect, rename, archive, and reopen user-owned research projects while preserving immutable snapshot, universe, selection, and analysis references.

## Server-owned inputs

Bounded project list, ownership-safe project summaries, current snapshot, latest funnel stage, warning state, created and updated timestamps, and archive status.

## Layout and states

Provide project table or cards, search and sort, create action, project status, latest activity, current funnel position, warning indicators, and empty/loading/error states.

## User actions

Create, open, rename, archive, restore, and select a current project. Destructive or state-changing actions require explicit confirmation where appropriate.

## Acceptance

- [ ] Users can access only their own projects through list, search, direct route, and action endpoints.
- [ ] Opening or refreshing a project does not duplicate snapshots, selections, or analyses.
- [ ] Renaming does not change immutable analytical identities.
- [ ] Archived projects are excluded by default but remain recoverable according to policy.
- [ ] Large project lists remain usable with stable ordering and bounded pagination.

## Security

Opaque project ids are not sufficient without authenticated ownership. Error messages and autocomplete do not disclose other users' project names or activity.

## Components and tests

Use approved DataTable, SearchField, SortControl, StatusBadge, ConfirmDialog, EmptyState, and Pagination components. Cover empty, multiple-project, archived, stale, and unauthorized fixtures.
