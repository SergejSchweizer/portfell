Last reviewed: 2026-08-22

# Active Backlog

## Status authority

This file is the operational index for the **Portfell data-loader extraction, PostgreSQL serving-plane cutover, and single-user backend simplification**.

The detailed implementation authority is:

- [`docs/backlog/postgres-loader-single-user-cutover.md`](docs/backlog/postgres-loader-single-user-cutover.md)

All older execution plans that assume in-repository EODHD loading, local/shared market-data files, users/tenants/project memberships, project-scoped routes, project bootstrap workers, or a Portfell-owned Sunday market-data refresh are superseded. In particular, `docs/backlog/parallel-weak-agent-execution-v2.md` and its amendments are historical evidence only for PR264-PR295 after PR296 merges.

## Target architecture

The cutover has one hard ownership boundary:

```text
EODHD
  |
  v
SergejSchweizer/portfell-data-loader
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

`portfell-data-loader` owns all provider/download/medallion/scheduling/write behavior. `portfell` owns portfolio analytics/optimization and reads market data from PostgreSQL only.

The new loader repository does not yet exist. Before PR297 starts, create `SergejSchweizer/portfell-data-loader` manually with default branch `main`. No Portfell Git history or old data is migrated into it.

## Frozen system invariants

- Production PostgreSQL endpoint: `10.10.1.3:54321`, supplied through environment/secret configuration; passwords are never committed.
- Consumer schema: `portfell_market`; loader operational schema: `portfell_loader_sync`.
- Consumer tables: `listings`, `eod_quotes`, `dividends`, `splits`.
- Full listing identity is always `(isin, exchange, code)`.
- Initial bootstrap loads **every XETRA listing with a non-empty ISIN**; there is no ETF/UCITS prefilter in the loader.
- Quotes, dividends, and splits are loaded for that full XETRA listing set.
- All PostgreSQL timestamp columns use `TIMESTAMPTZ(6)` and DB sessions use `UTC`, matching the `market-regime-loader` timestamp contract. EOD business date remains a separate `DATE`.
- First bootstrap is a clean full redownload. Existing Portfell market-data files/tables do not need migration and may be deleted.
- Weekly loader schedule is exactly:

```text
CRON_TZ=Europe/Vienna
0 11 * * 0
```

- After bootstrap, weekly refresh is idempotent and uses a seven-calendar-day correction overlap.
- Portfell is a **single-user, single-workspace** application. There are no users, tenants, memberships, project memberships, per-user provider credentials, or project bootstrap workers.
- Canonical workflow routes after cutover are `/metadata`, `/univariate`, `/bivariate`, `/multivariate`; no project slug is part of the route.
- Portfell contains no EODHD client/token, provider fetch command, Bronze/Silver/Gold market-data writer, shared-market filesystem fallback, market-data cron, or legacy import compatibility path.
- Portfell production runtime does not own a PostgreSQL container or a data-loading worker; it uses the external PostgreSQL serving plane read-only.

## Git naming and status contract

Every active work order uses the exact work-order name in the branch, every commit message, and the PR title.

Example:

```text
Work-order name: pr301-eod-quote-ingestion
Branch:          feat/pr301-eod-quote-ingestion
Commit:          feat(pr301-eod-quote-ingestion): add deterministic eod quote ingestion
PR title:        must contain pr301-eod-quote-ingestion
```

Before editing, every agent must run and record:

```bash
git status --short --branch
```

A work order whose dependency is not merged remains blocked. Weak agents must not create compatibility shims, broaden scope, or branch from a sibling implementation branch.

## Revised execution graph

```text
PR296 planning gate
        |
  manually create portfell-data-loader
        |
      PR297 -> PR298 -> PR299
                        |
                PR300 || PR301 || PR302
                        |
                      PR303 -> PR304 -> PR305 -> PR306 -> PR307

PR298 -> PR308
          |
   PR309 || PR310 || PR311
          |
   PR312 || PR313 || PR314 || PR315
          |
        PR316 || PR317
          |
        PR318 -> PR319
          |
