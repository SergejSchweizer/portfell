# PostgreSQL Loader Extraction and Single-User Portfell Cutover

Status: active implementation authority after PR296 is merged.

Last reviewed: 2026-08-22.

## 1. Goal

Split the current repository into two sharply separated systems:

1. `SergejSchweizer/portfell-data-loader` owns EODHD access, XETRA discovery, historical market-data loading, medallion persistence, validation, weekly refresh, and PostgreSQL publication.
2. `SergejSchweizer/portfell` owns a single-user portfolio-analysis and portfolio-optimization application. It reads market data from PostgreSQL only and has no provider, download, medallion, tenant, project-membership, or multi-user authority.

There is no migration requirement for current Portfell market-data files or current hosted/multi-user state. Existing local/NAS Portfell market-data artifacts may be deleted and the new loader performs a clean full rebuild from the provider.

`portfell-data-loader` does not exist yet. Repository creation is an explicit one-time prerequisite outside this work-order series because the available repository automation cannot create repositories. Create it as `SergejSchweizer/portfell-data-loader` with default branch `main` before PR297 starts. Do not copy Portfell Git history into it.

## 2. Hard architecture contract

### 2.1 Ownership boundary

`portfell-data-loader` owns:

- EODHD credentials and HTTP client;
- XETRA exchange-symbol discovery;
- all XETRA rows with a non-empty ISIN, without an ETF-only prefilter;
- EOD quotes, dividends, and splits for the complete selected XETRA listing identity `(isin, exchange, code)`;
- Bronze, Silver, and Gold data contracts and local loader state;
- deterministic correction/backfill planning;
- PostgreSQL DDL, writer role, idempotent Gold synchronization, sync state, and loader run records;
- Sunday scheduling, process locking, retry/rate-limit behavior, observability, and destructive bootstrap tooling.

`portfell` owns:

- read-only PostgreSQL market-data gateways;
- metadata filtering used by portfolio analysis;
- univariate, bivariate, and multivariate portfolio analytics;
- optimization objectives, solvers, walk-forward evaluation, risk calculations, decisions, and presentation;
- one application workspace for one operator.

`portfell` must not own or import:

- EODHD client/provider code;
- provider tokens or credential-management UI/API;
- `fetch-all-metadata`, `fetch-all-quotes`, market refresh workers, or scheduled market downloads;
- Bronze/Silver/Gold market-data persistence or local shared-market revisions;
- filesystem/NAS market-data fallbacks;
- user, tenant, membership, hosted credential, or multi-project authorization logic.

### 2.2 PostgreSQL serving plane

Production PostgreSQL endpoint is `10.10.1.3:54321`. The endpoint is configuration, not a source-code secret. Passwords and full DSNs must be supplied through ignored environment/secret files.

Freeze these schemas:

```text
portfell_market        # consumer-facing Gold tables
portfell_loader_sync   # loader-only sync/run state
```

Freeze these consumer tables:

```text
portfell_market.listings
portfell_market.eod_quotes
portfell_market.dividends
portfell_market.splits
```

Minimum identity/business keys:

```text
listings:   PRIMARY KEY (isin, exchange, code)
eod_quotes: PRIMARY KEY (isin, exchange, code, trade_date)
dividends:  UNIQUE (isin, exchange, code, event_key)
splits:     UNIQUE (isin, exchange, code, event_key)
```

`event_key` is a deterministic SHA-256 digest over the normalized provider business fields for that corporate action; it must not contain a run ID or ingest timestamp.

All PostgreSQL timestamp columns use the same SQL type as `market-regime-loader`:

```text
TIMESTAMPTZ(6)
```

The PostgreSQL session timezone is always `UTC`. This includes `timestamp_eod`, `fetched_at_utc`, `published_at_utc`, `synced_at_utc`, and loader-run timestamps. Source EOD rows are date-granular, so `trade_date DATE` remains the business date and `timestamp_eod TIMESTAMPTZ(6)` is a canonical UTC date anchor (`trade_date 00:00:00+00:00`), not a claim about the physical XETRA closing instant. Tests must reject naive Python datetimes and non-`TIMESTAMPTZ(6)` DDL for timestamp fields.

Create two database roles through provisioning scripts, with credentials supplied externally:

```text
portfell_data_loader   # INSERT/UPDATE/DELETE on loader-owned schemas
portfell_app           # SELECT only on portfell_market
```

`portfell_app` receives no DDL or mutation grant on `portfell_market` and no access to `portfell_loader_sync`.

### 2.3 XETRA universe and refresh semantics

Bootstrap target is every EODHD XETRA listing whose normalized ISIN is non-empty. Do not prefilter to UCITS, ETF, FUND, country, currency, or current Portfell selections. Preserve full listing identity `(isin, exchange, code)` even if multiple rows share an ISIN.

Each scheduled cycle does exactly this:

```text
refresh XETRA listing metadata
  -> determine current non-empty-ISIN XETRA listing set
  -> refresh quotes
  -> refresh dividends
  -> refresh splits
  -> build/validate Gold serving tables
  -> idempotently synchronize Gold delta to PostgreSQL
  -> verify row counts, key uniqueness, bounds, and sync state
```

