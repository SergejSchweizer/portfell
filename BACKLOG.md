Last reviewed: 2026-08-16

## Backlog Policy

This file contains only active planned work for the Plotly Dash replacement UI, Multivariate Statistics portfolio optimizer, professional decision visualization, continuous universe/history visibility, mandatory React/Docker cutover, scheduled full research refresh, and correctness remediation from the current-code review. Unrelated planned work is intentionally absent.

Active implementation authority is the combination of:

- `BACKLOG.md`;
- `docs/backlog/plotly-dash-multivariate-optimizer-ui.md`;
- `docs/backlog/plotly-dash-multivariate-optimizer-ui-detailed-v1.md`;
- `docs/backlog/plotly-dash-professional-plots-weekly-refresh.md`;
- `docs/backlog/current-code-correctness-amendment.md`;
- `docs/backlog/current-code-project-isolation-addendum.md`;
- `docs/backlog/universe-history-pipeline-amendment.md`.

Where an active amendment is more specific than older wording, the amendment wins. Historical files under `docs/backlog/archive/` are evidence only.

Every active PR must contain `Branch`, `Git status`, `PR`, `Suggested PR title`, `Required squash subject`, `Base`, `Merge method`, `Priority`, `Depends on`, `Scope`, `Tasks / Acceptance`, `Parallelization`, `Security`, `Determinism`, `Idempotency`, and `Rollback`. There is exactly one checklist per PR named `Tasks / Acceptance`; all active amendment rows named for that PR are part of that same checklist.

## Weak-Agent Execution Rules

Assume two agents with weak reasoning, incomplete context, and no permission to infer missing architecture:

- parallel PRs branch from the exact same predecessor `main` merge commit and never from each other;
- shared contracts, component IDs, plot IDs, objective IDs, reason codes, route suffixes, progress states, tie-breaks, cron stage IDs, universe/history stage IDs, snapshot fields, and fixture IDs are frozen before parallel branches start;
- each PR owns explicit files/modules; overlapping ownership is forbidden unless a one-time hand-off is written first;
- UI never recomputes portfolio statistics, history ranges, counts, or optimizer explanations; it renders server-produced/persisted evidence;
- production optimization never enumerates all ISIN subsets or a several-hundred-dimensional exhaustive weight grid;
- every important Multivariate decision is incomplete until persisted evidence has a visible Decision Audit representation;
- every production Plotly figure uses the frozen `ProfessionalPlotContract`; local page-specific alternatives are forbidden;
- scheduled work calls the same server/analytical contracts as explicit runs and never creates a browser-only or cron-only second implementation;
- full listing identity is `(isin, exchange, code)`; unique ISIN count is display metadata only and may never replace listing identity.

## Product And UI Invariants

The workflow is exactly:

```text
Metadata Builder
    -> Univariate Statistics
    -> Bivariate Statistics
    -> Multivariate Statistics
```

**Multivariate Statistics is the portfolio optimizer.** There is no separate Optimizer page, route, workflow stage, scheduled stage, status surface, or post-Multivariate step. Selector/risk-model/solver/walk-forward/ranking/DecisionArtifact modules are internal components of one Multivariate Statistics run.

All three statistics pages contain one explicit calculation surface:

- Univariate: `Compute univariate statistics` + progress bar + phase/status + failure state;
- Bivariate: `Compute bivariate statistics` + progress bar + phase/status + failure state;
- Multivariate: required `Optimization objective` selector + `Optimize portfolio` + progress bar + phase/status + failure state.

Multivariate objectives are exactly `Return / Risk` (`return_risk`, default), `Return / Drawdown` (`return_drawdown`), and `Minimum Risk` (`minimum_risk`). Winner selection is objective-specific and uses walk-forward out-of-sample evidence only.

Required professional top-level plots remain:

- Univariate: `Univariate Return / Risk Universe`, X=`Annualized volatility (% p.a.)`, Y=`Annualized geometric return (% p.a.)`;
- Bivariate: `Bivariate Return / Diversification Universe`, Y=`Annualized geometric return (% p.a.)`, dynamic named median-dependence X axis;
- Multivariate: `Portfolio Candidate OOS Return / Risk`, X=`OOS annualized volatility (% p.a.)`, Y=`OOS annualized return (% p.a.)`.