PR307 ----+----> PR320 -> PR321
```

Parallel siblings always start from the same predecessor merge SHA.

## Active Work-Order Index

Detailed Tasks / Acceptance, owned paths, security/idempotency rules, and cross-repository dependencies are in `docs/backlog/postgres-loader-single-user-cutover.md`.

| Key | Repository | PR work-order name | Branch | Depends on | Atomic outcome | Git status |
| --- | --- | --- | --- | --- | --- | --- |
| PR296 | `portfell` | `pr296-postgres-loader-single-user-backlog` | `docs/pr296-postgres-loader-single-user-backlog` | current `main` | replace execution authority with loader/Postgres/single-user cutover plan | pushed; validation pending |
| PR297 | `portfell-data-loader` | `pr297-loader-repository-bootstrap` | `chore/pr297-loader-repository-bootstrap` | PR296 + repo exists | bootstrap strict loader repository skeleton | not started; branch absent; blocked |
| PR298 | `portfell-data-loader` | `pr298-postgres-serving-contract` | `feat/pr298-postgres-serving-contract` | PR297 | freeze PostgreSQL schema/roles/`TIMESTAMPTZ(6)` contract | not started; branch absent; blocked |
| PR299 | `portfell-data-loader` | `pr299-medallion-dataset-contracts` | `feat/pr299-medallion-dataset-contracts` | PR298 | freeze Bronze/Silver/Gold datasets and business keys | not started; branch absent; blocked |
| PR300 | `portfell-data-loader` | `pr300-xetra-listing-ingestion` | `feat/pr300-xetra-listing-ingestion` | PR299 | ingest all XETRA non-empty-ISIN listings | not started; branch absent; blocked |
| PR301 | `portfell-data-loader` | `pr301-eod-quote-ingestion` | `feat/pr301-eod-quote-ingestion` | PR299 | full/delta EOD quote ingestion | not started; branch absent; blocked |
| PR302 | `portfell-data-loader` | `pr302-corporate-action-ingestion` | `feat/pr302-corporate-action-ingestion` | PR299 | full/delta dividends and splits ingestion | not started; branch absent; blocked |
| PR303 | `portfell-data-loader` | `pr303-gold-serving-build` | `feat/pr303-gold-serving-build` | PR300-PR302 | build serving-ready validated Gold | not started; branch absent; blocked |
| PR304 | `portfell-data-loader` | `pr304-postgres-idempotent-sync` | `feat/pr304-postgres-idempotent-sync` | PR303 | transactional semantic-delta Gold -> PostgreSQL sync | not started; branch absent; blocked |
| PR305 | `portfell-data-loader` | `pr305-sunday-1100-loader-runner` | `feat/pr305-sunday-1100-loader-runner` | PR304 | restart-safe weekly pipeline + Sunday 11:00 Vienna cron | not started; branch absent; blocked |
| PR306 | `portfell-data-loader` | `pr306-destructive-bootstrap-command` | `feat/pr306-destructive-bootstrap-command` | PR305 | confirmed destructive reset and clean full XETRA bootstrap | not started; branch absent; blocked |
| PR307 | `portfell-data-loader` | `pr307-loader-end-to-end-gate` | `test/pr307-loader-end-to-end-gate` | PR306 | production-like loader acceptance gate | not started; branch absent; blocked |
| PR308 | `portfell` | `pr308-portfell-postgres-read-contract` | `refactor/pr308-portfell-postgres-read-contract` | PR298 | freeze read-only Portfell market-data gateway | not started; branch absent; blocked |
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
| PR320 | `portfell` | `pr320-cross-repo-serving-contract-gate` | `test/pr320-cross-repo-serving-contract-gate` | PR307 + PR319 | prove loader schema and Portfell reader compatibility | not started; branch absent; blocked |
| PR321 | `portfell` | `pr321-production-destructive-cutover` | `docs/pr321-production-destructive-cutover` | PR320 | freeze destructive production cutover/runbook | not started; branch absent; blocked |

## Superseded PR264-PR295 branches

These work orders were designed for the old multi-project/in-repository-loading architecture. Their branches are retained only as historical/reference branches and must not be merged as-is. This table is the current Git status authority for them.

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

Do not branch new work from any superseded branch or from the old internal wave-base commits.

## Workload assessment

The permission to delete existing market data and redownload from scratch removes compatibility/migration complexity, but this remains a substantial two-repository refactor.

The main effort is concentrated in four areas:

1. **New loader platform:** repository scaffold, strict package boundaries, medallion contracts, EODHD adapters, XETRA-all-ISIN bootstrap, retry/rate-limit/restart behavior.
2. **PostgreSQL serving plane:** `TIMESTAMPTZ(6)`/UTC schema, writer/read-only roles, semantic delta sync, correction/retraction handling, and DB integration tests.
3. **Portfell simplification:** PostgreSQL read adapters, four workflow-stage cutovers, complete removal of in-repo loading and all multi-user/project/credential authority, simplified runtime/dependencies/Compose.
4. **Cutover assurance:** destructive bootstrap, no-legacy source guards, cross-repo contract smoke test, production runbook and verification queries.

A strong engineer should budget approximately **8-14 focused engineering days**, plus the wall-clock time of the first full XETRA historical download. With several weak agents constrained to the parallel sibling waves above, a realistic implementation/review window is about **4-7 calendar days** if CI and PostgreSQL test infrastructure are reliable. The duration of the first historical download is deliberately not guessed; the loader acceptance work orders must measure it against the actual EODHD plan/rate limits.

## Completion gate

The cutover is complete only when all of the following are true from clean `main` heads in both repositories:

- `portfell-data-loader` can destructively reset its own state, load every current XETRA non-empty-ISIN listing, load full quote/dividend/split history, build Gold, and publish idempotently to PostgreSQL;
- the weekly cron is exactly Sunday 11:00 `Europe/Vienna` and a repeat with unchanged source data produces zero semantic DB mutations;
- `portfell_market` timestamp columns are `TIMESTAMPTZ(6)` and UTC session behavior is verified;
- `portfell_app` can `SELECT` serving data but cannot mutate it;
- Portfell Metadata, Univariate, Bivariate, and Multivariate stages run from PostgreSQL data only;
- Portfell has no EODHD/provider credentials, loading workers, medallion/shared-market filesystem data path, or fallback reader;
- Portfell has no user/tenant/membership/project-scoped runtime or credential management;
- project-slug routes and project selector UI are gone;
- production Portfell runtime is reduced to the single-user application against the external PostgreSQL service;
- old market-data artifacts are deleted rather than migrated;
- cross-repository contract and final quality gates pass without importing one repository's Python package into the other.