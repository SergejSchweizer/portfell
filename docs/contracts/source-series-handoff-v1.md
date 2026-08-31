# Portfell source-series handoff v1

Status: PR343 handoff into the mandatory Plotly Dash + clean application-database replacement series. `BACKLOG.md` remains the only executable backlog authority.

## Table of contents

1. [Frozen market-source API](#1-frozen-market-source-api)
2. [Application-service capabilities](#2-frozen-application-service-capabilities-consumed-by-the-replacement)
3. [Persisted analytical concepts](#3-persisted-analytical-concepts-that-cross-the-replacement-boundary)
4. [Four-page workflow](#4-four-page-workflow-and-browser-contract)
5. [Visualization requirements](#5-professional-visualization-requirements-carried-forward)
6. [Universe and History](#6-universe--history-requirements-carried-forward)
7. [Legacy idea reconciliation](#7-pr264pr295-idea-reconciliation)
8. [Deletion inventory seed](#8-deletion-inventory-seed-for-pr344)
9. [PR344 entry conditions](#9-pr344-entry-conditions)

## 1. Frozen market-source API

The final source-series market seam is `portfell.market_source.gateway.MarketDataGateway`.

```python
MarketDataGateway(connection_factory, *, role, member_of)

read_active_listings() -> tuple[Listing, ...]
read_snapshot(
    keys: Sequence[ListingKey],
    *,
    start: date,
    end: date,
) -> MarketDataSnapshot
```

`MarketDataSnapshot` contains materialized tuples of `listings`, `quotes`, `dividends`, and `splits`. Each gateway call owns one short-lived `REPEATABLE READ, READ ONLY` transaction, sets UTC session semantics, validates the configured non-superuser LOGIN/member-of role contract, materializes rows, and closes the transaction before CPU-heavy analysis.

Listing identity is exactly `(isin, exchange, code)`. ISIN alone is never a business key. The market source remains external `10.10.1.3:54321 / xetra_loader`, schema `xetra_loader`, business tables `listings`, `eod_quotes`, `dividends`, `splits`. Raw market SQL remains only under `src/portfell/market_source/**`. `xetra_loader_sync` remains inaccessible and is never a source.

`adjusted_close` is authoritative for return/risk/drawdown calculations. Missing adjusted close is typed `missing_adjusted_close`; raw close is not a fallback. Raw PostgreSQL `NUMERIC` remains `Decimal` until the centralized analytical projection boundary. Dividends remain income/distribution evidence and are not double-counted on top of adjusted-close returns. No new split-return transform is introduced by the replacement.

## 2. Frozen application-service capabilities consumed by the replacement

The replacement UI calls typed application services; it never calls SQL.

### Metadata

Current source-backed service: `MetadataProjectService` plus `metadata_source_catalog(MarketDataGateway)`.

Source-backed capabilities to preserve cleanly:

- read active metadata options/catalog;
- create a deterministic filtered universe from the supported metadata predicates;
- persist the exact full-identity members and external market snapshot lineage;
- return counts and typed empty/invalid states.

Legacy `user_id`, project ownership, project switching, hosted navigation projection, provider fetch, and download-run semantics are compatibility artifacts and are not part of the final service contract.

### Univariate

Current source-backed implementation: `MarketSourceUnivariateResearchService`.

Capabilities to preserve:

```text
start(selection/universe identity) -> immutable logical run identity/status
complete(selection/universe identity) -> persisted statistics + downstream selection authority
read status/results/selection settings through typed service ports
```

The run consumes one coherent market snapshot and its deterministic snapshot ID. Formula/annualization/income semantics remain backend-authoritative.

### Bivariate

Current source-backed implementation: `MarketSourceBivariateResearchService` plus `BivariateMarketSourceData`.

Capabilities to preserve:

```text
plan(exact persisted Univariate selection) -> pair eligibility/count evidence
start(exact persisted Univariate selection) -> immutable logical run
complete(exact persisted Univariate selection) -> persisted pair results/evidence
read status/results/matrices/summary through typed service ports
```

Full listing identity, common-calendar rules, minimum-observation rules, same-ISIN exclusions, and unavailable-not-zero semantics survive the replacement.

### Multivariate

Current source-backed implementation: `MarketSourceMultivariateResearchService` plus the existing Multivariate analytical core.

Capabilities to preserve:

- start one Multivariate run from the exact upstream Bivariate/Univariate dependencies;
- resolve the source snapshot pinned by upstream evidence and fail if it changed;
- build aligned inputs, validated risk model/candidates, walk-forward/OOS evidence, portfolio performance, income evidence, risk contribution, and final decision artifacts;
- persist and reload completed immutable results through the new application-state boundary;
- distinguish requested method from actual method and never hide solver failure behind Equal Weight.

The final UI exposes exactly three objective IDs: `return_risk` (default), `return_drawdown`, `minimum_risk`. Winner selection remains driven by OOS evidence; an in-sample-best substitute is prohibited.

## 3. Persisted analytical concepts that cross the replacement boundary

The clean `portfell_dash` database must recreate, not migrate, these canonical concepts:

- singleton workspace identity `default`;
- immutable `market_source_snapshots` lineage;
- versioned `metadata_universes` and exact full-identity members;
- stage-neutral immutable/logically idempotent `analysis_runs` with stage/status/input snapshot/algorithm version/timestamps/failure code;
- immutable `analysis_artifacts` by run and artifact type;
- versioned `univariate_selections` and exact members;
- immutable `decision_artifacts` explaining the Multivariate winner/availability/production eligibility;
- small `ui_preferences` that are presentation state only.

No legacy row is silently imported. The new schema contains no `user_id`, tenant, membership, project-membership, provider credential owner, navigation projection, workflow projection, status-event, provider-download, or browser-cache authority.

## 4. Four-page workflow and browser contract

The final workflow is exactly:

```text
Metadata -> Univariate -> Bivariate -> Multivariate -> final portfolio decision
```

The product has exactly four Dash pages and routes:

```text
/metadata
/univariate
/bivariate
/multivariate
```

`/` may redirect deterministically to `/metadata`; it is not a fifth page. There is no project selector, user selector, dashboard/home page, optimizer page separate from Multivariate, provider download page, or refresh page.

Every page uses one shared visual grammar: Portfell product header, four-item navigation, page title/subtitle, compact controls, KPI row where specified, white content cards, `Universe & History`, and a stage footer. The shared primitives are `PageHeader`, `ControlBar`, `KpiCard`, `ChartCard`, `TableCard`, `StatusBanner`, `HistoryCard`, and `StageFooter`.

## 5. Professional visualization requirements carried forward

The external reference `https://financial-dashboard-example.plotly.app/` is layout inspiration only. It is never fetched at runtime/test time and no branding/content/assets are copied.

Named analytical plots carried into the final Dash contract are:

- `Univariate Return / Risk Universe`;
- `Bivariate Return / Diversification Universe`;
- `Portfolio Candidate OOS Return / Risk`;
- `Cumulative Performance`;
- `Drawdown`;
- `Allocation` when a weight artifact exists;
- `Risk Contribution` when a risk-contribution artifact exists.

Plots use backend/service artifact values. Axis labels/units, hover identity, legend ordering, unavailable state, responsiveness, and accessibility semantics are explicit. Dash does not recompute financial statistics merely to draw a figure.

## 6. Universe & History requirements carried forward

The useful idea from the old PR264–PR295 plan is retained without its project/tenant assumptions: each page must expose persisted analytical lineage and history appropriate to that stage. The final contract uses current universe/version, member count, source snapshot short ID, run/algorithm identity, upstream selection/run identity, and stage readiness. Unavailable/not-run/blocked values are typed and never represented by fabricated zero or empty dates.

Where backend artifacts already contain observed/aligned/common-history ranges, those values are rendered. Dash must not reconstruct historical ranges or counts from raw market rows.

## 7. PR264–PR295 idea reconciliation

The legacy PR264–PR295 work orders were written for a project-scoped React-to-Dash migration over the old hosted database and, later, a Portfell-owned Sunday market refresh. Their product ideas are classified below. This classification is semantic; old implementation branches are not merge dependencies of PR344–PR360.

| Old key | Classification | Handoff |
| --- | --- | --- |
| PR264 | reimplement-in-dash | Keep four-page registry, typed presentation ports, stable IDs; discard project-slug/base-prefix migration assumptions. |
| PR265 | reimplement-in-dash | Keep compact four-stage shell; retire user/project selector and cross-project browser authority. |
| PR266 | reimplement-in-dash | Keep metadata predicates, exact counts, universe/history; retire provider fetch/download/project-creation UX. |
| PR267 | reimplement-in-dash | Keep Univariate run control, filters, immutable results; use new single-workspace state service. |
| PR268 | reimplement-in-dash | Keep Bivariate run control/pair evidence; use persisted single-workspace selection. |
| PR269 | reuse-cleanly | Preserve full listing identity, canonical IDs/serialization, availability/error principles; remove tenant/project security scope. |
| PR270 | reuse-cleanly | Preserve deterministic eligibility/Pareto reduction where used by the backend optimizer; UI never owns it. |
| PR271 | reuse-cleanly | Preserve typed solver candidates and no-hidden-Equal-Weight-fallback rule. |
| PR272 | reuse-cleanly | Preserve walk-forward/OOS winner/final-refit semantics; persistence target changes to `app_state`. |
| PR273 | reimplement-in-dash | Decision/history persistence/read ideas survive, but old hosted DB schema/repositories are replaced, not migrated. |
| PR274 | reimplement-in-dash | Keep auditable Multivariate optimizer page/Decision evidence; rebuild using final shared Dash primitives and new state DB. |
| PR275 | reimplement-in-dash | Keep one-Python-app/no-React cutover goal; final topology is the PR358 topology, not the old three-service/project-worker contract. |
| PR276 | retire | Portfell no longer owns market refresh; no Sunday full-research cron is part of the current final architecture. |
| PR277 | retire | Temporary Dash sidecar/container is unnecessary; PR348 mounts the final Dash application directly into the Python runtime. |
| PR278 | reuse-cleanly | Preserve run-control, availability, professional plot, deterministic fixture principles; implement them as PR348/PR354 shared primitives. |
| PR279 | reimplement-in-dash | Rebuild Univariate professional/history figures against final artifact/service contracts. |
| PR280 | reimplement-in-dash | Rebuild Bivariate professional/history figures against final artifact/service contracts. |
| PR281 | reuse-cleanly | Preserve exact three objectives, immutable settings/run identity, typed progress concepts where supported by backend jobs. |
| PR282 | reuse-cleanly | Preserve immutable DecisionArtifact/content identity/reason evidence; persist in clean `decision_artifacts`. |
| PR283 | reuse-cleanly | Preserve universe/history lineage semantics and full identity; replace project isolation with singleton workspace/version isolation. |
| PR284 | reuse-cleanly | Preserve deterministic redundancy reduction where the backend uses it; no UI implementation. |
| PR285 | reuse-cleanly | Preserve risk-model/aligned-history configuration evidence where emitted by backend artifacts. |
| PR286 | reuse-cleanly | Preserve selector/candidate integration as backend analytical composition only. |
| PR287 | reimplement-in-dash | Preserve read-only/lazy evidence projection principle; implement against clean `app_state` service ports, not old project-auth routes. |
| PR288 | reimplement-in-dash | Rebuild Multivariate candidate/Decision/history figures with final shared Plotly template. |
| PR289 | reimplement-in-dash | Rebuild callbacks around single-workspace typed services/state; retire project switching. |
| PR290 | reimplement-in-dash | Rebuild page layout from frozen final `PageHeader -> ControlBar -> KPI -> cards -> History -> StageFooter` hierarchy. |
| PR291 | reimplement-in-dash | Mount final Dash into FastAPI with final canonical non-project routes. |
| PR292 | reuse-cleanly | Preserve the deletion outcome: all first-party React/Vite/TypeScript/TanStack/Node UI is deleted by PR356 after parity. |
| PR293 | retire | Shared active-union provider refresh belongs to xetra-loader, not Portfell. |
| PR294 | retire | Scheduled per-project research orchestration is not part of the current four-page replacement contract. |
| PR295 | retire | Sunday scheduler/cron/lock is not part of the current final runtime. |

## 8. Deletion inventory seed for PR344

PR344 must turn this seed into a deterministic exact-file inventory. The seed intentionally names categories rather than pretending to be the final exact inventory.

### Legacy browser/UI seed

- `apps/web/**`;
- React/ReactDOM/TanStack/Vite/TypeScript/Vitest application dependencies and lock/build scripts;
- Node Web Docker/runtime stages and Compose `web` service;
- React-only browser fixtures, route generators, component tests, browser-state/cache code and runtime env;
- legacy project selector/project-slug navigation and browser switching semantics.

### Legacy application-database seed

- old hosted catalog migrations/schema objects under the legacy Portfell application schema;
- hosted user/tenant/membership/project-membership/provider-credential repositories;
- navigation/workflow/status-event projections and their repositories;
- legacy provider/download/bootstrap/ingestion database lifecycle objects;
- request-scope/RLS helpers that exist only to enforce multi-user/tenant security;
- old database bootstrap/import/repair utilities and Compose volume/service identity that are superseded by `portfell_dash`.

### Retain seed

- `src/portfell/market_source/**` external market reader contract;
- financial/statistical analytical core required by the four stages;
- typed application-service behavior needed by the final pages, refactored away from legacy persistence where necessary;
- generic PostgreSQL driver/runtime helpers still required by `app_state` or `market_source`;
- tests/fixtures that prove financial formulas, source projection, full listing identity, unavailable semantics, and market read-only behavior.

`xetra_loader` database/schema/tables are explicitly excluded from deletion.

## 9. PR344 entry conditions

PR344 may inventory and freeze the replacement contract from this handoff, but no item in this source series is called integrated merely because its stacked branch exists. GitHub merge-gate PASS and dependency-ordered integration are still required before production cutover. The stacked implementation tree is development evidence, not final acceptance evidence.
