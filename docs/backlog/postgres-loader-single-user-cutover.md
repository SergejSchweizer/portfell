# PostgreSQL XETRA Read-Plane and Single-User Portfell Cutover

Status: implementation authority after PR296 is merged.

Last reviewed: 2026-08-29.

## 1. Goal and scope

Refactor `SergejSchweizer/portfell` so that all market data used by Metadata, Univariate, Bivariate, and Multivariate comes from the external PostgreSQL serving plane produced by `SergejSchweizer/xetra-loader`.

Portfell must contain no executable EODHD/provider acquisition plane after this series: no provider HTTP client, token, discovery, metadata/quote/corporate-action download, provider credential service, market Bronze/Silver/Gold writer, NAS/filesystem market fallback, shared-market publisher, market refresh worker, or market-download scheduler.

The PostgreSQL integration boundary is the database contract only. Portfell must never import `xetra-loader` as a Python package.

This series also retains the already-planned single-user simplification. It does **not** cancel the non-market product requirements from the older Dash/Multivariate backlog. Old PR264-PR295 implementation branches are frozen reference branches and must not be merged as-is because their market-source and multi-project assumptions conflict with this cutover. Their still-valid product requirements are explicitly reconciled in terminal planning gate PR343.

## 2. Hard ownership boundary

```text
SergejSchweizer/xetra-loader
provider acquisition -> Bronze/Silver/Gold -> PostgreSQL 10.10.1.3:54321
                                             |
                                             | SELECT-only application access
                                             v
                                          portfell
          Metadata -> Univariate -> Bivariate -> Multivariate -> optimization
```

`xetra-loader` owns provider access, market ingestion, reconciliation, serving-table DML/DDL, sync bookkeeping, and loader scheduling.

`portfell` owns read-only market access, deterministic analysis projections, analytical/application state, portfolio analytics/optimization, and UI/API.

## 3. Frozen external PostgreSQL contract

### 3.1 Endpoint and runtime identity

- Production endpoint is `10.10.1.3:54321`.
- Canonical Portfell seam is `PORTFELL_MARKET_DATABASE_URL`.
- Database name, LOGIN username, password, TLS options, and full DSN are runtime secrets and are never committed.
- In `xetra-loader`, `portfell_app` is a **NOLOGIN group role**, not a login account.
- The Portfell DSN therefore authenticates as a secret-supplied LOGIN role that must be a member of `portfell_app`.
- Portfell must fail closed if the current LOGIN role is a PostgreSQL superuser, is not a member of `portfell_app`, or has broader market/control-plane privileges than the frozen consumer contract.
- Portfell sets UTC session semantics and uses read-only transactions. Market snapshots used by one analytical operation use `REPEATABLE READ, READ ONLY` so cross-table inputs come from one coherent PostgreSQL snapshot.

No work order may invent or commit a login-role name or password.

### 3.2 Business schema

Portfell may read only these market business tables:

- `xetra_loader.listings`;
- `xetra_loader.eod_quotes`;
- `xetra_loader.dividends`;
- `xetra_loader.splits`.

Exact consumed contract:

#### `xetra_loader.listings`

Key: `(isin, exchange, code)`.

Columns: `isin`, `exchange`, `code`, `name`, `instrument_type`, `currency`, `country`, `is_active`, `fetched_at_utc`, `published_at_utc`.

#### `xetra_loader.eod_quotes`

Key: `(isin, exchange, code, trade_date)`.

Columns: `isin`, `exchange`, `code`, `trade_date`, `timestamp_eod`, `open`, `high`, `low`, `close`, `adjusted_close`, `volume`, `fetched_at_utc`, `published_at_utc`.

`trade_date` is `DATE`. `timestamp_eod` is the canonical UTC midnight anchor for the date and is not a physical XETRA close timestamp. PostgreSQL `NUMERIC` values stay `Decimal` in the raw source DTO layer.

#### `xetra_loader.dividends`

Key: `(isin, exchange, code, event_key)`.

Columns: `isin`, `exchange`, `code`, `event_key`, `event_date`, `declaration_date`, `record_date`, `payment_date`, `value`, `currency`, `period`, `fetched_at_utc`, `published_at_utc`.

#### `xetra_loader.splits`

Key: `(isin, exchange, code, event_key)`.

Columns: `isin`, `exchange`, `code`, `event_key`, `event_date`, `split_ratio`, `split_factor`, `fetched_at_utc`, `published_at_utc`.

All consumed PostgreSQL timestamp columns are timezone-aware UTC. Full listing identity `(isin, exchange, code)` is mandatory end-to-end; ISIN alone is display metadata, never a business key.

### 3.3 `xetra_loader_sync` is not a consumer schema

`xetra_loader_sync` is loader control-plane state. Existing loader RBAC explicitly denies `portfell_app` access to it.

Executable Portfell code must never query `xetra_loader_sync.sync_state` or `xetra_loader_sync.loader_runs`, request broader grants, infer loader run IDs/status, or use loader control state for authorization/freshness.

Portfell may expose only observational source evidence from accessible business rows, such as business-table reachability, active-listing count, latest quote `trade_date`, and maximum `published_at_utc`. It must not label the loader itself `fresh`, `stale`, `applied`, or `noop` because those states are not observable under the consumer contract.

QA may deliberately attempt forbidden `xetra_loader_sync` access and treat permission denial as PASS evidence. Such SQL belongs only in QA tests/runbooks, never executable application source.

### 3.4 Raw-source to analytics projection contract

The database contract and the existing analytics contract use different field names/types. The translation is explicit and centralized; stage code must not invent local mappings.

Frozen rules:

- raw quote `trade_date` projects to analytics `date`;
- raw dividend `event_date` projects to analytics `date`;
- raw PostgreSQL `Decimal` numerics are converted to `float` only at the analytics projection boundary, never in raw repositories;
- `adjusted_close` is the authoritative price basis for returns, risk, volatility, and drawdown calculations;
- `adjusted_close IS NULL` is **not** silently replaced by raw `close`; it produces typed `missing_adjusted_close` quality/ineligibility evidence;
- non-positive adjusted close continues to use the existing non-positive-price quality semantics;
- cash dividends remain income/distribution evidence only and are not added again to adjusted-close returns, preventing double counting;
- split rows are preserved/readable source evidence, but this source-cutover series does not invent a new split-adjustment formula; existing adjusted-close return semantics remain authoritative;
- fetched/published timestamps are provenance evidence, not analytical factors.

### 3.5 Active listing policy

`xetra-loader` intentionally retains historical/delisted identities with `is_active=false`. New Metadata candidate discovery in Portfell uses **active listings only**. Inactive listings remain resolvable by full identity for historical/audit evidence but must never silently enter a new portfolio universe.

Metadata predicate behavior remains the existing deterministic Portfell behavior. In particular, text `name contains` keeps the existing Python `casefold()` substring semantics; it is not redefined through database collation/`ILIKE` behavior.

### 3.6 Batch-read and snapshot policy

- Raw repositories support one identity and a bounded batch of identities.
- Canonical maximum identity batch is `500` listing keys per SQL statement.
- Batch reads use parameterized SQL; no string-built identity SQL.
- No analytical stage may issue one quote/dividend/split SQL query per listing when a batch API is available.
- No temp table or DDL is used for batching because the consumer is read-only.
- One analytical source snapshot keeps one repeatable-read transaction open across the business-table reads required to assemble that snapshot.

