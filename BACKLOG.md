Last reviewed: 2026-08-22

# Active Backlog

## Status authority

This file is the operational index for the **Portfell PostgreSQL read-plane cutover and single-user simplification only**.

The Portfell implementation authority is:

- [`docs/backlog/postgres-loader-single-user-cutover.md`](docs/backlog/postgres-loader-single-user-cutover.md)

The XETRA loader implementation authority has moved to `SergejSchweizer/xetra-data-loader` -> `BACKLOG.md`.

The old loader work orders PR297-PR307 are superseded. The active loader plan is now `XDL-PR001` through `XDL-PR033`. Portfell never implements those work orders.

## Target architecture

```text
EODHD
  |
  v
SergejSchweizer/xetra-data-loader
  Bronze -> Silver -> Gold
  |
  v
PostgreSQL 10.10.1.3:54321
  schema: portfell_market
  |
  | SELECT only
  v
SergejSchweizer/portfell
  Metadata -> Univariate -> Bivariate -> Multivariate -> portfolio optimization
```

Ownership boundary:

- `xetra-data-loader` owns provider access, XETRA discovery, Bronze/Silver/Gold, PostgreSQL DDL/publication/sync state, Sunday 11:00 Vienna schedule, initial complete database load, and production PostgreSQL verification.
- `portfell` owns read-only PostgreSQL gateways, analytics, portfolio optimization, one single-user workspace, and presentation.

Portfell must not contain EODHD credentials/client code, download jobs, medallion market-data persistence, PostgreSQL market-data writers, market-data cron jobs, filesystem/NAS fallbacks, users/tenants/memberships, or project-scoped authorization.

## Frozen shared contract

Portfell depends on these externally observable facts from `xetra-data-loader`:

- PostgreSQL endpoint: `10.10.1.3:54321`, supplied through configuration/secrets; passwords/full DSNs are never committed.
- Consumer schema: `portfell_market`.
- Consumer tables: `listings`, `eod_quotes`, `dividends`, `splits`.
- Full listing identity: `(isin, exchange, code)`.
- Quote key: `(isin, exchange, code, trade_date)`.
- Dividend/split key: `(isin, exchange, code, event_key)`.
- All PostgreSQL timestamp columns are exactly `TIMESTAMPTZ(6)` and DB sessions use UTC.
- EOD `trade_date` is a separate `DATE`; `timestamp_eod` is a canonical UTC date anchor, not a claimed physical XETRA close timestamp.
- Database role `portfell_app` is SELECT-only on `portfell_market` and cannot mutate serving data.
- Portfell has no provider/filesystem fallback if PostgreSQL is unavailable or incomplete.
- The loader is not considered complete until XDL-PR033 performs a real full synchronization to `10.10.1.3:54321` and independently reconciles PostgreSQL to validated Gold.

## Single-user Portfell invariants

- exactly one application workspace;
- no `user_id`, `tenant_id`, membership, project membership, credential-owner, or project-bootstrap-worker authority;
- saved portfolio/analysis domain IDs are allowed but are not security scopes;
- canonical browser routes: `/metadata`, `/univariate`, `/bivariate`, `/multivariate`;
- REST under `/api`;
- production runtime uses external PostgreSQL and does not run its own PostgreSQL or loader worker;
- legacy market-data files/tables are not migrated and may be deleted after verified PostgreSQL cutover.

## Git naming and status contract

Every Portfell work order uses the exact work-order name in branch, every commit message, and PR title. Every commit follows Conventional Commits. Agents record `git status --short --branch` before editing, start from the exact merged predecessor SHA, never branch from siblings, never create compatibility fallbacks, and stay blocked while dependencies are unmerged.

## Revised cross-repository execution graph

```text
xetra-data-loader:
XDL-PR001 ... XDL-PR032 -> XDL-PR033
                               |
                               | real target PostgreSQL full sync + PASS verification
                               v

portfell:
XDL-PR007 -> PR308
              |
       PR309 || PR310 || PR311
              |
       PR312 || PR313 || PR314 || PR315
              |
            PR316 || PR317
              |
            PR318 -> PR319
              |
XDL-PR033 ------+----> PR320 -> PR321
```

PR308 may start once the loader market schema is frozen in XDL-PR007. Portfell's final cross-repository gate PR320 is blocked until both Portfell PR319 and **XDL-PR033** are merged and green. XDL-PR032 fixture/E2E success alone is not sufficient.

## Active Portfell work-order index

