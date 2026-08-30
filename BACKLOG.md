# Portfell — Authoritative Backlog

Last reviewed: 2026-08-30

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

## 3. Source cutover and simplification series — PR308–PR343

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
- PR324–PR331 are all integrated on `main`; the final sibling PR331 is recorded at `b13eb0f`. Provider acquisition, legacy medallion/filesystem market authority, shared refresh, hosted download lifecycle, provider credentials, provider UI controls, and the residual hosted local-market runtime are removed from the active source-cutover runtime.
- PR332 is integrated on `main` at `7a980af`; provider-removal negative-space QA covers executable module/CLI inventories, OpenAPI lifecycle surface, and the market-SQL boundary.
- PR333 is implemented in GitHub PR #499 (`refactor/pr333-single-user-backend`, head `97c25be`). Production composition is frozen to one canonical workspace principal and no longer composes a hosted-user lifecycle repository. The PR is mergeable but unmerged: merge-gate run #308 (`33312194083`) fails all 14 jobs before any executable step is reported (`steps=null`), so no PASS is recorded.
- PR334 is implemented in GitHub PR #500 (`refactor/pr334-freeze-legacy-ui`, head `e0b8a23`). The transitional browser shell now uses canonical `/metadata`, `/univariate`, `/bivariate`, `/multivariate` routes with no project selector/switching; obsolete two-project browser coverage is replaced by single-workspace route/navigation regression coverage. The PR is mergeable but unmerged: merge-gate run #309 (`33312411773`) has the same pre-step infrastructure failure and no PASS is recorded.
- PR335 and every later work order remain intentionally unstarted until PR333 and PR334 are both integrated, as required by the merged-predecessor rule in section 2.
- The external xetra-loader production V2 artifact gate is cleared: `artifacts/acceptance/postgres-full-sync-v2.json` exists on xetra-loader `main` and reports `status: PASS`. PR340 is therefore no longer blocked by the external artifact itself, but it still cannot start until PR339 is merged.

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

Git status: integrated on `main` at `d1e3b5e`. The low-cost preflight verifies database/schema/role membership, exact source table catalog, and reader-role membership without reading source data, scanning tables, accessing the sync schema, or issuing DDL; its complete PR gate passed (`1017 passed`).

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

  Git status: integrated on `main` at `893af0e`; local Docker Node validation passes (19/19
  unit tests, TypeScript check, and production build).
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

External artifact gate: cleared on 2026-08-30. `artifacts/acceptance/postgres-full-sync-v2.json` exists on xetra-loader `main` and reports `status: PASS`. Do not start PR340 until PR339 is merged.

Acceptance: verify exact loader SHA/endpoint/database; use secret-supplied non-superuser LOGIN member; SELECT exact four business tables; representative rows through gateway; market DML/DDL fails; sync access fails and counts as PASS; sanitized evidence; full gate.

### PR341 — PostgreSQL-only source E2E

Branch: `test/pr341-postgres-only-source-e2e`

Depends on: PR340.

Acceptance: cold start without provider/NAS/medallion/xetra-loader Python package; full Metadata -> Uni -> Bi -> Multi; all market reads gateway-only; unavailable/empty/partial/missing-adjusted fail closed; duplicate ISIN full identity; snapshot lineage contains no provider/download/sync identity; repeated workflow leaves market tables unchanged; full gate.

### PR342 — Source cutover runbook

Branch: `docs/pr342-market-source-cutover-runbook`

Depends on: PR341.

Scope: preflight DSNs/tables/role/UTC/read-only; back up surviving application/analytical state only; legacy market files are disposable and never migrated; smoke four routes; rollback application/config only and never reactivate provider acquisition or broader grants.

### PR343 — Source-series closeout and Dash handoff

Branch: `docs/pr343-source-series-closeout`

Depends on: PR342.

Scope: freeze the exact merged source/runtime contracts that PR344 consumes; classify old PR264–PR295 UI/product ideas as `reuse-cleanly`, `reimplement-in-dash`, or `retire`; do **not** create a second backlog file and do not resurrect React-era architecture.

Acceptance: one checked-in handoff records exact source gateway API, application service API, persisted analytical concepts, four-page workflow, objective set (`return_risk`, `return_drawdown`, `minimum_risk`), professional plot requirements, Universe & History requirements, the Plotly visual-reference contract from section 1.6, and the deletion inventory seed used by PR344.

## 4. Plotly Dash + clean database full-replacement series — PR344–PR360

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

Owned paths: `BACKLOG.md`, new `docs/contracts/plotly-dash-replacement-v1.md`, new `docs/contracts/plotly-dash-ui-v1.md`, new `docs/contracts/legacy-ui-db-inventory-v1.json`, focused contract tests only.

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

Owned paths: new `src/portfell/app_state/**` repositories/contracts except migrations; focused tests.

Tasks: implement typed repositories for every PR345 concept; parameterized SQL only; no import from legacy hosted PostgreSQL repository modules; no market SQL.

Acceptance: create/read/list exact immutable revisions, stage-run lifecycle, selection membership, artifacts, decision artifacts, preferences; transaction rollback tests; restart tests; no user/project/tenant scope; no legacy table reference; PR gate passes.

Security: repository errors are typed/redacted; no SQL in public UI errors.

Determinism: stable ordering and canonical serialization for all list/read methods.

Idempotency: repeated insert-by-content identity converges to the same immutable row or typed conflict.

### PR347 — Application services cut over to new state DB

Branch: `refactor/pr347-app-services-portfell-dash-db`

Depends on: PR346.

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
