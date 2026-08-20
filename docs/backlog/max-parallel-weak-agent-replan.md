# Maximum-Parallel Weak-Agent Execution Replan

Status: active normative override for dependency graph, PR scope boundaries, file ownership, and parallel-wave scheduling of the remaining Dash / research / optimizer / weekly-refresh work.

This document refines the already-active requirements in `BACKLOG.md`, `docs/backlog/plotly-dash-multivariate-optimizer-ui.md`, `docs/backlog/plotly-dash-multivariate-optimizer-ui-detailed-v1.md`, `docs/backlog/plotly-dash-professional-plots-weekly-refresh.md`, `docs/backlog/current-code-correctness-amendment.md`, `docs/backlog/current-code-project-isolation-addendum.md`, and `docs/backlog/universe-history-pipeline-amendment.md`.

Where this file changes a remaining PR's dependency, branch, ownership, or scope split, this file wins. It does **not** remove any financial, correctness, plotting, project-isolation, universe/history, or scheduled-refresh acceptance requirement. Requirements moved out of an old PR are redistributed below and remain mandatory in the new owning PR.

## Goal

Maximize safe parallel implementation by two simple weak agents while keeping every PR atomic, deterministic, independently reviewable, and mergeable. The plan deliberately separates contract freezes, backend computation, persistence/API, page presentation, and production cutover so two agents can work concurrently without editing the same files or inferring missing architecture.

## Hard execution rules

- Exactly two implementation agents are assumed. No wave contains more than two active PRs.
- A parallel wave starts only from the exact same merged predecessor `main` SHA. Parallel branches never branch from each other.
- Both PRs in a wave must be merged before the next dependency wave starts, unless the graph explicitly says a later PR depends on only one lane.
- An agent owns only the files listed by its PR. Editing a sibling PR's files is forbidden.
- Shared enums, IDs, protocols, dataclasses, reason codes, plot IDs, objective IDs, route suffixes, snapshot fields, stage IDs, and fixture IDs are frozen in PR264. Later PRs import them and may not rename or duplicate them.
- Every PR has exactly one checklist named `Tasks / Acceptance`. A checkbox is complete only when both implementation and named verification exist.
- No PR may combine presentation calculations with financial calculations. Dash renders typed server evidence only.
- No production path may enumerate high-dimensional ISIN subsets or weight grids.
- Full listing identity is always `(isin, exchange, code)`.
- Unavailable is never encoded as numeric zero, infinity, empty date, or blank string when the field is semantically unavailable.
- Heavy Uni/Bi/Multi work is durable-worker owned. API/Dash processes never own long-running calculation threads.
- All manual and Sunday scheduled runs use the same service contracts and immutable result identities.

## Scope redistribution from the old plan

The old PR IDs are preserved where useful, but large PRs are narrowed and new PRs are introduced:

- old PR264 -> PR264 contract freeze + PR265 runtime/shell;
- old PR267 -> PR267 Univariate backend + PR277 Univariate Dash;
- old PR268 -> PR268 Bivariate backend + PR278 Bivariate Dash;
- old PR269 -> PR264 shared contracts + PR269 durable execution/persistence foundation;
- old PR274 -> PR274 Multivariate page shell + PR279 Universe/Risk tabs + PR280 Optimization/Validation/Final tabs;
- old PR275 -> PR281 production runtime preparation + final PR275 cutover;
- old PR276 keeps the weekly orchestrator but no longer waits for UI cutover; it depends on final backend research contracts, not React deletion.

No old acceptance criterion is dropped. Professional plot requirements formerly attached to PR267/268 move to PR277/278. Multivariate figure requirements formerly attached only to PR274 are split across PR274/279/280. Correctness requirements remain attached to the backend owner that actually fixes the defect.

## Maximum-parallel execution graph

```text
MERGED PR458 planning gate
        |
        v
GATE 0  PR264 shared contract + fixture freeze
        |
        +--------------------------------------+
        |                                      |
WAVE 1  PR265 Dash runtime/shell               PR269 durable research execution foundation
        |                                      |
        +------------------- merge both -------+
                            |
        +--------------------------------------+
        |                                      |
WAVE 2  PR267 Univariate backend               PR268 Bivariate backend
        |                                      |
        +------------------- merge both -------+
                            |
        +--------------------------------------+
        |                                      |
WAVE 3  PR270 automatic universe selector      PR271 risk models + production solvers
        |                                      |
        +------------------- merge both -------+
                            |
        +--------------------------------------+
        |                                      |
WAVE 4  PR272 durable Multi orchestrator       PR273 Decision/history persistence + API
        |                                      |
        +------------------- merge both -------+
                            |
        +--------------------------------------+
        |                                      |
WAVE 5  PR274 Multi page shell/run control     PR281 production Python runtime preparation
        |                                      |
        +------------------- merge both -------+
                            |
        +--------------------------------------+
        |                                      |
WAVE 6  PR279 Multi Universe/Risk tabs         PR280 Multi Optimization/Validation/Final tabs
        |                                      |
        +------------------- merge both -------+
                            |
        +--------------------------------------+
        |                                      |
WAVE 7  PR277 Univariate Dash                  PR278 Bivariate Dash
        |                                      |
        +------------------- merge both -------+
                            |
        +--------------------------------------+
        |                                      |
WAVE 8  PR266 Metadata Builder Dash            PR276 Sunday full research refresh
        |                                      |
        +------------------- merge both -------+
                            |
                            v
FINAL   PR275 React deletion + canonical route/Compose cutover
                            |
                            v
                    final one-SHA release gate
```