PR264-PR274 build Dash beside React only as temporary migration scaffolding. PR275 deletes the React/TypeScript/Vite production UI, removes Node web and temporary Dash containers, mounts Dash into FastAPI, and leaves exactly `postgres`, `app`, `project-bootstrap-worker` as long-running Compose services.

## Universe And History Invariant

The functionality in `docs/backlog/universe-history-pipeline-amendment.md` is mandatory across PR264-PR276.

Every workflow page shows one persistent `Universe & History` summary and one `Research Universe & History Pipeline` visualization before page-specific analytical tabs. The user must always be able to see:

- current full-listing count and unique-ISIN count;
- how many listings were removed since the previous stage and why;
- `Observed history envelope` separately from `Common usable history`;
- exact common date start/end and observation count when a joint calendar is meaningful;
- Univariate per-listing history min/median/max and `Univariate Listing History Coverage`;
- Bivariate exact pair count, pairwise shared-observation min/median/max and `Pairwise Shared-History Distribution`;
- Multivariate aligned optimization calendar and `Walk-Forward Training / Test Coverage`;
- final portfolio holding count and exact final-refit common range/observation count.

Stage order is fixed:

```text
Metadata -> Univariate -> Bivariate -> Multivariate -> Final portfolio
```

Future/not-run/blocked stages remain visible with typed state. Unavailable/not-applicable history is never represented as `0`, an empty date, or a guessed value. Dash receives persisted/server-produced snapshots and never derives these ranges/counts from raw rows.

PR269 freezes the canonical `ResearchUniverseSnapshot` contract and exact definitions; PR270/PR272 produce internal optimizer-stage snapshots; PR273 persists/exposes them; PR274 visualizes them; PR276 reuses the identical artifacts in the Sunday run.

## Scheduled Research Invariant

The managed production schedule is exactly:

```text
CRON_TZ=Europe/Vienna
0 9 * * 0
```

One Sunday cycle runs without a browser:

```text
shared market refresh once
(quotes + dividends + splits for de-duplicated active-project union)
        -> Univariate Statistics per active project
        -> Bivariate Statistics per successful Uni selection/revision
        -> Multivariate Statistics per successful Bi revision
           using persisted objective/constraints
           default objective only when absent: return_risk
        -> terminal cycle summary
```

Market data is fetched once for the active union, never once per project. Within one project Bi waits for successful Uni, Multi waits for successful Bi. Failures are project-isolated. Re-run/resume reuses unchanged logical runs and creates no duplicate market business keys, runs, winners, DecisionArtifacts, or universe/history snapshots.

## PR458 Correctness Backlog Gate

### PR458. Current-Code Correctness Hardening, Project Isolation, And Research-Evidence Contract Registration

Branch: `docs/current-code-correctness-backlog-review`.
Git status: merged to `main`.
PR: GitHub PR #458, merged.
Suggested PR title: `docs(backlog): harden correctness and add universe-history audit`.
Required squash subject: `docs(backlog): harden correctness and add universe-history audit`.
Base: reviewed `main` at `69d76a108257a9d07dd8e22a918ae789942afc07`.
Merge method: squash.
Priority: P0 planning gate, complete.
Depends on: repository-wide static review of current `main`.
Scope: registered CCR-01 through CCR-13, project-scoped selection isolation, professional plotting/weekly-refresh authority, and mandatory universe/history pipeline requirements. Runtime implementation remains in PR264-PR276.
Tasks / Acceptance: completed by merged planning artifacts; implementation acceptance remains delegated to the owning PR264-PR276 work orders.
Parallelization: complete.
Security: planning only.
Determinism: contracts pinned to reviewed source/versions and frozen identifiers.
Idempotency: planning merge created no runtime state.
Rollback: revert documentation merge if necessary.

## Execution Graph

