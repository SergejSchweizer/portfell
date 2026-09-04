# Portfell — Authoritative Backlog

Last reviewed: 2026-09-04

## 0. Single-file authority

`BACKLOG.md` is the only executable backlog authority for Portfell. Historical backlog text, old pull-request descriptions, archived planning branches, and old UI/database architecture documents are reference material only when they conflict with this file.

The legacy backlog that existed immediately before this rewrite is preserved in Git at commit `35cbec2e5502bff30d57c4235ade49c8bb6e41d3`. Its PR01–PR252 history remains auditable there, but no unfinished legacy UI/database work from that snapshot may be implemented unless it is explicitly re-listed below.

`GATES.md` remains the sole authority for quality/coverage thresholds. Any PR below that changes the runtime/test stack must update `GATES.md` in the same PR or in the explicitly named gate PR.

## 1. Final target architecture — hard decision

Portfell is moving to a Python-first, single-user analytical application. The final browser UI is **Plotly Dash**. The existing hand-written React/Vite/TypeScript/TanStack frontend is transitional and is deleted after Dash functional parity is proven.

Final production topology:

```text
Browser
  |
  v
Plotly Dash pages + callbacks
  |
  v
FastAPI / typed Portfell application services
  |                         |
  |                         +--> external PostgreSQL market source
  |                              10.10.1.3:54321 / xetra_loader
  |                              schema xetra_loader
  |                              read-only, coherent snapshots
  |
  +--> NEW Portfell-owned PostgreSQL application/research database
       database: portfell_dash
       schema: portfell
       single-user state and analytical persistence only
```

### 1.1 Complete UI replacement means complete replacement

The final runtime must satisfy all of the following simultaneously:

- exactly four production Dash pages exist: `/metadata`, `/univariate`, `/bivariate`, `/multivariate`;
- Plotly Dash is the only Portfell-owned browser application framework;
- all first-party React pages/components/hooks/stores/providers are deleted;
- the Vite build, TypeScript frontend build, TanStack Query cache, Vitest frontend stack, npm/pnpm/yarn application build, Node production Web image/stage, and React-specific runtime configuration are deleted;
- `apps/web/**` is deleted after parity and negative-space QA;
- no compatibility iframe, embedded legacy React route, proxy to the old Web container, hidden feature flag, or dual-UI runtime is allowed after cutover;
- no new business feature may be implemented only in the legacy UI after this architecture decision;
- Dash may of course contain transitive browser technology internally; the prohibition is on a Portfell-maintained React/Vite/TypeScript/TanStack application and Node frontend build boundary;
- static CSS/assets required by Dash may remain under the Dash assets directory and require no JavaScript build pipeline.

### 1.2 Complete database replacement means complete replacement

The existing Portfell-owned hosted application/tenant/control-plane database model is also transitional. The final runtime uses a **new clean database** named `portfell_dash`, not an in-place evolution of the old hosted schema.

Hard rules:

- `PORTFELL_DATABASE_URL` points only to the new `portfell_dash` database in the final runtime;
- the new application schema is `portfell` and is created from new migrations owned by this series;
- old user, tenant, membership, project-membership, encrypted-provider-credential, navigation-projection, workflow-projection, durable-status-event, legacy download/ingestion, and legacy browser-state tables are not migrated into the new schema;
- no dual-read, dual-write, table fallback, view compatibility layer, or old-schema adapter is permitted after cutover;
- the old Portfell application database is backed up before destructive removal, becomes rollback-only/offline, and is removed from Compose/runtime ownership after the final acceptance gate;
- old Portfell PostgreSQL volumes/databases, legacy DB credentials, old migrations, and old repository adapters are deleted from the active runtime after the new DB is proven;
- analytical state needed in the new application is recomputed or explicitly recreated through new contracts; legacy rows are not silently imported;
- the external `xetra_loader` PostgreSQL database is **not** a legacy Portfell database and is not deleted. It remains the canonical market-data authority;
- `xetra_loader_sync` remains inaccessible to the Portfell application and is never a data source;
- `PORTFELL_MARKET_DATABASE_URL` and `PORTFELL_DATABASE_URL` are separate authorities and never fall back to one another.

### 1.3 Final application-state model

The clean `portfell_dash` database is single-user and contains only state that Portfell itself owns. The v1 schema must provide these canonical concepts, with exact DDL frozen by PR345 before implementation callers depend on it:

- one singleton workspace identity (`default`);
- immutable `market_source_snapshots` lineage records;
- versioned `metadata_universes`;
- exact full-identity `metadata_universe_members`;
- stage-neutral `analysis_runs` with stage, status, input snapshot, algorithm version, timestamps, and typed failure code;
- immutable `analysis_artifacts` identified by run and artifact type;
- versioned `univariate_selections` and exact members;
- immutable `decision_artifacts` for Multivariate winner/diagnostic explanation;
- small `ui_preferences` values that are genuinely presentation state and not financial authority.

No `user_id`, tenant membership, project membership, provider credential owner, RLS tenant partition, or browser cache table exists in the new schema. Domain identifiers may exist only where they are intrinsic analytical identities, never as security scopes.

### 1.4 Market-source invariants that survive the replacement

- external endpoint: `10.10.1.3:54321`;
- external database: `xetra_loader`;
- business schema: `xetra_loader`;
- business tables: `listings`, `eod_quotes`, `dividends`, `splits`;
- listing identity is always `(isin, exchange, code)`; ISIN alone is never a business key;
- Portfell uses a secret-supplied non-superuser LOGIN role that is a member of external NOLOGIN group role `portfell_app`;
- application access to `xetra_loader_sync` must fail and that failure is PASS evidence;
- analytical input assembly uses `REPEATABLE READ, READ ONLY`, UTC session semantics, and closes the DB transaction after data materialization before CPU-heavy analysis;
- market SQL lives only under `src/portfell/market_source/**`;
- repository reads batch at most 500 listing identities per SQL statement and never use N+1 access where a batch API exists;
- raw PostgreSQL `NUMERIC` remains `Decimal` until one centralized analytical projection boundary;
- `trade_date` and `event_date` map to Python `date`;
- `adjusted_close` is authoritative for return/risk/volatility/drawdown calculations;
- missing adjusted close yields typed `missing_adjusted_close`, never fallback to raw `close`;
- dividends are distribution/income evidence and are not double-counted on top of adjusted-close returns;
- no split-return adjustment formula is introduced by the source/UI replacement;
- new Metadata universes use only `is_active=true`; inactive listings remain historically resolvable by full identity;
- Python metadata predicate semantics are preserved rather than silently redefined by PostgreSQL collation/`ILIKE`;
- source preflight is low-cost and never infers loader run state from full-table scans or the sync schema.

### 1.5 Local PostgreSQL `config.yaml` contract

PostgreSQL connection metadata must be explicit, local, and impossible to commit accidentally.

- repository-root `config.yaml` is the canonical local configuration file for **non-secret PostgreSQL connection metadata** used by Portfell;
- `config.yaml` must be listed in `.gitignore` and must never be committed, staged, copied into a Docker image, or emitted as an artifact;
- a tracked `config.example.yaml` must document the schema with placeholders only and contain no real credentials, complete credential-bearing DSN, tokens, or passwords;
- `config.yaml` must contain separate `postgres.app` and `postgres.market` sections so the Portfell application database and the external xetra-loader database can never collapse into one authority;
- `postgres.app` records at least `host`, `port`, `database: portfell_dash`, `schema: portfell`, and the configured LOGIN role name;
- `postgres.market` records at least `host: 10.10.1.3`, `port: 54321`, `database: xetra_loader`, `schema: xetra_loader`, business tables `listings`, `eod_quotes`, `dividends`, `splits`, and the configured LOGIN role name/member-of expectation for NOLOGIN group role `portfell_app`;
- raw passwords and tokens are not PostgreSQL metadata and must remain secret-supplied outside Git. `config.yaml` may contain only the name/reference of the secret source, never the secret value itself;
- `PORTFELL_DATABASE_URL` and `PORTFELL_MARKET_DATABASE_URL`, when used by deployment/runtime composition, remain independent secret-supplied connection authorities. Startup must verify that their non-secret host/port/database/schema/role identity is consistent with `config.yaml`; mismatch fails closed and neither DSN may fall back to the other;
- tests must prove `git check-ignore config.yaml` succeeds, `config.example.yaml` is tracked and secret-free, and startup rejects missing/malformed/mismatched PostgreSQL metadata with a typed/redacted configuration error.

PR308 owns the first implementation of this contract for the market source and the shared configuration loader. PR345/PR358 must extend/use the same contract for the new `portfell_dash` database rather than introducing another config file or configuration authority.

### 1.6 Plotly Dash visual reference and simplicity contract

The primary visual and interaction reference for the replacement UI is:

`https://financial-dashboard-example.plotly.app/`

The reference is used for **layout grammar and visual simplicity only**. Portfell must not copy the reference application's branding, fund-specific text, financial values, logos, images, downloadable documents, or source assets. The reference is never a runtime dependency, is never embedded by iframe, and deterministic tests must not require network access to it.

The final Portfell Dash application must deliberately mirror the reference application's simple financial-dashboard composition:

- persistent left navigation on desktop with one clearly highlighted active item;
- a small product header (`Portfell`) above navigation rather than a separate dashboard/home page;
- exactly four navigation items, in this order: `Metadata`, `Univariate`, `Bivariate`, `Multivariate`;
- a compact sidebar context block analogous to the reference's fund-information area, but showing Portfell workflow context only: current universe/version, selected instrument count when available, current market-source snapshot short ID, and current stage readiness;
- no resource/download section unless a later backlog contract explicitly introduces one;
- main content begins with one page title and one short descriptive subtitle;
- controls are grouped in one compact control strip directly below the title rather than scattered across the page;
- important stage metrics are shown in a small KPI-card row before detailed plots/tables;
- detailed content is grouped into white cards with a light border, modest radius, restrained shadow, clear card title, and generous whitespace;
- use Plotly charts as the primary visualization language; avoid decorative gauges, gradients, 3D charts, carousels, marketing hero sections, or animation that does not communicate analytical state;
- use one blue interaction/accent family, neutral grays, semantic green only for positive/success state, and semantic red only for negative/error state;
- use a system sans-serif font stack; no externally hosted font is required;
- pages must feel like one application: identical sidebar, title spacing, control layout, card styling, table styling, plot template, loading/error behavior, and stage footer;
- the UI exposes exactly the capabilities frozen elsewhere in this backlog. The visual reference must never be used as justification to add unrelated fund-management, benchmark, fee, document, or market-data-download features.

Frozen v1 layout tokens to be implemented by PR348 and finalized by PR354:

- desktop sidebar width: `220px`;
- desktop main padding: `24px`; tablet/mobile main padding: `16px`;
- layout gap: `16px`;
- card radius: `8px`;
- background: `#f7f9fc`;
- card/surface: `#ffffff`;
- border: `#e3e8ef`;
- primary text: `#172033`;
- muted text: `#6b7280`;
- accent: `#2f80ed`;
- accent-soft active-navigation background: `#eaf3ff`;
- success: `#198754`;
- danger: `#dc3545`;
- font stack: `system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`;
- no full-page horizontal scroll at supported viewport widths;
- tables may scroll horizontally inside their own card on narrow screens;
- Plotly figures use the shared Portfell figure template and `responsive=true` behavior.

Frozen page frame:

```text
+----------------------+--------------------------------------------------+
| Portfell             | Page title                                       |
|                      | Short subtitle                                   |
| Metadata             | [ compact controls / primary stage action ]      |
| Univariate           |                                                  |
| Bivariate            | [ KPI ] [ KPI ] [ KPI ] [ KPI ]                  |
| Multivariate         |                                                  |
|                      | [ primary chart/table card                      ] |
| Current analysis     | [ secondary chart/table/evidence card           ] |
| universe / snapshot  |                                                  |
| readiness            | [ Universe & History / stage footer             ] |
+----------------------+--------------------------------------------------+
```

Responsive contract:

- desktop `>= 1100px`: fixed `220px` sidebar, four-column KPI row when four KPIs exist, main content fluid;
- tablet `768px–1099px`: sidebar remains visible at reduced content density, KPI row becomes two columns, charts remain full-card width;
- mobile `< 768px`: sidebar converts to a compact top navigation region using CSS/Dash only, KPI cards stack to one column, charts and controls stack, tables scroll inside cards, and the page itself has no horizontal overflow;
- deterministic browser QA uses at least `1440x900`, `1024x768`, and `390x844` viewports.

Shared presentation primitives are frozen as `PageHeader`, `ControlBar`, `KpiCard`, `ChartCard`, `TableCard`, `StatusBanner`, `HistoryCard`, and `StageFooter`. PR348 owns their first implementation. Page PR349–PR352 must consume them rather than creating page-specific substitutes. PR354 may refine only shared presentation/figure styling and must not change financial calculations or stage semantics.

## 2. Global weak-agent execution contract

Every active PR below is a complete work order. Agents must not infer missing architecture decisions.

For every PR:

- record `git status --short --branch` before changing files;
- start from the exact merged dependency SHA; stop if a required predecessor is unmerged;
- sibling PRs start from the same predecessor SHA, not from one another;
- use the exact branch name and commit scope listed below;
- every non-`main` branch commit uses Conventional Commits with the branch's exact PR slug as
  scope (for example, `feat(pr310-xetra-quotes-repository): add quote reader`);
- `main` accepts rebase-only automatic completion after a pull request's successful `merge-gate`;
  native GitHub branch protection is unavailable for the current private repository plan, so this
  workflow is the enforced repository automation until the plan supports protection rules;
- change only owned paths plus explicitly named synchronized documentation/test manifests;
- do not add compatibility fallbacks, second market sources, second UI runtimes, dual DB reads/writes, broader database grants, or opportunistic refactors;
- implementation PRs run focused tests plus `uv run portfell-quality pr`;
- QA/integration PRs also run `uv run portfell-quality merge`;
- GitHub executes the complete `merge-gate` once per pull request targeting `main`; do not add a
  second workflow that reruns the same test, browser, container, or coverage families;
- QA PRs own tests/evidence only. Production defects discovered by QA require a corrective implementation PR rather than hidden QA fixes;
- browser-visible errors contain typed public codes/messages and never credentials, DSNs, SQL, paths, stack traces, or database internals;
- completed analytical revisions are immutable; retries create/reuse exact idempotent identities instead of mutating published results;
- no production UI callback performs direct SQL. Dash callbacks call typed application services; market SQL remains behind `MarketDataGateway`, application-state SQL remains behind the new `app_state` repository boundary.

## 3. Source cutover and simplification series — PR308–PR343 — OUTDATED

This series removes provider acquisition and legacy market-storage authority before the destructive Dash/database replacement. It is the prerequisite data-plane simplification.

Dependency graph:

```text
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
xetra-loader production V2 PASS artifact
  |
PR340(live QA) -> PR341(E2E) -> PR342(runbook) -> PR343(closeout)
```

### Execution status — 2026-08-30

- PR320 is integrated on `main` at `03cec1a`. It reads each Univariate computation from one coherent market snapshot and its complete local merge gate passes (`1034 passed`).
- PR321 is integrated on `main` at `8172ed4`. It reads each Bivariate computation from one coherent market snapshot and its complete local merge gate passes (`1029 passed`).
- PR322 is integrated on `main` at `511a32c`. It consumes source-pinned Multivariate inputs, preserves solver and validation semantics, and its complete local merge gate passes (`1037 passed`).
- PR323 is integrated on `main` at `c106498`; the four-stage semantic QA passes (`1040 passed`). The PR324–PR331 deletion-wave siblings are now unblocked and may proceed in parallel; later PRs remain governed by their explicit dependencies.
- PR327 is integrated on `main` at `0921245`. It deletes Portfell-owned shared market cache, refresh, publisher, inventory, and cron surfaces; the complete PR gate passes (`876 passed`).
- PR328 is integrated on `main` at `3549ad8`. It removes hosted provider-download, metadata-refresh, bootstrap, and quote-run lifecycle surfaces while retaining source-backed analytics; the complete PR gate passes (`911 passed`). The current `main` gate also passes all `911` tests but remains blocked at `88.98%` coverage pending the remaining deletion-wave siblings.
- The external xetra-loader production V2 artifact gate is now cleared: `artifacts/acceptance/postgres-full-sync-v2.json` exists on xetra-loader `main` and reports `status: PASS`. PR340 is therefore no longer blocked by the external artifact itself, but it still cannot start until PR339 is merged.

### PR308 — Xetra source contract foundation

Branch: `refactor/pr308-xetra-source-contract`

Priority: P0.

Git status: integrated on `main` at `691e8db`. Focused market-source tests and the complete PR
quality gate pass (`1001 passed`); the gate specifications are synchronized with this authoritative
backlog's transitional architecture. The local PostgreSQL metadata contract was subsequently
verified with the dedicated external LOGIN role `portfell`, a member of `portfell_app`. The
repository-wide coverage threshold is now `90%`; the complete `main` gate passes with `1001`
tests and `91.54%` coverage.

Scope: create only the new `src/portfell/market_source/` foundation (`errors.py`, `config.py`, `contracts.py`, `connection.py`, package init), the shared local PostgreSQL configuration contract (`config.yaml` loader/validation, tracked secret-free `config.example.yaml`, `.gitignore` rule for `config.yaml`), plus focused tests. Define `PORTFELL_MARKET_DATABASE_URL`, exact DTOs/types/keys, the six frozen source errors, role validation, UTC session behavior, and read-only/repeatable-read transaction helpers.

Frozen errors: `market_source_config_missing`, `market_source_unavailable`, `market_source_role_invalid`, `market_source_contract_mismatch`, `market_source_duplicate_key`, `market_source_invalid_value`.

Acceptance: no import of the xetra-loader Python package; no executable sync repository/API; non-superuser LOGIN membership in NOLOGIN `portfell_app` is required; market DSN never falls back to app DSN; PostgreSQL market metadata is read from the gitignored `config.yaml`; `config.example.yaml` is tracked and secret-free; `git check-ignore config.yaml` passes; DSN-vs-config identity mismatch fails closed; focused tests and PR gate pass.

Security: credentials are secret-supplied and never rendered/logged or written as raw values to `config.yaml`/`config.example.yaml`.

Determinism: exact connection/session settings and normalized local configuration are asserted.

Idempotency: connection/preflight reads are non-mutating.

### PR309 — Listings repository

Branch: `feat/pr309-xetra-listings-repository`

Depends on: PR308.

Git status: integrated on `main` at `452e45e`. The SELECT-only listings repository preserves
full listing identities, applies 500-key batching, and passed its complete PR gate (`1004 passed`).

Scope: SELECT-only repository over `xetra_loader.listings`; full identity lookup, batch lookup, exact active-universe read; no business filtering inside SQL beyond contract fields.

Acceptance: active/inactive semantics exact; duplicate ISINs across listing identities are preserved; stable full-key ordering; 500/501 batching; parameterized SQL; no write/fallback/`ILIKE` semantic substitution.

### PR310 — Quote repository

Branch: `feat/pr310-xetra-quotes-repository`

Depends on: PR308.

Git status: integrated on `main` at `099bb91`. The SELECT-only quote repository preserves
`date` and `Decimal` values, applies inclusive 500-key batching, and passed its complete PR gate
(`1008 passed`).

Scope: `eod_quotes` repository with full identity, inclusive date range, exact fields and `Decimal` values.

Acceptance: stable identity+trade_date ordering; duplicate key raises frozen typed error; UTC/date semantics; bounded query count including 501-identity test; no adjusted-close fallback.

### PR311 — Dividend repository

Branch: `feat/pr311-xetra-dividends-repository`

Depends on: PR308.

Git status: integrated on `main` at `ede9f46`. The SELECT-only dividend repository preserves
same-day source events and nullable `Decimal` values, applies inclusive 500-key batching, and
passed its complete PR gate (`1010 passed`).

Scope: full-identity/batched/inclusive-date reads from `dividends`.

Acceptance: preserve `event_key`, nullable/Decimal fields, stable identity/event_date/event_key ordering, same-day events, bounded queries, no writes/fallback.

### PR312 — Split repository

Branch: `feat/pr312-xetra-splits-repository`

Depends on: PR308.

Git status: integrated on `main` at `3e2596a`. The SELECT-only split repository preserves source
`split_ratio` and optional `Decimal` factors, applies inclusive 500-key batching, and passed its
complete PR gate (`1012 passed`).

Scope: same repository contract for `splits`.

Acceptance: preserve textual `split_ratio`, optional Decimal split factor, no local event-key generation, stable ordering/batching, no split-return calculation.

### PR313 — Low-cost source status

Branch: `feat/pr313-market-source-status`

Depends on: PR308.

Git status: integrated on `main` at `d1e3b5e`. The low-cost preflight verifies database/schema/role membership without reading source data, scanning
tables, accessing the sync schema, or issuing DDL; its complete PR gate passed (`1017 passed`).

Scope: low-cost connectivity/schema/role preflight only.

Acceptance: no full scans, no global max-timestamp freshness inference, no sync-schema access, no DDL.

### PR314 — Analytical projection boundary

Branch: `refactor/pr314-market-source-projection`

Depends on: PR308.

Git status: integrated on `main` at `f0f209d`. The centralized raw-DTO projection converts
`Decimal` values only at the analytical boundary, rejects missing adjusted close with a typed
error, and keeps dividend and split events outside return construction; its complete PR gate
passed (`1019 passed`).

Scope: one centralized mapping from raw market DTOs to analytical inputs.

Acceptance: `Decimal` conversion is centralized; missing adjusted close is typed; dividends not double-counted; no split return transform; regression fixtures preserve existing valid formulas.

### PR315 — MarketDataGateway and coherent snapshot

Branch: `feat/pr315-market-data-gateway`

Depends on: PR309–PR314.

Git status: integrated on `main` at `3a13e68`. `MarketDataGateway` materializes listings,
quotes, dividends, and splits through one short-lived repeatable-read/read-only transaction and
closes it after materialization; its complete PR gate passed (`1020 passed`).

Scope: only stage-level market seam; one coherent repeatable-read/read-only snapshot across required tables; batch reads only.

Acceptance: market SQL only under `market_source`; transaction closes after materialization; no sync/write/refresh/download operations; concurrency fixture proves coherent snapshot.

### PR316 — Source contract QA

Branch: `test/pr316-market-source-contract-qa`

Depends on: PR315.

Git status: integrated on `main` at `40789a8`. An isolated Docker PostgreSQL fixture validates
the NOLOGIN group/reader-role contract, exact source tables, 1001-record batching, repeatable-read
isolation, projection behavior, and provider/sync negative space; `uv run portfell-quality merge`
passed.

Scope: QA only. Build a contract-faithful PostgreSQL fixture with NOLOGIN group-role semantics and exact table types/keys.

Acceptance: role/read-only checks, 1001 batching, repeatable-read concurrency, projection behavior, sync/provider negative-space; `uv run portfell-quality merge` passes.

### PR317 — Hosted runtime read-plane cutover

Branch: `refactor/pr317-hosted-market-read-plane`

Depends on: PR316.

Git status: integrated on `main` at `5d15e03`. PostgreSQL hosted composition accepts a
server-owned, lazy `MarketDataGateway` and fails closed when it is absent; the gateway is never
browser-provided and its complete PR gate passed (`1022 passed`).

Scope: remove provider acquisition capabilities/provider-key arguments from hosted runtime ports and wire `MarketDataGateway` through composition. Legacy acquisition code may remain physically until deletion wave but must be unreachable.

Acceptance: hosted services can request market reads only through gateway; no provider command is reachable from browser/API composition.

### PR318 — MarketSourceSnapshot lineage

Branch: `refactor/pr318-market-source-lineage`

Depends on: PR317.

Git status: integrated on `main` at `4468f84`. `MarketSourceSnapshot` derives deterministic
`market_source.snapshot@v1` IDs from canonical semantic source DTOs only, excluding runtime,
provenance, DSN, credential, and sync metadata; its complete PR gate passed (`1024 passed`).

Scope: remove provider-download/quote-run lineage from research contracts and introduce deterministic `market_source.snapshot.v1`.

Acceptance: snapshot ID hashes semantic consumed rows only; excludes observation wall-clock, provenance timestamps, DSN, credentials, sync state; streaming/canonical hash; analytical IDs use snapshot identity; no fallback market-row copies.

### PR319 — Metadata source cutover

Branch: `refactor/pr319-metadata-market-source`

Depends on: PR318.

Git status: integrated on `main` at `ee1bc1c`. Active full-identity listings now come only from
the external market gateway; the consumed listing snapshot is persisted as metadata lineage and the
application and market PostgreSQL DSNs both fail closed unless they match `config.yaml`.

Scope: Metadata uses active listings from gateway only.

Acceptance: full identity/predicates preserved; inactive excluded from new universe; snapshot lineage persisted; no fallback.

### PR320 — Univariate source cutover

Branch: `refactor/pr320-univariate-market-source`

Depends on: PR318.

Git status: integrated on `main` at `03cec1a`. Univariate reads are pinned to a coherent
external-market snapshot with deterministic lineage; the complete local merge gate passes
(`1034 passed`).

Scope: quotes/dividends through one gateway snapshot; remove download/shared-market branches.

Acceptance: 252 annualization/formulas/income/selection semantics preserved; missing adjusted close typed; no split transform; regression equivalence.

### PR321 — Bivariate source cutover

Branch: `refactor/pr321-bivariate-market-source`

Depends on: PR318.

Git status: integrated on `main` at `8172ed4`. Bivariate computations now consume one
coherent external-market snapshot through the gateway, retain the source-snapshot lineage, and
the complete parallel test suite passes (`1029 passed`).

Scope: selected quote rows tied to one snapshot; no quote-run lookup.

Acceptance: formulas/common-calendar/minimum-observation/pair guards/skip-same-ISIN preserved; full identity; no missing-covariance-as-zero; regression equivalence.

### PR322 — Multivariate source cutover

Branch: `refactor/pr322-multivariate-market-source`

Depends on: PR318.

Git status: integrated on `main` at `511a32c`. Multivariate reads are pinned to the Bivariate
market-source snapshot and the pure return-series helper is storage-independent; the complete
local merge gate passes (`1037 passed`).

Scope: snapshot quote/dividend lineage; pure return helper moved out of legacy persistence module; objectives/solvers/risk/walk-forward/OOS winner remain unchanged.

Acceptance: exact matrix fixture; no source-plane redesign; Equal Weight is never a hidden failure fallback.

### PR323 — Four-stage semantic QA

Branch: `test/pr323-four-stage-market-source-qa`

Depends on: PR319–PR322.

Git status: integrated on `main` at `c106498`. End-to-end Metadata → Univariate → Bivariate
→ Multivariate source QA verifies full identity, source lineage, Decimal/date projection,
corporate-action non-interference, immutable reads, and fail-closed partial/insufficient input
behavior; the complete local merge gate passes (`1040 passed`).

Scope: QA only across Metadata -> Univariate -> Bivariate -> Multivariate.

Acceptance: active/inactive, duplicate ISIN/full identity, missing adjusted, dividends, split non-interference, UTC/date, Decimal projection, regression equivalence, one snapshot lineage; unavailable/partial/insufficient sources fail closed; market tables unchanged; no sync refs/direct SQL outside market_source; merge gate passes.

### PR324–PR331 — Legacy market/provider deletion wave

All depend on PR323 and are parallel siblings.

- PR324 `chore/pr324-delete-eodhd-client`: delete EODHD client/search/fetch CLI and executable provider acquisition.

  Git status: integrated on `main` at `54eb044`; the complete PR quality gate passes (`972 passed`).
  The main gate remains blocked at `89%` coverage until PR325 and PR327 remove the corresponding
  legacy persistence and shared-refresh implementation.
- PR325 `chore/pr325-delete-market-medallion`: delete market Bronze/Silver/Gold persistence/pipeline while retaining pure analytics moved elsewhere.

  Git status: integrated on `main` at `3b88d30`; the complete PR quality gate passes (`944 passed`).
  The main gate remains blocked at `88.48%` coverage while the PR327 shared-refresh plane and
  later deletion siblings still retain legacy implementation.
- PR326 `chore/pr326-delete-market-filesystem-plane`: delete market NAS/filesystem authority; preserve unrelated analytical/app artifacts only.

  Git status: integrated on `main` at `109e2d9`; focused validation passes (`44 passed`). Removed the NAS bind-mounted market
  volume, preflight/inventory entry points, and their tests/docs. As the narrowly required
  cross-sibling adaptation, the retained legacy cron entry point is fail-closed and disabled
  without any filesystem, Compose, or market refresh action; PR327 owns its final deletion.
- PR327 `chore/pr327-delete-shared-market-refresh`: integrated on `main` at `0921245`; Portfell-owned market refresh/publisher/cron/cache plane is deleted and xetra-loader owns refresh.
- PR328 `chore/pr328-delete-hosted-download-lifecycle`: integrated on `main` at `3549ad8`; hosted market download routes/workers/jobs are deleted.
- PR329 `chore/pr329-delete-provider-credentials`: delete provider credential backend; do not replace it with plaintext config.

  Git status: integrated on `main` at `ba8a3d4`; focused hosted API/catalog tests pass (`33 passed`).