The wave order after Wave 4 is chosen for two-agent capacity, not because every later UI PR technically depends on all earlier UI PRs. If more than two agents are ever allowed, PR266, PR277, PR278, PR274, PR276, and PR281 may start as soon as their explicit dependencies below are merged.

---

# PR264 — Shared Research/Dash Contract And Fixture Freeze

Branch: `feat/research-contract-freeze`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(contracts): freeze research, Dash, optimizer, and history contracts`.

Required squash subject: `feat(contracts): freeze research, Dash, optimizer, and history contracts`.

Base: current `main` containing merged PR458.

Merge method: squash only.

Priority: P0 serial gate.

Depends on: merged PR458 only.

Scope: contracts and deterministic fixtures only. No Dash runtime, page implementation, Docker service, database migration, financial recomputation, provider call, or long-running worker implementation.

Owned paths:
- `src/portfell/dash_ui/contracts.py`;
- `src/portfell/dash_ui/ids.py`;
- `src/portfell/dash_ui/plot_contracts.py`;
- `src/portfell/dash_ui/run_control.py`;
- new shared research contract modules under `src/portfell/research_contracts/`;
- contract/fixture tests only.

Tasks / Acceptance:
- [ ] Freeze exactly four workflow IDs/routes, `StatisticsRunControl`, objective IDs `return_risk|return_drawdown|minimum_risk`, run statuses, public failure codes, eight Multivariate DecisionArtifact stage IDs, weekly stage IDs, and all production figure IDs; registry tests reject additions/renames without explicit version change.
- [ ] Freeze `ListingIdentity`, `MetricAvailability`, `ConfigurationId`, `ResearchJobAttempt`, `ResearchUniverseSnapshot`, `DecisionArtifact`, and typed section-availability contracts with canonical serialization and stable IDs; deterministic round-trip tests pass.
- [ ] Freeze `ResearchUniverseSnapshot` semantics for listing/unique-ISIN counts, removed reasons, observed envelope, common usable history, listing-history distribution, pair-history distribution, aligned optimization calendar, and typed not-applicable values; zero-vs-unavailable regression fixtures pass.
- [ ] Freeze `ProfessionalPlotContract`, shared numeric/date/listing formatters, and required title/axis/legend/hover metadata for every already-planned figure; contract tests reject missing title/axes/semantic legend/hovertemplate where required.
- [ ] Freeze `DashResearchGateway` and backend service protocols so later UI/backend PRs can compile against fixtures without importing each other's implementation; architecture tests forbid DB/provider/lake/formula objects in Dash contracts.
- [ ] Add deterministic two-project fixtures including duplicate-ISIN multi-exchange listings, unavailable metrics, same-method different-configuration candidates, Uni/Bi/Multi snapshots, all three objectives, all decision stages, walk-forward ranges, and final portfolio evidence; byte-stability tests pass.

Parallelization: serial gate. One agent edits contracts; the second agent may review and add tests only after the contract commit is frozen inside the branch. No concurrent contract edits.

Security: no credentials or authorization bypass; only typed data shapes.

Determinism: canonical serialization and frozen IDs are the sole authority.

Idempotency: pure contracts/fixtures mutate no runtime state.

Rollback: revert PR264; no persistent migration exists.

---

# PR265 — Dash Runtime, Shell, Navigation, And Shared Evidence Components

Branch: `feat/dash-runtime-shell`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(dash): add runtime, shell, navigation, and shared evidence components`.

Required squash subject: `feat(dash): add runtime, shell, navigation, and shared evidence components`.

Base: exact PR264 merge commit.

Merge method: squash only.

Priority: P0.

Depends on: PR264.

Scope: presentation/runtime only. Temporary `/dash/` coexistence runtime, shell/navigation, page registration, shared run-control renderer, Universe & History summary, Research Universe & History Pipeline renderer, typed gateway adapter. No Metadata/Uni/Bi/Multi page-specific analytics.

Owned paths:
- `src/portfell/dash_ui/app.py`;
- `src/portfell/dash_ui/runtime.py`;
- `src/portfell/dash_ui/shell.py`;
- `src/portfell/dash_ui/navigation.py`;
- shared presentation components/CSS;
- temporary `apps/dash/Dockerfile` and temporary Dash compose profile only.

Tasks / Acceptance:
- [ ] Start a temporary Dash runtime under `/dash/` with exactly four registered workflow routes and no import-time provider/database/calculation side effects; runtime/Docker smoke tests pass.
- [ ] Render responsive shell, project selector, four-stage sidebar, process overview, shared `StatisticsRunControl`, `Universe & History` summary, and `Research Universe & History Pipeline` from PR264 fixtures only; desktop/mobile component tests pass.
- [ ] Implement typed `DashResearchGateway` adapter boundary with project identity on every project-scoped call; architecture tests prove `dash_ui` cannot import PostgreSQL, provider, lake, risk-model, portfolio, or raw table readers.
- [ ] Project switching clears old-project evidence before new reads complete and never flashes cross-project counts/plots; two-project deterministic tests pass.
- [ ] Temporary Dash container receives no DB/provider secret and browser persistence stores no credentials, matrices, series, weights, or DecisionArtifacts; security tests/docs pass.

Parallelization: Wave 1 Agent A, parallel with PR269. Files overlap with no PR269-owned paths.

Security: Dash is presentation only.

Determinism: route/ID/fixture contracts define the runtime shape.

Idempotency: startup, health, navigation, and reads mutate nothing.

Rollback: remove temporary Dash runtime/profile; React remains production UI until PR275.

