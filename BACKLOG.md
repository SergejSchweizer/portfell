Last reviewed: 2026-08-29

# Active Backlog

## Status authority

This file is the operational index for the **Portfell PostgreSQL market-source cutover and single-user simplification**.

Detailed scope, owned paths, complete Tasks / Acceptance, security, determinism, idempotency, rollback, and parallelization are authoritative in:

- [`docs/backlog/postgres-loader-single-user-cutover.md`](docs/backlog/postgres-loader-single-user-cutover.md)

For **current external database topology, upstream production-gate status, and active work-order index**, this `BACKLOG.md` is authoritative if an older sentence in the detailed document conflicts. Older market-loading/EODHD plans are superseded where they conflict with this authority. Historical files remain evidence only.

## Target architecture

```text
SergejSchweizer/xetra-loader
provider acquisition -> Bronze/Silver/Gold
  |
  v
PostgreSQL 10.10.1.3:54321 / database xetra_loader
  schema: xetra_loader
  tables: listings / eod_quotes / dividends / splits
  |
  | read-only LOGIN role that is member of NOLOGIN group role portfell_app
  v
SergejSchweizer/portfell
Metadata -> Univariate -> Bivariate -> Multivariate -> portfolio optimization
```

Portfell does not own provider acquisition after this series. PostgreSQL is the only market-data integration boundary.

### Application-state DB and market DB are different authorities

Portfell already has its own application-state PostgreSQL authority (`PORTFELL_DATABASE_URL`) for writable Portfell-owned state such as analyses/runs/decisions. That database is **not** replaced by the XETRA source cutover merely because both are PostgreSQL.

The external market serving plane uses the separate seam `PORTFELL_MARKET_DATABASE_URL` and current xetra-loader database name `xetra_loader`. Market data is read-only to Portfell. Application/analytical state must not be written into the external `xetra_loader` database, and market rows must not be copied into the Portfell application database as a fallback authority. A missing market DSN must never fall back to `PORTFELL_DATABASE_URL`.

The role name `portfell_app` exists in different database contexts today: the existing Portfell application DB may use a LOGIN role named `portfell_app`, while the external xetra-loader database defines `portfell_app` as a NOLOGIN consumer group role. Agents must not conflate these identities. External market preflight validates the actual external session independently.

## Frozen external market contract

- Endpoint: `10.10.1.3:54321`.
- Current xetra-loader database: `xetra_loader`.
- Business schema: `xetra_loader`.
- Tables: `listings`, `eod_quotes`, `dividends`, `splits`.
- Listing key: `(isin, exchange, code)`.
- Quote key: `(isin, exchange, code, trade_date)`.
- Dividend/split key: `(isin, exchange, code, event_key)`.
- `trade_date` is `DATE`; `timestamp_eod` is the UTC-midnight date anchor, not a physical exchange close.
- PostgreSQL `NUMERIC` stays `Decimal` in the raw repository layer.
- All consumed timestamps are timezone-aware UTC.
- `portfell_app` is a NOLOGIN group role in xetra-loader; Portfell authenticates through a secret-supplied LOGIN role that must be a non-superuser member of that group.
- Market reads use `REPEATABLE READ, READ ONLY` while assembling one analytical input snapshot; the transaction closes after input materialization and before CPU-heavy statistics/optimization.
- `xetra_loader_sync` is loader-owned and inaccessible to Portfell application code.
- No provider/filesystem/NAS/dual-read/app-database fallback is permitted.
- Canonical market DSN seam: `PORTFELL_MARKET_DATABASE_URL`; password/full DSN/login-role name are never committed.

## Analytical projection invariants

- DB quote `trade_date -> date`; dividend `event_date -> date` at one centralized projection boundary.
- `Decimal -> float` only at that analytics projection boundary.
- `adjusted_close` is authoritative for return/risk/drawdown calculations.
- Missing adjusted close becomes typed `missing_adjusted_close` evidence; raw `close` is never a silent substitute.
- Dividends remain income/distribution evidence and are not added again to adjusted-close returns.
- No new split-adjustment formula is introduced by this source cutover.
- New Metadata candidate universes use `is_active=true`; inactive listings remain resolvable for historical evidence.
- Existing Python Metadata predicate semantics, including casefolded name-substring matching, remain unchanged.

