# Plotly Dash full-replacement contract v1

Status: normative replacement-boundary contract for PR345–PR360. `BACKLOG.md` remains the only executable backlog authority.

## Table of contents

1. [Final authorities](#1-final-authorities)
2. [Final browser routes](#2-final-browser-routes)
3. [Callback-to-service boundary](#3-callback-to-service-boundary)
4. [Clean app-state authority](#4-clean-app_state-authority)
5. [Legacy browser deletion](#5-legacy-browserui-deletion-boundary)
6. [Legacy database deletion](#6-legacy-portfell-database-deletion-boundary)
7. [Configuration boundary](#7-configuration-boundary)
8. [Negative-space rules](#8-negative-space-rules)
9. [Inventory semantics](#9-inventory-semantics)
10. [Handoff order](#10-handoff-order)

## 1. Final authorities

The final Portfell runtime has exactly three architectural authorities:

1. Plotly Dash is the only Portfell-maintained browser application.
2. `PORTFELL_DATABASE_URL` points only to the clean Portfell database `portfell_dash`, schema `portfell`.
3. `PORTFELL_MARKET_DATABASE_URL` points only to the external read-only `xetra_loader` database, schema `xetra_loader`.

The application database and market database are independent authorities. Neither DSN may fall back to the other. The external `xetra_loader_sync` schema is never a source and access denial remains PASS evidence.

## 2. Final browser routes

Exactly four product pages exist:

| Page | Route | Stable page ID |
| --- | --- | --- |
| Metadata | `/metadata` | `page-metadata` |
| Univariate | `/univariate` | `page-univariate` |
| Bivariate | `/bivariate` | `page-bivariate` |
| Multivariate | `/multivariate` | `page-multivariate` |

`/` redirects deterministically to `/metadata` and is not a fifth product page. There is no Dashboard, Home, Project, User, Provider, Download, Refresh, Fees, Resources, Documents, or separate Optimizer product page.

The detailed visual/page contract is `docs/contracts/plotly-dash-ui-v1.md`.

## 3. Callback-to-service boundary

Dash callbacks are orchestration/presentation only. They may validate presentation inputs, call typed application-service ports, map typed service values into components/figures, persist identifier-only browser state, and render typed public errors. They never execute SQL, own financial formulas, infer missing analytical values, or trigger work merely because a page renders or resizes.

### Metadata capability

Required typed capabilities:

- list/filter active Xetra listing metadata through the application service;
- preserve full listing identity `(isin, exchange, code)`;
- create/read versioned Metadata universes;
- read current Metadata universe/history/readiness;
- resolve inactive historical members without allowing them into a new active universe.

The current FastAPI surface that provides transitional equivalents includes Metadata builder options/project criteria and workflow/page-view endpoints. PR347 may refactor the concrete API/service names but must preserve the capability, not the legacy project/user authority.

### Univariate capability

Required typed capabilities:

- start/read one Univariate run for one persisted Metadata universe;
- list immutable Univariate result rows and typed unavailable evidence;
- create/read a versioned exact downstream selection;
- read source-snapshot ID, algorithm version, counts, status, and history;
- survive restart without browser-owned result authority.

The transitional `ResearchService` surface currently exposes `start_univariate`, `univariate_status`, `univariate_results`, `apply_selection`, and `selection_results`; replacement callers depend on the capability only.

### Bivariate capability

Required typed capabilities:

- plan/start/read one Bivariate run for the persisted Univariate selection;
- list immutable pair rows plus summary/covariance/correlation/tail evidence through typed service methods;
- preserve both full listing identities for every pair;
- surface unavailable common-calendar/covariance/correlation evidence explicitly;
- expose persisted counts, status, source snapshot, algorithm version, and history.

The transitional service exposes `bivariate_plan`, `start_bivariate`, `bivariate_status`, `bivariate_results`, `bivariate_summary`, `bivariate_covariance_matrix`, `bivariate_correlation_matrix`, and `bivariate_tail_risk_scatter`; replacement callers depend on the capability only.

### Multivariate capability

Required typed capabilities:

- start/read one Multivariate run for the matching persisted Bivariate lineage and one frozen objective ID;
- objectives are exactly `return_risk`, `return_drawdown`, and `minimum_risk`, with `return_risk` the default;
- read immutable summary, structure, candidate, performance, allocation/weights, drawdown, risk-contribution, validation, artifact and DecisionArtifact evidence;
- preserve requested/actual method, source snapshot, algorithm version, availability and production eligibility;
- reload the completed winner and evidence after restart.

The transitional research surface already exposes typed Multivariate detail methods. PR347 may change concrete composition but may not weaken this capability contract.

## 4. Clean `app_state` authority

PR345 creates the clean state schema in database `portfell_dash`, schema `portfell`. Only the following v1 concepts are persisted:

- singleton workspace identity `default`;
- immutable `market_source_snapshots`;
- versioned `metadata_universes`;
- exact `metadata_universe_members`;
- stage-neutral `analysis_runs`;
- immutable `analysis_artifacts`;
- versioned `univariate_selections`;
- exact `univariate_selection_members`;
- immutable `decision_artifacts`;
- presentation-only `ui_preferences`.

There is no `user_id`, tenant membership, project membership, provider credential owner, RLS tenant partition, browser cache table, legacy ingestion lifecycle, or compatibility view in the new schema.

All application-state SQL is owned by `src/portfell/app_state/**`. All external market SQL is owned by `src/portfell/market_source/**`. No Dash module contains SQL.

## 5. Legacy browser/UI deletion boundary

The deterministic inventory `legacy-ui-db-inventory-v1.json` is the sole deletion manifest for PR356 and PR357. `delete-pr356` owns the first-party React/Vite/TypeScript/TanStack/Node application and its production/test/build/runtime-only integration surfaces. The inventory deliberately groups `apps/web/**` as one complete path-prefix item so every file below that root is in scope, including package manifests/lockfiles, React source, browser tests, Vite/TypeScript config, Node server and Web Dockerfile.

PR356 must also remove or rewrite the legacy Web-only Compose/CI/scripts/entrypoints identified by the manifest. Backend analytical modules are not deleted merely because the old UI invoked them.

## 6. Legacy Portfell database deletion boundary

`delete-pr357` owns the old Portfell hosted database plane: old hosted schema/migration/catalog modules, old hosted PostgreSQL repositories/adapters, old tenant/project/user/provider-credential/navigation/workflow/status/download persistence, and runtime references that can connect to the old Portfell DB.

The generic PostgreSQL driver is retained because both `app_state` and `market_source` use PostgreSQL. Analytical domain code and the external market gateway are retained.

The external database `xetra_loader`, schema `xetra_loader`, tables `listings`, `eod_quotes`, `dividends`, and `splits` are explicitly excluded from deletion. `xetra_loader_sync` is also excluded from deletion because Portfell does not own it; Portfell must simply remain unable to use it.

## 7. Configuration boundary

Repository-root `config.yaml` is the only local non-secret PostgreSQL metadata authority. It is gitignored and never copied into images/artifacts. `config.example.yaml` is tracked and secret-free. It has separate `postgres.app` and `postgres.market` identities.

`PORTFELL_DATABASE_URL` and `PORTFELL_MARKET_DATABASE_URL` remain secret-supplied runtime connection authorities. Startup verifies their non-secret host/port/database/schema/role identity against `config.yaml` and fails closed on missing, malformed, mismatched, or collapsed authorities.

## 8. Negative-space rules

The completed replacement must contain none of the following production boundaries:

- first-party React, ReactDOM, TanStack Query, Vite, TypeScript, Vitest, npm/pnpm/yarn application build, or Node Web runtime;
- `apps/web/**`;
- old Portfell hosted tenant/control-plane database schema, migrations, repositories, connection fallback or active legacy DB volume;
- provider/EODHD acquisition, provider credentials, Portfell-owned market refresh, NAS/medallion market authority;
- direct SQL from Dash;
- market SQL outside `market_source`;
- application-state SQL outside `app_state`;
- `xetra_loader_sync` as a source;
- compatibility iframe, dual UI, dual database read/write, hidden old-UI flag, or old-schema fallback;
- runtime/test dependency on the external Plotly reference URL or copied branding/content/assets.

## 9. Inventory semantics

`docs/contracts/legacy-ui-db-inventory-v1.json` is canonical JSON with:

- `schema_version = 1`;
- a sorted `items` array keyed by `identifier`;
- each item has one of exactly four dispositions: `delete-pr356`, `delete-pr357`, `retain-backend`, `retain-test-only`;
- identifiers contain repository paths, path prefixes, configuration selectors, dependency names, runtime surface names, or database object families only;
- no passwords, tokens, secret values, or credential-bearing DSNs;
- no `unknown` disposition;
- explicit exclusion records for the externally owned xetra-loader authorities.

Identical source tree and frozen classification rules must produce byte-identical inventory. Validation is read-only/idempotent.

## 10. Handoff order

PR345 and PR348 may start from PR344 in parallel. PR346 follows PR345; PR347 follows PR346. PR348 must rebase onto PR347 before integration if shared production composition changed. Page PR349–PR352 start only once the PR347 service/state capability and PR348 shell primitives are both present. PR353 unifies state semantics, PR354 finalizes presentation, PR355 provides immutable parity evidence, PR356/PR357 execute manifest deletion in parallel, PR358 cuts runtime/Compose, PR359 proves negative space, and PR360 performs/document final production cutover.