---

# PR269 — Durable Research Execution, Project-Scoped State, Safe Errors, And Readiness Foundation

Branch: `feat/durable-research-execution`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(research): add durable attempts, project-scoped state, and readiness`.

Required squash subject: `feat(research): add durable attempts, project-scoped state, and readiness`.

Base: exact PR264 merge commit.

Merge method: squash only.

Priority: P0 correctness foundation.

Depends on: PR264.

Scope: generic backend execution/persistence infrastructure only. No Uni/Bi/Multi formulas, selectors, solvers, Dash pages, or scheduled orchestration.

Owned paths:
- generic research run/attempt repository modules;
- PostgreSQL migrations/repository changes for attempts/leases/project-scoped current selections/shared snapshot storage primitives;
- safe public error mapping;
- health/readiness modules;
- generic worker claim/heartbeat/reclaim tests.

Tasks / Acceptance:
- [ ] Implement durable `ResearchJobAttempt` claim/lease/heartbeat/reclaim semantics in the existing worker authority; API-process daemon/background threads are not required for heavy research execution; restart/reclaim integration tests pass.
- [ ] Make status/read APIs strictly non-mutating; elapsed wall clock during GET cannot fail a still-owned attempt; stale-attempt publication is rejected by attempt/lease identity tests.
- [ ] Change current Univariate selection authority from user-global to at least `(user_id, project_id)` with migration/backfill and uniqueness enforcement; two-project A->B/B->A tests prove isolation.
- [ ] Implement safe public error-code envelopes while retaining server-internal diagnostics; tests prove raw exception text, SQL, paths, provider payloads, and secrets never reach browser-visible failure fields.
- [ ] Add generic immutable result/snapshot publication primitive with atomic publish-after-success semantics and idempotent logical-run reuse; interrupted-write tests prove prior completed evidence remains readable.
- [ ] Separate liveness from dependency-aware readiness and make production readiness fail when PostgreSQL/request dependencies are unavailable; focused readiness tests pass.

Parallelization: Wave 1 Agent B, parallel with PR265. No Dash paths.

Security: errors redacted; authorization/project keys enforced in repositories.

Determinism: stable logical-run and attempt IDs from frozen contracts.

Idempotency: duplicate claims/writes converge or fail closed without duplicate logical runs.

Rollback: revert migration/repository changes with documented schema rollback; no analytical artifact deletion.

---

# PR267 — Univariate Backend Correctness, Durable Run, And History Snapshot

Branch: `feat/univariate-durable-research`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(univariate): make research durable and publish typed history evidence`.

Required squash subject: `feat(univariate): make research durable and publish typed history evidence`.

Base: exact `main` after PR265+PR269 merge.

Merge method: squash only.

Priority: P0.

Depends on: PR264, PR269.

Scope: Univariate analytical/service/backend only. No Dash page/figure implementation.

Owned paths:
- `src/portfell/univariate_statistics.py` and Uni-specific availability adapters;
- Uni service/orchestrator/repository integration;
- Uni snapshot producer;
- Uni-focused tests.

Tasks / Acceptance:
- [ ] Replace ambiguous numeric sentinels for unavailable Univariate ratios/tail/history metrics with PR264 `MetricAvailability` semantics while preserving genuine observed zero; zero-vs-unavailable tests pass.
- [ ] Run heavy Univariate computation through PR269 durable attempts with deterministic logical-run reuse, progress, restart/reclaim, and atomic completed publication; process-restart integration test passes.
- [ ] Publish one immutable Univariate `ResearchUniverseSnapshot` containing full listing count, unique ISINs, removed/data-quality reasons, observed envelope, per-listing history min/median/max, and common downstream overlap when meaningful; deterministic fixture assertions pass.
- [ ] Preserve existing return/dividend/data-quality calculations and cache identity unless explicitly versioned by this correctness change; regression tests compare unaffected metrics against fixed fixtures.
- [ ] Project-scoped saved/current Univariate selection uses the PR269 `(user_id, project_id)` authority and never leaks across projects; A/B isolation test passes.

Parallelization: Wave 2 Agent A, parallel with PR268. Uni-only backend files.

Security: authorize project/run before data access; safe reason codes only.

Determinism: listing identity, input revision, settings, and contract version define one result.

Idempotency: duplicate starts reuse one logical run and completed revision.

Rollback: revert Uni service/version while retaining prior immutable results.

---

# PR268 — Bivariate Backend Correctness, Durable Run, Pair Coverage, And Atomic Publication