```text
PR458 merged planning gate
        |
        v
PR264 foundation
  |
  +---------------------------+
  |                           |
PR265 shell/navigation     PR266 Metadata + initial universe/history
  |                           |
  +-------------+-------------+
                |
        both merged to main
                |
  +-------------+-------------+
  |                           |
PR267 Uni + return/risk    PR268 Bi + diversification
+ listing-history         + pair-history
  |                           |
  +-------------+-------------+
                |
        both merged to main
                |
PR269 objective/run/decision + ResearchUniverseSnapshot contracts
                |
  +-------------+-------------+
  |                           |
PR270 universe selector    PR271 solver/risk-model candidates
+ history impact          + aligned-history evidence
  |                           |
  +-------------+-------------+
                |
        both merged to main
                |
  +-------------+-------------+
  |                           |
PR272 durable Multi run    PR273 decision + history persistence/API
+ OOS + WF ranges         |
  +-------------+-------------+
                |
        both merged to main
                |
PR274 Multivariate Dash optimizer + Decision/History Audit
                |
PR275 React deletion + Dash/FastAPI/Docker cutover
                |
PR276 Sunday full research refresh + same evidence contracts
```

## PR264-PR276

### PR264. Plotly Dash Runtime, Shared Run-Control, Professional Plot, And Universe/History Foundation
Branch: `feat/dash-runtime-foundation`.
Git status: planned.
PR: not opened.
Suggested PR title: `feat(dash): add four-page runtime, run-control, plot, and history foundation`.
Required squash subject: `feat(dash): add four-page runtime, run-control, plot, and history foundation`.
Base: `main`.
Merge method: squash only.
Priority: P0.
Depends on: PR458 merged planning gate.
Scope: temporary Dash/FastAPI sidecar, four routes, shared `StatisticsRunControl`, typed gateway, `ProfessionalPlotContract`, Universe/History presentation contracts/figure IDs, deterministic two-project fixtures, Docker/profile and architecture boundaries.
Tasks / Acceptance: PR264 base checklist + professional-plot amendment + PR264 universe/history amendment.
Parallelization: Agent B freezes contracts/IDs/run-control/plot/history fixtures first; Agent A owns runtime/container wiring.
Security: Dash gets no DB/provider/shared-data authority.
Determinism: frozen IDs/contracts/fixtures.
Idempotency: startup/health/reads mutate nothing.
Rollback: remove temporary Dash additions.

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
Scope: shell/project selector/process overview/sidebar with exactly four workflow links; compact current-stage listing/common-history indicator from the shared snapshot.
Tasks / Acceptance: base PR265 checklist + PR265 universe/history amendment.
Parallelization: wave 1 Agent A; concurrent with PR266; shell-only paths.
Security: route/project state never authorizes data.
Determinism: workflow + snapshot projection determines shell.
Idempotency: same-project selection emits no command.
Rollback: revert shell/navigation.

### PR266. Dash Metadata Builder And Initial Universe/History Evidence
Branch: `feat/dash-metadata-builder`.
Git status: planned.
PR: not opened.
Suggested PR title: `feat(dash): add Metadata Builder and initial universe history`.
Required squash subject: `feat(dash): add Metadata Builder and initial universe history`.
Base: same exact PR264 merge commit as PR265.
Merge method: squash only.
Priority: P1.
Depends on: PR264.
Scope: metadata download/builder with exact five criteria, project creation/fill progress, listing/unique-ISIN counts and history evidence when market history exists; downstream stages typed not-run/blocked.
Tasks / Acceptance: base PR266 checklist + PR266 universe/history amendment.
Parallelization: wave 1 Agent B; concurrent with PR265; Metadata-only paths.
Security: provider credential stays server-side.
Determinism: same revision/options -> same summary.
Idempotency: duplicate callbacks cannot create duplicate logical commands.
Rollback: revert Metadata Dash files.

### PR267. Dash Univariate Statistics, Return-Risk, And Listing-History Views
Branch: `feat/dash-univariate-universe`.
Git status: planned.
PR: not opened.
Suggested PR title: `feat(dash): add professional Univariate return-risk and history views`.
Required squash subject: `feat(dash): add professional Univariate return-risk and history views`.
Base: exact `main` after PR265+PR266.
Merge method: squash only.
Priority: P0.
Depends on: PR264-PR266.
Scope: compute control/progress, existing tabs/selection, professional Return/Risk plot/Pareto frontier, Univariate snapshot, per-listing history distribution and `Univariate Listing History Coverage`.
Tasks / Acceptance: base PR267 + professional plot + correctness + universe/history amendments.
Parallelization: wave 2 Agent A; concurrent with PR268; Univariate-only paths.
Security: authorized project results only.
Determinism: stable listing/trace/history ordering.
Idempotency: duplicate start converges; plots read-only.
Rollback: revert Univariate Dash files.

