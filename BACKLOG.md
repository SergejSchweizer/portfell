Last reviewed: 2026-08-29

# Active Backlog

## Status authority

This file is the operational index for the **Portfell XETRA PostgreSQL read-plane cutover and single-user simplification**.

Detailed Tasks / Acceptance, owned paths, parallelization, security, determinism, idempotency, and rollback are authoritative in:

- [`docs/backlog/postgres-loader-single-user-cutover.md`](docs/backlog/postgres-loader-single-user-cutover.md)

Older Portfell market-loading and EODHD backlog plans are superseded where they conflict with this file. Historical files under `docs/backlog/archive/` remain evidence only.

## Target architecture

```text
SergejSchweizer/xetra-loader
provider acquisition -> validated XETRA data
  |
  v
PostgreSQL 10.10.1.3:54321
  schema: xetra_loader
  tables: listings / eod_quotes / dividends / splits
  |
  | SELECT only as portfell_app
  v
SergejSchweizer/portfell
Metadata -> Univariate -> Bivariate -> Multivariate -> portfolio optimization
```

Portfell contains **no EODHD/provider acquisition plane** after this series. It does not download XETRA metadata, quotes, dividends, or splits itself.

## Frozen PostgreSQL source contract

Market business schema:

- `xetra_loader.listings` — key `(isin, exchange, code)`;
- `xetra_loader.eod_quotes` — key `(isin, exchange, code, trade_date)`;
- `xetra_loader.dividends` — key `(isin, exchange, code, event_key)`;
- `xetra_loader.splits` — key `(isin, exchange, code, event_key)`.

Endpoint/configuration:

- production target endpoint: `10.10.1.3:54321`;
- Portfell runtime seam: `PORTFELL_MARKET_DATABASE_URL`;
- database name/password/full DSN are secret-supplied and never committed;
- production reader identity: `portfell_app`;
- all consumed PostgreSQL timestamps are timezone-aware UTC;
- `trade_date` remains a `DATE`;
- `timestamp_eod` is a canonical UTC midnight date anchor, not a claimed physical XETRA close timestamp;
- full listing identity `(isin, exchange, code)` is mandatory everywhere.

### `xetra_loader_sync` boundary

The database also contains loader control schema `xetra_loader_sync`, but it is **not a Portfell consumer schema**. Existing `xetra-loader` grants explicitly revoke `portfell_app` access to it.

Therefore Portfell must never query `xetra_loader_sync.sync_state` or `xetra_loader_sync.loader_runs`, must never request broader grants, and must never treat loader-internal run state as application evidence. Portfell derives only observational source status from accessible `xetra_loader` facts such as business-table reachability, row counts, `MAX(published_at_utc)`, and quote `MAX(trade_date)`.

## Hard removal invariant

At completion Portfell must not contain executable:

- EODHD client/token/endpoint/discovery/fetch logic;
- metadata/quote/dividend/split provider-download commands;
- provider credential storage/API/UI or provider-key encryption state;
- market-data Bronze/Silver/Gold writer pipeline;
- NAS/filesystem market-data fallback;
- shared market-data publisher/cache/refresh authority;
- market acquisition scheduler/worker/cron;
- market-data DML/DDL;
- fallback to another provider when PostgreSQL is unavailable.

A PostgreSQL failure or insufficient market history fails closed with typed source evidence.

## Single-user target

The existing single-user simplification remains active:

- one application workspace;
- no user/tenant/membership/project-membership/credential-owner security authority;
- saved analysis/portfolio/decision IDs may remain as domain identifiers but not security scopes;
- canonical browser routes exactly `/metadata`, `/univariate`, `/bivariate`, `/multivariate`;
- REST remains under `/api`.

## Weak-agent execution contract

Every implementation work order is small and atomic. Exact branch/work-order name must appear in branch, Conventional Commit scope, and PR title. Before editing, each agent records `git status --short --branch`. Sibling PRs start from the exact same merged predecessor SHA, own disjoint paths, and never branch from one another. `GATES.md` remains the sole quality/coverage authority. No agent may invent a compatibility layer, hidden provider feature flag, second market-data authority, or opportunistic refactor.