### 3.7 Stable market-source error codes

Infrastructure/source errors are frozen in PR308:

- `market_source_config_missing`;
- `market_source_unavailable`;
- `market_source_role_invalid`;
- `market_source_contract_mismatch`;
- `market_source_duplicate_key`;
- `market_source_invalid_value`.

Analytical insufficiency such as `insufficient_history`, `missing_adjusted_close`, or an ineligible portfolio candidate is not rewritten into an infrastructure error.

### 3.8 Production handoff gate from xetra-loader

The older XDL-PR033 completion claim is superseded in `xetra-loader`. The current final loader production gate is XDL-PR053 plus its sanitized V2 acceptance artifact:

`artifacts/acceptance/postgres-full-sync-v2.json`

Portfell PR308-PR339 may proceed against contract-faithful test PostgreSQL or a development serving plane. **PR340 may not start** until the artifact exists on `xetra-loader` `main`, is marked `PASS`, and the exact loader commit SHA containing it is recorded. Until then the real target must not be treated as production-reconciled.

## 4. Single-user target

The application target after this series is one workspace:

- no user/tenant/membership/project-membership/credential-owner security authority;
- no project-bootstrap worker or project-scoped market refresh;
- saved portfolio/analysis/optimization/decision identifiers may remain domain identifiers but are not security scopes;
- canonical browser routes exactly `/metadata`, `/univariate`, `/bivariate`, `/multivariate`;
- REST remains under `/api`.

## 5. Weak-agent Git and ownership contract

Every work order below is written for weak independent agents.

Mandatory rules for every implementation PR:

1. Record `git status --short --branch` before editing and include it in PR evidence.
2. Start from the exact merged dependency SHA; if any dependency is unmerged, stop.
3. Sibling branches start from the exact same predecessor SHA and never from another sibling.
4. Exact work-order slug appears in branch name, every Conventional Commit scope, and PR title.
5. Edit only named owned paths. A sibling-owned path is forbidden even when a local workaround appears easier.
6. Do not add compatibility fallbacks, hidden provider flags, second market-source authority, opportunistic refactors, or broader DB grants.
7. Focused tests and `uv run portfell-quality pr` pass from the final PR SHA.
8. QA/integration gates additionally run `uv run portfell-quality merge` from one clean SHA because the PR gate alone does not run all architecture/schema/coverage checks.
9. Coverage and merge policy remain governed only by `GATES.md`.
10. A work order is not complete because code was pushed; its complete checklist and required quality evidence must pass.

## 6. Dependency graph and parallel waves

```text
PR296 planning authority
   |
 PR308  source contract / connection / errors
   |
 PR309 || PR310 || PR311 || PR312 || PR313 || PR314
   |       repositories/status/projection (same PR308 SHA)
   +---------------------------+
                               v
                             PR315 gateway + coherent snapshot
                               |
                             PR316 QA source contract gate
                               |
                             PR317 hosted runtime port cutover
                               |
                             PR318 immutable market-source lineage
                               |
                 PR319 || PR320 || PR321 || PR322
                     four analytical stages
                               |
                             PR323 QA four-stage semantics
                               |
 PR324 || PR325 || PR326 || PR327 || PR328 || PR329 || PR330 || PR331
                    deletion wave
                               |
                             PR332 QA negative-space gate
                               |
                         PR333 || PR334
                      single-user backend/UI
                               |
                             PR335 QA single-user gate
                               |
                       PR336 || PR337 || PR338
                     package/runtime/docs cleanup
                               |
                             PR339 QA clean-runtime gate
                               |
        xetra-loader XDL-PR053 V2 PASS artifact
                               |
                               +----> PR340 live PostgreSQL QA
                                         |
                                       PR341 final E2E
                                         |
                                       PR342 production runbook
                                         |
                                       PR343 deferred-product backlog reconciliation
```

Safe parallel waves are exactly the sibling groups shown above. Integration/QA gates are serial barriers.

## 7. Atomic work orders

### PR308 — pr308-xetra-source-contract

Branch: `refactor/pr308-xetra-source-contract`

Commit scope: `refactor(pr308-xetra-source-contract): ...`

Depends on: PR296 merged.

Owned paths: new `src/portfell/market_source/errors.py`, `config.py`, `contracts.py`, `connection.py`, package init, focused tests.

Tasks / Acceptance:

- [ ] Implement only `PORTFELL_MARKET_DATABASE_URL`; no database credentials/full DSN in source or examples.
- [ ] Freeze exact raw DTO fields/keys from section 3.2 and preserve `Decimal`, `date`, and UTC-aware `datetime` types.
- [ ] Implement the six stable source error codes from section 3.7 with deterministic DB-exception mapping.
- [ ] Connection preflight verifies current LOGIN role is non-superuser and a member of NOLOGIN group role `portfell_app`; no literal login-role name is assumed.
- [ ] Connection/session sets UTC and opens market transactions as `REPEATABLE READ, READ ONLY`; no commit/write helper exists.
- [ ] Unit tests reject missing config, naive timestamps, invalid keys/values, non-membership, superuser sessions, and non-UTC decoding.
- [ ] Architecture test proves this package has no EODHD/provider HTTP dependency and no `xetra-loader` Python import.
- [ ] Architecture test proves executable Portfell source defines no `xetra_loader_sync` repository/API.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: foundation; Wave A waits for merge.
Security: least privilege and no secret literals.
Determinism: exact DTO/error/session contracts.
Idempotency: connection/preflight creates no state.
Rollback: remove new package only.

### PR309 — pr309-xetra-listings-repository

Branch: `feat/pr309-xetra-listings-repository`

Commit scope: `feat(pr309-xetra-listings-repository): ...`

Depends on: PR308.

Owned paths: new `src/portfell/market_source/listings.py`, focused tests.

Tasks / Acceptance:

- [ ] SELECT only exact `xetra_loader.listings` columns through PR308 connection.
- [ ] API supports full-identity lookup, all active rows, and bounded identity batches; business filtering remains outside this repository.
- [ ] Preserve inactive rows when explicitly resolved by identity; `active()` returns only `is_active=true`.
- [ ] Deterministic ordering is `(isin, exchange, code)`; multiple listings sharing one ISIN remain distinct.
- [ ] Empty lookup is typed empty data, not source failure; DB/contract failures use PR308 errors.
- [ ] No SQL `ILIKE`/collation rule redefines Metadata name matching.
- [ ] Parameterized SELECT only; no DML/DDL/fallback.
- [ ] Tests cover active/inactive, nullable metadata, duplicate ISIN identities, batching boundary 500/501, ordering, and DB failure.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: Wave A with PR310-PR314 from same PR308 merge SHA.
Security: SELECT only.
Determinism: stable identity/order.
Idempotency: read-only.
Rollback: remove repository/tests.

### PR310 — pr310-xetra-quotes-repository

Branch: `feat/pr310-xetra-quotes-repository`

Commit scope: `feat(pr310-xetra-quotes-repository): ...`

Depends on: PR308.

Owned paths: new `src/portfell/market_source/quotes.py`, focused tests.

Tasks / Acceptance:

