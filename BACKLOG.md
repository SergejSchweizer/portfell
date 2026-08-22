Last reviewed: 2026-08-22

# Active Backlog

## Status authority

This file is the operational index for the **Portfell PostgreSQL read-plane cutover and single-user simplification only**.

The Portfell implementation authority is:

- [`docs/backlog/postgres-loader-single-user-cutover.md`](docs/backlog/postgres-loader-single-user-cutover.md)

The XETRA loader implementation authority has moved out of this repository to:

- `SergejSchweizer/xetra-data-loader` -> `BACKLOG.md`

Work orders `PR297`-`PR307` are no longer Portfell work orders. Their IDs are preserved in `xetra-data-loader/BACKLOG.md` for traceability and all implementation for those work orders must happen in that repository.

All older execution plans that assume in-repository EODHD loading, local/shared market-data files, users/tenants/project memberships, project-scoped routes, project bootstrap workers, or a Portfell-owned Sunday market-data refresh are superseded. In particular, `docs/backlog/parallel-weak-agent-execution-v2.md` and its amendments are historical evidence only for PR264-PR295 after PR296 merges.

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

- `xetra-data-loader` owns provider access, XETRA discovery, Bronze/Silver/Gold, PostgreSQL DDL/publication/sync state, and the Sunday 11:00 Vienna schedule.
- `portfell` owns read-only PostgreSQL gateways, analytics, portfolio optimization, one single-user workspace, and presentation.

Portfell must not contain EODHD credentials/client code, download jobs, medallion market-data persistence, PostgreSQL market-data writers, market-data cron jobs, filesystem/NAS fallbacks, users/tenants/memberships, or project-scoped authorization.

## Frozen shared contract

The authoritative loader-side details are in `xetra-data-loader/BACKLOG.md`. Portfell depends on these frozen externally observable facts:

- PostgreSQL endpoint: `10.10.1.3:54321`, supplied through environment/secret configuration; passwords/full DSNs are never committed.
- Consumer schema: `portfell_market`.
- Consumer tables: `listings`, `eod_quotes`, `dividends`, `splits`.
- Full listing identity: `(isin, exchange, code)`.
- `eod_quotes` business key: `(isin, exchange, code, trade_date)`.
- All PostgreSQL timestamp columns are `TIMESTAMPTZ(6)` and DB sessions use UTC.
- EOD `trade_date` remains a separate `DATE`; `timestamp_eod` is a canonical UTC date anchor, not a claimed physical XETRA close timestamp.
- Database role `portfell_app` is `SELECT` only on `portfell_market` and has no mutation/DDL rights.
- Portfell has no provider/filesystem fallback if PostgreSQL is unavailable or incomplete.

## Single-user Portfell invariants

- exactly one application workspace;
- no `user_id`, `tenant_id`, membership, project membership, credential-owner, or project-bootstrap-worker authority;
- saved portfolio/analysis domain IDs are allowed, but they are not security/tenant/project IDs;
- canonical browser routes are `/metadata`, `/univariate`, `/bivariate`, `/multivariate`;
- REST remains under `/api`;
- production Portfell runtime uses external PostgreSQL and does not run its own PostgreSQL or loader worker;
- existing legacy market-data files/tables do not need migration and may be deleted after the PostgreSQL cutover is proven.

## Git naming and status contract

Every active work order uses the exact work-order name in the branch, every commit message, and the PR title.

Example:

```text
Work-order name: pr313-univariate-stage-postgres-cutover
Branch:          refactor/pr313-univariate-stage-postgres-cutover
Commit:          refactor(pr313-univariate-stage-postgres-cutover): cut univariate reads to postgres
PR title:        must contain pr313-univariate-stage-postgres-cutover
```

Before editing, every agent records:

```bash
git status --short --branch
```

A work order whose dependency is not merged remains blocked. Parallel siblings start from the same predecessor merge SHA. Weak agents must not branch from sibling work, create compatibility shims, broaden scope, or resurrect legacy loader/runtime paths.

## Revised cross-repository execution graph

Loader work now lives entirely in `xetra-data-loader`:

```text
xetra-data-loader:
PR297 -> PR298 -> PR299
                  |
          PR300 || PR301 || PR302
                  |
                PR303 -> PR304 -> PR305 -> PR306 -> PR307
```

Portfell work stays here:

```text
xetra PR298 -> PR308
                |
         PR309 || PR310 || PR311
                |
         PR312 || PR313 || PR314 || PR315
                |
              PR316 || PR317
                |
              PR318 -> PR319
                |
xetra PR307 -----+----> PR320 -> PR321
```

`PR308` may start after the shared PostgreSQL contract in xetra PR298 is merged; it does not require a live complete loader. `PR320` is the hard cross-repository compatibility gate and requires xetra PR307 plus Portfell PR319.

## Active Portfell work-order index

