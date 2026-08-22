# PostgreSQL Read-Plane and Single-User Portfell Cutover

Status: active Portfell implementation authority after PR296 is merged.

Last reviewed: 2026-08-22.

## 1. Goal

Refactor `SergejSchweizer/portfell` into a single-user portfolio analytics/optimization application that reads market data exclusively from PostgreSQL at `10.10.1.3:54321`.

All provider/download/medallion/PostgreSQL-write work belongs to `SergejSchweizer/xetra-data-loader`. Its active work orders are `XDL-PR001` through `XDL-PR033`. The old loader IDs PR297-PR307 are superseded.

The final production handoff is **XDL-PR033**, which must complete a real full XETRA -> PostgreSQL synchronization and independently reconcile the target database to validated Gold before Portfell PR320 may start.

## 2. Hard ownership boundary

```text
xetra-data-loader
EODHD -> XETRA discovery -> Bronze/Silver/Gold -> PostgreSQL 10.10.1.3:54321
                                                        |
                                                        | SELECT only as portfell_app
                                                        v
                                                     portfell
               Metadata -> Univariate -> Bivariate -> Multivariate -> optimization
```

Portfell owns only read-only market-data gateways, analytics/optimization, application-domain state, and single-user UI/API. It must not own EODHD/provider credentials, exchange discovery, medallion market persistence, market-data DDL/writers/sync state, loader scheduling, users/tenants/memberships/project authorization, provider-credential management, or loader fallback paths.

Portfell must not import `xetra-data-loader` as a Python package. PostgreSQL is the integration boundary.

## 3. Frozen external contract

- schema: `portfell_market`;
- tables: `listings`, `eod_quotes`, `dividends`, `splits`;
- listing key: `(isin, exchange, code)`;
- quote key: `(isin, exchange, code, trade_date)`;
- dividend/split key: `(isin, exchange, code, event_key)`;
- every PostgreSQL timestamp column exactly `TIMESTAMPTZ(6)`;
- DB session timezone UTC;
- `trade_date` remains `DATE`;
- `timestamp_eod` is the canonical UTC midnight anchor, not physical exchange close;
- `portfell_app` SELECT-only on `portfell_market`, no market-data DML/DDL and no `portfell_loader_sync` access;
- no Portfell provider/filesystem/NAS/dual-read fallback.

Schema work may begin after XDL-PR007. Permission integration may use XDL-PR008. Final production cutover may not rely on XDL-PR032 alone: XDL-PR033 must be merged with a PASS production PostgreSQL reconciliation report.

## 4. Single-user target

Delete user, tenant, membership, project-membership, credential-owner, project-bootstrap-worker, project-scoped refresh, and multi-user authorization concepts. Domain IDs for saved portfolios, optimization runs, analysis runs, and decisions remain allowed but cannot act as security scopes.

Canonical browser routes:

```text
/metadata
/univariate
/bivariate
/multivariate
```

REST remains under `/api`.

## 5. Git contract for weak agents

For every work order, the exact work-order name must appear in branch name, every Conventional Commit message, and PR title. Before editing, record `git status --short --branch`. Start from the exact merged dependency SHA. Parallel siblings start from the same predecessor SHA and never from each other. If a dependency is not merged, remain blocked. No compatibility shims, hidden legacy feature flags, or opportunistic refactors.

## 6. Execution graph

```text
XDL-PR007 -> PR308
              |
       PR309 || PR310 || PR311
              |
       PR312 || PR313 || PR314 || PR315
              |
            PR316 || PR317
              |
            PR318 -> PR319
              |
XDL-PR033 ------+----> PR320 -> PR321
```

Safe parallel waves:

- PR309/PR310/PR311 after PR308;
- PR312/PR313/PR314/PR315 after PR309-PR311;
- PR316/PR317 after PR312-PR315.

PR308 does not require a complete historical loader. PR320 is the hard cutover gate and requires **XDL-PR033 + PR319**.

## 7. Work orders

### PR308 — pr308-portfell-postgres-read-contract
Branch: `refactor/pr308-portfell-postgres-read-contract`.
Commit scope: `refactor(pr308-portfell-postgres-read-contract): ...`.
Depends on: XDL-PR007 merged.
Owned scope: read-only DB config/contracts/gateway seam + focused tests.
Tasks: configure external PostgreSQL from env/secrets; define DTOs matching frozen market tables; timezone-aware UTC decoding; read-only connection/session factory; independent contract fixtures; architecture guard against provider/lake writers; do not switch stages yet.
Acceptance: contracts match loader DDL/keys; no secret in source; no INSERT/UPDATE/DELETE/DDL path; no xetra package import; workflow behavior unchanged.

