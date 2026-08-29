# Portfell — Authoritative Backlog

Last reviewed: 2026-08-29

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

Git status: in progress from `main` at `e72415a`; the prior 451-file worktree report was
identical executable-bit metadata noise with no content changes.

Scope: `eod_quotes` repository with full identity, inclusive date range, exact fields and `Decimal` values.

Acceptance: stable identity+trade_date ordering; duplicate key raises frozen typed error; UTC/date semantics; bounded query count including 501-identity test; no adjusted-close fallback.

### PR311 — Dividend repository

Branch: `feat/pr311-xetra-dividends-repository`

Depends on: PR308.

Git status: in progress from `main` at `e72415a`; the prior 451-file worktree report was
identical executable-bit metadata noise with no content changes.

Scope: full-identity/batched/inclusive-date reads from `dividends`.

Acceptance: preserve `event_key`, nullable/Decimal fields, stable identity/event_date/event_key ordering, same-day events, bounded queries, no writes/fallback.

### PR312 — Split repository

Branch: `feat/pr312-xetra-splits-repository`

Depends on: PR308.

Git status: in progress from `main` at `e72415a`; the prior 451-file worktree report was
identical executable-bit metadata noise with no content changes.

Scope: same repository contract for `splits`.

Acceptance: preserve textual `split_ratio`, optional Decimal split factor, no local event-key generation, stable ordering/batching, no split-return calculation.

### PR313 — Low-cost source status

Branch: `feat/pr313-market-source-status`

Depends on: PR308.

Git status: in progress from `main` at `e72415a`; the prior 451-file worktree report was
identical executable-bit metadata noise with no content changes.

Scope: low-cost connectivity/schema/role preflight only.

Acceptance: no full scans, no global max-timestamp freshness inference, no sync-schema access, no DDL.

### PR314 — Analytical projection boundary

Branch: `refactor/pr314-market-source-projection`

Depends on: PR308.

Git status: in progress from `main` at `e72415a`; the prior 451-file worktree report was
identical executable-bit metadata noise with no content changes.

Scope: one centralized mapping from raw market DTOs to analytical inputs.

Acceptance: `Decimal` conversion is centralized; missing adjusted close is typed; dividends not double-counted; no split return transform; regression fixtures preserve existing valid formulas.

### PR315 — MarketDataGateway and coherent snapshot

Branch: `feat/pr315-market-data-gateway`

Depends on: PR309–PR314.

Scope: only stage-level market seam; one coherent repeatable-read/read-only snapshot across required tables; batch reads only.

Acceptance: market SQL only under `market_source`; transaction closes after materialization; no sync/write/refresh/download operations; concurrency fixture proves coherent snapshot.

### PR316 — Source contract QA

Branch: `test/pr316-market-source-contract-qa`

Depends on: PR315.

Scope: QA only. Build a contract-faithful PostgreSQL fixture with NOLOGIN group-role semantics and exact table types/keys.

Acceptance: role/read-only checks, 1001 batching, repeatable-read concurrency, projection behavior, sync/provider negative-space; `uv run portfell-quality merge` passes.

### PR317 — Hosted runtime read-plane cutover

Branch: `refactor/pr317-hosted-market-read-plane`

Depends on: PR316.

Scope: remove provider acquisition capabilities/provider-key arguments from hosted runtime ports and wire `MarketDataGateway` through composition. Legacy acquisition code may remain physically until deletion wave but must be unreachable.

Acceptance: hosted services can request market reads only through gateway; no provider command is reachable from browser/API composition.

### PR318 — MarketSourceSnapshot lineage

Branch: `refactor/pr318-market-source-lineage`

Depends on: PR317.

Scope: remove provider-download/quote-run lineage from research contracts and introduce deterministic `market_source.snapshot.v1`.