- [ ] SELECT quote history by full identity or bounded batches of at most 500 identities and inclusive date range.
- [ ] Return exact source names/types, including nullable `adjusted_close`, with PostgreSQL `NUMERIC` preserved as `Decimal`.
- [ ] Deterministic order is full identity then `trade_date`.
- [ ] Duplicate quote keys raise `market_source_duplicate_key`; never silently deduplicate.
- [ ] Preserve canonical UTC-midnight `timestamp_eod` semantics; no exchange-close reinterpretation.
- [ ] Parameterized batching proves bounded query count; tests reject an N+1 implementation for 501 identities.
- [ ] Empty history is an empty data result; DB/contract/value failures map through PR308.
- [ ] No provider/filesystem fallback or DML/DDL.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: Wave A.
Security: SELECT only.
Determinism: exact source ordering/types.
Idempotency: read-only.
Rollback: remove repository/tests.

### PR311 — pr311-xetra-dividends-repository

Branch: `feat/pr311-xetra-dividends-repository`

Commit scope: `feat(pr311-xetra-dividends-repository): ...`

Depends on: PR308.

Owned paths: new `src/portfell/market_source/dividends.py`, focused tests.

Tasks / Acceptance:

- [ ] SELECT dividends by full identity/batches <=500 and inclusive `event_date` range.
- [ ] Preserve `event_key` exactly; never regenerate event identity in Portfell.
- [ ] Preserve `Decimal value`, nullable auxiliary dates/currency/period, and UTC provenance timestamps.
- [ ] Deterministic order is full identity, `event_date`, `event_key`.
- [ ] Duplicate action keys raise `market_source_duplicate_key`.
- [ ] Batching tests prove bounded query count and same-day distinct events survive.
- [ ] No provider/filesystem fallback or DML/DDL.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: Wave A.
Security: SELECT only.
Determinism: source event identity/order.
Idempotency: read-only.
Rollback: remove repository/tests.

### PR312 — pr312-xetra-splits-repository

Branch: `feat/pr312-xetra-splits-repository`

Commit scope: `feat(pr312-xetra-splits-repository): ...`

Depends on: PR308.

Owned paths: new `src/portfell/market_source/splits.py`, focused tests.

Tasks / Acceptance:

- [ ] SELECT splits by full identity/batches <=500 and inclusive `event_date` range.
- [ ] Preserve loader `event_key`, textual `split_ratio`, optional `Decimal split_factor`, and UTC provenance exactly.
- [ ] Deterministic order is full identity, `event_date`, `event_key`.
- [ ] Duplicate action keys raise `market_source_duplicate_key`.
- [ ] Batching tests prove bounded query count; textual ratios and same-day distinct events survive unchanged.
- [ ] No provider/filesystem fallback, local split-key generation, or DML/DDL.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: Wave A.
Security: SELECT only.
Determinism: source event identity/order.
Idempotency: read-only.
Rollback: remove repository/tests.

### PR313 — pr313-xetra-observed-source-status

Branch: `feat/pr313-xetra-observed-source-status`

Commit scope: `feat(pr313-xetra-observed-source-status): ...`

Depends on: PR308.

Owned paths: new `src/portfell/market_source/status.py`, focused tests.

Tasks / Acceptance:

- [ ] Return only observable business-plane evidence: schema/table reachability, nonempty flags, active-listing count, latest quote `trade_date`, and maximum `published_at_utc` per business table.
- [ ] Do not expose semantic fields named loader status/run/fingerprint/applied/noop/fresh/stale.
- [ ] Do not query `xetra_loader_sync` under any application path.
- [ ] Avoid hot-path full `COUNT(*)` scans of large quote/action tables; status SQL uses bounded/aggregate evidence appropriate to indexed business fields and is isolated from analytical reads.
- [ ] Empty table, contract failure, and database-unavailable are distinct deterministic states.
- [ ] Tests prove no sync-schema SQL and no loader-state inference.
- [ ] Read model performs no writes/refresh/download.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: Wave A.
Security: business schema only.
Determinism: same DB snapshot -> same status DTO.
Idempotency: read-only.
Rollback: remove status module/tests.

### PR314 — pr314-market-analysis-projection-contract

Branch: `refactor/pr314-market-analysis-projection-contract`

Commit scope: `refactor(pr314-market-analysis-projection-contract): ...`

Depends on: PR308.

Owned paths: new `src/portfell/market_source/projection.py`, focused projection/quality fixtures only.

Tasks / Acceptance:

- [ ] Freeze the section 3.4 projection from raw DTOs to legacy analytics field names/types.
- [ ] Quote `trade_date -> date`; dividend `event_date -> date`; full identity retained.
- [ ] `Decimal -> float` occurs only here for fields required by existing analytics.
- [ ] Never `COALESCE(adjusted_close, close)`; missing adjusted close emits `missing_adjusted_close` evidence and is not fabricated.
- [ ] Preserve non-positive adjusted-close quality semantics and deterministic ordering.
- [ ] Dividend cashflows remain income evidence and are not added to adjusted-close returns.
- [ ] Splits receive no new return-adjustment algorithm in this PR.
- [ ] Tests cover nullable adjusted close, precision conversion, dividend date mapping, no double counting, and full identity.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: Wave A with repositories because it depends only on PR308 DTOs.
Security: pure transformation.
Determinism: canonical projection rules.
Idempotency: pure function.
Rollback: remove projection module/tests.

### PR315 — pr315-xetra-market-data-gateway

Branch: `feat/pr315-xetra-market-data-gateway`

Commit scope: `feat(pr315-xetra-market-data-gateway): ...`

Depends on: PR309-PR314.

Owned paths: new `src/portfell/market_source/gateway.py`, package exports, market-source architecture checks, focused integration tests.

Tasks / Acceptance:

- [ ] Compose all raw repositories/status/projection behind one typed `MarketDataGateway`.
- [ ] Gateway offers explicit `snapshot(...)` context that holds one `REPEATABLE READ, READ ONLY` transaction across required table reads.
- [ ] Stage-facing methods return projected analytical rows plus explicit projection/quality evidence; stage code never embeds source table names.
- [ ] Gateway batches selected listing keys using canonical <=500 policy and never uses one-query-per-listing loops.
- [ ] Direct `xetra_loader` SQL is allowed only under `src/portfell/market_source/**`.
- [ ] Executable source reference to `xetra_loader_sync` is forbidden.
- [ ] No gateway method accepts a provider token or performs write/refresh/download/publish.
- [ ] Integration fixture proves transaction snapshot consistency when a concurrent writer commits between two gateway reads.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: serial integration gate.
Security: one read-only market boundary.
Determinism: coherent database snapshot and stable batches.
Idempotency: read-only.
Rollback: remove gateway while leaving isolated repos.

### PR316 — pr316-xetra-source-contract-qa

Branch: `test/pr316-xetra-source-contract-qa`

Commit scope: `test(pr316-xetra-source-contract-qa): ...`

Depends on: PR315.

Owned paths: source-contract QA fixtures/tests/evidence only; no production code.

Tasks / Acceptance:

- [ ] Provision contract-faithful PostgreSQL with exact four business tables and NOLOGIN group role semantics equivalent to `portfell_app`.
- [ ] Prove raw types/keys/UTC/date semantics and `Decimal` round-trip for all four tables.
- [ ] Prove login membership/superuser/read-only guards and failed market DML.
- [ ] Prove <=500 batching and bounded SQL count for 1,001 identities.
- [ ] Prove repeatable-read snapshot consistency under concurrent publication.
- [ ] Prove missing adjusted close is not replaced with raw close and dividends are not double-counted.
- [ ] Prove executable source contains no sync-schema query/provider fallback in the new boundary.
- [ ] Run focused QA plus `uv run portfell-quality merge` from one clean SHA.