After an initial full bootstrap, weekly refresh uses bounded deltas with a seven-calendar-day correction overlap for provider revisions. A repeated run for the same source data must produce zero semantic mutations in PostgreSQL. Deleted/retracted provider business keys in the correction window must be reconciled deliberately; they must not survive because of append-only behavior.

### 2.4 Schedule

The managed loader schedule is exactly:

```text
CRON_TZ=Europe/Vienna
0 11 * * 0
```

That is Sunday at 11:00 Vienna local time, including DST behavior. Only the loader repository owns this schedule. Portfell has no market-data cron after cutover.

### 2.5 Single-user Portfell

Portfell has exactly one application workspace. There is no `user_id`, `tenant_id`, membership table, project membership, credential owner, project bootstrap worker, or per-user authorization boundary.

Canonical browser workflow remains portfolio focused and loses project-slug routing:

```text
/metadata
/univariate
/bivariate
/multivariate
```

REST remains under `/api`. Saved portfolio/analysis entities may have their own domain IDs, but those IDs are not user/tenant/project security scopes.

Production Portfell does not run a local PostgreSQL service and does not run a data-loader/refresh worker. It connects read-only to the external PostgreSQL serving plane. The target long-running Portfell application service is `app` only; any reverse proxy is deployment infrastructure, not a Portfell data service.

### 2.6 Destructive cutover and no-legacy rule

No legacy compatibility path is allowed. In particular:

- do not migrate existing Parquet/shared-market/NAS data;
- do not keep provider-to-Portfell fallback code;
- do not keep dual-read PostgreSQL/filesystem adapters;
- do not keep old project/user tables for compatibility;
- do not keep old EODHD CLI aliases as deprecated commands;
- do not keep hidden feature flags that can reactivate the old loader;
- do not copy old data into new tables merely to preserve history.

The cutover runbook explicitly deletes loader-owned test/bootstrap schemas and old Portfell market-data artifacts before a clean full download. Destructive commands require an explicit `--confirm-destructive-reset` flag and print the exact schemas/paths they will delete before mutation.

## 3. Weak-agent execution rules

Every work order below is a single PR-sized unit. These rules are mandatory:

- An agent starts from a clean working tree on the exact named base branch/merge SHA.
- The agent runs `git status --short --branch` before editing and records it in the PR description.
- Branch name must contain the exact PR work-order name shown below.
- Every commit message must contain the exact PR work-order name shown below.
- One work order owns one outcome and the listed paths only. Do not opportunistically refactor adjacent code.
- Parallel siblings start from the same predecessor merge SHA and never from each other.
- If a required predecessor is not merged, the work order stays blocked; do not recreate its contract locally.
- No compatibility adapters, migration shims, legacy aliases, or fallback readers may be added unless this document explicitly asks for them; it does not.
- Focused tests plus the repository's canonical quality gate must pass from the same head SHA.
- Any discovered scope conflict is returned to planning instead of being silently broadened.

### Required naming form

For every work order, the exact work-order name is the text after the PR key, for example `pr301-eod-quote-ingestion`.

```text
Branch:  <type>/pr301-eod-quote-ingestion
Commit:  feat(pr301-eod-quote-ingestion): add deterministic eod quote ingestion
PR title must contain: pr301-eod-quote-ingestion
```

## 4. Execution graph

```text
PR296 planning gate
        |
  manual create SergejSchweizer/portfell-data-loader
        |
      PR297
        |
      PR298
        |
      PR299
        |
   +----+----+----+
   |    |    |    |
 PR300 PR301 PR302 PR308
   |    |    |    |
   +----+----+    +----------------------+
        |                                |
      PR303                            PR309 || PR310 || PR311
        |                                |
      PR304                              +------+
        |                                       |
      PR305                          PR312 || PR313 || PR314 || PR315
        |                                       |
      PR306                                  PR316 || PR317
        |                                       |
      PR307                                  PR318
        |                                       |
        +-------------------+-------------------+
                            |
                          PR319
                            |
                          PR320
                            |
                          PR321
```

Notes:

- PR300/PR301/PR302 are parallel loader source families from the same PR299 base.
- PR308 can begin after PR298 because it consumes only the frozen PostgreSQL contract and test fixtures; it does not require a live loader.
- PR309/PR310/PR311 are parallel Portfell PostgreSQL repositories from PR308.
- PR312-PR315 are parallel stage cutovers once all three read repositories are merged.
- PR316 and PR317 are parallel single-user backend/UI cuts after the stage cutovers; they own disjoint code.
- Destructive deletion PR318 starts only after the new DB read paths and single-user paths are green.
- PR319 is the Portfell no-legacy/runtime simplification integration gate.
- PR320 is the cross-repository contract smoke gate.
- PR321 is the production cutover/runbook gate.

## 5. Work orders

### PR296 — `pr296-postgres-loader-single-user-backlog`