## Execution graph

```text
PR296 planning authority
        |
      PR308
        |
 PR309 || PR310 || PR311 || PR312 || PR313
        |
      PR314
        |
 PR315 || PR316 || PR317 || PR318
        |
      PR319
        |
 PR320 || PR321 || PR322 || PR323 || PR324 || PR325 || PR326
        |
      PR327 || PR328
        |
      PR329 || PR330 || PR331
        |
      PR332
        |
      PR333
        |
      PR334
```

Parallel waves are intentionally wide. With fewer agents, execute any sibling subset first but keep all siblings on the same predecessor SHA.

## Active Portfell work-order index

| Key | Branch | Depends on | Atomic outcome | Git status |
| --- | --- | --- | --- | --- |
| PR296 | `docs/pr296-postgres-loader-single-user-backlog` | current `main` | replace old EODHD/in-repo-loader plan with atomic `xetra_loader` PostgreSQL consumer plan | pushed; validation pending |
| PR308 | `refactor/pr308-xetra-postgres-read-contract` | PR296 | freeze exact external PostgreSQL DTO/config/read-only contract | not started; branch absent; blocked |
| PR309 | `feat/pr309-xetra-listings-repository` | PR308 | SELECT-only `xetra_loader.listings` repository | not started; branch absent; blocked |
| PR310 | `feat/pr310-xetra-quotes-repository` | PR308 | SELECT-only `xetra_loader.eod_quotes` repository | not started; branch absent; blocked |
| PR311 | `feat/pr311-xetra-dividends-repository` | PR308 | SELECT-only `xetra_loader.dividends` repository | not started; branch absent; blocked |
| PR312 | `feat/pr312-xetra-splits-repository` | PR308 | SELECT-only `xetra_loader.splits` repository | not started; branch absent; blocked |
| PR313 | `feat/pr313-xetra-source-status-read-model` | PR308 | observational business-table source status with zero sync-schema access | not started; branch absent; blocked |
| PR314 | `feat/pr314-xetra-market-gateway-integration` | PR309-PR313 | one typed read-only MarketDataGateway and direct-SQL architecture guard | not started; branch absent; blocked |
| PR315 | `refactor/pr315-metadata-stage-xetra-cutover` | PR314 | Metadata reads PostgreSQL listings only | not started; branch absent; blocked |
| PR316 | `refactor/pr316-univariate-stage-xetra-cutover` | PR314 | Univariate inputs use PostgreSQL gateway only | not started; branch absent; blocked |
| PR317 | `refactor/pr317-bivariate-stage-xetra-cutover` | PR314 | Bivariate histories use PostgreSQL gateway only | not started; branch absent; blocked |
| PR318 | `refactor/pr318-multivariate-stage-xetra-cutover` | PR314 | Multivariate/optimizer inputs use PostgreSQL gateway only | not started; branch absent; blocked |
| PR319 | `test/pr319-four-stage-xetra-read-integration-gate` | PR315-PR318 | prove all four analytics stages consume only the PostgreSQL gateway | not started; branch absent; blocked |
| PR320 | `refactor/pr320-delete-eodhd-provider-client-and-fetchers` | PR319 | delete EODHD HTTP/search/fetch/token/CLI acquisition surface | not started; branch absent; blocked |
| PR321 | `refactor/pr321-delete-portfell-market-medallion` | PR319 | delete Portfell Bronze/Silver/Gold market persistence pipeline | not started; branch absent; blocked |
| PR322 | `refactor/pr322-delete-portfell-market-filesystem-nas-plane` | PR319 | delete market filesystem/NAS paths and fallback authority | not started; branch absent; blocked |
| PR323 | `refactor/pr323-delete-portfell-market-refresh-scheduler` | PR319 | delete shared market refresh/publisher/scheduler authority | not started; branch absent; blocked |
| PR324 | `refactor/pr324-delete-hosted-market-download-jobs` | PR319 | delete hosted metadata/quote/download job APIs and workers | not started; branch absent; blocked |
| PR325 | `refactor/pr325-delete-provider-credential-backend` | PR319 | delete provider credential persistence/service/API | not started; branch absent; blocked |
| PR326 | `refactor/pr326-delete-provider-loading-ui` | PR319 | delete provider token/fetch/progress UI | not started; branch absent; blocked |
| PR327 | `refactor/pr327-single-user-backend-cutover` | PR320-PR326 | remove multi-user/project security/bootstrap backend | not started; branch absent; blocked |
| PR328 | `refactor/pr328-single-user-ui-route-cutover` | PR320-PR326 | remove project/user UI and expose four canonical routes | not started; branch absent; blocked |
| PR329 | `refactor/pr329-remove-provider-packaging-dependencies` | PR327+PR328 | prune provider/loading dependencies and package entrypoints | not started; branch absent; blocked |
| PR330 | `refactor/pr330-external-postgres-runtime-compose` | PR327+PR328 | production/E2E runtime uses external PostgreSQL and no provider secrets | not started; branch absent; blocked |
| PR331 | `docs/pr331-remove-eodhd-docs-and-governance` | PR327+PR328 | remove active EODHD docs/artifacts and enforce architecture guard | not started; branch absent; blocked |
| PR332 | `test/pr332-live-xetra-postgres-readonly-contract-gate` | PR329-PR331 + prepared external DB | prove live `10.10.1.3:54321` business-table contract and least privilege | not started; branch absent; blocked |
| PR333 | `test/pr333-full-postgres-source-replacement-e2e` | PR332 | prove complete EODHD-free four-stage application end-to-end | not started; branch absent; blocked |
| PR334 | `docs/pr334-production-postgres-cutover-runbook` | PR333 | executable production cutover/rollback without legacy acquisition | not started; branch absent; blocked |

