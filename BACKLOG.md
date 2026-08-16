Last reviewed: 2026-08-16

## Table Of Contents

- [Backlog Policy](#backlog-policy)
- [Weak-Agent Execution Rules](#weak-agent-execution-rules)
- [Product Invariant](#product-invariant)
- [Execution Graph](#execution-graph)
- [PR264-PR275](#pr264-pr275)
- [Series Completion Gate](#series-completion-gate)
- [Historical Backlog Archive](#historical-backlog-archive)

## Backlog Policy

This file contains only active planned work for the Plotly Dash replacement UI and Multivariate Statistics portfolio optimizer. Planned work unrelated to Plotly/Dash, Multivariate optimization, optimizer explainability, required Uni/Bivariate visualizations, React removal, or final Docker/runtime cutover is intentionally absent from active planning.

Completed, superseded, pushed, and historical records from before this refocus are preserved verbatim in `docs/backlog/archive/BACKLOG-2026-08-16-before-dash-optimizer.md`; they are not active authority. The superseded three-page-only Dash plan is preserved in `docs/backlog/archive/plotly-dash-three-page-research-ui-v1.md`.

Every active PR contains `Branch`, `Git status`, `PR`, `Priority`, `Depends on`, `Base`, `Merge method`, `Scope`, `Tasks / Acceptance`, `Parallelization`, `Security`, `Determinism`, `Idempotency`, and `Rollback`. The detailed executable work orders are in `docs/backlog/plotly-dash-multivariate-optimizer-ui.md`.

There is exactly one checklist per PR named `Tasks / Acceptance`. There is no second acceptance list. A checkbox may be completed only when implementation and the exact evidence named by that checkbox both exist.

## Weak-Agent Execution Rules

Assume two agents with weak reasoning, incomplete context, and no permission to infer missing architecture:

- parallel PRs branch from the exact same predecessor `main` merge commit and never from each other;
- shared contracts, IDs, reason codes, objective IDs, route suffixes, status values, tie-breaks, and fixture names are frozen in predecessor PRs;
- every PR owns explicit paths and forbids overlapping ownership unless a one-time hand-off is written first;
- UI never recomputes portfolio statistics or invents optimizer explanations; it renders server-produced/persisted evidence;
- production optimization never enumerates all ISIN subsets or a several-hundred-dimensional weight grid;
- every important Multivariate decision is incomplete until its persisted evidence has a visible Decision Audit representation;
- historical archive wording never overrides this active file or the normative specification.

## Product Invariant

The workflow is exactly:

```text
Metadata Builder
    -> Univariate Statistics
    -> Bivariate Statistics
    -> Multivariate Statistics
```

**Multivariate Statistics is the portfolio optimizer.** There is no separate Optimizer page, route, workflow stage, run-status surface, or post-Multivariate step. Internal selector/solver/walk-forward/decision modules are components of one Multivariate Statistics run.

All three statistics pages have one explicit calculation surface above results:

- Univariate: `Compute univariate statistics` + progress bar + phase/status + failure state.
- Bivariate: `Compute bivariate statistics` + progress bar + phase/status + failure state.
- Multivariate: required `Optimization objective` selector + `Optimize portfolio` + progress bar + phase/status + failure state.

Multivariate objective selector supports exactly `Return / Risk` (`return_risk`, default), `Return / Drawdown` (`return_drawdown`), and `Minimum Risk` (`minimum_risk`). Winner selection is objective-specific and based only on walk-forward out-of-sample evidence. The exact ranking/tie rules are frozen in the normative specification.

Univariate has one always-visible Return/Risk universe Plotly chart above tabs. Bivariate has one always-visible Return/Diversification universe Plotly chart above tabs. Multivariate has one always-visible portfolio-candidate chart above tabs and visual evidence for every important optimizer decision stage.

PR264-PR274 build Dash beside React only as temporary migration scaffolding. **PR275 is mandatory**: it deletes the current React/TypeScript production UI and reorganizes Docker so Dash is the only browser UI. Final Compose contains exactly `postgres`, `app`, and `project-bootstrap-worker`; one Python `app` process/container serves FastAPI REST plus mounted Dash.

## Execution Graph

```text
PR264 Dash/runtime/run-control foundation
  |
  +---------------------------+
  |                           |
  v                           v
PR265 shell/navigation     PR266 Metadata Builder
  |                           |
  +-------------+-------------+
                |
        both merged to main
                |
  +-------------+-------------+
  |                           |
  v                           v
PR267 Uni + plot + control PR268 Bi + plot + control
  |                           |
  +-------------+-------------+
                |
        both merged to main
                |
                v
PR269 Multivariate objective/run/decision contracts
                |
  +-------------+-------------+
  |                           |
  v                           v
PR270 automatic universe   PR271 solver-backed candidates
selector                      |
  |                           |
  +-------------+-------------+
                |
        both merged to main
                |
  +-------------+-------------+
  |                           |
  v                           v
PR272 Multivariate run     PR273 Multivariate decision
orchestration + OOS winner persistence/API
  |                           |
  +-------------+-------------+
                |
        both merged to main
                |
                v
PR274 Multivariate Dash optimizer + Decision Audit
                |
                v
PR275 React deletion + production Dash/FastAPI/Docker cutover
```

## PR264-PR275

### PR264. Plotly Dash Runtime, Shared Run-Control, And Four-Page Foundation

Branch: `feat/dash-runtime-foundation`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(dash): add four-page runtime and run-control foundation`.

Required squash subject: `feat(dash): add four-page runtime and run-control foundation`.

Base: `main`.

Merge method: squash only.

Priority: P0.

Depends on: already-merged hosted page-view, lazy-section, workflow, run, and command contracts.

Scope: temporary Dash/FastAPI sidecar under `/dash/`, exactly four workflow suffixes, shared `StatisticsRunControl`, typed gateway, Plotly presentation contracts, deterministic fixtures, temporary Dash Docker/profile, and architecture boundaries. The final production topology is explicitly deferred only to mandatory PR275.

Tasks / Acceptance: single authoritative `PR264` checklist in `docs/backlog/plotly-dash-multivariate-optimizer-ui.md`.

Parallelization: Agent B freezes contracts/IDs/run-control/fixtures first; Agent A owns runtime/dependency/container wiring and may import but not edit frozen files.

Security: temporary Dash container gets no database/provider/shared-data authority.

Determinism: frozen IDs/routes/run-control/contracts determine runtime shape.

Idempotency: startup/health/reads mutate nothing.

Rollback: remove temporary Dash additions; no persistent migration.

### PR265. Dash Shell And Four-Stage Project Navigation

Branch: `feat/dash-research-shell`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(dash): add four-stage research shell`.

Required squash subject: `feat(dash): add four-stage research shell`.

Base: exact PR264 merge commit.

Merge method: squash only.

Priority: P1.

Depends on: PR264.

Scope: Portfell shell, project selector, process overview, responsive sidebar, exactly four workflow links, temporary `/dash/projects/<slug>/...` navigation, and two-project isolation. No separate Optimizer link/state is allowed.

Tasks / Acceptance: single authoritative `PR265` checklist in normative specification.

Parallelization: wave 1 Agent A; concurrent with PR266; owns shell/navigation only.

Security: route/project state never authorizes data.

Determinism: project workflow projection determines shell.

Idempotency: same-project selection emits no command.

Rollback: revert shell/navigation only.

### PR266. Dash Metadata Builder

Branch: `feat/dash-metadata-builder`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(dash): add Metadata Builder page`.

Required squash subject: `feat(dash): add Metadata Builder page`.

Base: same exact PR264 merge commit as PR265.

Merge method: squash only.

Priority: P1.

Depends on: PR264.

Scope: combined metadata download/builder, five criteria, create-project, initial-fill progress/retry/restore, responsive behavior, no provider credential in browser.

Tasks / Acceptance: single authoritative `PR266` checklist.

Parallelization: wave 1 Agent B; concurrent with PR265; Metadata-only paths.

Security: server remains provider-credential boundary.

Determinism: same page-view/options produce same UI.

Idempotency: duplicate callbacks cannot create duplicate logical commands.

Rollback: revert Metadata Dash files.

### PR267. Dash Univariate Statistics, Calculation Control, And Global Return-Risk Plot

Branch: `feat/dash-univariate-universe`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(dash): add Univariate calculation and return-risk universe`.

Required squash subject: `feat(dash): add Univariate calculation and return-risk universe`.

Base: exact `main` after PR265+PR266.

Merge method: squash only.

Priority: P0.

Depends on: PR264-PR266.

Scope: exact `Compute univariate statistics` control with progress/status/failure/reload semantics; existing Uni tabs/selection; always-visible Return/Volatility universe scatter and Pareto frontier above tabs.

Tasks / Acceptance: single authoritative `PR267` checklist.

Parallelization: wave 2 Agent A; concurrent with PR268; Univariate-only paths.

Security: only authorized project result/run payloads.

Determinism: stable run adapter/listing sort/frontier rule.

Idempotency: duplicate start converges on one run; plots are read-only.

Rollback: revert Univariate Dash files.

### PR268. Dash Bivariate Statistics, Calculation Control, And Global Return-Diversification Plot

Branch: `feat/dash-bivariate-universe`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(dash): add Bivariate calculation and diversification universe`.

Required squash subject: `feat(dash): add Bivariate calculation and diversification universe`.

Base: same exact post-PR265/PR266 `main` as PR267.

Merge method: squash only.

Priority: P0.

Depends on: PR264-PR266.

Scope: exact `Compute bivariate statistics` control with progress/status/failure/reload semantics; nine Bivariate views; Plotly matrices/WebGL tail scatter; always-visible Return/median-dependence universe plot above tabs with six-metric selector.

Tasks / Acceptance: single authoritative `PR268` checklist.

Parallelization: wave 2 Agent B; concurrent with PR267; Bivariate-only paths.

Security: section IDs never authorize access.

Determinism: pair revision/median rule/stable order.

Idempotency: duplicate start converges on one run; plot switches are read-only.

Rollback: revert Bivariate Dash files.

### PR269. Multivariate Statistics Decision, Objective, And Run Contract Foundation

Branch: `feat/multivariate-optimizer-contracts`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(multivariate): define optimizer objective and decision contracts`.

Required squash subject: `feat(multivariate): define optimizer objective and decision contracts`.

Base: exact `main` after PR267+PR268.

Merge method: squash only.

Priority: P0.

Depends on: PR267, PR268, existing Multivariate/risk-model/scorecard contracts.

Scope: freeze three optimization objectives, objective-specific OOS ranking, one Multivariate run identity/progress phase model, immutable DecisionArtifact contracts, reason codes, sink, fixtures. This is one Multivariate Statistics lifecycle, not a separate Optimizer lifecycle.

Tasks / Acceptance: single authoritative `PR269` checklist.

Parallelization: contracts/objectives first by Agent A; fixtures/property/progress tests by Agent B; next wave waits for merge.

Security: decision artifacts contain analytical evidence only.

Determinism: objective registry + canonical serialization determine IDs.

Idempotency: identical run/decision inputs converge; conflict fails closed.

Rollback: remove new Multivariate optimizer contracts.

### PR270. Multivariate Automatic Universe Selector From Uni/Bivariate Evidence

Branch: `feat/multivariate-universe-selector`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(multivariate): add automatic optimizer universe selection`.

Required squash subject: `feat(multivariate): add automatic optimizer universe selection`.

Base: exact PR269 merge commit.

Merge method: squash only.

Priority: P0.

Depends on: PR269.

Scope: automatic eligibility, Univariate Pareto selection, deterministic Bivariate redundancy reduction only when needed to fit bounded risk model, <=250 output, full decision evidence, no manual ISIN picking.

Tasks / Acceptance: single authoritative `PR270` checklist.

Parallelization: wave 3 Agent A; concurrent with PR271; selector-only paths.

Security: selector may only remove from authorized pinned input.

Determinism: frozen ranking/clustering/tie rules.

Idempotency: pure selection repeats exactly.

Rollback: remove selector; upstream unchanged.

### PR271. Multivariate Solver-Backed Portfolio Candidate Set

Branch: `feat/multivariate-production-solvers`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(multivariate): add solver-backed portfolio candidates`.

Required squash subject: `feat(multivariate): add solver-backed portfolio candidates`.

Base: same exact PR269 merge commit as PR270.

Merge method: squash only.

Priority: P0.

Depends on: PR269.

Scope: solver-backed Maximum Sharpe/Maximum Diversification plus existing Min Variance/ERC/HRP/Min CVaR/Equal Weight baseline, Sample/Ledoit-Wolf/EWMA risk configurations, deterministic diagnostics, no exhaustive production subset/weight-grid enumeration.

Tasks / Acceptance: single authoritative `PR271` checklist.

Parallelization: wave 3 Agent B; concurrent with PR270; solver/candidate-only paths.

Security: pure numerical inputs only.

Determinism: fixed solver settings and stable identities.

Idempotency: pure calculations mutate nothing.

Rollback: remove new solver adapters.

### PR272. Multivariate Statistics Run Orchestration And OOS Objective Winner

Branch: `feat/multivariate-auto-orchestrator`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(multivariate): optimize portfolio by selected OOS objective`.

Required squash subject: `feat(multivariate): optimize portfolio by selected OOS objective`.

Base: exact `main` after PR270+PR271.

Merge method: squash only.

Priority: P0.

Depends on: PR269-PR271 plus walk-forward/scorecard infrastructure.

Scope: the one Multivariate Statistics run performs universe selection, risk models, candidate construction, walk-forward validation, objective-specific OOS winner selection, final refit, progress publication, and final decision artifacts. No separate optimizer run type is browser-visible.

Tasks / Acceptance: single authoritative `PR272` checklist.

Parallelization: wave 4 Agent A; concurrent with PR273; orchestration/ranking/progress only.

Security: authorize project/run before resolving data.

Determinism: objective + bounded model registry + split/ranking policy determine winner.

Idempotency: same input/objective/settings -> one Multivariate run/winner.

Rollback: restore previous Multivariate orchestration.

### PR273. Multivariate Decision Artifact Persistence And Lazy Read Sections

Branch: `feat/multivariate-decision-sections`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(multivariate): persist and expose optimizer decision sections`.

Required squash subject: `feat(multivariate): persist and expose optimizer decision sections`.

Base: same exact post-PR270/PR271 `main` as PR272.

Merge method: squash only.

Priority: P0.

Depends on: PR269-PR271.

Scope: persist decisions under Multivariate run authority, expose compact page-view progress/objective/winner state and lazy decision sections, no financial calculation in GET paths, two-project isolation.

Tasks / Acceptance: single authoritative `PR273` checklist.

Parallelization: wave 4 Agent B; concurrent with PR272; persistence/read/API only.

Security: project + Multivariate run authorization precedes artifact access.

Determinism: canonical bytes/revisions.

Idempotency: repeated identical writes no-op; reads non-mutating.

Rollback: remove persistence/read surfaces only.

### PR274. Dash Multivariate Statistics Optimizer, Calculation Control, Objective Selector, And Decision Audit

Branch: `feat/dash-multivariate-optimizer`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(dash): make Multivariate Statistics the portfolio optimizer`.

Required squash subject: `feat(dash): make Multivariate Statistics the portfolio optimizer`.

Base: exact `main` after PR272+PR273.

Merge method: squash only.

Priority: P0.

Depends on: PR264-PR273.

Scope: fourth Dash page; exact three-choice optimization-objective selector; exact `Optimize portfolio` button; progress/status/failure/reload semantics; always-visible candidate plot; tabs `Universe`, `Risk Model`, `Optimization`, `Validation`, `Final Portfolio`; visual audit of every important decision stage; deterministic 400-listing/three-objective journey.

Tasks / Acceptance: single authoritative `PR274` checklist.

Parallelization: Agent A page/objective layout/figures/CSS; Agent B callbacks/view-model/sections/run-control/E2E/docs; frozen PR269/PR273 contracts cannot change.

Security: browser consumes authorized Multivariate sections only.

Determinism: objective/run revision -> stable plots/winner.

Idempotency: identical start -> one Multivariate run; charts read-only.

Rollback: revert Multivariate Dash layer.

### PR275. Production Dash Cutover, React UI Deletion, And Docker Consolidation

Branch: `refactor/dash-production-cutover`.

Git status: planned.

PR: not opened.

Suggested PR title: `refactor(ui): replace React with Dash and consolidate runtime`.

Required squash subject: `refactor(ui): replace React with Dash and consolidate runtime`.

Base: exact PR274 merge commit.

Merge method: squash only.

Priority: P0 mandatory final cutover.

Depends on: PR264-PR274 all merged/green.

Scope: delete `apps/web/**` and React/TypeScript/Vite production UI; remove temporary Dash sidecar topology; mount Dash in production FastAPI ASGI app; canonicalize browser paths without `/dash`; reorganize Compose to exactly `postgres`, `app`, `project-bootstrap-worker`; replace old API/Web/Dash images with one Python app image plus worker command; migrate tests/docs/gates and prove rollback.

Tasks / Acceptance: single authoritative `PR275` checklist, including exact cutover manifest and strict two-agent path ownership.

Parallelization: Agent B first freezes cutover manifest. Agent A owns old UI deletion/test/doc migration; Agent B owns Python runtime/Docker/Compose/health/ports/operations. Shared root files are individually assigned in manifest before edits.

Security: final shared `app` container holds API secrets as required, but architecture/injection tests prove `dash_ui` itself cannot import/receive database/provider/storage adapters.

Determinism: cutover manifest + three-service topology + route registry determine final runtime.

Idempotency: build/start/restart/cutover smoke does not duplicate analytical state.

Rollback: return to PR274 coexistence SHA; no schema/data migration is introduced by cutover.

## Series Completion Gate

The series is complete only when all PR264-PR275 acceptance checklists pass and one clean final `main` SHA proves:

- exactly four workflow pages exist and Multivariate Statistics is consistently the only portfolio optimizer page/run;
- Uni, Bi, Multivariate each expose their exact calculation button, progress bar, phase/status, failure/reload behavior, duplicate-start protection, and project isolation;
- Multivariate objective selector exposes exactly `return_risk`, `return_drawdown`, `minimum_risk`, and objective-specific winner ranking is OOS-only;
- Univariate/Bivariate global plots and every Multivariate decision visualization are present and use server/persisted evidence only;
- no manual per-ISIN or optimizer-method choice is required after a Multivariate run starts;
- no exhaustive several-hundred-ISIN subset permutation or high-dimensional weight-grid production path exists;
- React/TypeScript production UI is deleted and no production Node UI container remains;
- final Compose services are exactly `postgres`, `app`, `project-bootstrap-worker`;
- one Python `app` serves existing `/api` REST plus canonical Dash `/projects/<slug>/...` browser routes;
- all Python/Dash/API/contract/architecture/Docker/Compose/E2E/quality gates pass from one SHA.

## Historical Backlog Archive

`docs/backlog/archive/BACKLOG-2026-08-16-before-dash-optimizer.md` and `docs/backlog/archive/plotly-dash-three-page-research-ui-v1.md` are historical evidence only. They may contain superseded React, three-page Dash, or separate-optimizer wording and must not be used as active implementation instructions.