Repository: `SergejSchweizer/portfell`.
Branch: `docs/pr296-postgres-loader-single-user-backlog`.
Git status: planning branch created from clean `main`; documentation changes only; validation pending until PR merge.
Depends on: current `main`.
Atomic outcome: replace the old multi-user/in-repo-loading execution authority with this extraction/cutover plan.
Owned paths: `BACKLOG.md`, `docs/backlog/postgres-loader-single-user-cutover.md` only.
Required commit scope: `docs(pr296-postgres-loader-single-user-backlog): ...`.
Tasks / Acceptance:
- [ ] `BACKLOG.md` marks PR264-PR295 superseded and names this document as active scope authority.
- [ ] PostgreSQL `TIMESTAMPTZ(6)`/UTC, XETRA-all-ISIN bootstrap, Sunday 11:00, single-user, destructive rebuild, and no-legacy requirements are explicit.
- [ ] Every new work order has exact repository, branch, Git status, dependencies, atomic outcome, owned paths, and machine-checkable acceptance.
- [ ] Markdown/link checks and Portfell documentation gates pass.

### PR297 — `pr297-loader-repository-bootstrap`

Repository: `SergejSchweizer/portfell-data-loader`.
Branch: `chore/pr297-loader-repository-bootstrap`.
Git status: not started; branch absent; blocked until the new repository is manually created with clean `main`.
Depends on: PR296 + new repository exists.
Atomic outcome: establish a minimal loader repository skeleton analogous to the reference loaders, without any EODHD dataset implementation.
Owned paths: repository root scaffolding, `api/**`, `application/**`, `ingestion/**` package markers, `tests/**` bootstrap tests, `.github/workflows/**`, `.importlinter`, `pyproject.toml`, `README.md`, `ARCHITECTURE.md`, `AGENTS.md`, `GATES.md`.
Required commit scope: `chore(pr297-loader-repository-bootstrap): ...`.
Tasks / Acceptance:
- [ ] Python package has strict `api -> application -> ingestion` dependency direction and import-linter test.
- [ ] Canonical lint/type/unit/integration commands exist and CI runs them in parallel where safe.
- [ ] No Portfell application, UI, optimizer, user, or project code is copied into the loader.
- [ ] No provider token, PostgreSQL password, NAS path, or generated dataset is committed.

### PR298 — `pr298-postgres-serving-contract`

Repository: `SergejSchweizer/portfell-data-loader`.
Branch: `feat/pr298-postgres-serving-contract`.
Git status: not started; branch absent; blocked on PR297.
Depends on: PR297.
Atomic outcome: freeze consumer/sync schemas, typed DTOs, DDL, roles, timestamp rules, and test fixtures; no network calls.
Owned paths: `application/postgres_contracts.py`, `ingestion/postgres_schema.py`, `scripts/provision_postgres_roles.py`, contract/schema tests, schema documentation.
Required commit scope: `feat(pr298-postgres-serving-contract): ...`.
Tasks / Acceptance:
- [ ] DDL creates `portfell_market.listings`, `eod_quotes`, `dividends`, `splits` and loader-only sync/run tables with frozen keys.
- [ ] Every timestamp field is `TIMESTAMPTZ(6)` and DB sessions set timezone `UTC`; tests inspect generated DDL and reject naive datetimes.
- [ ] `timestamp_eod` is derived as UTC midnight from `trade_date` and docs state that it is a date anchor, not an exchange-close timestamp.
- [ ] `portfell_data_loader` writer and `portfell_app` read-only grant plans are explicit; tests prove the app role receives no write/DDL grants.
- [ ] Host/port may default in deployment examples to `10.10.1.3:54321`, but no password/DSN is committed.

### PR299 — `pr299-medallion-dataset-contracts`

Repository: `SergejSchweizer/portfell-data-loader`.
Branch: `feat/pr299-medallion-dataset-contracts`.
Git status: not started; branch absent; blocked on PR298.
Depends on: PR298.
Atomic outcome: define deterministic Bronze/Silver/Gold dataset identities, paths, schemas, business keys, and manifests without provider fetching.
Owned paths: `application/datasets.py`, `application/dataset_contracts.py`, `application/paths.py`, `ingestion/parquet_repository.py`, contract/path tests, `DATASETS.md`.
Required commit scope: `feat(pr299-medallion-dataset-contracts): ...`.
Tasks / Acceptance:
- [ ] Dataset IDs cover XETRA listings, EOD quotes, dividends, and splits from Bronze through Gold.
- [ ] Full listing identity is `(isin, exchange, code)` at every layer; no ISIN-only deduplication silently drops listings.
- [ ] Business keys match PR298 serving keys and normalized rows are deterministically ordered.
- [ ] Writes are idempotent and atomic; manifests include row count, min/max business date, schema version, source hash, and build ID.
- [ ] Gold contains serving-ready market data only; no portfolio optimization/statistics are moved into the loader.

### PR300 — `pr300-xetra-listing-ingestion`