Parallelization: serial QA barrier.
Security: defense-in-depth and role proof.
Determinism: contract fixture fixed.
Idempotency: market row counts/hashes unchanged after QA.
Rollback: tests/evidence only.

### PR317 — pr317-hosted-runtime-read-plane-cutover

Branch: `refactor/pr317-hosted-runtime-read-plane-cutover`

Commit scope: `refactor(pr317-hosted-runtime-read-plane-cutover): ...`

Depends on: PR316.

Owned paths: `src/portfell/hosted_api_ports.py`, new PostgreSQL hosted runtime adapter/composition wiring, focused tests. Do not yet delete legacy provider adapter files.

Tasks / Acceptance:

- [ ] Replace `HostedRuntimePort` acquisition methods (`run_metadata`, `run_quotes`, provider-key arguments) with read-only market-source capabilities required by application services.
- [ ] Wire `MarketDataGateway` through application composition; services receive a typed read port, never a DSN/raw connection.
- [ ] Runtime has no market write/download/refresh method.
- [ ] Preserve analytical persistence ports separately; market read-only does not imply analytical state is read-only.
- [ ] Legacy provider/local runtime may remain physically present until deletion wave but is no longer reachable from default application composition.
- [ ] Tests prove app composition starts with PostgreSQL market config and no provider key/lake root.
- [ ] Tests prove unavailable PostgreSQL maps to frozen source error semantics.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: serial because it owns the shared runtime protocol.
Security: no provider secret crosses service boundary.
Determinism: one market runtime composition.
Idempotency: composition/read only.
Rollback: restore old port/composition without touching gateway.

### PR318 — pr318-market-source-lineage-cutover

Branch: `refactor/pr318-market-source-lineage-cutover`

Commit scope: `refactor(pr318-market-source-lineage-cutover): ...`

Depends on: PR317.

Owned paths: `hosted_research_ports.py`, research source-lineage contracts/repositories/workflow/facade, associated analytical-state schema/migration and focused tests. Excludes stage-specific service files owned by PR319-PR322.

Tasks / Acceptance:

- [ ] Remove `ProviderDownloadRun`, `quote_run_id`, `bind_quote_run`, and provider-download identity from the research port contract.
- [ ] Introduce immutable `MarketSourceSnapshot` analytical lineage with deterministic `snapshot_id` derived from source-contract version, selected full identities, and canonical semantic rows actually consumed.
- [ ] Snapshot records input row counts/date bounds and maximum consumed `published_at_utc` evidence; it contains no credentials/full DSN/sync state.
- [ ] `observed_at_utc` may be recorded as non-semantic evidence and is excluded from deterministic `snapshot_id`.
- [ ] Snapshot hash proves input identity but does not claim historical reconstruction from PostgreSQL after upstream corrections; documentation/tests state this explicitly.
- [ ] Research run source IDs/idempotency keys use `MarketSourceSnapshot.snapshot_id` instead of download-run/shared-market magic strings.
- [ ] Persisted analytical state may store snapshot metadata/hash but never becomes a market-source fallback.
- [ ] Repository/service contracts compile without provider entitlement/download types.
- [ ] Focused migration/contract tests and `uv run portfell-quality pr` pass.

Parallelization: serial contract gate before stage siblings.
Security: lineage contains no secret/control-plane data.
Determinism: same semantic input -> same snapshot ID.
Idempotency: repeated identical source snapshot reuses deterministic lineage.
Rollback: reverse analytical schema/contract migration only.

### PR319 — pr319-metadata-stage-xetra-cutover

Branch: `refactor/pr319-metadata-stage-xetra-cutover`

Commit scope: `refactor(pr319-metadata-stage-xetra-cutover): ...`

Depends on: PR318.

Owned paths: Metadata service/selection input seam and focused Metadata tests only; physical provider job/route/UI deletion is later.

Tasks / Acceptance:

- [ ] Metadata candidate universe comes from `MarketDataGateway` active listings only.
- [ ] Existing predicates remain exchange/name~/instrument_type/country/currency with existing Python predicate semantics.
- [ ] Full listing identity is retained; duplicate ISIN listings remain distinct.
- [ ] Inactive listings never enter a new candidate universe but remain resolvable for existing historical identities.
- [ ] Metadata selection source lineage uses `MarketSourceSnapshot`, not provider metadata revision/download run.
- [ ] Empty/unavailable business data returns explicit typed evidence; no discovery/download/refresh fallback is invoked.
- [ ] Regression fixture proves equivalent active listing rows produce equivalent selection results to pre-cutover behavior.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: Wave B with PR320-PR322 from same PR318 SHA.
Security: gateway only.
Determinism: DB snapshot + predicates.
Idempotency: analytical selection persistence only.
Rollback: restore metadata adapter.

### PR320 — pr320-univariate-stage-xetra-cutover

Branch: `refactor/pr320-univariate-stage-xetra-cutover`

Commit scope: `refactor(pr320-univariate-stage-xetra-cutover): ...`

Depends on: PR318.

Owned paths: Univariate service/input assembly, `univariate_statistics.py`/`return_quality.py` source-shape compatibility needed for this cutover, focused tests.

Tasks / Acceptance:

- [ ] Obtain selected quote/dividend inputs only through one `MarketDataGateway` snapshot.
- [ ] Remove quote-download/shared-market source branching from Univariate service; lineage is snapshot ID only.
- [ ] Preserve existing formulas, 252-day annualization, confidence semantics, income features, selection behavior, and full identity.
- [ ] Update price-quality path so nullable adjusted close yields `missing_adjusted_close`/ineligible evidence instead of `float(None)` or raw-close fallback.
- [ ] Dividend `event_date -> date` projection feeds existing distribution/income formulas; adjusted-close returns do not add cash dividends again.
- [ ] Split rows do not introduce a new return transformation.
- [ ] Regression fixture proves equivalent pre-cutover adjusted-close/dividend rows produce equivalent numerical output.
- [ ] No direct SQL/provider/lake/filesystem market read.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: Wave B.
Security: gateway only.
Determinism: same snapshot -> same statistics.
Idempotency: analytical state only.
Rollback: restore Univariate adapter.

### PR321 — pr321-bivariate-stage-xetra-cutover

Branch: `refactor/pr321-bivariate-stage-xetra-cutover`

Commit scope: `refactor(pr321-bivariate-stage-xetra-cutover): ...`

Depends on: PR318.

Owned paths: Bivariate service/input source seam and focused tests only.

Tasks / Acceptance:

- [ ] Build Bivariate input returns from the selected quote rows tied to the upstream `MarketSourceSnapshot`; no download-run lookup remains.
- [ ] Preserve pair formulas, pair identity, common-calendar/intersection, minimum observation logic, pair-count guard, and diagnostics.
- [ ] Full listing identity is preserved on both sides; existing skip-same-ISIN policy is unchanged.
- [ ] Mismatched calendars, missing dates, duplicate ISIN identities, empty overlap, and insufficient history are deterministic tests.
- [ ] Equivalent legacy return rows and projected PostgreSQL rows produce equivalent Bivariate output.
- [ ] No direct SQL/provider/lake/filesystem market read.
- [ ] Source failure never starts a downloader.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: Wave B.
Security: gateway/snapshot lineage only.
Determinism: existing pair alignment retained.
Idempotency: analytical state only.
Rollback: restore Bivariate adapter.