Branch: `feat/bivariate-durable-research`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(bivariate): make pair research durable, exact, and atomic`.

Required squash subject: `feat(bivariate): make pair research durable, exact, and atomic`.

Base: same exact post-PR265/PR269 `main` as PR267.

Merge method: squash only.

Priority: P0.

Depends on: PR264, PR269.

Scope: Bivariate analytical/service/backend only. No Dash page/figure implementation.

Owned paths:
- `src/portfell/bivariate_statistics.py`;
- pair-plan/exact-pair helpers where required;
- Bivariate service/repository integration;
- pair coverage snapshot producer;
- Bivariate-focused tests.

Tasks / Acceptance:
- [ ] Build one exact eligible pair set after same-ISIN exclusions and use that same set for total count, progress, calculation, paging, publication, and history distribution; duplicate-ISIN cross-listing fixture proves exact count.
- [ ] Preserve completed Bivariate revisions on identical restart, reuse unchanged completed results, and atomically publish replacement rows only after successful recomputation; failure-injection test proves a failed rerun cannot erase prior complete evidence.
- [ ] Run heavy Bivariate work through PR269 durable attempts with progress/restart/reclaim and stale-attempt rejection; worker restart test passes.
- [ ] Encode unavailable correlation/tail/downside metrics with typed availability rather than zero sentinels; insufficient-observation fixtures distinguish genuine zero from unavailable.
- [ ] Publish one immutable Bivariate `ResearchUniverseSnapshot` with listing/unique-ISIN counts, exact pair count, pairwise shared-observation min/median/max/distribution, observed envelope, and common downstream overlap where meaningful; deterministic assertions pass.
- [ ] Label independently pairwise-aligned covariance as pairwise covariance evidence/surface and prohibit PSD/eigenvalue/determinant claims unless backed by a separately estimated common-calendar matrix; semantic regression tests pass.

Parallelization: Wave 2 Agent B, parallel with PR267. Bi-only backend files.

Security: authorized project and source Uni revision required.

Determinism: exact pair set, source revision, settings, version define one result.

Idempotency: identical rerun reuses complete revision; no duplicate pair rows.

Rollback: revert Bivariate service/version; prior immutable completed results remain readable.

---

# PR270 — Automatic Multivariate Universe Selector And History-Impact Evidence

Branch: `feat/multivariate-universe-selector`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(multivariate): add deterministic automatic universe selection`.

Required squash subject: `feat(multivariate): add deterministic automatic universe selection`.

Base: exact `main` after PR267+PR268 merge.

Merge method: squash only.

Priority: P0.

Depends on: PR264, PR267, PR268.

Scope: pure selector and decision evidence only. No risk-model fitting, portfolio solvers, orchestration, persistence/API, or Dash.

Owned paths: new selector modules and selector-only tests.

Tasks / Acceptance:
- [ ] Implement exact pinned-input hard eligibility and deterministic Univariate nondominated sorting with frozen objectives/tie rules; property tests prove order invariance and no unauthorized listing addition.
- [ ] Keep Pareto rank 1 and extend ranks only to minimum feasibility; when surviving universe is <=250 emit `bivariate_redundancy=not_applicable` with reason; boundary fixtures pass.
- [ ] For >250 listings perform deterministic Pearson hierarchical clustering to exactly 250 clusters and select one representative with frozen tie order; duplicate-ISIN/multi-exchange fixture retains full listing identity.
- [ ] Emit immutable DecisionArtifacts and `ResearchUniverseSnapshot` summaries for input eligibility, Univariate Pareto, Bivariate redundancy, before/after listing counts, removal reasons, and history-range/observation impact; byte-stability tests pass.
- [ ] Production selector never enumerates ISIN subsets and performs no manual per-ISIN UI selection after run start; architecture/performance tests enforce the bound.

Parallelization: Wave 3 Agent A, parallel with PR271. Selector-only files.

Security: pure authorized pinned input; can remove only.

Determinism: frozen ranking/clustering/ties and canonical snapshot serialization.

Idempotency: pure function returns byte-identical evidence for identical input.

Rollback: remove selector modules.

---

# PR271 — Risk-Model Registry, Production Solvers, And Configuration Identity

Branch: `feat/multivariate-production-solvers`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(multivariate): add risk-model configurations and production portfolio solvers`.

Required squash subject: `feat(multivariate): add risk-model configurations and production portfolio solvers`.

Base: same exact post-PR267/PR268 `main` as PR270.

Merge method: squash only.

Priority: P0.

Depends on: PR264, PR267, PR268.

Scope: pure risk-model/candidate construction only. No selector, winner ranking, orchestration, persistence/API, or Dash.

Owned paths:
- risk-model configuration adapters;
- solver/candidate modules;
- numerical tests.

Tasks / Acceptance:
- [ ] Support risk-model configurations `sample`, `ledoit_wolf`, and `ewma` with truthful common-calendar observation policy, aligned date range/count, diagnostics, and stable `risk_model_id`; tests reject mislabeled pairwise policy.
- [ ] Provide candidate methods exactly `equal_weight`, `minimum_variance`, `maximum_sharpe`, `maximum_diversification`, `equal_risk_contribution`, `hierarchical_risk_parity`, and `minimum_cvar`; Maximum Sharpe/Maximum Diversification are real solver-backed production methods, not high-dimensional grids.
- [ ] Give every method × risk-model × training-window/settings combination a stable `configuration_id`; same-method multiple-configuration fixtures remain distinct end-to-end.
- [ ] Enforce full `(isin, exchange, code)` weights and covariance keys in all production paths; duplicate-ISIN multi-exchange tests prove no weight collapse.
- [ ] Persistable diagnostics include aligned history range/count, covariance condition/stability, solver status, convergence, constraint residuals, turnover estimate, and typed unavailable reasons; deterministic numerical fixtures pass.
- [ ] Production code contains no exhaustive several-hundred-dimensional weight grid; 2-4 asset brute-force comparison is test-only reference evidence.

Parallelization: Wave 3 Agent B, parallel with PR270. Risk/solver-only files.

Security: pure numerical inputs.

Determinism: fixed solver tolerances, configuration IDs, canonical listing order.

Idempotency: pure calculations mutate nothing.

Rollback: remove new adapters/solvers and retain old research code as non-production reference if needed.

---

# PR272 — Durable Multivariate Orchestration, Walk-Forward, Objective Winner, And Final Refit

Branch: `feat/multivariate-auto-orchestrator`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(multivariate): orchestrate durable OOS portfolio selection`.

Required squash subject: `feat(multivariate): orchestrate durable OOS portfolio selection`.

