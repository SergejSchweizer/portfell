Last reviewed: 2026-08-16

## Table Of Contents

- [Backlog Policy](#backlog-policy)
- [Weak-Agent Execution Rules](#weak-agent-execution-rules)
- [Active Plotly Dash And Automatic Optimizer Stack](#active-plotly-dash-and-automatic-optimizer-stack)
- [Execution Graph](#execution-graph)
- [PR264-PR274](#pr264-pr274)
- [Series Completion Gate](#series-completion-gate)
- [Historical Backlog Archive](#historical-backlog-archive)

## Backlog Policy

This file contains only active planned work for the Plotly Dash research UI and the automatic portfolio optimizer. Planned work unrelated to Plotly/Dash, optimizer construction, optimizer explainability, or the required Uni/Bivariate decision visualizations is intentionally removed from the active backlog.

Completed, superseded, pushed, and historical records that existed before this refocus are preserved verbatim in `docs/backlog/archive/BACKLOG-2026-08-16-before-dash-optimizer.md`; they are not active planning authority. The superseded three-page-only Dash specification is preserved in `docs/backlog/archive/plotly-dash-three-page-research-ui-v1.md`.

Every active PR must contain `Branch`, `Git status`, `PR`, `Priority`, `Depends on`, `Base`, `Merge method`, `Scope`, `Tasks / Acceptance`, `Parallelization`, `Security`, `Determinism`, `Idempotency`, and `Rollback`. The detailed, normative work orders are in `docs/backlog/plotly-dash-three-page-research-ui.md`.

There is exactly one checklist per PR named `Tasks / Acceptance`. There is no second acceptance list. A checkbox may be marked complete only when the implementation and the exact evidence named by that checkbox are both present.

## Weak-Agent Execution Rules

Assume two agents with weak reasoning, incomplete context, and no permission to infer missing architecture. Therefore:

- parallel PRs always branch from the same named `main` merge commit and never from each other;
- every shared contract is frozen in a predecessor PR before parallel branches start;
- each PR owns explicit files/modules and forbidden paths; overlapping ownership is prohibited unless the predecessor defines a one-time hand-off;
- identifiers, route names, reason codes, metric names, fixture IDs, sorting rules, tie-break rules, and test commands are written explicitly in the normative specification;
- UI code never recomputes portfolio statistics or reverse-engineers why the optimizer made a decision; it renders persisted server-produced decision artifacts;
- the optimizer never uses exhaustive permutation or exhaustive weight-grid enumeration for a several-hundred-ISIN production universe; numerical solvers and bounded automatic universe reduction are required;
- a decision is not considered implemented until its reason/evidence can be rendered on the Multivariate Decision Audit page.

## Active Plotly Dash And Automatic Optimizer Stack

The target research workflow is exactly:

```text
Metadata Builder
    -> Univariate Statistics
    -> Bivariate Statistics
    -> Multivariate Statistics / Automatic Optimizer
```

Dash remains a presentation/orchestration adapter over existing authorized Portfell application services. It may not read PostgreSQL, Parquet, the shared market store, or EODHD directly and may not own financial formulas. The automatic optimizer runs in the Python analytical/service layer, persists immutable decision artifacts, and exposes those artifacts through authorized project/run sections. React is not deleted by this planning series; production cutover is a separate explicit decision after PR274.

Every important algorithmic choice must be auditable. At minimum the persisted decision chain must explain: input eligibility, Univariate Pareto status, Bivariate redundancy reduction when required, risk-model/configuration candidates, optimizer-method candidates, walk-forward scorecard, winner selection, final weights, risk contributions, and income contributions when income evidence exists.

Univariate Statistics must contain a global Plotly universe chart above its tabs. Bivariate Statistics must contain a global Plotly universe chart above its tabs. Multivariate Statistics must contain a global portfolio-candidate chart above its tabs and one or more plots for every important optimizer decision stage.

## Execution Graph

```text
PR264 Dash + shared visualization/decision UI foundation
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
PR267 Univariate + plot    PR268 Bivariate + plot
  |                           |
  +-------------+-------------+
                |
        both merged to main
                |
                v
PR269 optimizer decision-contract foundation
                |
  +-------------+-------------+
  |                           |
  v                           v
PR270 automatic universe   PR271 production solver set
selector                   + robust candidate builder
  |                           |
  +-------------+-------------+
                |
        both merged to main
                |
  +-------------+-------------+
  |                           |
  v                           v
PR272 auto optimizer       PR273 decision-artifact API
orchestrator + OOS winner  and lazy sections
  |                           |
  +-------------+-------------+
                |
        both merged to main
                |
                v
PR274 Dash Multivariate Decision Audit + end-to-end gate
```

## PR264-PR274

### PR264. Plotly Dash Runtime And Four-Page Contract Foundation

Branch: `feat/dash-runtime-foundation`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(dash): add four-page research runtime foundation`.

Required squash subject: `feat(dash): add four-page research runtime foundation`.

Base: `main`.

Merge method: squash merge only after current `main` is integrated and all named gates pass.

Priority: P0; all later parallel Dash work depends on immutable IDs/contracts.

Depends on: already-merged hosted page-view, lazy-section, workflow, run, and command contracts.

Scope: Dash/FastAPI sidecar, exactly four page IDs/routes, common Plotly figure conventions, typed gateway, fixed component-ID registry, decision-visualization presentation contracts, Docker/Compose runtime, deterministic fixtures, and architecture boundary tests. No optimizer math is implemented here.

Tasks / Acceptance: the single authoritative `PR264` checklist in `docs/backlog/plotly-dash-three-page-research-ui.md`.

Parallelization: within this foundation PR, Agent B freezes contracts/IDs/fixtures first; Agent A then owns runtime/dependency/container wiring and may import but not edit those frozen files.

Security: no provider secret, database credential, lake mount, or authorization authority enters Dash.

Determinism: frozen IDs/routes/contracts and locked dependencies determine one runtime shape per Git SHA.

Idempotency: import/startup/health/read paths are non-mutating.

Rollback: remove Dash runtime/dependencies/profile only; no database or analytical migration exists.

### PR265. Dash Shell And Four-Stage Project Navigation

Branch: `feat/dash-research-shell`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(dash): add four-stage research shell`.

Required squash subject: `feat(dash): add four-stage research shell`.

Base: exact `main` commit containing merged PR264.

Merge method: squash merge only.

Priority: P1.

Depends on: PR264.

Scope: Portfell header, project selector, process overview, responsive sidebar and exactly four workflow links in order: Metadata Builder, Univariate Statistics, Bivariate Statistics, Multivariate Statistics. Canonical `/dash/projects/<slug>/...` routes and two-project isolation are mandatory.

Tasks / Acceptance: the single authoritative `PR265` checklist in the normative specification.

Parallelization: wave 1 Agent A. It may run concurrently with PR266. It owns shell/navigation/CSS only and must not edit Metadata Builder page/callback files.

Security: route/project state never grants access.

Determinism: project slug normalization and server workflow projection determine navigation state.

Idempotency: navigation GETs are reads; re-selecting the current project emits no command.

Rollback: revert Dash shell/navigation files only.

### PR266. Dash Metadata Builder

Branch: `feat/dash-metadata-builder`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(dash): add Metadata Builder page`.

Required squash subject: `feat(dash): add Metadata Builder page`.

Base: same exact PR264 merge commit as PR265; never branch from PR265.

Merge method: squash merge only.

Priority: P1.

Depends on: PR264.

Scope: existing combined metadata download/builder workflow, five criteria, create-project, initial-fill progress/retry/restore, responsive behavior, no provider credential in the browser.

Tasks / Acceptance: the single authoritative `PR266` checklist in the normative specification.

Parallelization: wave 1 Agent B. It may run concurrently with PR265 and owns only Metadata page/view-model/callback/tests/docs paths.

Security: existing server command remains authorization and credential boundary.

Determinism: same page-view revision and criteria payload produce the same controls/status.

Idempotency: duplicate callbacks cannot create duplicate logical metadata/project commands.

Rollback: revert Dash Metadata files only.

### PR267. Dash Univariate Statistics With Global Return-Risk Universe Plot

Branch: `feat/dash-univariate-universe`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(dash): visualize Univariate return-risk universe`.

Required squash subject: `feat(dash): visualize Univariate return-risk universe`.

Base: exact `main` commit after PR265 and PR266 are both merged.

Merge method: squash merge only.

Priority: P0; this plot becomes the visual explanation of the current one-ISIN selection.

Depends on: PR264, PR265, PR266.

Scope: complete current Univariate run/restore/selection UI plus one always-visible Plotly scatter above all tabs. X is annualized volatility, Y is annualized geometric return, one point is one listing, selected/rejected/data-quality states remain visible, hover exposes the named metrics, and the non-dominated Return/Risk Pareto frontier is drawn from server-provided Univariate values without changing selection formulas.

Tasks / Acceptance: the single authoritative `PR267` checklist in the normative specification.

Parallelization: wave 2 Agent A. It may run concurrently with PR268. Visual agent owns figures/page/CSS; state agent owns callbacks/view-model/tests/docs; Bivariate files are forbidden.

Security: only authorized project-scoped result/settings payloads are rendered.

Determinism: stable listing order plus fixed figure builder/tie rules produce byte-equivalent trace inputs.

Idempotency: plot interactions do not mutate analytical results; selection saves retain server last-value-wins semantics.

Rollback: remove Univariate Dash page/figure additions only.

### PR268. Dash Bivariate Statistics With Global Return-Diversification Universe Plot

Branch: `feat/dash-bivariate-universe`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(dash): visualize Bivariate diversification universe`.

Required squash subject: `feat(dash): visualize Bivariate diversification universe`.

Base: same exact post-PR265/PR266 `main` commit as PR267; never branch from PR267.

Merge method: squash merge only.

Priority: P0.

Depends on: PR264, PR265, PR266.

Scope: complete nine-view Bivariate Dash page plus one always-visible Plotly scatter above all tabs. One point is one ISIN; Y is that ISIN's annualized geometric return from the pinned Univariate selection and X defaults to median Pearson correlation to all other selected ISINs. The X metric can switch among median Pearson, Spearman, Downside Correlation, Lower-Tail Dependence, Co-exceedance, and Drawdown Overlap. Existing matrices become Plotly heatmaps and the Tail-Risk Scatter uses WebGL.

Tasks / Acceptance: the single authoritative `PR268` checklist in the normative specification.

Parallelization: wave 2 Agent B. It may run concurrently with PR267. It owns only Bivariate page/figure/callback/view-model/tests/docs paths.

Security: section IDs and listing labels never authorize access.

Determinism: pair order, aggregation rule, metric selector, and stable listing order determine identical figure inputs.

Idempotency: lazy reads and chart interactions are non-mutating.

Rollback: revert Bivariate Dash changes only.

### PR269. Optimizer Decision Artifact And Profile Contract Foundation

Branch: `feat/optimizer-decision-contracts`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(optimizer): define auditable automatic decision contracts`.

Required squash subject: `feat(optimizer): define auditable automatic decision contracts`.

Base: exact `main` commit after PR267 and PR268 are merged.

Merge method: squash merge only.

Priority: P0; PR270-PR274 may not invent their own reason codes or artifact shapes.

Depends on: PR267, PR268 and existing Multivariate/risk-model/scorecard contracts.

Scope: freeze `return_risk` optimization profile, immutable `DecisionArtifact`/`DecisionCandidate`/`DecisionRejection` contracts, stage/reason enums, automatic-run settings, deterministic IDs, a `DecisionSink` protocol, and fixtures for every later stage. No universe-selection or solver implementation is permitted.

Tasks / Acceptance: the single authoritative `PR269` checklist in the normative specification.

Parallelization: within PR269, Agent A owns contracts/reason enums/IDs; Agent B owns fixtures/schema/property tests/docs. Contracts merge before the next wave starts.

Security: artifacts contain metrics/reasons and stable listing/candidate IDs only; no credentials, SQL, storage paths, or cross-tenant data.

Determinism: canonical sorted payload plus algorithm/profile version yields stable decision IDs.

Idempotency: persisting the same decision ID/content is a no-op; conflicting content for one ID fails closed.

Rollback: remove only new optimizer decision contracts; existing portfolio calculations stay usable.

### PR270. Automatic Universe Selector From Uni/Bivariate Evidence

Branch: `feat/optimizer-universe-selector`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(optimizer): add automatic universe selection`.

Required squash subject: `feat(optimizer): add automatic universe selection`.

Base: exact `main` commit containing merged PR269.

Merge method: squash merge only.

Priority: P0.

Depends on: PR269.

Scope: automatically convert several hundred selected listings into a bounded optimizer universe with no manual per-ISIN picking. Apply data/history/distribution eligibility, Univariate non-dominated sorting, and only when the remaining set exceeds the bounded risk-model limit, deterministic Bivariate redundancy clustering/representative selection. Every include/exclude decision emits a DecisionArtifact with exact evidence and reason code.

Tasks / Acceptance: the single authoritative `PR270` checklist in the normative specification.

Parallelization: wave 3 Agent A. It may run concurrently with PR271. It owns selector/ranking/clustering/selector-tests only and consumes but never edits PR269 contracts.

Security: input membership is already project-authorized; selector cannot add a listing absent from the pinned input universe.

Determinism: same pinned Uni/Bivariate revisions and policy version produce identical membership/order/reasons.

Idempotency: repeated selection produces the same artifact IDs and no duplicate run state.

Rollback: remove selector/orchestration hook; upstream statistics remain unchanged.

### PR271. Solver-Backed Return-Risk Portfolio Candidate Set

Branch: `feat/optimizer-production-solvers`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(optimizer): add solver-backed return-risk candidates`.

Required squash subject: `feat(optimizer): add solver-backed return-risk candidates`.

Base: same exact PR269 merge commit as PR270; never branch from PR270.

Merge method: squash merge only.

Priority: P0.

Depends on: PR269.

Scope: add real numerical production implementations for Maximum Sharpe and Maximum Diversification and expose the existing Minimum Variance, ERC, HRP, Minimum CVaR, and Equal Weight baseline through one candidate-builder contract. Use validated Sample/Ledoit-Wolf/EWMA risk models as versioned configurations. Exhaustive portfolio permutation or weight-grid enumeration is forbidden in production beyond the existing tiny-baseline guard.

Tasks / Acceptance: the single authoritative `PR271` checklist in the normative specification.

Parallelization: wave 3 Agent B. It may run concurrently with PR270. It owns solver adapters/candidate builder/numerical tests only and consumes frozen PR269 contracts and fixture universes.

Security: pure numerical code receives only already-resolved return matrices and constraints.

Determinism: fixed solver tolerances, initialization, sorted listings, and tie rules yield stable feasible weights within named numeric tolerances.

Idempotency: pure solver calls mutate no durable state.

Rollback: remove new solver adapters while existing solver methods remain intact.

### PR272. Automatic Optimizer Orchestrator And Out-Of-Sample Winner

Branch: `feat/optimizer-auto-orchestrator`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(optimizer): select return-risk portfolio automatically`.

Required squash subject: `feat(optimizer): select return-risk portfolio automatically`.

Base: exact `main` commit after PR270 and PR271 are both merged.

Merge method: squash merge only.

Priority: P0; this is the first end-to-end automatic portfolio choice.

Depends on: PR269, PR270, PR271 and existing walk-forward/scorecard code.

Scope: one `return_risk` command consumes the pinned Bivariate universe and optional portfolio constraints, runs the automatic selector, builds bounded model configurations, performs rolling walk-forward evaluation, ranks only out-of-sample results, selects exactly one winner, computes final full-history weights, risk/income contributions, and writes all PR269 decision stages. No user chooses individual ISINs or optimizer method after the command starts.

Tasks / Acceptance: the single authoritative `PR272` checklist in the normative specification.

Parallelization: wave 4 Agent A. It may run concurrently with PR273. It owns orchestration/model-ranking/winner tests and may only write decisions through the PR269 `DecisionSink`.

Security: command authorizes user/project/run before resolving any analysis input; no artifact identifier alone grants access.

Determinism: same pinned input revisions/profile/constraints produce the same model set, rankings, winner, weights, and decision IDs.

Idempotency: duplicate command delivery reuses one logical automatic run and cannot create two winners.

Rollback: automatic command is removed; existing manual Multivariate candidate APIs remain intact.

### PR273. Authorized Decision Artifact Persistence And Lazy Read Sections

Branch: `feat/optimizer-decision-sections`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(optimizer): persist and expose decision audit sections`.

Required squash subject: `feat(optimizer): persist and expose decision audit sections`.

Base: same exact post-PR270/PR271 `main` commit as PR272; never branch from PR272.

Merge method: squash merge only; rebase after PR272 only for final integration evidence.

Priority: P0; Dash must render actual persisted algorithm decisions rather than reconstruct explanations.

Depends on: PR269, PR270, PR271.

Scope: content-addressed/persisted DecisionArtifact storage through existing artifact authority, project/run authorization mapping, compact summary and lazy sections for universe, risk model, optimizer candidates, validation, and final portfolio. Add size bounds, revision IDs, typed unavailable/stale states, and two-project isolation. No financial computation occurs in GET/read paths.

Tasks / Acceptance: the single authoritative `PR273` checklist in the normative specification.

Parallelization: wave 4 Agent B. It may run concurrently with PR272. It owns decision repositories/read models/routes/contracts/tests and may not edit optimizer algorithms.

Security: every read begins with owned project and run; decision/artifact IDs are never authorization.

Determinism: persisted canonical artifact bytes and section revisions are stable for identical decision content.

Idempotency: repeated writes of identical artifacts and repeated reads do not mutate state.

Rollback: remove decision persistence/routes; automatic optimizer core can still run in-memory for tests.

### PR274. Dash Multivariate Decision Audit And Full Automatic-Optimizer Gate

Branch: `feat/dash-multivariate-decision-audit`.

Git status: planned.

PR: not opened.

Suggested PR title: `feat(dash): add automatic optimizer decision audit`.

Required squash subject: `feat(dash): add automatic optimizer decision audit`.

Base: exact `main` commit after PR272 and PR273 are both merged.

Merge method: squash merge only.

Priority: P0 final series gate.

Depends on: PR264-PR273.

Scope: add the fourth Dash page. Above all tabs render the global portfolio-candidate OOS Return/Risk scatter with the algorithmic winner highlighted. Tabs are exactly `Universe`, `Risk Model`, `Optimization`, `Validation`, and `Final Portfolio`. Required plots include universe funnel and before/after scatter, redundancy/cluster heatmap when reduction occurred, risk-model diagnostics, candidate/efficient-frontier map, OOS cumulative performance, OOS Return/Risk scatter, weight-stability heatmap, final capital weights, risk contributions, and income contributions when available. Every plotted reason/value comes from PR273 decision sections; no browser-side financial recomputation is allowed.

Tasks / Acceptance: the single authoritative `PR274` checklist in the normative specification, including the deterministic several-hundred-ISIN journey and four-page two-project gate.

Parallelization: final integration PR. Agent A owns Dash Multivariate page/figures/CSS; Agent B owns callbacks/view-model/contract fixtures/end-to-end tests/docs. The PR273 section contract is immutable during parallel work.

Security: browser receives only authorized decision sections; plots contain no credentials/storage paths.

Determinism: stable decision revisions map to stable Plotly trace inputs and one highlighted winner.

Idempotency: chart/tab interactions are read-only; repeated automatic-run submission reuses the same logical run when inputs are unchanged.

Rollback: revert Multivariate Dash page/end-to-end additions; PR264-PR273 remain independently testable.

## Series Completion Gate

The series is complete only after PR264-PR274 merge in the dependency graph above and one clean `main` evidence run proves all of the following:

- exactly four Dash workflow pages exist in the required order and all are project-scoped;
- Univariate shows the always-visible Return/Volatility universe scatter and Pareto frontier with selected/rejected/data-quality states;
- Bivariate shows the always-visible Return/median-dependence universe scatter with the exact metric selector and all nine detailed views;
- an automatic `return_risk` run requires no manual ISIN picking or manual optimizer-method selection after the pinned input universe is supplied;
- production optimization does not enumerate all ISIN combinations or a several-hundred-dimensional weight grid;
- every important optimizer decision has a persisted DecisionArtifact and at least one Multivariate visualization or explicit `not_applicable` reason;
- winner selection uses out-of-sample walk-forward evidence, not maximum in-sample return or a single best split;
- final portfolio output includes exact weights, OOS metrics, final full-history metrics, risk contributions, and income contributions when evidence exists;
- two-project tests prove no selection, decision, candidate, winner, figure, or artifact can cross project boundaries;
- Dash imports no provider client, database repository, table I/O, lake path, or analytical formula module outside the typed gateway/presentation boundary;
- all focused Python tests, Dash tests, architecture tests, OpenAPI/contract checks, Docker Dash build, Compose profile validation, and `uv run portfell-quality pr` pass from one Git SHA.

## Historical Backlog Archive

The full pre-refocus backlog, including completed history and unrelated previously active/pushed records, is preserved verbatim at `docs/backlog/archive/BACKLOG-2026-08-16-before-dash-optimizer.md`.

The superseded planning contract that allowed only three Dash pages is preserved verbatim at `docs/backlog/archive/plotly-dash-three-page-research-ui-v1.md`.

Those archive files are historical evidence only. They must not be used by agents as current implementation instructions when they conflict with this file or the current normative Dash/optimizer specification.