Detailed Tasks/Acceptance and owned scope are in `docs/backlog/postgres-loader-single-user-cutover.md`.

| Key | Repository | PR work-order name | Branch | Depends on | Atomic outcome | Git status |
| --- | --- | --- | --- | --- | --- | --- |
| PR296 | `portfell` | `pr296-postgres-loader-single-user-backlog` | `docs/pr296-postgres-loader-single-user-backlog` | current `main` | replace execution authority with xetra-loader/PostgreSQL/single-user cutover plan | pushed; validation pending |
| PR308 | `portfell` | `pr308-portfell-postgres-read-contract` | `refactor/pr308-portfell-postgres-read-contract` | xetra PR298 | freeze read-only Portfell market-data gateway | not started; branch absent; blocked |
| PR309 | `portfell` | `pr309-portfell-listing-repository` | `feat/pr309-portfell-listing-repository` | PR308 | implement read-only listing repository | not started; branch absent; blocked |
| PR310 | `portfell` | `pr310-portfell-quote-repository` | `feat/pr310-portfell-quote-repository` | PR308 | implement read-only quote repository | not started; branch absent; blocked |
| PR311 | `portfell` | `pr311-portfell-corporate-action-repository` | `feat/pr311-portfell-corporate-action-repository` | PR308 | implement read-only dividend/split repository | not started; branch absent; blocked |
| PR312 | `portfell` | `pr312-metadata-stage-postgres-cutover` | `refactor/pr312-metadata-stage-postgres-cutover` | PR309-PR311 | Metadata stage reads PostgreSQL only | not started; branch absent; blocked |
| PR313 | `portfell` | `pr313-univariate-stage-postgres-cutover` | `refactor/pr313-univariate-stage-postgres-cutover` | PR309-PR311 | Univariate stage reads PostgreSQL only | not started; branch absent; blocked |
| PR314 | `portfell` | `pr314-bivariate-stage-postgres-cutover` | `refactor/pr314-bivariate-stage-postgres-cutover` | PR309-PR311 | Bivariate stage reads PostgreSQL only | not started; branch absent; blocked |
| PR315 | `portfell` | `pr315-multivariate-stage-postgres-cutover` | `refactor/pr315-multivariate-stage-postgres-cutover` | PR309-PR311 | Multivariate optimizer inputs read PostgreSQL only | not started; branch absent; blocked |
| PR316 | `portfell` | `pr316-single-user-backend-cutover` | `refactor/pr316-single-user-backend-cutover` | PR312-PR315 | remove multi-user/project/credential backend | not started; branch absent; blocked |
| PR317 | `portfell` | `pr317-single-user-ui-cutover` | `refactor/pr317-single-user-ui-cutover` | PR312-PR315 | remove project/user/loading UI and project routes | not started; branch absent; blocked |
| PR318 | `portfell` | `pr318-delete-portfell-data-loading-stack` | `refactor/pr318-delete-portfell-data-loading-stack` | PR316-PR317 | physically delete EODHD/lake/loading/refresh stack | not started; branch absent; blocked |
| PR319 | `portfell` | `pr319-simplify-portfell-runtime` | `refactor/pr319-simplify-portfell-runtime` | PR318 | collapse dependencies/composition/Compose to stable read-only app | not started; branch absent; blocked |
| PR320 | `portfell` | `pr320-cross-repo-serving-contract-gate` | `test/pr320-cross-repo-serving-contract-gate` | xetra PR307 + PR319 | prove xetra loader schema and Portfell reader compatibility | not started; branch absent; blocked |
| PR321 | `portfell` | `pr321-production-destructive-cutover` | `docs/pr321-production-destructive-cutover` | PR320 | freeze destructive production cutover/runbook | not started; branch absent; blocked |

## Moved loader work orders

The following work orders have been removed from Portfell implementation ownership and are authoritative only in `SergejSchweizer/xetra-data-loader/BACKLOG.md`:

| Key | Work-order name | New repository |
| --- | --- | --- |
| PR297 | `pr297-loader-repository-bootstrap` | `xetra-data-loader` |
| PR298 | `pr298-postgres-serving-contract` | `xetra-data-loader` |
| PR299 | `pr299-medallion-dataset-contracts` | `xetra-data-loader` |
| PR300 | `pr300-xetra-listing-ingestion` | `xetra-data-loader` |
| PR301 | `pr301-eod-quote-ingestion` | `xetra-data-loader` |
| PR302 | `pr302-corporate-action-ingestion` | `xetra-data-loader` |
| PR303 | `pr303-gold-serving-build` | `xetra-data-loader` |
| PR304 | `pr304-postgres-idempotent-sync` | `xetra-data-loader` |
| PR305 | `pr305-sunday-1100-loader-runner` | `xetra-data-loader` |
| PR306 | `pr306-destructive-bootstrap-command` | `xetra-data-loader` |
| PR307 | `pr307-loader-end-to-end-gate` | `xetra-data-loader` |