Base: exact `main` after PR270+PR271 merge.

Merge method: squash only.

Priority: P0.

Depends on: PR264, PR269-PR271.

Scope: execution/ranking only. No Dash page and no read-section API implementation.

Owned paths: Multivariate orchestrator, walk-forward policy/ranking/final-refit modules, orchestration tests.

Tasks / Acceptance:
- [ ] One durable Multivariate run executes selector -> risk-model configurations -> portfolio candidates -> training-fold-only refits -> OOS validation -> objective ranking -> final refit with PR269 attempts/progress/restart semantics; restart integration test passes.
- [ ] Fix walk-forward `maximum_refit_count=1` division-by-zero edge, annualize OOS volatility consistently, and preserve no-lookahead by fitting selector/risk model/expected return/solver parameters inside each training fold only; policy/units/no-lookahead tests pass.
- [ ] Match evaluated candidates by stable `configuration_id`, never by method string; same-method multi-configuration fixture proves no overwrite.
- [ ] Implement exact OOS winner rules for `return_risk`, `return_drawdown`, and `minimum_risk`, including typed unavailable zero-drawdown Calmar and frozen tie order; objective fixtures produce deterministic winner IDs.
- [ ] Emit all eight DecisionArtifact stages, walk-forward train/test ranges, final winner, final portfolio, final-refit common history, and stage `ResearchUniverseSnapshot` evidence; byte-stability tests pass.
- [ ] Raw exceptions never become public failure reasons and stale attempts cannot publish winner/DecisionArtifacts after lease loss; failure/redaction race tests pass.

Parallelization: Wave 4 Agent A, parallel with PR273. Orchestration/ranking files only.

Security: project/run authorization resolved before data; public failures redacted.

Determinism: objective + configuration registry + split policy + tie rules determine one winner.

Idempotency: same input/settings/objective -> one logical run/winner/artifact set.

Rollback: restore previous Multivariate orchestration while keeping immutable completed artifacts.

---

# PR273 — Decision/Universe-History Persistence, Lazy Read API, And Project Isolation

Branch: `feat/multivariate-decision-sections`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(multivariate): persist and expose decision and history evidence`.

Required squash subject: `feat(multivariate): persist and expose decision and history evidence`.

Base: same exact post-PR270/PR271 `main` as PR272.

Merge method: squash only.

Priority: P0.

Depends on: PR264, PR269-PR271.

Scope: persistence/read API only, implemented against PR264 fixtures and frozen artifact contracts. No solver/orchestration/Dash calculations.

Owned paths: Multivariate DecisionArtifact/snapshot repositories, lazy read API/service adapters, API tests.

Tasks / Acceptance:
- [ ] Persist immutable DecisionArtifacts, configuration evidence, walk-forward ranges, winner/final portfolio, and all `ResearchUniverseSnapshot` rows under project + run + revision authority with canonical bytes; duplicate identical writes are no-op and conflicting bytes fail closed.
- [ ] Expose compact page view plus lazy sections for Universe, Risk Model, Optimization, Validation, Final Portfolio, and Universe/History pipeline using typed section availability; GET/read paths perform zero financial calculation and zero state mutation.
- [ ] Enforce project/run authorization before every section/snapshot lookup and project-scoped current selection throughout; two-project tests prove no cross-project IDs, counts, histories, weights, or artifacts leak.
- [ ] Expose only safe public failure codes/reasons and typed unavailable/not-applicable fields; API tests reject raw SQL/path/provider/exception text.
- [ ] Repository/service integration tests prove restart-safe reads and exact revision pinning while a newer same-project run is starting; old complete evidence remains explicitly previous/stale, never overwritten.

Parallelization: Wave 4 Agent B, parallel with PR272. Persistence/API-only paths.

Security: project + run authorization first.

Determinism: canonical artifact/snapshot bytes and immutable revisions.

Idempotency: reads non-mutating; identical writes converge.

Rollback: remove new read surfaces without deleting completed artifacts.

---

# PR274 — Multivariate Dash Page Shell, Objective/Run Control, Global Candidate Plot, And Tab Registry

Branch: `feat/dash-multivariate-shell`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(dash): add Multivariate optimizer shell and candidate overview`.

Required squash subject: `feat(dash): add Multivariate optimizer shell and candidate overview`.

Base: exact `main` after PR272+PR273 merge.

Merge method: squash only.

Priority: P0.

Depends on: PR265, PR272, PR273.

Scope: Multivariate page shell only. Detailed tab figures are PR279/PR280.

Owned paths: Multivariate top-level page, objective selector, run-control callback/view-model, global candidate figure, frozen tab registry integration.

Tasks / Acceptance:
- [ ] Render exactly three objective choices with `return_risk` default, exact `Optimize portfolio` button, shared run control, stale/previous behavior, and no manual method/ISIN selection after start; callback tests prove one logical start.
- [ ] Render persistent Universe & History summary/pipeline and global `Portfolio Candidate OOS Return / Risk` from PR273 evidence only; figure passes `ProfessionalPlotContract` title/axis/legend/hover/revision/accessibility tests.
- [ ] Register exactly five Multivariate tabs `Universe|Risk Model|Optimization|Validation|Final Portfolio` through frozen extension slots so PR279 and PR280 can own disjoint modules without editing this page shell.
- [ ] Project switch clears old candidate/history evidence before replacement fetch; two-project UI test passes.
- [ ] Dash imports no formula/repository/provider/lake module and never reconstructs winner reasons from weights; architecture tests pass.

Parallelization: Wave 5 Agent A, parallel with PR281. Multi shell only.

