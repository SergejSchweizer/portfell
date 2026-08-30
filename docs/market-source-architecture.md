# Portfell market-source architecture

Status: source-cutover contract for PR338. The authoritative executable plan remains `BACKLOG.md`.

This sidecar defines the one market-data authority that the Portfell runtime may
read. Start with the topology, then the database boundary, and finally the
snapshot and numerical rules. It intentionally does not duplicate the runtime
commands in `DOCKER.md`, the implementation plan in `BACKLOG.md`, or the
application-service contracts documented with their modules.

## Table Of Contents

- [1. Production Data Flow](#1-production-data-flow)
- [2. Database Authorities](#2-database-authorities)
- [3. Market Reader Role And Privilege Boundary](#3-market-reader-role-and-privilege-boundary)
- [4. Listing Identity](#4-listing-identity)
- [5. Coherent Snapshot Semantics](#5-coherent-snapshot-semantics)
- [6. Numeric And Date Projection](#6-numeric-and-date-projection)
- [7. SQL Ownership](#7-sql-ownership)
- [8. Transitional Browser And Application Database](#8-transitional-browser-and-application-database)
- [9. Final Topology Handoff](#9-final-topology-handoff)

## 1. Production Data Flow

```text
xetra-loader
    |
    | owns ingestion, synchronization, normalization, and publication
    v
external PostgreSQL 10.10.1.3:54321
  database xetra_loader
  schema   xetra_loader
  tables   listings, eod_quotes, dividends, splits
    |
    | SELECT only through the dedicated Portfell LOGIN role
    v
src/portfell/market_source/**
  repositories -> MarketDataGateway -> coherent MarketDataSnapshot
    |
    v
Metadata -> Univariate -> Bivariate -> Multivariate services
```

Portfell does not import the xetra-loader Python package and does not own a loader, refresh loop, provider client, medallion market store, NAS market cache, or market synchronization job. xetra-loader is a separately deployed upstream authority and is never defined as a Portfell Compose service.

## 2. Database Authorities

The source-cutover runtime has two independent PostgreSQL authorities. `PORTFELL_DATABASE_URL` addresses the transitional Portfell-owned application/control database. `PORTFELL_MARKET_DATABASE_URL` addresses the external xetra-loader market database. Neither URL may fall back to the other. Non-secret identities are validated against the gitignored repository-root `config.yaml`; passwords are supplied outside Git through separate secret-file references.

The current Portfell application database is transitional. It is not the final state model. PR344–PR360 replace it with a clean database named `portfell_dash`, schema `portfell`, and delete the old hosted/tenant/control-plane database after parity and clean-runtime QA. The external xetra-loader database survives that replacement unchanged.

## 3. Market Reader Role And Privilege Boundary

Portfell connects with a secret-supplied non-superuser LOGIN role. The LOGIN is a member of the NOLOGIN group role `portfell_app`. Startup/preflight verifies the role contract and rejects a superuser or a role without the required membership. The application receives SELECT capability for the exact four business tables only.

Access to `xetra_loader_sync` is forbidden. Failure to read that schema is expected PASS evidence in live and clean-runtime QA. Portfell must not receive DML/DDL capability on the market database; `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `ALTER`, `CREATE`, and `DROP` are outside the application contract.

## 4. Listing Identity

A market instrument is identified by the full tuple:

```text
(isin, exchange, code)
```

ISIN alone is never a Portfell business key. Duplicate ISINs across exchanges/codes remain distinct. New Metadata universes use only `listings.is_active = true`; an inactive full identity remains historically resolvable when it is part of persisted lineage.

## 5. Coherent Snapshot Semantics

Analytical input assembly runs under `REPEATABLE READ, READ ONLY` with UTC session semantics. `MarketDataGateway` materializes required listings, quotes, dividends, and splits inside that short transaction, then closes the database transaction before CPU-heavy analytics begin. Repository reads are batched at no more than 500 listing identities per SQL statement.

`MarketSourceSnapshot` is deterministic lineage over the semantic rows actually consumed. It excludes DSNs, passwords, observation wall-clock timestamps, provider/download identities, and synchronization internals. Metadata, Univariate, Bivariate, and Multivariate artifacts refer to source snapshot identity rather than a provider download run.

## 6. Numeric And Date Projection

PostgreSQL `NUMERIC` values remain Python `Decimal` through the raw repository boundary. Conversion to analytical numeric types occurs at the centralized projection boundary. PostgreSQL trade/event dates map to Python `date`; session semantics are UTC.

`adjusted_close` is authoritative for return, volatility, risk, and drawdown calculations. A missing adjusted close produces typed `missing_adjusted_close`; raw `close` is never a fallback. Dividend rows are separate income/distribution evidence and are not added again on top of adjusted-close total-return behavior. Split rows are preserved as source events; the source cutover does not invent a split-return adjustment formula.

## 7. SQL Ownership

Raw market SQL belongs only under:

```text
src/portfell/market_source/**
```

Dash/React callbacks, FastAPI route adapters, and analytical service modules do not execute market SQL directly. They consume typed application services and `MarketDataGateway` contracts.

## 8. Transitional Browser And Application Database

The current hand-written React/Vite/TypeScript/TanStack browser application is transitional. During source cutover it is frozen to the four canonical routes `/metadata`, `/univariate`, `/bivariate`, `/multivariate` and does not gain new product functionality. It is deleted after Plotly Dash parity in PR356.

The current Portfell-owned hosted PostgreSQL schema is likewise transitional. PR344 inventories it, PR345–PR347 introduce and adopt the clean `portfell_dash` application-state plane, PR357 deletes the old database adapters/schema, PR358 performs final Compose/runtime cutover, PR359 proves negative space and clean installation, and PR360 records final production acceptance and destructive removal.

## 9. Final Topology Handoff

The source series hands PR344–PR360 this invariant topology:

```text
Browser
  -> Plotly Dash (final replacement)
  -> FastAPI / typed Portfell services
       -> clean Portfell app-state PostgreSQL: portfell_dash / portfell
       -> external read-only market PostgreSQL: xetra_loader / xetra_loader
```

The two database authorities remain independent. Provider acquisition and Portfell-owned market refresh never return as rollback mechanisms.