Repository: `SergejSchweizer/portfell-data-loader`.
Branch: `feat/pr300-xetra-listing-ingestion`.
Git status: not started; branch absent; blocked on PR299.
Depends on: PR299.
Atomic outcome: ingest and normalize the complete current EODHD XETRA listing universe with non-empty ISIN.
Owned paths: EODHD HTTP adapter, XETRA listing fetcher/parser, listing orchestration, focused fixtures/tests.
Required commit scope: `feat(pr300-xetra-listing-ingestion): ...`.
Tasks / Acceptance:
- [ ] Fetch only the provider's XETRA exchange-symbol endpoint/configured equivalent and normalize all non-empty-ISIN rows; no ETF/UCITS filter.
- [ ] Preserve provider code, exchange, ISIN, name, type, country, currency, active/delisted fields when available.
- [ ] Duplicate exact listing identities collapse deterministically; distinct codes sharing one ISIN remain distinct.
- [ ] Rate-limit/retry behavior is bounded and tested; logs redact tokens.
- [ ] Bronze and Silver listing outputs satisfy PR299 contracts.

### PR301 — `pr301-eod-quote-ingestion`

Repository: `SergejSchweizer/portfell-data-loader`.
Branch: `feat/pr301-eod-quote-ingestion`.
Git status: not started; branch absent; blocked on PR299.
Depends on: PR299.
Atomic outcome: full/delta EOD quote ingestion for an injected frozen XETRA listing set.
Owned paths: quote fetcher/parser, quote planner/orchestrator, quote tests/fixtures only.
Required commit scope: `feat(pr301-eod-quote-ingestion): ...`.
Tasks / Acceptance:
- [ ] Full history request is supported when no prior coverage exists.
- [ ] Incremental requests begin seven calendar days before the last covered business date and end at the requested target date.
- [ ] Normalize `open/high/low/close/adjusted_close/volume` plus listing identity and business date; reject invalid/missing business keys.
- [ ] Re-fetching an overlap replaces matching business keys deterministically instead of appending duplicates.
- [ ] Focused tests cover empty provider responses, revised rows, duplicate payload rows, partial failure, retry, and restart.

### PR302 — `pr302-corporate-action-ingestion`

Repository: `SergejSchweizer/portfell-data-loader`.
Branch: `feat/pr302-corporate-action-ingestion`.
Git status: not started; branch absent; blocked on PR299.
Depends on: PR299.
Atomic outcome: full/delta dividends and splits ingestion as one corporate-action family for an injected frozen XETRA listing set.
Owned paths: dividend/split fetchers/parsers, corporate-action planner/orchestrator, focused tests/fixtures only.
Required commit scope: `feat(pr302-corporate-action-ingestion): ...`.
Tasks / Acceptance:
- [ ] Dividends and splits use explicit normalized business fields and deterministic SHA-256 `event_key` values.
- [ ] Seven-calendar-day correction overlap is supported and revised/retracted events within the overlap are reconciled.
- [ ] Missing/invalid event business dates are quarantined or fail with typed reason; they never create empty keys.
- [ ] Repeated identical fetches create no semantic duplicates.
- [ ] Tests cover same-date multiple dividends, multiple split formats, empty responses, corrections, and restart.

### PR303 — `pr303-gold-serving-build`

Repository: `SergejSchweizer/portfell-data-loader`.
Branch: `feat/pr303-gold-serving-build`.
Git status: not started; branch absent; blocked on PR300-PR302.
Depends on: PR300, PR301, PR302.
Atomic outcome: build validated Gold listing/quote/dividend/split datasets that exactly match the PostgreSQL consumer contract.
Owned paths: Gold builders/catalog/validation, Gold tests/fixtures only.
Required commit scope: `feat(pr303-gold-serving-build): ...`.
Tasks / Acceptance:
- [ ] Gold includes only rows whose listing identity exists in the current XETRA non-empty-ISIN universe, with an explicit policy/test for newly delisted rows.
- [ ] Gold keys are unique and timestamp/date contracts match PR298 exactly.
- [ ] Validation reports row counts, unique listing count, min/max dates, null-key count, duplicate-key count, and content hash.
- [ ] Same Silver inputs produce byte/semantic-equivalent Gold records and stable hashes.
- [ ] No optimizer return, covariance, correlation, or portfolio-weight calculations exist in Gold.

### PR304 — `pr304-postgres-idempotent-sync`

Repository: `SergejSchweizer/portfell-data-loader`.
Branch: `feat/pr304-postgres-idempotent-sync`.
Git status: not started; branch absent; blocked on PR303.
Depends on: PR303.
Atomic outcome: transactionally synchronize the current Gold build into PostgreSQL using semantic deltas.
Owned paths: PostgreSQL repository adapter, delta planner, sync service/CLI, focused unit/integration tests.
Required commit scope: `feat(pr304-postgres-idempotent-sync): ...`.
Tasks / Acceptance:
- [ ] Sync computes insert/update/delete/unchanged sets from stable business-key row hashes and stores sync state in `portfell_loader_sync`.
- [ ] Apply one dataset delta plus its state update transactionally; rollback leaves both consumer rows and sync state unchanged on failure.
- [ ] Second sync of identical Gold yields zero inserts, updates, and deletes.
- [ ] Corrected and retracted rows are updated/deleted, not duplicated.
- [ ] Integration tests use PostgreSQL and assert `TIMESTAMPTZ(6)`, UTC sessions, PK/unique constraints, grants, row counts, and date bounds.