Security: typed gateway only.

Determinism: project + run revision -> stable objective/status/figure.

Idempotency: reads/plots mutate nothing; duplicate start converges server-side.

Rollback: remove Multi shell while backend remains intact.

---

# PR281 — Production Python Runtime Preparation And Dependency-Aware Readiness

Branch: `refactor/python-app-runtime-prep`.

Git status: planned.

PR: not opened.

Suggested PR title: `refactor(runtime): prepare consolidated FastAPI and Dash app runtime`.

Required squash subject: `refactor(runtime): prepare consolidated FastAPI and Dash app runtime`.

Base: same exact post-PR272/PR273 `main` as PR274.

Merge method: squash only.

Priority: P0 cutover preparation.

Depends on: PR265, PR269, PR272, PR273.

Scope: prepare final Python app/runtime while React remains production UI. Do not delete `apps/web/**`, do not remove canonical old routes yet, and do not activate final cutover.

Owned paths: Python app mounting/runtime, app Dockerfile, readiness/liveness wiring, coexistence compose additions/overrides, runtime tests.

Tasks / Acceptance:
- [ ] Build one Python application process capable of serving existing FastAPI `/api` plus mounted Dash route registry without giving `dash_ui` direct DB/provider authority; app Docker smoke test passes.
- [ ] Add dependency-aware liveness/readiness endpoints using PR269 readiness primitives; PostgreSQL-down test yields not-ready while liveness remains process-level.
- [ ] Prepare final three-service topology `postgres|app|project-bootstrap-worker` in a non-canonical/coexistence configuration without deleting current React/web services yet; compose validation passes.
- [ ] Prove restart does not duplicate research runs/snapshots and mounted Dash uses the same authorized gateway/API services; restart integration test passes.

Parallelization: Wave 5 Agent B, parallel with PR274. Runtime/Docker paths only; no Multivariate page files.

Security: app may hold server secrets, `dash_ui` dependency graph remains presentation-only.

Determinism: mount registry and service topology are frozen.

Idempotency: build/start/restart does not mutate analytical state.

Rollback: remove coexistence runtime prep; current production web remains available.

---

# PR279 — Multivariate Universe And Risk Model Decision-Audit Tabs

Branch: `feat/dash-multivariate-universe-risk`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(dash): add Multivariate universe and risk-model audit tabs`.

Required squash subject: `feat(dash): add Multivariate universe and risk-model audit tabs`.

Base: exact `main` after PR274+PR281 merge.

Merge method: squash only.

Priority: P1.

Depends on: PR274, PR273.

Scope: only `Universe` and `Risk Model` tab modules/figures/tables.

Owned paths: Multivariate Universe/Risk tab modules, their figure builders/CSS/tests. Optimization/Validation/Final files forbidden.

Tasks / Acceptance:
- [ ] Universe tab renders funnel, before/after Return/Risk evidence, removal reasons, redundancy/cluster evidence, listing/unique-ISIN counts, and history shrinkage for every selector stage from persisted DecisionArtifacts/snapshots; no local selection math.
- [ ] Risk Model tab renders model candidates, aligned history ranges/counts, condition/stability/parameter diagnostics, and selected/eligible/unavailable semantics; no pairwise-covariance surface is mislabeled as a coherent matrix.
- [ ] Every production figure/table passes shared ProfessionalPlotContract and deterministic hover/title/axis/legend/availability tests.
- [ ] Typed `not_applicable`/blocked/unavailable states render explicit reasons rather than zero/blank charts.

Parallelization: Wave 6 Agent A, parallel with PR280. Owns only Universe/Risk tab paths.

Security: authorized lazy sections only.

Determinism: persisted artifact revision determines stable figure bytes/trace order.

Idempotency: interactions/read filters mutate no research state.

Rollback: remove these two tab modules.

---

# PR280 — Multivariate Optimization, Validation, And Final Portfolio Decision-Audit Tabs

Branch: `feat/dash-multivariate-validation-final`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(dash): add Multivariate optimization, validation, and final portfolio audit`.

Required squash subject: `feat(dash): add Multivariate optimization, validation, and final portfolio audit`.

Base: same exact post-PR274/PR281 `main` as PR279.

Merge method: squash only.

Priority: P1.

Depends on: PR274, PR273.

Scope: only `Optimization`, `Validation`, and `Final Portfolio` tab modules/figures/tables.

Owned paths: those three tab modules, their figure builders/CSS/tests. Universe/Risk files forbidden.

Tasks / Acceptance:
- [ ] Optimization tab renders solver/risk-model configuration trade-offs with full configuration identity, objective metrics, eligibility, and winner evidence; same-method configurations remain visually distinct.
- [ ] Validation tab renders OOS cumulative performance, OOS Return/Risk, Weight Stability, and `Walk-Forward Training / Test Coverage` with exact train/test ranges and observation counts from persisted evidence; no-lookahead evidence is visible.
- [ ] Final Portfolio tab renders final capital weights, risk contributions, income contributions, holding count, final-refit common range/count, and explicit unavailable income reasons; full listing identity appears in labels/hover.
- [ ] All figures/tables pass ProfessionalPlotContract, typed-unavailable, stable-trace, responsive, and accessibility tests; no financial formula runs in Dash.

Parallelization: Wave 6 Agent B, parallel with PR279. Owns only Optimization/Validation/Final paths.

Security: authorized lazy sections only.

Determinism: final persisted revision determines all views.

Idempotency: read/hover/tab changes mutate nothing.

Rollback: remove these three tab modules.