Do not implement those work orders in Portfell.

## Superseded PR264-PR295 branches

These work orders were designed for the old multi-project/in-repository-loading architecture. Their branches are retained only as historical/reference branches and must not be merged as-is.

| Key | Branch | Git status | Action |
| --- | --- | --- | --- |
| PR264 | `feat/pr264-dash-contract-registry` | superseded; pushed branch exists | do not merge |
| PR277 | `feat/pr277-dash-temporary-runtime` | superseded; pushed branch exists | do not merge |
| PR278 | `feat/pr278-dash-presentation-contracts` | superseded; pushed branch exists | do not merge |
| PR265 | `feat/pr265-dash-research-shell` | superseded; pushed branch exists | do not merge |
| PR266 | `feat/pr266-dash-metadata-builder` | superseded; pushed branch exists | do not merge |
| PR267 | `feat/pr267-dash-univariate-control` | superseded; pushed branch exists | do not merge |
| PR268 | `feat/pr268-dash-bivariate-control` | superseded; pushed branch exists | do not merge |
| PR279 | `feat/pr279-dash-univariate-figures` | superseded; pushed branch exists | do not merge |
| PR280 | `feat/pr280-dash-bivariate-figures` | superseded; pushed branch exists | do not merge |
| PR269 | `feat/pr269-multivariate-contract-registry` | superseded; pushed branch exists | do not merge |
| PR281 | `feat/pr281-multivariate-run-contracts` | superseded; pushed branch exists | do not merge |
| PR282 | `feat/pr282-multivariate-decision-contracts` | superseded; pushed branch exists | do not merge |
| PR283 | `feat/pr283-multivariate-history-contracts` | superseded; pushed branch exists | do not merge |
| PR270 | `feat/pr270-multivariate-pareto-selector` | superseded; pushed branch exists | do not merge |
| PR271 | `feat/pr271-multivariate-solver-candidates` | superseded; pushed branch exists | do not merge |
| PR284 | `feat/pr284-multivariate-redundancy-reducer` | superseded; pushed branch exists | do not merge |
| PR285 | `feat/pr285-multivariate-risk-candidates` | superseded; pushed branch exists | do not merge |
| PR286 | `feat/pr286-multivariate-algorithm-integration` | superseded; pushed branch exists | do not merge |
| PR272 | `feat/pr272-multivariate-oos-orchestration` | superseded; pushed branch exists | do not merge |
| PR273 | `feat/pr273-multivariate-decision-persistence` | superseded; pushed branch exists | do not merge |
| PR287 | `feat/pr287-multivariate-read-api` | superseded; pushed branch exists | do not merge |
| PR288 | `feat/pr288-dash-multivariate-figures` | superseded; pushed branch exists | do not merge |
| PR289 | `feat/pr289-dash-multivariate-callbacks` | superseded; pushed branch exists | do not merge |
| PR290 | `feat/pr290-dash-multivariate-layout` | superseded; pushed branch exists | do not merge |
| PR274 | `feat/pr274-dash-multivariate-integration` | superseded; pushed branch exists | do not merge |
| PR291 | `refactor/pr291-dash-fastapi-mount` | superseded; pushed branch exists | do not merge |
| PR292 | `refactor/pr292-remove-react-ui` | superseded; pushed branch exists | do not merge |
| PR275 | `refactor/pr275-dash-production-cutover` | superseded; pushed branch exists | do not merge |
| PR293 | `feat/pr293-scheduled-union-refresh` | superseded; pushed branch exists | do not merge |
| PR294 | `feat/pr294-scheduled-project-research` | superseded; pushed branch exists | do not merge |
| PR295 | `feat/pr295-scheduled-sunday-runner` | superseded; pushed branch exists | do not merge |
| PR276 | `feat/pr276-weekly-full-research-refresh` | superseded; pushed branch exists | do not merge |

Do not branch new work from superseded branches or old internal wave-base commits.

## Completion gate

Portfell cutover is complete only when all of the following are true from clean `main`:

- Metadata/Univariate/Bivariate/Multivariate read market data from PostgreSQL only;
- `portfell_app` is used as a read-only database identity and cannot mutate the serving schema;
- there is no EODHD/provider credential, fetch command, medallion/shared-market persistence, loading worker, scheduled market download, filesystem/NAS market fallback, or hidden legacy feature flag in Portfell;
- there is no user/tenant/membership/project runtime or credential-management authority;
- project-slug routes and project selector are removed;
- runtime is a single-user application against external PostgreSQL;
- legacy Portfell market-data artifacts are deleted rather than migrated;
- Portfell does not import `xetra-data-loader` as a Python package;
- xetra PR307 and Portfell PR319 jointly satisfy PR320 cross-repository contract tests;
- PR321 documents destructive production cutover and operational rollback without reactivating any legacy loader/fallback path.