### PR305 — `pr305-sunday-1100-loader-runner`

Repository: `SergejSchweizer/portfell-data-loader`.
Branch: `feat/pr305-sunday-1100-loader-runner`.
Git status: not started; branch absent; blocked on PR304.
Depends on: PR304.
Atomic outcome: add one restart-safe weekly orchestration command and the exact Sunday 11:00 Vienna cron definition.
Owned paths: `application/weekly_pipeline.py`, CLI wiring, `ops/portfell-data-loader.cron`, schedule exporter, lock/logging tests.
Required commit scope: `feat(pr305-sunday-1100-loader-runner): ...`.
Tasks / Acceptance:
- [ ] One command runs listing refresh -> quote refresh -> dividends/splits -> Gold -> PostgreSQL sync in the frozen order.
- [ ] Process lock rejects overlapping runs with a stable nonzero exit code.
- [ ] Cron is exactly `CRON_TZ=Europe/Vienna` and `0 11 * * 0`; tests parse the template and fail on another day/time/timezone.
- [ ] Stage failures stop dependent stages, keep restartable durable state, and emit redacted structured summary counts.
- [ ] Portfell itself is not invoked by this cron.

### PR306 — `pr306-destructive-bootstrap-command`

Repository: `SergejSchweizer/portfell-data-loader`.
Branch: `feat/pr306-destructive-bootstrap-command`.
Git status: not started; branch absent; blocked on PR305.
Depends on: PR305.
Atomic outcome: provide an explicit clean-reset/full-XETRA bootstrap path for the one-time cutover.
Owned paths: reset/bootstrap command, destructive confirmation helper, bootstrap integration test/runbook fragment.
Required commit scope: `feat(pr306-destructive-bootstrap-command): ...`.
Tasks / Acceptance:
- [ ] Dry-run prints exact loader-owned local paths and PostgreSQL schemas/tables that would be cleared and performs no mutation.
- [ ] Destructive mode requires literal `--confirm-destructive-reset`; omission fails closed.
- [ ] Reset never drops unrelated schemas or touches Portfell optimizer/result tables.
- [ ] After reset, full bootstrap fetches all current XETRA non-empty-ISIN listings and full quote/dividend/split history, builds Gold, and synchronizes PostgreSQL.
- [ ] Integration fixture proves reset -> bootstrap -> rerun is idempotent.

### PR307 — `pr307-loader-end-to-end-gate`

Repository: `SergejSchweizer/portfell-data-loader`.
Branch: `test/pr307-loader-end-to-end-gate`.
Git status: not started; branch absent; blocked on PR306.
Depends on: PR306.
Atomic outcome: freeze one production-like loader acceptance gate without adding product features.
Owned paths: end-to-end fixtures/tests, quality-gate wiring, operations evidence docs only.
Required commit scope: `test(pr307-loader-end-to-end-gate): ...`.
Tasks / Acceptance:
- [ ] E2E fixture covers first full load, second no-op load, one corrected quote, one retracted corporate action, and one newly listed XETRA ISIN.
- [ ] PostgreSQL assertions prove keys, counts, bounds, UTC `TIMESTAMPTZ(6)`, and read/write role separation.
- [ ] No test depends on Portfell source code or imports the Portfell package.
- [ ] Canonical loader CI is green from one SHA.

### PR308 — `pr308-portfell-postgres-read-contract`

Repository: `SergejSchweizer/portfell`.
Branch: `refactor/pr308-portfell-postgres-read-contract`.
Git status: not started; branch absent; blocked on PR298.
Depends on: PR298.
Atomic outcome: freeze Portfell's read-only market-data gateway and DTO contract against the new PostgreSQL schema; no page is switched yet.
Owned paths: new `src/portfell/market_data/contracts.py`, read-only connection/config module, contract tests, architecture test.
Required commit scope: `refactor(pr308-portfell-postgres-read-contract): ...`.
Tasks / Acceptance:
- [ ] Typed interfaces cover listing metadata, bounded quote history, dividends, and splits needed by current analytics.
- [ ] Connection configuration targets external PostgreSQL through env/secret DSN and defaults/examples document `10.10.1.3:54321` without a password.
- [ ] Connection opens read-only transactions/session and has no DDL/mutation methods.
- [ ] Architecture tests forbid this layer importing EODHD, lake/path IO, hosted user/project modules, or loader package internals.
- [ ] Contract fixture matches PR298 table/column names and timestamp semantics exactly.

### PR309 — `pr309-portfell-listing-repository`