---

# PR277 — Univariate Dash Page, Professional Return/Risk, And Listing History

Branch: `feat/dash-univariate-research`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(dash): add Univariate research and history page`.

Required squash subject: `feat(dash): add Univariate research and history page`.

Base: exact `main` after PR279+PR280 merge.

Merge method: squash only.

Priority: P1.

Depends on: PR265, PR267.

Scope: Univariate presentation only.

Owned paths: Univariate Dash page/callback/view-model/figures/CSS/UI tests.

Tasks / Acceptance:
- [ ] Render exact `Compute univariate statistics` run control and restore idle/running/complete/failed/stale states from backend without inventing progress; duplicate-click UI test starts at most one logical run.
- [ ] Render professional `Univariate Return / Risk Universe` with required axes, semantic Selected/Rejected/Data-quality/Pareto legend, complete friendly hover, and no raw metric keys.
- [ ] Render `Universe & History`, pipeline, per-listing min/median/max, and `Univariate Listing History Coverage` from PR267 snapshots; history envelope and common usable history remain distinct.
- [ ] Preserve existing Univariate tabs/ranges/distribution-frequency controls using server result values only; no formula imports.
- [ ] Two-project/reload/responsive/accessibility/ProfessionalPlotContract tests pass.

Parallelization: Wave 7 Agent A, parallel with PR278. Uni Dash paths only.

Security: authorized gateway only.

Determinism: result revision + saved view settings -> stable plots.

Idempotency: reads/interactions mutate no research state.

Rollback: remove Uni Dash page.

---

# PR278 — Bivariate Dash Page, Professional Diversification, Matrices, Tail Views, And Pair History

Branch: `feat/dash-bivariate-research`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(dash): add Bivariate diversification and pair-history page`.

Required squash subject: `feat(dash): add Bivariate diversification and pair-history page`.

Base: same exact post-PR279/PR280 `main` as PR277.

Merge method: squash only.

Priority: P1.

Depends on: PR265, PR268.

Scope: Bivariate presentation only.

Owned paths: Bivariate Dash page/callback/view-model/figures/CSS/UI tests.

Tasks / Acceptance:
- [ ] Render exact `Compute bivariate statistics` run control and restore durable status/progress without inventing percent; duplicate-click UI test starts at most one logical run.
- [ ] Render professional `Bivariate Return / Diversification Universe` with dynamic named median-dependence X axis, annualized-return Y axis, semantic legend, usable-pair count and complete friendly hover.
- [ ] Render required matrix/heatmap/tail/rolling views with descriptive titles, listing labels, named colorbars, pair identities, shared-observation hover, stable order, and explicit pairwise-covariance-surface semantics.
- [ ] Render `Universe & History`, pipeline, exact eligible pair count, pairwise min/median/max history, and `Pairwise Shared-History Distribution`; envelope/common-history meanings remain distinct.
- [ ] Deterministic 201-listing fixture, two-project/reload/responsive/accessibility, and ProfessionalPlotContract tests pass without browser-side financial calculations.

Parallelization: Wave 7 Agent B, parallel with PR277. Bi Dash paths only.

Security: authorized gateway/sections only.

Determinism: pair revision + metric/view settings -> stable plots.

Idempotency: reads/plot switches mutate nothing.

Rollback: remove Bi Dash page.

---

# PR266 — Metadata Builder Dash And Initial Universe/History Evidence

Branch: `feat/dash-metadata-builder`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(dash): add Metadata Builder and initial universe evidence`.

Required squash subject: `feat(dash): add Metadata Builder and initial universe evidence`.

Base: exact `main` after PR277+PR278 merge.

Merge method: squash only.

Priority: P1.

Depends on: PR265.

Scope: Metadata page only; delayed in the two-agent schedule because it is not on the analytical backend critical path.

Owned paths: Metadata Dash page/callback/view-model/CSS/UI tests/docs.

Tasks / Acceptance:
- [ ] Render combined metadata download/builder with exactly Exchange, Instrument type, Country, Currency, and `Name contains`, deterministic option counts/order, project creation, initial-fill progress/retry/restore, and no provider key in browser.
- [ ] Render initial full-listing count, unique-ISIN count, observed history envelope when server evidence exists, and fixed pipeline with downstream stages typed not-run/blocked; no guessed common history.
- [ ] Project create/select/reload behavior is idempotent and cannot paint old-project criteria/counts; two-project test passes.
- [ ] Responsive/accessibility/focused Ruff/Pyright/Dash tests pass.

Parallelization: Wave 8 Agent A, parallel with PR276. Metadata-only paths.

Security: provider credentials remain server-side.

Determinism: metadata revision + exact criteria -> stable view.

Idempotency: duplicate callbacks do not duplicate project/metadata commands.

Rollback: remove Metadata Dash page.

---

# PR276 — Sunday Full Research Refresh Independent Of UI Cutover

Branch: `feat/weekly-full-research-refresh`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(cron): refresh market data and all portfolio statistics weekly`.

Required squash subject: `feat(cron): refresh market data and all portfolio statistics weekly`.

Base: same exact post-PR277/PR278 `main` as PR266 in the two-agent schedule; logical dependencies are only the final backend contracts listed below.

Merge method: squash only.

Priority: P0 scheduled research freshness.

Depends on: PR267, PR268, PR269, PR272, PR273. **Does not depend on PR275 or React deletion.**

Scope: scheduler/orchestrator only; no Dash page/figure changes.

Owned paths: `src/portfell/shared_market_cron.py`, new `src/portfell/weekly_research_refresh.py`, one CLI entrypoint if needed, scheduler/orchestrator tests, scheduled-job operations docs.