- PR330 `chore/pr330-freeze-legacy-web-provider-ui`: delete provider-loading UI/actions. This PR must not add React features; it only removes provider controls and leaves the old UI transitional until PR356.

  Git status: integrated on `main` at `893af0e`; local Docker Node type checking, production build, 96.77% aggregate unit coverage, and Playwright
browser tests (3 passed) pass locally.
- PR331 `chore/pr331-delete-hosted-local-market-runtime`: delete residual hosted local market runtime and EODHD/token/KEK/provider runtime config not owned by siblings.

  Git status: integrated on `main` at `b13eb0f`; the remaining local hosted runtime and local
test composition are removed, with test-only in-memory composition replacing them (`61 passed`).

Acceptance for every sibling: owned deletion is complete, no unrelated refactor, focused tests and PR gate pass.

### PR332 — Provider-removal negative-space QA

Branch: `test/pr332-provider-removal-negative-space`

Depends on: PR324–PR331.

Scope: QA only.

Acceptance: scan executable Python, entrypoints, current UI, Compose/workflows/scripts, tests/docs; no provider acquisition/credentials/medallion/market filesystem fallback/shared refresh/download/cron; no sync refs; no raw market SQL outside `market_source`; OpenAPI clean; full merge gate.

Git status: integrated on `main` at `7a980af`; executable negative-space checks cover the
retired provider/refresh module and CLI inventories, OpenAPI lifecycle surface, and raw market
SQL boundary. Full parallel test suite passes.

### PR333 — Single-user backend simplification

Branch: `refactor/pr333-single-user-backend`

Depends on: PR332.

Git status: integrated on `main` at `fe2b672` after rebase. Production composition now fixes
one canonical workspace principal and no longer composes a hosted-user lifecycle repository.
Focused API, architecture, contract, Ruff, and Pyright checks pass locally. The GitHub workflow
also now accepts stacked pull requests and documents the required final rebase-and-rerun gate.

Scope: remove user/tenant/membership/project-membership/credential-owner security authority from production services. Domain run/selection IDs may remain, but never as tenant scopes.

Acceptance: one workspace; no authorization behavior depends on user/project membership; no provider credentials; backend tests prove single-user semantics.

### PR334 — Legacy UI freeze for source-cutover compatibility

Branch: `refactor/pr334-freeze-legacy-ui`

Depends on: PR332.

Git status: integrated on `main` at `1739294` after rebase. The legacy shell now exposes only
the canonical `/metadata`, `/univariate`, `/bivariate`, and `/multivariate` navigation routes;
project switching is removed. Production server fallbacks and browser tests enforce those routes.
Docker Node type checking, production build, 96.77% aggregate unit coverage, and Playwright
browser tests (3 passed) pass locally.

Scope: **transitional only**. Remove user/project switching and obsolete provider controls needed to keep the legacy UI usable during source cutover. Do not redesign it and do not add new React/TanStack/Vite functionality.

Acceptance: canonical transitional routes `/metadata`, `/univariate`, `/bivariate`, `/multivariate`; no project selector/user switching; all new product UI work is explicitly deferred to Dash PR348–PR354.

### PR335 — Single-user/source-cutover QA

Branch: `test/pr335-single-user-source-cutover-qa`

Depends on: PR333 and PR334.

Acceptance: one workspace, no membership/security scope, four transitional routes, market PG privileges unchanged, full merge gate. This PR is not Dash parity evidence.

Git status: integrated on `main` at `3755ed9` after rebase. The QA guard verifies the
single workspace principal, absence of user/credential authority, canonical transitional
routes, and read-only external-market transaction and role constraints (10 focused tests pass).

### PR336 — Package/entrypoint cleanup

Branch: `chore/pr336-market-source-package-cleanup`

Depends on: PR335.

Scope: remove provider/loading/NAS/refresh CLI/dependencies, update package description, retain required PostgreSQL/analytics dependencies, regenerate lock, add market import-boundary checks.

Git status: integrated on `main` at `2a1ed48` after rebase. Retired local-market CLI and
workflow modules are deleted; packaging retains only PostgreSQL and analytics requirements and
negative-space/import-boundary checks enforce the removal (848 local tests, Ruff, and Pyright pass).

### PR337 — Transitional Compose source topology

Branch: `chore/pr337-market-source-compose`

Depends on: PR335.

Scope: keep Portfell application DB and external read-only market DB distinct during source cutover; no provider secrets/download workers; Compose never owns xetra-loader.

Acceptance: required external market DSN; no market DSN fallback; fixture uses LOGIN member of NOLOGIN `portfell_app`; market DML fails. This Compose is explicitly superseded later by PR358 for the new `portfell_dash` DB + Dash runtime.

Git status: integrated on `main` at `1717932` after rebase. Compose requires an explicit,
distinct external market DSN and secret, while the disposable Docker contract fixture proves
read-only role membership and market DML denial (852 local tests; Compose and Docker fixture pass).

### PR338 — Source architecture documentation

Branch: `docs/pr338-market-source-architecture`

Depends on: PR335.

Scope: document xetra-loader -> external PostgreSQL -> Portfell, exact keys/tables/role/snapshot/adjusted-close/Decimal/sync denial. Mark React/Vite UI and current Portfell application DB as transitional and point to PR344–PR360.

Git status: integrated on `main` at `0b56d77` after rebase. The navigable source-architecture
sidecar defines the external PostgreSQL authority, immutable snapshot contract, adjusted-close
and Decimal rules, sync denial, and the transitional application/UI boundary (4 focused QA tests pass).

### PR339 — Clean source-cutover runtime QA

Branch: `test/pr339-clean-market-source-runtime`

Depends on: PR336–PR338.

Acceptance: clean `uv sync`, imports, entrypoints, Compose/container without provider/NAS; two DB authorities remain separate; fixture exercises all four analytical stages; full merge gate.

Git status: integrated on `main` at `d8c538f` after rebase. The clean runtime guard covers
imports, entrypoints, exact two-PostgreSQL Compose authority, no provider/NAS/refresh runtime,
four-stage source fixtures, raw-market SQL confinement, and removal of unreachable legacy
multi-user/local-market modules. `uv sync --frozen`, Docker contract checks, and 859 tests pass;
coverage is 91.06%.

### PR340 — Live xetra-loader V2 QA

Branch: `test/pr340-live-xetra-loader-v2`

Depends on: PR339 and upstream production V2 PASS artifact.

Git status: integrated on `main` at `e7db84f`. The static source-contract guard, the
secret-supplied live acceptance against the pinned xetra-loader production V2 artifact, and the
complete local quality gate pass (`863 passed`, `5` live-only skips in the offline gate, `91.06%`
coverage). The live gate verified the non-superuser `portfell` login only through its configured
read path: Listings, Quotes, Dividends and Splits materialize through the gateway; business-table
DML/DDL and sync-schema access are denied. No DSN or credential is recorded here.

External artifact gate: cleared on 2026-08-30. `artifacts/acceptance/postgres-full-sync-v2.json` exists on xetra-loader `main` and reports `status: PASS`.

Acceptance: verify exact loader SHA/endpoint/database; use secret-supplied non-superuser LOGIN member; SELECT exact four business tables; representative rows through gateway; market DML/DDL fails; sync access fails and counts as PASS; sanitized evidence; full gate.

### PR341 — PostgreSQL-only source E2E

Branch: `test/pr341-postgres-only-source-e2e`

Depends on: PR340.

Git status: integrated on `main` at `14d263e`. The PostgreSQL-only source E2E guard and complete
local quality gate pass (`869 passed`, `5` live-only skips, `91.06%` coverage). It locks the
two-database cold runtime, four-stage workflow fixture, gateway-only market SQL, full listing
identity, source-snapshot lineage, fail-closed partial/missing values and source immutability.

Acceptance: cold start without provider/NAS/medallion/xetra-loader Python package; full Metadata -> Uni -> Bi -> Multi; all market reads gateway-only; unavailable/empty/partial/missing-adjusted fail closed; duplicate ISIN full identity; snapshot lineage contains no provider/download/sync identity; repeated workflow leaves market tables unchanged; full gate.

### PR342 — Source cutover runbook

Branch: `docs/pr342-market-source-cutover-runbook`

Depends on: PR341.

Git status: integrated on `main` at `c70ecff`. The checked-in runbook has a navigable, staged
cutover procedure covering identity/privilege preflight, backup boundary, four-route smoke,
analytical smoke, sanitized evidence, and fail-closed rollback. The complete local quality gate
passes (`869 passed`, `5` live-only skips, `91.06%` coverage).

Scope: preflight DSNs/tables/role/UTC/read-only; back up surviving application/analytical state only; legacy market files are disposable and never migrated; smoke four routes; rollback application/config only and never reactivate provider acquisition or broader grants.

### PR343 — Source-series closeout and Dash handoff

Branch: `docs/pr343-source-series-closeout`

Depends on: PR342.

Git status: integrated on `main` at `af92ee9`. The source-series handoff freezes the current
gateway and application-service seams, persisted analytical concepts, four-page workflow,
visualization and Universe & History rules, PR264–PR295 reconciliation, and PR344 deletion seed.
The complete local quality gate passes (`869 passed`, `5` live-only skips, `91.06%` coverage).

Scope: freeze the exact merged source/runtime contracts that PR344 consumes; classify old PR264–PR295 UI/product ideas as `reuse-cleanly`, `reimplement-in-dash`, or `retire`; do **not** create a second backlog file and do not resurrect React-era architecture.

Acceptance: one checked-in handoff records exact source gateway API, application service API, persisted analytical concepts, four-page workflow, objective set (`return_risk`, `return_drawdown`, `minimum_risk`), professional plot requirements, Universe & History requirements, the Plotly visual-reference contract from section 1.6, and the deletion inventory seed used by PR344.

## 4. Plotly Dash + clean database full-replacement series — PR344–PR360 — OUTDATED

This series is mandatory. Completion of the source series does **not** make the product architecture final until PR360 passes.

Dependency graph:

```text
PR343
  |
PR344
  |
PR345 -> PR346 -> PR347
  |                 |
  +------> PR348 ---+
            |
PR349 || PR350 || PR351 || PR352
            |
          PR353
            |
          PR354
            |
          PR355(QA)
            |
      PR356 || PR357
            |
          PR358
            |
          PR359(QA)
            |
          PR360
```

### PR344 — Full-replacement inventory and frozen contract

Branch: `docs/pr344-dash-full-replacement-contract`

Priority: P0.

Depends on: PR343.

Git status: integrated on `main` at `1293eb2`. The deterministic, schema-validated and
secret-free legacy inventory, replacement contract, and normative Dash UI contract are frozen;
their focused contract test and the complete local quality gate pass (`876 passed`, `5` live-only
skips, `91.06%` coverage).

Owned paths: `BACKLOG.md`, new `docs/contracts/plotly-dash-replacement-v1.md`, new `docs/contracts/plotly-dash-ui-v1.md`, new `docs/contracts/legacy-ui-db-inventory-v1.json`, focused contract tests only. No production analytical code.

Tasks:

- inventory every production file/path belonging to the legacy browser UI;
- inventory every direct frontend dependency and Node/npm build/runtime surface;
- inventory every legacy Portfell-owned application database/schema/table/migration/repository/env var/Compose volume/service dependency;
- inventory current FastAPI routes/application-service methods used by the four stages;
- freeze exact Dash route/page IDs, callback service contracts, final DB authorities, and final negative-space rules;
- write `plotly-dash-ui-v1.md` as the normative implementation copy of section 1.6, including the external reference URL, layout tokens, responsive breakpoints, shared presentation primitives, page-frame contract, page-specific content map, and explicit non-goals;
- freeze the exact page titles/subtitles, primary action labels, KPI slots, named plots, table roles, history/evidence placement, and stage-footer behavior used by PR348–PR354;
- classify each legacy item exactly `delete-pr356`, `delete-pr357`, `retain-backend`, or `retain-test-only`.

Acceptance:

- inventory is deterministic, schema-validated, sorted, contains no secrets, and has no `unknown` disposition;
- every production React/Vite/TypeScript/TanStack/Node UI path is owned by PR356;
- every legacy Portfell DB object/adapter/migration is owned by PR357 or explicitly proven still required by the new DB contract;
- `xetra_loader` objects are explicitly excluded from deletion;
- `plotly-dash-ui-v1.md` contains no feature that is absent from this backlog and no copied reference branding/content/assets;
- reference URL is documentation-only; no code/runtime/test depends on availability of the external reference;
- no implementation code is changed;
- PR gate passes.

Security: inventory stores names only, never credentials/DSNs with passwords.

Determinism: identical tree produces byte-identical inventory.

Idempotency: rerunning inventory validation changes nothing.

### PR345 — New `portfell_dash` schema and migrations

Branch: `feat/pr345-portfell-dash-database`

Priority: P0.

Depends on: PR344.

Git status: integrated on `main` at `d9946ca`. The clean, deterministic `portfell_dash`/
`portfell` v1 migration chain, bounded runtime grants, configuration identity validation, catalog
fingerprint, and destructive-only rollback boundary are implemented. Focused migration tests and
the complete local quality gate pass (`882 passed`, `5` live-only skips, `91.06%` coverage).

Owned paths: new `src/portfell/app_state/migrations/**`, new schema contracts, focused migration/catalog tests. Do not edit legacy DB adapters.

Tasks:

- create a clean database-target migration chain for database `portfell_dash`, schema `portfell`;
- implement exact v1 tables for singleton workspace, `market_source_snapshots`, `metadata_universes`, `metadata_universe_members`, `analysis_runs`, `analysis_artifacts`, `univariate_selections`, `univariate_selection_members`, `decision_artifacts`, `ui_preferences`;
- use full listing identity `(isin, exchange, code)` in universe/selection membership;
- enforce immutable/published revision uniqueness, run-stage/status constraints, foreign keys, typed timestamps, and deterministic IDs;
- include no tenant/user/project/provider-credential/status-event/navigation-projection tables;
- extend the shared gitignored root `config.yaml` schema with `postgres.app` metadata for `portfell_dash`/`portfell`; do not introduce another local config file or raw credential storage.

Acceptance:

- empty database migrates from zero to head and back only according to documented reversible/destructive boundaries;
- catalog snapshot equals frozen DDL contract exactly;
- no migration references a legacy schema/table as an input source;
- one clean fixture supports one universe and one completed run per stage without user/project rows;
- `postgres.app` configuration matches the actual migration target and mismatch fails closed;
- migration repeat is idempotent; focused tests and PR gate pass.

Security: new login has only required privileges on `portfell`; no superuser requirement. Passwords remain secret-supplied and are never stored as raw values in tracked files or `config.example.yaml`.

Determinism: same migration head yields same catalog fingerprint.

Idempotency: migration application is repeat-safe under the migration tool contract.

### PR346 — New application-state repositories

Branch: `feat/pr346-portfell-dash-app-state-repositories`

Depends on: PR345.

Git status: integrated on `main` at `8fb3bc8`. Typed, parameterized app-state repositories now
cover immutable universe/selection memberships, stage runs, artifacts, decisions and preferences
without legacy hosted or market-SQL dependencies. Focused repository/migration tests and the
complete local quality gate pass (`887 passed`, `5` live-only skips, `90.26%` coverage).

Owned paths: new `src/portfell/app_state/**` repositories/contracts except migrations; focused tests.

Tasks: implement typed repositories for every PR345 concept; parameterized SQL only; no import from legacy hosted PostgreSQL repository modules; no market SQL.

Acceptance: create/read/list exact immutable revisions, stage-run lifecycle, selection membership, artifacts, decision artifacts, preferences; transaction rollback tests; restart tests; no user/project/tenant scope; no legacy table reference; PR gate passes.

Security: repository errors are typed/redacted; no SQL in public UI errors.

Determinism: stable ordering and canonical serialization for all list/read methods.

Idempotency: repeated insert-by-content identity converges to the same immutable row or typed conflict.

### PR347 — Application services cut over to new state DB

Branch: `refactor/pr347-app-services-portfell-dash-db`

Depends on: PR346.

Git status: integrated on `main` at `04a7f54`. The canonical four-stage service now uses only
the clean app-state port plus `MarketDataGateway`; it persists/reloads typed lineage, artifacts,
selections and Multivariate decisions without a legacy database fallback. Focused Metadata →
Univariate → Bivariate → Multivariate, fail-closed and helper-contract tests plus the complete
quality gate pass (`891 passed`, `5` live-only skips, `90.02%` coverage).

Scope: wire Metadata, Univariate, Bivariate, and Multivariate application services to the new `app_state` repositories while market reads remain through `MarketDataGateway`.

Acceptance:

- all four stages can run against an empty new `portfell_dash` DB plus external market fixture;
- no production application service imports legacy hosted DB repositories;
- snapshot lineage, exact selections, analysis results/artifacts, and Multivariate DecisionArtifact persist/reload after process restart;
- no legacy DB read/write fallback; failure of new app DB fails closed;
- focused stage regression tests and PR gate pass.

### PR348 — Plotly Dash reference shell and shared presentation primitives

Branch: `feat/pr348-plotly-dash-shell`

Depends on: PR344. May execute in parallel with PR345–PR347 but must rebase on PR347 before merge if shared composition changes.

Git status: integrated on `main` at `dd34937`. The first-party Dash application now supplies the
four-route shell, FastAPI mount, shared presentation primitives, responsive Plotly grammar and
deterministic placeholders until page plugins land. It has no SQL/legacy Web dependency; focused
Dash contract tests and the complete quality gate pass (`897 passed`, `5` live-only skips,
`90.06%` coverage).

Owned paths: new `src/portfell/dash_app/**` shell/navigation/layout/shared presentation primitives/assets, FastAPI composition mount, focused tests. Do not change analytical calculations.

Visual authority: section 1.6 and `docs/contracts/plotly-dash-ui-v1.md`. The external Plotly example is reference-only and must not be fetched at runtime.

Tasks:

- add Dash/Plotly Python dependencies only; do not add a Node/npm/Vite/TypeScript build;
- create one Dash application mounted/integrated with the production FastAPI runtime;
- register exactly four routes `/metadata`, `/univariate`, `/bivariate`, `/multivariate`; `/` redirects deterministically to `/metadata` and is not a fifth product page;
- implement the reference-style desktop shell with `220px` left sidebar, `Portfell` product header, four ordered navigation items, active-page highlight, workflow-context block, and main content region;
- implement the section 1.6 CSS tokens and responsive breakpoints in Dash static assets only;
- implement shared `PageHeader`, `ControlBar`, `KpiCard`, `ChartCard`, `TableCard`, `StatusBanner`, `HistoryCard`, and `StageFooter` primitives with stable IDs/classes and focused rendering tests;
- implement one shared Plotly figure template for font, margins, axis grid, hover formatting baseline, transparent plot area, white card surface, and responsive rendering;
- implement loading, empty, typed-error, disabled-action, and unavailable-data presentation primitives without financial logic;
- implement sidebar workflow context slots for universe/version, selected-count, snapshot short ID, and stage readiness using values supplied by typed services/state only;
- ensure callbacks call typed application-service ports, never SQL.

Acceptance:

- all four routes resolve and render the same reference-style shell with placeholder page bodies;
- navigation order is exactly Metadata -> Univariate -> Bivariate -> Multivariate;
- only the current route has accent-soft active styling;
- no `Dashboard`, `Price Performance`, `Portfolio Analysis`, `Fees & Distributions`, `Resources`, or other reference-application page is introduced;
- desktop `1440x900` shows fixed sidebar and main content with no page-level horizontal overflow;
- tablet `1024x768` and mobile `390x844` meet the frozen responsive contract using CSS/Dash only;
- one process/container topology is documented and tested;
- FastAPI health/API routes remain reachable;
- browser smoke test has zero console/page errors attributable to Portfell;
- no import from `apps/web`, no copied Plotly-reference branding/assets, and no network request to the example site;
- PR gate passes.

### PR349 — Dash Metadata page

Branch: `feat/pr349-dash-metadata-page`

Depends on: PR347 and PR348.

Git status: integrated on `main` at `f07690a`. The Dash Metadata page uses the clean typed
service contract for active listings, filter options, persisted universe history and explicit
universe creation; it preserves full listing identity and contains no provider/download action.
Focused page tests and the complete gate passed before integration (`900 passed`, `5` live-only
skips, `90.11%` coverage).

Owned paths: Dash Metadata page/callbacks and focused tests only. Reuse PR348 shared presentation primitives; do not add page-local card/navigation styling.

Frozen page title: `Metadata`.

Frozen subtitle: `Build the active Xetra instrument universe.`

Primary actions: `Reset filters`, `Create universe`, and `Continue to Univariate`. No provider fetch/download action exists.

Required layout:

- `PageHeader` with frozen title/subtitle;
- one `ControlBar` containing only metadata predicates supported by the frozen backend contract plus the two metadata actions;
- four KPI slots: `Active listings`, `Filtered listings`, `Selected listings`, `Universe version`; unavailable values render `—`, never fabricated zero;
- one `TableCard` titled `Xetra Listings` showing the exact metadata fields required by the service contract and always preserving full identity `(isin, exchange, code)`;
- one `HistoryCard` titled `Universe & History` showing persisted universe version, creation timestamp, source snapshot short ID, and member count from persisted data;
- one `StageFooter` with `Continue to Univariate`, disabled until a persisted Metadata universe is ready.

Business behavior: browse/filter the active Xetra listing universe, show exact metadata fields/counts, create a versioned Metadata universe, and hand it to Univariate.

Acceptance:

- uses active listings only for new universe construction;
- filtering semantics match the Python contract exactly;
- duplicate ISINs remain distinguishable by full identity;
- inactive historical identity can be resolved but not newly selected;
- selected/filtered/active counts are service-derived and exact;
- create-universe is idempotent for an identical content identity according to the app-state contract;
- callbacks never perform direct SQL or provider refresh;
- persisted universe reloads after restart and repopulates sidebar context/history;
- empty results keep the table/card visible with an explicit empty message, not a blank page;
- validation/loading/error/unavailable states use shared primitives and are keyboard reachable;
- mobile keeps filters stacked and table scrolling inside its card only;
- no chart or unrelated financial metric is added to Metadata merely to resemble the reference example;
- PR gate passes.

### PR350 — Dash Univariate page

Branch: `feat/pr350-dash-univariate-page`

Depends on: PR347 and PR348.

Git status: integrated on `main` at `f10a641`. The Dash Univariate page renders backend-owned
return/risk evidence, typed unavailable rows and persisted downstream selection controls through
the clean application-service contract. Dash-4-compatible selection/navigation controls are
covered by focused tests; the complete gate passed (`903 passed`, `5` live-only skips, `90.13%`
coverage).

Owned paths: Dash Univariate page/callbacks/plots/tables and focused tests. Reuse PR348 shared presentation primitives; do not duplicate global CSS.

Frozen page title: `Univariate`.

Frozen subtitle: `Inspect single-instrument return and risk statistics, then persist the downstream selection.`

Primary actions: `Compute univariate statistics`, `Save selection`, `Continue to Bivariate`.

Required layout:

- `PageHeader` with frozen title/subtitle;
- `ControlBar` containing the primary compute action and only result filters/settings supported by the frozen service contract; no UI-only analytical parameter may be invented;
- four KPI slots: `Input instruments`, `Available results`, `Selected instruments`, `Unavailable results`;
- `ChartCard` titled exactly `Univariate Return / Risk Universe` with Plotly scatter data supplied by the service/artifact contract; selected instruments are visually distinguishable and hover shows full listing identity plus the backend-provided return/risk metrics;
- `TableCard` titled `Univariate Statistics` with exact service-provided metrics and multi-row downstream selection controls;
- `HistoryCard` titled `Universe & History` showing input Metadata universe/version, run ID/status, source snapshot short ID, algorithm version, and persisted selection version/count;
- `StageFooter` with `Save selection` and `Continue to Bivariate`; downstream continuation is disabled until a valid persisted selection exists.

Business behavior: run and inspect univariate statistics for the selected Metadata universe, apply result filters, persist the exact downstream selection.

Acceptance:

- formulas/annualization/return conventions remain backend-authoritative;
- Dash callbacks do not recompute annualized return, volatility, drawdown, distribution yield, or any other financial metric solely for display;
- missing adjusted close is shown as typed unavailable evidence, never zero/raw-close fallback;
- distribution/income evidence does not alter adjusted-close return calculation;
- input/available/selected/unavailable KPI counts are exact service values or exact counts over returned immutable rows, never inferred from hidden client state;
- plot axes, units, hover values, and selected-marker semantics are explicit and deterministic;
- result filter/selection state never changes the underlying immutable run artifact;
- persisted selection reloads after restart and repopulates table selection, KPI, history, sidebar context, and readiness;
- empty/unavailable instrument rows remain explainable in the table/status region;
- mobile stacks controls/KPIs and keeps chart readable without page overflow;
- PR gate passes.

### PR351 — Dash Bivariate page

Branch: `feat/pr351-dash-bivariate-page`

Depends on: PR347 and PR348.

Git status: integrated on `main` at `92cc19a`. The Dash Bivariate page exposes typed pair
evidence, full left/right identities, unavailable pair states and the frozen continuation path
through the clean service boundary. Dash-4-compatible navigation and Plotly hover details are
covered; the complete gate passed (`906 passed`, `5` live-only skips, `90.15%` coverage).

Owned paths: Dash Bivariate page/callbacks/plots/tables and focused tests. Reuse PR348 shared presentation primitives; do not add a second pair-analysis state model.

Frozen page title: `Bivariate`.

Frozen subtitle: `Inspect pairwise diversification evidence for the persisted Univariate selection.`

Primary actions: `Compute bivariate statistics`, `Continue to Multivariate`.

Required layout:

- `PageHeader` with frozen title/subtitle;
- `ControlBar` with the primary compute action and only pair-result controls supported by the frozen service contract;
- four KPI slots: `Input instruments`, `Candidate pairs`, `Eligible pairs`, `Unavailable pairs`;
- `ChartCard` titled exactly `Bivariate Return / Diversification Universe`; the figure consumes backend/service values only and exposes full pair identity in hover/tooltips;
- `TableCard` titled `Bivariate Statistics` with both full listing identities and all contracted pair metrics/evidence needed for interpretation;
- unavailable correlation/covariance/common-calendar evidence is rendered explicitly as unavailable with reason where supplied;
- `HistoryCard` titled `Universe & History` showing upstream selection version/count, bivariate run ID/status, source snapshot short ID, algorithm version, and pair-result counts;
- `StageFooter` with `Continue to Multivariate`, disabled until the Bivariate stage is ready according to the backend contract.

Acceptance:

- consumes the exact persisted Univariate selection and never a browser-only row subset;
- common-calendar/minimum-observation/pair eligibility rules are preserved;
- candidate/eligible/unavailable counts reconcile exactly with persisted/backend evidence;
- missing covariance/correlation is unavailable, never encoded or plotted as zero;
- no same-ISIN pair where prohibited by the analytical contract;
- full listing identity is visible where ambiguity exists;
- no financial pair metric is recomputed in Dash for plotting or sorting unless the frozen service contract explicitly designates it as presentation-only transformation;
- large pair result handling is bounded, table rendering is paged/virtualized according to the chosen Dash-native component, and no page-level horizontal overflow occurs;
- run state/history/readiness survive process restart;
- PR gate passes.

### PR352 — Dash Multivariate page

Branch: `feat/pr352-dash-multivariate-page`

Depends on: PR347 and PR348.

Owned paths: Dash Multivariate page/callbacks/plots/tables and focused tests. Reuse PR348 shared presentation primitives and the shared Plotly template.

Frozen page title: `Multivariate`.

Frozen subtitle: `Optimize candidate portfolios and select the final portfolio from out-of-sample evidence.`

Frozen objectives: `return_risk` default, `return_drawdown`, `minimum_risk`.

Primary action: `Optimize portfolio`.

Required layout:

- `PageHeader` with frozen title/subtitle;
- `ControlBar` with one objective selector exposing exactly the three frozen objective values plus `Optimize portfolio`; any additional optimizer/risk-model control may appear only if it is already part of the frozen backend service contract;
- four KPI slots: `Winner OOS return`, `Winner OOS risk`, `Winner max drawdown`, `Production eligibility`; values come from the winning persisted artifact/DecisionArtifact and unavailable values render `—`/typed unavailable, never zero;
- `ChartCard` titled exactly `Portfolio Candidate OOS Return / Risk`;
- `ChartCard` titled `Cumulative Performance` using persisted backend artifact data;
- `ChartCard` titled `Drawdown` using persisted backend artifact data;
- `ChartCard` titled `Allocation` when weight artifacts exist;
- `ChartCard` titled `Risk Contribution` when risk-contribution artifacts exist;
- `TableCard` titled `Final Portfolio` showing full listing identity, final weight, and only other fields supplied by the winner artifact;
- one decision/evidence card titled `Decision` showing objective, winning candidate ID, requested method, actual method, source snapshot short ID, algorithm version, availability, production eligibility, and persisted explanation/reason fields;
- `HistoryCard` titled `Universe & History` showing upstream stage identities and Multivariate run history;
- `StageFooter` shows final readiness/eligibility but does not create a fifth workflow stage.

Acceptance:

- Multivariate is the only optimizer page/stage;
- objective selector defaults to `return_risk` and serializes exact frozen objective IDs;
- OOS ranking selects the winner; no in-sample-best substitution;
- requested and actual optimizer/risk-model method are displayed from persisted artifacts rather than guessed from controls;
- Equal Weight is never a hidden solver fallback;
- candidate OOS return/risk, performance, drawdown, allocation, risk contribution, final weights, and KPI values are rendered from backend artifacts only;
- unavailable optional Allocation/Risk Contribution cards show a shared unavailable state rather than disappearing in a way that can be mistaken for zero exposure;
- DecisionArtifact explains the winner and availability/production eligibility;
- no Dash callback reruns optimization merely because the page renders, changes tabs/cards, or resizes;
- objective changes mark prior displayed winner as stale until a matching completed run is selected/executed according to PR353 state rules;
- restart restores the completed run, winner, plots, table, decision evidence, KPI values, and history;
- mobile displays cards sequentially with responsive Plotly figures and no page-level horizontal overflow;
- PR gate passes.

### PR353 — Shared Dash callback/state/job semantics

Branch: `feat/pr353-dash-shared-state`

Depends on: PR349–PR352.

Scope: add one typed Dash state/callback layer for current universe/selection/run IDs, job progress, cancellation/retry, stale-result invalidation, cross-page handoff, navigation readiness, and sidebar context. Do not redesign page visuals owned by PR348/PR354.

Tasks:

- define one immutable browser-state DTO containing identifiers and presentation state only;
- wire sidebar current-analysis context and per-stage readiness from the same typed state source used by page footers;
- define deterministic upstream/downstream invalidation: a new Metadata universe invalidates Uni/Bi/Multi readiness; a new Univariate selection invalidates Bi/Multi readiness; a new matching Bivariate run invalidates only downstream Multi readiness as specified by the service contract;
- define one job-status presentation model for queued/running/succeeded/failed/cancelled plus optional progress supplied by the backend;
- make retry/cancel buttons appear only when supported by the backend job contract;
- ensure route changes are read-only with respect to analytical state.

Acceptance:

- no global mutable Python singleton is business authority;
- browser `dcc.Store`/client state contains identifiers/presentation state only, never full market authority, financial result tables, database credentials, or secrets;
- stale upstream revision invalidates downstream readiness deterministically and visibly in sidebar/footer/status banner;
- double-click/retry does not duplicate logical runs;
- page navigation never changes analytical state by GET/render side effect;
- one page cannot display another revision's result after rapid navigation;
- active sidebar item always follows the URL, while readiness/status icons follow persisted/service state;
- job/status polling is non-mutating and stops/reduces appropriately after terminal state;
- restart reconstructs state from persisted backend/app-state contracts rather than browser cache;
- focused concurrency/restart tests and PR gate pass.

### PR354 — Dash reference-style professional visualization and UX parity

Branch: `feat/pr354-dash-professional-visualization`

Depends on: PR353.

Scope: final shared visual/interaction layer for all four pages. Use Plotly figures and Dash components only; no React extension application. This PR aligns the implementation with the simple composition of `https://financial-dashboard-example.plotly.app/` without copying its content or adding its product features.

Owned changes: shared Dash assets/CSS, shared figure template/formatters, shared presentation primitives, and page presentation-only wiring required to apply those shared pieces. Do not change application-service semantics, analytical formulas, database contracts, or page business callbacks.

Required visual behavior:

- desktop has the reference-style white left sidebar, clear active navigation highlight, restrained product header, workflow context block, neutral application background, and white content cards;
- every page follows the frozen `PageHeader -> ControlBar -> KPI row -> primary cards -> Universe & History -> StageFooter` vertical hierarchy;
- card titles are left aligned and concise; descriptive body copy is secondary/muted;
- KPI cards contain one label, one primary value, and at most one short secondary evidence line; they are not mini dashboards;
- tables use consistent header/body spacing, sticky header when useful, explicit empty/unavailable rows, and bounded card-local overflow;
- buttons, dropdowns, checkboxes, radios, pagination, focus outlines, loading indicators, errors, and disabled states use one coherent style family;
- green/red are semantic only; normal navigation/selection uses the blue accent family;
- all plots use the shared Portfell Plotly template with explicit axis labels/units, deterministic legend placement, responsive sizing, hover labels, and no decorative 3D/gradient effects;
- positive/negative colors in plots are used only when the underlying metric semantics justify them; categorical series otherwise use the shared Plotly categorical palette;
- no page adds a banner/hero, giant logo, marketing copy, or reference-app document links.

Required named plots include at minimum:

- `Univariate Return / Risk Universe`;
- `Bivariate Return / Diversification Universe`;
- `Portfolio Candidate OOS Return / Risk`;
- `Cumulative Performance`;
- `Drawdown`;
- `Allocation` where artifacts exist;
- `Risk Contribution` where artifacts exist;
- Universe & History evidence views required by the final product contract.

Acceptance:

- deterministic visual fixtures exist for representative populated states of all four pages at `1440x900`, `1024x768`, and `390x844` without requiring the external reference site;
- desktop composition is visibly the frozen left-sidebar/card-based financial-dashboard grammar; mobile composition is a stacked adaptation, not a separate product;
- legends/axes/units/date ranges/hover labels are explicit and testable;
- text/interactive controls satisfy the repository's accessibility target, keyboard focus is visible, and color is never the sole carrier of unavailable/error/readiness meaning;
- unavailable data is shown as unavailable, not zero;
- no financial recomputation in callbacks solely for plotting;
- all plots derive from immutable backend/service artifacts;
- no copied Plotly-reference logo, wording, fund data, document links, screenshot, or asset is committed into production assets;
- the only external-reference footprint is the documentation URL/description in the UI contract;
- PR gate passes.

### PR355 — Dash four-page parity, reference-layout and browser QA

Branch: `test/pr355-dash-four-page-parity`

Depends on: PR354.

Scope: QA only. Establish the deletion gate for the old UI and old DB and prove the new UI satisfies both functional parity and the frozen reference-style simplicity contract.

Testing stack: Python `pytest` plus the repository-approved Python browser automation stack. Do not require an application npm/Node build. Browser binaries/test tooling may exist as test dependencies only if they do not restore a Node production UI boundary.

Required deterministic journeys:

- Metadata: filter -> select -> create persisted universe -> reload -> continue;
- Univariate: compute -> inspect plot/table -> select -> persist selection -> reload -> continue;
- Bivariate: compute -> inspect plot/table/unavailable evidence -> reload -> continue;
- Multivariate: choose objective -> optimize -> inspect OOS winner/KPIs/plots/final weights/DecisionArtifact -> reload;
- cross-stage invalidation: change upstream revision and prove downstream stale/readiness behavior;
- failure/retry path using typed fixture failure without exposing internals.

Reference-layout assertions at `1440x900`:

- `Portfell` header and four-item left navigation are visible;
- navigation order is exact and only current page is highlighted;
- workflow context block is present and contains only Portfell analytical context;
- page title/subtitle precede one compact control strip;
- KPI cards appear before detailed cards when the page defines KPIs;
- content cards have consistent shared classes/tokens;
- no fifth dashboard/home page or reference-app feature exists.

Responsive assertions:

- `1024x768`: two-column KPI layout where applicable, no page overflow, tables bounded to card;
- `390x844`: compact top navigation, one-column KPI/cards, stacked controls, responsive plots, table card horizontal scroll allowed, no body horizontal scroll.

Functional/security acceptance:

- deterministic real-stack journey Metadata -> Univariate -> Bivariate -> Multivariate passes;
- valid/empty/invalid/partial/unavailable/retry/restart states pass;
- exact request/callback effects and persisted new-DB state are asserted;
- no external production network access in deterministic CI fixtures, including no request to the Plotly example URL;
- no direct market/app SQL from Dash modules;
- no legacy DB reads/writes during the journey;
- no route requires `apps/web`;
- market DB is read-only and sync schema denied;
- screenshot/evidence artifacts are generated from Portfell itself and contain no external-reference screenshot or copied asset;
- `uv run portfell-quality merge` passes.

This PR produces the immutable `dash-parity-v1` evidence artifact required by PR356 and PR357. The artifact must include the three viewport screenshots for all four populated pages plus machine-readable functional/layout assertions.

### PR356 — Delete legacy React/Vite/TypeScript/TanStack/Node UI

Branch: `chore/pr356-delete-legacy-web-ui`

Depends on: PR355 PASS artifact.

Owned deletion scope: exactly every `delete-pr356` item in `legacy-ui-db-inventory-v1.json`.

Tasks:

- delete `apps/web/**`;
- delete first-party React/ReactDOM/TanStack/Vite/TypeScript/Vitest application dependencies/config;
- delete npm/pnpm/yarn lock/build scripts when no non-legacy use remains;
- delete Node Web Docker stage/container/service and old static-web proxy configuration;
- delete legacy browser contract generators/tests that exist only for React UI;
- update CI so no production frontend build is expected.

Acceptance:

- inventory check reports zero undeleted `delete-pr356` entries;
- repository has no production import/path to `apps/web`;
- no Node frontend container/build is present;
- four Dash routes still pass browser smoke and full PR gate;
- no analytical/backend code is deleted merely because old UI called it.

Rollback: revert this PR only while the old DB still exists and before PR360 destructive finalization; no dual-UI production deployment is permitted.

### PR357 — Delete legacy Portfell database plane

Branch: `chore/pr357-delete-legacy-portfell-db`

Depends on: PR355 PASS artifact.

Owned deletion scope: exactly every `delete-pr357` item in `legacy-ui-db-inventory-v1.json`.

Tasks:

- delete legacy hosted DB migrations/repositories/models for user/tenant/membership/project membership/provider credentials/navigation/workflow projections/status events/download lifecycle and any other inventory-owned legacy table;
- delete old DB bootstrap/import/repair utilities;
- delete compatibility SQL/views and old-schema feature flags;
- remove runtime code paths that can connect to the old Portfell DB;
- retain the generic PostgreSQL driver only if required by the new `app_state` and `market_source` layers.

Acceptance:

- all four stages and Dash UI operate only with clean `portfell_dash` + external `xetra_loader` fixture;
- starting with only the old DB and no new DB fails closed rather than falling back;
- legacy database/table names from the inventory have zero production references;
- no legacy migration is required on fresh install;
- new DB migration/catalog/restart/backup tests pass; full PR gate passes.

Rollback: old database backup remains offline/read-only and is not mounted into the runtime.

### PR358 — Final Compose/runtime cutover

Branch: `chore/pr358-dash-runtime-compose`

Depends on: PR356 and PR357.

Final runtime requirements:

- FastAPI + Dash application service(s);
- new Portfell `portfell_dash` PostgreSQL service/database or explicit external equivalent;
- external `PORTFELL_MARKET_DATABASE_URL` to xetra-loader;
- repository-root `config.yaml` is mounted/read as local runtime configuration, is gitignored, never baked into an image, and its `postgres.app`/`postgres.market` identities must match the effective secret-supplied connections;
- tracked `config.example.yaml` remains placeholder-only and secret-free;
- no Web/Node container;
- no old Portfell DB service/volume;
- no provider/download/refresh worker;
- no provider credentials/secrets;
- analytical worker only if still required by the frozen service contract.

Acceptance:

- cold `docker compose up` from empty new DB reaches healthy state after new migrations;
- exactly one Portfell app DB authority and one external market DB authority;
- missing/malformed/mismatched `config.yaml` fails closed with a typed/redacted error;
- market DML fails; sync access fails;
- no legacy volume is mounted;
- four Dash routes and API health pass;
- restart preserves new app-state data; PR gate passes.

### PR359 — Final negative-space and clean-install QA

Branch: `test/pr359-dash-clean-runtime-qa`

Depends on: PR358.

Scope: QA only.

Acceptance must prove all of the following:

- no first-party React/Vite/TypeScript/TanStack production UI;
- no `apps/web` production directory/reference;
- no Node production Web build/container;
- no legacy Portfell DB schema/table/migration/repository/runtime connection;
- no provider/EODHD acquisition/credential/medallion/Portfell market refresh plane;
- no `xetra_loader_sync` access/reference as a source;
- no direct SQL in Dash modules;
- market SQL only under `market_source`; app-state SQL only under `app_state`;
- root `config.yaml` is ignored by Git, absent from images/artifacts, and the tracked example contains no real connection secret;
- clean install from empty `portfell_dash` plus contract-faithful xetra fixture completes all four stages;
- deterministic browser journey and restart pass;
- the frozen section 1.6 / `plotly-dash-ui-v1.md` layout contract still passes after legacy UI deletion;
- production runtime performs no request to the visual-reference site and contains no copied reference branding/assets;
- `uv run portfell-quality pr` and `uv run portfell-quality merge` both pass.

Any production defect found here requires a separate corrective implementation PR; PR359 itself does not hide fixes.

### PR360 — Production cutover, destructive removal, rollback runbook and final acceptance

Branch: `docs/pr360-dash-production-cutover`

Depends on: PR359.

Scope: exact production transition from the transitional runtime to Plotly Dash + clean `portfell_dash` DB.

Required order:

1. record exact application/source SHAs and current runtime inventory;
2. stop writes to the legacy Portfell application DB;
3. create encrypted offline backup of the legacy DB and verify restoreability;
4. provision/migrate clean `portfell_dash`;
5. create/deploy the local gitignored `config.yaml` with non-secret `postgres.app` and `postgres.market` metadata, then configure independent secret-supplied `PORTFELL_DATABASE_URL` and `PORTFELL_MARKET_DATABASE_URL` values and verify their identity matches the YAML contract;
6. deploy FastAPI + Dash runtime;
7. run four-page smoke and one full analytical workflow;
8. verify market SELECT works, market DML/DDL fails, and `xetra_loader_sync` access fails;
9. verify new app-state restart persistence and DecisionArtifact retrieval;
10. remove old UI service/container/image references from deployment;
11. detach/delete legacy active DB service/volume/database from runtime ownership after the acceptance window defined by the runbook;
12. retain only the encrypted offline backup for the documented rollback retention period.

Final acceptance:

- production runtime serves exactly four Dash pages and no legacy UI route;
- the production pages conform to the frozen simple financial-dashboard visual contract and the reference URL remains documentation-only;
- no active old Portfell DB connection/service/volume exists;
- no first-party old frontend build/libraries are required to build or run Portfell;
- new DB and external market DB are the only production database authorities;
- production `config.yaml` is not tracked by Git and is not present in application images/artifacts; tracked `config.example.yaml` contains placeholders only;
- complete workflow succeeds after application restart;
- sanitized final evidence records image digests, schema/catalog fingerprint, market-source contract version, Git SHAs, and PASS results without secrets;
- documentation (`README.md`, `ARCHITECTURE.md`, page docs, `docs/contracts/plotly-dash-ui-v1.md`, Compose/runbook, `GATES.md`) describes only the final architecture.

Rollback: restore the last complete pre-cutover application release and the encrypted legacy DB backup only as one coordinated rollback. Never run old and new databases as simultaneous business authorities and never reactivate provider acquisition.

## 5. Product/quantitative invariants carried into Dash

These rules are not negotiable UI details:

- workflow is exactly Metadata -> Univariate -> Bivariate -> Multivariate -> final portfolio decision;
- Multivariate is the only optimizer stage/page;
- objectives are exactly `return_risk` (default), `return_drawdown`, `minimum_risk` unless a future backlog PR explicitly versions the contract;
- OOS metrics drive winner selection; in-sample best is never silently substituted;
- simple returns compound geometrically; log returns remain a separate concept;
- missing/undefined analytical values are never encoded as plausible zero;
- pairwise-calendar covariance is not presented as a coherent portfolio covariance unless the risk-model contract explicitly makes it so;
- missing covariance is never zero;
- future leakage is prohibited in walk-forward/OOS evaluation;
- production walk-forward settings are versioned and cannot silently use tiny fixture defaults;
- `requested_method` and `actual_method`, source snapshot, algorithm version, availability, and production eligibility are retained in artifacts;
- stable candidate configuration identity is required;
- long-running runs have durable ownership/idempotency and status reads are non-mutating;
- published revisions are immutable;
- Universe & History evidence remains part of the product;
- jurisdiction/tax/cost modeling remains deferred unless a later explicit backlog series implements the already-defined jurisdiction-neutral architecture. Unsupported jurisdiction/fund-tax/broker/cost inputs must never be silently assumed zero.

## 6. Final series completion gate

The architecture is considered complete only when both source and replacement series are complete and PR360 final evidence is PASS.

A clean production-like acceptance must show:

- Xetra market data comes only from external read-only `xetra_loader` business tables;
- one coherent source snapshot per analytical input assembly;
- one clean Portfell-owned `portfell_dash` DB with no legacy tenant/control-plane schema;
- exactly four Plotly Dash pages;
- all four pages follow the frozen section 1.6 / `plotly-dash-ui-v1.md` simple financial-dashboard composition with consistent navigation, controls, KPI cards, content cards, evidence/history, and responsive behavior;
- the external Plotly example is documentation/design reference only: no runtime dependency, iframe, copied branding/content/assets, or deterministic-test network dependency exists;
- no Portfell-maintained React/Vite/TypeScript/TanStack/Node frontend runtime/build;
- no old Portfell DB runtime authority;
- no provider acquisition or Portfell-owned market refresh plane;
- local PostgreSQL metadata is defined in the root `config.yaml`, which is ignored by Git and excluded from images/artifacts; only secret-free `config.example.yaml` is tracked;
- full Metadata -> Univariate -> Bivariate -> Multivariate workflow succeeds, persists, restarts, and reproduces against frozen inputs;
- exact full listing identities are preserved;
- missing adjusted close and missing analytical values fail/show unavailable correctly;
- OOS portfolio winner and DecisionArtifact are reproducible;
- clean install, restart, backup/restore, browser tests, source privilege tests, negative-space tests, PR gate, and merge gate all pass.

No item is complete because code merely exists. Completion requires its named acceptance evidence and merged dependency order.

## 7. Multivariate structural-risk analysis v2 — PR361–PR376 — OUTDATED

This is a post-cutover quantitative-analysis series. No PR in this section may start before PR360 has merged with its final acceptance evidence. The series extends only the existing Multivariate stage; it does not create a fifth page or stage and it must not reintroduce React/Vite/TypeScript/Node application code.

Hard decisions for the entire series:

- every structural statistic is derived from the exact immutable Multivariate input snapshot, its aligned daily log-return matrix, and the canonical production Ledoit-Wolf joint covariance model;
- covariance PCA answers where absolute portfolio variance sits; correlation PCA answers how many distinct co-movement patterns remain after volatility scaling; the two are persisted and named separately;
- `effective_independent_drivers` is not a v2 metric because it is currently only an alias for effective rank. V2 exposes `covariance_effective_rank`, `correlation_effective_rank`, `signal_component_count`, and candidate-level `effective_pca_risk_drivers` as distinct quantities;
- the causal-sounding `strongest_common_driver` name is retired. V2 uses `covariance_dominant_component_representative` and `correlation_dominant_component_representative`, each meaning only the listing with the largest absolute Component-1 coefficient in that PCA basis;
- the canonical v2 risk clusters use deterministic average-linkage hierarchical clustering on correlation distance. The current threshold-connected-component grouping is not a canonical v2 cluster and must not be silently retained under the same name;
- PCA, clusters, effective-rank, signal-component, rolling-stability, factor-risk, and cluster-risk outputs are diagnostics only throughout PR361–PR376. They must not alter candidate weights, the three frozen objectives, candidate feasibility, OOS ranking, or the DecisionArtifact winner;
- Hierarchical Risk Parity keeps its own optimizer-internal clustering contract. Risk-Structure clusters must never be substituted into HRP without a later explicit optimizer-contract PR;
- all optional diagnostics fail closed with typed availability reasons. Unavailable structure is never represented as zero and does not silently fall back to sample covariance, pairwise covariance, or a weaker clustering rule;
- all expensive structural calculations are server-owned, immutable and persisted. Dash renders persisted/service values only and performs no financial recomputation;
- every rolling, bootstrap and walk-forward calculation is time-safe. Test-period observations may not influence a training-period covariance model, PCA basis, cluster assignment, or structural metric;
- no composite `Structural Diversification Score` is authorized by this series. Primitive diagnostics remain visible separately until independent OOS evidence justifies any later composite or optimizer objective.

Frozen v2 parameters unless a later versioned backlog PR changes them:

- explained-variance thresholds: `0.80`, `0.90`, `0.95`;
- canonical cluster correlation cut: `0.70`, represented in correlation-distance space as `sqrt((1 - 0.70) / 2)`;
- signal-component parallel analysis: `100` null replicates, RNG `numpy.random.Generator(numpy.random.PCG64(41))`, rank-wise `0.95` null quantile with NumPy quantile method `higher`;
- rolling structure: exactly `252` aligned daily observations per window, `21`-observation stride, at most `24` most-recent windows, always including the latest aligned date;
- PCA subspace comparison: top `min(3, listing_count)` components;
- cluster stability bootstrap: `100` circular moving-block replicates, block length `21`, RNG `numpy.random.Generator(numpy.random.PCG64(41))`.

Dependency graph:

```text
PR360 -> PR361 -> PR362
PR362 -> PR363
PR362 -> PR364 -> PR365
PR363 -> PR366
PR363 -> PR367 -> PR368
PR363 + PR367 -> PR369 -> PR370
PR367 -> PR371
PR365 + PR366 + PR368 + PR370 + PR371 -> PR372
PR372 -> PR373 || PR374 || PR375
PR373 + PR374 + PR375 -> PR376(QA)
```

### PR361 — Freeze Multivariate Structure v2 quantitative contract

Branch: `docs/pr361-multivariate-structure-v2-contract`

Depends on: PR360.

Owned paths: `BACKLOG.md`, new `docs/contracts/multivariate-structure-v2.md`, focused contract-schema/documentation tests only. No production analytical code.

Scope:

- freeze artifact names, field names, formulas in implementation-neutral code notation, availability reasons, deterministic ordering, numerical tolerances, frozen parameters, and the exact hand-offs used by PR362–PR376;
- define universe artifact `multivariate.structure@v2` and candidate artifact `multivariate.candidate_structure@v1`;
- define covariance-PCA, correlation-PCA, effective-rank, signal-component, hierarchical-cluster, rolling, subspace-stability, bootstrap-stability, candidate PCA-risk and candidate cluster-risk schemas;
- explicitly retire v2 use of `effective_independent_drivers` and `strongest_common_driver` without rewriting immutable v1 artifacts;
- state that v1 artifacts remain historical data only; new production runs switch to v2 only when PR372 lands.

Acceptance:

- every output field has one exact mathematical/statistical definition, unit, availability rule and deterministic ordering rule;
- `effective_rank` is frozen as `exp(-sum(p_i * log(p_i)))` over strictly positive normalized eigenvalue shares;
- candidate PCA variance contribution is frozen as `eigenvalue_k * (eigenvector_k dot weights)^2` and must reconcile to portfolio variance;
- candidate effective PCA risk drivers are frozen as entropy effective count over normalized non-negative PCA variance contributions;
- hierarchical cluster distance, average-linkage rule, cut threshold and label ordering are fully specified;
- rolling-window endpoints, bootstrap sampling, parallel-analysis RNG/replicate count/quantile method and subspace-overlap definition are fully specified;
- no production code changes and no winner/objective change occur;
- contract validation and PR gate pass.

### PR362 — Extract deterministic spectral-analysis core

Branch: `refactor/pr362-multivariate-spectral-core`

Depends on: PR361.

Owned paths: one pure Multivariate spectral-analysis module, minimal adapter changes in the current structure module, and focused unit/property tests. No service, persistence, UI, candidate or optimizer changes.

Scope: extract the current symmetric eigensystem, deterministic component ordering/sign normalization, explained variance, cumulative explained variance, threshold component counts and entropy effective rank into one reusable pure module.

Acceptance:

- existing covariance-PCA fixtures produce the same sorted eigenvalues, explained variance, cumulative variance, effective rank and component coefficients within `rel_tol=1e-9`, `abs_tol=1e-12`;
- eigenpairs are ordered by descending eigenvalue with deterministic stable tie handling;
- sign normalization is deterministic and repeated identical input is byte-identical after canonical serialization;
- only numerical eigenvalues in `[-1e-12, 0)` may be clipped to zero; values below `-1e-12` produce typed spectral-unavailable evidence rather than silent repair;
- threshold counts for `0.80`, `0.90`, `0.95` are exact and regression-tested;
- no risk-model estimator, return series, candidate weight, ranking or persistence behavior changes;
- focused tests and PR gate pass.

### PR363 — Add correlation PCA beside covariance PCA

Branch: `feat/pr363-correlation-pca`

Depends on: PR362.

Owned paths: Multivariate structure/spectral modules and focused tests only.

Scope: derive one correlation matrix from the canonical Ledoit-Wolf covariance matrix and run the PR362 spectral core on it, while retaining covariance PCA as a separate result.

Acceptance:

- correlation is derived only as `covariance_ij / sqrt(variance_i * variance_j)` from the canonical risk-model artifact; raw pairwise Bivariate covariance/correlation is never substituted;
- every positive-variance diagonal equals `1.0` within `abs_tol=1e-12`;
- any non-finite or non-positive diagonal variance makes correlation PCA unavailable with a typed reason while covariance PCA may remain available;
- a computed correlation outside `[-1, 1]` by no more than `1e-12` may be clipped to the boundary; a larger violation is typed unavailable rather than repaired;
- persist separate correlation eigenvalues, explained/cumulative variance, `correlation_effective_rank`, `components_for_80pct`, `components_for_90pct`, `components_for_95pct`, component coefficients and `correlation_dominant_component_representative`;
- covariance fields remain separately named and `covariance_dominant_component_representative` replaces the causal-sounding v1 label for new artifacts;
- no candidate/optimizer/result-ranking behavior changes;
- focused tests and PR gate pass.

### PR364 — Candidate PCA variance-contribution decomposition

Branch: `feat/pr364-candidate-pca-risk`

Depends on: PR362.

Owned paths: new pure candidate structural-risk module plus focused tests. No candidate solver changes.

Scope: project each feasible candidate weight vector onto the covariance-PCA basis and persist per-component portfolio-variance contributions.

Acceptance:

- listing order is taken from the same canonical risk-model/PCA artifact and every candidate weight is matched by full `(isin, exchange, code)` identity;
- for component `k`, contribution is exactly `eigenvalue_k * (eigenvector_k dot weights)^2`;
- the sum of component contributions matches `weights^T * covariance * weights` using `math.isclose(rel_tol=1e-9, abs_tol=1e-12)`;
- contributions below zero only within numerical tolerance `[-1e-12, 0)` are clipped to zero; a lower value is typed unavailable;
- output rows contain exact `candidate_id`, `method`, `component_id`, contribution, percent portfolio variance and source structure/risk-model identity;
- unavailable or infeasible candidates remain unavailable and do not receive fabricated zero contributions;
- candidate weights, solver execution, candidate metrics and OOS ranking are unchanged;
- focused analytical fixtures and PR gate pass.

### PR365 — Candidate effective PCA risk-driver diagnostics

Branch: `feat/pr365-candidate-effective-risk-drivers`

Depends on: PR364.

Owned paths: candidate structural-risk module/DTOs and focused tests only.

Scope: derive candidate-level structural concentration diagnostics from PR364 contributions; do not create a new optimizer objective.

Acceptance:

- normalize strictly non-negative component contributions by total candidate variance into shares `q_k`;
- `effective_pca_risk_drivers` equals `exp(-sum(q_k * log(q_k)))` over positive shares;
- `largest_pca_risk_share` equals the maximum normalized component contribution;
- candidate `components_for_80pct_risk`, `components_for_90pct_risk`, and `components_for_95pct_risk` use descending component risk contributions and deterministic ties;
- zero/non-finite portfolio variance produces typed unavailable fields rather than `0`, `1`, or `NaN`;
- an exact one-factor fixture yields effective count `1`; an exact equal-`k` contribution fixture yields effective count `k` within `rel_tol=1e-9`, `abs_tol=1e-12`;
- for every available candidate, effective count is in `[1, positive_component_count]` within tolerance and largest share is in `(0, 1]`;
- no value from this PR enters candidate feasibility, solver weights, OOS scorecards or DecisionArtifact ranking;
- focused tests and PR gate pass.

### PR366 — Deterministic signal-component parallel analysis

Branch: `feat/pr366-signal-component-analysis`

Depends on: PR363.

Owned paths: one pure signal-component module, Multivariate structure adapter and focused tests. No UI or optimizer changes.

Scope: estimate how many leading correlation-PCA components exceed a deterministic cross-sectional-noise null instead of relabeling effective rank as an independent-driver count.

Acceptance:

- input is the exact aligned daily log-return matrix pinned by the Multivariate snapshot;
- run exactly `100` null replicates with `numpy.random.Generator(numpy.random.PCG64(41))`;
- within each replicate, independently permute the observation order of each asset column without replacement, preserving every column's observed values/count while breaking synchronous cross-asset dependence;
- each null replicate re-estimates the production Ledoit-Wolf covariance, derives correlation and computes sorted correlation-PCA eigenvalues through the same production spectral contract;
- for each eigenvalue rank, use the rank-wise `0.95` empirical null quantile with NumPy method `higher`;
- `signal_component_count` is the number of **contiguous leading** observed correlation-PCA eigenvalues that strictly exceed their rank-wise null thresholds, stopping at the first non-exceedance;
- persist the observed eigenvalues, rank-wise null thresholds, replicate count, seed, quantile/method and stable input identity required to reproduce the result;
- identical input yields byte-identical output; reordered input rows with the same canonical matrix yield the same result;
- no future observations, candidate weights or OOS test rows enter the computation;
- no `effective_independent_drivers` alias is reintroduced;
- focused deterministic fixtures and PR gate pass.