### PR309 — pr309-portfell-listing-repository
Branch: `feat/pr309-portfell-listing-repository`.
Commit scope: `feat(pr309-portfell-listing-repository): ...`.
Depends on: PR308.
Owned scope: listing repository + tests.
Tasks: query `portfell_market.listings`; preserve `(isin,exchange,code)`; deterministic filter/sort; explicit empty/not-found behavior.
Acceptance: duplicate ISIN under different identities preserved; deterministic ordering; no mutation; DB failure never triggers fallback.

### PR310 — pr310-portfell-quote-repository
Branch: `feat/pr310-portfell-quote-repository`.
Commit scope: `feat(pr310-portfell-quote-repository): ...`.
Depends on: PR308.
Owned scope: quote repository + tests.
Tasks: query quote history by full identity/date range; preserve `trade_date` and UTC timestamp; deterministic ordering; duplicate-key rejection.
Acceptance: exact ordering/key behavior; UTC preserved; no provider/filesystem fallback.

### PR311 — pr311-portfell-corporate-action-repository
Branch: `feat/pr311-portfell-corporate-action-repository`.
Commit scope: `feat(pr311-portfell-corporate-action-repository): ...`.
Depends on: PR308.
Owned scope: dividend/split repositories + tests.
Tasks: query actions by full identity/date range; preserve loader `event_key`; deterministic conversion/order; duplicate-event rejection.
Acceptance: semantic identity preserved; no regeneration from run-local data; no mutation/fallback.

### PR312 — pr312-metadata-stage-postgres-cutover
Branch: `refactor/pr312-metadata-stage-postgres-cutover`.
Commit scope: `refactor(pr312-metadata-stage-postgres-cutover): ...`.
Depends on: PR309-PR311.
Owned scope: Metadata stage source seam/API/UI controls + tests.
Tasks: PostgreSQL listings only; preserve relevant filtering; remove token/fetch/progress/refresh controls from stage; explicit empty-data failure; leave physical legacy deletion to PR318.
Acceptance: zero provider/filesystem reads; no metadata-download controls; filtering regression tests pass; no fallback.

### PR313 — pr313-univariate-stage-postgres-cutover
Branch: `refactor/pr313-univariate-stage-postgres-cutover`.
Commit scope: `refactor(pr313-univariate-stage-postgres-cutover): ...`.
Depends on: PR309-PR311.
Owned scope: Univariate input seam + tests.
Tasks: quotes/actions from repositories; preserve current formulas/date windows; remove shared-market dependencies; explicit incomplete-data failure.
Acceptance: calculations unchanged; PostgreSQL DTOs only; no fallback.

### PR314 — pr314-bivariate-stage-postgres-cutover
Branch: `refactor/pr314-bivariate-stage-postgres-cutover`.
Commit scope: `refactor(pr314-bivariate-stage-postgres-cutover): ...`.
Depends on: PR309-PR311.
Owned scope: Bivariate input/alignment seam + tests.
Tasks: PostgreSQL aligned histories; preserve formulas; deterministic intersection rules; remove legacy source references.
Acceptance: PostgreSQL DTOs only; alignment/formulas regression-tested; no fallback.

### PR315 — pr315-multivariate-stage-postgres-cutover
Branch: `refactor/pr315-multivariate-stage-postgres-cutover`.
Commit scope: `refactor(pr315-multivariate-stage-postgres-cutover): ...`.
Depends on: PR309-PR311.
Owned scope: Multivariate/optimizer market-input assembly + tests.
Tasks: use repositories for universe/return matrix/risk inputs; preserve solver/objective/walk-forward internals; deterministic multi-asset alignment.
Acceptance: no provider/filesystem input; fixture matrices exact; optimizer interfaces stable; missing input explicit.

### PR316 — pr316-single-user-backend-cutover
Branch: `refactor/pr316-single-user-backend-cutover`.
Commit scope: `refactor(pr316-single-user-backend-cutover): ...`.
Depends on: PR312-PR315.
Owned scope: backend authority/context/API cleanup + tests.
Tasks: remove user/tenant/membership/project/credential authority and project-bootstrap workers; replace request-time security scoping with one workspace; preserve non-security domain IDs.
Acceptance: backend works without multi-user/project records; no provider credential API/storage; source guards prevent reintroduction.

