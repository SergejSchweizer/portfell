Last reviewed: 2026-08-16

## Table Of Contents

- [Backlog Policy](#backlog-policy)
- [Weak-Agent Execution Rules](#weak-agent-execution-rules)
- [Product And UI Invariants](#product-and-ui-invariants)
- [Scheduled Research Invariant](#scheduled-research-invariant)
- [PR458 Correctness Backlog Gate](#pr458-correctness-backlog-gate)
- [Execution Graph](#execution-graph)
- [PR264-PR276](#pr264-pr276)
- [Series Completion Gate](#series-completion-gate)
- [Historical Backlog Archive](#historical-backlog-archive)

## Backlog Policy

This file contains only active planned work for the Plotly Dash replacement UI, Multivariate Statistics portfolio optimizer, professional decision visualization, mandatory React/Docker cutover, scheduled full research refresh, and the correctness remediation required by the current-code review. Unrelated planned work is intentionally absent.

The detailed base work orders for PR264-PR275 are in `docs/backlog/plotly-dash-multivariate-optimizer-ui.md`. The active amendment `docs/backlog/plotly-dash-professional-plots-weekly-refresh.md` adds mandatory professional Plotly requirements to PR264/PR267/PR268/PR274/PR275 and defines PR276. The active correctness authorities `docs/backlog/current-code-correctness-amendment.md` and `docs/backlog/current-code-project-isolation-addendum.md` add mandatory current-code remediation to PR267-PR276. PR458 is the documentation/backlog gate that registers those findings before affected implementation PRs proceed. Where an active amendment is more specific or conflicts with older wording, the amendment wins. Historical files under `docs/backlog/archive/` are evidence only.

Every active PR must contain `Branch`, `Git status`, `PR`, `Suggested PR title`, `Required squash subject`, `Base`, `Merge method`, `Priority`, `Depends on`, `Scope`, `Tasks / Acceptance`, `Parallelization`, `Security`, `Determinism`, `Idempotency`, and `Rollback`. There is exactly one checklist per PR named `Tasks / Acceptance`; implementation and the evidence named in the same checkbox must both exist before it is checked.

## Weak-Agent Execution Rules

Assume two agents with weak reasoning, incomplete context, and no permission to infer missing architecture:

- parallel PRs branch from the exact same predecessor `main` merge commit and never from each other;
- shared contracts, component IDs, plot IDs, objective IDs, reason codes, route suffixes, progress states, tie-breaks, cron stage IDs, and fixture IDs are frozen in predecessor work before parallel branches start;
- each PR owns explicit files/modules; overlapping ownership is forbidden unless a one-time hand-off is written first;
- UI never recomputes portfolio statistics or invents optimizer explanations; it renders server-produced/persisted evidence;
- production optimization never enumerates all ISIN subsets or a several-hundred-dimensional exhaustive weight grid;
- every important Multivariate decision is incomplete until its persisted evidence has a visible Decision Audit representation;
- every production Plotly figure must use the frozen `ProfessionalPlotContract`; local page-specific alternatives are forbidden;
- scheduled work must call the same server/analytical contracts as explicit runs and must not create a browser-only or cron-only second implementation of Uni/Bi/Multivariate calculations.

## Product And UI Invariants

The workflow is exactly:

```text
Metadata Builder
    -> Univariate Statistics
    -> Bivariate Statistics
    -> Multivariate Statistics
```

**Multivariate Statistics is the portfolio optimizer.** There is no separate Optimizer page, route, workflow stage, status surface, scheduled stage, or post-Multivariate step. Internal selector/risk-model/solver/walk-forward/ranking/DecisionArtifact modules are components of one Multivariate Statistics run.

All three statistics pages contain one explicit calculation surface above analytical results:

- Univariate: `Compute univariate statistics` + progress bar + phase/status + failure state.
- Bivariate: `Compute bivariate statistics` + progress bar + phase/status + failure state.
- Multivariate: required `Optimization objective` selector + `Optimize portfolio` + progress bar + phase/status + failure state.

Multivariate objective selector supports exactly `Return / Risk` (`return_risk`, default), `Return / Drawdown` (`return_drawdown`), and `Minimum Risk` (`minimum_risk`). Winner selection is objective-specific and based only on walk-forward out-of-sample evidence.

Every production Plotly chart is professional and self-explanatory. It must have a descriptive title, explicit axis labels and units, semantic legend when visual encodings distinguish classes/traces, deterministic hover menus with friendly labels and stable identities, explicit unavailable/blocked/not-applicable states, stable trace names/order, responsive layout, and accessible text metadata. Raw field names such as `annualized_geometric_return` may be data keys but may not be shown as user-facing titles/axis/hover labels. The exact shared contract and page-specific required titles/labels/hover fields are frozen in `docs/backlog/plotly-dash-professional-plots-weekly-refresh.md`.

Required top-level charts remain:

- Univariate: `Univariate Return / Risk Universe`, X=`Annualized volatility (% p.a.)`, Y=`Annualized geometric return (% p.a.)`, with selection/data-quality classes and Pareto frontier.
- Bivariate: `Bivariate Return / Diversification Universe`, Y=`Annualized geometric return (% p.a.)`, dynamic named median-dependence X axis, semantic legend and complete listing hover.
- Multivariate: `Portfolio Candidate OOS Return / Risk`, X=`OOS annualized volatility (% p.a.)`, Y=`OOS annualized return (% p.a.)`, objective/candidate/winner evidence and professional plots for every decision stage.

PR264-PR274 build Dash beside React only as temporary migration scaffolding. **PR275 is mandatory**: delete the React/TypeScript/Vite production UI, remove Node web and temporary Dash containers, mount Dash into FastAPI, and make final Compose exactly `postgres`, `app`, `project-bootstrap-worker`.

## Scheduled Research Invariant

The managed production schedule is exactly:

```text
CRON_TZ=Europe/Vienna
0 9 * * 0
```

That means Sunday at 09:00 Vienna local time, including DST behavior from `Europe/Vienna`.

The weekly job is not market-data-only. One cycle must run without a browser and execute/reuse this dependency chain:

```text
shared market refresh once
(quotes + dividends + splits for de-duplicated active-project union)
        -> Univariate Statistics for every active project
        -> Bivariate Statistics for each successful Uni selection/revision
        -> Multivariate Statistics for each successful Bi revision
           using persisted Optimization objective/constraints
           default objective only when absent: return_risk
        -> terminal cycle summary
```

Market data is fetched once for the active union, never once per project. Within a project, Bivariate never starts before successful Univariate and Multivariate never starts before successful Bivariate. Project failures are isolated: a failed project does not stop other projects, while downstream stages of that project are explicitly `blocked_upstream`. A market-refresh failure blocks all project calculations for that cycle. Re-runs/resume must reuse unchanged logical runs and create no duplicate market business keys, Uni/Bi/Multivariate runs, winners, or DecisionArtifacts.

Current `main` already uses `0 9 * * 0` but with `Europe/Amsterdam` and invokes only `python -m portfell.shared_market_refresh`; PR276 changes the timezone to `Europe/Vienna` and replaces the market-only invocation with the complete scheduled research orchestrator.

## PR458 Correctness Backlog Gate

### PR458. Current-Code Correctness Hardening And Project Isolation

Branch: `docs/current-code-correctness-backlog-review`.

Git status: open documentation/backlog PR; no runtime code changes.

PR: GitHub PR #458, open.

Suggested PR title: `docs(backlog): harden current-code correctness and project isolation`.

Required squash subject: `docs(backlog): harden current-code correctness and project isolation`.

Base: `main` reviewed at `69d76a108257a9d07dd8e22a918ae789942afc07`.

Merge method: squash only.

Priority: P0 correctness planning gate.

Depends on: repository-wide static review of current `main`; no implementation PR dependency.

Scope: documentation/backlog-only registration of the current-code correctness review; make CCR-01 through CCR-13 mandatory remediation inside the already-planned PR267-PR276 stack; register project-scoped current-Univariate-selection authority; no runtime code, financial-formula, schema, Docker, provider, or production-behavior change in PR458 itself.

Tasks / Acceptance:

- [ ] `BACKLOG.md` registers PR458 explicitly as the P0 correctness planning gate and names `docs/backlog/current-code-correctness-amendment.md` plus `docs/backlog/current-code-project-isolation-addendum.md` as active normative authorities.
- [ ] CCR-01 through CCR-13 have one unambiguous owning implementation PR and deterministic acceptance evidence, covering durable worker ownership, immutable/reusable Bivariate revisions, read-only status projection, public error redaction, unavailable-vs-zero metric semantics, exact pair counts, pairwise-covariance semantics, full `ListingIdentity`, stable `configuration_id`, walk-forward policy/units, truthful risk-model observation policy, production readiness, and project-scoped current-selection isolation.
- [ ] The active base specification and weekly-refresh amendment reference the correctness authorities so weak agents cannot implement PR267-PR276 from an older incomplete contract.
- [ ] Two-project isolation is explicitly tested across selection changes, restarts, and weekly A->B versus B->A processing order; user-global current-Univariate-selection authority is forbidden in the final production design.
- [ ] PR458 remains documentation/backlog-only; runtime implementation belongs to the affected PR267-PR276 work orders and must not be silently pulled into this PR.

Parallelization: review findings may be independently verified, but edits to the active normative backlog/specification files have one sequential owner to avoid conflicting authority text.

Security: documents only; the review explicitly freezes safe public error-code requirements and forbids exposing raw exception/SQL/path/provider details in later runtime PRs.

Determinism: findings are pinned to the reviewed `main` SHA; each defect has fixed ownership and deterministic regression evidence.

Idempotency: merging PR458 changes planning authority only and creates no runtime state, jobs, selections, market rows, or analytical artifacts.

Rollback: revert the PR458 documentation changes; no runtime or persistent data rollback is required.

Implementation sequencing rule: PR458 must be merged before any not-yet-open affected PR267-PR276 branch is treated as implementation-authoritative. Those PRs must use the merged correctness amendments, not an older backlog snapshot.

## Execution Graph

```text
PR458 current-code correctness/backlog gate
                |
                v
PR264 Dash/runtime/run-control/professional-plot foundation
  |
  +---------------------------+
  |                           |
PR265 shell/navigation     PR266 Metadata Builder
  |                           |
  +-------------+-------------+
                |
        both merged to main
                |
  +-------------+-------------+
  |                           |
PR267 Uni + professional   PR268 Bi + professional
plot + run control         plots + run control
  |                           |
  +-------------+-------------+
                |
        both merged to main
                |
PR269 Multivariate objective/run/decision contracts
                |
  +-------------+-------------+
  |                           |
PR270 automatic universe   PR271 solver-backed candidates
selector                   |
  +-------------+-------------+
                |
        both merged to main
                |
  +-------------+-------------+
  |                           |
PR272 Multivariate run     PR273 decision persistence/API
+ OOS objective winner     |
  +-------------+-------------+
                |
        both merged to main
                |
PR274 Multivariate Dash optimizer + professional Decision Audit
                |
PR275 React deletion + production Dash/FastAPI/Docker cutover
                |
PR276 Sunday full research refresh
```

## PR264-PR276

### PR264. Plotly Dash Runtime, Shared Run-Control, Professional Plot Contract, And Four-Page Foundation

Branch: `feat/dash-runtime-foundation`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(dash): add four-page runtime, run-control, and plot foundation`.

Required squash subject: `feat(dash): add four-page runtime, run-control, and plot foundation`.

Base: `main`.

Merge method: squash only.

Priority: P0.

Depends on: already-merged hosted page-view, lazy-section, workflow, run, and command contracts.

Scope: temporary Dash/FastAPI sidecar, four page IDs/routes, shared `StatisticsRunControl`, typed gateway, deterministic fixtures, Docker/profile, architecture boundaries, and one frozen `ProfessionalPlotContract` covering titles, labeled axes/units, semantic legends, hovertemplates, stable trace ordering, unavailable states, responsive/accessibility metadata, and shared formatting.

Tasks / Acceptance: PR264 base checklist in `docs/backlog/plotly-dash-multivariate-optimizer-ui.md` plus the PR264 professional-plot amendment in `docs/backlog/plotly-dash-professional-plots-weekly-refresh.md`; both form one acceptance contract.

Parallelization: Agent B freezes contracts/IDs/run-control/plot contract/fixtures first; Agent A owns runtime/dependency/container wiring and may import but not edit frozen contracts.

Security: temporary Dash gets no DB/provider/shared-data authority.

Determinism: frozen IDs/routes/run-control/plot contracts determine display/runtime shape.

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

Scope: Portfell shell, project selector, process overview, responsive sidebar, exactly four workflow links, temporary `/dash/projects/<slug>/...` navigation, two-project isolation, no separate Optimizer link/status.

Tasks / Acceptance: authoritative PR265 checklist in base specification.

Parallelization: wave 1 Agent A; concurrent with PR266; shell/navigation-only paths.

Security: route/project state never authorizes data.

Determinism: workflow projection determines shell.

Idempotency: same-project selection emits no command.

Rollback: revert shell/navigation.

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

Scope: combined metadata download/builder, exact five criteria, project creation, initial-fill progress/retry/restore, responsive behavior, no provider credential in browser.

Tasks / Acceptance: authoritative PR266 checklist in base specification.

Parallelization: wave 1 Agent B; concurrent with PR265; Metadata-only paths.

Security: server remains provider-credential boundary.

Determinism: same page-view/options produce same UI.

Idempotency: duplicate callbacks cannot create duplicate logical commands.

Rollback: revert Metadata Dash files.

### PR267. Dash Univariate Statistics, Run Control, And Professional Return-Risk Universe

Branch: `feat/dash-univariate-universe`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(dash): add professional Univariate return-risk universe`.

Required squash subject: `feat(dash): add professional Univariate return-risk universe`.

Base: exact `main` after PR265+PR266.

Merge method: squash only.

Priority: P0.

Depends on: PR264-PR266.

Scope: exact `Compute univariate statistics` control/progress/status; existing Uni tabs/selection; professional always-visible Return/Volatility scatter and Pareto frontier with exact title/axes/legend/hover contract.

Tasks / Acceptance: base PR267 checklist plus PR267 amendment; title `Univariate Return / Risk Universe`, X `Annualized volatility (% p.a.)`, Y `Annualized geometric return (% p.a.)`, semantic legend, full listing/return/risk hover and visual-contract tests are mandatory.

Parallelization: wave 2 Agent A; concurrent with PR268; Univariate-only paths.

Security: authorized project results only.

Determinism: stable listing/trace/frontier order.

Idempotency: duplicate start converges; chart interactions read-only.

Rollback: revert Univariate Dash files.

### PR268. Dash Bivariate Statistics, Run Control, And Professional Return-Diversification Views

Branch: `feat/dash-bivariate-universe`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(dash): add professional Bivariate diversification views`.

Required squash subject: `feat(dash): add professional Bivariate diversification views`.

Base: same exact post-PR265/PR266 `main` as PR267.

Merge method: squash only.

Priority: P0.

Depends on: PR264-PR266.

Scope: exact `Compute bivariate statistics` control/progress/status; nine detailed views; professional global Return/median-dependence scatter, Plotly heatmaps, WebGL tail scatter, exact titles/axes/legends/colorbars/hover menus.

Tasks / Acceptance: base PR268 checklist plus PR268 amendment; all global/matrix/tail plots must pass the shared ProfessionalPlotContract and deterministic 201-listing fixture.

Parallelization: wave 2 Agent B; concurrent with PR267; Bivariate-only paths.

Security: section IDs never authorize access.

Determinism: pair revision/metric/trace order determine figures.

Idempotency: duplicate start converges; plot switches read-only.

Rollback: revert Bivariate Dash files.

### PR269. Multivariate Statistics Objective, Run, Progress, And Decision Contracts

Branch: `feat/multivariate-optimizer-contracts`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(multivariate): define optimizer objective and decision contracts`.

Required squash subject: `feat(multivariate): define optimizer objective and decision contracts`.

Base: exact `main` after PR267+PR268.

Merge method: squash only.

Priority: P0.

Depends on: PR267, PR268.

Scope: exactly three objectives, OOS ranking/tie rules, one Multivariate run/progress model, eight DecisionArtifact stages, reason codes, deterministic IDs/fixtures. No separate optimizer lifecycle.

Tasks / Acceptance: authoritative PR269 checklist in base specification.

Parallelization: Agent A contracts/objectives; Agent B fixtures/property/progress tests after freeze.

Security: analytical evidence only.

Determinism: objective registry/canonical serialization determine IDs.

Idempotency: identical writes converge; conflicts fail closed.

Rollback: remove new Multivariate optimizer contracts.

### PR270. Multivariate Automatic Universe Selector

Branch: `feat/multivariate-universe-selector`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(multivariate): add automatic optimizer universe selection`.

Required squash subject: `feat(multivariate): add automatic optimizer universe selection`.

Base: exact PR269 merge commit.

Merge method: squash only.

Priority: P0.

Depends on: PR269.

Scope: eligibility, Univariate Pareto selection, deterministic Bivariate redundancy reduction only when needed, <=250 output, decision evidence, no manual ISIN picking.

Tasks / Acceptance: authoritative PR270 checklist.

Parallelization: wave 3 Agent A; concurrent with PR271; selector-only paths.

Security: may only remove from authorized pinned input.

Determinism: frozen ranking/clustering/ties.

Idempotency: pure selector repeats exactly.

Rollback: remove selector.

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

Scope: solver-backed Maximum Sharpe/Maximum Diversification plus existing Minimum Variance/ERC/HRP/Minimum CVaR and Equal Weight baseline; Sample/Ledoit-Wolf/EWMA configurations; deterministic diagnostics; no exhaustive production subset/weight-grid enumeration.

Tasks / Acceptance: authoritative PR271 checklist.

Parallelization: wave 3 Agent B; concurrent with PR270; solver/candidate-only paths.

Security: pure numerical inputs.

Determinism: fixed solver settings/identities.

Idempotency: pure calculations mutate nothing.

Rollback: remove new solver adapters.

### PR272. Multivariate Run Orchestration And OOS Objective Winner

Branch: `feat/multivariate-auto-orchestrator`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(multivariate): optimize portfolio by selected OOS objective`.

Required squash subject: `feat(multivariate): optimize portfolio by selected OOS objective`.

Base: exact `main` after PR270+PR271.

Merge method: squash only.

Priority: P0.

Depends on: PR269-PR271 and walk-forward/scorecard infrastructure.

Scope: one Multivariate run performs automatic universe selection, risk models, candidate construction, walk-forward validation, objective-specific OOS winner, final refit, progress publication and all decisions.

Tasks / Acceptance: authoritative PR272 checklist.

Parallelization: wave 4 Agent A; concurrent with PR273; orchestration/ranking/progress only.

Security: authorize project/run before data.

Determinism: objective + bounded registry + split/ranking policy determine winner.

Idempotency: same inputs/objective/settings -> one run/winner.

Rollback: restore prior Multivariate orchestration.

### PR273. Multivariate Decision Persistence And Lazy Read Sections

Branch: `feat/multivariate-decision-sections`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(multivariate): persist and expose optimizer decision sections`.

Required squash subject: `feat(multivariate): persist and expose optimizer decision sections`.

Base: same exact post-PR270/PR271 `main` as PR272.

Merge method: squash only.

Priority: P0.

Depends on: PR269-PR271.

Scope: persist decisions under Multivariate run authority; compact page-view status/objective/winner; lazy decision sections; no calculation in GET paths; two-project isolation.

Tasks / Acceptance: authoritative PR273 checklist.

Parallelization: wave 4 Agent B; concurrent with PR272; persistence/read/API only.

Security: project + Multivariate run authorization first.

Determinism: canonical bytes/revisions.

Idempotency: identical writes no-op; reads non-mutating.

Rollback: remove persistence/read surfaces.

### PR274. Dash Multivariate Statistics Optimizer, Objective, Run Control, And Professional Decision Audit

Branch: `feat/dash-multivariate-optimizer`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(dash): make Multivariate Statistics the professional portfolio optimizer`.

Required squash subject: `feat(dash): make Multivariate Statistics the professional portfolio optimizer`.

Base: exact `main` after PR272+PR273.

Merge method: squash only.

Priority: P0.

Depends on: PR264-PR273.

Scope: exact objective selector, `Optimize portfolio`, progress/status; tabs `Universe`, `Risk Model`, `Optimization`, `Validation`, `Final Portfolio`; professional global candidate chart and professional plot/table/hover evidence for every important decision stage.

Tasks / Acceptance: base PR274 checklist plus complete PR274 ProfessionalPlotContract amendment. A registry test must enumerate every production Multivariate figure and reject missing title/axes/legend/hover metadata.

Parallelization: Agent A page/objective/figures/CSS; Agent B callbacks/view-model/sections/run-control/E2E/docs; frozen contracts immutable.

Security: authorized Multivariate sections only.

Determinism: objective/run revision -> stable traces/winner.

Idempotency: identical start -> one run; charts read-only.

Rollback: revert Multivariate Dash layer.

### PR275. Production Dash Cutover, React Deletion, And Docker Consolidation

Branch: `refactor/dash-production-cutover`.

Git status: planned.

PR: not opened.

Suggested PR title: `refactor(ui): replace React with Dash and consolidate runtime`.

Required squash subject: `refactor(ui): replace React with Dash and consolidate runtime`.

Base: exact PR274 merge commit.

Merge method: squash only.

Priority: P0 mandatory cutover.

Depends on: PR264-PR274 all green.

Scope: delete `apps/web/**` and React/TypeScript/Vite production UI; remove Node web and temporary Dash containers; mount Dash in FastAPI; remove `/dash` from canonical browser routes; final Compose exactly `postgres`, `app`, `project-bootstrap-worker`; migrate tests/docs/gates. Cutover E2E must prove professional plot title/axis/legend/hover semantics survived.

Tasks / Acceptance: base PR275 checklist plus PR275 plot-preservation amendment.

Parallelization: Agent B freezes cutover manifest; Agent A owns old UI/test/doc deletion; Agent B owns Python runtime/Docker/Compose/health/ports. Shared root files receive one owner in manifest.

Security: shared app may hold API secrets, but `dash_ui` dependency graph remains presentation-only.

Determinism: cutover manifest + route registry + three-service topology.

Idempotency: build/start/restart/cutover smoke does not duplicate state.

Rollback: return to PR274 coexistence SHA; no schema rewrite.

### PR276. Sunday Full Research Refresh

Branch: `feat/weekly-full-research-refresh`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(cron): refresh market data and all portfolio statistics weekly`.

Required squash subject: `feat(cron): refresh market data and all portfolio statistics weekly`.

Base: exact PR275 merge commit.

Merge method: squash only.

Priority: P0 scheduled research freshness.

Depends on: PR275 and final Uni/Bi/Multivariate service/run contracts.

Scope: keep one managed host cron; exact `CRON_TZ=Europe/Vienna`, `0 9 * * 0`; execute inside `project-bootstrap-worker`; refresh canonical quotes/dividends/splits once for the de-duplicated active-project union, then run/reuse Uni -> Bi -> Multivariate for every active project in stable order using persisted settings/objective/constraints; default missing Multivariate objective only to `return_risk`; persist progress/status/DecisionArtifacts; support failure isolation and restart/resume; no fourth long-running container and no browser required.

Tasks / Acceptance: single authoritative PR276 checklist in `docs/backlog/plotly-dash-professional-plots-weekly-refresh.md`.

Parallelization: Agent A owns scheduler/orchestrator and frozen cycle-result/stage contracts; Agent B independently owns cron/integration verification and operations docs. `pyproject.toml` is Agent A-only; docs are Agent B-only; Dash figure/page code is forbidden.

Security: trusted worker retains operations provider credential; nothing moves to browser/Dash; project isolation remains existing authority.

Determinism: exact schedule/timezone, stable project order, pinned market revision, persisted settings/objective, algorithm versions determine cycle.

Idempotency: `flock` + existing logical/content identities converge repeated/resumed cycles without duplicate market rows/runs/winners/DecisionArtifacts.

Rollback: revert to prior market-only cron behavior; already published analytical artifacts remain immutable/auditable.

## Series Completion Gate

The target is complete only when PR458 and PR264-PR276 are merged and one clean final `main` evidence run proves:

- PR458's CCR-01 through CCR-13 remediation contracts are satisfied by their owning implementation PRs, including durable worker execution, immutable analytical revisions, typed metric availability, full listing/configuration identity, truthful risk-model/OOS semantics, readiness, and project-scoped current-Univariate-selection authority;
- exactly four workflow pages exist and Multivariate Statistics is the only optimizer page/run/stage;
- Uni, Bi, Multivariate each expose their exact calculation button, progress bar, phase/status, failure/reload behavior, duplicate-start protection, and project isolation;
- Multivariate exposes exactly `return_risk`, `return_drawdown`, `minimum_risk` and selects the winner from objective-specific OOS evidence;
- every production Plotly figure is professional: descriptive title, labeled axes/units, semantic legend where applicable, deterministic friendly hover menu, stable trace semantics, explicit unavailable states, responsive/accessibility metadata;
- Univariate/Bivariate top-level plots and every important Multivariate decision visualization use server/persisted evidence only;
- no manual per-ISIN or optimizer-method selection is required after a Multivariate run starts and no exhaustive several-hundred-ISIN subset/weight-grid production path exists;
- React/TypeScript production UI is deleted, no production Node UI container remains, final Compose is exactly `postgres`, `app`, `project-bootstrap-worker`, and one Python app serves `/api` plus canonical Dash `/projects/<slug>/...`;
- managed cron is exactly Sunday `09:00 Europe/Vienna`, refreshes the active-union market data once, then completes/reuses Uni/Bi/Multivariate for every active project in dependency order without a browser;
- weekly Multivariate uses each project's persisted objective/constraints and defaults only an absent objective to `return_risk`;
- scheduled failure isolation/restart/resume/duplicate protection, two-project isolation, logs, worker execution, Python/Dash/API/contract/architecture/Docker/Compose/E2E/quality gates pass from one SHA.

## Historical Backlog Archive

`docs/backlog/archive/BACKLOG-2026-08-16-before-dash-optimizer.md` and `docs/backlog/archive/plotly-dash-three-page-research-ui-v1.md` are historical evidence only and must not override this file, the base implementation specification, or the active amendment.