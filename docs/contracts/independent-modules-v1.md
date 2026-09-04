# Independent module contract v1

## Table of contents

- [Purpose](#purpose)
- [Runtime topology](#runtime-topology)
- [Module ownership](#module-ownership)
- [PostgreSQL hand-off](#postgresql-hand-off)
- [Shared data share](#shared-data-share)
- [Allowed dependencies](#allowed-dependencies)
- [Forbidden dependencies](#forbidden-dependencies)
- [Gateway boundary](#gateway-boundary)
- [Compatibility and migration](#compatibility-and-migration)

## Purpose

This contract freezes the boundaries required to evolve Portfell from one
modular monolith into four independently deployable analytical applications.
The modules share PostgreSQL and a read-oriented immutable data share. They do
not share in-process mutable state or call one another's implementation code.

The contract is architectural authority for PR407–PR427. A later change must
add a versioned contract instead of silently widening a boundary.

## Runtime topology

```text
Browser
   |
   v
Workflow gateway
   |
   +--> Metadata application     /metadata     /api/metadata/*
   +--> Univariate application   /univariate   /api/univariate/*
   +--> Bivariate application    /bivariate    /api/bivariate/*
   +--> Multivariate application /multivariate /api/multivariate/*

All applications
   +--> PostgreSQL: portfell_dash
   +--> immutable shared data share
```

The gateway is the only public HTTP entrypoint in the independent-process
topology. Each application can still be started and health-checked in
isolation after its prerequisite artifacts have been published.

## Module ownership

| Module | Browser route | REST prefix | Input authority | Published output | PostgreSQL owner | Data-share owner |
| --- | --- | --- | --- | --- | --- | --- |
| Metadata | `/metadata` | `/api/metadata` | local market snapshot | `metadata_universe_id` | `metadata` | `market/` and `metadata/` |
| Univariate | `/univariate` | `/api/univariate` | `metadata_universe_id` | `univariate_run_id`, `univariate_selection_id` | `univariate` | `univariate/` |
| Bivariate | `/bivariate` | `/api/bivariate` | `univariate_selection_id` | `bivariate_run_id` | `bivariate` | `bivariate/` |
| Multivariate | `/multivariate` | `/api/multivariate` | `bivariate_run_id` | `multivariate_run_id`, decision ID | `multivariate` | `multivariate/` |

The gateway owns only the bounded workflow read projection and presentation
preferences. It owns no analytical rows, matrices, metrics or portfolio
weights.

## PostgreSQL hand-off

The only cross-module hand-off is a persisted identifier and its immutable
lineage:

```text
metadata_universe_id
        |
        v
univariate_run_id -> univariate_selection_id
                              |
                              v
                       bivariate_run_id
                              |
                              v
                      multivariate_run_id
```

Run records contain `run_id`, `stage`, `status`, `input_ref`,
`input_snapshot_id`, `algorithm_version`, timestamps and a typed failure code.
An input ID is accepted only when the referenced upstream run/artifact is
published, immutable and belongs to the expected stage.

REST payloads may contain IDs, filter predicates and bounded control values.
They must never contain complete quote, dividend, metric, pair, matrix or
portfolio row sets.

## Shared data share

Large data is exchanged by immutable, content-addressed artifacts:

```text
/shared/portfell/
├── market/
├── metadata/
├── univariate/
├── bivariate/
└── multivariate/
```

Each artifact has an `artifact_id`, owner, schema version, content hash, byte
size, row count, publication timestamp and `published` status in PostgreSQL.
Writers publish through a temporary path followed by an atomic replacement.
Readers accept only a matching published manifest and never read temporary,
unhashed or cross-owner paths.

## Allowed dependencies

The dependency direction is strictly downstream:

```text
Metadata -> Univariate -> Bivariate -> Multivariate
```

- A module may import `portfell_contracts` and stage-neutral runtime utilities.
- A module may read published upstream IDs/artifacts through a typed repository
  interface.
- A module may write only its own PostgreSQL schema and data-share namespace.
- The gateway may read the bounded workflow projection from PostgreSQL.
- The shared UI shell may use presentation DTOs but not analytical internals.

## Forbidden dependencies

The following are contract violations:

- a sibling implementation import or direct sibling Python call;
- one analytical module calling another module's REST endpoint;
- a cross-module database write, delete or migration;
- a read of an unpublished or unverified data-share artifact;
- complete analytical data in a REST hand-off;
- browser storage as financial or workflow authority;
- a gateway calculation of metrics, pairs, risk, weights or returns;
- a generic `/api/runs` endpoint that removes stage ownership;
- a compatibility fallback to the former monolithic service after cutover.

## Gateway boundary

The gateway may perform routing, authentication, health aggregation, bounded
workflow reads and shared navigation rendering. It may not submit analytical
work except by inserting an ID-only workflow command in PostgreSQL. It may not
read market data or analytical artifacts merely to render navigation.

## Compatibility and migration

PR407 freezes this contract only. PR408–PR411 provide the shared contracts,
storage and command infrastructure. PR412–PR419 extract and test the four
applications. PR420–PR422 provide gateway, Compose and least-privilege
deployment. PR423–PR427 prove integration, browser behavior, resilience and
remove the monolith.

Until PR427 passes, the current single-process runtime remains the active
implementation. No compatibility path may be introduced that changes the
contract above.