## Observability, snapshots, and performance invariants

- PR313 source status is a **low-cost preflight**, not a global freshness scanner. It may check connection/session/contract/table reachability and active-listing evidence. It must not full-scan large quote/action tables merely to compute global `MAX(published_at_utc)`/row counts, must not add indexes/DDL, and must not infer loader run state.
- Freshness-like evidence attached to an analytical `MarketSourceSnapshot` comes only from the rows actually consumed by that snapshot, e.g. selected quote date bounds and maximum consumed `published_at_utc`.
- `MarketSourceSnapshot` contract version is `market_source.snapshot.v1`.
- Its deterministic ID hashes canonical semantic input only: selected full listing identities plus consumed listing semantic fields; quote key + OHLC/close/adjusted-close/volume; dividend key + event/declaration/record/payment dates + value/currency/period; and split key + event date/ratio/factor only when splits are actually consumed. `fetched_at_utc`, `published_at_utc`, observation clock time, credentials, DSN, and sync-state fields are excluded from the ID.
- Snapshot hashing is streaming/canonical and must not create a second full in-memory copy solely for hashing.
- Source repositories provide bounded multi-identity reads; canonical batch maximum is 500 listing identities per SQL statement.
- No one-query-per-listing analytical implementation when batch reads are available.
- Direct `xetra_loader` SQL is confined to `src/portfell/market_source/**`.

## Stable source errors

Infrastructure error codes are exactly:

- `market_source_config_missing`;
- `market_source_unavailable`;
- `market_source_role_invalid`;
- `market_source_contract_mismatch`;
- `market_source_duplicate_key`;
- `market_source_invalid_value`.

Analytical insufficiency remains analytical evidence and is not collapsed into these infrastructure errors.

## xetra-loader production handoff

The old XDL-PR033 final-gate assumption is obsolete. In current `xetra-loader`, XDL-PR053 supersedes it as the real production rewrite/reconciliation gate.

Portfell development and fixture QA may proceed before the production loader gate is complete, but **PR340 is blocked** until this exact artifact exists on `xetra-loader` `main` and is marked `PASS`:

```text
artifacts/acceptance/postgres-full-sync-v2.json
```

The exact loader commit SHA containing the PASS artifact must be recorded in Portfell live-QA evidence. As reviewed on 2026-08-29, that V2 artifact is not yet present and the loader recurring cron remains disabled; therefore the real-target production handoff is currently blocked.

## Single-user target

- exactly one application workspace;
- no user/tenant/membership/project-membership/credential-owner security authority;
- saved portfolio/analysis/optimization/decision IDs may remain domain identifiers but are not security scopes;
- canonical browser routes exactly `/metadata`, `/univariate`, `/bivariate`, `/multivariate`;
- REST remains under `/api`;
- the Portfell-owned application-state PostgreSQL may remain if required by surviving analytical/application persistence.

## Deferred product-scope protection

PR264-PR295 implementation branches are **frozen reference branches and must not be merged as-is**, because their market-source and multi-project assumptions predate this cutover. They are not wholesale product cancellations.

Still-valid non-market requirements remain deferred: Plotly Dash mounted in FastAPI, exactly four workflow pages, Multivariate as sole optimizer stage, three frozen optimization objectives, objective-specific OOS winner selection, professional plots, Universe & History evidence, and analytical persistence/reproducibility requirements. PR343 must explicitly disposition every old work order against the post-cutover architecture so no requirement is silently lost.

## Weak-agent contract