### PR367 — Canonical average-linkage hierarchical risk clusters

Branch: `feat/pr367-hierarchical-risk-clusters`

Depends on: PR363.

Owned paths: new pure cluster module, structure adapter and focused tests. HRP implementation is explicitly out of scope.

Scope: replace the v2 canonical threshold-connected-component grouping with deterministic average-linkage hierarchical clustering based on the canonical Ledoit-Wolf correlation matrix.

Acceptance:

- pair distance is exactly `sqrt((1 - correlation_ij) / 2)` after the PR363 correlation-validity rules are satisfied;
- inter-cluster distance is the arithmetic mean of all cross-cluster pair distances (average linkage), never single linkage;
- the dendrogram is cut at distance `sqrt((1 - 0.70) / 2)`;
- merge ties are resolved deterministically from sorted full listing identities and final cluster labels are assigned by the lexicographically smallest member identity, producing stable `Cluster 1..N` labels;
- a chaining fixture with correlations `A-B=0.75`, `B-C=0.75`, `A-C=0.20` does not collapse all three names into one cluster merely because two edges exceed `0.70`;
- `largest_redundancy_warning` remains the maximum valid pair correlation with deterministic tie handling;
- zero/non-finite variance or invalid correlation yields typed cluster unavailability, never an implicit correlation of zero;
- the old connected-component algorithm is not exposed as the canonical v2 cluster result;
- HRP weights/linkage are unchanged and do not consume this structure artifact;
- focused fixtures and PR gate pass.

### PR368 — Candidate cluster-risk attribution

Branch: `feat/pr368-cluster-risk-attribution`

Depends on: PR367.

Owned paths: new pure candidate cluster-risk module and focused tests only.

Scope: aggregate existing asset-level candidate variance contributions into the canonical PR367 clusters without changing candidate weights.

Acceptance:

- cluster membership comes only from the immutable v2 structure artifact for the same risk-model identity;
- signed cluster variance contribution equals the sum of member asset variance contributions `weight_i * (covariance * weights)_i`;
- signed cluster contributions sum to total portfolio variance using `math.isclose(rel_tol=1e-9, abs_tol=1e-12)`;
- `cluster_percent_variance_contribution` is signed and the available cluster percentages sum to `1.0` within the same tolerance; negative contributions remain visible and are not clipped away;
- `cluster_gross_abs_risk_share` equals the cluster sum of absolute member variance contributions divided by the portfolio sum of absolute member variance contributions and sums to `1.0` when the denominator is positive;
- persist candidate ID, method, cluster ID, member count, signed contribution, signed percent, gross-absolute share and source identities;
- unavailable candidate/cluster/risk-model inputs yield typed unavailable evidence rather than zero rows;
- no cluster cap, rebalance rule, candidate ranking or optimizer objective is introduced;
- focused fixtures and PR gate pass.

### PR369 — Rolling structural diagnostics

Branch: `feat/pr369-rolling-structure-diagnostics`

Depends on: PR363 and PR367.

Owned paths: one pure rolling-structure module plus focused tests. No persistence/UI changes yet.

Scope: show whether the universe's covariance/correlation structure is stable through time by refitting the production risk model on deterministic trailing windows.

Acceptance:

- use exactly `252` aligned daily log-return observations per window, stride exactly `21` observations, maximum `24` windows;
- the most recent window always ends on the latest aligned date; earlier endpoints move backward by exactly `21` aligned observations and output is then sorted chronologically;
- every window re-estimates Ledoit-Wolf from only its own 252 rows and recomputes covariance PCA, correlation PCA and PR367 clusters;
- each row contains window start/end, observation count, covariance dominant-component share, correlation dominant-component share, covariance effective rank, correlation effective rank and risk-cluster count;
- parallel analysis and bootstrap cluster stability are **not** rerun inside each rolling window in this PR;
- fewer than `252` aligned observations yields typed `rolling_structure_insufficient_history`, not a shorter silent window;
- no row at time `t` uses any observation after its window end;
- repeated identical input yields identical windows/values and stable identity;
- focused boundary/leakage fixtures and PR gate pass.

### PR370 — PCA leading-subspace stability

Branch: `feat/pr370-pca-subspace-stability`

Depends on: PR369.

Owned paths: one pure subspace-stability module plus focused tests only.

Scope: compare adjacent rolling PCA **subspaces**, not raw loading-by-loading differences that are unstable under sign changes or rotations of near-degenerate components.

Acceptance:

- for each adjacent rolling pair, set `k = min(3, listing_count)` and use the first `k` orthonormal component vectors;
- compute stability exactly as `squared_frobenius_norm(previous_basis^T * current_basis) / k` separately for covariance PCA and correlation PCA;
- available stability is bounded in `[0, 1]` within `1e-12` numerical tolerance;
- identical subspaces yield `1.0` within tolerance even if component signs are flipped;
- rotating the basis inside the same `k`-dimensional subspace leaves the score unchanged within tolerance;
- an exactly orthogonal subspace fixture yields `0.0` when dimensionality permits;
- fewer than two valid rolling windows yields typed unavailable stability;
- no individual component is labeled stable/unstable from raw coefficient difference alone;
- focused invariance tests and PR gate pass.

### PR371 — Deterministic bootstrap cluster stability

Branch: `feat/pr371-cluster-bootstrap-stability`

Depends on: PR367.

Owned paths: one pure cluster-stability module plus focused tests. No UI/optimizer changes.

Scope: quantify whether canonical cluster relationships survive resampling of the aligned return history.

Acceptance:

- use exactly `100` circular moving-block bootstrap replicates, block length exactly `21`, with `numpy.random.Generator(numpy.random.PCG64(41))`;
- every replicate contains exactly the original aligned observation count by concatenating randomly selected circular contiguous blocks and truncating only the final block to exact length;
- each replicate re-estimates Ledoit-Wolf, derives correlation and reruns the exact PR367 average-linkage cluster contract;
- for every listing pair, `co_cluster_probability` equals same-cluster replicate count divided by `100` and is in `[0, 1]`;
- for each canonical non-singleton cluster, persist mean and minimum within-cluster pair co-cluster probability; singleton clusters report typed/not-applicable stability rather than fabricated `1.0`;
- identical duplicate-series fixtures co-cluster with probability `1.0` under deterministic resampling;
- output includes seed, block length, replicate count, source structure/risk-model identity and canonical pair ordering;
- bootstrap output is byte-identical for identical input and does not alter canonical cluster membership;
- focused deterministic tests and PR gate pass.

### PR372 — Persist and serve immutable Structure v2 artifacts

Branch: `feat/pr372-structure-v2-persistence`

Depends on: PR365, PR366, PR368, PR370 and PR371.

Owned paths: Multivariate application-service orchestration, `app_state` artifact serialization/repository adapters for these new artifact types, typed API/service DTOs and focused restart/idempotency tests. Dash presentation is out of scope.

Scope: integrate the pure computations into new production Multivariate runs and make the complete results immutable/readable after restart.

Acceptance:

- new completed Multivariate runs persist exactly one `multivariate.structure@v2` universe artifact and one `multivariate.candidate_structure@v1` artifact for the matching run when base inputs are available;
- universe artifact identity includes the input snapshot/risk-model identity, structure contract version and all frozen parameter values that can change output;
- candidate artifact identity includes the exact candidate-set identity plus the matching structure-v2 identity;
- static covariance PCA may remain available when an optional correlation/signal/rolling/bootstrap diagnostic is unavailable; every optional sub-artifact carries its own typed availability reasons rather than making the whole run silently fail;
- base risk-model unavailability propagates explicitly and no sample/pairwise covariance fallback is used;
- v1 artifacts are never mutated/re-written in place; v2 publication is a new immutable artifact revision;
- read/list API/service calls return persisted values and do not recompute PCA, clusters, bootstraps or candidate structural risk;
- restart reloads byte-equivalent canonical payloads and stable IDs;
- existing candidate weights, objective selection, OOS ranking and DecisionArtifact winner are identical to a pre-v2 regression fixture;
- focused persistence/restart/idempotency tests and PR gate pass.

### PR373 — Dash universe Risk Structure presentation

Branch: `feat/pr373-dash-universe-risk-structure`

Depends on: PR372.

Owned paths: Dash Multivariate page presentation/callback read paths, synchronized `docs/ui`/Dash contract docs and focused browser/component tests. No backend financial calculations.

Scope: expose universe-level v2 structural evidence inside the existing `/multivariate` page without changing its optimizer controls or top winner KPIs.

Required presentation:

- `ChartCard` titled exactly `PCA Spectrum` showing persisted covariance-PCA and correlation-PCA explained variance by component with an explicit selector/legend distinguishing the two bases;
- `TableCard` titled `Structural Diversification` showing listing count, covariance effective rank, correlation effective rank, signal component count, covariance/correlation dominant-component shares, component counts for `80%/90%/95%`, and risk-cluster count;
- `TableCard` titled `Risk Clusters` showing every full listing identity, canonical cluster ID, and available cluster-stability evidence;
- `ChartCard` titled `Structural Stability` showing persisted rolling effective ranks/dominant-component shares and adjacent-window subspace-stability series, with explicit date windows;
- typed unavailable reasons remain visible for signal, rolling, subspace or bootstrap evidence independently.

Acceptance:

- no fifth page/tab-stage is introduced; all content is part of existing Multivariate;
- no Dash callback computes covariance, correlation, eigenvalues, effective rank, clusters, bootstrap probability or rolling metrics;
- UI labels distinguish covariance PCA from correlation PCA everywhere;
- the retired terms `effective_independent_drivers` and causal `strongest_common_driver` do not appear in v2 UI copy;
- full listing identity is visible wherever cluster membership could be ambiguous;
- plot/table ordering is deterministic from persisted artifact order and unavailable is never rendered as numerical zero;
- `1440x900`, `1024x768`, and `390x844` fixtures have no page-level horizontal overflow;
- page render/navigation never starts a Multivariate recomputation;
- focused browser tests and PR gate pass.

### PR374 — Dash candidate structural-risk presentation

Branch: `feat/pr374-dash-candidate-structural-risk`

Depends on: PR372.

Owned paths: Dash Multivariate candidate-structure cards/read callbacks, synchronized page docs and focused browser tests only.

Scope: compare how the already-computed candidate portfolios concentrate risk across PCA components and canonical clusters. Presentation choices do not alter analytical artifacts.

Required presentation:

- `TableCard` titled `Candidate Structural Risk` with candidate ID/method, effective PCA risk drivers, largest PCA risk share, components for `80%/90%/95%` of candidate variance, and largest cluster gross-absolute risk share;
- one presentation-only candidate selector populated from persisted candidate IDs; default to the persisted winning candidate when one exists, otherwise the first available candidate in deterministic service order;
- `ChartCard` titled `PCA Risk Contribution` showing persisted per-component percent portfolio variance for the selected candidate;
- `ChartCard` titled `Cluster Risk Contribution` showing both signed cluster percent variance contribution and gross-absolute risk share without suppressing negative signed contributions;
- candidate selector state may be a UI preference but must never mutate the analysis run, candidate set or DecisionArtifact.

Acceptance:

- all values come from `multivariate.candidate_structure@v1`; Dash performs only formatting/selection of already-persisted rows;
- changing the selected candidate does not invoke any optimizer, covariance fit, PCA, cluster computation or persistence write except optional presentation preference;
- signed negative cluster contributions remain visibly signed and are not converted to zero/absolute values;
- candidate unavailable reasons are shown explicitly and do not remove the candidate silently;
- existing winner KPIs, objective selector and Decision card remain unchanged;
- responsive/browser fixtures and PR gate pass.

### PR375 — Leakage-safe structural walk-forward evidence

Branch: `feat/pr375-structural-walk-forward-evidence`

Depends on: PR372.

Owned paths: Multivariate validation/evidence modules, immutable evidence artifact serialization and focused leakage/numerical tests. No Dash and no winner-selection changes.

Scope: determine whether candidate structural diversification measured **ex ante** is associated with subsequent OOS robustness, without yet converting that evidence into an optimizer objective or score.

Acceptance:

- reuse the production walk-forward split calendar and candidate refit contract; do not create a second incompatible split schedule;
- for every completed split, fit Ledoit-Wolf/PCA/clusters using training rows only and compute each refitted candidate's training-period `effective_pca_risk_drivers`, `largest_pca_risk_share`, and largest cluster gross-absolute risk share before the test window is evaluated;
- every persisted row records `split_id`, candidate ID/method, train start/end, test start/end, structural metric values, and the already-defined OOS post-cost return, volatility, CVaR and max drawdown for that exact test window;
- `train_end < test_start` is asserted for every row and a deliberate future-row injection fixture must fail the test;
- no test return, OOS covariance or future cluster assignment can influence training-period structural metrics or weights;
- evidence rows are immutable, deterministically ordered and linked to exact risk-model/candidate/structure algorithm versions;
- this PR does not aggregate the primitive metrics into a proprietary score and does not change the production candidate scorecard or DecisionArtifact winner;
- independent numerical QA fixtures do not call the production structural helper they are verifying;
- focused leakage/numerical tests and PR gate pass.

### PR376 — Structural-risk v2 integration QA and future-candidate decision gate

Branch: `test/pr376-structural-risk-v2-qa`

Depends on: PR373, PR374 and PR375.

Scope: QA/evidence only. Production defects found here require separate corrective implementation PRs.

Acceptance must prove all of the following:

- independent numerical fixtures verify covariance PCA, correlation PCA, entropy effective rank, candidate PCA variance reconciliation, candidate effective driver count, average-linkage clustering, signed/gross cluster attribution and subspace overlap without reusing the production implementation as the oracle;
- parallel-analysis output is deterministic for the frozen `100`/seed-`41`/`0.95`/`higher` contract and changes when the synchronous cross-asset structure in the fixture is materially changed;
- bootstrap co-cluster probabilities are deterministic and duplicate-series pair stability equals `1.0` in the exact fixture;
- rolling windows are exactly `252` observations, stride `21`, maximum `24`, latest-date anchored, and contain no future observations;
- structural walk-forward evidence proves train/test separation for every split and leaves the pre-v2 OOS winner unchanged on a frozen regression fixture;
- persistence/restart reproduces both v2 artifacts and the structural walk-forward evidence byte-equivalently from immutable IDs;
- Dash universe/candidate Risk Structure views render persisted populated, unavailable and mixed-availability states at `1440x900`, `1024x768`, and `390x844` with no browser-side financial recomputation;
- scans prove no `effective_independent_drivers` or causal `strongest_common_driver` label is emitted by v2 service/UI paths and no v2 risk cluster is consumed by HRP;
- `uv run portfell-quality pr` and `uv run portfell-quality merge` pass;
- produce one immutable sanitized `structural-risk-v2` PASS evidence artifact containing exact Git SHA, contract/algorithm versions, frozen parameters, test counts and deterministic fixture fingerprints without market credentials or private data.

Future optimizer gate: PR376 does **not** authorize or implement a structurally diversified portfolio candidate. Any later `Factor Diversified`, `Cluster Balanced`, structural constraint, or composite structural score requires a new versioned backlog PR after the PR375/PR376 OOS evidence has been reviewed. The new PR must state the exact optimization objective/constraints and demonstrate that it is evaluated through the existing leakage-safe OOS selection framework before it can affect the DecisionArtifact.

## 8. Structural-risk v2 corrective production closeout — PR377–PR382 — OUTDATED

Audit date: 2026-08-31.

This corrective series is mandatory because a repository audit after PR361–PR375 found that several pure Structure-v2 components exist on `main`, but the normal production Multivariate orchestration, persisted artifact assembly and live Dash page are not yet equivalent to the acceptance contract written in PR372–PR375. This section is authoritative over Section 7 wherever the earlier text could be read as declaring Structure v2 production-complete merely because the component PRs merged.

PR376 remains useful as an independent QA harness and defect-discovery branch, but it is **not** the final Structure-v2 PASS gate while any PR377–PR380 acceptance item is open. The final immutable `structural-risk-v2` PASS artifact is owned by PR381. No structural metric may affect candidate weights, feasibility, the three frozen objectives, OOS scorecards or the DecisionArtifact winner anywhere in PR377–PR382.

Observed corrective targets that must be closed, not waived:

- the production `compute_multivariate()` path must publish Structure-v2 artifacts rather than only the pre-v2 structure document;
- `subspace_stability` must contain the persisted PR370 result rather than an adapter-pending placeholder;
- candidate structure must persist `largest_cluster_gross_abs_risk_share` as a first-class field rather than force Dash to derive it;
- structural walk-forward evidence must be produced from the same production refit/split execution and persisted/reloaded with the run;
- the existing PR373/PR374 presentation helpers must be wired into the real `/multivariate` page and service read path, not remain presenter prestaging;
- runtime documentation must match the actual Compose bind behavior and open QA metadata must not claim already-resolved blockers;
- the final gate needs coverage headroom above the hard 90% floor so small follow-up changes do not immediately make the merge line brittle.

Dependency graph:

```text
PR375 -----------------------> PR377 -> PR378 -> PR379 ----+
PR376(QA harness/findings) -------------------------------+--> PR381(QA/PASS) -> PR382
PR378 -------------------------------> PR380(docs/runtime) +
```

PR377 and PR376 may proceed independently from the current merged main line. PR379 must not merge before PR378 proves that the artifacts it renders are production-persisted. PR381 is the only final Structure-v2 PASS authority after this corrective series.

### PR377 — Complete Structure-v2 artifact assembly

Branch: `fix/pr377-structure-v2-artifact-completeness`

Priority: P0.

Depends on: PR375 merged implementation. PR376 findings may add tests but are not a blocking implementation dependency.

Owned paths: `src/portfell/multivariate_structure_artifacts.py`, the minimal rolling/subspace adapter needed to expose PR370 results, candidate-structure serialization, and focused deterministic tests. No application-service orchestration, database repository, Dash or optimizer changes.

Scope:

- replace the `subspace_stability_adapter_pending` placeholder with the actual persisted adjacent-window covariance/correlation leading-subspace stability produced under the PR370 contract;
- add `largest_cluster_gross_abs_risk_share` to every candidate structure row as an explicit persisted primitive derived from that candidate's already-computed cluster rows;
- keep per-cluster signed and gross contributions unchanged and retain their full detail;
- ensure all availability reasons remain local to their diagnostic and no optional diagnostic makes available covariance PCA disappear;
- keep the artifact contract/version semantics explicit: if adding either field changes a frozen payload schema in a non-backward-compatible way, version the affected artifact rather than silently changing meaning under an immutable identifier.

Acceptance:

- `subspace_stability.items` contains one deterministic row for every adjacent pair of valid rolling windows, with previous/current window endpoints, component count `k`, covariance overlap and correlation overlap, each in `[0, 1]` within `1e-12` tolerance;
- the subspace rows are generated from the same rolling PCA bases whose window metrics are persisted in `rolling_structure`, never from a separately shifted calendar;
- fewer than two valid rolling windows produces the exact typed unavailable reason defined by the v2 contract and an empty item list, never a fabricated zero/one;
- `largest_cluster_gross_abs_risk_share` equals `max(cluster_gross_abs_risk_share)` over that candidate's available canonical cluster rows and is `None` with explicit availability reason when the denominator/cluster evidence is unavailable;
- a one-cluster available fixture yields exactly `1.0`; a multi-cluster fixture reconciles the stored maximum to the persisted row values with `rel_tol=1e-9`, `abs_tol=1e-12`;
- candidate structure still persists `effective_pca_risk_drivers`, `largest_pca_risk_share`, component counts and full PCA/cluster contribution rows unchanged;
- artifact IDs are stable for byte-equivalent inputs and include every frozen parameter that can change the new output;
- no candidate weight, solver method, objective score, OOS rank or DecisionArtifact field changes on a frozen regression fixture;
- no HRP code imports or consumes v2 risk-cluster memberships;
- focused numerical/serialization tests and `uv run portfell-quality pr` pass.

### PR378 — Wire Structure v2 and structural walk-forward into the production Multivariate run

Branch: `fix/pr378-structure-v2-production-orchestration`

Priority: P0.

Depends on: PR377.

Git status: integrated on `main` at `109b491`. The production Multivariate path now publishes
immutable Structure-v2, candidate-structure, and structural walk-forward artifacts from the
same risk-model, refit, and validation execution used by the existing decision path.

Owned paths: `src/portfell/app_services/multivariate_compute.py`, the clean `app_state` artifact persistence/read adapters if required, typed service DTOs, and focused persistence/restart/idempotency tests. Dash presentation is out of scope.

Scope:

- make the normal `compute_multivariate()` execution call the canonical Structure-v2 document assembler using the exact production risk model, aligned return rows and already-built candidate set;
- call structural walk-forward evidence generation using the **same** production `refitted_candidate_sets` and `validation_splits` that feed OOS scorecards; no second candidate refit or split calendar is allowed;
- persist the universe Structure-v2 artifact, candidate Structure artifact and structural walk-forward evidence as immutable analysis artifacts for the same Multivariate run;
- make service reads and restart recovery return persisted payloads only; read/render operations must never trigger PCA, clustering, bootstrap or walk-forward recomputation;
- stop treating the pre-v2 `structure` document as the canonical structure artifact for new runs. Historical v1 artifacts remain readable/immutable but are never mutated into v2.

Acceptance:

- one successful production Multivariate run with sufficient data persists exactly one canonical `multivariate.structure@v2` artifact, exactly one matching candidate-structure artifact, and exactly one structural-walk-forward artifact/document containing all completed split/candidate rows;
- all three artifacts carry the exact run/input-snapshot/risk-model/candidate identities required to prove they belong to the same analytical revision;
- the structural walk-forward row count exactly reconciles to completed production validation splits and candidate identities; there are no orphan, duplicate or second-calendar rows;
- every structural walk-forward row satisfies `train_end < test_start`; deliberate future-row injection fails closed with the typed leakage error before persistence;
- the production winner ID, requested/actual method, objective score, scorecards, candidate weights and DecisionArtifact document are byte-equivalent to a frozen pre-integration fixture except for the addition of diagnostic artifacts outside the decision document;
- optional correlation/signal/rolling/subspace/bootstrap unavailability does not fail an otherwise valid Multivariate run and is persisted as typed diagnostic unavailability; base risk-model failure remains fail-closed with no covariance fallback;
- after a real app-state process/database restart, service reads return byte-equivalent canonical Structure-v2, candidate-structure and structural-walk-forward payloads with the same IDs;
- repeated execution of the same logical run converges to the same immutable artifact identities according to the existing idempotency contract and creates no duplicate published artifacts;
- direct scans prove no v2 structural computation is executed by read/list service methods;
- focused integration/restart tests and `uv run portfell-quality pr` pass; the branch must also pass the complete `uv run portfell-quality merge` before it is considered merge-ready.

### PR379 — Wire live Structure-v2 evidence into `/multivariate`

Branch: `fix/pr379-dash-structure-v2-live-wiring`

Priority: P0.

Depends on: PR378 and the already-merged PR373/PR374 presentation adapters.

Git status: integrated on `main` at `4b2956d`. The Multivariate page reads the persisted
Structure-v2 and candidate-structure artifacts through the existing presentation adapters.

Owned paths: `src/portfell/dash_app/pages/multivariate.py`, narrowly required Dash presenter/callback/read wiring, shared presentation components only when unavoidable, and focused component/browser tests. No financial-analysis modules, optimizer or persistence writes.

Scope:

- make `multivariate_page_data()` request and consume the persisted production Structure-v2 and candidate-structure artifacts from the run detail/service contract;
- integrate the existing universe/candidate presenter logic into the real page rather than leaving it as unused/prestaged helpers;
- render the PR373 universe cards and PR374 candidate cards on the existing Multivariate page while preserving the current objective controls, winner KPIs, OOS plots, Decision card, Final Portfolio and History sections;
- candidate selection is presentation-only and defaults to the persisted winning candidate when present, otherwise deterministic first available candidate.

Acceptance:

- a populated production run renders `PCA Spectrum`, `Structural Diversification`, `Risk Clusters`, `Structural Stability`, `Candidate Structural Risk`, `PCA Risk Contribution`, and `Cluster Risk Contribution` from persisted artifacts on `/multivariate`;
- the page does not derive `largest_cluster_gross_abs_risk_share`; it displays the persisted PR377 field;
- covariance and correlation PCA are visibly distinguished in labels, legends and tables; retired `effective_independent_drivers` and causal `strongest_common_driver` wording is absent;
- signed negative cluster percent-variance contributions remain negative in data/hover/table presentation while gross-absolute shares remain separately labelled;
- mixed availability is local: unavailable signal/rolling/subspace/bootstrap/candidate evidence shows its persisted reason while unrelated available cards remain populated;
- changing candidate selection performs no optimizer call, covariance fit, PCA, clustering, bootstrap, analysis-artifact write or DecisionArtifact mutation;
- page render, reload, navigation and responsive resize are read-only with respect to analytical state and do not start a new Multivariate run;
- reload after application restart restores the same structural cards from app-state persistence;
- deterministic browser fixtures pass at `1440x900`, `1024x768`, and `390x844`, with no body-level horizontal overflow and no Portfell console/page errors;
- browser/runtime request inspection proves no direct SQL from Dash and no request to the external visual-reference site;
- focused component/browser tests and `uv run portfell-quality pr` pass.

### PR380 — Reconcile runtime documentation and Structural-v2 QA governance

Branch: `docs/pr380-runtime-structure-v2-reconciliation`

Priority: P1.

Depends on: PR378. May run in parallel with PR379.

Owned paths: `README.md`, `DOCKER.md`, `ARCHITECTURE.md`, `GATES.md` only if wording requires synchronization, `docs/runbooks/dash-production-cutover.md`, relevant structural-risk contract/status documentation, and backlog status text. No production runtime or analytical code.

Scope:

- reconcile documented HTTP bind behavior with the actually intended production Compose contract after the public-bind change;
- update Structural-v2 status text so merged component PRs are not described as production-complete until PR378/PR379/PR381 evidence exists;
- remove stale statements that PR360, NumPy declaration, PR370 or other already-resolved prerequisites are still blockers;
- document the PR376/PR381 distinction: PR376 is independent QA harness/defect discovery; PR381 owns final PASS after corrective implementation.

Acceptance:

- README, Docker/runbook and Compose descriptions agree on one exact default bind contract. If `compose.yaml` remains `0.0.0.0:${PORTFELL_PORT:-8080}:8000`, no authoritative document claims loopback-only `127.0.0.1:8080` by default; if the intended security contract is changed back to loopback, the runtime change must be a separate implementation PR and this documentation PR follows the merged runtime truth;
- all documented service/database authorities still match FastAPI + Dash, `portfell_dash`, and external read-only `xetra_loader`; no legacy/provider plane is reintroduced;
- Structural-v2 documentation names the actual persisted artifacts/read paths created by PR378 and the live `/multivariate` views created by PR379;
- open PR376 metadata/body is refreshed before it is marked ready for review so it does not claim resolved blockers and does not claim ownership of the final PASS artifact; if connector permissions cannot update PR metadata, the exact required text change is recorded as a blocking manual acceptance item rather than silently ignored;
- no credentials, complete credential-bearing DSNs or private market data enter documentation/evidence;
- documentation contract tests, link/negative-space scans and `uv run portfell-quality pr` pass.

### PR381 — Final Structural-risk v2 production integration QA and PASS artifact

Branch: `test/pr381-structural-risk-v2-production-closeout`

Priority: P0 final gate.

Depends on: PR379 and PR380. Reuses the independent PR376 fixtures where valid but must execute against the post-corrective production path.

Scope: QA/evidence only. No production financial calculations or hidden corrective implementation are allowed in this PR. Any production defect discovered here requires a separate implementation PR and a fresh PR381 run.

Acceptance must prove all of the following on the exact PR381 head SHA:

- independent numerical fixtures verify covariance PCA, correlation PCA, entropy effective rank, candidate PCA variance reconciliation/effective driver count, deterministic average-linkage clusters, signed/gross cluster attribution, rolling window boundaries, subspace overlap, parallel analysis and bootstrap stability without using the production function under test as the numerical oracle;
- a production `compute_multivariate()` invocation, not a direct helper-only fixture, emits the canonical Structure-v2, candidate-structure and structural-walk-forward artifacts and persists them through the real application-state boundary;
- canonical Structure-v2 contains real subspace-stability rows when history permits and never contains `subspace_stability_adapter_pending` in an available production fixture;
- every available candidate row contains the persisted `largest_cluster_gross_abs_risk_share`, and it reconciles to its cluster rows;
- structural walk-forward evidence uses the exact production split/refit identities, contains no future observations and leaves the frozen pre-v2 winner/DecisionArtifact unchanged;
- database/application restart reproduces all three artifact payloads byte-equivalently with stable IDs and no structural recomputation during reads;
- browser QA uses persisted production artifacts and proves all PR379 universe/candidate cards for populated, unavailable and mixed-availability cases at `1440x900`, `1024x768`, and `390x844`;
- candidate selection and all page render/navigation/reload paths are analytically read-only;
- negative-space scans prove no v2 risk cluster is consumed by HRP, no retired v2 labels are emitted, no Dash SQL exists, and no structural metric enters candidate feasibility, objectives, scorecards or DecisionArtifact ranking;
- README/runtime documentation matches the actual bind topology and contains no stale finality/blocker statement;
- `uv run portfell-quality pr`, `uv run portfell-quality merge`, and the GitHub `merge-gate` all execute successfully for the exact head; skipped, cancelled or zero-step jobs are not PASS;
- produce exactly one immutable sanitized `structural-risk-v2` PASS evidence artifact containing exact 40-hex Git SHA, contract/algorithm versions, frozen parameters, executed test counts, database restart evidence references, browser evidence references and deterministic fixture fingerprints without secrets/private market rows;
- the PASS assembler refuses PASS when any required executed check/evidence reference is absent, belongs to another SHA, is malformed, or reports unavailable/failed status where the contract requires success.