Acceptance: snapshot ID hashes semantic consumed rows only; excludes observation wall-clock, provenance timestamps, DSN, credentials, sync state; streaming/canonical hash; analytical IDs use snapshot identity; no fallback market-row copies.

### PR319 — Metadata source cutover

Branch: `refactor/pr319-metadata-market-source`

Depends on: PR318.

Scope: Metadata uses active listings from gateway only.

Acceptance: full identity/predicates preserved; inactive excluded from new universe; snapshot lineage persisted; no fallback.

### PR320 — Univariate source cutover

Branch: `refactor/pr320-univariate-market-source`

Depends on: PR318.

Scope: quotes/dividends through one gateway snapshot; remove download/shared-market branches.

Acceptance: 252 annualization/formulas/income/selection semantics preserved; missing adjusted close typed; no split transform; regression equivalence.

### PR321 — Bivariate source cutover

Branch: `refactor/pr321-bivariate-market-source`

Depends on: PR318.

Scope: selected quote rows tied to one snapshot; no quote-run lookup.

Acceptance: formulas/common-calendar/minimum-observation/pair guards/skip-same-ISIN preserved; full identity; no missing-covariance-as-zero; regression equivalence.

### PR322 — Multivariate source cutover

Branch: `refactor/pr322-multivariate-market-source`

Depends on: PR318.

Scope: snapshot quote/dividend lineage; pure return helper moved out of legacy persistence module; objectives/solvers/risk/walk-forward/OOS winner remain unchanged.

Acceptance: exact matrix fixture; no source-plane redesign; Equal Weight is never a hidden failure fallback.

### PR323 — Four-stage semantic QA

Branch: `test/pr323-four-stage-market-source-qa`

Depends on: PR319–PR322.

Scope: QA only across Metadata -> Univariate -> Bivariate -> Multivariate.

Acceptance: active/inactive, duplicate ISIN/full identity, missing adjusted, dividends, split non-interference, UTC/date, Decimal projection, regression equivalence, one snapshot lineage; unavailable/partial/insufficient sources fail closed; market tables unchanged; no sync refs/direct SQL outside market_source; merge gate passes.

### PR324–PR331 — Legacy market/provider deletion wave

All depend on PR323 and are parallel siblings.

- PR324 `chore/pr324-delete-eodhd-client`: delete EODHD client/search/fetch CLI and executable provider acquisition.
- PR325 `chore/pr325-delete-market-medallion`: delete market Bronze/Silver/Gold persistence/pipeline while retaining pure analytics moved elsewhere.
- PR326 `chore/pr326-delete-market-filesystem-plane`: delete market NAS/filesystem authority; preserve unrelated analytical/app artifacts only.
- PR327 `chore/pr327-delete-shared-market-refresh`: delete Portfell-owned market refresh/publisher/cron/cache plane; xetra-loader owns refresh.
- PR328 `chore/pr328-delete-hosted-download-lifecycle`: delete hosted market download routes/workers/jobs.
- PR329 `chore/pr329-delete-provider-credentials`: delete provider credential backend; do not replace it with plaintext config.
- PR330 `chore/pr330-freeze-legacy-web-provider-ui`: delete provider-loading UI/actions. This PR must not add React features; it only removes provider controls and leaves the old UI transitional until PR356.
- PR331 `chore/pr331-delete-hosted-local-market-runtime`: delete residual hosted local market runtime and EODHD/token/KEK/provider runtime config not owned by siblings.

Acceptance for every sibling: owned deletion is complete, no unrelated refactor, focused tests and PR gate pass.

### PR332 — Provider-removal negative-space QA

Branch: `test/pr332-provider-removal-negative-space`

Depends on: PR324–PR331.

Scope: QA only.

Acceptance: scan executable Python, entrypoints, current UI, Compose/workflows/scripts, tests/docs; no provider acquisition/credentials/medallion/market filesystem fallback/shared refresh/download/cron; no sync refs; no raw market SQL outside `market_source`; OpenAPI clean; full merge gate.

