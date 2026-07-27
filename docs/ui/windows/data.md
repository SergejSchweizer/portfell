# Data Window

## Identity

- Route: `/projects/:projectId/data`
- Funnel stage: Data
- Shared layout: authenticated header and footer

## Purpose

Show the user's entitled market-data coverage, plan and run provider-backed refreshes, communicate credential and quota constraints, and publish an immutable User Data Snapshot.

## Server-owned inputs

Credential status, provider capability, visible datasets, listing and date coverage, quality warnings, refresh plan, run progress, partial failures, quota information, and resulting snapshot reference.

## Layout and states

Provide coverage summary, dataset table, refresh-planning panel, run progress, result summary, snapshot identity, warnings, and empty/loading/running/partial-failure/failed/complete/stale states.

## User actions

Inspect coverage, request a refresh plan, confirm a provider call, monitor or resume a run, retry permitted failures, and continue to Metadata after successful snapshot publication.

## Acceptance

- [ ] A new user sees zero entitled data before their own successful provider-backed refresh.
- [ ] Physical shared-data existence never appears as user-visible access.
- [ ] Partial or failed runs cannot grant unreturned observations.
- [ ] Refresh and navigation resume the existing run instead of submitting duplicates.
- [ ] Exact visible date range, listing count, warnings, and resulting snapshot are shown.

## Security

Provider keys, request headers, raw provider bodies, internal storage paths, shared object ids, and other users' coverage are never rendered. All actions require authenticated entitlement-aware API routes.

## Components and tests

Use approved CoverageCard, DatasetTable, RefreshPlan, ProgressPanel, SnapshotBadge, WarningList, and ErrorSummary components. Cover Free, paid, invalid credential, quota, partial failure, correction, retry, and success fixtures.