Tasks / Acceptance:
- [ ] Install exactly one managed schedule `CRON_TZ=Europe/Vienna` and `0 9 * * 0` using `/usr/bin/flock -n`, preserving unrelated crontab bytes; tests reject Amsterdam/daily/duplicate scheduler configurations.
- [ ] Refresh canonical quotes/dividends/splits exactly once for the de-duplicated active-project union, pin the published market revision, and never fetch provider data once per project.
- [ ] For each active project in stable project-ID order start/reuse durable Uni -> Bi -> Multi using persisted project-scoped selection/settings/objective/constraints and default only absent objective to `return_risk`; no browser required.
- [ ] Reuse the same `ResearchUniverseSnapshot`, DecisionArtifact, progress/status, logical-run, and error contracts as manual runs; no cron-only calculations or duplicate snapshots/winners/artifacts.
- [ ] Enforce exact failure isolation: market failure blocks all; project Uni failure blocks that project's Bi/Multi; Bi failure blocks only that project's Multi; Multi failure does not stop other projects; downstream states are `blocked_upstream` not successful zero data.
- [ ] Two-project deterministic fixture proves one provider refresh, A->B/B->A order invariance, default and non-default objectives, independent current selections, interruption/resume, lock contention, byte-stable cycle summary, and redacted logs.

Parallelization: Wave 8 Agent B, parallel with PR266. Scheduler/orchestrator paths only.

Security: trusted worker holds provider credential; host cron/browser never receives it.

Determinism: pinned market revision + project IDs/settings/objective + algorithm versions define the cycle.

Idempotency: lock + logical identities converge resumed/repeated cycles.

Rollback: revert to prior market-only cron; published analytical artifacts remain immutable.

---

# PR275 — Final React Deletion And Canonical Dash/FastAPI/Compose Cutover

Branch: `refactor/dash-production-cutover`.

Git status: planned final serial PR.

PR: not opened.

Suggested PR title: `refactor(ui): replace React with Dash and finalize Python runtime`.

Required squash subject: `refactor(ui): replace React with Dash and finalize Python runtime`.

Base: exact `main` after PR266+PR276 and all prior waves are merged green.

Merge method: squash only.

Priority: P0 mandatory final cutover.

Depends on: PR265-PR281 all owning relevant final behavior; specifically PR266, PR277, PR278, PR274, PR279, PR280, PR281, PR276 and all backend PRs.

Scope: deletion/switch/integration only. No new financial logic, no new plot formulas, no new research contracts.

Owned paths: `apps/web/**` deletion, final compose files, canonical route/base-prefix switch, obsolete Node/Dash-sidecar cleanup, production E2E/cutover docs.

Tasks / Acceptance:
- [ ] Delete React/TypeScript/Vite production UI and production Node web service, remove temporary separate Dash service, remove `/dash` prefix, and expose exactly `/projects/<slug>/metadata-builder|univariate-statistics|bivariate-statistics|multivariate-statistics`; route E2E passes.
- [ ] Make final long-running Compose services exactly `postgres`, `app`, `project-bootstrap-worker`; `app` serves FastAPI `/api` plus mounted Dash and dependency-aware readiness; compose/runtime smoke tests pass.
- [ ] Run one production-like two-project journey covering Metadata -> Uni -> Bi -> Multi, project switching, restart, objective selection, professional plots, Universe/History pipeline, final portfolio, and no cross-project flash/leak; E2E passes from one SHA.
- [ ] Prove all production figures retain titles/axes/semantic legends/hover/accessibility, unavailable remains typed, duplicate-ISIN listings stay distinct, same-method configurations stay distinct, and walk-forward/history evidence survives cutover; registry/E2E tests pass.
- [ ] Prove weekly orchestrator still runs in `project-bootstrap-worker` with no fourth long-running service and no browser dependency; worker smoke test passes.
- [ ] Ruff, Pyright, unit, integration, PostgreSQL, architecture, Docker/Compose, E2E, coverage/quality gates pass from the exact merge SHA.

Parallelization: final serial integration PR; no other implementation PR may run concurrently against moving cutover-owned root/runtime files.

Security: final browser has no provider/database credentials; app is trusted server boundary.

Determinism: final route registry, three-service topology, and merged immutable contracts define production shape.

Idempotency: build/start/restart/cutover smoke creates no duplicate research state.

Rollback: return to pre-PR275 coexistence SHA; no analytical schema/data rollback required.

## Final release gate

The stack is complete only when one `main` SHA proves all of the following:

- four and only four user workflow pages exist;
- Multivariate Statistics is the only optimizer page/run/stage;
- every statistics run is durable, restart-safe, project-scoped, idempotent, and read-status is non-mutating;
- typed unavailable semantics, full listing identity, stable configuration identity, exact Bivariate pairs, atomic result publication, safe errors, truthful risk-model calendar semantics, and dependency-aware readiness pass;
- Universe & History evidence is visible and revision-pinned from Metadata through Final portfolio, with envelope/common-history distinctions and exact observation counts;
- all required professional plots satisfy the shared contract;
- no high-dimensional brute-force production path exists;
- OOS walk-forward and objective winner selection are no-lookahead and deterministic;
- Sunday 09:00 Europe/Vienna runs one market refresh then Uni -> Bi -> Multi for every active project using the same backend evidence contracts;
- final runtime is exactly `postgres`, `app`, `project-bootstrap-worker` and React/Node production UI is absent;
- repository quality gates pass from one SHA.