The complete acceptance checklist for every PR above is in `docs/backlog/postgres-loader-single-user-cutover.md`; this index intentionally does not duplicate or weaken it.

## Superseded implementation branches

PR264-PR295 were designed around the old multi-project/in-repository market-loading architecture and remain historical/reference branches only. Do not merge them as-is and do not use their internal wave-base branches as predecessors for this series.

The earlier draft PR308-PR321 plan using schema `portfell_market`, repository name `xetra-data-loader`, or fictional XDL-PR handoff IDs is also superseded by this revision. The authoritative upstream repository is `SergejSchweizer/xetra-loader`, and Portfell consumes its existing `xetra_loader` schema contract directly through PostgreSQL.

## Completion gate

Portfell cutover is complete only when a clean final `main` proves:

- market source is PostgreSQL configured through `PORTFELL_MARKET_DATABASE_URL`, targeting `10.10.1.3:54321` in production;
- Metadata/Univariate/Bivariate/Multivariate read only via `MarketDataGateway` from `xetra_loader` business tables;
- `portfell_app` has SELECT-only access to those business tables and market mutation attempts fail;
- access to `xetra_loader_sync` fails for `portfell_app` and executable Portfell code never queries it;
- no EODHD/provider credential/client/fetch/download/progress surface remains;
- no market-data Bronze/Silver/Gold writer, NAS/filesystem fallback, publisher, refresh worker, or market cron remains;
- no provider/local fallback activates when PostgreSQL is unavailable or incomplete;
- analytical formula/optimizer semantics are preserved by source-cutover regression evidence;
- single-user backend/UI target and exactly four canonical routes are complete;
- production runtime requires no EODHD/provider secret and no market-data filesystem mount;
- PR332 live PostgreSQL contract gate passes;
- PR333 full source-replacement E2E passes;
- PR334 documents a production cutover and rollback that cannot reactivate legacy acquisition.