Repository: `SergejSchweizer/portfell`.
Branch: `feat/pr309-portfell-listing-repository`.
Git status: not started; branch absent; blocked on PR308.
Depends on: PR308.
Atomic outcome: implement only the read-only PostgreSQL listing metadata repository.
Owned paths: `src/portfell/market_data/postgres_listings.py`, focused tests.
Required commit scope: `feat(pr309-portfell-listing-repository): ...`.
Tasks / Acceptance:
- [ ] Queries only `portfell_market.listings` and returns deterministic full listing identities.
- [ ] Supports the metadata fields/filters required by Portfell without provider calls.
- [ ] Empty, duplicate-corrupt, and DB-unavailable states are typed and tested.
- [ ] SQL is parameterized and query plans use the frozen key/index contract.

### PR310 — `pr310-portfell-quote-repository`

Repository: `SergejSchweizer/portfell`.
Branch: `feat/pr310-portfell-quote-repository`.
Git status: not started; branch absent; blocked on PR308.
Depends on: PR308.
Atomic outcome: implement only bounded read-only quote history access from PostgreSQL.
Owned paths: `src/portfell/market_data/postgres_quotes.py`, focused tests.
Required commit scope: `feat(pr310-portfell-quote-repository): ...`.
Tasks / Acceptance:
- [ ] Query by exact listing identity and optional inclusive business-date bounds.
- [ ] Preserve `trade_date`, UTC-aware `timestamp_eod`, adjusted close, OHLC, and volume types without filesystem conversion.
- [ ] Return order is deterministic by listing identity then business date.
- [ ] Tests prove no fallback to Parquet/local shared-market files and no mutation SQL exists.

### PR311 — `pr311-portfell-corporate-action-repository`

Repository: `SergejSchweizer/portfell`.
Branch: `feat/pr311-portfell-corporate-action-repository`.
Git status: not started; branch absent; blocked on PR308.
Depends on: PR308.
Atomic outcome: implement only read-only dividend/split access from PostgreSQL.
Owned paths: `src/portfell/market_data/postgres_corporate_actions.py`, focused tests.
Required commit scope: `feat(pr311-portfell-corporate-action-repository): ...`.
Tasks / Acceptance:
- [ ] Query dividends/splits by exact listing identity and date bounds with stable `event_key` exposure.
- [ ] Deterministic ordering and UTC-aware timestamp decoding are tested.
- [ ] No EODHD, local-lake, or mutation path is imported.

### PR312 — `pr312-metadata-stage-postgres-cutover`

Repository: `SergejSchweizer/portfell`.
Branch: `refactor/pr312-metadata-stage-postgres-cutover`.
Git status: not started; branch absent; blocked on PR309-PR311.
Depends on: PR309, PR310, PR311.
Atomic outcome: make the Metadata workflow read the XETRA universe from the PostgreSQL gateway only.
Owned paths: Metadata application service/page callbacks and its focused tests only.
Required commit scope: `refactor(pr312-metadata-stage-postgres-cutover): ...`.
Tasks / Acceptance:
- [ ] Metadata stage contains no provider/download button, token input, or fetch progress control.
- [ ] Filters operate on PostgreSQL listings and persisted single-workspace selection state only.
- [ ] UI/API failure for unavailable PostgreSQL is explicit and does not attempt another data source.
- [ ] Existing selection semantics keep full `(isin, exchange, code)` identity.

### PR313 — `pr313-univariate-stage-postgres-cutover`

Repository: `SergejSchweizer/portfell`.
Branch: `refactor/pr313-univariate-stage-postgres-cutover`.
Git status: not started; branch absent; blocked on PR309-PR311.
Depends on: PR309, PR310, PR311.
Atomic outcome: switch Univariate calculations to bounded PostgreSQL quote/corporate-action reads.
Owned paths: Univariate input service/callbacks and focused tests only.
Required commit scope: `refactor(pr313-univariate-stage-postgres-cutover): ...`.
Tasks / Acceptance:
- [ ] Univariate calculations receive only gateway DTOs and never LakePaths/shared-market paths.
- [ ] Existing financial formulas/results are unchanged for identical fixture rows.
- [ ] History bounds and missing-data evidence are derived from PostgreSQL rows, not local manifests.
- [ ] DB unavailable/no-history states are explicit and no provider refresh is triggered.

### PR314 — `pr314-bivariate-stage-postgres-cutover`

Repository: `SergejSchweizer/portfell`.
Branch: `refactor/pr314-bivariate-stage-postgres-cutover`.
Git status: not started; branch absent; blocked on PR309-PR311.
Depends on: PR309, PR310, PR311.
Atomic outcome: switch Bivariate calculations to PostgreSQL-backed selected quote history only.
Owned paths: Bivariate input service/callbacks and focused tests only.
Required commit scope: `refactor(pr314-bivariate-stage-postgres-cutover): ...`.
Tasks / Acceptance:
- [ ] Pair alignment/correlation/covariance inputs are gateway DTOs only.
- [ ] Existing calculation semantics and deterministic pair identity are unchanged for identical fixture rows.
- [ ] No filesystem discovery, local Gold correlation artifact, or provider call is reachable from the stage.

### PR315 — `pr315-multivariate-stage-postgres-cutover`

