# Workflow module boundaries

## Table of contents

- [Purpose](#purpose)
- [Physical layout](#physical-layout)
- [Contracts](#contracts)
- [Dependency rules](#dependency-rules)
- [Adding a module](#adding-a-module)

## Purpose

Portfell is one deployable application with four physically separated feature modules. The
separation prevents routine work on one analytical stage from silently changing another stage's
HTTP or UI behavior. One process and one application database remain sufficient; module isolation
does not require four containers.

## Physical layout

```text
src/portfell/modules/
├── metadata/       # /api/metadata/*
├── univariate/     # /api/univariate/*
├── bivariate/      # /api/bivariate/*
├── multivariate/   # /api/multivariate/*
├── http.py         # transport-only error/value helpers
└── runtime.py      # capability-restricted module service registry

src/portfell/dash_app/pages/
├── metadata.py
├── univariate.py
├── bivariate.py
└── multivariate.py
```

`hosted_api.py` is the only composition root. It creates the module registry, assigns one bounded
service facade to each API router and UI page, and mounts the application. A facade raises
`ModuleBoundaryError` when code tries to call an operation owned by another feature.

## Contracts

| Module | Browser route | API prefix | Persisted input | Persisted output |
| --- | --- | --- | --- | --- |
| Metadata | `/metadata` | `/api/metadata` | local market snapshot plus filter values | immutable Metadata universe ID |
| Univariate | `/univariate` | `/api/univariate` | Metadata universe ID | Univariate run and selection IDs |
| Bivariate | `/bivariate` | `/api/bivariate` | Univariate selection ID | Bivariate run ID and pair artifacts |
| Multivariate | `/multivariate` | `/api/multivariate` | Bivariate run ID | Multivariate run and decision artifacts |

Stage history and run-detail reads live below the owning module's `/runs` resource. There is no
generic `/api/runs` endpoint because it would erase ownership at the HTTP boundary. Shared
`/api/workflow` contains identifiers and readiness only; it is a coordinator read model, not a
fifth analytical module.

## Dependency rules

```text
MetadataUniverseId
        |
        v
UnivariateRunId -> UnivariateSelectionId
                           |
                           v
                    BivariateRunId
                           |
                           v
                   MultivariateRunId
```

- Feature packages must not import sibling feature packages.
- UI pages receive only their owning module facade.
- Cross-stage transitions belong to the workflow callback facade and pass persisted IDs.
- Dash code contains no SQL or financial calculations.
- Feature routers contain no database or UI imports.
- `architecture_checks.py` and `test_feature_module_boundaries.py` enforce these rules in the
  merge gate.

## Adding a module

Add a module only when it has a distinct immutable input and output contract. Create its package,
API router, restricted facade capability set, Dash page, documentation sidecar, and negative
boundary tests. Register it only in `hosted_api.py`. Downstream modules must consume the new
module's persisted output ID rather than importing its implementation or reading browser state.