### PR333 — Single-user backend simplification

Branch: `refactor/pr333-single-user-backend`

Depends on: PR332.

Scope: remove user/tenant/membership/project-membership/credential-owner security authority from production services. Domain run/selection IDs may remain, but never as tenant scopes.

Acceptance: one workspace; no authorization behavior depends on user/project membership; no provider credentials; backend tests prove single-user semantics.

### PR334 — Legacy UI freeze for source-cutover compatibility

Branch: `refactor/pr334-freeze-legacy-ui`

Depends on: PR332.

Scope: **transitional only**. Remove user/project switching and obsolete provider controls needed to keep the legacy UI usable during source cutover. Do not redesign it and do not add new React/TanStack/Vite functionality.

Acceptance: canonical transitional routes `/metadata`, `/univariate`, `/bivariate`, `/multivariate`; no project selector/user switching; all new product UI work is explicitly deferred to Dash PR348–PR354.

### PR335 — Single-user/source-cutover QA

Branch: `test/pr335-single-user-source-cutover-qa`

Depends on: PR333 and PR334.

Acceptance: one workspace, no membership/security scope, four transitional routes, market PG privileges unchanged, full merge gate. This PR is not Dash parity evidence.

### PR336 — Package/entrypoint cleanup

Branch: `chore/pr336-market-source-package-cleanup`

Depends on: PR335.

Scope: remove provider/loading/NAS/refresh CLI/dependencies, update package description, retain required PostgreSQL/analytics dependencies, regenerate lock, add market import-boundary checks.

### PR337 — Transitional Compose source topology

Branch: `chore/pr337-market-source-compose`

Depends on: PR335.

Scope: keep Portfell application DB and external read-only market DB distinct during source cutover; no provider secrets/download workers; Compose never owns xetra-loader.

Acceptance: required external market DSN; no market DSN fallback; fixture uses LOGIN member of NOLOGIN `portfell_app`; market DML fails. This Compose is explicitly superseded later by PR358 for the new `portfell_dash` DB + Dash runtime.

### PR338 — Source architecture documentation

Branch: `docs/pr338-market-source-architecture`

Depends on: PR335.

Scope: document xetra-loader -> external PostgreSQL -> Portfell, exact keys/tables/role/snapshot/adjusted-close/Decimal/sync denial. Mark React/Vite UI and current Portfell application DB as transitional and point to PR344–PR360.

### PR339 — Clean source-cutover runtime QA

Branch: `test/pr339-clean-market-source-runtime`

Depends on: PR336–PR338.

Acceptance: clean `uv sync`, imports, entrypoints, Compose/container without provider/NAS; two DB authorities remain separate; fixture exercises all four analytical stages; full merge gate.

### PR340 — Live xetra-loader V2 QA

Branch: `test/pr340-live-xetra-loader-v2`

Depends on: PR339 and upstream production V2 PASS artifact.

Blocker: do not start until `artifacts/acceptance/postgres-full-sync-v2.json` exists on xetra-loader `main` and is marked PASS.

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

Acceptance: one checked-in handoff records exact source gateway API, application service API, persisted analytical concepts, four-page workflow, objective set (`return_risk`, `return_drawdown`, `minimum_risk`), professional plot requirements, Universe & History requirements, and the deletion inventory seed used by PR344.

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

Owned paths: `BACKLOG.md`, new `docs/contracts/plotly-dash-replacement-v1.md`, new `docs/contracts/legacy-ui-db-inventory-v1.json`, focused contract tests only.

Tasks:

- inventory every production file/path belonging to the legacy browser UI;
- inventory every direct frontend dependency and Node/npm build/runtime surface;
- inventory every legacy Portfell-owned application database/schema/table/migration/repository/env var/Compose volume/service dependency;
- inventory current FastAPI routes/application-service methods used by the four stages;
- freeze exact Dash route/page IDs, callback service contracts, final DB authorities, and final negative-space rules;
- classify each legacy item exactly `delete-pr356`, `delete-pr357`, `retain-backend`, or `retain-test-only`.