### PR322 — pr322-multivariate-stage-xetra-cutover

Branch: `refactor/pr322-multivariate-stage-xetra-cutover`

Commit scope: `refactor(pr322-multivariate-stage-xetra-cutover): ...`

Depends on: PR318.

Owned paths: Multivariate service/market-input assembly, extraction of any pure return helper still imported from legacy market Gold, focused tests.

Tasks / Acceptance:

- [ ] Resolve quote/dividend inputs by `MarketSourceSnapshot`; remove provider quote-run/shared-market magic identities.
- [ ] Move/reuse pure return construction under an analytics-owned module so Multivariate no longer imports legacy market persistence module `portfell.gold`.
- [ ] Build exact optimizer universe/aligned return matrix/source-dependent risk and income inputs from gateway-projected rows only.
- [ ] Preserve objectives, solvers, risk-model logic, walk-forward/OOS boundaries, validation, and winner-selection semantics; no optimizer redesign.
- [ ] Preserve full listing identity through candidates/final weights and source snapshot ID through input/artifact lineage.
- [ ] Exact fixture matrices are asserted before optimizer invocation; missing common history is typed/ineligible.
- [ ] Equivalent legacy source rows and projected PostgreSQL rows produce equivalent optimizer inputs.
- [ ] No direct SQL/provider/lake/filesystem market read.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: Wave B.
Security: gateway/snapshot lineage only.
Determinism: exact matrix/lineage.
Idempotency: analytical artifacts only.
Rollback: restore Multivariate adapter.

### PR323 — pr323-four-stage-source-semantics-qa

Branch: `test/pr323-four-stage-source-semantics-qa`

Commit scope: `test(pr323-four-stage-source-semantics-qa): ...`

Depends on: PR319-PR322.

Owned paths: cross-stage QA tests/fixtures/evidence only.

Tasks / Acceptance:

- [ ] Exercise Metadata -> Univariate -> Bivariate -> Multivariate through one coherent PostgreSQL fixture snapshot.
- [ ] Prove active/inactive policy, duplicate ISIN/full identity, nullable adjusted close, dividends, split non-interference, UTC/date mapping, and Decimal projection.
- [ ] Prove identical semantic source rows produce equivalent analytical outputs versus frozen legacy fixtures within existing numerical tolerances; no new tolerance is invented here.
- [ ] Prove all four stages carry one deterministic source snapshot lineage and no provider download-run ID.
- [ ] Prove database failure/partial/insufficient data fails closed and no acquisition fallback runs.
- [ ] Prove direct source SQL outside `market_source` and executable sync-schema references fail architecture checks.
- [ ] Prove repeated run does not mutate four market tables.
- [ ] Run focused QA plus `uv run portfell-quality merge` from one clean SHA.

Parallelization: serial QA barrier before destructive deletion.
Security: least-privilege read path.
Determinism: fixed source fixture/snapshot.
Idempotency: market unchanged.
Rollback: tests/evidence only.

### PR324 — pr324-delete-eodhd-client-fetch-cli

Branch: `refactor/pr324-delete-eodhd-client-fetch-cli`

Commit scope: `refactor(pr324-delete-eodhd-client-fetch-cli): ...`

Depends on: PR323.

Owned paths: `src/portfell/http.py`, `search.py`, `fetch_all_metadata.py`, `fetch_all_quotes.py`, provider-acquisition portions of `cli.py`, their focused tests. Shared config cleanup belongs to PR331.

Tasks / Acceptance:

- [ ] Delete EODHD HTTP/endpoint/retry/search/discovery/fetch implementations and acquisition CLI commands.
- [ ] Remove tests/stubs whose only purpose is provider HTTP acquisition from these owned paths.
- [ ] Preserve unrelated CLI behavior.
- [ ] No disabled wrapper/feature flag retains provider acquisition.
- [ ] Imports succeed without these modules from the PR323 application path.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: Wave C with PR325-PR331 from same PR323 SHA; do not edit sibling-owned paths.
Security: removes provider HTTP authority.
Determinism: acquisition removed.
Idempotency: deletion.
Rollback: revert this PR only.

### PR325 — pr325-delete-market-medallion-persistence

Branch: `refactor/pr325-delete-market-medallion-persistence`

Commit scope: `refactor(pr325-delete-market-medallion-persistence): ...`

Depends on: PR323.

Owned paths: `bronze.py`, `silver.py`, market-persistence portions of `gold.py`, `pipeline.py`, market-loading tests/imports.

Tasks / Acceptance:

- [ ] Delete Portfell-owned market Bronze/Silver/Gold ingestion/publication and provider market pipeline.
- [ ] Any pure analytical helper needed by source-independent analytics must already have been moved by PR322; no market reader/writer survives under a renamed file.
- [ ] Keep analytical DecisionArtifact/statistics/optimizer persistence untouched.
- [ ] Remove imports/callers of deleted market medallion code from owned scope.
- [ ] Four-stage PR323 fixture workflow runs without medallion directories.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: Wave C.
Security: removes duplicate market authority.
Determinism: PostgreSQL only.
Idempotency: deletion.
Rollback: revert code only; DB unchanged.

### PR326 — pr326-delete-market-filesystem-nas-plane

Branch: `refactor/pr326-delete-market-filesystem-nas-plane`

Commit scope: `refactor(pr326-delete-market-filesystem-nas-plane): ...`

Depends on: PR323.

Owned paths: market-data portions of `paths.py`, `table_io.py`, `ugreen_nas_data_root_preflight.py`, market-only persistent inventory/import helpers, focused tests.

Tasks / Acceptance:

- [ ] Remove market-data NAS/lake path requirements and market filesystem fallback/read/write helpers.
- [ ] Preserve filesystem functionality demonstrably required by unrelated analytical/application features; do not delete generic persistence blindly.
- [ ] Remove startup/readiness gates that require a market NAS mount.
- [ ] No migration of legacy market files into PostgreSQL is added; loader owns serving data.
- [ ] Tests prove app/four stages need no market filesystem mount and cannot fallback to files.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: Wave C; do not edit provider CLI/config/UI files owned elsewhere.
Security: removes filesystem fallback authority.
Determinism: PostgreSQL sole market source.
Idempotency: deletion.
Rollback: revert Portfell code only.

### PR327 — pr327-delete-shared-market-refresh-plane

Branch: `refactor/pr327-delete-shared-market-refresh-plane`

Commit scope: `refactor(pr327-delete-shared-market-refresh-plane): ...`

Depends on: PR323.

Owned paths: `shared_market_cron.py`, `shared_market_refresh.py`, `shared_market_data.py`, `shared_observations.py`, `shared_metadata_catalog.py`, `hosted_shared_coverage_bootstrap.py`, `hosted_shared_market_research_data.py`, `hosted_shared_quote_publisher.py`, related tests.

Tasks / Acceptance:

- [ ] Delete union refresh, provider refresh execution, shared quote publication, market cache/read authority, and Portfell market-download scheduling.
- [ ] Remove market-specific locks/progress/retry while preserving analytical-run locking.
- [ ] Any surviving market consumer uses PR315 gateway, not another seam.
- [ ] Portfell starts no market acquisition schedule/process.
- [ ] Source guard rejects imports of deleted shared-market modules.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: Wave C.
Security: removes duplicate publisher/scheduler.
Determinism: external DB snapshot only.
Idempotency: no market refresh.
Rollback: revert code only; loader schedule untouched.