Every work order uses exact branch/work-order slug in branch, Conventional Commit scope, and PR title. Agents record `git status --short --branch`, start from the exact merged predecessor SHA, never branch from siblings, and edit only the owned paths in the detailed backlog. No compatibility shim, hidden provider flag, second market source, broader DB grant, or opportunistic refactor is allowed. Implementation PRs run focused tests plus `uv run portfell-quality pr`; QA barriers additionally run `uv run portfell-quality merge` from one clean SHA. QA PRs own tests/evidence only: a production defect found by QA creates a new atomic corrective PR before the QA gate, rather than being fixed opportunistically in the QA branch. `GATES.md` remains the sole quality/coverage authority.

## Dependency graph

```text
PR296
  |
PR308
  |
PR309 || PR310 || PR311 || PR312 || PR313 || PR314
  |
PR315 -> PR316(QA) -> PR317 -> PR318
  |
PR319 || PR320 || PR321 || PR322
  |
PR323(QA)
  |
PR324 || PR325 || PR326 || PR327 || PR328 || PR329 || PR330 || PR331
  |
PR332(QA)
  |
PR333 || PR334
  |
PR335(QA)
  |
PR336 || PR337 || PR338
  |
PR339(QA)
  |
xetra-loader XDL-PR053 V2 PASS
  |
PR340(live QA) -> PR341(E2E) -> PR342(runbook) -> PR343(next-product planning)
```

## Active work-order index