| Key | Repository | PR work-order name | Branch | Depends on | Atomic outcome | Git status |
| --- | --- | --- | --- | --- | --- | --- |
| PR296 | `portfell` | `pr296-postgres-loader-single-user-backlog` | `docs/pr296-postgres-loader-single-user-backlog` | current `main` | replace execution authority with xetra-loader/PostgreSQL/single-user cutover plan | pushed; validation pending |
| PR308 | `portfell` | `pr308-portfell-postgres-read-contract` | `refactor/pr308-portfell-postgres-read-contract` | XDL-PR007 | freeze read-only Portfell market-data gateway | not started; branch absent; blocked |
| PR309 | `portfell` | `pr309-portfell-listing-repository` | `feat/pr309-portfell-listing-repository` | PR308 | implement read-only listing repository | not started; branch absent; blocked |
| PR310 | `portfell` | `pr310-portfell-quote-repository` | `feat/pr310-portfell-quote-repository` | PR308 | implement read-only quote repository | not started; branch absent; blocked |
| PR311 | `portfell` | `pr311-portfell-corporate-action-repository` | `feat/pr311-portfell-corporate-action-repository` | PR308 | implement read-only dividend/split repository | not started; branch absent; blocked |
| PR312 | `portfell` | `pr312-metadata-stage-postgres-cutover` | `refactor/pr312-metadata-stage-postgres-cutover` | PR309-PR311 | Metadata reads PostgreSQL only | not started; branch absent; blocked |
| PR313 | `portfell` | `pr313-univariate-stage-postgres-cutover` | `refactor/pr313-univariate-stage-postgres-cutover` | PR309-PR311 | Univariate reads PostgreSQL only | not started; branch absent; blocked |
| PR314 | `portfell` | `pr314-bivariate-stage-postgres-cutover` | `refactor/pr314-bivariate-stage-postgres-cutover` | PR309-PR311 | Bivariate reads PostgreSQL only | not started; branch absent; blocked |
| PR315 | `portfell` | `pr315-multivariate-stage-postgres-cutover` | `refactor/pr315-multivariate-stage-postgres-cutover` | PR309-PR311 | Multivariate optimizer inputs read PostgreSQL only | not started; branch absent; blocked |
| PR316 | `portfell` | `pr316-single-user-backend-cutover` | `refactor/pr316-single-user-backend-cutover` | PR312-PR315 | remove multi-user/project/credential backend | not started; branch absent; blocked |
| PR317 | `portfell` | `pr317-single-user-ui-cutover` | `refactor/pr317-single-user-ui-cutover` | PR312-PR315 | remove project/user/loading UI and project routes | not started; branch absent; blocked |
| PR318 | `portfell` | `pr318-delete-portfell-data-loading-stack` | `refactor/pr318-delete-portfell-data-loading-stack` | PR316-PR317 | physically delete EODHD/lake/loading/refresh stack | not started; branch absent; blocked |
| PR319 | `portfell` | `pr319-simplify-portfell-runtime` | `refactor/pr319-simplify-portfell-runtime` | PR318 | collapse runtime to stable read-only app | not started; branch absent; blocked |
| PR320 | `portfell` | `pr320-cross-repo-serving-contract-gate` | `test/pr320-cross-repo-serving-contract-gate` | XDL-PR033 + PR319 | prove verified real loader serving plane and Portfell reader compatibility | not started; branch absent; blocked |
| PR321 | `portfell` | `pr321-production-destructive-cutover` | `docs/pr321-production-destructive-cutover` | PR320 | freeze production cutover/runbook | not started; branch absent; blocked |

## Loader handoff milestones

The loader-side milestones authoritative in `xetra-data-loader/BACKLOG.md` are:

- XDL-PR007: PostgreSQL market DDL/DTO contract frozen; unblocks PR308 contract work.
- XDL-PR008: writer/read-only role grants frozen.
- XDL-PR032: production-like fixture E2E gate green; useful evidence but not final production handoff.
- XDL-PR033: real full sync to `10.10.1.3:54321` plus independent Gold/PostgreSQL reconciliation PASS; mandatory final handoff to PR320.

The old PR297-PR307 loader IDs are historical only and must not be implemented in Portfell.

## Superseded PR264-PR295 branches

All PR264-PR295 branches were designed for the old multi-project/in-repository-loading architecture. They remain historical/reference branches only and must not be merged as-is. Do not branch new work from them or from old internal wave-base commits.

## Completion gate

Portfell cutover is complete only when all of the following hold from clean `main`:

- Metadata/Univariate/Bivariate/Multivariate read market data from PostgreSQL only;
- `portfell_app` is used as read-only DB identity and cannot mutate serving data;
- no EODHD/provider credential, fetch command, medallion/shared-market persistence, loader worker, scheduled market download, filesystem/NAS fallback, or hidden legacy feature flag remains in Portfell;
- no user/tenant/membership/project runtime or credential-management authority remains;
- project-slug routes/project selector are removed;
- runtime is a single-user app against external PostgreSQL;
- legacy Portfell market-data artifacts are deleted rather than migrated;
- Portfell does not import `xetra-data-loader` as a Python package;
- **XDL-PR033 has completed the real full XETRA -> PostgreSQL synchronization and its sanitized production reconciliation report is PASS**;
- PR320 independently proves Portfell can consume the verified serving plane;
- PR321 documents production cutover and rollback without reactivating legacy loader/fallback paths.