Repository: `SergejSchweizer/portfell`.
Branch: `refactor/pr315-multivariate-stage-postgres-cutover`.
Git status: not started; branch absent; blocked on PR309-PR311.
Depends on: PR309, PR310, PR311.
Atomic outcome: switch Multivariate optimizer input assembly to PostgreSQL-backed selected quote history only.
Owned paths: Multivariate input/alignment orchestration and focused tests only; solver implementations are read-only.
Required commit scope: `refactor(pr315-multivariate-stage-postgres-cutover): ...`.
Tasks / Acceptance:
- [ ] Aligned return matrix is built from the frozen quote gateway and current selection only.
- [ ] Optimizer objectives/solvers/walk-forward formulas are not changed in this PR.
- [ ] Common usable history is computed from actual DB observations and remains distinct from the observed envelope.
- [ ] No lake/shared-market/provider fallback exists.

### PR316 — `pr316-single-user-backend-cutover`

Repository: `SergejSchweizer/portfell`.
Branch: `refactor/pr316-single-user-backend-cutover`.
Git status: not started; branch absent; blocked on PR312-PR315.
Depends on: PR312, PR313, PR314, PR315.
Atomic outcome: remove multi-user/tenant/project/credential authority from the Python backend and replace it with one workspace composition.
Owned paths: hosted user/project/credential/membership services/routes/schemas, application composition, replacement single-workspace settings repository, focused backend tests.
Required commit scope: `refactor(pr316-single-user-backend-cutover): ...`.
Tasks / Acceptance:
- [ ] Delete user, tenant, membership, project-membership, hosted credential, per-user EODHD token, and project-bootstrap code paths; do not deprecate them.
- [ ] Canonical API/browser stage routes have no project slug/security scope.
- [ ] One workspace settings/selection authority remains and contains no `user_id`/`tenant_id`/membership columns.
- [ ] Tests prove no cross-user/project scenarios remain in production contracts.
- [ ] No market-data write authority is introduced into Portfell.

### PR317 — `pr317-single-user-ui-cutover`

Repository: `SergejSchweizer/portfell`.
Branch: `refactor/pr317-single-user-ui-cutover`.
Git status: not started; branch absent; blocked on PR312-PR315.
Depends on: PR312, PR313, PR314, PR315.
Atomic outcome: remove project/user/credential/download controls from the production UI and use the four simple single-workspace routes.
Owned paths: production Dash/web shell/navigation/pages plus UI/E2E tests; backend modules from PR316 are read-only.
Required commit scope: `refactor(pr317-single-user-ui-cutover): ...`.
Tasks / Acceptance:
- [ ] Navigation routes are exactly `/metadata`, `/univariate`, `/bivariate`, `/multivariate` for the workflow.
- [ ] Remove project selector, user/account switch, credential management, metadata fetch/download controls, and multi-project E2E fixtures.
- [ ] Preserve portfolio analysis/optimization controls and professional plots unrelated to tenancy/loading.
- [ ] UI displays a clear read-only data-source health state for PostgreSQL without exposing DSN credentials.

### PR318 — `pr318-delete-portfell-data-loading-stack`

Repository: `SergejSchweizer/portfell`.
Branch: `refactor/pr318-delete-portfell-data-loading-stack`.
Git status: not started; branch absent; blocked on PR316-PR317.
Depends on: PR316, PR317.
Atomic outcome: physically delete all in-repo market-data loading, EODHD, medallion, shared-market, refresh-worker, and legacy import code/tests.
Owned paths: obsolete loader/provider/lake modules, obsolete CLI commands/routes/workers/tests, dependency manifest entries directly used only by that stack.
Required commit scope: `refactor(pr318-delete-portfell-data-loading-stack): ...`.
Tasks / Acceptance:
- [ ] Delete EODHD HTTP/client/config/token code and every fetch/refresh/ingestion command from Portfell.
- [ ] Delete Bronze/Silver/Gold market-data persistence, shared-market revisions/coverage, market-data cron/worker, and legacy importer/fallback code.
- [ ] Delete tests/fixtures/docs that assert those removed behaviors rather than skipping them.
- [ ] Source search for `Eodhd`, `fetch-all-metadata`, `fetch-all-quotes`, `SharedMarketDataStore`, `PORTFELL_SHARED_DATA_ROOT`, and loader cron identifiers returns no production references except an explicit historical archive if retained.
- [ ] Portfolio math/statistics modules remain and all focused tests pass from PostgreSQL fixtures.

### PR319 — `pr319-simplify-portfell-runtime`

