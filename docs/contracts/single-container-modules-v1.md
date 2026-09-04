# Single-container module contract v1

## Table of contents

- [Purpose](#purpose)
- [Runtime topology](#runtime-topology)
- [Internal module boundaries](#internal-module-boundaries)
- [Persistence and hand-off](#persistence-and-hand-off)
- [Forbidden topology](#forbidden-topology)
- [Acceptance gate](#acceptance-gate)

## Purpose

Portfell is deployed as one Application container. The four analytical
modules remain independently owned in source code and are composed in-process;
the boundary is an architectural boundary, not a container boundary.

## Runtime topology

```text
Browser :8080
    |
    v
+----------------------------------------------+
| portfell-app (one Application container)     |
|                                              |
|  Gateway shell                               |
|    +-- Metadata module                       |
|    +-- Univariate module                     |
|    +-- Bivariate module                      |
|    +-- Multivariate module                   |
|                                              |
|  one composition root                        |
+----------------------+-----------------------+
                       |
          +------------+-------------+
          v                          v
  PostgreSQL portfell_dash   read-only market share
```

`compose.yaml` is the sole supported deployment definition. It contains one
Application service (`portfell-app`) and one PostgreSQL service. Only the
Application service publishes port 8080.

## Internal module boundaries

| Module | Browser route | REST prefix | Owns |
| --- | --- | --- | --- |
| Metadata | `/metadata` | `/api/metadata` | metadata filters and universe IDs |
| Univariate | `/univariate` | `/api/univariate` | univariate runs and selections |
| Bivariate | `/bivariate` | `/api/bivariate` | pair statistics and artifacts |
| Multivariate | `/multivariate` | `/api/multivariate` | optimizer runs and decisions |

Each module receives a typed port/facade from the composition root. A module
may not import or invoke a sibling implementation. Cross-module hand-off uses
only typed IDs, immutable persisted artifacts and the bounded workflow DTO.
The gateway owns routing, shell presentation, health and workflow projection;
it owns no analytical calculations or rows.

## Persistence and hand-off

PostgreSQL is the workflow authority. The local market share is a read-only
input plane. Connections are opened once by the composition root and passed to
repositories through typed adapters; callbacks never execute SQL directly.

```text
metadata_universe_id
        |
        v
univariate_run_id -> univariate_selection_id -> bivariate_run_id
                                                     |
                                                     v
                                            multivariate_run_id
```

## Forbidden topology

- a second Application container or alternate module Compose profile;
- a module-to-module HTTP call or sibling implementation import;
- cross-module schema writes, dual writes or mutable global hand-off state;
- complete analytical row sets in REST payloads;
- an unpublished artifact or an in-memory result as workflow authority.

## Acceptance gate

The contract is valid only when `docker compose -f compose.yaml config` shows
exactly `api` and `postgres`, all four routes are reachable from that one API
process, and the repository quality gate passes with at least 92% coverage.
