# Workflow module boundaries

Last reviewed: 2026-10-03

Portfell is one deployable FastAPI + Plotly Dash application with four physically separated
feature modules. Module separation is enforced in Python and at the HTTP boundary; it does
not require one container per module.

## Physical layout

```text
src/portfell/modules/
├── metadata/       # /api/metadata/*
├── univariate/     # /api/univariate/*
├── bivariate/      # /api/bivariate/*
├── multivariate/   # /api/multivariate/*
├── http.py         # transport helpers
└── runtime.py      # restricted service registry

src/portfell/dash_app/pages/
├── metadata.py
├── univariate.py
├── bivariate.py
└── multivariate.py
```

## Current contracts

| Module | Browser route | API prefix | Input | Output |
| --- | --- | --- | --- | --- |
| Metadata | `/metadata` | `/api/metadata` | market snapshot and filters | Metadata universe |
| Univariate | `/univariate` | `/api/univariate` | Metadata universe | Univariate run/selection |
| Bivariate | `/bivariate` | `/api/bivariate` | Univariate selection | Bivariate run/artifacts |
| Multivariate | `/multivariate` | `/api/multivariate` | Bivariate run | Multivariate decision |

There is no generic `/api/runs` endpoint. Shared workflow reads expose readiness and IDs only;
run history and run-detail resources remain owned by the module that creates them.

## Dependency rules

- Feature packages do not import sibling feature packages.
- Each page receives only its owning module facade.
- Cross-stage transitions pass persisted IDs through the workflow coordinator.
- Feature routers contain no database or UI imports; Dash pages contain no SQL.
- Architecture checks and module-boundary tests enforce these rules.