### PR328 — pr328-delete-hosted-market-download-lifecycle

Branch: `refactor/pr328-delete-hosted-market-download-lifecycle`

Commit scope: `refactor(pr328-delete-hosted-market-download-lifecycle): ...`

Depends on: PR323.

Owned paths: hosted download-run, metadata-refresh, quote-run lifecycle schemas/repositories/workers/services/routes/status hooks and focused tests.

Tasks / Acceptance:

- [ ] Delete hosted market-download lifecycle and metadata/quote refresh commands/endpoints/workers.
- [ ] Delete queue/job registrations and status hooks used only by market acquisition.
- [ ] Preserve analytical calculation run/status APIs.
- [ ] Research lineage already uses PR318 snapshot IDs; no quote-run compatibility shim remains.
- [ ] OpenAPI/route tests prove no market download/refresh command endpoint.
- [ ] Application composition has no market downloader worker.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: Wave C.
Security: removes remotely triggerable acquisition.
Determinism: analytics-only command plane.
Idempotency: deletion.
Rollback: revert this PR only.

### PR329 — pr329-delete-provider-credential-backend

Branch: `refactor/pr329-delete-provider-credential-backend`

Commit scope: `refactor(pr329-delete-provider-credential-backend): ...`

Depends on: PR323.

Owned paths: `provider_credential_schema.py`, `hosted_credentials.py`, `hosted_credential_project_service.py`, `hosted_routes_credentials.py`, credential-focused tests. Shared config residuals belong PR331.

Tasks / Acceptance:

- [ ] Delete provider credential persistence/vault/services/routes and credential ownership links.
- [ ] Delete storing/validating/rotating/assigning/reading provider credential operations.
- [ ] Do not introduce plaintext provider token configuration.
- [ ] Preserve unrelated application state until PR333.
- [ ] OpenAPI/source tests prove no provider credential DTO/table/route/service.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: Wave C.
Security: removes provider secret store.
Determinism: credential branches gone.
Idempotency: deletion.
Rollback: revert this PR only.

### PR330 — pr330-delete-provider-loading-ui

Branch: `refactor/pr330-delete-provider-loading-ui`

Commit scope: `refactor(pr330-delete-provider-loading-ui): ...`

Depends on: PR323.

Owned paths: current browser provider token/fetch/refresh/progress controls and frontend acquisition contracts/tests, including `metadata-fetch-context.tsx` and `quote-progress.ts`. Project/user route work belongs PR334.

Tasks / Acceptance:

- [ ] Remove provider token UI/storage/display and metadata/quote fetch/refresh/retry/progress controls.
- [ ] Metadata UI becomes a filter/view over server PostgreSQL listings plus analytical selection controls.
- [ ] Remove frontend API calls/contracts that start/poll acquisition; analytical run controls remain.
- [ ] Source unavailable renders unavailable evidence with no download CTA.
- [ ] Browser storage/network tests prove no provider secret/acquisition command.
- [ ] Existing four analytical pages remain navigable.
- [ ] Focused frontend tests and `uv run portfell-quality pr` pass.

Parallelization: Wave C.
Security: no provider secret in browser.
Determinism: server-read state only.
Idempotency: no acquisition command.
Rollback: revert UI removal only.

### PR331 — pr331-delete-legacy-market-runtime-residuals

Branch: `refactor/pr331-delete-legacy-market-runtime-residuals`

Commit scope: `refactor(pr331-delete-legacy-market-runtime-residuals): ...`

Depends on: PR323.

Owned paths: `hosted_api_local_runtime.py`, provider/market residuals in `config.py` and shared contracts, provider-specific entitlement/user-ingestion remnants not owned by PR324-PR330, focused tests.

Tasks / Acceptance:

- [ ] Delete legacy local provider/lake runtime adapter now unreachable since PR317.
- [ ] Remove EODHD token/endpoint/KEK/provider config classes left after sibling deletions without editing sibling-owned files.
- [ ] Remove provider-download entitlement/value types no longer referenced after PR318/PR328.
- [ ] Preserve unrelated application configuration/contracts and user-input functionality.
- [ ] Runtime imports/default composition use only PostgreSQL market read plane.
- [ ] Source tests prove no executable EODHD/provider market runtime residual in owned scope.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: Wave C. If a required residual lives in a sibling-owned file, do not edit it; report the exact path to PR332 QA instead of creating a conflict.
Security: final provider-config/runtime removal.
Determinism: one runtime market seam.
Idempotency: deletion.
Rollback: revert residual cleanup only.

### PR332 — pr332-provider-removal-negative-space-qa

Branch: `test/pr332-provider-removal-negative-space-qa`

Commit scope: `test(pr332-provider-removal-negative-space-qa): ...`

Depends on: PR324-PR331.

Owned paths: QA/source-governance tests and evidence only; production fixes discovered here become new corrective PRs, never hidden inside QA.

Tasks / Acceptance:

- [ ] Repository scan covers executable Python, package entrypoints, active frontend, Compose/workflows/scripts, active tests, and non-historical active docs for provider acquisition symbols/secrets/fallbacks.
- [ ] Historical archive may use a narrow explicit allowlist and cannot be imported/executed.
- [ ] Prove no EODHD client/token/fetch/discovery/provider credential flow, market medallion writer, market filesystem fallback, shared-market publisher, market refresh worker, market-download job, or market cron remains executable.
- [ ] Prove no executable `xetra_loader_sync` reference and no direct `xetra_loader` SQL outside `market_source`.
- [ ] OpenAPI/entrypoint snapshots contain no acquisition/credential endpoint/command.
- [ ] Four-stage PR323 PostgreSQL workflow still passes.
- [ ] If any residual is found, QA fails and a new atomic corrective PR is inserted before PR332 can be accepted.
- [ ] Run focused QA plus `uv run portfell-quality merge` from one clean SHA.

Parallelization: serial deletion-wave QA.
Security: negative-space proof.
Determinism: explicit scan allowlist.
Idempotency: tests only.
Rollback: tests/evidence only.

### PR333 — pr333-single-user-backend-cutover

Branch: `refactor/pr333-single-user-backend-cutover`

Commit scope: `refactor(pr333-single-user-backend-cutover): ...`

Depends on: PR332.

Owned paths: backend user/tenant/membership/project-security/project-bootstrap authority and tests; excludes market/provider files already removed.

Tasks / Acceptance:

- [ ] Remove user, tenant, membership, project-membership, credential-owner, and project-bootstrap security/runtime authority.
- [ ] Replace request-time multi-user/project authorization with exactly one application workspace.
- [ ] Preserve domain IDs required for saved portfolios/analyses/optimization/decisions but they cannot authorize access.
- [ ] Remove project-scoped market refresh/bootstrap remnants; no downloader replacement exists.
- [ ] Backend/API tests run without user/tenant/project-membership seed data.
- [ ] Repeated startup does not create duplicate workspace/domain state.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: Wave D with PR334 from same PR332 SHA.
Security: smaller authority surface; market DB grants unchanged.
Determinism: one workspace.
Idempotency: one workspace initialization.
Rollback: revert backend simplification.