### PR268. Dash Bivariate Statistics, Diversification, And Pair-History Views
Branch: `feat/dash-bivariate-universe`.
Git status: planned.
PR: not opened.
Suggested PR title: `feat(dash): add professional Bivariate diversification and history views`.
Required squash subject: `feat(dash): add professional Bivariate diversification and history views`.
Base: same exact post-PR265/PR266 `main` as PR267.
Merge method: squash only.
Priority: P0.
Depends on: PR264-PR266.
Scope: compute control/progress, global Return/Diversification plot, detailed heatmaps/tail scatter, exact pair evidence, pairwise history statistics and `Pairwise Shared-History Distribution`.
Tasks / Acceptance: base PR268 + professional plot + correctness + universe/history amendments.
Parallelization: wave 2 Agent B; concurrent with PR267; Bivariate-only paths.
Security: section IDs never authorize access.
Determinism: exact pair set/revision/metric order.
Idempotency: duplicate start converges; plot switches read-only.
Rollback: revert Bivariate Dash files.

### PR269. Multivariate Objective, Run, Decision, Correctness, And ResearchUniverseSnapshot Contracts
Branch: `feat/multivariate-optimizer-contracts`.
Git status: planned.
PR: not opened.
Suggested PR title: `feat(multivariate): define optimizer, correctness, and universe-history contracts`.
Required squash subject: `feat(multivariate): define optimizer, correctness, and universe-history contracts`.
Base: exact `main` after PR267+PR268.
Merge method: squash only.
Priority: P0.
Depends on: PR267, PR268.
Scope: three objectives, OOS ranking/ties, one Multivariate run/progress model, eight DecisionArtifact stages, full ListingIdentity/configuration identity, durable attempt/error/availability contracts, project-scoped selection contract, canonical `ResearchUniverseSnapshot`, exact envelope/common-history semantics and removal reason registry.
Tasks / Acceptance: base PR269 + correctness/project-isolation + universe/history amendments.
Parallelization: Agent A freezes contracts; Agent B writes fixtures/tests after freeze.
Security: analytical evidence only; public errors redacted.
Determinism: canonical serialization/IDs.
Idempotency: identical writes converge; conflicts fail closed.
Rollback: remove new contracts.

### PR270. Multivariate Automatic Universe Selector With History Impact Evidence
Branch: `feat/multivariate-universe-selector`.
Git status: planned.
PR: not opened.
Suggested PR title: `feat(multivariate): add automatic universe selection and history evidence`.
Required squash subject: `feat(multivariate): add automatic universe selection and history evidence`.
Base: exact PR269 merge commit.
Merge method: squash only.
Priority: P0.
Depends on: PR269.
Scope: eligibility, Univariate Pareto selection, deterministic Bivariate redundancy reduction when needed, <=250 output, DecisionArtifacts, before/after counts/reasons and common-history effect at each reduction; no manual ISIN picking.
Tasks / Acceptance: base PR270 + correctness + universe/history amendments.
Parallelization: wave 3 Agent A; concurrent with PR271; selector-only paths.
Security: may only remove from authorized pinned input.
Determinism: frozen ranking/clustering/ties/snapshot definitions.
Idempotency: pure selector repeats exactly.
Rollback: remove selector.

### PR271. Multivariate Solver-Backed Candidates And Aligned-History Diagnostics
Branch: `feat/multivariate-production-solvers`.
Git status: planned.
PR: not opened.
Suggested PR title: `feat(multivariate): add solver-backed candidates and aligned history diagnostics`.
Required squash subject: `feat(multivariate): add solver-backed candidates and aligned history diagnostics`.
Base: same exact PR269 merge commit as PR270.
Merge method: squash only.
Priority: P0.
Depends on: PR269.
Scope: solver-backed Maximum Sharpe/Maximum Diversification plus Minimum Variance/ERC/HRP/Minimum CVaR/Equal Weight; Sample/Ledoit-Wolf/EWMA; full listing identity; exact risk-model aligned date range/observation count per configuration; no exhaustive production enumeration.
Tasks / Acceptance: base PR271 + correctness + universe/history amendments.
Parallelization: wave 3 Agent B; concurrent with PR270; solver/risk-model paths.
Security: pure numerical inputs.
Determinism: fixed solver/model/configuration identities.
Idempotency: pure calculations mutate nothing.
Rollback: remove solver adapters.