Repository: `SergejSchweizer/portfell`.
Branch: `refactor/pr319-simplify-portfell-runtime`.
Git status: not started; branch absent; blocked on PR318.
Depends on: PR318.
Atomic outcome: collapse runtime/dependencies/containers to a stable single-user read-only application after deletion.
Owned paths: app composition root, Docker/Compose, runtime env example, dependency lock, health/readiness, architecture tests.
Required commit scope: `refactor(pr319-simplify-portfell-runtime): ...`.
Tasks / Acceptance:
- [ ] Production Compose has Portfell `app` only and no local `postgres`, project bootstrap, market refresh, or download worker service.
- [ ] App startup validates read-only PostgreSQL connectivity/schema version and fails clearly on an incompatible/missing serving schema.
- [ ] Remove dependencies used only by provider ingestion, local medallion IO, multi-user auth/tenant infrastructure, or removed web stack.
- [ ] Architecture guard forbids production imports from removed namespaces/identifiers and forbids market-data mutation SQL.
- [ ] All application state required for optimization is either read-only market data or explicitly owned single-workspace/optimizer state; there is no second market-data authority.

### PR320 — `pr320-cross-repo-serving-contract-gate`

Repository: `SergejSchweizer/portfell`.
Branch: `test/pr320-cross-repo-serving-contract-gate`.
Git status: not started; branch absent; blocked on PR307 and PR319.
Depends on: PR307 (`portfell-data-loader`), PR319 (`portfell`).
Atomic outcome: prove compatibility between the independently versioned loader serving schema and Portfell reader without coupling source packages.
Owned paths: Portfell contract fixture/SQL smoke test, CI test harness/docs only.
Required commit scope: `test(pr320-cross-repo-serving-contract-gate): ...`.
Tasks / Acceptance:
- [ ] Test creates the frozen serving schema from a checked contract fixture, inserts representative XETRA rows, and exercises Metadata -> Univariate -> Bivariate -> Multivariate input flow.
- [ ] Portfell never imports `portfell-data-loader`; compatibility is PostgreSQL schema/semantics only.
- [ ] Test proves `TIMESTAMPTZ(6)`/UTC decoding, full listing identity, date bounds, and read-only app role.
- [ ] Schema mismatch fails fast with an actionable version error rather than silently falling back.

### PR321 — `pr321-production-destructive-cutover`

Repository: `SergejSchweizer/portfell`.
Branch: `docs/pr321-production-destructive-cutover`.
Git status: not started; branch absent; blocked on PR320.
Depends on: PR320.
Atomic outcome: freeze the one-time production cutover and operational rollback/verification procedure; no new application feature.
Owned paths: deployment/runbook docs, env templates, final no-legacy checklist, smoke-command documentation.
Required commit scope: `docs(pr321-production-destructive-cutover): ...`.
Tasks / Acceptance:
- [ ] Runbook stops Portfell, backs up only configuration/optimizer state worth retaining, deletes obsolete Portfell market-data artifacts, performs loader destructive bootstrap, validates PostgreSQL serving tables, then starts Portfell read-only.
- [ ] Runbook uses endpoint `10.10.1.3:54321` through environment configuration and never embeds a password.
- [ ] Verification queries check schema versions, row counts, unique XETRA listing count, min/max quote dates, duplicate keys, timestamp SQL types, UTC timezone, and app-role grants.
- [ ] Rollback is operational rollback to prior application image/config only; it does not re-enable old Portfell market-data loading.
- [ ] Final source/config search proves no legacy provider/lake/multi-user runtime path remains.

## 6. Superseded work

After PR296 merges, PR264-PR295 and their implementation branches are superseded by this architecture. They must not be merged as-is. Their branches may be retained temporarily as reference evidence, but new agents must not branch from them, cherry-pick them wholesale, or revive their project-scoped/scheduled-market-refresh assumptions.

Pure optimizer algorithms from those branches may be reimplemented later only through a new atomic work order after the PostgreSQL/single-user cutover; do not use that possibility as a reason to preserve legacy runtime dependencies.

## 7. Estimated engineering effort

This is a substantial but clean refactor rather than a migration project. The permission to delete and reload data removes the hardest compatibility and data-migration work.

Expected effort drivers:

- loader scaffold and medallion contracts: medium;
- three provider ingestion families: medium and highly parallelizable;
- PostgreSQL DDL/delta sync/role tests: medium-high because correctness and idempotency matter;
- full-XETRA bootstrap and provider-rate-limit validation: operationally high/variable;
- Portfell PostgreSQL read adapters/stage cutovers: medium and parallelizable;
- multi-user/data-loader deletion and runtime simplification: medium-high because many existing modules/tests must be removed coherently;
- cross-repo and destructive cutover gates: medium.

For a strong engineer this series is approximately 8-14 focused engineering days plus the wall-clock time of the first provider bootstrap. With several weak agents working only on dependency-safe sibling PRs, expect roughly 4-7 calendar days of implementation/review iterations if CI and PostgreSQL test infrastructure are reliable. The full XETRA historical download duration is intentionally not estimated here because it depends on the EODHD subscription, request pacing, history depth, and provider response behavior; PR306/PR307 must measure and record it instead of guessing.

The critical path is PR297 -> PR298 -> PR299 -> PR300/301/302 -> PR303 -> PR304 -> PR305 -> PR306 -> PR307 on the loader side, and PR308 -> PR309/310/311 -> PR312-315 -> PR316/317 -> PR318 -> PR319 -> PR320 -> PR321 on the Portfell side. Most source-family and stage-adapter work is deliberately parallel.