### PR334 — pr334-single-user-ui-route-cutover

Branch: `refactor/pr334-single-user-ui-route-cutover`

Commit scope: `refactor(pr334-single-user-ui-route-cutover): ...`

Depends on: PR332.

Owned paths: current UI shell/navigation/project selector/project slug/user-switching routes/tests; provider-loading UI is already owned/deleted by PR330.

Tasks / Acceptance:

- [ ] Canonical browser routes exactly `/metadata`, `/univariate`, `/bivariate`, `/multivariate`.
- [ ] Remove project selector, project-slug prefix, user switcher, membership navigation.
- [ ] Preserve four-stage analytics navigation/functionality.
- [ ] Legacy project routes follow one explicit tested not-found/redirect rule and never silently choose another workspace.
- [ ] REST remains under `/api`.
- [ ] Responsive/browser smoke tests pass for four routes.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: Wave D with PR333.
Security: URL/project identity no longer authorization.
Determinism: fixed route registry.
Idempotency: navigation read-only.
Rollback: revert route/shell changes.

### PR335 — pr335-single-user-authority-qa

Branch: `test/pr335-single-user-authority-qa`

Commit scope: `test(pr335-single-user-authority-qa): ...`

Depends on: PR333+PR334.

Owned paths: single-user architecture/API/UI QA tests/evidence only.

Tasks / Acceptance:

- [ ] Prove startup/API/UI require no user/tenant/membership/project-membership records.
- [ ] Prove domain IDs cannot act as security scopes and one workspace is deterministic across restart.
- [ ] Prove exactly four canonical browser routes and `/api` REST boundary.
- [ ] Prove no project/user/provider control remains in UI or API authority.
- [ ] Prove PostgreSQL market role/permissions were not broadened by single-user simplification.
- [ ] Run focused QA plus `uv run portfell-quality merge` from one clean SHA.

Parallelization: serial QA barrier.
Security: authority proof.
Determinism: one workspace/route set.
Idempotency: restart proof.
Rollback: tests/evidence only.

### PR336 — pr336-package-entrypoint-import-boundary-cleanup

Branch: `refactor/pr336-package-entrypoint-import-boundary-cleanup`

Commit scope: `refactor(pr336-package-entrypoint-import-boundary-cleanup): ...`

Depends on: PR335.

Owned paths: `pyproject.toml`, `uv.lock`, package script metadata, import-linter contracts, dependency-focused tests.

Tasks / Acceptance:

- [ ] Remove obsolete provider/loading/NAS/refresh CLI entrypoints and dependencies used only by deleted behavior.
- [ ] Update package description so it no longer describes Portfell as EODHD tooling.
- [ ] Keep `psycopg` and every dependency still imported by analytical/runtime code; do not remove by guess.
- [ ] Rewrite import-linter contracts to the new market-source boundary and removed modules.
- [ ] Regenerate lock deterministically; `uv sync --locked` succeeds in clean environment.
- [ ] Package imports with no provider token/lake root.
- [ ] Focused tests and `uv run portfell-quality pr` pass.

Parallelization: Wave E with PR337/PR338.
Security: reduced dependency/entrypoint surface.
Determinism: locked dependency graph.
Idempotency: reproducible install.
Rollback: manifest/lock only.

### PR337 — pr337-external-postgres-runtime-compose

Branch: `refactor/pr337-external-postgres-runtime-compose`

Commit scope: `refactor(pr337-external-postgres-runtime-compose): ...`

Depends on: PR335.

Owned paths: `.env.example`, Compose files, deployment runtime wiring, `tests/e2e/**`, Compose/runtime tests.

Tasks / Acceptance:

- [ ] Runtime requires external `PORTFELL_MARKET_DATABASE_URL`; target host/port documented, secret DSN/password not committed.
- [ ] Remove EODHD/KEK/provider test secrets/stub and market download/refresh worker services.
- [ ] Portfell Compose does not own `xetra_loader` database/loader service.
- [ ] CI/local E2E uses contract-faithful PostgreSQL fixture with a LOGIN role that is a member of NOLOGIN `portfell_app`, or an explicitly supplied external test DSN.
- [ ] Startup failure is explicit for missing/unreachable/invalid-role PostgreSQL config.
- [ ] E2E proves market DML fails and no market filesystem/provider env is needed.
- [ ] `docker compose config`, container smoke, focused E2E and `uv run portfell-quality pr` pass.

Parallelization: Wave E.
Security: DB secret only for market source.
Determinism: fixed runtime topology.
Idempotency: restart creates no market data.
Rollback: runtime manifests only.

### PR338 — pr338-active-docs-market-source-rewrite

Branch: `docs/pr338-active-docs-market-source-rewrite`

Commit scope: `docs(pr338-active-docs-market-source-rewrite): ...`

Depends on: PR335.

Owned paths: README/ARCHITECTURE/CONTRACTS/DOCKER/GOALS/RISKS/current active docs and obsolete EODHD-derived active CSV artifacts only; no production/test code.

Tasks / Acceptance:

- [ ] One authoritative architecture story: `xetra-loader -> xetra_loader PostgreSQL -> Portfell`.
- [ ] Document four tables/keys, NOLOGIN `portfell_app` membership model, repeatable-read read-only snapshot, active-listing policy, adjusted-close policy, Decimal projection, and inaccessible sync schema.
- [ ] Remove active EODHD token/fetch/how-to-load docs and obsolete EODHD-derived catalog CSV artifacts if no runtime/test consumes them.
- [ ] Historical backlog archive remains clearly historical and cannot override active docs.
- [ ] Remove fictional `portfell_market` / `xetra-data-loader` names from active docs.
- [ ] Document that xetra-loader production reconciliation is blocked until PR053 V2 PASS artifact exists.
- [ ] Docs validation and `uv run portfell-quality pr` pass.

Parallelization: Wave E.
Security: no secrets/full DSNs.
Determinism: one active architecture story.
Idempotency: docs only.
Rollback: docs only.

### PR339 — pr339-clean-runtime-install-docs-qa

Branch: `test/pr339-clean-runtime-install-docs-qa`

Commit scope: `test(pr339-clean-runtime-install-docs-qa): ...`

Depends on: PR336-PR338.

Owned paths: final pre-live QA tests/evidence only.

Tasks / Acceptance:

- [ ] Clean `uv sync --locked`, package import, import-linter, CLI entrypoint enumeration, Compose config, and container startup pass without provider/NAS variables.
- [ ] Active docs/config/entrypoint/workflow/source scans agree on PostgreSQL-only market source and contain no secret/full DSN.
- [ ] Contract-faithful PostgreSQL E2E exercises all four routes/stages under read-only role membership.
- [ ] No obsolete market acquisition service/entrypoint/environment variable is required.
- [ ] Run focused QA plus `uv run portfell-quality merge` from one clean SHA.

Parallelization: serial pre-live barrier.
Security: clean runtime proof.
Determinism: clean install/runtime topology.
Idempotency: restart/reads leave market fixture unchanged.
Rollback: tests/evidence only.

### PR340 — pr340-live-xetra-postgres-v2-contract-qa

Branch: `test/pr340-live-xetra-postgres-v2-contract-qa`

Commit scope: `test(pr340-live-xetra-postgres-v2-contract-qa): ...`

Depends on: PR339 **and xetra-loader XDL-PR053 V2 acceptance artifact present on `main` and marked PASS**.