### PR272. Durable Multivariate Orchestration, OOS Winner, And Walk-Forward History Evidence
Branch: `feat/multivariate-auto-orchestrator`.
Git status: planned.
PR: not opened.
Suggested PR title: `feat(multivariate): optimize by OOS objective with auditable history`.
Required squash subject: `feat(multivariate): optimize by OOS objective with auditable history`.
Base: exact `main` after PR270+PR271.
Merge method: squash only.
Priority: P0.
Depends on: PR269-PR271.
Scope: one durable Multivariate run performs selection, risk models, candidates, walk-forward, objective winner and final refit; publishes attempt-safe DecisionArtifacts, universe/history snapshots and exact train/test ranges.
Tasks / Acceptance: base PR272 + correctness + universe/history amendments.
Parallelization: wave 4 Agent A; concurrent with PR273; orchestration/ranking/progress paths.
Security: authorize project/run before data.
Determinism: objective + registry + split/ranking policy.
Idempotency: same inputs/settings -> one logical result.
Rollback: restore prior orchestration.

### PR273. Multivariate Decision And Universe/History Persistence/API
Branch: `feat/multivariate-decision-sections`.
Git status: planned.
PR: not opened.
Suggested PR title: `feat(multivariate): persist decision and universe-history sections`.
Required squash subject: `feat(multivariate): persist decision and universe-history sections`.
Base: same exact post-PR270/PR271 `main` as PR272.
Merge method: squash only.
Priority: P0.
Depends on: PR269-PR271.
Scope: project-scoped immutable decisions/current-selection state, `ResearchUniverseSnapshot` persistence, compact pipeline projection and lazy detailed history/decision sections; GET paths calculate nothing.
Tasks / Acceptance: base PR273 + correctness/project-isolation + universe/history amendments.
Parallelization: wave 4 Agent B; concurrent with PR272; persistence/read/API paths.
Security: project + run authorization first.
Determinism: canonical bytes/revisions.
Idempotency: identical writes no-op; reads non-mutating.
Rollback: remove persistence/read surfaces.

### PR274. Dash Multivariate Statistics Optimizer, Decision Audit, And Universe/History Audit
Branch: `feat/dash-multivariate-optimizer`.
Git status: planned.
PR: not opened.
Suggested PR title: `feat(dash): make Multivariate Statistics the auditable portfolio optimizer`.
Required squash subject: `feat(dash): make Multivariate Statistics the auditable portfolio optimizer`.
Base: exact `main` after PR272+PR273.
Merge method: squash only.
Priority: P0.
Depends on: PR264-PR273.
Scope: objective selector, `Optimize portfolio`, progress/status, tabs `Universe`, `Risk Model`, `Optimization`, `Validation`, `Final Portfolio`, professional Decision Audit, persistent Universe & History summary/pipeline, reduction history, aligned risk-model history, `Walk-Forward Training / Test Coverage`, final-refit history.
Tasks / Acceptance: base PR274 + professional plot + correctness + universe/history amendments. Registry tests cover every figure.
Parallelization: Agent A page/figures/CSS; Agent B callbacks/view-model/sections/E2E/docs.
Security: authorized persisted sections only.
Determinism: run/objective/revision -> stable traces/ranges/winner.
Idempotency: identical start -> one run; charts read-only.
Rollback: revert Multivariate Dash layer.

### PR275. Production Dash Cutover, React Deletion, Docker Consolidation, And Evidence-Preservation Gate
Branch: `refactor/dash-production-cutover`.
Git status: planned.
PR: not opened.
Suggested PR title: `refactor(ui): replace React with Dash and consolidate runtime`.
Required squash subject: `refactor(ui): replace React with Dash and consolidate runtime`.
Base: exact PR274 merge commit.
Merge method: squash only.
Priority: P0 mandatory cutover.
Depends on: PR264-PR274 all green.
Scope: delete React/TS/Vite/Node UI, mount Dash in FastAPI, canonical routes without `/dash`, final Compose exactly `postgres`, `app`, `project-bootstrap-worker`; preserve professional plots, DecisionArtifacts, project isolation, typed availability and Universe/History semantics through restart/project switching.
Tasks / Acceptance: base PR275 + professional plot + correctness/project-isolation + universe/history amendments.
Parallelization: Agent B freezes cutover manifest; Agent A old UI deletion; Agent B Python runtime/Docker/Compose/readiness.
Security: Dash package remains presentation-only.
Determinism: cutover manifest + route/evidence contracts.
Idempotency: build/start/restart do not duplicate state.
Rollback: return to PR274 coexistence SHA.

