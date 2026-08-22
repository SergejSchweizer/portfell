# PostgreSQL Read-Plane and Single-User Portfell Cutover

Status: active Portfell implementation authority after PR296 is merged.

Last reviewed: 2026-08-22.

## 1. Goal

Refactor `SergejSchweizer/portfell` into a single-user portfolio analytics/optimization application that reads market data exclusively from PostgreSQL at `10.10.1.3:54321`.

All XETRA provider/download/medallion/PostgreSQL-write work has moved to the separate repository `SergejSchweizer/xetra-data-loader`. Its authoritative implementation plan is `xetra-data-loader/BACKLOG.md` and contains work orders PR297-PR307.

This document contains only the Portfell side: PR308-PR321.

## 2. Hard ownership boundary

```text
SergejSchweizer/xetra-data-loader
  EODHD -> XETRA discovery -> Bronze/Silver/Gold -> PostgreSQL publication
                                      |
                                      v
                         PostgreSQL 10.10.1.3:54321
                              schema portfell_market
                                      |
                                      | SELECT only
                                      v
SergejSchweizer/portfell
  Metadata -> Univariate -> Bivariate -> Multivariate -> portfolio optimization
```

Portfell owns:

- read-only PostgreSQL market-data gateways;
- metadata filtering used by portfolio analysis;
- univariate, bivariate, and multivariate statistics;
- portfolio optimization objectives/solvers/walk-forward/risk calculations;
- portfolio/analysis decision persistence that is application-domain state rather than shared market-data state;
- single-user UI and API presentation.

Portfell must not own or import:

- EODHD HTTP clients or provider credentials;
- exchange-symbol discovery;
- fetch-all-metadata/fetch-all-quotes provider commands;
- Bronze/Silver/Gold market-data persistence;
- shared-market/NAS market-data paths or revisions;
- market-data PostgreSQL DDL/writers/sync state;
- Sunday market-data refresh workers;
- users, tenants, memberships, project memberships, per-user credentials, or project-bootstrap authorization.

Portfell must not import `xetra-data-loader` as a Python package. The database contract is the integration boundary.

## 3. Frozen external PostgreSQL contract

PR308 and later code consume only the externally observable database contract frozen by xetra-data-loader PR298.

Expected consumer schema:

- `portfell_market.listings`;
- `portfell_market.eod_quotes`;
- `portfell_market.dividends`;
- `portfell_market.splits`.

Identity contract:

- listing: `(isin, exchange, code)`;
- quote: `(isin, exchange, code, trade_date)`;
- dividends/splits: `(isin, exchange, code, event_key)`.

Timestamp contract:

- all PostgreSQL timestamp columns are exactly `TIMESTAMPTZ(6)`;
- DB session timezone is UTC;
- `trade_date` is a separate `DATE` business field;
- `timestamp_eod` is a canonical UTC date anchor, not a claimed physical XETRA close timestamp.

Security contract:

- Portfell uses database identity `portfell_app`;
- `portfell_app` has `SELECT` only on `portfell_market`;
- Portfell does not need and must not receive access to loader operational schema `portfell_loader_sync`;
- no Portfell runtime code performs DDL or market-data insert/update/delete operations.

Availability rule:

- PostgreSQL is the only market-data source after stage cutover;
- if required market data is absent or PostgreSQL is unavailable, Portfell fails explicitly;
- there is no provider fallback, filesystem fallback, NAS fallback, dual-read adapter, or legacy feature flag.

## 4. Single-user target model

Portfell is one operator using one application workspace.

Delete application authority for:

- `user_id`;
- `tenant_id`;
- memberships;
- project memberships;
- hosted/provider credential owners;
- project bootstrap jobs/workers;
- project-scoped market-data refreshes;
- access-control checks whose sole purpose is multi-user/project isolation.

Allowed domain identities:

- saved portfolio IDs;
- optimization run IDs;
- analysis run IDs;
- decision IDs;
- other domain identities required for analytics reproducibility.

Those IDs must not act as tenant/security scopes.

Canonical browser routes:

```text
/metadata
/univariate
/bivariate
/multivariate
```

REST stays under `/api`. No project slug is part of browser/API routing unless it is a true domain object unrelated to authorization; the planned target has no project-scoped route prefix.

## 5. Git contract for weak agents

Every work order must use its exact work-order name in:

- branch name;
- every commit scope/message;
- pull-request title.

Example:

```text
Work-order: pr314-bivariate-stage-postgres-cutover
Branch:     refactor/pr314-bivariate-stage-postgres-cutover
Commit:     refactor(pr314-bivariate-stage-postgres-cutover): cut bivariate reads to postgres
PR title:   must contain pr314-bivariate-stage-postgres-cutover
```

Every agent starts by recording:

```bash
git status --short --branch
```

Rules:

- start from the exact merged predecessor SHA;
- parallel siblings start from the same predecessor merge SHA;
- do not branch from a sibling;
- if a dependency is not merged, remain blocked;
- do not add compatibility shims or opportunistic refactors;
- do not preserve old loader/runtime code “temporarily” behind feature flags;
- focused tests and canonical quality gates must pass on the same head SHA;
- unexpected path ownership conflicts return to backlog planning.

## 6. Execution graph

```text
xetra PR298 -> PR308
                |
         PR309 || PR310 || PR311
                |
         PR312 || PR313 || PR314 || PR315
                |
              PR316 || PR317
                |
              PR318
                |
              PR319
                |
xetra PR307 -----+----> PR320
                        |
                      PR321
```

Safe parallel waves:

- PR309/PR310/PR311 after PR308;
- PR312/PR313/PR314/PR315 after PR309-PR311;
- PR316/PR317 after PR312-PR315.

PR308 depends only on xetra PR298's frozen contract, not on a full historical load. PR320 is the hard cross-repository gate and requires xetra PR307 and Portfell PR319.

## 7. Work orders

### PR308 - pr308-portfell-postgres-read-contract

Repository: `SergejSchweizer/portfell`

Branch: `refactor/pr308-portfell-postgres-read-contract`

Required commit scope: `refactor(pr308-portfell-postgres-read-contract): ...`

Git status: not started; branch absent; blocked until xetra-data-loader PR298 is merged.

Atomic outcome: freeze Portfell's read-only database gateway and typed consumer contracts without changing workflow-stage behavior yet.

Tasks:

- add PostgreSQL connection configuration using environment/secrets only;
- default/configure the external endpoint as `10.10.1.3:54321` without committing a password/full DSN;
- define read-only DTOs/interfaces matching `portfell_market` tables from xetra PR298;
- enforce timezone-aware UTC timestamp decoding;
- provide a connection/session factory that never issues schema DDL or market-data mutations;
- add contract fixtures independent from importing the xetra-data-loader package;
- add an architectural test preventing Portfell database adapters from importing EODHD/provider/lake writers;
- do not switch existing workflow stages in this PR.

Acceptance:

- typed consumer contracts match the frozen loader DDL/business keys;
- connection configuration contains no secret in source control;
- tests reject naive datetimes and unexpected schema/type drift;
- read layer contains no INSERT/UPDATE/DELETE/DDL path;
- no xetra-data-loader Python import exists;
- current workflow behavior remains unchanged until PR312-PR315.

Owned scope: new read-contract/configuration/database-gateway seam plus its focused tests.

### PR309 - pr309-portfell-listing-repository

Branch: `feat/pr309-portfell-listing-repository`

Required commit scope: `feat(pr309-portfell-listing-repository): ...`

Depends on: PR308 merged.

Atomic outcome: implement a deterministic read-only repository for XETRA listing metadata.

Tasks:

- implement listing queries against `portfell_market.listings`;
- preserve full identity `(isin, exchange, code)` and never collapse duplicate ISINs silently;
- support deterministic filtering/sorting needed by the Metadata stage;
- expose explicit empty/not-found behavior;
- add fixture/integration tests against the PR308 contract;
- avoid analytics or UI logic in the repository.

Acceptance:

- repository returns all fixture identities including duplicate ISINs with distinct code/exchange;
- query ordering is deterministic;
- no mutation statement is present;
- database unavailability surfaces as an explicit application error rather than invoking a fallback.

### PR310 - pr310-portfell-quote-repository

Branch: `feat/pr310-portfell-quote-repository`

Required commit scope: `feat(pr310-portfell-quote-repository): ...`

Depends on: PR308 merged.

Atomic outcome: implement a deterministic read-only repository for EOD quote history.

Tasks:

- query `portfell_market.eod_quotes` by complete listing identity and date range;
- preserve `trade_date` as business date and timezone-aware `timestamp_eod` as supplied by the serving contract;
- expose OHLCV/adjusted fields required by existing analytics without changing formulas;
- define deterministic ordering and duplicate-key rejection;
- add empty-window and multi-instrument tests;
- never derive/fabricate provider or physical market-close timestamps.

Acceptance:

- quote histories are ordered deterministically by identity/date;
- duplicate serving keys fail fast;
- UTC timestamp contract is preserved;
- no filesystem/provider fallback is invoked when data is missing.

### PR311 - pr311-portfell-corporate-action-repository

Branch: `feat/pr311-portfell-corporate-action-repository`

Required commit scope: `feat(pr311-portfell-corporate-action-repository): ...`

Depends on: PR308 merged.

Atomic outcome: implement read-only dividend and split repositories required by return/adjustment analytics.

Tasks:

- query `portfell_market.dividends` and `portfell_market.splits` by listing identity/date bounds;
- preserve deterministic `event_key` and serving timestamps;
- provide typed conversion required by existing analytics seams;
- define deterministic ordering and duplicate-event rejection;
- add tests for no-action periods, multiple actions, and duplicate identities.

Acceptance:

- events retain loader-provided semantic identity;
- repository does not regenerate `event_key` using run-local data;
- no mutation or fallback path exists;
- duplicate serving keys fail fast.

### PR312 - pr312-metadata-stage-postgres-cutover

Branch: `refactor/pr312-metadata-stage-postgres-cutover`

Required commit scope: `refactor(pr312-metadata-stage-postgres-cutover): ...`

Depends on: PR309, PR310, and PR311 merged.

Atomic outcome: make the Metadata workflow stage read its market universe exclusively from PostgreSQL and remove provider/download controls from that stage.

Tasks:

- replace metadata/shared-market/provider reads with PR309 repository calls;
- keep user-facing filtering semantics that are still relevant to portfolio analysis;
- remove `fetch all metadata`, token-entry, provider-download progress, and refresh actions from Metadata stage API/UI seams owned by this stage;
- make missing/empty PostgreSQL data explicit;
- add regression tests showing same fixture filtering output from the new source contract;
- do not delete global legacy loader modules yet; PR318 owns physical deletion.

Acceptance:

- Metadata stage performs zero provider/filesystem market reads;
- no metadata-download control remains in the stage;
- deterministic filtering output is covered by tests;
- stage failure never falls back to EODHD or local market files.

### PR313 - pr313-univariate-stage-postgres-cutover

Branch: `refactor/pr313-univariate-stage-postgres-cutover`

Required commit scope: `refactor(pr313-univariate-stage-postgres-cutover): ...`

Depends on: PR309, PR310, and PR311 merged.

Atomic outcome: source all Univariate workflow inputs from PostgreSQL while preserving existing statistical formulas/results.

Tasks:

- replace quote and corporate-action input resolution with PR310/PR311 repositories;
- preserve date-window, return-series, volatility, drawdown, distribution, and other existing univariate calculations;
- remove shared-market revision/path dependencies from the stage;
- add fixture-based before/after regression tests around calculations, not legacy storage mechanisms;
- fail explicitly on incomplete required data.

Acceptance:

- numerical/statistical formulas are unchanged except where the old source adapter itself was incorrect and a separate change is explicitly required;
- no EODHD/filesystem/shared-market read exists in the stage;
- stable fixtures produce expected statistics from PostgreSQL-backed DTOs;
- data gaps are surfaced, not silently backfilled from legacy sources.

### PR314 - pr314-bivariate-stage-postgres-cutover

Branch: `refactor/pr314-bivariate-stage-postgres-cutover`

Required commit scope: `refactor(pr314-bivariate-stage-postgres-cutover): ...`

Depends on: PR309, PR310, and PR311 merged.

Atomic outcome: source Bivariate workflow inputs exclusively from PostgreSQL while preserving existing pairwise statistics.

Tasks:

- use PR310/PR311 for aligned instrument histories;
- preserve correlation/covariance/pairwise-return and other existing formulas;
- make date/intersection alignment deterministic and explicit;
- remove local/shared-market source references from the stage;
- add regression tests for aligned, partially overlapping, and insufficient histories.

Acceptance:

- Bivariate computations consume PostgreSQL DTOs only;
- deterministic alignment rules are tested;
- formulas remain unchanged;
- no legacy source fallback exists.

### PR315 - pr315-multivariate-stage-postgres-cutover

Branch: `refactor/pr315-multivariate-stage-postgres-cutover`

Required commit scope: `refactor(pr315-multivariate-stage-postgres-cutover): ...`

Depends on: PR309, PR310, and PR311 merged.

Atomic outcome: assemble all Multivariate/optimizer market-data inputs from PostgreSQL while preserving optimization objectives and algorithms.

Tasks:

- replace shared-market/provider input assembly with PR309-PR311 repositories;
- preserve existing universe selection, aligned return matrix, covariance/risk inputs, solver contracts, and walk-forward data semantics;
- isolate market-data acquisition from optimizer algorithms so source changes cannot alter solver internals;
- add deterministic fixture tests for multi-asset alignment and optimizer-input matrices;
- do not opportunistically rewrite optimizer algorithms.

Acceptance:

- no optimizer input is read from EODHD/filesystem/shared-market persistence;
- expected fixture matrices are reproduced exactly from PostgreSQL-backed data;
- optimizer algorithm interfaces remain stable;
- missing/incomplete inputs fail explicitly.

### PR316 - pr316-single-user-backend-cutover

Branch: `refactor/pr316-single-user-backend-cutover`

Required commit scope: `refactor(pr316-single-user-backend-cutover): ...`

Depends on: PR312, PR313, PR314, and PR315 merged.

Atomic outcome: remove backend multi-user/tenant/project/credential authority and expose one single-user workspace.

Tasks:

- identify and delete user/tenant/membership/project-membership authorization models and services;
- remove per-user/per-project provider credential storage and APIs;
- remove project-bootstrap worker contracts and project-scoped refresh authority;
- replace request-time project/user resolution with one application workspace context where a context object is still technically useful;
- preserve analytics-domain run/portfolio/decision IDs that are not security scopes;
- simplify REST paths/services that exist only to serve tenant/project authority;
- add source guards preventing reintroduction of removed authorization entities.

Acceptance:

- backend starts and serves analytics with no user/tenant/project membership records;
- no provider credential API/storage remains;
- no project-bootstrap worker remains;
- tests contain no authorization matrix for multiple application users/projects;
- saved portfolio/analysis domain objects continue to work without becoming a tenant abstraction.

### PR317 - pr317-single-user-ui-cutover

Branch: `refactor/pr317-single-user-ui-cutover`

Required commit scope: `refactor(pr317-single-user-ui-cutover): ...`

Depends on: PR312, PR313, PR314, and PR315 merged.

Atomic outcome: reduce UI navigation to one workspace and four canonical workflow routes.

Tasks:

- make `/metadata`, `/univariate`, `/bivariate`, and `/multivariate` the canonical browser routes;
- remove project selector/project slug routing;
- remove login/user switcher/tenant/project-membership UI owned solely by multi-user behavior if present;
- remove provider token input, fetch buttons, refresh progress, and loader scheduling controls;
- preserve analysis controls/figures relevant to portfolio work;
- update navigation/regression tests for direct canonical routes.

Acceptance:

- every workflow page is reachable without a project/user route prefix;
- no project selector/provider credential/loading control is rendered;
- navigation contains only single-workspace portfolio/research concepts;
- UI failure cannot trigger a market-data fetch fallback.

### PR318 - pr318-delete-portfell-data-loading-stack

Branch: `refactor/pr318-delete-portfell-data-loading-stack`

Required commit scope: `refactor(pr318-delete-portfell-data-loading-stack): ...`

Depends on: PR316 and PR317 merged.

Atomic outcome: physically delete all Portfell-owned market-data loading/persistence/refresh code after PostgreSQL-backed stages and single-user paths are green.

Tasks:

- delete EODHD provider client/adapters and token configuration from Portfell;
- delete Bronze/Silver/Gold/shared-market/lake market-data writers/readers no longer used by analytics;
- delete market refresh workers/schedulers/commands and provider fetch CLIs;
- delete NAS/filesystem market-data fallback code;
- delete tests/fixtures that exist solely for removed loading behavior;
- remove deprecated aliases and hidden flags that could reactivate the old loader;
- add architecture/source-search tests proving forbidden loader concepts are absent from production code.

Acceptance:

- repository contains no executable EODHD/download/medallion/shared-market refresh stack;
- canonical analytics tests remain green from PostgreSQL-backed fixtures/integration setup;
- source guard fails if forbidden production imports/namespaces are reintroduced;
- no compatibility shim keeps the old loader callable.

### PR319 - pr319-simplify-portfell-runtime

Branch: `refactor/pr319-simplify-portfell-runtime`

Required commit scope: `refactor(pr319-simplify-portfell-runtime): ...`

Depends on: PR318 merged.

Atomic outcome: simplify composition, dependencies, configuration, and production Compose around one read-only Portfell application service.

Tasks:

- remove runtime dependencies needed only by provider loading/medallion persistence/multi-user bootstrap;
- simplify application composition and startup wiring;
- make external PostgreSQL connection an explicit required production dependency;
- remove Portfell-owned production PostgreSQL and project/data-loader worker services from Compose;
- target long-running production service set of `app` only for Portfell itself;
- retain one-shot migrations only for genuine Portfell-owned application-domain state if still required, not for `portfell_market`;
- update deployment/configuration docs and health checks;
- add runtime architecture test asserting no local market-data loader service or provider secret is required.

Acceptance:

- production Portfell starts against external PostgreSQL with one long-running app service;
- no local market-data PostgreSQL/container is declared as Portfell ownership;
- no EODHD secret is required by Portfell startup;
- dependency tree no longer includes packages used solely by deleted loader paths unless another verified production use exists;
- canonical quality gates pass.

### PR320 - pr320-cross-repo-serving-contract-gate

Branch: `test/pr320-cross-repo-serving-contract-gate`

Required commit scope: `test(pr320-cross-repo-serving-contract-gate): ...`

Depends on: xetra-data-loader PR307 and Portfell PR319 merged.

Atomic outcome: prove that the independent xetra-data-loader serving contract is consumable by Portfell without source/package coupling.

Tasks:

- consume xetra PR307's machine-readable contract/acceptance fixture or reproduce its frozen SQL contract in an integration environment;
- start an empty test PostgreSQL instance, apply loader-owned serving DDL by artifact/SQL boundary rather than importing loader Python modules;
- load representative listing/quote/dividend/split fixture data;
- run PR309-PR315 repositories/stage smoke paths against it;
- assert `TIMESTAMPTZ(6)`/UTC behavior and duplicate full-identity handling;
- assert `portfell_app` cannot mutate consumer tables;
- add a test that fails if Portfell imports the xetra-data-loader package;
- document the exact two-repository commit SHAs used for the contract gate.

Acceptance:

- cross-repository smoke suite passes on both clean main heads;
- every Portfell workflow stage can consume the representative serving data;
- database write attempt under `portfell_app` fails;
- no shared Python package/import coupling exists;
- contract drift produces a failing test instead of silent adaptation.

### PR321 - pr321-production-destructive-cutover

Branch: `docs/pr321-production-destructive-cutover`

Required commit scope: `docs(pr321-production-destructive-cutover): ...`

Depends on: PR320 merged.

Atomic outcome: provide the exact production cutover/runbook that removes old Portfell market-data state and switches operations permanently to xetra-data-loader -> PostgreSQL -> Portfell.

Tasks:

- document pre-cutover backups for Portfell-owned analytics/optimizer state that must survive;
- explicitly classify legacy Portfell market-data files/tables as disposable and not migrated;
- reference the xetra-data-loader destructive bootstrap procedure rather than duplicating provider logic;
- provide PostgreSQL verification queries for listing counts, quote date bounds, corporate-action counts, duplicate business keys, timestamp SQL types, and grants;
- provide Portfell smoke checks for all four workflow routes/stages;
- list exact legacy Portfell paths/tables/services/configuration to delete/disable;
- define rollback as application/configuration rollback only where possible, never by reactivating EODHD/filesystem legacy loading;
- record responsible repository/commit/version for both sides of the deployment.

Acceptance:

- an operator can execute cutover without guessing ownership or destruction scope;
- verification demonstrates external serving plane health before Portfell legacy deletion;
- rollback instructions do not re-enable old loader/fallback paths;
- runbook distinguishes loader-owned market data from Portfell-owned analytics/optimizer state;
- completion checklist maps one-to-one to the final architecture invariants below.

## 8. Final Portfell completion gate

The Portfell side is complete only when all conditions below hold on clean `main`:

- market data for Metadata, Univariate, Bivariate, and Multivariate comes exclusively from `portfell_market` through read-only repositories;
- `portfell_app` cannot insert/update/delete/DDL consumer market tables;
- Portfell contains no EODHD token/client/provider-fetch logic;
- Portfell contains no Bronze/Silver/Gold/shared-market/NAS market-data persistence or fallback;
- Portfell contains no market-data scheduler/refresh worker;
- Portfell contains no user/tenant/membership/project-membership/provider-credential runtime;
- project-slug routes and project selector are gone;
- canonical routes are `/metadata`, `/univariate`, `/bivariate`, `/multivariate`;
- production runtime is a single-user app against external PostgreSQL;
- old market-data artifacts are deleted, not migrated;
- Portfell does not import `xetra-data-loader` as a Python package;
- PR320 proves the database contract across the two independent repositories;
- PR321 documents an executable destructive cutover and rollback that never reactivates legacy loading.
