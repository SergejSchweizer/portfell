# Shared Contracts v1

## Contents

- [Purpose](#purpose)
- [Contract surface](#contract-surface)
- [Migration rule](#migration-rule)
- [Compatibility](#compatibility)

## Purpose

`portfell_contracts` is the stage-neutral value-object package used at process
boundaries. It has no Dash, FastAPI, PostgreSQL, market-data, numerical, or
financial-calculation dependency.

## Contract surface

The package owns typed stage identifiers, `Stage`, `JobStatus`, and
`ArtifactStatus`, plus the serializable `ArtifactManifest`, `JobProgress`,
`PublicError`, and `WorkflowProjection` DTOs. Every DTO carries
`contract_version="1"` and emits a deterministic JSON-compatible document.

```
metadata_universe_id -> univariate_run_id / selection_id
                                  |
                                  v
                           bivariate_run_id
                                  |
                                  v
                          multivariate_run_id
```

## Migration rule

New boundary code imports from `portfell_contracts`. Existing internal
`portfell.app_state` records remain temporarily owned by the application-state
adapter and must be migrated by a dedicated PR; they must not be duplicated as
aliases in this package. A migration PR must preserve field names and add a
round-trip contract test before changing a caller.

## Compatibility

Unknown contract versions and unsafe public-error context are rejected at
construction time. Paths in manifests are POSIX-relative and cannot escape the
shared data root.