Acceptance:

- inventory is deterministic, schema-validated, sorted, contains no secrets, and has no `unknown` disposition;
- every production React/Vite/TypeScript/TanStack/Node UI path is owned by PR356;
- every legacy Portfell DB object/adapter/migration is owned by PR357 or explicitly proven still required by the new DB contract;
- `xetra_loader` objects are explicitly excluded from deletion;
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

### PR348 — Plotly Dash shell mounted in FastAPI

Branch: `feat/pr348-plotly-dash-shell`

Depends on: PR344. May execute in parallel with PR345–PR347 but must rebase on PR347 before merge if shared composition changes.

Owned paths: new `src/portfell/dash_app/**` shell/navigation/layout/assets, FastAPI composition mount, focused tests. Do not change analytical calculations.

Tasks:

- add Dash/Plotly Python dependencies;
- create one Dash application mounted/integrated with the production FastAPI runtime;
- register exactly four routes `/metadata`, `/univariate`, `/bivariate`, `/multivariate`;
- add shared navigation, loading/error region, page title contract, responsive desktop/tablet/mobile layout foundation;
- callbacks call typed application-service ports, never SQL;
- no Node/npm/Vite/TypeScript build is introduced.

Acceptance:

- all four routes resolve and only shell/placeholders render before page PRs;
- one process/container topology is documented and tested;
- FastAPI health/API routes remain reachable;
- browser smoke test has zero console/page errors attributable to Portfell;
- no import from `apps/web`;
- PR gate passes.

### PR349 — Dash Metadata page

Branch: `feat/pr349-dash-metadata-page`

Depends on: PR347 and PR348.

Owned paths: Dash Metadata page/callbacks and focused tests only.

Business behavior: browse/filter the active Xetra listing universe, show exact metadata fields/counts, create a versioned Metadata universe, and hand it to Univariate.

Acceptance:

- uses active listings only for new universe construction;
- filtering semantics match the Python contract exactly;
- duplicate ISINs remain distinguishable by full identity;
- inactive historical identity can be resolved but not newly selected;
- callbacks never perform direct SQL or provider refresh;
- persisted universe reloads after restart;
- accessible validation/loading/empty/error states; PR gate passes.

### PR350 — Dash Univariate page

Branch: `feat/pr350-dash-univariate-page`

Depends on: PR347 and PR348.

Owned paths: Dash Univariate page/callbacks/plots/tables and focused tests.

Business behavior: run and inspect univariate statistics for the selected Metadata universe, apply result filters, persist the exact downstream selection.

Acceptance:

- formulas/annualization/return conventions remain backend-authoritative;
- missing adjusted close is shown as typed unavailable evidence, never zero/raw-close fallback;
- distribution/income evidence does not alter adjusted-close return calculation;
- filter/selection counts are exact;
- professional Plotly return/risk visualization is produced from API/service values only;
- restart restores run and selection; PR gate passes.

### PR351 — Dash Bivariate page

Branch: `feat/pr351-dash-bivariate-page`

Depends on: PR347 and PR348.

Owned paths: Dash Bivariate page/callbacks/plots/tables and focused tests.

Acceptance:

- consumes exact persisted Univariate selection;
- common-calendar/minimum-observation/pair eligibility rules preserved;
- missing covariance/correlation is unavailable, never encoded as zero;
- no same-ISIN pair where prohibited by analytical contract;
- full listing identity visible where ambiguity exists;
- professional Plotly diversification/relationship visualization uses backend values only;
- large pair result handling is bounded; restart-safe; PR gate passes.

### PR352 — Dash Multivariate page

Branch: `feat/pr352-dash-multivariate-page`

Depends on: PR347 and PR348.