Only after PR381 PASS may a later backlog proposal use PR375/PR381 evidence to justify a new structural optimizer candidate/constraint/score. PR381 itself authorizes none.

### PR382 — Restore quality-gate coverage headroom

Branch: `test/pr382-coverage-headroom`

Priority: P2 hardening.

Depends on: PR381 PASS.

Scope: tests/coverage hardening only. Keep the repository's contractual failure threshold at 90%; create operational headroom by covering meaningful production branches rather than weakening exclusions or deleting code for coverage optics.

Acceptance:

- the same combined unit + integration coverage aggregation used by GitHub `merge-gate` reports at least **92.0%** total statement coverage on the PR382 head;
- no `# pragma: no cover`, coverage omit rule, source exclusion, generated-code reclassification or test deletion is added solely to improve the percentage;
- added tests target real low-covered production behavior with priority on `app_state` persistence/error paths, application-service orchestration and Dash callback/state behavior introduced or exercised by PR377–PR381;
- deterministic failure/unavailable/idempotency/restart branches are covered rather than only happy-path line execution;
- browser tests are added only when browser behavior is the actual uncovered contract; do not inflate browser runtime for pure unit branches;
- all tests remain deterministic and do not depend on the live external market host or external visual-reference site;
- `uv run portfell-quality pr`, `uv run portfell-quality merge`, and GitHub `merge-gate` pass with the unchanged 90% hard threshold and measured aggregate coverage `>=92.0%`;
- GATES.md continues to state 90% as the mandatory floor unless a later explicit governance PR changes that policy.

## 9. Responsive staged-analysis execution and instant read plane — PR383–PR396 — OUTDATED

Audit date: 2026-08-31.

This series makes analytical computation explicitly asynchronous from browser rendering and turns
the four Dash pages into bounded persisted read views. It is a performance/interaction series only:
Univariate/Bivariate/Multivariate formulas, source-snapshot semantics, the three Multivariate
objectives, OOS winner selection and Structure-v2 financial meaning remain unchanged.

The required workflow is deliberately split at the only point where user choice exists:

```text
Metadata predicates
  |
  v
[Create universe & compute Univariate]
  |
  +--> immutable Metadata universe U
  +--> queued/running Univariate job over every member of U
          |
          v
      immutable Univariate result UNI
          |
          +--> read-only filter preview; no analytical recomputation
          |
          v
      [Apply selection & compute downstream]
          |
          +--> immutable Selection S
          +--> Bivariate job B(S)
                    |
                    v
               Multivariate job M(S, B, return_risk)
```

Hard decisions for PR383–PR396:

- Univariate is computed once for the complete persisted Metadata universe and exact market snapshot.
  Moving result filters never reruns Univariate.
- Filter edits are preview-only. They may change preview counts/table/chart data but do not create a
  `selection_id`, Bivariate run, Multivariate run or analytical artifact.
- `Apply selection & compute downstream` is the only v1 filter-commit action. It persists the exact
  filtered full-identity membership and queues Bivariate; successful Bivariate completion
  automatically queues Multivariate with the frozen default objective `return_risk`.
- Alternate Multivariate objectives remain explicit user actions on `/multivariate`; they are not
  silently run for every filter preview.
- A page render, route change, resize, status poll, table-page change, chart interaction or filter
  preview is read-only with respect to analytical computation.
- Calculation progress is backend-owned persisted job state. A progress percentage means completed
  logical work units, not elapsed-time percentage or ETA.
- Univariate work units are processed universe members; Bivariate work units are planned candidate
  pairs. Multivariate uses the frozen logical phases `inputs`, `risk_model_and_candidates`,
  `walk_forward_validation`, `scorecards`, `structural_diagnostics`, `decision`,
  `artifact_persistence`, `complete`; phase progress is explicitly labelled as logical phase
  progress, not remaining-time estimation.
- No synthetic combined Bivariate+Multivariate percentage is displayed. While downstream analysis is
  active, the UI shows the Bivariate and Multivariate stage states separately.
- The current API/Dash container remains the only Portfell application runtime. This series may use a
  bounded in-process executor owned by the API process, but must not add Redis, Celery, RQ, a new
  Compose worker service, Node, or a second application authority.
- Queued/running job state is durable in `portfell_dash`. Process restart reclaims stale work
  idempotently; completed analysis runs and artifacts remain immutable.
- Current Univariate/Bivariate row results are stored in a bounded row-addressable artifact form.
  Page reads never deserialize a complete large JSON array merely to return the first page.
- Browser state contains identifiers, small summaries, filter presentation state and progress only;
  it never contains complete market history, complete analytical tables or financial authority.
- While a new selection revision computes, the last completed downstream revision may remain visible
  only when clearly labelled `Previous selection`; values from old and new revisions must never be
  combined in one KPI/chart/table/Decision view.
- Normal Dash page code must not call the heavyweight all-artifacts `run_detail()` path. That method
  may remain for bounded diagnostic/API use, but page read paths use explicit summaries, artifact
  reads and paged rows.
- Frozen presentation caps for this series are `100` table rows per page, `500` Univariate chart
  points and `1000` Bivariate chart points. Pagination/filtering happens server-side or within the
  bounded application read plane; the browser is never given all Bivariate pairs.
- Performance QA uses deterministic local PostgreSQL/Dash fixtures, never the live market database,
  and records both latency and structural evidence such as query count, returned-row count and
  response size so timing cannot hide an unbounded implementation.

Dependency graph:

```text
PR382
  |
PR383
  |
PR384 -----> PR385
  |           |
  +-----> PR386
              |
            PR387
              |
            PR388
              |
            PR389
              |
            PR390
              |
        PR391 -> PR392
              \   /
               PR393
                 |
              PR394(QA baseline)
                 |
              PR395(performance optimization)
                 |
              PR396(QA/PASS)
```

### PR383 — Freeze staged execution, progress and read-plane contract

Branch: `docs/pr383-staged-analysis-read-plane-contract`

Priority: P0.

Depends on: PR382.

Owned paths: `BACKLOG.md`, new
`docs/contracts/staged-analysis-read-plane-v1.md`, focused contract/documentation tests only. No
production code.

Scope: freeze the exact job state machine, progress semantics, two user commit actions, immutable
revision graph, paged-result contract, page read APIs, stale/previous-result behavior and measurable
performance budgets consumed by PR384–PR396.

Acceptance:

- the contract contains the exact workflow and hard decisions from Section 9 and does not authorize a
  third computation trigger;
- job status is exactly `queued`, `running`, `succeeded`, `failed`, `cancelled`;
- every job status payload contains `job_id`, `stage`, `status`, `input_ref`, optional `run_id`,
  `progress_current`, `progress_total`, `progress_phase`, `attempt`, `failure_code`, timestamps and
  enough revision identity to reject cross-selection display;
- `progress_current/progress_total` is defined only when total is known, satisfies
  `0 <= current <= total`, and is monotone within one execution attempt; restart may create a new
  attempt and must expose that attempt number rather than pretending progress never restarted;
- Univariate and Bivariate progress units and all eight Multivariate logical phases are frozen exactly
  as listed in Section 9;
- exact primary labels are frozen as `Create universe & compute Univariate` on Metadata and
  `Apply selection & compute downstream` on Univariate;
- the filter-preview contract explicitly states that preview requests are read-only and create no
  selection/run/job/artifact;
- the downstream commit contract states `Selection -> Bivariate -> Multivariate(return_risk)` and
  states that Multivariate is queued only after matching Bivariate success;
- paged row reads freeze default/max page sizes `100/500`, chart caps `500` Univariate and `1000`
  Bivariate, stable ordering and exact full listing identities;
- page render contracts explicitly prohibit `run_detail()`/market-gateway/financial-compute calls;
- target performance budgets used by PR394/PR396 are frozen: warm page-content p95 `<=750 ms`,
  warm filter-preview p95 `<=400 ms`, warm status-read p95 `<=200 ms`, and page-specific JSON/Dash
  callback response bodies `<=512 KiB` on the deterministic performance fixture;
- active-computation navigation has a separate p95 budget `<=1000 ms`;
- contract tests verify terminology, exact action labels, state transitions, caps and negative-space
  rules; `uv run portfell-quality pr` passes.

### PR384 — Durable analysis-job and progress persistence

Branch: `feat/pr384-analysis-job-progress-state`

Priority: P0.

Depends on: PR383.

Owned paths: `src/portfell/app_state/migrations/**`, `src/portfell/app_state/schema.py`,
`src/portfell/app_state/contracts.py`, `src/portfell/app_state/repository.py`, focused migration/
repository tests. No Dash, market-source or financial-calculation changes.

Scope: add a durable `analysis_jobs` control record for non-blocking stage requests without changing
the immutable identity of `analysis_runs`.

Acceptance:

- one new migration adds `portfell.analysis_jobs` without rewriting v1 analysis runs/artifacts;
- each job stores exactly workspace `default`, `job_id`, stage in
  `univariate|bivariate|multivariate`, `input_ref`, nullable requested objective, status, nullable
  linked `run_id`, progress current/total/phase, execution attempt, heartbeat, failure code and
  created/started/completed timestamps;
- queued jobs can exist before a market snapshot/run ID is known; a linked `run_id` is written only
  after the worker creates/reuses the exact source-pinned analysis run;
- a partial unique index prevents two simultaneous queued/running logical jobs for the same
  `(stage, input_ref, requested_objective)` while permitting a later terminal rerun;
- `create_or_get_active_job()` is atomic under two concurrent callers and returns one active job;
- `claim_job()` changes exactly one queued/stale job to running and increments `attempt`; a second
  claimant cannot own the same live lease;
- progress updates reject negative totals, `current > total`, missing phase, terminal jobs and
  decreasing current values within the same attempt;
- `heartbeat_at`/lease expiry support deterministic stale-job reclamation after process restart
  without mutating completed analysis artifacts;
- terminal `succeeded` requires a linked succeeded `analysis_run`; `failed` requires a typed
  `failure_code`; `cancelled` never fabricates a run result;
- terminal job rows cannot be reset to running; rerun creates/reuses a new job identity under the
  frozen request contract;
- list/read methods are stably ordered, parameterized and redacted on failure;
- exact indexes support active-job lookup, stage/status polling and recent-job history;
- fresh migration, upgrade from v1, rollback boundary, concurrent claim, stale reclaim, terminal
  immutability and restart tests pass;
- no market SQL or Dash import enters `app_state`; `uv run portfell-quality pr` passes.

### PR385 — Row-addressable immutable analytical artifacts

Branch: `feat/pr385-paged-analysis-artifact-items`

Priority: P0.

Depends on: PR383. May execute in parallel with PR384.

Owned paths: `src/portfell/app_state/migrations/**`, schema/contracts/repository support for artifact
items, focused persistence/pagination tests. No calculation or Dash changes.

Scope: provide an immutable row-addressable storage form for large Univariate/Bivariate result
artifacts so the read plane never has to fetch one giant JSON array.

Acceptance:

- one migration adds `portfell.analysis_artifact_items` keyed by
  `(artifact_id, ordinal)` with immutable FK ownership by `analysis_artifacts`;
- an item stores deterministic `ordinal`, optional non-empty `item_key` and one JSON object; arrays,
  scalars and null item documents are rejected;
- artifact header/document remains a small canonical manifest containing artifact schema/version,
  `storage = "row_items"`, exact `item_count` and summary metadata; new row-backed artifacts do not
  duplicate the complete item array in the header JSONB;
- header plus item rows publish in one app-state transaction: partial item publication is rolled back;
- item writes use batches of at most `500` rows per repository operation;
- repeated publication with identical content identity converges to the existing immutable artifact;
  any differing header/item content for the same immutable identity fails with typed conflict;
- read API supports stable `offset >= 0` and `1 <= limit <= 500`, defaults to `100`, and never
  returns more than requested;
- count and one-page reads do not select/deserialise all item documents;
- index/EXPLAIN fixtures prove a page read is constrained by artifact identity plus ordinal range;
- historical inline JSON artifacts remain immutable/readable through historical diagnostic paths,
  but new production Univariate/Bivariate runs introduced by this series use row-backed artifact
  versions and page code has no inline fallback for those new versions;
- restart yields byte-equivalent manifests/items and stable order;
- mutation/delete attempts against published item rows fail;
- migration/repository/pagination/idempotency tests and `uv run portfell-quality pr` pass.

### PR386 — Non-blocking in-process analysis executor and restart recovery

Branch: `feat/pr386-nonblocking-analysis-executor`

Priority: P0.

Depends on: PR384 and PR385.

Owned paths: new `src/portfell/app_services/analysis_executor.py` or equivalently narrow execution
module, `src/portfell/app_services/research.py` orchestration seam, FastAPI runtime lifecycle wiring,
focused concurrency/restart tests. No Dash page work and no financial-formula changes.

Scope: submit durable jobs immediately and execute them off the Dash/FastAPI request path inside the
existing API runtime.

Acceptance:

- `start_univariate_job`, `start_bivariate_job` and `start_multivariate_job` persist/reuse a queued
  job and return its small DTO without reading full market history or performing financial compute
  on the caller thread;
- the existing API container owns exactly one top-level analytical job executor; no new Compose
  service, Redis, Celery, RQ, Node process or external queue is introduced;
- the executor claims jobs through PR384 repository semantics and creates/reuses the existing exact
  source-pinned analysis run only after worker-side market materialization;
- if the exact analysis run already succeeded for the current source snapshot, the job links it and
  succeeds without recomputation;
- double-click/two concurrent submitters converge to one active logical job;
- a failed worker records only a typed public failure code; traceback/SQL/DSN/credential detail is
  not persisted or returned to Dash;
- process shutdown stops accepting new work cleanly; startup scans only queued/stale jobs and
  idempotently reclaims them;
- restart during market materialization or computation may restart that job attempt from its
  immutable inputs but cannot create duplicate completed artifacts or DecisionArtifacts;
- status/read calls never execute a job or touch the market gateway;
- executor saturation never blocks submission/status reads waiting for an available compute slot;
- existing synchronous calculation helpers remain directly testable and numerically unchanged;
- focused double-submit, stale-lease, shutdown/startup, failure and exact-run-reuse tests pass;
- `uv run portfell-quality pr` passes.

### PR387 — Decouple Dash route rendering from polling and add shared progress presentation

Branch: `refactor/pr387-dash-progress-read-shell`

Priority: P0.

Depends on: PR386.

Owned paths: `src/portfell/dash_app/app.py`, `shell.py`, `callbacks.py`, `state.py`,
`components.py`, shared Dash CSS/assets and focused Dash tests. No page-specific analytics.

Scope: stop rebuilding an entire page whenever job/browser state changes and add one shared progress
presentation used by the analytical pages.

Acceptance:

- `pf-route-content` full-page rendering is triggered by pathname/navigation only; `pf-browser-state`
  or job polling is not an Input that rebuilds the complete current page;
- one small identifier/presentation store carries current universe/selection/run/job IDs and
  readiness only;
- active job polling reads PR384 job state only and never calls `run_detail()`, the market gateway or
  a computation method;
- polling interval is exactly `1000 ms` while a current job is queued/running and is disabled after
  terminal state;
- shared progress presentation renders stage, status, phase, `current / total` and percentage when
  total is known, and an indeterminate bar with phase/status text when it is not;
- progress is accessible with semantic label/value text; color is not the sole carrier of state;
- terminal success renders 100% only when the persisted job reports completed logical work;
- failed/cancelled status retains typed reason/status and never shows a false 100% success;
- route changes during a running job complete without waiting for the worker and do not mutate the
  job;
- staying on one route receives progress updates without replacing the full page subtree or losing
  control/filter state;
- browser state reconstructs from persisted workflow/job state after reload/restart;
- focused callback tests prove no compute call from route/status callbacks and no full page
  re-render from polling;
- responsive component tests and `uv run portfell-quality pr` pass.

### PR388 — Metadata one-click Universe-to-Univariate kickoff with exact progress

Branch: `feat/pr388-metadata-univariate-kickoff`

Priority: P0.

Depends on: PR387.

Owned paths: Metadata page/callback, Univariate compute orchestration/progress adapter, row-backed
Univariate publication, focused service/Dash tests. No Univariate filtering yet.

Scope: replace the manual Create-universe then Compute-univariate sequence with one Metadata commit
action that creates/reuses the universe and immediately queues full-universe Univariate analysis.

Acceptance:

- Metadata primary action label is exactly `Create universe & compute Univariate`; the separate
  `Compute univariate statistics` button is removed from normal Univariate flow;
- one click first creates/reuses the exact filtered Metadata universe, then submits exactly one
  Univariate job for that universe and returns control to the browser without waiting for market
  history or calculation;
- repeated identical clicks while the job is active return the same active job and do not create
  duplicate universe versions/runs/artifacts;
- Univariate computation receives every persisted member of the chosen Metadata universe; no
  Univariate result filter or browser-visible subset can reduce compute input;
- worker phase begins `loading_market_data` with an indeterminate bar until the source snapshot is
  materialized, then `progress_total` equals exact universe member count;
- the existing Univariate `on_progress` callback reports processed members and is coalesced to
  monotone persisted progress; succeeded job finishes at exact member count;
- new production Univariate results publish as row-backed artifact type
  `univariate.rows@v2` with exact item count and small manifest;
- every row preserves `(isin, exchange, code)`, availability reason and the existing backend
  financial metrics without formula/annualization changes;
- missing adjusted close remains typed unavailable exactly as before;
- `/univariate` is immediately navigable while the job is queued/running and shows shell, universe
  context and progress without waiting for rows;
- once the job succeeds, Univariate data regions refresh from persisted result reads without a
  whole-route rebuild;
- process restart during Univariate work recovers the job and cannot publish duplicate v2 artifacts;
- focused full-universe, progress, double-click, restart and formula-regression tests plus
  `uv run portfell-quality pr` pass.

### PR389 — Fast Univariate read plane, filter preview and explicit selection commit

Branch: `feat/pr389-univariate-filter-read-plane`

Priority: P0.

Depends on: PR388.

Owned paths: Univariate application-service read methods, row-item repository filter/read helpers if
needed, Univariate Dash page/callbacks and focused tests. No Bivariate/Multivariate compute changes.

Scope: make filtering a fast read-only operation over persisted `univariate.rows@v2` and make the
selection boundary explicit.

Acceptance:

- Univariate page reads use explicit `univariate_summary`, `univariate_page` and
  `univariate_chart_sample` service contracts; page code does not call all-artifact `run_detail()`;
- initial READY load returns summary, at most `100` table rows and at most `500` deterministic chart
  points; it never returns all Univariate rows to the browser;
- v1 result filters are exact persisted metrics: minimum `annualized_return`, maximum
  `annualized_volatility`, minimum `max_drawdown`, minimum `sharpe_ratio` and minimum
  `sortino_ratio`; omitted filters impose no predicate;
- only rows with `availability_reason == "ok"` can enter a downstream selection; unavailable rows
  remain countable/explainable but cannot be silently selected;
- filter preview returns exact matching count, unavailable count, candidate Bivariate pair count,
  `downstream_runnable` against the existing `DEFAULT_MAX_PAIR_COUNT`, the first requested page and
  bounded chart sample;
- preview filtering uses persisted Univariate values only and performs zero market reads, zero
  Univariate calculations and zero selection/run/job/artifact writes;
- changing a filter marks the preview `Unapplied`; the previously persisted selection remains
  authoritative until the user commits;
- range/control updates use Dash `mouseup`/equivalent non-chatty semantics so dragging does not
  create a server request for every pixel movement;
- primary commit label is exactly `Apply selection & compute downstream`;
- pressing Apply creates/reuses an immutable selection from the exact current persisted
  Univariate run plus normalized predicates; no browser-only unchecked/hidden row list is accepted
  as authority;
- empty previews and pair plans above the existing Bivariate cap disable Apply with a typed,
  human-readable reason; they never create a zero-member/known-unrunnable selection;
- persisted predicate ordering and selection membership are deterministic; duplicate ISINs remain
  distinct by full listing identity;
- reload restores the persisted selection but not an unapplied transient preview as business
  authority;
- focused filtering/preview/no-side-effect/pagination/selection-idempotency tests and
  `uv run portfell-quality pr` pass.

### PR390 — Selection-triggered Bivariate-to-Multivariate pipeline

Branch: `feat/pr390-selection-downstream-pipeline`

Priority: P0.

Depends on: PR389.

Owned paths: application-service job orchestration/chaining, job state/read DTOs and focused pipeline
tests. No Bivariate/Multivariate page presentation and no financial formulas.

Scope: make one committed Univariate selection launch the complete downstream calculation chain.

Acceptance:

- successful `Apply selection & compute downstream` submits/reuses exactly one Bivariate job whose
  `input_ref` is the persisted selection ID;
- no Bivariate job is submitted for an unapplied preview, empty selection or pair plan rejected by
  the existing Bivariate runnable contract;
- matching Bivariate success submits/reuses exactly one Multivariate job with the same selection ID,
  the exact succeeded Bivariate run ID and objective exactly `return_risk`;
- Multivariate is never started before matching Bivariate `succeeded`;
- Bivariate `failed|cancelled` leaves Multivariate not-started and exposes a typed downstream blocked
  state;
- a newer selection does not mutate/cancel/relabel artifacts from an older completed selection;
- rapid S1 -> S2 commits cannot cause B(S1) to feed M(S2) or vice versa; every chain checks exact
  selection/run dependencies before submit;
- repeated callbacks/polls/restart recovery are idempotent and cannot enqueue duplicate logical
  downstream jobs;
- a process restart after Bivariate success but before Multivariate submit reconstructs the chain
  and submits/reuses the missing matching Multivariate job exactly once;
- alternate user-selected Multivariate objectives remain explicit independent jobs and are not
  automatically fanned out by this pipeline;
- no page render/status read causes pipeline advancement except the server-owned job completion
  orchestration;
- focused race, restart, failure, double-submit and exact-dependency tests plus
  `uv run portfell-quality pr` pass.

### PR391 — Bivariate progress, paged read plane and bounded chart/table rendering

Branch: `feat/pr391-bivariate-progress-read-plane`

Priority: P0.

Depends on: PR390 and PR385.

Owned paths: Bivariate progress adapter/publication/read service, Bivariate Dash page/callbacks and
focused tests. No Multivariate code or Bivariate formula changes.

Scope: expose exact pair progress and make `/bivariate` independent of Bivariate result cardinality.

Acceptance:

- Bivariate `progress_total` equals the exact planned candidate-pair count for the committed
  selection and `progress_current` uses the existing Bivariate `on_progress(current, total)` path;
- progress remains monotone within an attempt and job success requires `current == total`;
- new production pair results publish as row-backed `bivariate.rows@v2`; complete pair arrays are
  not stored in the manifest or browser state;
- Bivariate page uses explicit `bivariate_summary`, `bivariate_page` and
  `bivariate_chart_sample` reads and never normal-page `run_detail()`;
- QUEUED/RUNNING page load returns only selection identity/count, candidate-pair count, job status
  and progress; it does not request pair rows that do not yet exist;
- READY table reads at most `100` rows per requested page with deterministic ordering;
- Bivariate chart contains at most `1000` deterministic persisted/sample points and preserves both
  full listing identities in hover;
- no Dash callback builds a Plotly trace from the complete pair artifact or creates one HTML table
  row per complete pair set;
- candidate/eligible/unavailable counts reconcile to the persisted manifest and existing analytical
  pair rules;
- missing correlation/covariance remains unavailable, never zero;
- pagination/chart/status changes perform zero market reads, pair calculations or artifact writes;
- restart reloads manifest, page rows, chart sample and progress/final status from app-state;
- focused exact-progress, 100001-pair fixture, pagination, bounded-render, restart and numerical
  regression tests plus `uv run portfell-quality pr` pass.

### PR392 — Multivariate phase progress and lightweight artifact-specific read plane

Branch: `feat/pr392-multivariate-progress-read-plane`

Priority: P0.

Depends on: PR390 and PR387.

Owned paths: Multivariate computation progress callbacks/adapters, application-service artifact
specific reads, Multivariate Dash page read callbacks and focused tests. No objective/formula/winner
changes.

Scope: report meaningful logical phase progress while preventing `/multivariate` from hydrating all
artifacts on every render/status update.

Acceptance:

- production Multivariate execution emits the eight frozen phases in exact order and never reports a
  later phase before an earlier phase completes;
- persisted phase progress uses `progress_total = 8`, current `0..8`, and UI copy states explicitly
  that this is logical phase progress, not ETA;
- final `complete` phase/current `8` is written only after all required artifacts and
  DecisionArtifact persist successfully;
- a failure records the last completed/current phase plus typed failure and never advances to 8;
- instrumentation changes no candidate weights, risk model, walk-forward split, scorecard, OOS
  ranking, Structure-v2 artifact values or DecisionArtifact winner on frozen regression fixtures;
- `/multivariate` reads a small summary first and requests only the named artifacts needed by each
  visible card/figure/table; normal page code does not call the all-artifacts `run_detail()` method;
- structural cluster/candidate tables that can scale with instrument count are paged at `100` rows
  rather than fully rendered;
- QUEUED/RUNNING page shows exact selection/Bivariate dependency, objective and phase progress while
  keeping prior completed revision clearly separate;
- status polling cannot cause optimization, PCA, clustering, bootstrap, persistence or market reads;
- objective change still marks the displayed decision stale until a matching completed explicit
  objective run exists;
- restart restores the same phase/final artifacts and Decision view without recomputation on read;
- focused phase-order/failure/regression/artifact-read/pagination/restart tests and
  `uv run portfell-quality pr` pass.

### PR393 — Revision-safe previous-result handoff across all analytical pages

Branch: `feat/pr393-revision-safe-page-handoff`

Priority: P1.

Depends on: PR391 and PR392.

Owned paths: Dash identifier/presentation state, page status/summary callbacks and focused
cross-revision browser/service tests only. No calculation or persistence-schema changes.

Scope: keep pages useful while a newer revision calculates without ever mixing old and new evidence.

Acceptance:

- browser/service state distinguishes `current_input_revision`, `current_job`, `current_ready_run`
  and optional `previous_ready_run`; no generic latest-run lookup may substitute for an exact
  dependency;
- after a new Metadata universe commit, old Univariate/Bivariate/Multivariate results may be shown
  only in a visibly labelled `Previous universe` region until matching new results exist;
- after a new Univariate selection commit, old Bivariate/Multivariate evidence may be shown only as
  `Previous selection`; current KPIs/status use the new selection and never old values;
- when a matching new run succeeds, displayed current data switches atomically by run ID; a callback
  cannot combine a new summary with an old table/chart/Decision artifact;
- rapid navigation and out-of-order poll responses are rejected when their revision/run ID does not
  match current browser state;
- previous-result visibility is presentation-only and creates no copies or mutated analytical
  artifacts;
- EMPTY, COMPUTING, READY, FAILED and PREVIOUS states all have explicit deterministic UI copy;
- previous data remains inspectable after restart from persisted immutable IDs;
- cross-revision race tests prove S1/B1/M1 and S2/B2/M2 never cross-wire;
- browser fixtures at all three frozen viewports have no page-level overflow or state flicker that
  removes the shell;
- `uv run portfell-quality pr` passes.

### PR394 — Staged-analysis correctness and performance baseline QA

Branch: `test/pr394-staged-analysis-performance-baseline`

Priority: P0 QA gate.

Depends on: PR393.

Scope: QA/evidence only. Production defects or tuning changes are forbidden in this PR and must be
implemented by PR395 or a separately named corrective PR.

Deterministic fixture sizes:

- Metadata/Univariate: `5,000` full-identity listings with persisted Univariate rows;
- filtered selection: exactly `400` runnable listings;
- Bivariate persisted read fixture: at least `100,000` pair rows;
- Multivariate fixture: completed winner/Decision plus Structure-v2 tables large enough to require
  pagination;
- one controllable long-running job fixture that advances progress without sleeping on live market
  I/O.

Acceptance:

- full browser journey proves Metadata one-click -> full-universe Univariate -> preview-only
  filtering -> Apply -> Bivariate -> automatic `return_risk` Multivariate;
- exact job status/progress is monotone for Univariate/Bivariate and phase-ordered for Multivariate;
- filter preview causes zero analytical writes and zero computation invocations under request spy;
- page render/navigation/reload/status polling causes zero market reads and zero analytical compute
  calls;