| Key | Branch | Depends on | Atomic outcome | Git status |
| --- | --- | --- | --- | --- |
| PR296 | `docs/pr296-postgres-loader-single-user-backlog` | current `main` | audited execution authority | pushed; validation pending |
| PR308 | `refactor/pr308-xetra-source-contract` | PR296 | exact DTO/error/role/read-only snapshot foundation | not started; branch absent; blocked |
| PR309 | `feat/pr309-xetra-listings-repository` | PR308 | raw SELECT-only listing repository | not started; branch absent; blocked |
| PR310 | `feat/pr310-xetra-quotes-repository` | PR308 | bulk exact quote repository | not started; branch absent; blocked |
| PR311 | `feat/pr311-xetra-dividends-repository` | PR308 | bulk exact dividend repository | not started; branch absent; blocked |
| PR312 | `feat/pr312-xetra-splits-repository` | PR308 | bulk exact split repository | not started; branch absent; blocked |
| PR313 | `feat/pr313-xetra-observed-source-status` | PR308 | low-cost business-plane preflight; no sync/freshness scan | not started; branch absent; blocked |
| PR314 | `refactor/pr314-market-analysis-projection-contract` | PR308 | freeze DB->analytics mapping/adjusted-close policy | not started; branch absent; blocked |
| PR315 | `feat/pr315-xetra-market-data-gateway` | PR309-PR314 | single gateway + coherent repeatable-read snapshots | not started; branch absent; blocked |
| PR316 | `test/pr316-xetra-source-contract-qa` | PR315 | QA repository/role/batching/snapshot/projection contract | not started; branch absent; blocked |
| PR317 | `refactor/pr317-hosted-runtime-read-plane-cutover` | PR316 | replace provider runtime port with read-only gateway port | not started; branch absent; blocked |
| PR318 | `refactor/pr318-market-source-lineage-cutover` | PR317 | replace provider quote-run lineage with MarketSourceSnapshot v1 | not started; branch absent; blocked |
| PR319 | `refactor/pr319-metadata-stage-xetra-cutover` | PR318 | active-listing Metadata source cutover | not started; branch absent; blocked |
| PR320 | `refactor/pr320-univariate-stage-xetra-cutover` | PR318 | Univariate PostgreSQL/snapshot cutover | not started; branch absent; blocked |
| PR321 | `refactor/pr321-bivariate-stage-xetra-cutover` | PR318 | Bivariate PostgreSQL/snapshot cutover | not started; branch absent; blocked |
| PR322 | `refactor/pr322-multivariate-stage-xetra-cutover` | PR318 | Multivariate PostgreSQL/snapshot cutover | not started; branch absent; blocked |
| PR323 | `test/pr323-four-stage-source-semantics-qa` | PR319-PR322 | QA end-to-end source semantics/regression gate | not started; branch absent; blocked |
| PR324 | `refactor/pr324-delete-eodhd-client-fetch-cli` | PR323 | delete provider HTTP/search/fetch/CLI | not started; branch absent; blocked |
| PR325 | `refactor/pr325-delete-market-medallion-persistence` | PR323 | delete Portfell market Bronze/Silver/Gold/pipeline | not started; branch absent; blocked |
| PR326 | `refactor/pr326-delete-market-filesystem-nas-plane` | PR323 | delete market filesystem/NAS fallback plane | not started; branch absent; blocked |
| PR327 | `refactor/pr327-delete-shared-market-refresh-plane` | PR323 | delete shared market cache/publisher/refresh/cron | not started; branch absent; blocked |
| PR328 | `refactor/pr328-delete-hosted-market-download-lifecycle` | PR323 | delete hosted market download jobs/routes/workers | not started; branch absent; blocked |
| PR329 | `refactor/pr329-delete-provider-credential-backend` | PR323 | delete provider credential backend/routes | not started; branch absent; blocked |
| PR330 | `refactor/pr330-delete-provider-loading-ui` | PR323 | delete provider token/fetch/progress UI | not started; branch absent; blocked |
| PR331 | `refactor/pr331-delete-legacy-market-runtime-residuals` | PR323 | remove legacy local provider runtime/config residues | not started; branch absent; blocked |
| PR332 | `test/pr332-provider-removal-negative-space-qa` | PR324-PR331 | QA prove no executable acquisition/fallback remains | not started; branch absent; blocked |
| PR333 | `refactor/pr333-single-user-backend-cutover` | PR332 | one-workspace backend authority | not started; branch absent; blocked |
| PR334 | `refactor/pr334-single-user-ui-route-cutover` | PR332 | one-workspace four-route UI | not started; branch absent; blocked |
| PR335 | `test/pr335-single-user-authority-qa` | PR333+PR334 | QA single-user authority/routes | not started; branch absent; blocked |
| PR336 | `refactor/pr336-package-entrypoint-import-boundary-cleanup` | PR335 | prune package/entrypoint/import boundaries | not started; branch absent; blocked |
| PR337 | `refactor/pr337-external-postgres-runtime-compose` | PR335 | separate writable app DB from external read-only market DB | not started; branch absent; blocked |
| PR338 | `docs/pr338-active-docs-market-source-rewrite` | PR335 | rewrite active docs and remove obsolete EODHD artifacts | not started; branch absent; blocked |
| PR339 | `test/pr339-clean-runtime-install-docs-qa` | PR336-PR338 | QA clean install/runtime/docs/two-DB authority | not started; branch absent; blocked |
| PR340 | `test/pr340-live-xetra-postgres-v2-contract-qa` | PR339 + XDL-PR053 V2 PASS | live target least-privilege/contract proof | not started; external production gate pending |
| PR341 | `test/pr341-full-postgres-source-replacement-e2e` | PR340 | final PostgreSQL-only four-stage E2E | not started; branch absent; blocked |
| PR342 | `docs/pr342-production-postgres-cutover-runbook` | PR341 | executable production cutover/rollback | not started; branch absent; blocked |
| PR343 | `docs/pr343-rebase-deferred-product-backlog` | PR342 | re-plan old Dash/Multivariate product work on new main | not started; branch absent; blocked |

The complete checklist for every work order is in the detailed authority file. The hard topology/snapshot/status clarifications above are global acceptance constraints on every affected work order even when the detailed entry uses older shorthand.

## Completion gates

PR342 completes the PostgreSQL source cutover only after PR340 has verified the real target against the xetra-loader PR053 V2 PASS handoff and PR341 has proved complete source replacement end-to-end. The source cutover must leave Portfell application-state persistence and external market-source persistence as separate authorities. PR343 is mandatory before resuming the deferred Dash/Multivariate product series so the still-valid product requirements from PR264-PR295 receive an explicit reuse/reimplement/split/retire disposition rather than being silently discarded.