### PR317 — pr317-single-user-ui-cutover
Branch: `refactor/pr317-single-user-ui-cutover`.
Commit scope: `refactor(pr317-single-user-ui-cutover): ...`.
Depends on: PR312-PR315.
Owned scope: UI routes/navigation/user/project/provider-loading controls + tests.
Tasks: canonical four routes; remove project selector/slug routing/user switching/provider token/fetch/progress/scheduler UI; preserve analytics controls/figures.
Acceptance: no project/user prefix needed; no provider/loading controls rendered; no UI-triggered fallback.

### PR318 — pr318-delete-portfell-data-loading-stack
Branch: `refactor/pr318-delete-portfell-data-loading-stack`.
Commit scope: `refactor(pr318-delete-portfell-data-loading-stack): ...`.
Depends on: PR316+PR317.
Owned scope: physical deletion of Portfell provider/medallion/refresh/fallback code + guards.
Tasks: delete EODHD client/config; market-data Bronze/Silver/Gold/shared-market/NAS code; refresh workers/schedulers/provider fetch CLI; loading-only tests; aliases/flags that reactivate old loader.
Acceptance: no executable loader/fallback remains; analytics tests green; source guard detects forbidden reintroduction.

### PR319 — pr319-simplify-portfell-runtime
Branch: `refactor/pr319-simplify-portfell-runtime`.
Commit scope: `refactor(pr319-simplify-portfell-runtime): ...`.
Depends on: PR318.
Owned scope: dependencies/composition/Compose/deployment docs + tests.
Tasks: remove loader/multi-user runtime dependencies; require external PostgreSQL; remove Portfell-owned market DB/loader worker services; target one long-running `app`; no EODHD secret required.
Acceptance: app starts against external PostgreSQL; no loader/local-market-DB service; dependency tree pruned; quality gates green.

### PR320 — pr320-cross-repo-serving-contract-gate
Branch: `test/pr320-cross-repo-serving-contract-gate`.
Commit scope: `test(pr320-cross-repo-serving-contract-gate): ...`.
Depends on: **XDL-PR033 merged with production report PASS + PR319 merged**.
Owned scope: cross-repo contract/real-serving-plane smoke tests + documentation.
Tasks: consume XDL-PR033 sanitized production acceptance report and frozen SQL contract without importing loader Python; verify report identifies target `10.10.1.3:54321` and PASS full reconciliation; run Portfell repositories/stage smoke queries against the verified serving plane or a contract-faithful isolated copy; assert timestamp/key behavior and full identity handling; assert `portfell_app` read-only; document exact repository SHAs.
Acceptance: XDL-PR033 report confirms complete real sync, exact Gold/PostgreSQL row counts, zero key diffs, matching semantic fingerprints, zero duplicates/orphans, matching bounds, UTC/TIMESTAMPTZ(6), and zero-mutation unchanged replay; all Portfell stage smoke paths consume the contract; app-role mutation fails; no package coupling.

### PR321 — pr321-production-destructive-cutover
Branch: `docs/pr321-production-destructive-cutover`.
Commit scope: `docs(pr321-production-destructive-cutover): ...`.
Depends on: PR320.
Owned scope: production cutover/runbook only.
Tasks: backup surviving Portfell analytics/optimizer state; classify legacy market-data state as disposable; reference XDL-PR033 verified production state rather than duplicating loader logic; provide DB verification queries and four-route smoke checks; enumerate legacy deletion; rollback application/config only without reactivating loader fallback.
Acceptance: operator can execute without guessing; XDL-PR033 PASS is a mandatory precondition; rollback cannot reactivate old loading; checklist maps to target architecture.

## 8. Final Portfell completion gate

Portfell is complete only when all of the following hold on clean `main`:

- Metadata, Univariate, Bivariate, and Multivariate read exclusively from `portfell_market`;
- `portfell_app` cannot mutate market tables;
- no EODHD/provider-fetch logic, medallion/shared-market/NAS persistence, market-data scheduler/refresh worker, or fallback remains;
- no user/tenant/membership/project-membership/provider-credential runtime remains;
- canonical routes are `/metadata`, `/univariate`, `/bivariate`, `/multivariate` with no project selector/slug requirement;
- runtime is a single-user app against external PostgreSQL;
- old market-data artifacts are deleted, not migrated;
- no Python-package import coupling to `xetra-data-loader` exists;
- **XDL-PR033 has completed the real full XETRA synchronization to PostgreSQL `10.10.1.3:54321` and independently verified the database against validated Gold with report PASS**;
- PR320 proves Portfell consumes that verified serving plane correctly;
- PR321 provides executable destructive cutover/rollback without legacy-loader reactivation.