- DB query tracing proves normal page reads do not invoke all-artifacts `run_detail()` and no
  Bivariate page query/deserialization returns all `100,000+` pair rows;
- response tracing proves table pages contain `<=100` rows, Univariate charts `<=500` points,
  Bivariate charts `<=1000` points and callback response bodies `<=512 KiB`;
- restart in queued/running Univariate, running Bivariate and Bivariate-succeeded-before-Multivariate
  handoff states recovers idempotently with no duplicate terminal artifacts;
- revision-race fixture proves previous/current labelling and no S1/S2 cross-wire;
- baseline warm p95 on the deterministic Docker fixture is recorded for at least `30` samples each
  for page content, filter preview, status read and navigation under active compute;
- baseline gate requires page-content p95 `<=1500 ms`, filter-preview p95 `<=800 ms`, status-read
  p95 `<=400 ms`, active-compute navigation p95 `<=2000 ms`; tighter final budgets remain owned by
  PR396;
- evidence records SQL query counts, rows decoded, callback payload bytes, CPU/executor concurrency
  and exact Git SHA without credentials/private market rows;
- `uv run portfell-quality pr` and `uv run portfell-quality merge` pass;
- produce immutable sanitized `staged-analysis-performance-baseline-v1` evidence used by PR395.

### PR395 — Read-plane and compute-contention performance optimization

Branch: `perf/pr395-staged-analysis-performance`

Priority: P0 performance hardening.

Depends on: PR394 baseline PASS.

Owned paths: bounded read-plane repository/service queries and indexes, analysis executor capacity
policy, progress-write/polling coalescing, deterministic chart-sample persistence and focused
performance regression tests. No financial formulas, objectives or winner rules.

Scope: create deterministic headroom between long-running analytics and interactive page reads.

Acceptance:

- Metadata page data materializes the active-listing source at most once per page-data request; the
  same request derives options/count/preview from that one materialization rather than issuing
  duplicate full active-listing reads;
- Univariate/Bivariate READY summaries and chart data use persisted small manifest/sample artifacts;
  page rendering never scans all row items merely to compute counts or select chart points;
- deterministic chart samples are persisted once with the run using stable full-identity ordering/
  deterministic sampling and caps `500/1000`; repeated page reads do not resample;
- app-state indexes cover active-job polling, artifact manifest lookup and artifact-item page ranges;
  deterministic `EXPLAIN` fixtures reject sequential full-artifact scans for paged Bivariate reads;
- progress persistence is coalesced to at most `101` normal progress writes per Univariate or
  Bivariate attempt plus terminal write; no per-pair database update storm is permitted;
- polling remains `1000 ms` only while active and disabled terminal; no duplicate polling callback
  independently reloads workflow/page artifacts;
- top-level analytical job concurrency remains exactly one per API process; Multivariate internal
  parallelism is capped by `max(1, min(4, cpu_count - 1))` when `cpu_count > 1`, otherwise `1`, so
  at least one logical CPU is reserved for interactive reads when the host exposes more than one;
- executor-capacity policy is centralized/testable and never changes deterministic analytical
  outputs;
- service/page call graphs contain no normal Dash dependency on all-artifacts `run_detail()`;
- large table HTML is created only for the currently requested `<=100` rows;
- focused benchmark regression tests show improvement or non-regression versus the PR394 baseline
  for every recorded operation and at least `25%` lower p95 for the slowest baseline operation;
- no performance change weakens immutability, source-snapshot identity, typed unavailability,
  progress correctness or revision isolation;
- `uv run portfell-quality pr` passes.

### PR396 — Final staged-analysis UX, performance and restart QA PASS

Branch: `test/pr396-staged-analysis-performance-closeout`

Priority: P0 final gate.

Depends on: PR395.

Scope: QA/evidence only. Any production defect discovered here requires a corrective implementation
PR and a fresh PR396 run; QA does not hide production fixes.

Acceptance must prove all of the following on the exact PR396 head SHA:

- the complete workflow is exactly Metadata -> full-universe Univariate -> read-only filtering ->
  committed Selection -> Bivariate -> automatic default-objective Multivariate;
- there is no separate normal `Compute univariate statistics` or `Compute bivariate statistics`
  action after the two frozen commit buttons, and preview interactions never compute;
- Univariate uses every member of its persisted Metadata universe and one exact source snapshot;
- filter preview membership/counts exactly match an independent Python oracle over the persisted
  Univariate fixture and do not mutate the Univariate artifact;
- committed selection membership exactly equals the applied preview predicates/full identities;
- Bivariate consumes only that selection; Multivariate consumes the exact matching succeeded
  Bivariate run and default objective `return_risk`;
- Univariate/Bivariate progress bars are monotone and reconcile `current == total` on success;
  Multivariate emits all eight logical phases in order and reaches 8/8 only after durable result/
  Decision publication;
- progress/failure/restart states survive application/database restart and stale work is reclaimed
  without duplicate completed artifacts;
- route render, navigation, reload, pagination, chart interaction, status polling and unapplied
  filtering are analytically read-only under spies and database audit;
- READY pages use only bounded reads: `<=100` table rows, `<=500` Univariate chart points,
  `<=1000` Bivariate chart points, and `<=512 KiB` per page-specific callback response on the
  deterministic fixture;
- no normal Dash page invokes all-artifacts `run_detail()`, no full `100,000+` pair artifact is
  deserialized for one Bivariate page, and no market SQL appears outside `market_source`;
- previous/current revision behavior passes rapid U1->U2 and S1->S2 race fixtures with zero mixed
  KPI/chart/table/Decision evidence;
- deterministic browser QA at `1440x900`, `1024x768`, `390x844` proves the progress bar/status,
  filtering, pagination and previous-result labels remain usable with no body horizontal overflow
  and no Portfell console/page errors;
- with the PR394 fixture and at least `30` warm samples per operation, final p95 is
  `<=750 ms` page content, `<=400 ms` filter preview, `<=200 ms` status read and `<=1000 ms`
  navigation while the controllable long-running compute fixture is active;
- each final p95 is no worse than the corresponding PR394 baseline, and the slowest baseline
  operation improves by at least `25%`;
- `uv run portfell-quality pr`, `uv run portfell-quality merge` and GitHub `merge-gate` pass for the
  exact head SHA; skipped/cancelled/zero-step evidence is not PASS;
- produce exactly one immutable sanitized `staged-analysis-performance-v1` PASS artifact containing
  exact 40-hex SHA, fixture sizes, latency distributions/p95, SQL query counts, decoded-row counts,
  payload maxima, executor-capacity policy, progress/restart/race evidence refs and browser evidence
  refs without credentials, complete DSNs or private market rows.

## 10. Plotly Dash five-decimal numeric presentation — PR397 — OUTDATED

### PR397 — Format every displayed floating-point value to exactly five decimal places

Branch: `feat/pr397-dash-five-decimal-float-formatting`

Priority: P1 presentation consistency.

Depends on: PR396 PASS. This PR intentionally lands after the staged-analysis/read-plane series so
its shared formatter and browser assertions apply to the final bounded Dash rendering paths rather
than being repeatedly rebased through PR387–PR396.

Owned paths: `src/portfell/dash_app/**`, shared Dash presentation/figure formatting helpers,
synchronized Dash UI contract documentation when required, and focused unit/component/browser
tests. No application-service financial formulas, market-source code, app-state schema, persisted
analytical artifacts, optimizer logic or numerical decision rules may change.

Scope: introduce one canonical presentation-only float formatting contract for the complete Plotly
Dash application. Every user-visible floating-point number on `/metadata`, `/univariate`,
`/bivariate` and `/multivariate` must be rendered with exactly five digits after the decimal
separator while preserving the underlying full-precision backend value for calculation,
filtering, ranking, persistence and IDs.

Formatting contract:

- ordinary scalar floats render with fixed-point precision equivalent to `.5f`; for example
  `1.234567 -> 1.23457`, `-1.234567 -> -1.23457`, `1.2 -> 1.20000`, `0.000006 -> 0.00001`;
- values that round to negative zero render as `0.00000`, never `-0.00000`;
- percentage displays preserve their existing semantic unit and show exactly five decimal places
  before the percent sign; when the underlying Plotly value is a fraction, use the semantic
  equivalent of `.5%` rather than converting or mutating the analytical value;
- currency/unit prefixes or suffixes remain intact, but the floating-point numeric portion has
  exactly five decimal places;
- integers, counts, ordinals, dates, timestamps, IDs, ISIN/exchange/code identities, categorical
  labels and text are not coerced into float formatting;
- `None`, typed unavailable values and non-finite values must keep the existing unavailable/error
  presentation (`—` or typed reason as appropriate); `nan`, `inf` and `-inf` must never become
  apparently valid five-decimal numbers;
- editable numeric control values must not be rounded in a way that changes filter or analytical
  semantics. Any read-only echo/label/preview of such a float is formatted to five decimals, while
  the underlying submitted value retains its original precision;
- formatting is presentation-only: no `round(..., 5)` or equivalent may be introduced into market
  data, return/risk calculations, covariance/PCA, optimizer inputs/weights, OOS scoring,
  selection predicates, artifact serialization, database writes or DecisionArtifact logic solely
  to satisfy this UI requirement.

User-visible surfaces covered by the contract include, where a float can appear:

- KPI primary/secondary values;
- Dash table numeric cells and history/evidence rows;
- status/progress numeric labels and percentages;
- Plotly x/y/z axis tick labels;
- Plotly hover labels and custom hover templates;
- Plotly annotations, text labels, marker text and data labels;
- chart-specific summaries, legends or titles when they interpolate a float;
- Univariate filter-preview readouts and other read-only control-adjacent numeric labels;
- Multivariate winner, allocation, risk-contribution, PCA/cluster/structural-risk and walk-forward
  diagnostic values.

Acceptance:

- one shared formatting helper/contract is the default path for scalar float text across the Dash
  presentation layer; page-specific ad-hoc precision rules are removed unless a non-float semantic
  explicitly requires different formatting;
- all Plotly figure builders use deterministic axis/hover/annotation formatting so a displayed float
  never falls back to Plotly's variable default precision;
- populated deterministic fixtures for all four routes prove every user-visible finite float has
  exactly five digits after the decimal separator, including KPI cards, tables, hover text, axis
  labels, annotations and progress/status presentation where applicable;
- representative regression fixtures include positive, negative, zero, negative-zero-producing,
  sub-`1e-5`, greater-than-one, percentage and large-magnitude values;
- exact examples assert `1.234567 -> 1.23457`, `-1.234567 -> -1.23457`, `1.2 -> 1.20000`,
  `0.000006 -> 0.00001` and a value rounding to negative zero -> `0.00000`;
- integer counts remain integers and full listing identities/dates/IDs are byte-equivalent to the
  pre-PR397 presentation fixture;
- unavailable/non-finite fixtures never display `nan`, `inf`, `-inf`, fabricated `0.00000`, or a
  five-decimal value in place of an unavailable reason;
- browser and service spies prove display formatting causes zero financial recomputation, zero
  market reads, zero analysis writes and zero mutation of persisted artifact values;
- a frozen analytical regression fixture proves candidate weights, Univariate/Bivariate metrics,
  Multivariate scorecards, OOS winner and DecisionArtifact are byte-equivalent before and after
  PR397; only browser-visible string/tick/hover formatting may differ;
- browser QA covers `1440x900`, `1024x768` and `390x844` and confirms five-decimal formatting does
  not create body-level horizontal overflow or truncate required units/identity context;
- focused formatting/component/browser tests and `uv run portfell-quality pr` pass; GitHub
  `merge-gate` must pass on the exact PR head before merge.
## 11. Nightly Xetra refresh and Univariate age encoding — PR398 — OUTDATED

### PR398 — 20:00 Xetra freshness refresh, automatic Univariate recompute, and age-colored Return/Risk Universe

Branch: `feat/pr398-nightly-xetra-univariate-refresh`

Priority: P1 data freshness and analytical UX.

Depends on: PR397 PASS. This PR lands after the shared five-decimal Dash presentation contract so
its new age colorbar/hover values use the same final formatting path and do not reintroduce
page-specific numeric formatting.

Owned paths: one narrow scheduler/runtime-lifecycle module, low-cost market-source freshness probe,
`app_state` scheduled-refresh checkpoint persistence when required, Univariate job orchestration and
read DTOs, the Dash `/univariate` Return/Risk figure, synchronized operational/UI documentation and
focused scheduler/service/browser tests. No Bivariate or Multivariate financial calculations,
selection semantics, optimizer objectives or DecisionArtifact ranking may change.

Scope: Portfell runs one daily refresh check at exactly `20:00` in timezone `Europe/Vienna`. The
check reads the external `xetra_loader` PostgreSQL source only far enough to determine whether a
newer Xetra EOD quote date exists than the last successfully processed nightly refresh. Only when
that source watermark is newer does Portfell materialize the required coherent market input for the
latest committed Metadata universe and submit/reuse a full-universe Univariate calculation. The
`Univariate Return/Risk Universe` scatter keeps its existing return/risk axes and additionally uses
marker color to encode available quote-history age: the longer the history, the redder the point.

Nightly scheduling and freshness contract:

- the schedule is exactly once per calendar day at `20:00 Europe/Vienna`; DST is handled by an IANA
  timezone-aware scheduler and the job must not be pinned to a fixed UTC hour;
- the scheduler is owned by the existing Portfell API runtime; no new Compose service, Redis,
  Celery, RQ, Node process or second analytical executor is introduced;
- overlapping scheduler callbacks, process restart and duplicate delivery are idempotent and cannot
  create two logical refreshes or two Univariate jobs for the same universe/source revision;
- the freshness watermark is the latest non-null `trade_date` available from
  `xetra_loader.eod_quotes`; the probe must use one bounded/index-supported query such as an ordered
  latest-row lookup and must not materialize quote history, scan `xetra_loader_sync`, or infer loader
  state from private sync tables;
- the persisted comparison point is the watermark of the last **successfully processed** nightly
  refresh, not the last attempted refresh; first run with no checkpoint is treated as stale and is
  eligible for refresh;
- if `source_latest_trade_date <= last_successful_trade_date`, the run is a clean no-op: no bulk
  listing/quote/dividend/split materialization, no new market-source snapshot, no analysis run/job,
  and no Univariate artifact write occurs;
- if the source watermark is newer, Portfell materializes the current committed Metadata-universe
  members and their required listings/quotes/dividends/splits under the existing
  `REPEATABLE READ, READ ONLY` market-source contract, closes the source transaction before CPU-heavy
  calculation, and pins the resulting immutable source snapshot to the Univariate run;
- `fetch` in this PR means read/materialize analytical input from the canonical external PostgreSQL
  source. Portfell must not create a second raw Xetra market-data mirror or take ownership of
  `xetra_loader` tables;
- if no committed Metadata universe exists, the scheduler records a typed no-op
  `nightly_refresh_no_universe`; it must not invent a default universe or silently change Metadata
  predicates/membership;
- when fresh source data exists, the scheduler submits/reuses the existing durable full-universe
  Univariate job path; computation is never performed synchronously inside the scheduler callback;
- if the exact universe/source-snapshot Univariate run already succeeded before the nightly trigger,
  the refresh reuses that result and advances the checkpoint without recomputing statistics;
- the successful checkpoint advances only after the matching Univariate run/artifact is durably
  `succeeded`; materialization, executor or calculation failure leaves the prior watermark intact so
  a later invocation can retry;
- nightly refresh does **not** automatically create a new Univariate selection or launch Bivariate or
  Multivariate computation. Downstream selection remains an explicit user commit;
- public status/evidence records the scheduled time, observed source watermark, prior successful
  watermark, outcome (`no_change`, `refreshed`, `reused`, `no_universe`, `failed`), exact universe ID,
  snapshot ID/run ID when present, and typed/redacted failure code without SQL, DSNs or credentials.

Instrument-age color contract for `Univariate Return/Risk Universe`:

- age is derived only from persisted Univariate row history, not from wall-clock time or an external
  issuer lookup: `history_age_days = last_quote_date - first_quote_date` for the same full
  `(isin, exchange, code)` identity;
- the UI labels this measure `History age` so it is not misrepresented as the legal issuance date of
  the ISIN; hover shows `First quote`, `Last quote` and `History age`;
- the color variable is continuous and monotone in `history_age_days`; younger histories use the
  light end and older histories the dark/red end of Plotly's sequential `Reds` scale, so for two
  valid rows with different ages the older row is always redder;
- a visible colorbar is titled exactly `History age (years)`; the display value may convert days by
  `365.25` for presentation only, while ordering/color normalization uses exact integer day counts;
- missing, malformed or negative history intervals are typed `history_age_unavailable`, rendered as
  a neutral marker outside the continuous age scale, and never coerced to age `0`;
- an equal-age fixture renders all valid points with one stable age color and does not divide by zero
  or produce `NaN` color coordinates;
- marker color is presentation-only and never changes Univariate filtering, persisted selection
  membership, chart sampling, ranking, availability, return/risk metrics or downstream eligibility;
- the existing bounded Univariate chart contract remains in force (`<=500` deterministic points);
  `first_quote_date`, `last_quote_date` and age evidence must travel through the bounded persisted
  chart/read DTO rather than causing an all-row artifact read or market query;
- full listing identity remains visible in hover wherever ISIN alone could be ambiguous;
- this age encoding is an explicit chart-local exception to the older visual rule that reserved red
  exclusively for error/negative state; the colorbar and hover must make clear that red means older
  history, not loss, risk severity or failure.

Acceptance:

- deterministic timezone tests prove exactly one scheduled trigger at `20:00 Europe/Vienna` across
  both CET and CEST dates and no duplicate logical refresh on repeated delivery;
- a stale-source fixture performs exactly the bounded freshness probe and zero bulk market reads,
  analysis submissions or writes;
- a newer-source fixture materializes one coherent source revision, submits/reuses one full-universe
  Univariate job and publishes the same numerical rows as the existing synchronous regression
  fixture for that exact input;
- failed refresh leaves the previous successful watermark unchanged; retry after recovery succeeds
  without duplicate immutable snapshots/runs/artifacts;
- restart tests prove the schedule/checkpoint and in-flight durable Univariate job recover without
  double execution;
- browser/component fixtures prove older history maps monotonically to redder markers, colorbar and
  hover age are present, unavailable age is neutral/not-zero, and the existing return/risk x/y values
  are byte-equivalent before and after this PR;
- page render, hover, color normalization and nightly no-change checks perform zero financial
  recomputation on the Dash request thread and do not read the complete Univariate artifact;
- `1440x900`, `1024x768` and `390x844` browser fixtures have no body-level horizontal overflow and
  preserve readable colorbar/hover context;
- focused scheduler/freshness/idempotency/service/browser tests and `uv run portfell-quality pr`
  pass; GitHub `merge-gate` must pass on the exact PR head before merge.
## 12. Metadata distribution overview and project selector — PR399–PR400 — OUTDATED

### PR399 — Replace Metadata Xetra listing table with one three-distribution figure

Branch: `feat/pr399-metadata-distribution-overview`

Priority: P1 analytical UX and bounded rendering.

Depends on: PR397 PASS. May execute in parallel with PR398 because it changes only Metadata-page read/presentation behavior and does not alter the nightly Univariate refresh contract.

Owned paths: Metadata page/read-model code, shared Plotly figure helpers required for this figure, synchronized Metadata UI documentation, and focused service/component/browser tests. No market-source schema, universe membership semantics, Univariate/Bivariate/Multivariate formulas, selection predicates, optimizer logic, or DecisionArtifact behavior may change.

Scope: remove the `Xetra Listings` table/preview from `/metadata`. In the same location render one Plotly distribution figure that summarizes the currently filtered active Xetra universe with exactly three categorical distributions: `Instrument type`, `Country`, and `Currency`.

Distribution contract:

- the figure is one Plotly figure/card, not three independent page cards; it contains exactly three clearly labelled panels/traces for `Instrument type`, `Country`, and `Currency`;
- distributions are computed from the exact same currently filtered active-listing set that drives `Filtered listings`, `Selected listings`, and universe creation, so applying any Metadata filter updates all three distributions consistently;
- each distribution is a frequency distribution over listing count; every non-empty category is represented and the counts for each distribution reconcile exactly to the current filtered listing count;
- missing/blank categorical values are grouped under one explicit `Unknown` category rather than silently dropped;
- categories are ordered deterministically by descending count and then lexicographically by displayed label for ties;
- hover exposes category, exact listing count, and percentage of the current filtered universe; percentages are presentation-only and do not alter membership;
- the figure title is exactly `Universe distributions`; panel labels are exactly `Instrument type`, `Country`, and `Currency`;
- the existing `Xetra Listings` table, its bounded first-100-row preview note, and listing-row HTML rendering are removed from the normal Metadata page;
- no complete listing-row payload is sent to the browser solely to draw this figure. The Metadata read model returns compact aggregated distribution DTOs plus the existing counts/options/current-universe data;
- one Metadata page-data request materializes the filtered active-listing source at most once and derives all three distributions from that same materialization, preserving the PR395 no-duplicate-read contract;
- the four Metadata filters and `Create universe & compute Univariate` behavior are unchanged; chart interaction is informational only and must not mutate filter values, universe membership, or create a universe;
- duplicate ISINs on different `(exchange, code)` identities remain separate listings in distribution counts, consistent with the repository-wide full-identity contract;
- the shared PR397 five-decimal formatting contract applies to percentage hover/readouts, while listing counts remain integers.

Acceptance:

- deterministic fixtures prove the three distribution totals each equal `filtered_count` for unfiltered and filtered universes;
- a fixture containing null/blank instrument type, country, and currency values produces explicit `Unknown` buckets and no lost listings;
- tie-order fixtures are stable across repeated runs and input-row ordering changes;
- browser/service spies prove filter changes perform no analytical compute or persistence writes and use at most one active-listing materialization per page-data request;
- the normal `/metadata` DOM contains no `Xetra Listings` table and no per-listing preview rows after this PR;
- the figure contains exactly the three required distributions and updates when Metadata filters change;
- universe creation from a frozen filter fixture produces byte-equivalent member identities before and after PR399;
- `1440x900`, `1024x768`, and `390x844` browser fixtures show all three distribution labels with no body-level horizontal overflow;
- focused aggregation/component/browser tests and `uv run portfell-quality pr` pass; GitHub `merge-gate` must pass on the exact PR head before merge.

### PR400 — Sidebar project/universe dropdown and complete selected-project context

Branch: `feat/pr400-sidebar-project-selector`

Priority: P1 workflow navigation and historical project inspection.

Depends on: PR399. It may consume the final Metadata-universe read contracts from PR399 but must not reintroduce the removed listing table.

Owned paths: Dash shared shell/sidebar, identifier-only browser/presentation state, narrow application-service project-summary reads, synchronized shell/UI documentation, and focused service/component/browser tests. No financial calculation, market-source write, artifact mutation, universe-member mutation, selection mutation, optimizer objective, or DecisionArtifact ranking may change.

Scope: under the existing sidebar heading `Current analysis`, add one dropdown containing every persisted Metadata universe created in Portfell. In this UI contract, a `project` is exactly one persisted `metadata_universe` revision. Selecting a project updates the information shown directly beneath `Current analysis` to the exact persisted information and analytical lineage for that selected universe.

Project selector contract:

- the dropdown is rendered directly below `Current analysis` and above the project-information rows;
- its options contain every persisted Metadata universe, not only the latest one, ordered newest version first with deterministic ties;
- option values are exact `universe_id` values; the human-readable label is `Universe v<version> · <short-universe-id>` so two projects can never collide because of display name reuse;
- on first load with no explicit browser selection, the latest persisted Metadata universe is selected; when no universe exists the dropdown is disabled and the existing empty/not-ready context is retained;
- selecting a different option is a read-only context action: it performs zero market reads, zero analytical computation, zero job submission, zero universe/selection/artifact writes, and does not make a new project;
- selected `universe_id` is stored only as identifier-level browser/UI state suitable for reload reconstruction; no complete universe member list or analytical artifact is copied into browser state;
- invalid/deleted/non-existent selected IDs fail closed to typed `project_not_found` presentation and must not silently substitute the latest universe;
- changing the selected project updates the sidebar context without a full-route rebuild and does not discard page filter/control state.

Selected-project information shown beneath the dropdown:

- `Universe ID` — full persisted universe ID, with responsive wrapping rather than truncating the authoritative value;
- `Version`;
- `Created` timestamp;
- `Published` timestamp;
- `Members` count;
- `Source snapshot` — full persisted source snapshot ID;
- `Univariate` — exact latest matching run status plus run ID for that universe, or `Not computed`;
- `Selection` — exact persisted selection ID/member count sourced from a matching Univariate run, or `Not selected`;
- `Bivariate` — exact latest matching run status plus run ID for that selection, or `Not computed`;
- `Multivariate` — exact latest matching run status plus run ID for that same lineage, or `Not computed`;
- `Readiness` — deterministic stage-readiness summary derived only from the selected project's exact lineage;
- `Active job` — shown only when a durable job belongs to the selected project's exact lineage; unrelated jobs from another universe are never displayed as belonging to the project.

Lineage/read contract:

- project summary resolution starts from the selected `universe_id`; a generic latest-run/selection lookup is forbidden once a project has been selected;
- Univariate linkage is by exact `AnalysisRun.input_ref == universe_id`;
- any displayed selection must have `source_run_id` equal to a matching Univariate run for the selected universe;
- Bivariate/Multivariate status must be resolved through the exact selected selection/run dependencies already frozen by the staged-analysis pipeline; evidence from another universe or selection must never cross-wire into the sidebar;
- when several historical runs exist for the same exact project lineage, display the newest matching persisted revision deterministically and retain exact IDs so the choice is auditable;
- the summary read is bounded and identifier/status-oriented; it must not deserialize row-backed Univariate/Bivariate artifacts, full member lists, PCA/cluster artifacts, or market history;
- project selection is presentation/navigation state only in PR400. It does not change the nightly PR398 refresh target, create a new analysis, or implicitly recompute an old project; future compute-against-selected-project behavior requires an explicit backlog contract.

Acceptance:

- fixtures with at least five universes prove all five appear in newest-first order and each dropdown value is its exact `universe_id`;
- selecting each fixture universe produces only that universe's IDs, timestamps, member count, source snapshot, matching selection/run statuses, readiness, and matching active-job evidence;
- a deliberate U1/S1/B1/M1 versus U2/S2/B2/M2 race fixture proves zero cross-project lineage mixing;
- switching projects performs zero market reads, zero analytical compute calls, zero job submissions and zero app-state writes;
- sidebar selection changes do not trigger full page reconstruction and preserve Metadata/Univariate filter state already present in the browser;
- reload reconstructs the selected project when still valid; a missing project renders typed `project_not_found` rather than silently switching projects;
- the selected-project block remains usable at `1440x900`, `1024x768`, and `390x844`, with full IDs accessible and no body-level horizontal overflow;
- focused summary-lineage/state/sidebar/browser tests and `uv run portfell-quality pr` pass; GitHub `merge-gate` must pass on the exact PR head before merge.

## 13. Income-first Univariate metric distributions and selection dashboard — PR401–PR406 — OUTDATED

This series replaces the generic Univariate first-page result preview with an income-first metric distribution dashboard while preserving the existing staged-analysis contract: the full Metadata universe is computed once, metric interactions are read-only selection preview, and only the existing `Apply selection & compute downstream` commit creates the immutable selection that Bivariate consumes.

Dependency graph:

```text
PR398 + PR400
      |
    PR401
      |
    PR402
      |
    PR403
      |
    PR404
      |
    PR405
      |
    PR406(QA/PASS)
```

Hard decisions for PR401–PR406:

- the normal `/univariate` page no longer presents the generic `Showing the first 100 of ... persisted results.` result-table experience; the detailed result region is metric-centric;
- the existing `Univariate Return / Risk Universe` overview may remain above the metric dashboard, but it is not a substitute for any required metric card;
- every required Univariate metric has one dedicated metric card containing its optimal cross-sectional distribution plot, summary-number table, and selection controls;
- on desktop every metric card uses exactly `60%` width for the Plotly distribution area, `30%` for the numeric/category table, and `10%` for the selection-control rail; mobile stacks those three regions in the same semantic order;
- Univariate is still calculated over every full-identity member of the exact Metadata universe. Selecting thresholds/categories never changes the immutable Univariate run and never recomputes a metric;
- the default transient preview is income-first: `distribution_frequency` includes `monthly` and `quarterly` and excludes other/unknown/accumulating frequencies. This default is not business authority until the user commits it;
- selection predicates across different metrics combine with logical AND. Missing/unavailable metric values are never converted to zero and cannot pass a filter whose metric is enabled;
- the existing action label `Apply selection & compute downstream` remains the only commit. It persists exact full `(isin, exchange, code)` members and then uses the already-frozen PR390 `Selection -> Bivariate -> Multivariate(return_risk)` chain;
- metric checkbox changes, distribution-card expansion, chart hover/zoom, summary-table interaction, project switching and page reload are analytically read-only and cannot start Bivariate or Multivariate;
- the PR398 daily `20:00 Europe/Vienna` scheduler remains the only Portfell nightly market-refresh scheduler. No second cron/scheduler is introduced by this series;
- when PR398 observes a newer canonical Xetra EOD quote watermark, the resulting coherent market snapshot includes the then-current dividend evidence and the full income/risk metric catalog is recomputed and persisted for that exact universe/snapshot before the nightly checkpoint can advance;
- the no-change PR398 path remains a true no-op. A separate full-market scan is not authorized merely to check whether dividend rows changed;
- dividends remain income evidence and are never added a second time to adjusted-close returns. Raw `close` is not introduced as a split-unsafe return authority;
- the previously proposed raw `price_cagr` is therefore not a required metric under this contract. The canonical return CAGR is `total_return_cagr`, preserving the repository's existing adjusted-close return convention; any future separate price-only CAGR requires an explicit split-safe source/return contract;
- all finite float values rendered by the new metric cards use the PR397 exactly-five-decimal presentation contract without rounding persisted analytical values.