Owned paths: Dash Multivariate page/callbacks/plots/tables and focused tests.

Frozen objectives: `return_risk` default, `return_drawdown`, `minimum_risk`.

Acceptance:

- Multivariate is the only optimizer page/stage;
- OOS ranking selects the winner; no in-sample-best substitution;
- requested and actual optimizer/risk-model method are displayed from persisted artifacts;
- Equal Weight is never a hidden solver fallback;
- portfolio candidate OOS return/risk, performance, drawdown, allocation/risk contribution, and required professional plots are rendered from backend artifacts;
- DecisionArtifact explains winner and availability/production eligibility;
- restart-safe; PR gate passes.

### PR353 — Shared Dash callback/state/job semantics

Branch: `feat/pr353-dash-shared-state`

Depends on: PR349–PR352.

Scope: remove page-local duplication by adding one typed Dash state/callback layer for current universe/selection/run IDs, job progress, cancellation/retry, stale-result invalidation, and cross-page handoff.

Acceptance:

- no global mutable Python singleton is business authority;
- browser `dcc.Store`/client state contains identifiers/presentation state only, never full market authority or secrets;
- stale upstream revision invalidates downstream readiness deterministically;
- double-click/retry does not duplicate logical runs;
- page navigation never changes analytical state by GET/render side effect;
- one page cannot display another revision's result after rapid navigation;
- focused concurrency/restart tests and PR gate pass.

### PR354 — Dash professional visualization and UX parity

Branch: `feat/pr354-dash-professional-visualization`

Depends on: PR353.

Scope: final visual/interaction layer for all four pages. Use Plotly figures and Dash components only; no React extension application.

Required named plots include at minimum:

- `Univariate Return / Risk Universe`;
- `Bivariate Return / Diversification Universe`;
- `Portfolio Candidate OOS Return / Risk`;
- Multivariate cumulative performance and drawdown views;
- allocation and risk-contribution views where artifacts exist;
- Universe & History evidence views required by the final product contract.

Acceptance:

- desktop/tablet/mobile responsive checks;
- legends/axes/units/date ranges/hover labels are explicit and testable;
- unavailable data shown as unavailable, not zero;
- no financial recomputation in callbacks solely for plotting;
- all plots derive from immutable backend/service artifacts; PR gate passes.

### PR355 — Dash four-page parity and browser QA

Branch: `test/pr355-dash-four-page-parity`

Depends on: PR354.

Scope: QA only. Establish the deletion gate for the old UI and old DB.

Testing stack: Python `pytest` plus the repository-approved Python browser automation stack. Do not require an application npm/Node build. Browser binaries/test tooling may exist as test dependencies only if they do not restore a Node production UI boundary.

Acceptance:

- deterministic real-stack journey: Metadata -> Univariate -> Bivariate -> Multivariate;
- desktop/tablet/mobile;
- valid/empty/invalid/partial/unavailable/retry/restart states;
- exact request/callback effects and persisted new-DB state;
- no external production network access in deterministic CI fixtures;
- no direct market/app SQL from Dash modules;
- no legacy DB reads/writes during the journey;
- no route requires `apps/web`;
- market DB is read-only and sync schema denied;
- `uv run portfell-quality merge` passes.

This PR produces the immutable `dash-parity-v1` evidence artifact required by PR356 and PR357.

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
- no active old Portfell DB connection/service/volume exists;
- no first-party old frontend build/libraries are required to build or run Portfell;
- new DB and external market DB are the only production database authorities;
- production `config.yaml` is not tracked by Git and is not present in application images/artifacts; tracked `config.example.yaml` contains placeholders only;
- complete workflow succeeds after application restart;
- sanitized final evidence records image digests, schema/catalog fingerprint, market-source contract version, Git SHAs, and PASS results without secrets;
- documentation (`README.md`, `ARCHITECTURE.md`, page docs, Compose/runbook, `GATES.md`) describes only the final architecture.

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