### PR276. Sunday Full Research Refresh With Complete Research Evidence
Branch: `feat/weekly-full-research-refresh`.
Git status: planned.
PR: not opened.
Suggested PR title: `feat(cron): refresh market data and all portfolio statistics weekly`.
Required squash subject: `feat(cron): refresh market data and all portfolio statistics weekly`.
Base: exact PR275 merge commit.
Merge method: squash only.
Priority: P0 scheduled research freshness.
Depends on: PR275 and final service/run/evidence contracts.
Scope: exact Sunday `09:00 Europe/Vienna`; one shared quotes/dividends/splits refresh for de-duplicated active union; stable per-project Uni -> Bi -> Multivariate using persisted settings/objective/constraints; same progress/DecisionArtifact/ResearchUniverseSnapshot authority as manual runs; project failure isolation/restart/resume; no browser/fourth service.
Tasks / Acceptance: PR276 professional/weekly-refresh checklist + correctness/project-isolation + universe/history amendments.
Parallelization: Agent A scheduler/orchestrator/contracts; Agent B independent integration verification/operations docs.
Security: trusted worker keeps operations credential; browser receives none.
Determinism: schedule + pinned market revision + project settings/objective + algorithm versions.
Idempotency: `flock` + logical identities prevent duplicates.
Rollback: revert to prior market-only cron behavior; published evidence remains auditable.

## Series Completion Gate

The target is complete only when PR264-PR276 are merged and one clean final `main` evidence run proves:

- CCR-01 through CCR-13 remediation contracts pass;
- exactly four workflow pages exist and Multivariate Statistics is the only optimizer page/run/stage;
- Uni/Bi/Multi expose exact calculation buttons, progress, phase/status, failure/reload behavior and duplicate-start protection;
- Multivariate exposes exactly the three frozen objectives and selects the winner from OOS evidence;
- every production Plotly figure has professional title, labeled axes/units, semantic legend where applicable, deterministic friendly hover, stable trace semantics, explicit unavailable states, responsiveness and accessible metadata;
- every workflow page shows exact listing count + unique ISIN count + revision-backed Universe & History evidence;
- the pipeline keeps `Metadata -> Univariate -> Bivariate -> Multivariate -> Final portfolio` visible in stable order and distinguishes history envelope from common usable history;
- Univariate shows per-listing history evidence; Bivariate shows exact pair/shared-history evidence; Multivariate shows aligned risk-model history and all walk-forward train/test ranges;
- unavailable/not-run/blocked history is typed, never `0`, empty date or guessed value;
- manual runs and Sunday refresh reuse the same universe/history snapshot semantics and identities for the same immutable inputs;
- no manual per-ISIN or optimizer-method selection is required after Multivariate starts and no exhaustive several-hundred-ISIN subset/weight-grid production path exists;
- React/TypeScript production UI is deleted; final Compose is exactly `postgres`, `app`, `project-bootstrap-worker`; one Python app serves `/api` and canonical Dash `/projects/<slug>/...`;
- cron is exactly Sunday `09:00 Europe/Vienna`, refreshes active-union market data once, then completes/reuses Uni/Bi/Multivariate in dependency order without a browser;
- weekly Multivariate uses each project's persisted objective/constraints and defaults only absent objective to `return_risk`;
- two-project isolation covers counts/ranges/selections/results across project switch, restart and weekly processing order;
- all Python/Dash/API/contract/architecture/Docker/Compose/E2E/quality gates pass from one SHA.

## Historical Backlog Archive

`docs/backlog/archive/BACKLOG-2026-08-16-before-dash-optimizer.md` and `docs/backlog/archive/plotly-dash-three-page-research-ui-v1.md` are historical evidence only and must not override this file or the active authority documents.