Frozen required metric catalog:

- **Data quality:** `history_years`, `distribution_history_years`, `observation_count`, `missing_ratio`;
- **Income/distributions:** `distribution_frequency`, `distributions_per_year`, `ttm_distribution`, `ttm_distribution_yield`, `distribution_cagr_3y`, `distribution_cagr_5y`, `distribution_cv`, `distribution_regularity`, `distribution_cut_ratio`, `max_distribution_cut`, `rolling_12m_distribution_yield_median`, `rolling_12m_distribution_yield_min`, `rolling_12m_distribution_yield_max`, `rolling_12m_distribution_yield_std`, `distribution_growth_positive_year_ratio`, `distribution_drawdown`;
- **Return/capital risk:** `total_return_cagr`, `annualized_volatility`, `downside_deviation`, `max_drawdown`, `current_drawdown`, `max_drawdown_duration`, `current_drawdown_duration`, `max_drawdown_recovery_days`, `var_95`, `cvar_95`, `ulcer_index`;
- **Risk-adjusted return:** `sharpe`, `sortino`, `calmar`;
- **Robustness/distribution shape:** `rolling_3y_cagr_median`, `rolling_3y_cagr_min`, `rolling_3y_sharpe_median`, `rolling_3y_sharpe_min`, `skewness`, `excess_kurtosis`, `positive_month_ratio`, `worst_month`, `best_month`, `worst_3m_return`, `worst_12m_return`, `rolling_1y_return_median`, `rolling_1y_return_min`, `rolling_1y_return_std`, `rolling_1y_vol_median`, `rolling_1y_vol_max`, `gain_loss_ratio`.

Frozen plot registry:

- `distribution_frequency`: horizontal categorical bar chart with exact category counts/shares;
- signed metrics with an economically/statistically meaningful zero (`distribution_cagr_3y`, `distribution_cagr_5y`, `max_distribution_cut`, `distribution_drawdown`, `total_return_cagr`, `current_drawdown`, `skewness`, `worst_month`, `best_month`, `worst_3m_return`, `worst_12m_return`, rolling return/CAGR summaries): histogram plus ECDF and an explicit vertical zero reference line;
- ratios naturally bounded to `[0,1]` (`distribution_regularity`, `distribution_cut_ratio`, `distribution_growth_positive_year_ratio`, `positive_month_ratio`): histogram plus ECDF with the bounded axis explicit;
- all other continuous metrics: histogram plus ECDF using deterministic persisted bins/points; no kernel-density estimate is required and no distributional parametric assumption is implied;
- raw `ttm_distribution` cash amounts must preserve dividend currency. If more than one non-equivalent currency exists in the displayed run, the plot is partitioned/labeled by currency and a single cross-currency amount threshold is unavailable; `ttm_distribution_yield` remains the comparable percentage metric and no FX conversion is invented.

Frozen metric-card summary/filter contract:

- continuous metric tables show exact `Available`, `Unavailable`, `Minimum`, `P05`, `P25`, `Median`, `P75`, `P95`, `Maximum`, `Mean`, and `Std` values derived from the immutable run;
- the `10%` selector rail aligns selectable threshold controls to the table anchors `Minimum`, `P05`, `P25`, `Median`, `P75`, `P95`, and `Maximum`;
- every continuous metric allows at most one enabled inclusive lower bound (`>=`) and one enabled inclusive upper bound (`<=`); the selected bound is the exact backend value behind the displayed table cell, not the five-decimal formatted string;
- categorical metric tables show `Category`, `Count`, `Share`; the selector rail has one include checkbox per category row;
- selecting a new lower/upper anchor for a metric replaces the previous bound of that direction for the same metric; contradictory `lower > upper` is rejected as typed invalid preview rather than returning a fabricated empty selection;
- the metric plot always shows the immutable full-run distribution and visually marks the active lower/upper bounds or included categories. Filter changes therefore do not make percentile anchors drift underneath an already-selected threshold;
- summary/card reads are bounded persisted reads. No metric card may cause a market query or load the complete Univariate row artifact into browser state.

### PR401 — Freeze the income-first Univariate metric/plot/filter contract

Branch: `docs/pr401-univariate-income-metric-contract`

Priority: P0 quantitative/UI contract.

Depends on: PR398 and PR400.

Owned paths: `BACKLOG.md`, new `docs/contracts/univariate-income-metrics-v1.md`, synchronized Univariate UI contract documentation, and focused contract/documentation tests only. No production calculation, persistence, Dash or scheduler code.

Scope: make the Section 13 metric catalog executable by freezing each metric's exact formula/input series, unit, minimum-history rule, availability reason, plot kind, summary-table semantics, filter direction/type and deterministic ordering.

Acceptance:

- all metric IDs in the frozen catalog have one exact definition and no alias with different economics;
- `history_years` uses valid adjusted-close first/last dates and exact day span divided by `365.25` for display/statistics;
- `observation_count` counts valid adjusted-close observations, not quarantined/raw rows;
- `missing_ratio` is defined against the deterministic set of observed Xetra-universe trade dates between the listing's first and last valid quote in the same coherent snapshot; no guessed weekend/holiday calendar is introduced;
- distribution-history metrics use positive dividend/distribution events only and preserve full listing identity;
- `ttm_distribution` is the positive cash amount in `(last_quote_date - 365 days, last_quote_date]`; `ttm_distribution_yield` divides the same economically comparable amount by the last valid adjusted close under the frozen currency rule;
- distribution CAGR `3y/5y`, CV, regularity, cut ratio, maximum cut, growth-positive ratio, distribution drawdown and rolling-yield statistics are frozen on one deterministic trailing-12-month distribution series with explicit complete-history requirements;
- monthly/quarterly regularity uses expected cadence buckets from the backend-detected frequency; multiple positive events within one expected period do not fabricate extra regularity;
- `total_return_cagr` preserves the current adjusted-close CAGR convention; dividends are not added again and raw close is not substituted;
- `var_95` and `cvar_95` are separately defined at exactly `95%` confidence and do not silently reuse the current default `97.5%` tail statistic under a misleading name;
- monthly/rolling-return, drawdown-duration/recovery, Ulcer, gain/loss, skewness and excess-kurtosis definitions include exact edge-case and insufficient-history behavior;
- every metric defines a typed per-metric unavailable reason rather than using numerical zero/NaN;
- the plot registry, 60/30/10 desktop card geometry, summary rows and filter-rail semantics are reproduced exactly in the contract;
- contract tests prove every catalog metric has formula/unit/availability/plot/filter metadata and no undocumented metric appears in the UI registry;
- `uv run portfell-quality pr` passes.

### PR402 — Compute and persist the full Univariate income/risk metric catalog

Branch: `feat/pr402-univariate-income-metrics-v3`

Priority: P0 analytics.

Depends on: PR401.

Owned paths: `src/portfell/univariate_statistics.py` and narrowly separated pure Univariate metric modules/helpers, Univariate analytical DTO/schema contracts, row-artifact publication adapters, and focused numerical/property/regression tests. No Dash, Bivariate, Multivariate or scheduler presentation changes.

Scope: version the production Univariate calculation/output so every full-universe row contains the complete PR401 metric catalog plus per-metric availability evidence.

Acceptance:

- new production rows publish as immutable `univariate.rows@v3` under an explicit Univariate calculation contract version; historical v2 artifacts remain readable and are never mutated;
- every v3 row preserves exact `(isin, exchange, code)`, source snapshot/run identity, current existing metrics required by downstream code, the complete Section 13 metric catalog, and deterministic per-metric availability reasons;
- formulas already present on `main` (`annualized_volatility`, downside deviation, Sharpe, Sortino, max drawdown, existing adjusted-close CAGR, current distribution frequency/TTM dividend evidence) remain regression-equivalent unless PR401 explicitly versions the semantic definition;
- return/risk/volatility/drawdown calculations continue to use adjusted close only; missing adjusted close remains typed unavailable and dividends/splits are not double-counted;
- dividend-currency mismatch/mixed-currency conditions fail the affected cash-amount/yield calculation closed unless the PR401 contract proves comparability; no FX rate is assumed;
- new `95%` VaR/CVaR, Calmar, Ulcer, current/max drawdown duration/recovery, monthly/rolling return statistics, skewness/kurtosis and gain/loss statistics pass independent numerical fixtures;
- distribution CAGR/stability/regularity/cut/drawdown/rolling-yield statistics pass fixtures for monthly, quarterly, missing-period, multiple-same-period, growing, cut, accumulating and insufficient-history series;
- all rolling windows are backward-looking only and include no observation after the row's `last_quote_date`;
- unavailable values serialize as `null` plus typed reason, never `NaN`, infinity or plausible zero;
- repeated byte-equivalent market inputs produce byte-equivalent row documents and stable artifact identity;
- downstream code that still needs legacy metric names is updated through one explicit compatibility mapping inside the service/calculation boundary, not by duplicating formulas in Dash;
- focused numerical tests and `uv run portfell-quality pr` pass.

### PR403 — Persist metric distributions and connect v3 to the nightly Xetra refresh

Branch: `feat/pr403-univariate-metric-distributions-nightly`

Priority: P0 data freshness/read plane.

Depends on: PR402.

Owned paths: Univariate artifact assembly/read DTOs, compact metric-distribution artifact persistence, PR398 nightly Univariate orchestration adapter, and focused persistence/scheduler/read tests. No Dash layout or Bivariate logic.

Scope: produce one compact, immutable distribution-summary artifact for every successful v3 Univariate run and make the existing PR398 fresh-Xetra path publish/reuse v3 rows plus that distribution artifact.

Acceptance:

- every successful `univariate.rows@v3` run publishes exactly one matching `univariate.metric_distributions@v1` artifact keyed to the same run/source snapshot;
- for every continuous metric the artifact stores exact available/unavailable counts, full-run summary anchors, deterministic histogram bins/counts, and a bounded deterministic ECDF representation with at most `500` plotted points while computing percentiles/counts from all available rows;
- categorical metrics store exact category/count/share rows with deterministic ordering; counts reconcile to the v3 row artifact;
- raw TTM cash-amount summaries retain currency partitions and never combine incomparable currencies into one scalar distribution;
- the distribution artifact is small enough that normal metric-card reads do not deserialize all row items; repeated page reads do not rebuild histograms/ECDFs;
- PR398's existing `20:00 Europe/Vienna` scheduler remains the sole daily trigger. A newer EOD quote watermark materializes one coherent latest market revision, including then-current dividends, and submits/reuses the v3 Univariate computation;
- the PR398 checkpoint advances only after both the matching v3 row artifact and metric-distribution artifact are durably available;
- if the source EOD watermark has not advanced, the nightly path performs the existing bounded no-change probe only and creates no v3 run/distribution artifact;
- if an exact v3 run/distribution artifact already exists for the universe/source snapshot, nightly refresh reuses it idempotently;
- process restart and duplicate scheduler delivery cannot create duplicate v3/distribution artifacts;
- no second scheduler, raw Xetra mirror, sync-schema read or direct Dash market read is introduced;
- focused artifact/persistence/scheduler/restart tests and `uv run portfell-quality pr` pass.

### PR404 — Replace the generic Univariate first-100 table with metric distribution cards

Branch: `feat/pr404-dash-univariate-metric-cards`

Priority: P0 analytical UX.

Depends on: PR403.

Owned paths: `/univariate` Dash page, metric-card/presentation helpers, shared CSS only where required for the frozen grid, synchronized Univariate UI documentation and focused component/browser tests. No financial calculation, artifact write or downstream-job logic.

Scope: remove the generic `Univariate Statistics` first-100 result-table experience and render the complete metric catalog as grouped distribution cards sourced from the persisted PR403 artifact.

Required presentation:

- the literal/semantic `Showing the first 100 of ... persisted results.` preview is absent from normal `/univariate` READY state;
- metric cards are grouped in this order: `Data quality`, `Income & distributions`, `Return & capital risk`, `Risk-adjusted return`, `Robustness & distribution shape`;
- every catalog metric has exactly one card and no card silently disappears when unavailable; unavailable cards show exact available/unavailable evidence/reason;
- desktop card inner grid is exactly `60% plot / 30% table / 10% selector rail`; at `1024x768` the relationship remains visually preserved without body overflow; at `390x844` the regions stack plot -> table -> selector rail;
- distribution plots use the exact PR401 plot registry, shared Plotly template and PR397 five-decimal formatting; zero reference lines, bounded axes and currency labels are explicit where contracted;
- continuous tables show the exact PR401 summary rows; categorical tables show category/count/share; integer counts remain integers;
- the selector rail renders aligned `>=`/`<=` checkboxes for numeric threshold anchors or category include checkboxes for categorical rows;
- the active threshold/category state is visually marked on the plot but never alters the immutable full-run distribution data;
- the transient default frequency selection is exactly `monthly + quarterly`; accumulating/unknown/other remain visible in the distribution table/plot but initially unchecked;
- the existing Return/Risk overview, job progress, project/history context and `Apply selection & compute downstream` stage action continue to work and do not cross-wire revisions;
- card groups may use deterministic accordion/lazy rendering so the page remains bounded, but opening/closing a group is presentation-only and every metric remains reachable on the same `/univariate` page;
- page/card reads use only compact persisted artifacts/service DTOs and perform zero market reads or financial calculations;
- focused card-registry/layout/unavailable/currency/five-decimal/browser tests and `uv run portfell-quality pr` pass.

### PR405 — Generalize Univariate metric-filter preview and feed the exact committed selection to Bivariate

Branch: `feat/pr405-univariate-metric-filter-selection`

Priority: P0 selection semantics.

Depends on: PR404.

Owned paths: Univariate filter predicate DTO/normalization, bounded app-state row-filter queries/service reads, Univariate filter callbacks/state, and focused selection/downstream-lineage tests. Reuse PR390 orchestration; do not add a second downstream pipeline.

Scope: replace the old five-field v1 filter set with the versioned metric-card predicate model while preserving read-only preview and the single explicit commit boundary.

Acceptance:

- define one canonical `univariate.metric_filters@v1` predicate payload containing normalized sorted metric IDs and, per metric, either inclusive numeric `lower`/`upper` bounds or a categorical allowed-value set;
- every numeric bound originates from the exact immutable full-run summary anchor selected in the metric card; the service persists/compares the full-precision backend value, not formatted display text;
- different enabled metrics combine by AND; multiple allowed categories within one categorical metric combine by OR;
- rows with a required metric unavailable fail that enabled predicate and remain counted as unavailable evidence; no missing-as-zero behavior exists;
- the initial unapplied preview has exactly `distribution_frequency in {monthly, quarterly}` and all other metric predicates disabled;
- every preview change returns exact matching full-identity count, unavailable/excluded evidence, planned Bivariate pair count and downstream-runnable state without market reads, Univariate recomputation, selection writes or downstream job submission;
- contradictory bounds and cross-currency `ttm_distribution` amount filters fail with typed preview reasons; `ttm_distribution_yield` remains independently filterable;
- changing project/universe selects only that project's exact matching Univariate v3 run/distribution artifact and cannot reuse predicates or rows from another lineage as business authority;
- pressing `Apply selection & compute downstream` creates/reuses one immutable Univariate selection whose members exactly equal an independent oracle over the v3 row artifact and normalized predicates;
- the committed selection stores source Univariate run ID plus normalized filter payload for auditability and restart reconstruction;
- after commit, the existing PR390 path submits/reuses Bivariate with `input_ref == selection_id`; Bivariate receives exactly the committed full identities and never a browser-only table/chart subset;
- filter checkbox/anchor changes alone never create Bivariate or Multivariate jobs; only Apply commits;
- reload restores the persisted committed selection/readiness while any uncommitted filter edits remain presentation state only;
- race fixtures prove U1/S1/B1 and U2/S2/B2 cannot cross-wire under rapid project/filter/apply changes;
- focused predicate/oracle/selection/idempotency/race/downstream tests and `uv run portfell-quality pr` pass.

### PR406 — Income-first Univariate dashboard, nightly-refresh and Bivariate-handoff QA PASS

Branch: `test/pr406-univariate-income-dashboard-closeout`

Priority: P0 final QA gate.

Depends on: PR405.

Scope: QA/evidence only. Any production defect found here requires a corrective implementation PR and a fresh PR406 run.

Acceptance must prove all of the following on the exact PR406 head SHA:

- an independent numerical fixture verifies every PR401 catalog metric, including monthly/quarterly dividend cases, growing/cut/irregular distributions, tail risk, drawdowns/durations, rolling statistics, skewness/kurtosis and insufficient-history/unavailable states without using the production helper under test as the oracle;
- one full-universe v3 run persists exact row count and one matching metric-distribution artifact; every metric's available/unavailable counts and summary/category totals reconcile to the row artifact;
- a deterministic nightly newer-Xetra-watermark fixture runs through the PR398 scheduler path and refreshes the v3 metric catalog using the latest coherent dividend evidence; no-change performs zero bulk market reads/compute writes;
- the `/univariate` READY DOM contains no generic first-100 persisted-results note/table experience and exposes one reachable card for every frozen metric;
- every populated metric card at desktop has measured inner geometry matching `60% plot / 30% table / 10% selector rail` within a browser-test tolerance of `±2` percentage points; mobile stacks in the frozen order;
- plot-registry fixtures prove frequency uses horizontal bars, continuous metrics use histogram+ECDF, signed metrics show zero reference, bounded ratios show bounded axes, and mixed-currency TTM cash evidence is not falsely aggregated;
- all finite float summary/hover/axis values satisfy the PR397 five-decimal display contract without changing full-precision selection thresholds;
- the initial transient preview selects exactly monthly and quarterly distributing rows from the fixture and does not mutate the run or create downstream jobs;
- selecting percentile/category checkboxes across at least six different metric families yields exact AND/OR predicate membership matching an independent persisted-row oracle;
- `Apply selection & compute downstream` persists exactly that membership and the subsequent Bivariate job reads exactly those full listing identities through the existing selection input contract;
- unapplied checkbox changes, plot interactions, accordion/group changes, project switching, pagination/status polling and reload cause zero financial compute calls and zero Bivariate/Multivariate job submissions;
- restart restores v3 artifacts, distribution summaries, committed selection and exact Bivariate lineage without recomputation on read;
- deterministic fixtures at `1440x900`, `1024x768`, and `390x844` have no body-level horizontal overflow and retain accessible table/selector labels and typed unavailable states;
- normal Univariate page/card callbacks remain within the existing staged-analysis bounded-response/read-plane contract and do not deserialize the complete row artifact merely to render a card;
- `uv run portfell-quality pr`, `uv run portfell-quality merge` and GitHub `merge-gate` pass on the exact head; skipped/cancelled/zero-step evidence is not PASS;
- produce one immutable sanitized `univariate-income-dashboard-v1` PASS artifact containing exact Git SHA, catalog/contract versions, fixture sizes, metric-registry fingerprint, nightly-refresh evidence refs, browser-layout evidence refs, selection-oracle fingerprint and exact Bivariate-handoff evidence without credentials, DSNs or private market rows.

**Active backlog status — PR407–PR427 only**

**Status override — 2026-09-04:** Every PR from PR308 through PR406 is now
marked **OUTDATED** for backlog execution. Those entries are retained only as
historical/audit reference and must not be implemented, reopened, or used as a
dependency for new work. PR407–PR427 are the only active backlog PRs. Their
dependencies must be taken from the active graph below, not from the retired
PR descriptions.

## 14. Four independently deployable page modules over shared PostgreSQL and data share — PR407–PR427

This series evolves the current modular monolith into four independently deployable applications:
Metadata, Univariate, Bivariate and Multivariate. Each application owns its browser page, REST API,
business logic and write model. Cross-module hand-off occurs only through immutable PostgreSQL IDs
and published artifacts in one shared data share. Direct Python calls, direct HTTP calls and shared
mutable memory between analytical modules are forbidden in the final topology.

### 14.1 Frozen target topology

```text
Browser
   |
   v
Portfell gateway (routing, shared shell, workflow read model only)
   |
   +--> Metadata application     /metadata     /api/metadata/*
   +--> Univariate application   /univariate   /api/univariate/*
   +--> Bivariate application    /bivariate    /api/bivariate/*
   +--> Multivariate application /multivariate /api/multivariate/*

All five processes
   |
   +--> one PostgreSQL instance / database portfell_dash
   |       schemas: workflow, metadata, univariate, bivariate, multivariate
   |
   +--> one shared immutable data share
           market/, univariate/, bivariate/, multivariate/
```

Hard decisions:

- each analytical application has one production entrypoint, one FastAPI application, one Dash
  page application, one application service and one repository interface;
- the gateway contains no financial calculation, selection calculation or artifact writer;
- modules never call sibling module REST endpoints and never import sibling implementation code;
- PostgreSQL is the only workflow hand-off authority; REST requests carry IDs, not analytical row
  sets;
- the shared data share holds large immutable Parquet/JSON artifacts; PostgreSQL stores artifact
  identity, owner, schema version, path, content hash, row count and publication status;
- each module may read published upstream records/artifacts through contract readers but may write
  only its own schema and artifact namespace;
- one common package may contain immutable DTOs, ID types, error envelopes, configuration, logging,
  health checks and presentation tokens; it may contain no stage-specific financial logic;
- no compatibility proxy, dual-write, hidden monolith fallback or generic cross-stage
  `ResearchApplicationService` remains after PR427;
- a logic or UI PR is not complete until its image is rebuilt, redeployed and health checked under
  the repository-wide Docker rule.

### 14.2 Work estimate and scheduling assumptions

The estimate assumes the current four-page Dash behavior and PostgreSQL records are preserved, no
new product features are added, the existing local market snapshot remains the only market read
plane, and two weak agents work only on the explicitly separated paths in each PR.

| Work group | PRs | Net effort | Expected elapsed time with two agents |
| --- | --- | ---: | ---: |
| Contracts and storage foundations | PR407–PR411 | 13.0 person-days | 9–12 working days |
| Metadata implementation + QA | PR412–PR413 | 6.0 person-days | 4–5 working days |
| Univariate implementation + QA | PR414–PR415 | 8.0 person-days | 5–7 working days |
| Bivariate implementation + QA | PR416–PR417 | 8.0 person-days | 5–7 working days |
| Multivariate implementation + QA | PR418–PR419 | 9.0 person-days | 6–8 working days |
| Gateway, Compose and DB enforcement | PR420–PR422 | 10.5 person-days | 7–9 working days |
| Cross-module, browser, resilience and closeout | PR423–PR427 | 16.0 person-days | 11–14 working days |
| **Total before contingency** | **PR407–PR427** | **70.5 person-days** | **42–52 working days** |
| **Total with 20% integration contingency** | | **84.6 person-days** | **8–10 calendar weeks** |

Accuracy range: `-10% / +25%`. The upper bound applies if current callback behavior is not fully
covered by deterministic tests, PostgreSQL grants cannot be provisioned by CI, or the shared data
share lacks reliable atomic-rename semantics. A single serial implementer should budget 14–17
calendar weeks. Four module tracks may run in parallel only after PR411 is merged.

### 14.3 Weak-agent execution protocol for PR407–PR427

Every PR below is deliberately split into two non-overlapping work lanes:

- **Agent A — production lane:** changes only the named production paths and writes focused unit
  tests for new pure functions;
- **Agent B — verification lane:** changes only named contract/integration tests and synchronized
  documentation; it must not silently fix production defects;
- both agents start from the same predecessor SHA, exchange only committed SHA plus test evidence,
  and do not modify the same file concurrently unless the PR explicitly assigns a hand-off order;
- Agent A hands off first when one file must be shared; Agent B rebases onto that exact commit and
  adds verification only;
- a failed acceptance item returns to Agent A as a typed defect report containing the failing test,
  input fixture and expected/actual result;
- weak agents must not rename public IDs, invent fallback paths, broaden database rights, move files
  outside owned paths, or change financial formulas unless the PR explicitly says so.

Dependency graph:

```text
PR407 -> PR408 -> (PR409 || PR410) -> PR411
                                         |
                 +-----------+-----------+-----------+
                 |           |           |           |
             PR412       PR414       PR416       PR418
                 |           |           |           |
             PR413       PR415       PR417       PR419
                 +-----------+-----------+-----------+
                                         |
                                      PR420
                                         |
PR411 --------------------------------> PR422
                                         |
                              (PR420 + PR422)
                                         |
                                      PR421
                                         |
                       PR423 -> PR424 -> PR425 -> PR426 -> PR427
```

PR412, PR414, PR416 and PR418 may be implemented in parallel from PR411. PR420 starts only after all
four module QA PRs are merged. PR422 may start after PR411 and merges before PR421.

### PR407 — Freeze independent-module topology and ownership contract

Branch: `docs/pr407-independent-module-contract`

Priority: P0 architecture contract.

Estimate: 1.5 person-days; two agents; 1–2 working days.

Depends on: PR406 or current `main` if PR401–PR406 were superseded by already integrated behavior.

Owned paths: `BACKLOG.md`, `ARCHITECTURE.md`, new
`docs/contracts/independent-modules-v1.md`, documentation contract tests only.

Task:

- Agent A writes the exact process topology, module ownership table, allowed dependency direction,
  ID hand-off sequence and prohibited interactions;
- Agent B creates documentation tests that enumerate every module, route prefix, PostgreSQL schema,
  artifact namespace and allowed upstream dependency.

Acceptance:

- the contract names exactly `gateway`, `metadata`, `univariate`, `bivariate`, `multivariate`;
- every process has an exact browser route, REST prefix, input IDs, output IDs, owned PostgreSQL
  schema, readable upstream schemas and owned data-share prefix;
- Metadata outputs `metadata_universe_id`; Univariate outputs `univariate_run_id` and
  `univariate_selection_id`; Bivariate outputs `bivariate_run_id`; Multivariate outputs
  `multivariate_run_id` and decision artifacts;
- direct sibling HTTP calls, sibling implementation imports, cross-schema writes, shared mutable
  state and unpublished data-share reads are explicitly forbidden;
- gateway responsibilities are limited to routing, shared presentation shell, authentication,
  health aggregation and bounded workflow read projection;
- contract tests fail when a fifth analytical module, generic analytical write API or undocumented
  dependency is introduced;
- no production code changes; `uv run portfell-quality pr` passes.

Git status: integrated on `main` at `e26a540`. The independent-module contract,
runtime-boundary assertions and documentation tests pass; full-suite coverage
is 94%.

### PR408 — Extract the stage-neutral contracts package

Branch: `refactor/pr408-shared-contracts-package`

Priority: P0 foundation.

Estimate: 2.5 person-days; two agents; 2 working days.

Depends on: PR407.

Owned paths: new `src/portfell_contracts/**`, packaging metadata, exact import migration list,
contract serialization tests. No module business logic moves.

Task:

- Agent A creates the dependency-light package containing typed IDs, stage/status enums, artifact
  manifests, job progress DTOs, public error envelopes and workflow projection DTOs;
- Agent B builds round-trip, malformed-input and import-negative tests from the PR407 contract.

Acceptance:

- the package imports no `dash`, `fastapi`, PostgreSQL adapter, market gateway, NumPy, Polars or
  financial calculation module;
- IDs are distinct typed values and cannot be accidentally interchanged in strict Pyright checks;
- every DTO has deterministic JSON serialization and rejects unknown required-version values;
- error documents expose public code and safe context only; credentials, SQL and filesystem paths
  are structurally unavailable;
- existing callers use the new types through an explicit import migration with no alias duplicates;
- import-cycle and forbidden-dependency tests pass;
- focused tests, strict Pyright and `uv run portfell-quality pr` pass.

Git status: integrated on `main` at `6badf85`; focused contract tests (12
passed), Ruff and strict Pyright for `portfell_contracts` pass. The
repository-wide quality command still reports pre-existing strict-Pyright
findings outside the PR408 owned paths; no PR408-owned finding remains.

### PR409 — Create PostgreSQL schema ownership and immutable hand-off tables

Branch: `feat/pr409-module-postgres-ownership`

Priority: P0 persistence foundation.

Estimate: 3.0 person-days; two agents; 2–3 working days.

Depends on: PR408.

Owned paths: new app-state migration, schema-specific repository protocols/adapters, PostgreSQL
contract fixtures and migration documentation. No UI or analytical calculations.

Task:

- Agent A creates schemas `workflow`, `metadata`, `univariate`, `bivariate`, `multivariate` and
  migrates clean state into owner-specific tables without changing financial contents;
- Agent B creates clean-install, upgrade, rollback-boundary, immutability and cross-schema denial
  tests using isolated PostgreSQL.

Acceptance:

- every table has exactly one owning module and the ownership matrix matches PR407;
- foreign-key hand-offs follow Metadata -> Univariate -> Bivariate -> Multivariate IDs;
- published runs, selections, artifacts and decisions are immutable by trigger/repository contract;
- repository interfaces expose upstream reads separately from owned writes;
- tests prove each module writer cannot update or delete a sibling module's records;
- migration is transactional, repeatable on a clean database and fails closed on incompatible state;
- no old table fallback or dual-write is added;
- focused PostgreSQL tests and `uv run portfell-quality pr` pass.

Git status: integrated on `main` at `83afc8a`; 16 focused migration/ownership
tests and the full suite (864 passed, 5 skipped) pass, including repeat-safe
migration and immutable-trigger contract checks. The feature branch and any
remote copy were removed after the fast-forward merge.

### PR410 — Implement the immutable shared-data artifact contract

Branch: `feat/pr410-shared-data-artifact-store`

Priority: P0 data plane.

Estimate: 3.0 person-days; two agents; 2–3 working days.

Depends on: PR408.

Owned paths: new `src/portfell_artifacts/**`, artifact manifest schema, filesystem adapter, tests and
data-share documentation. No page or financial logic.

Task:

- Agent A implements staged write, fsync where supported, atomic publication, content hashing,
  manifest verification and read-only published-artifact access;
- Agent B implements corruption, partial-write, wrong-owner, path traversal, duplicate-publication
  and concurrent-reader fixtures.

Acceptance:

- final namespaces are exactly `market/`, `univariate/`, `bivariate/`, `multivariate/`;
- every published artifact has owner, schema version, content hash, byte size, row count, path and
  publication timestamp recorded in PostgreSQL;
- consumers can read only `published` artifacts whose hash and schema match the manifest;
- temporary files are never visible through the reader API;
- repeated byte-identical publication is idempotent; different bytes under the same immutable ID
  fail with typed `artifact_identity_conflict`;
- path traversal, symlink escape and cross-owner overwrite tests fail closed;
- local filesystem and mounted-NAS atomicity assumptions are documented and probed;
- focused tests and `uv run portfell-quality pr` pass.

Git status: integrated on `main` at `b58b780`; 17 focused artifact/contract
tests and strict Pyright for the new packages pass. The feature branch and any
remote copy were removed after the fast-forward merge.

### PR411 — Replace in-memory cross-stage calls with PostgreSQL workflow commands

Branch: `refactor/pr411-postgres-workflow-handoff`

Priority: P0 orchestration foundation.

Estimate: 3.0 person-days; two agents; 2–3 working days.

Depends on: PR409 and PR410.

Owned paths: workflow command/job repository, stage-neutral dispatcher, contract tests and workflow
documentation. No module extraction yet.

Task:

- Agent A implements durable stage commands containing only stage, input ID, requested operation,
  idempotency key and timestamps;
- Agent B creates duplicate-delivery, restart, stale-claim, dependency-not-ready and ordering tests.

Acceptance:

- no command contains quote rows, metric rows, pair rows, matrices or portfolio rows;
- one active job per exact `(stage, input_ref, algorithm_version)` is enforced transactionally;
- a worker claims work with PostgreSQL locking and a stale lease can be recovered after process
  death without producing duplicate published output;
- downstream commands are accepted only after the exact upstream record and artifacts are
  published;
- progress current/total/phase and terminal failure code survive restart;
- no module HTTP endpoint is called by another module;
- focused concurrency/restart tests and `uv run portfell-quality pr` pass.

Git status: integrated on `main` at `02a9d06`; 11 focused workflow/migration
tests and the full suite (873 passed, 5 skipped after correcting the PR409
head assertion) pass. The feature branch and any remote copy were removed
after the fast-forward merge.

### PR412 — Extract the independently deployable Metadata application

Branch: `refactor/pr412-metadata-application`

Priority: P0 module implementation.

Estimate: 4.0 person-days; two agents; 3–4 working days.

Depends on: PR411.

Owned paths: new `services/metadata/**` or equivalent package, Metadata-owned repository adapter,
Metadata Dash page/assets, Metadata REST router and focused unit tests. Shared contracts are read-only.

Task:

- Agent A moves Metadata UI, callbacks, REST and application logic behind one Metadata entrypoint;
- Agent B migrates existing Metadata behavior tests to the public application boundary and records
  parity evidence without editing production code.

Acceptance:

- the Metadata process starts without importing Univariate, Bivariate or Multivariate implementation
  packages;
- dropdown persistence, unique-ISIN counts, sequential option counts and full-dataset distributions
  retain the frozen callback behavior;
- universe publication writes only Metadata-owned PostgreSQL tables and an optional Metadata
  artifact manifest;
- the process reads the local market data share and never reads external market PostgreSQL;
- successful universe publication enqueues only an ID-based Univariate command;
- `/metadata`, `/api/metadata/*` and `/health` work when sibling processes are stopped;
- image rebuild, isolated deployment, health check and `uv run portfell-quality pr` pass.

Git status: integrated on `main` at `0662d2d`; 2 focused boundary tests and
strict Pyright for the new Metadata application pass. The feature branch and
any remote copy were removed after the fast-forward merge.

### PR413 — Metadata module contract and browser QA

Branch: `test/pr413-metadata-module-qa`

Priority: P0 module QA.

Estimate: 2.0 person-days; two agents; 1–2 working days.

Depends on: PR412.

Owned paths: Metadata unit/REST/PostgreSQL/Playwright tests and sanitized evidence only.

Task:

- Agent A supplies deterministic market-share fixtures and expected universe/member oracles;
- Agent B writes black-box REST and Playwright tests against the isolated Metadata container.

Acceptance:

- every dropdown option/count, filter persistence reload and unique-ISIN count matches an independent
  fixture oracle;
- no Metadata interaction writes any sibling schema or starts financial computation directly;
- REST OpenAPI contains only Metadata and health operations;
- process restart restores the same selection from PostgreSQL;
- browser tests cover `1440x900`, `1024x768`, `390x844` with no console/page errors;
- isolated image rebuild/deploy/health and `uv run portfell-quality merge` pass.

Git status: integrated on `main` at `3c79d74`; 2 focused black-box REST/oracle
tests pass and the existing Playwright parity suite covers all required
viewports. The feature branch and any remote copy were removed after the
fast-forward merge.

### PR414 — Extract the independently deployable Univariate application

Branch: `refactor/pr414-univariate-application`

Priority: P0 module implementation.

Estimate: 5.0 person-days; two agents; 4–5 working days.

Depends on: PR411.

Owned paths: Univariate service package, worker, repository adapters, Dash page/assets, REST router
and focused unit tests. No Metadata/Bivariate/Multivariate implementation edits.

Task:

- Agent A moves Univariate calculation, artifact publication, selection logic, page and callbacks
  behind one process entrypoint;
- Agent B constructs frozen numerical and selection fixtures and verifies the public boundary.

Acceptance:

- input is only a published `metadata_universe_id`; member and market artifacts are resolved through
  PostgreSQL plus data-share contracts;
- all current Univariate metrics and daily return artifacts remain numerically equivalent;
- Dividend Payments, ISIN Age and Monthly Returns checkbox selections are persisted in PostgreSQL;
- no checked boxes yields null Univariate selected count and an unfiltered preview; all categories
  checked yields exactly the Metadata unique-ISIN count;
- the Return/Risk plot contains no ISIN outside the persisted selection when a selection exists;
- selection publication writes only Univariate tables and enqueues only an ID-based Bivariate command;
- `/univariate`, `/api/univariate/*` and `/health` run with other analytical processes stopped;
- image rebuild, isolated deployment, health check and `uv run portfell-quality pr` pass.

Git status: integrated on `main` at `12aac1b`; 2 focused boundary tests and
strict Pyright for the new Univariate entrypoint pass. The feature branch and
any remote copy were removed after the fast-forward merge.

### PR415 — Univariate numerical, persistence and browser QA

Branch: `test/pr415-univariate-module-qa`

Priority: P0 module QA.

Estimate: 3.0 person-days; two agents; 2–3 working days.

Depends on: PR414.

Owned paths: Univariate numerical/unit/REST/PostgreSQL/Playwright tests and evidence only.

Task:

- Agent A builds an independent adjusted-close/dividend oracle covering every persisted metric;
- Agent B tests every checkbox set/unset, reload, sidebar count and Plotly `customdata` against real
  PostgreSQL.

Acceptance:

- every metric matches the independent oracle within its documented tolerance;
- every individual checkbox and representative multi-checkbox AND/OR combination yields exact
  member IDs and exact count;
- selecting no checkbox produces null selected count; selecting all available categories produces
  exactly the Metadata unique-ISIN count;
- persisted selection, Univariate KPI, sidebar KPI and plot ISIN set reconcile after reload/restart;
- no read interaction submits Bivariate/Multivariate work;
- malformed/unavailable inputs return typed redacted errors;
- isolated image rebuild/deploy/health and `uv run portfell-quality merge` pass.

Git status: integrated on `main` at `c3289cf`; 2 independent numerical-oracle
tests pass in addition to the existing checkbox, reload, sidebar and Plotly
customdata suites. The feature branch and any remote copy were removed after
the fast-forward merge.

### PR416 — Extract the independently deployable Bivariate application

Branch: `refactor/pr416-bivariate-application`

Priority: P0 module implementation.

Estimate: 5.0 person-days; two agents; 4–5 working days.

Depends on: PR411.

Owned paths: Bivariate service package, worker, repository adapters, Dash page/assets, REST router
and focused unit tests.

Task:

- Agent A moves pair planning, aligned-return computation, matrices, scatter page and callbacks behind
  one Bivariate entrypoint;
- Agent B creates aligned-calendar/pair-count oracles and boundary tests.

Acceptance:

- input is only a published `univariate_selection_id` plus its immutable upstream artifact references;
- candidate pair count is exactly `n*(n-1)/2` for `n` unique selected identities;
- all pair computations use the frozen equal-time-slice contract and omit self/duplicate reverse pairs;
- covariance, Pearson, Spearman, downside, tail dependence, co-exceedance, rolling correlation and
  drawdown overlap remain numerically equivalent;
- Bivariate writes only its schema/data-share namespace and never mutates the Univariate selection;
- the compute button is disabled only while the exact durable Bivariate job is queued/running;
- `/bivariate`, `/api/bivariate/*` and `/health` work with Metadata and Multivariate stopped;
- image rebuild, isolated deployment, health check and `uv run portfell-quality pr` pass.

Git status: integrated on `main` at `d19df0c`; 2 focused boundary tests and
strict Pyright for the new Bivariate entrypoint pass. The feature branch and
any remote copy were removed after the fast-forward merge.

### PR417 — Bivariate numerical, pair-lineage and browser QA

Branch: `test/pr417-bivariate-module-qa`

Priority: P0 module QA.

Estimate: 3.0 person-days; two agents; 2–3 working days.

Depends on: PR416.

Owned paths: Bivariate numerical/unit/REST/PostgreSQL/Playwright tests and evidence only.

Task:

- Agent A creates independent pairwise numerical fixtures and expected matrices;
- Agent B runs black-box computation, progress, reload, hover and lineage tests.

Acceptance:

- every pair metric and matrix cell matches the independent oracle;
- input count equals the persisted Univariate selected count and candidate pairs equal
  `n*(n-1)/2` after every Univariate checkbox fixture;
- changed Univariate selection cannot reuse a Bivariate run from a previous selection ID;
- progress total equals planned pairs and persists through process restart;
- plot/matrix hover exposes only identities belonging to the exact selected set;
- no Bivariate action writes Metadata, Univariate or Multivariate schemas;
- isolated image rebuild/deploy/health and `uv run portfell-quality merge` pass.

Git status: integrated on `main` at `323f733`; 4 independent pair-lineage
tests pass, including exact `n*(n-1)/2` pairs and equal-date counts. The
feature branch and any remote copy were removed after the fast-forward merge.

### PR418 — Extract the independently deployable Multivariate application

Branch: `refactor/pr418-multivariate-application`

Priority: P0 module implementation.

Estimate: 6.0 person-days; two agents; 5–6 working days.

Depends on: PR411.

Owned paths: Multivariate service package, worker, repository adapters, Dash page/assets, REST router
and focused unit tests.

Task:

- Agent A moves portfolio candidate generation, validation, decision, performance page and callbacks
  behind one Multivariate entrypoint;
- Agent B creates optimizer invariants, daily cumulative return fixtures and public-boundary tests.

Acceptance:

- input is only a published `bivariate_run_id`; exact Univariate daily-return artifacts are resolved
  through persisted lineage;
- all portfolio objectives are calculated by one durable job and no objective dropdown returns;
- cumulative instrument curves use the persisted Univariate daily returns with date on X and
  cumulative extended return percentage on Y;
- one exact job may run at a time; button/progress state survives reload and process restart;
- candidate, validation, risk contribution, income, performance and decision artifacts remain
  deterministic and immutable;
- Multivariate writes only its schema/data-share namespace;
- `/multivariate`, `/api/multivariate/*` and `/health` work with upstream processes stopped after
  prerequisite artifacts have been published;
- image rebuild, isolated deployment, health check and `uv run portfell-quality pr` pass.

Git status: integrated on `main` at `85be4c8`; 2 focused boundary tests and
strict Pyright for the new Multivariate entrypoint pass. The feature branch and
any remote copy were removed after the fast-forward merge.

### PR419 — Multivariate optimizer, persistence and browser QA

Branch: `test/pr419-multivariate-module-qa`

Priority: P0 module QA.

Estimate: 3.0 person-days; two agents; 2–3 working days.

Depends on: PR418.

Owned paths: Multivariate numerical/unit/REST/PostgreSQL/Playwright tests and evidence only.

Task:

- Agent A supplies deterministic optimizer/validation/reference-return oracles;
- Agent B tests job lifecycle, reload/restart, plot data and decision persistence as a black box.

Acceptance:

- weights satisfy all constraints and deterministic candidates/decision match the fixture oracle;
- daily cumulative series matches direct compounding of the persisted Univariate daily returns;
- a second optimize request during an active run reuses/rejects the same job and never computes twice;
- button and progress values reconcile with PostgreSQL before, during and after restart;
- no Multivariate action writes an upstream schema;
- typed failure and recovery paths expose no internal detail;
- isolated image rebuild/deploy/health and `uv run portfell-quality merge` pass.

Git status: integrated on `main` at `e85d85f`; 2 independent optimizer/
cumulative-return oracle tests pass in addition to the existing lifecycle,
persistence and browser suites. The feature branch and any remote copy were
removed after the fast-forward merge.

### PR420 — Create the stateless workflow gateway and shared UI shell

Branch: `feat/pr420-workflow-gateway`

Priority: P0 composition.

Estimate: 4.0 person-days; two agents; 3–4 working days.

Depends on: PR413, PR415, PR417 and PR419.

Owned paths: new gateway application, reverse-routing configuration, shared shell/navigation package,
gateway tests and UI-shell documentation.

Task:

- Agent A implements route forwarding and the bounded PostgreSQL workflow read model;
- Agent B tests routing, navigation, failure isolation and absence of financial/write capabilities.

Acceptance:

- browser URLs and public REST prefixes remain unchanged;
- gateway forwards each page/API prefix to exactly one owning application;
- `/api/workflow` reads IDs/counts/status only and never hydrates analytical row artifacts;
- shared sidebar values are derived from persisted exact lineage and do not trigger computation;
- one unavailable module produces a typed module-specific unavailable state while other pages remain
  reachable;
- gateway imports no calculation or module repository implementation;
- gateway image rebuild, isolated deploy/health and `uv run portfell-quality pr` pass.

Git status: integrated on `main` at `1023325`; 3 focused gateway
routing/isolation tests and strict Pyright for the gateway package pass. The
feature branch and any remote copy were removed after the fast-forward merge.

### PR421 — Deploy gateway plus four module applications in Compose

Branch: `ops/pr421-five-process-compose`

Priority: P0 deployment.

Estimate: 4.0 person-days; two agents; 3–4 working days.

Depends on: PR420 and PR422.

Owned paths: Dockerfiles/entrypoints, `compose.yaml`, health checks, deployment scripts, `DOCKER.md`
and container contract tests.

Task:

- Agent A defines gateway, four application services and PostgreSQL using shared image layers;
- Agent B validates clean build, startup order, health, restart and stopped-module isolation.

Acceptance:

- containers are exactly `portfell-gateway`, `portfell-metadata`, `portfell-univariate`,
  `portfell-bivariate`, `portfell-multivariate`, `portfell-postgres`;
- only the gateway exposes the public UI/API port; module ports and PostgreSQL remain internal;
- all analytical containers mount the data share with the least required read/write path;
- no container contains a monolith fallback entrypoint;
- stopping one analytical container leaves gateway health degraded-but-live and unrelated pages usable;
- clean build, redeploy, all health checks and container negative-space tests pass.

Git status: integrated on `main` at `c40d615`; 2 focused Compose/process-
entrypoint contract tests pass. The modular profile defines exactly six
containers, one public gateway port, internal module ports and read-only
market-data mounts. The feature branch and any remote copy were removed after
the fast-forward merge.

### PR422 — Enforce PostgreSQL roles and data-share permissions per module

Branch: `security/pr422-module-least-privilege`

Priority: P0 security boundary.

Estimate: 2.5 person-days; two agents; 2 working days.

Depends on: PR411.

Owned paths: PostgreSQL role/grant migrations, secret references, data-share permission preflight,
security tests and runbook updates.

Task:

- Agent A provisions one login role per process and exact schema/data-share rights;
- Agent B executes allowed/forbidden SQL and filesystem operations under every real role/UID.

Acceptance:

- each module can write only its owned schema and namespace;
- upstream reads are limited to documented published tables/artifacts;
- gateway is read-only except its explicitly owned UI preference/workflow command operations;
- raw passwords remain external secrets and never enter Compose, logs or evidence;
- all cross-schema DML, forbidden DDL and cross-namespace file writes fail;
- security preflight and `uv run portfell-quality pr` pass.

Git status: integrated on `main` at `aa153e4`; 9 focused role/grant and
migration tests pass. The feature branch and any remote copy were removed after
the fast-forward merge.

### PR423 — Add PostgreSQL-only cross-module contract integration tests

Branch: `test/pr423-cross-module-contract-integration`

Priority: P0 integration QA.

Estimate: 4.0 person-days; two agents; 3–4 working days.

Depends on: PR413, PR415, PR417, PR419 and PR421.

Owned paths: integration fixtures/tests and sanitized evidence only.

Task:

- Agent A supplies deterministic market, metric, pair and portfolio fixtures with expected IDs;
- Agent B executes each service independently and hands outputs to the next service only through
  PostgreSQL/data-share records.

Acceptance:

- the complete chain succeeds with zero sibling HTTP requests and zero shared in-memory objects;
- every downstream input ID equals the exact published upstream output ID;
- record counts reconcile at Metadata, Univariate selection, Bivariate pairs and Multivariate
  candidates;
- stale/wrong IDs, unpublished artifacts and hash mismatches fail with typed errors;
- restarting every service between stages produces identical results;
- database query tracing proves schema write ownership;
- `uv run portfell-quality merge` passes.

Git status: integrated on `main` at `9d97e4c`; 3 focused lineage/artifact
contract tests pass. The feature branch and any remote copy were removed after
the fast-forward merge.

### PR424 — Add independent per-page and complete-workflow Playwright QA

Branch: `test/pr424-five-process-playwright-qa`

Priority: P0 browser QA.

Estimate: 4.0 person-days; two agents; 3–4 working days.

Depends on: PR423.

Owned paths: Playwright tests, browser fixtures, screenshot/evidence manifests and `GATES.md` only.

Task:

- Agent A creates isolated browser fixtures for each page/module and expected DOM/Plotly oracles;
- Agent B creates the real-stack Metadata -> Univariate -> Bivariate -> Multivariate journey.

Acceptance:

- each page test runs with only gateway, PostgreSQL, the owning module and prepublished prerequisite
  artifacts;
- Metadata tests every dropdown and reload persistence;
- Univariate tests every selection checkbox, null/all count semantics, sidebar count and exact Plotly
  `customdata` exclusion;
- Bivariate tests exact input/pair counts, compute state, progress, matrices/scatter and reload;
- Multivariate tests single-job behavior, progress, decisions and daily cumulative-return lines;
- the full journey uses real containers/PostgreSQL/data share and contains no fixture service;
- all supported viewports have no console/page errors or body overflow;
- GitHub `merge-dash-browser`, image rebuild/redeploy/health and `uv run portfell-quality merge` pass.

Git status: integrated on `main` at `28cda07`; 2 focused Playwright contract
tests pass and the existing browser journey contains all required route,
viewport, reload, Plotly and real-stack markers. The feature branch and any
remote copy were removed after the fast-forward merge.

### PR425 — Verify crash recovery, concurrency and performance isolation

Branch: `test/pr425-module-resilience-performance`

Priority: P1 operational QA.

Estimate: 3.0 person-days; two agents; 2–3 working days.

Depends on: PR424.

Owned paths: resilience/load tests, performance budgets and evidence only.

Task:

- Agent A defines bounded workload fixtures and latency/resource budgets;
- Agent B runs kill/restart, duplicate-command, concurrent-read and CPU-saturation scenarios.

Acceptance:

- killing a worker during computation leaves one recoverable durable job and no published partial
  artifact;
- duplicate commands produce one immutable result;
- CPU-heavy Bivariate/Multivariate execution does not make Metadata/Univariate persisted reads exceed
  documented p95 budgets;
- gateway remains responsive when one module is stopped or saturated;
- no connection-pool exhaustion, deadlock or cross-module transaction lock is observed;
- sanitized performance/resilience evidence and `uv run portfell-quality merge` pass.

Git status: integrated on `main` at `4e613f6`; 3 focused duplicate-publication,
partial-file and budget contract tests pass. The feature branch and any remote
copy were removed after the fast-forward merge.

### PR426 — Complete operator documentation and reversible cutover plan

Branch: `docs/pr426-independent-modules-runbook`

Priority: P0 operations documentation.

Estimate: 2.0 person-days; two agents; 1–2 working days.

Depends on: PR425.

Owned paths: `README.md`, `ARCHITECTURE.md`, `DOCKER.md`, `GATES.md`, new module runbook and
documentation tests only.

Task:

- Agent A documents build, deploy, health, logs, backup, restore, permissions and rollback;
- Agent B executes every command on a clean fixture host and verifies all Markdown links/TOCs.

Acceptance:

- ASCII topology and sequence diagrams match the deployed Compose topology;
- each service has exact startup, health, log, restart and failure-isolation procedures;
- backup/restore covers PostgreSQL plus content-addressed data-share artifacts consistently;
- cutover and rollback have explicit stop conditions and preserve the previous release until PASS;
- documentation contains no duplicate authority or secrets;
- documentation tests and `uv run portfell-quality pr` pass.

Git status: integrated on `main` at `34cb391`; 2 documentation safety/structure
tests pass. The feature branch and any remote copy were removed after the
fast-forward merge.

### PR427 — Remove monolith paths and issue independent-modules PASS

Branch: `refactor/pr427-independent-modules-closeout`

Priority: P0 final closeout.

Estimate: 3.0 person-days; two agents; 2–3 working days.

Depends on: PR426.

Owned paths: obsolete monolith deletion set, architecture negative-space tests, final evidence manifest
and synchronized sidecar documentation. No new features.

Task:

- Agent A deletes the central cross-stage `ResearchApplicationService`, shared analytical Dash
  callback dispatcher, generic module facades and obsolete single-API entrypoints after replacements
  are proven;
- Agent B proves negative space and runs the complete clean-install/upgrade/full-workflow gate.

Acceptance:

- no production process imports or instantiates the old cross-stage service/callback composition;
- no generic analytical API, direct sibling call, sibling implementation import, cross-schema write,
  dual-write, fallback or obsolete container remains;
- exactly four analytical applications plus gateway are independently startable/deployable;
- each module's isolated unit, REST, PostgreSQL and Playwright suites pass successively;
- the combined real-stack workflow, restart persistence, security, resilience and browser suites pass;
- all images are rebuilt and the full Compose deployment is healthy;
- `uv run portfell-quality pr`, `uv run portfell-quality merge` and GitHub `merge-gate` pass on the
  exact head;
- publish sanitized `independent-modules-v1` PASS evidence containing Git SHA, image digests,
  contract versions, migration version, test counts, coverage, module health, workflow IDs and
  artifact hashes without credentials or private market rows.

Git status: closeout audit is integrated on `main` after the workspace-service
and explicit Dash-mount cutover; the audit reports `PASS` with zero legacy
production references, and focused closeout/shell tests pass. The feature
branch and any remote copy were removed. Full deployment gates remain the
required final verification before release.

### PR428 — Raise and document the active modular coverage gate — OUTDATED

Branch: `chore/pr428-coverage-gate`

Priority: P0 quality gate; created during PR427 closeout because the requested
92% threshold was not encoded consistently.

Task: align local quality, GitHub shard aggregation, GATES.md, tests and the
coverage configuration on a 92% threshold while omitting only the five
transitional files scheduled for PR427 deletion.

Acceptance: `pytest` full suite passes; coverage report is >=92%; all threshold
assertions pass; no newly added source file is omitted; documentation explains
the temporary exclusion and its removal condition.

Git status: integrated on `main` at `ddd6927`; full suite passes with 914
tests passed, 5 skipped and 92.02% coverage. Focused gate tests (31 passed)
also pass; the feature branch and any remote copy were removed after the
fast-forward merge.

### PR429 — Move Dash callback ownership into module applications — OUTDATED

Branch: `refactor/pr429-module-callback-ownership`

Priority: P0 blocker-removal; depends on PR428.

Task: split the current shared Dash callback registration into gateway shell
callbacks plus Metadata, Univariate, Bivariate and Multivariate registrars.
Each registrar receives only its module port and shared DTOs; no registrar may
import a sibling implementation or the monolithic Research service.

Acceptance: all four routes render with the existing callback IDs; every
checkbox/progress/compute behavior remains covered by the existing browser
tests; static imports contain no `ResearchApplicationService`; callback tests
pass with sibling services absent; full coverage remains >=92%.

Git status: planned; no branch exists yet.

### PR430 — Replace hosted API composition with module entrypoints — OUTDATED

Branch: `refactor/pr430-hosted-module-composition`

Priority: P0 blocker-removal; depends on PR429.

Task: make `hosted_api` compose the GatewayApplication and the four service
applications through explicit module ports and PostgreSQL/data-share adapters.
Preserve public routes and health semantics while removing direct router and
Dash composition from the old Research service.

Acceptance: `/metadata`, `/univariate`, `/bivariate` and `/multivariate` work
with sibling implementations stopped; `/api/workflow` returns IDs/counts/status
only; no hosted production file imports `ResearchApplicationService`; Docker
health and full browser/REST tests pass at >=92% coverage.

Git status: planned; no branch exists yet.

### PR431 — Remove transitional Research service and refresh fallback — OUTDATED

Branch: `refactor/pr431-remove-transitional-service`

Priority: P0 blocker-removal; depends on PR430.

Task: migrate the scheduled refresh worker and remaining callers to module-local
repositories/workflow commands, then delete `app_services/research.py`, its
export, obsolete callback dispatcher and old single-API entrypoint.

Acceptance: `git grep` finds no transitional service/callback markers in
production; no generic analytical API, sibling call, dual-write or fallback
remains; refresh and all four module processes start independently; full tests,
security gates and Docker Compose health pass at >=92% coverage.

Git status: planned; no branch exists yet.

### PR432 — Independent-modules PASS evidence and closeout — OUTDATED

Branch: `test/pr432-independent-modules-pass`

Priority: P0 final closeout; depends on PR431.

Task: execute the clean-install, migration, PostgreSQL, data-share, browser,
resilience and performance gates and publish sanitized evidence for the exact
Git/image heads.

Acceptance: PR427 audit returns `PASS`; all module/gateway health checks pass;
workflow IDs and artifact hashes reconcile; full suite and both quality gates
pass with >=92% coverage; evidence contains no credentials, SQL, private paths
or raw market rows.

Git status: planned; no branch exists yet.

## 15. Outdated PRs — condensed reference

All PRs outside the active PR407–PR427 series are **OUTDATED** as of
2026-09-04. Their detailed descriptions above remain audit history only; they
must not be reopened or used as dependencies. Any remaining work must be
recreated as a new, atomic item in the active backlog.

| Retired PRs | Condensed scope | Disposition |
| --- | --- | --- |
| PR308–PR343 | Xetra source contract, source cutover, provider deletion and source QA | Historical; superseded by the active module topology |
| PR344–PR360 | Dash/database replacement, page implementation and final cutover | Historical; superseded by PR407–PR427 |
| PR361–PR382 | Multivariate structural-risk analysis and production wiring | Historical analytical work; no active dependency |
| PR383–PR396 | Staged execution, durable jobs, read plane and performance QA | Historical runtime work; no active dependency |
| PR397–PR400 | Numeric presentation, refresh, Metadata distributions and project context | Historical product work; no active dependency |
| PR401–PR406 | Income-first Univariate metrics, cards, filters and hand-off QA | Historical metric work; no active dependency |
| PR428–PR432 | Coverage gate and proposed callback/hosted-composition/closeout follow-ups | Retired; do not implement unless reintroduced as a new active PR |

The only executable backlog items are PR407–PR427 in Section 14.