Owned paths: live-contract smoke tests/runbook evidence only; no production source changes.

Tasks / Acceptance:

- [ ] Verify `xetra-loader/artifacts/acceptance/postgres-full-sync-v2.json` exists on loader `main`, is sanitized, reports PASS, targets `10.10.1.3:54321`, and record exact loader SHA.
- [ ] Connect to real serving plane using secret-supplied production-equivalent LOGIN role; verify it is non-superuser and member of NOLOGIN `portfell_app`.
- [ ] SELECT works for exact four business tables and observed columns/types/PKs match section 3.
- [ ] Representative full identities and quote/action rows round-trip through PR315 gateway with exact date/UTC/Decimal/projection semantics.
- [ ] INSERT/UPDATE/DELETE/DDL on market schema fail for application identity.
- [ ] Deliberate `xetra_loader_sync` access fails; expected denial is PASS evidence.
- [ ] Record sanitized endpoint/schema/table/row-count/date-bound evidence plus exact Portfell/loader SHAs; never record credentials/full DSN/raw provider data.
- [ ] Live smoke and `uv run portfell-quality merge` pass from one clean SHA.

Parallelization: serial live gate.
Security: real least-privilege proof.
Determinism: stable ordered evidence.
Idempotency: successful operations SELECT only; forbidden writes fail.
Rollback: tests/evidence only.

### PR341 — pr341-full-postgres-source-replacement-e2e

Branch: `test/pr341-full-postgres-source-replacement-e2e`

Commit scope: `test(pr341-full-postgres-source-replacement-e2e): ...`

Depends on: PR340.

Owned paths: final source-replacement E2E tests/evidence only.

Tasks / Acceptance:

- [ ] Cold-start Portfell with no EODHD/provider env, market NAS/filesystem, local market medallion state, or loader package.
- [ ] Execute Metadata -> Univariate -> Bivariate -> Multivariate against verified PostgreSQL source successfully.
- [ ] Prove every market read goes through `MarketDataGateway`; no direct source SQL outside market_source.
- [ ] Simulate DB unavailable, empty required history, partial history, and missing adjusted close; each fails closed/typed with no acquisition fallback.
- [ ] Prove inactive listings cannot enter new candidate universe and duplicate ISIN listings retain full identity.
- [ ] Prove source snapshot lineage is deterministic and contains no provider/download/sync-control identity.
- [ ] Prove repeated workflow execution leaves all four market tables unchanged.
- [ ] Full focused E2E plus `uv run portfell-quality merge` pass from one clean SHA.

Parallelization: final technical source-cutover gate.
Security: end-to-end least privilege/fail closed.
Determinism: verified source and stable lineage.
Idempotency: zero market mutation.
Rollback: tests/evidence only.

### PR342 — pr342-production-postgres-cutover-runbook

Branch: `docs/pr342-production-postgres-cutover-runbook`

Commit scope: `docs(pr342-production-postgres-cutover-runbook): ...`

Depends on: PR341.

Owned paths: production cutover/rollback runbook and operator checklist only.

Tasks / Acceptance:

- [ ] Preflight exact market DSN presence, endpoint reachability, four-table SELECTs, LOGIN membership in `portfell_app`, non-superuser state, UTC, and read-only transaction behavior.
- [ ] Require PR340 PASS and PR341 PASS before production switch.
- [ ] Back up surviving Portfell analytical/application state only; legacy Portfell market files/caches are disposable and never migrated into loader serving plane.
- [ ] Deterministic smoke checks cover `/metadata`, `/univariate`, `/bivariate`, `/multivariate` and representative calculations.
- [ ] Rollback changes only Portfell app version/config; it must never reactivate provider download, medallion persistence, market NAS fallback, or broader DB grants.
- [ ] Checklist contains no secret values and can be executed without architectural guessing.
- [ ] Docs validation and `uv run portfell-quality pr` pass.

Parallelization: terminal production source-cutover gate.
Security: no secret disclosure; least privilege preserved on rollback.
Determinism: ordered cutover/rollback.
Idempotency: read-only preflights/smokes do not mutate market data.
Rollback: explicitly defined.

### PR343 — pr343-rebase-deferred-product-backlog

Branch: `docs/pr343-rebase-deferred-product-backlog`

Commit scope: `docs(pr343-rebase-deferred-product-backlog): ...`

Depends on: PR342.

Owned paths: active backlog/planning docs only; no production code.

Tasks / Acceptance:

- [ ] Re-audit old PR264-PR295 branches against the new PostgreSQL-only, single-user `main`; no old branch is merged wholesale by this PR.
- [ ] Preserve still-valid product invariants: four-stage workflow; Plotly Dash target mounted in FastAPI; Multivariate as sole optimizer page/stage; three frozen objectives; objective-specific OOS winner selection; professional plots; Universe & History evidence; analytical persistence/reproducibility requirements.
- [ ] Explicitly retire old Portfell-owned market refresh/download concepts, including old PR293-style shared market refresh, because loader owns market refresh.
- [ ] For every old work order, classify `reuse-cleanly`, `reimplement`, `split`, or `retire` with exact evidence/path conflicts.
- [ ] Create a new atomic dependency graph for remaining Dash/Multivariate/scheduled-analytics product work using the post-PR342 architecture and weak-agent ownership rules.
- [ ] Scheduled analytical research, if retained, consumes PostgreSQL snapshots only and cannot trigger loader/provider refresh or query `xetra_loader_sync`.
- [ ] No product requirement is silently lost merely because an old implementation branch is superseded.
- [ ] Backlog/docs validation and `uv run portfell-quality pr` pass.

Parallelization: planning gate for the next product series, not an implementation branch merge.
Security: new plan inherits PostgreSQL-only least privilege.
Determinism: every old requirement receives explicit disposition.
Idempotency: docs only.
Rollback: docs only.

## 8. Final completion gate for this series

PR342 is the production source-cutover completion gate; PR343 is the required carry-forward planning gate for deferred product work.

Source cutover is accepted only when clean `main` proves:

- all market inputs come through `MarketDataGateway` from exact `xetra_loader` business tables;
- raw PostgreSQL contract preserves `Decimal`/date/UTC semantics and full listing identity;
- analytical projection uses adjusted close without raw-close fallback, does not double-count dividends, and invents no split formula;
- new Metadata universes use active listings only;
- one analytical market snapshot uses repeatable-read/read-only semantics and deterministic input lineage;
- Portfell LOGIN identity is non-superuser, member of NOLOGIN `portfell_app`, can SELECT business tables, cannot mutate them, and cannot access `xetra_loader_sync`;
- no EODHD/provider acquisition, credential backend/UI, market medallion writer, NAS/filesystem fallback, shared-market publisher/refresh, download worker, or market cron remains executable;
- source outages/incomplete data fail closed under frozen source/analytical error semantics;
- single-user backend/UI is complete with `/metadata`, `/univariate`, `/bivariate`, `/multivariate` and REST `/api`;
- clean install/runtime requires no provider secret or market NAS mount;
- xetra-loader XDL-PR053 V2 artifact is present and PASS before live gate;
- PR340 proves real serving-plane contract/least privilege;
- PR341 proves complete source replacement E2E;
- PR342 provides executable cutover/rollback without legacy acquisition reactivation;
- PR343 preserves/replans still-valid Dash/Multivariate product requirements rather than silently discarding old PR264-PR295 scope.
