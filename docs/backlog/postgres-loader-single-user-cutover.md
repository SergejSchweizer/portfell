# PostgreSQL XETRA Read-Plane and Single-User Portfell Cutover

Status: active Portfell implementation authority after PR296 is merged.

Last reviewed: 2026-08-29.

## 1. Goal

Refactor `SergejSchweizer/portfell` so that **all EODHD/provider acquisition, metadata discovery, quote download, corporate-action download, medallion market-data persistence, refresh scheduling, provider credential handling, and provider fallback paths are removed from Portfell**.

Portfell becomes a read-only consumer of the existing PostgreSQL serving plane at `10.10.1.3:54321` produced by `SergejSchweizer/xetra-loader`.

The market-data integration boundary is PostgreSQL only. Portfell must not import `xetra-loader` as a Python package and must not call EODHD or any other market-data provider.

## 2. Hard ownership boundary

```text
SergejSchweizer/xetra-loader
provider acquisition -> validated XETRA datasets -> PostgreSQL 10.10.1.3:54321
                                                   |
                                                   | SELECT only as portfell_app
                                                   v
                                                portfell
                  Metadata -> Univariate -> Bivariate -> Multivariate -> optimization
```

`xetra-loader` owns provider access, download/reconciliation, market-data publication, PostgreSQL market-table writes, sync bookkeeping, and loader scheduling.

`portfell` owns only read-only market-data gateways, analytics/optimization, application-domain state, and the application UI/API.

Portfell must not own:

- EODHD client/configuration/tokens or provider HTTP access;
- XETRA/provider discovery or download commands;
- Bronze/Silver/Gold market-data persistence;
- NAS/filesystem market-data fallback;
- market-data writers, refresh workers, publisher jobs, or market-data cron jobs;
- loader sync-state mutation or loader administration;
- provider credential storage/API/UI;
- dual-read or fail-open fallback paths.

## 3. Frozen external PostgreSQL contract

### 3.1 Endpoint and credentials

- target PostgreSQL endpoint: `10.10.1.3:54321`;
- database name, username, password, TLS options, and full DSN are supplied only through runtime configuration/secrets;
- canonical Portfell configuration seam: `PORTFELL_MARKET_DATABASE_URL`;
- no password, complete DSN, provider key, or EODHD token may be committed;
- production database role is `portfell_app`.

### 3.2 Business schema

Portfell may read only these business tables in schema `xetra_loader`:

- `xetra_loader.listings`;
- `xetra_loader.eod_quotes`;
- `xetra_loader.dividends`;
- `xetra_loader.splits`.

The externally observable contract is:

#### `xetra_loader.listings`

- key: `(isin, exchange, code)`;
- columns consumed by Portfell: `isin`, `exchange`, `code`, `name`, `instrument_type`, `currency`, `country`, `is_active`, `fetched_at_utc`, `published_at_utc`.

#### `xetra_loader.eod_quotes`

- key: `(isin, exchange, code, trade_date)`;
- columns consumed by Portfell: `isin`, `exchange`, `code`, `trade_date`, `timestamp_eod`, `open`, `high`, `low`, `close`, `adjusted_close`, `volume`, `fetched_at_utc`, `published_at_utc`;
- `trade_date` is a PostgreSQL `DATE`;
- `timestamp_eod` is the canonical UTC midnight anchor for `trade_date`, not a claimed physical exchange close timestamp.

#### `xetra_loader.dividends`

- key: `(isin, exchange, code, event_key)`;
- columns consumed by Portfell: `isin`, `exchange`, `code`, `event_key`, `event_date`, `declaration_date`, `record_date`, `payment_date`, `value`, `currency`, `period`, `fetched_at_utc`, `published_at_utc`.

#### `xetra_loader.splits`

- key: `(isin, exchange, code, event_key)`;
- columns consumed by Portfell: `isin`, `exchange`, `code`, `event_key`, `event_date`, `split_ratio`, `split_factor`, `fetched_at_utc`, `published_at_utc`.

All PostgreSQL timestamp columns consumed by Portfell are timezone-aware and decoded as UTC. Full listing identity `(isin, exchange, code)` is preserved everywhere; ISIN alone is never a business key.

### 3.3 Loader control schema is intentionally inaccessible

`xetra_loader_sync` is a loader-owned control-plane schema. Current loader RBAC explicitly revokes `portfell_app` access to that schema and its tables.

Therefore Portfell must:

- never query `xetra_loader_sync.sync_state`;
- never query `xetra_loader_sync.loader_runs`;
- never request broader grants to `xetra_loader_sync`;
- never infer application authorization from loader control-plane state.

Portfell source availability/freshness is an **observational read model** derived only from accessible business-table evidence such as `MAX(trade_date)`, `MAX(published_at_utc)`, and row counts. It must not pretend to know the loader run status.

### 3.4 Read-only fail-closed rule

`portfell_app` has SELECT-only access to `xetra_loader`. Portfell has no market-data DML/DDL path. If PostgreSQL is unavailable, a required table is unavailable, or required source data is insufficient, the affected stage returns a typed unavailable/incomplete state. It never downloads data, reads a local market-data cache, or switches to another provider.

## 4. Single-user target retained

The existing single-user simplification remains part of the active plan and is orthogonal to the market-source cutover.

Delete user, tenant, membership, project-membership, credential-owner, project-bootstrap-worker, project-scoped market refresh, and multi-user authorization concepts. Domain IDs for saved portfolios, optimization runs, analysis runs, and decisions remain allowed but cannot act as security scopes.

Canonical browser routes are:

```text
/metadata
/univariate
/bivariate
/multivariate
```

REST remains under `/api`.

## 5. Git contract for weak agents

Every work order below is intentionally small and atomic.

For every work order:

- exact work-order name appears in branch name, every Conventional Commit message, and PR title;
- record `git status --short --branch` before editing and include it in PR evidence;
- start from the exact merged dependency SHA;
- parallel siblings start from the same predecessor SHA and never from another sibling;
- edit only the owned paths named by the work order;
- if an owned path contains unrelated surviving behavior, preserve it or extract it without broad opportunistic refactoring;
- no compatibility shim, hidden feature flag, provider fallback, or second market-data authority may be introduced;
- focused tests plus `uv run portfell-quality pr` must pass from the final PR SHA;
- current coverage/quality thresholds remain governed only by `GATES.md`.

## 6. Execution graph

```text
PR308
  |
  +--> PR309 || PR310 || PR311 || PR312 || PR313
                         |
                       PR314
                         |
        PR315 || PR316 || PR317 || PR318
                         |
                       PR319
                         |
  +----------------------+---------------------------+
  |          |          |          |          |      |
 PR320      PR321      PR322      PR323      PR324  PR325 || PR326
  |          |          |          |          |      |
  +----------+----------+----------+----------+------+------+
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

Safe parallel waves:

- Wave A after PR308: PR309/PR310/PR311/PR312/PR313;
- Wave B after PR314: PR315/PR316/PR317/PR318;
- Wave C after PR319: PR320/PR321/PR322/PR323/PR324 plus PR325/PR326;
- Wave D after Wave C: PR327/PR328;
- Wave E after PR327+PR328: PR329/PR330/PR331;
- integration gates: PR314, PR319, PR332, PR333, PR334.

With fewer agents, execute any subset of siblings first but keep every sibling based on the same predecessor SHA. Do not rebase an unstarted sibling onto a partially merged sibling.

## 7. Work orders

### PR308 — pr308-xetra-postgres-read-contract

Branch: `refactor/pr308-xetra-postgres-read-contract`.
Commit scope: `refactor(pr308-xetra-postgres-read-contract): ...`.
Depends on: PR296 merged.
Owned paths: new `src/portfell/market_source/config.py`, `contracts.py`, `connection.py`, package init, and focused contract/connection tests only.

Tasks / Acceptance:

- [ ] Add `PORTFELL_MARKET_DATABASE_URL` as the only market-source connection seam; target endpoint is documented as `10.10.1.3:54321`, while database name/password/full DSN remain secret-supplied.
- [ ] Freeze DTOs for the exact columns and keys of `xetra_loader.listings`, `eod_quotes`, `dividends`, and `splits` defined in section 3.
- [ ] Preserve full listing identity `(isin, exchange, code)` and quote/action keys without ISIN-only aliases.
- [ ] Decode all PostgreSQL timestamps as timezone-aware UTC; preserve `trade_date`/event dates as dates and do not reinterpret `timestamp_eod` as an exchange-close timestamp.
- [ ] Add a read-only connection/session factory that sets UTC session semantics and exposes no commit/write helper.
- [ ] Add architecture tests proving `market_source` contains no EODHD/provider HTTP client and does not import `xetra-loader` Python code.
- [ ] Add a negative contract asserting Portfell has no `xetra_loader_sync` repository/API in this package.
- [ ] Focused tests, Ruff, Pyright, and `uv run portfell-quality pr` pass from one SHA.

Parallelization: foundation; no sibling starts before merge.
Security: no hard-coded credentials; read-only authority only.
Determinism: DTO field order, keys, date/time conversion, and ordering contracts are frozen.
Idempotency: connection/read contract creates no market state.
Rollback: remove the new market-source contract package.

### PR309 — pr309-xetra-listings-repository

Branch: `feat/pr309-xetra-listings-repository`.
Commit scope: `feat(pr309-xetra-listings-repository): ...`.
Depends on: PR308.
Owned paths: new `src/portfell/market_source/listings.py` and focused tests.

Tasks / Acceptance:

- [ ] Implement SELECT-only reads from `xetra_loader.listings` using the PR308 connection contract.
- [ ] Support deterministic filters required by Metadata Builder: exchange, instrument type, country, currency, active status, and case-stable `name contains` behavior.
- [ ] Return full `(isin, exchange, code)` identity and preserve multiple listings sharing one ISIN.
- [ ] Use deterministic ordering with an explicit stable tie-break on full identity.
- [ ] Empty result is a typed empty result; connection/schema errors are typed source failures and never trigger provider/filesystem fallback.
- [ ] Tests cover duplicate ISINs across codes/exchanges, nullable metadata, active/inactive rows, filter combinations, ordering, and DB failure.
- [ ] SQL is read-only and contains no DML/DDL.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: may run with PR310-PR313 from the same PR308 merge SHA.
Security: SELECT only.
Determinism: stable filters and ordering.
Idempotency: repeated reads do not mutate state.
Rollback: remove listing repository/tests.

### PR310 — pr310-xetra-quotes-repository

Branch: `feat/pr310-xetra-quotes-repository`.
Commit scope: `feat(pr310-xetra-quotes-repository): ...`.
Depends on: PR308.
Owned paths: new `src/portfell/market_source/quotes.py` and focused tests.

Tasks / Acceptance:

- [ ] Implement SELECT-only reads from `xetra_loader.eod_quotes` by full listing identity and inclusive date range.
- [ ] Return `trade_date`, `timestamp_eod`, OHLC, `adjusted_close`, `volume`, `fetched_at_utc`, and `published_at_utc` without provider-specific renaming that loses source semantics.
- [ ] Order deterministically by full identity then `trade_date`.
- [ ] Reject/raise typed contract failure if a test fixture contains duplicate quote keys instead of silently deduplicating.
- [ ] Preserve nullable OHLC/adjusted-close/volume values and require `close` according to the external contract.
- [ ] Tests prove UTC timestamp decoding, canonical midnight anchor preservation, date-bound behavior, missing history, multiple listings, and DB failure.
- [ ] No query or failure path reads filesystem/NAS or invokes provider HTTP.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: may run with PR309/PR311/PR312/PR313.
Security: SELECT only.
Determinism: exact key/date ordering.
Idempotency: read-only.
Rollback: remove quote repository/tests.

### PR311 — pr311-xetra-dividends-repository

Branch: `feat/pr311-xetra-dividends-repository`.
Commit scope: `feat(pr311-xetra-dividends-repository): ...`.
Depends on: PR308.
Owned paths: new `src/portfell/market_source/dividends.py` and focused tests.

Tasks / Acceptance:

- [ ] Implement SELECT-only reads from `xetra_loader.dividends` by full listing identity and event-date range.
- [ ] Preserve loader `event_key` exactly; Portfell never regenerates or substitutes an event identity.
- [ ] Preserve `value`, currency, period, declaration/record/payment dates, and UTC fetched/published timestamps.
- [ ] Order deterministically by full identity, `event_date`, then `event_key`.
- [ ] Duplicate action keys are typed contract failures, not silently collapsed.
- [ ] Tests cover nullable auxiliary dates/currency/period, repeated same-day distinct events, ordering, empty history, and DB failure.
- [ ] No provider/filesystem fallback exists.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: may run with PR309/PR310/PR312/PR313.
Security: SELECT only.
Determinism: stable event identity/order.
Idempotency: read-only.
Rollback: remove dividend repository/tests.

### PR312 — pr312-xetra-splits-repository

Branch: `feat/pr312-xetra-splits-repository`.
Commit scope: `feat(pr312-xetra-splits-repository): ...`.
Depends on: PR308.
Owned paths: new `src/portfell/market_source/splits.py` and focused tests.

Tasks / Acceptance:

- [ ] Implement SELECT-only reads from `xetra_loader.splits` by full listing identity and event-date range.
- [ ] Preserve loader `event_key`, textual `split_ratio`, optional numeric `split_factor`, and UTC fetched/published timestamps exactly.
- [ ] Order deterministically by full identity, `event_date`, then `event_key`.
- [ ] Duplicate event keys are typed contract failures.
- [ ] Tests cover textual ratio preservation, nullable split factor, repeated same-day distinct events, ordering, empty history, and DB failure.
- [ ] No local recomputation of event identity and no provider/filesystem fallback exists.
- [ ] SQL is read-only.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: may run with PR309/PR310/PR311/PR313.
Security: SELECT only.
Determinism: stable event identity/order.
Idempotency: read-only.
Rollback: remove split repository/tests.

### PR313 — pr313-xetra-source-status-read-model

Branch: `feat/pr313-xetra-source-status-read-model`.
Commit scope: `feat(pr313-xetra-source-status-read-model): ...`.
Depends on: PR308.
Owned paths: new `src/portfell/market_source/status.py` and focused tests.

Tasks / Acceptance:

- [ ] Implement an observational source-status DTO using only accessible `xetra_loader` business tables.
- [ ] Evidence may include table reachability, row counts, maximum `published_at_utc`, and quote maximum `trade_date`; field names must explicitly describe observed data rather than loader-run state.
- [ ] Do not query `xetra_loader_sync.sync_state` or `xetra_loader_sync.loader_runs` under any code path.
- [ ] Do not infer `applied`, `noop`, run ID, semantic fingerprint, or other loader-internal status that is not observable through the business schema.
- [ ] Database-unavailable/schema-unavailable/empty-table states are typed separately.
- [ ] Tests prove no sync-schema SQL appears and prove deterministic status for fresh, empty, partial, and unavailable fixtures.
- [ ] The read model performs no writes and starts no refresh.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: may run with PR309-PR312.
Security: honors `portfell_app` denial on `xetra_loader_sync`.
Determinism: same database snapshot produces same status DTO.
Idempotency: read-only.
Rollback: remove status read model/tests.

### PR314 — pr314-xetra-market-gateway-integration

Branch: `feat/pr314-xetra-market-gateway-integration`.
Commit scope: `feat(pr314-xetra-market-gateway-integration): ...`.
Depends on: PR309-PR313.
Owned paths: new `src/portfell/market_source/gateway.py`, package exports, architecture tests, gateway integration tests.

Tasks / Acceptance:

- [ ] Compose listings, quotes, dividends, splits, and source-status repositories behind one typed read-only `MarketDataGateway` used by application stages.
- [ ] Freeze gateway methods so stage code never embeds table names or raw PostgreSQL SQL.
- [ ] Add architecture guard: direct `xetra_loader` SQL is allowed only inside `src/portfell/market_source/**`.
- [ ] Add architecture guard: no market gateway method can write, refresh, download, publish, or accept a provider token.
- [ ] Add architecture guard: no `xetra_loader_sync` reference is allowed in executable Portfell source.
- [ ] Gateway errors preserve typed source-unavailable/incomplete semantics and never select another data source.
- [ ] Integration fixtures cover all four tables and duplicate ISIN/full-identity behavior.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: integration gate; Wave B starts only after merge.
Security: single read-only boundary.
Determinism: repository ordering propagates unchanged.
Idempotency: read-only.
Rollback: remove gateway composition while leaving repositories isolated.

### PR315 — pr315-metadata-stage-xetra-cutover

Branch: `refactor/pr315-metadata-stage-xetra-cutover`.
Commit scope: `refactor(pr315-metadata-stage-xetra-cutover): ...`.
Depends on: PR314.
Owned paths: Metadata Builder/backend metadata source seam and metadata-stage tests only; physical provider deletion is later.

Tasks / Acceptance:

- [ ] Replace Metadata stage market-universe input with `MarketDataGateway.listings` only.
- [ ] Preserve existing relevant builder filters and full listing identity.
- [ ] Remove runtime behavior that starts metadata discovery/download/refresh from the Metadata stage.
- [ ] Render/return source empty/unavailable evidence explicitly rather than manufacturing zero-history success.
- [ ] Existing analytical selection semantics are regression-tested against a contract fixture with equivalent listing rows.
- [ ] No Metadata-stage path reads Bronze/Silver/Gold/filesystem/NAS or provider HTTP.
- [ ] Duplicate UI/API activation cannot trigger a market refresh because no such command exists after this cutover.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: may run with PR316-PR318 from the same PR314 merge SHA.
Security: no provider credential enters Metadata stage.
Determinism: database snapshot + builder criteria determine result.
Idempotency: reads/filters only.
Rollback: restore prior stage seam without deleting gateway.

### PR316 — pr316-univariate-stage-xetra-cutover

Branch: `refactor/pr316-univariate-stage-xetra-cutover`.
Commit scope: `refactor(pr316-univariate-stage-xetra-cutover): ...`.
Depends on: PR314.
Owned paths: Univariate service/input assembly seam and focused tests only.

Tasks / Acceptance:

- [ ] Source quote history, dividends, and splits only through `MarketDataGateway`.
- [ ] Preserve current univariate formulas, annualization rules, date-window semantics, distribution metrics, and selection behavior; this PR changes source plumbing only.
- [ ] Preserve full listing identity through input assembly and outputs.
- [ ] Missing/incomplete required history yields typed unavailable/ineligible evidence according to existing analytical contracts; it never invokes a download.
- [ ] Regression fixture proves identical analytical output for equivalent pre-cutover and PostgreSQL input rows.
- [ ] No direct SQL/provider/lake/filesystem read remains in the Univariate stage.
- [ ] Tests cover split/dividend inputs where those inputs affect existing formulas.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: may run with PR315/PR317/PR318.
Security: gateway-only market read.
Determinism: existing analytical determinism preserved.
Idempotency: calculation run may persist analytical state only; never market data.
Rollback: restore prior stage adapter.

### PR317 — pr317-bivariate-stage-xetra-cutover

Branch: `refactor/pr317-bivariate-stage-xetra-cutover`.
Commit scope: `refactor(pr317-bivariate-stage-xetra-cutover): ...`.
Depends on: PR314.
Owned paths: Bivariate service/input-alignment seam and focused tests only.

Tasks / Acceptance:

- [ ] Source all required quote histories through `MarketDataGateway` only.
- [ ] Preserve pairwise formulas, pair identity, common-calendar/intersection rules, minimum-observation logic, and existing diagnostics.
- [ ] Preserve full listing identity for both sides of every pair.
- [ ] Deterministic alignment tests cover mismatched calendars, missing dates, duplicate ISINs under different listing identities, and empty overlap.
- [ ] Regression fixture proves equivalent pre-cutover rows and PostgreSQL rows produce equivalent bivariate results.
- [ ] No direct SQL/provider/lake/filesystem read remains in the Bivariate stage.
- [ ] Source failure is typed and never starts/falls back to a downloader.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: may run with PR315/PR316/PR318.
Security: gateway-only market read.
Determinism: alignment and ordering are frozen.
Idempotency: analytics persistence only; no market mutation.
Rollback: restore prior stage adapter.

### PR318 — pr318-multivariate-stage-xetra-cutover

Branch: `refactor/pr318-multivariate-stage-xetra-cutover`.
Commit scope: `refactor(pr318-multivariate-stage-xetra-cutover): ...`.
Depends on: PR314.
Owned paths: Multivariate/optimizer market-input assembly seam and focused tests only.

Tasks / Acceptance:

- [ ] Build the optimizer universe, aligned return matrix, and source-dependent risk inputs only from `MarketDataGateway` data.
- [ ] Preserve existing objectives, solver interfaces, risk-model logic, walk-forward/OOS boundaries, and winner-selection semantics; no optimizer redesign is allowed here.
- [ ] Preserve full listing identity through candidate construction and final weights.
- [ ] Multi-asset alignment is deterministic and tests cover missing dates/insufficient common history.
- [ ] Exact fixture matrices are asserted before optimizer invocation.
- [ ] No direct SQL/provider/lake/filesystem read remains in Multivariate market-input assembly.
- [ ] Missing source data yields typed unavailable/ineligible candidates and never provider fallback.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: may run with PR315-PR317.
Security: gateway-only market read.
Determinism: exact matrix assembly and existing optimizer determinism preserved.
Idempotency: analytical artifacts only; no market mutation.
Rollback: restore prior input adapter.

### PR319 — pr319-four-stage-xetra-read-integration-gate

Branch: `test/pr319-four-stage-xetra-read-integration-gate`.
Commit scope: `test(pr319-four-stage-xetra-read-integration-gate): ...`.
Depends on: PR315-PR318.
Owned paths: cross-stage integration tests, market-source architecture tests, test fixtures only.

Tasks / Acceptance:

- [ ] Exercise Metadata -> Univariate -> Bivariate -> Multivariate against one contract-faithful PostgreSQL fixture exposing schema `xetra_loader` and all four business tables.
- [ ] Prove every stage obtains market inputs through `MarketDataGateway`; direct source readers outside `market_source` fail architecture tests.
- [ ] Prove no test requires an EODHD token, EODHD stub, NAS mount, Bronze/Silver/Gold market directory, or market refresh worker.
- [ ] Prove PostgreSQL unavailability fails closed at the affected workflow boundary and no fallback path executes.
- [ ] Prove multiple listings with one ISIN remain distinct end-to-end.
- [ ] Prove date/timestamp/action semantics survive all stage adapters unchanged.
- [ ] Run focused integration suite and `uv run portfell-quality pr` successfully.

Parallelization: integration gate; deletion wave starts only after merge.
Security: fixture verifies read-only market boundary.
Determinism: same database fixture produces identical stage inputs/results.
Idempotency: repeat run creates no market-table changes.
Rollback: tests only.

### PR320 — pr320-delete-eodhd-provider-client-and-fetchers

Branch: `refactor/pr320-delete-eodhd-provider-client-and-fetchers`.
Commit scope: `refactor(pr320-delete-eodhd-provider-client-and-fetchers): ...`.
Depends on: PR319.
Owned paths: `src/portfell/http.py`, `search.py`, `fetch_all_metadata.py`, `fetch_all_quotes.py`, provider-specific portions of `config.py`, `contracts.py`, `cli.py`, and their focused tests.

Tasks / Acceptance:

- [ ] Delete the EODHD HTTP client, endpoint/request/retry logic, provider discovery/search, metadata fetcher, and quote fetcher from executable Portfell source.
- [ ] Remove EODHD token configuration and CLI commands/options that start provider acquisition.
- [ ] Preserve non-provider application configuration/contracts/CLI commands that remain required; no unrelated API removal.
- [ ] Remove tests whose only purpose is EODHD/provider acquisition and replace any surviving analytical fixtures with provider-neutral rows where needed.
- [ ] Source scan over executable Python fails on known EODHD endpoint/client/token symbols except an explicit historical-doc allowlist.
- [ ] Application imports succeed without any provider token environment variable.
- [ ] No compatibility wrapper or disabled EODHD implementation remains.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: may run with PR321-PR326 from the same PR319 merge SHA; owns shared `config.py`, `contracts.py`, `cli.py` exclusively in this wave.
Security: removes provider secrets/HTTP authority.
Determinism: no acquisition behavior remains.
Idempotency: deletion only.
Rollback: revert this PR only while PR319 gateway remains usable.

### PR321 — pr321-delete-portfell-market-medallion

Branch: `refactor/pr321-delete-portfell-market-medallion`.
Commit scope: `refactor(pr321-delete-portfell-market-medallion): ...`.
Depends on: PR319.
Owned paths: `src/portfell/bronze.py`, `silver.py`, market-data portions of `gold.py`, `pipeline.py`, their market-loading tests and imports.

Tasks / Acceptance:

- [ ] Delete Portfell-owned Bronze/Silver market persistence and market-data Gold publication paths.
- [ ] Delete pipeline stages whose purpose is provider market-data ingestion/transformation/publication.
- [ ] If `gold.py` contains a surviving analytical helper, move only that helper to an analytics-owned module before deleting the market-persistence authority; no market reader/writer survives under a renamed file.
- [ ] Remove imports/callers of the deleted medallion market stack from executable source.
- [ ] Keep analytical DecisionArtifacts/statistics/optimizer persistence untouched.
- [ ] Tests prove the four-stage workflow of PR319 still runs from PostgreSQL without any medallion directory.
- [ ] Source guard fails if `bronze`, `silver`, or legacy market Gold persistence is reintroduced as a market-source dependency.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: may run with PR320/PR322-PR326.
Security: removes duplicate local market-data authority.
Determinism: source-of-truth reduced to PostgreSQL.
Idempotency: deletion only.
Rollback: revert this PR without altering PostgreSQL.

### PR322 — pr322-delete-portfell-market-filesystem-nas-plane

Branch: `refactor/pr322-delete-portfell-market-filesystem-nas-plane`.
Commit scope: `refactor(pr322-delete-portfell-market-filesystem-nas-plane): ...`.
Depends on: PR319.
Owned paths: market-data portions of `src/portfell/paths.py`, `table_io.py`, `ugreen_nas_data_root_preflight.py`, market-only persistent inventory/import code, and focused tests.

Tasks / Acceptance:

- [ ] Remove market-data directory/NAS path configuration and preflight requirements from Portfell runtime.
- [ ] Remove table-I/O helpers used only for market-data Bronze/Silver/Gold/local-cache persistence.
- [ ] Preserve filesystem use that is demonstrably unrelated to market-data acquisition only when an existing surviving application feature requires it.
- [ ] Remove startup/readiness checks that block Portfell because a market NAS path is missing.
- [ ] Tests prove application startup and all four stages require no market-data filesystem mount.
- [ ] Source guard rejects any market-source fallback to local files/NAS.
- [ ] No data migration from old market files is introduced; old market files are disposable after cutover.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: may run with PR320/PR321/PR323-PR326; do not edit provider config files owned by PR320.
Security: eliminates filesystem fallback authority.
Determinism: external PostgreSQL is sole market source.
Idempotency: deletion only.
Rollback: revert application code only; PostgreSQL unchanged.

### PR323 — pr323-delete-portfell-market-refresh-scheduler

Branch: `refactor/pr323-delete-portfell-market-refresh-scheduler`.
Commit scope: `refactor(pr323-delete-portfell-market-refresh-scheduler): ...`.
Depends on: PR319.
Owned paths: `src/portfell/shared_market_cron.py`, `shared_market_refresh.py`, `shared_market_data.py`, `shared_observations.py`, `shared_metadata_catalog.py`, `hosted_shared_coverage_bootstrap.py`, `hosted_shared_market_research_data.py`, `hosted_shared_quote_publisher.py`, related refresh docs/tests.

Tasks / Acceptance:

- [ ] Delete Portfell-owned market refresh scheduling, union-refresh planning, provider refresh execution, shared quote publication, and shared market-data cache/read authority.
- [ ] Replace any surviving analytics caller with PR314 `MarketDataGateway`; no second market read seam remains.
- [ ] Delete Sunday/periodic market-download scheduler behavior from Portfell; loader scheduling remains external and loader-owned.
- [ ] Remove refresh locks/status/progress concepts that are market-acquisition-specific while preserving analytical-run locking where still needed.
- [ ] Tests prove no Portfell process starts, schedules, or retries market acquisition.
- [ ] Source guard rejects imports of deleted shared-market modules.
- [ ] Four-stage calculations remain runnable from PostgreSQL after deletion.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: may run with PR320-PR322/PR324-PR326.
Security: removes provider scheduling and duplicate publisher authority.
Determinism: market snapshot is whatever PostgreSQL exposes at read time.
Idempotency: no market refresh exists.
Rollback: revert Portfell code only; do not change loader schedule.

### PR324 — pr324-delete-hosted-market-download-jobs

Branch: `refactor/pr324-delete-hosted-market-download-jobs`.
Commit scope: `refactor(pr324-delete-hosted-market-download-jobs): ...`.
Depends on: PR319.
Owned paths: hosted download/metadata-refresh/quote-run job schemas, repositories, workers, services/routes, and their focused tests.

Tasks / Acceptance:

- [ ] Delete `hosted_download_run_*` market-download lifecycle authority.
- [ ] Delete metadata-refresh job repository/worker/schema and provider-backed metadata refresh commands.
- [ ] Delete quote-run lifecycle/service/routes whose purpose is downloading/publishing market quotes.
- [ ] Remove their API routes, queue/job registration, status-event hooks, and dependency-composition bindings.
- [ ] Preserve analytical calculation-run lifecycle/status APIs unrelated to market acquisition.
- [ ] OpenAPI/route tests prove no market download/quote refresh/metadata refresh command endpoint remains.
- [ ] Application composition has no market downloader worker dependency.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: may run with PR320-PR323/PR325-PR326.
Security: removes remotely triggerable provider acquisition.
Determinism: command surface reduced to analytics only.
Idempotency: deletion only.
Rollback: revert this PR only.

### PR325 — pr325-delete-provider-credential-backend

Branch: `refactor/pr325-delete-provider-credential-backend`.
Commit scope: `refactor(pr325-delete-provider-credential-backend): ...`.
Depends on: PR319.
Owned paths: `src/portfell/provider_credential_schema.py`, `hosted_credentials.py`, `hosted_credential_project_service.py`, `hosted_routes_credentials.py`, provider-specific ingestion/entitlement branches, and focused tests.

Tasks / Acceptance:

- [ ] Delete EODHD/provider credential persistence schemas and repositories from Portfell.
- [ ] Delete API/service operations for storing, validating, rotating, assigning, or reading provider credentials.
- [ ] Remove provider credential ownership from project/user/domain state while preserving unrelated application state until PR327.
- [ ] Remove KEK/encryption configuration that exists only for provider credentials.
- [ ] OpenAPI and source tests prove no provider credential route, DTO, table, secret store, or validation service remains.
- [ ] Runtime starts with only PostgreSQL market-source credentials and requires no EODHD/provider credential.
- [ ] No substitute plaintext provider token setting is introduced.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: may run with PR320-PR324/PR326; provider UI is owned by PR326.
Security: eliminates provider-secret attack surface.
Determinism: credential-dependent branches disappear.
Idempotency: deletion only.
Rollback: revert this PR only.

### PR326 — pr326-delete-provider-loading-ui

Branch: `refactor/pr326-delete-provider-loading-ui`.
Commit scope: `refactor(pr326-delete-provider-loading-ui): ...`.
Depends on: PR319.
Owned paths: browser/provider-loading controls including `apps/web/src/shell/metadata-fetch-context.tsx`, `quote-progress.ts`, Metadata provider fetch/token/progress controls, frontend provider-loading contracts/tests.

Tasks / Acceptance:

- [ ] Remove provider token input/storage/display from browser code.
- [ ] Remove metadata fetch, quote fetch, refresh, retry-download, and acquisition progress controls from the UI.
- [ ] Metadata page becomes a view/filter over PostgreSQL-backed listings and keeps analytical selection controls only.
- [ ] Remove frontend API calls/contracts that start or poll market acquisition while preserving analytical run controls.
- [ ] Browser storage and network tests prove no provider credential or provider-download command is emitted.
- [ ] Source-unavailable state is rendered as unavailable with no fallback/download CTA.
- [ ] Existing analytical pages remain navigable and their calculation controls continue to work.
- [ ] Focused frontend tests and repository `uv run portfell-quality pr` pass.

Parallelization: may run with PR320-PR325; do not edit project/user routing owned later by PR328.
Security: no provider secret reaches browser.
Determinism: UI renders persisted/server-read source state only.
Idempotency: no market acquisition command exists.
Rollback: revert provider UI removal only.

### PR327 — pr327-single-user-backend-cutover

Branch: `refactor/pr327-single-user-backend-cutover`.
Commit scope: `refactor(pr327-single-user-backend-cutover): ...`.
Depends on: PR320-PR326.
Owned paths: backend user/tenant/membership/project-security/project-bootstrap authority and tests; excludes market-source/provider files already owned by prior PRs.

Tasks / Acceptance:

- [ ] Remove user, tenant, membership, project-membership, credential-owner, and project-bootstrap security/runtime concepts.
- [ ] Replace request-time multi-user/project authorization with one application workspace.
- [ ] Preserve non-security domain IDs for saved portfolios, analysis runs, optimization runs, and decisions where required.
- [ ] Remove project-scoped market refresh/bootstrap concepts completely; no replacement downloader exists.
- [ ] API/service tests run without user/tenant/project membership seed data.
- [ ] Architecture tests reject new market-source authorization or provider-credential authority hidden behind user/project code.
- [ ] Existing analytical persistence remains scoped to the single workspace and deterministic domain IDs.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: may run in parallel with PR328 after deletion wave is merged.
Security: simplifies authorization surface; does not broaden market DB grants.
Determinism: one workspace context.
Idempotency: repeated startup does not create duplicate workspace/domain state.
Rollback: revert backend simplification only.

### PR328 — pr328-single-user-ui-route-cutover

Branch: `refactor/pr328-single-user-ui-route-cutover`.
Commit scope: `refactor(pr328-single-user-ui-route-cutover): ...`.
Depends on: PR320-PR326.
Owned paths: UI shell/navigation/project selector/project slug/user-switching routes/tests only; excludes provider-loading files removed by PR326.

Tasks / Acceptance:

- [ ] Canonical browser routes become exactly `/metadata`, `/univariate`, `/bivariate`, `/multivariate`.
- [ ] Remove project selector, project-slug route prefix, user switching, and membership-dependent navigation.
- [ ] Preserve four-stage analytics navigation and page functionality.
- [ ] Unknown legacy project routes do not silently map to another workspace; use an explicit redirect/not-found rule frozen by tests.
- [ ] UI tests prove no project/user/provider-loading control remains.
- [ ] REST remains under `/api` and route snapshot tests are updated deterministically.
- [ ] Responsive/browser smoke tests pass for all four routes.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: may run with PR327 from the same deletion-wave merge SHA.
Security: URL/project identity no longer acts as authorization.
Determinism: fixed route registry.
Idempotency: navigation is read-only.
Rollback: revert route/shell changes only.

### PR329 — pr329-remove-provider-packaging-dependencies

Branch: `refactor/pr329-remove-provider-packaging-dependencies`.
Commit scope: `refactor(pr329-remove-provider-packaging-dependencies): ...`.
Depends on: PR327+PR328.
Owned paths: `pyproject.toml`, `uv.lock`, package/entrypoint metadata, dependency-focused tests only.

Tasks / Acceptance:

- [ ] Remove dependencies used only by EODHD/provider acquisition, market medallion loading, or removed provider credential flows.
- [ ] Remove obsolete provider/download CLI entrypoints and package extras without removing analytics/runtime dependencies still imported on `main`.
- [ ] Regenerate `uv.lock` deterministically from the final dependency declaration.
- [ ] Clean-environment install and import tests pass with no provider token or market-data filesystem.
- [ ] Dependency scan proves no removed provider SDK/client is transitively required by Portfell source.
- [ ] No dependency is added merely to recreate a second data plane.
- [ ] `uv sync --locked` and `uv run portfell-quality pr` pass.

Parallelization: may run with PR330/PR331 after PR327+PR328.
Security: reduces provider/dependency attack surface.
Determinism: locked dependency graph.
Idempotency: clean install reproducible.
Rollback: restore dependency manifest/lock only.

### PR330 — pr330-external-postgres-runtime-compose

Branch: `refactor/pr330-external-postgres-runtime-compose`.
Commit scope: `refactor(pr330-external-postgres-runtime-compose): ...`.
Depends on: PR327+PR328.
Owned paths: `.env.example`, Compose files, deployment runtime wiring, `tests/e2e/**`, runtime/Compose tests.

Tasks / Acceptance:

- [ ] Production runtime requires external `PORTFELL_MARKET_DATABASE_URL`; documented target endpoint is `10.10.1.3:54321`, but no password/full DSN is committed.
- [ ] Remove EODHD token/KEK/provider secret variables, EODHD test stub, provider-token test secrets, and market download/refresh worker services.
- [ ] Portfell production Compose does not own an `xetra_loader` market database or loader service; the serving database is external.
- [ ] E2E uses a contract-faithful PostgreSQL fixture for CI/local isolation or an explicitly supplied external DSN; it never emulates EODHD.
- [ ] Health/startup failure is explicit when required PostgreSQL configuration is absent or unreachable.
- [ ] E2E proves the application cannot mutate `xetra_loader` when run with a read-only test role equivalent to `portfell_app`.
- [ ] `docker compose config`, container smoke, focused E2E tests, and `uv run portfell-quality pr` pass.

Parallelization: may run with PR329/PR331.
Security: only DB secret remains for market-source access; no provider secret.
Determinism: fixed Compose topology/config contract.
Idempotency: restart creates no market data.
Rollback: restore runtime manifests only.

### PR331 — pr331-remove-eodhd-docs-and-governance

Branch: `docs/pr331-remove-eodhd-docs-and-governance`.
Commit scope: `docs(pr331-remove-eodhd-docs-and-governance): ...`.
Depends on: PR327+PR328.
Owned paths: README/ARCHITECTURE/CONTRACTS/DOCKER/GOALS/RISKS/current docs, EODHD-derived Portfell docs/CSV artifacts, governance/source-scan tests; historical archive may remain clearly marked non-authoritative.

Tasks / Acceptance:

- [ ] Update authoritative documentation to show `xetra-loader -> PostgreSQL xetra_loader -> Portfell` and no direct EODHD path inside Portfell.
- [ ] Document exact four business tables, full keys, `trade_date`/UTC timestamp semantics, and the read-only `portfell_app` boundary.
- [ ] Document that `xetra_loader_sync` is loader-owned and intentionally inaccessible; Portfell source status is observational only.
- [ ] Remove obsolete EODHD discovery/provider-token/how-to-fetch documentation and non-authoritative EODHD-derived catalog CSV artifacts from active docs when no runtime/test consumes them.
- [ ] Mark historical archived backlog documents as historical rather than allowing them to override this plan.
- [ ] Add/refresh governance test that rejects EODHD/provider acquisition symbols in executable source and active runtime/docs, with a narrow historical archive allowlist only.
- [ ] Documentation references no fictional `portfell_market` schema or obsolete `xetra-data-loader` repository name.
- [ ] Docs validation and `uv run portfell-quality pr` pass.

Parallelization: may run with PR329/PR330.
Security: docs expose no secrets/full DSNs.
Determinism: one authoritative architecture story.
Idempotency: docs/test-only.
Rollback: revert documentation/governance changes only.

### PR332 — pr332-live-xetra-postgres-readonly-contract-gate

Branch: `test/pr332-live-xetra-postgres-readonly-contract-gate`.
Commit scope: `test(pr332-live-xetra-postgres-readonly-contract-gate): ...`.
Depends on: PR329-PR331 and reachable prepared `xetra-loader` PostgreSQL serving plane.
Owned paths: live-contract smoke tests/runbook evidence only.

Tasks / Acceptance:

- [ ] Connect to the configured real target serving plane at `10.10.1.3:54321` using the production-equivalent `portfell_app` identity without committing credentials.
- [ ] Verify SELECT works for `xetra_loader.listings`, `eod_quotes`, `dividends`, and `splits` and the observed columns/types/primary-key semantics match section 3.
- [ ] Verify representative full identities and quote/action rows round-trip through PR314 repositories with correct UTC/date semantics.
- [ ] Verify attempted INSERT/UPDATE/DELETE/DDL on `xetra_loader` fails for `portfell_app`.
- [ ] Verify access to `xetra_loader_sync` fails for `portfell_app`; this failure is expected PASS evidence, not a defect.
- [ ] Verify no Python-package coupling to `xetra-loader` is needed for the smoke test.
- [ ] Record sanitized endpoint/schema/table/row-count/date-bound evidence and exact Portfell/xetra-loader commit SHAs; never record passwords/full DSNs.
- [ ] Live smoke and `uv run portfell-quality pr` pass from one SHA.

Parallelization: integration gate; not parallel with PR333 because its evidence is a prerequisite.
Security: explicitly proves least privilege.
Determinism: queries use stable ordering and sanitized evidence format.
Idempotency: mutation attempts fail; successful operations are SELECT only.
Rollback: tests/evidence only.

### PR333 — pr333-full-postgres-source-replacement-e2e

Branch: `test/pr333-full-postgres-source-replacement-e2e`.
Commit scope: `test(pr333-full-postgres-source-replacement-e2e): ...`.
Depends on: PR332.
Owned paths: final source-replacement integration/E2E tests and completion evidence only.

Tasks / Acceptance:

- [ ] Cold-start Portfell with no EODHD/provider variables, no market NAS/filesystem, no local medallion market state, and only the configured PostgreSQL market read plane.
- [ ] Execute Metadata -> Univariate -> Bivariate -> Multivariate successfully against contract-faithful/verified XETRA PostgreSQL data.
- [ ] Prove all market reads are SELECTs against `xetra_loader` through `MarketDataGateway`; no direct SQL outside the source package.
- [ ] Simulate PostgreSQL unavailable, empty required history, and partial history; every case fails closed/typed and never downloads/falls back.
- [ ] Repository-wide executable-source scan proves no EODHD client/token/fetcher, provider credential flow, medallion market writer, market refresh scheduler, or filesystem market fallback remains.
- [ ] Prove `xetra_loader_sync` remains unqueried by application code and inaccessible to the app role.
- [ ] Prove repeated application/workflow execution leaves all four `xetra_loader` business tables unchanged.
- [ ] Full focused E2E suite and `uv run portfell-quality pr` pass from one SHA.

Parallelization: final technical integration gate.
Security: end-to-end least privilege/fail-closed proof.
Determinism: fixed fixture/verified source snapshot and stable evidence.
Idempotency: repeated run has zero market mutation.
Rollback: tests/evidence only.

### PR334 — pr334-production-postgres-cutover-runbook

Branch: `docs/pr334-production-postgres-cutover-runbook`.
Commit scope: `docs(pr334-production-postgres-cutover-runbook): ...`.
Depends on: PR333.
Owned paths: production cutover/rollback runbook and final operator checklist only.

Tasks / Acceptance:

- [ ] Document deployment preflight for `PORTFELL_MARKET_DATABASE_URL`, endpoint reachability, four business-table SELECTs, `portfell_app` role, and UTC session behavior.
- [ ] Require PR332 live-contract PASS and PR333 full E2E PASS before production cutover.
- [ ] Back up only surviving Portfell analytical/application state; legacy Portfell market-data files/tables/caches are classified as disposable after verified cutover and are not migrated into the serving plane.
- [ ] Provide deterministic smoke checks for `/metadata`, `/univariate`, `/bivariate`, `/multivariate` and representative analytical runs.
- [ ] Rollback changes only Portfell application version/configuration; rollback must never reactivate EODHD/provider download, market medallion persistence, or filesystem fallback.
- [ ] Include explicit verification that `xetra_loader_sync` remains inaccessible and no broader database grants are requested.
- [ ] Operator checklist contains no secret values and can be executed without architectural guessing.
- [ ] Documentation validation and `uv run portfell-quality pr` pass.

Parallelization: terminal documentation gate.
Security: no secret disclosure; rollback preserves least privilege.
Determinism: ordered preflight/cutover/rollback procedure.
Idempotency: repeating read-only preflight/smoke checks does not mutate market data.
Rollback: defined in the runbook and never restores legacy data acquisition.

## 8. Final completion gate

The Portfell source cutover is complete only when all of the following hold on clean `main`:

- Metadata, Univariate, Bivariate, and Multivariate obtain market data exclusively through `MarketDataGateway` backed by PostgreSQL at the configured serving endpoint;
- business source schema is exactly `xetra_loader` with `listings`, `eod_quotes`, `dividends`, and `splits`;
- full listing identity `(isin, exchange, code)` is preserved end-to-end;
- `portfell_app` can SELECT business tables and cannot mutate them;
- `portfell_app` cannot access `xetra_loader_sync`, and Portfell contains no executable sync-schema query;
- no EODHD/provider client, token, fetcher, discovery, credential storage/API/UI, acquisition progress, or provider fallback remains in Portfell;
- no Portfell market-data Bronze/Silver/Gold writer, NAS/filesystem market fallback, shared market refresh/publisher, market-download worker, or market-data cron remains;
- no market-data DML/DDL path exists in Portfell;
- PostgreSQL outage/incomplete data fails closed with typed source evidence and never starts a downloader;
- current analytical formulas/optimizer semantics are preserved by source-cutover regression tests;
- single-user backend/UI target is complete with canonical routes `/metadata`, `/univariate`, `/bivariate`, `/multivariate`;
- production runtime requires no EODHD/provider secret or market NAS mount;
- PR332 proves the real serving-plane contract and least privilege;
- PR333 proves complete source replacement end-to-end;
- PR334 provides an executable production cutover/rollback procedure that cannot reactivate legacy acquisition.
