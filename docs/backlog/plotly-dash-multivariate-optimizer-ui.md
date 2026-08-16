# Plotly Dash And Multivariate Portfolio Optimizer PR Stack

Status: normative planning contract for `BACKLOG.md` PR264-PR275.

This document is the executable work order for the replacement Plotly Dash UI and the Multivariate Statistics portfolio optimizer. It is the only active implementation authority for PR264-PR275. Historical plans under `docs/backlog/archive/` are evidence only and may contain superseded terminology.

## Product invariant: Multivariate Statistics is the optimizer

There is no workflow step, page, route, or user concept called `Optimizer` after Multivariate Statistics. The browser workflow is exactly:

```text
Metadata Builder
    -> Univariate Statistics
    -> Bivariate Statistics
    -> Multivariate Statistics
       = automatic portfolio optimization
       + decision audit
       + final portfolio
```

Internally, Multivariate Statistics may use selector, risk-model, solver, walk-forward, ranking, and decision-artifact modules. Those are implementation components of one Multivariate Statistics run, not additional workflow stages.

The user starts one Multivariate Statistics run, supplies one optimization objective plus optional portfolio constraints, watches one Multivariate progress surface, and receives one automatically selected portfolio plus the complete visual decision audit. The user does not manually choose individual ISINs or one optimizer method after the run starts.

## Calculation-control invariant

Each statistics page has one page-owned calculation control above its result tabs and plots. The control is always present and uses the same presentation contract:

`StatisticsRunControl(stage_id, status, phase, completed_units, total_units, percent, message, can_start, failure_reason)`.

Statuses are exactly `idle`, `starting`, `running`, `complete`, `failed`, and `stale`. The displayed percent is server-owned progress normalized to `[0,100]`; unavailable progress is rendered as indeterminate rather than invented `0`. Duplicate activation may not create a second logical run.

Exact primary buttons are:

- Univariate Statistics: `Compute univariate statistics`
- Bivariate Statistics: `Compute bivariate statistics`
- Multivariate Statistics: `Optimize portfolio`

Each control contains, in order: page label, progress bar, status/phase text, failure text when applicable, and primary button. A completed result remains visible while a new run is starting/running only when it belongs to the same project and the UI labels it as previous/stale evidence; cross-project results are cleared before the replacement request.

## Multivariate optimization objectives

Multivariate Statistics contains an `Optimization objective` selector immediately before its calculation control. Version 1 supports exactly these three objective IDs and labels:

1. `return_risk` — `Return / Risk`
2. `return_drawdown` — `Return / Drawdown`
3. `minimum_risk` — `Minimum Risk`

Default is `return_risk`. The selected objective is part of the immutable Multivariate run identity and every decision artifact. Changing the selector after a completed run marks the visible result stale but does not start a run until `Optimize portfolio` is activated.

Winner ranking is objective-specific and out-of-sample only:

- `return_risk`: maximize median OOS Sharpe; ties: higher median OOS Sortino, lower absolute whole-period OOS maximum drawdown, lower OOS CVaR, lower median turnover, lexical configuration ID.
- `return_drawdown`: maximize OOS Calmar (`annualized OOS return / abs(whole-period OOS maximum drawdown)`); ties: higher annualized OOS return, lower absolute OOS maximum drawdown, lower OOS CVaR, lower median turnover, lexical configuration ID. Zero drawdown yields a typed unavailable Calmar and cannot silently become infinity.
- `minimum_risk`: minimize OOS annualized volatility; ties: lower absolute OOS maximum drawdown, lower OOS CVaR, higher annualized OOS return, lower median turnover, lexical configuration ID.

No objective ranks by maximum in-sample return or by one best split.

## Visualization invariant

Every important algorithmic decision must be represented by an immutable `DecisionArtifact` and must have at least one visible Multivariate plot/table/explanation. UI code may not reconstruct a reason from final weights or independently rerun financial calculations. A stage that does not apply emits `not_applicable` with an explicit reason.

Univariate Statistics has one always-visible global Return/Risk universe plot above its tabs. Bivariate Statistics has one always-visible global Return/Diversification universe plot above its tabs. Multivariate Statistics has one always-visible portfolio-candidate plot above its tabs plus decision-stage plots inside its tabs.

## Temporary and final routing/runtime

PR264-PR274 build the replacement UI safely beside the current React UI. During those implementation PRs the Dash base path is `/dash/`; this coexistence is temporary migration scaffolding only.

PR275 performs the mandatory production cutover. After PR275:

- `apps/web/**` and the React/TypeScript production UI are deleted;
- no production Node UI container exists;
- Dash becomes the only browser UI;
- canonical browser routes are `/projects/<project_slug>/<page-suffix>` without `/dash`;
- REST routes remain under their existing `/api` namespace;
- one Python `app` container serves FastAPI + mounted Dash;
- the final Compose application services are exactly `postgres`, `app`, and `project-bootstrap-worker`.

The final `app` container may contain API/database/provider secrets because it also hosts FastAPI, but the `portfell.dash_ui` package must still receive only its typed gateway and must not import or receive database/provider/storage authority directly.

## Frozen route suffix registry

Workflow IDs and suffixes are exactly:

- `metadata_builder` -> `/metadata-builder`
- `univariate_statistics` -> `/univariate-statistics`
- `bivariate_statistics` -> `/bivariate-statistics`
- `multivariate_statistics` -> `/multivariate-statistics`

PR264 freezes suffixes and component IDs. PR275 changes only the deployment base prefix from `/dash/projects/<slug>` to `/projects/<slug>`.

## Parallel execution contract

Two weak agents may work in parallel only from the exact same predecessor merge commit. Parallel branches never stack on each other. Shared contracts are frozen by a predecessor before parallel branches start.

```text
PR264 foundation
  |
  +----------------------+----------------------+
  |                                             |
PR265 shell/navigation                         PR266 metadata
  |                                             |
  +----------------------+----------------------+
                         |
                     merge both
                         |
  +----------------------+----------------------+
  |                                             |
PR267 univariate + universe plot + control     PR268 bivariate + universe plot + control
  |                                             |
  +----------------------+----------------------+
                         |
                     merge both
                         |
                      PR269
       Multivariate decision/objective contracts
                         |
  +----------------------+----------------------+
  |                                             |
PR270 automatic universe selector             PR271 production solver/candidate set
  |                                             |
  +----------------------+----------------------+
                         |
                     merge both
                         |
  +----------------------+----------------------+
  |                                             |
PR272 Multivariate run orchestration          PR273 Multivariate decision persistence/API
+ OOS objective winner                          |
  |                                             |
  +----------------------+----------------------+
                         |
                     merge both
                         |
                      PR274
 Multivariate Dash optimizer page + decision audit
                         |
                         v
                      PR275
 React deletion + production Dash/FastAPI/Docker cutover
```

For every PR below, `Tasks / Acceptance` is the only checklist. Checking a box means both implementation and its named verification evidence exist.

---

## PR264 — Plotly Dash Runtime, Shared Run-Control, And Four-Page Foundation

Git metadata:

- Branch: `feat/dash-runtime-foundation`
- Base: `main`
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested title: `feat(dash): add four-page runtime and run-control foundation`
- Required squash subject: `feat(dash): add four-page runtime and run-control foundation`
- Merge method: squash only
- Parallel wave: foundation; two-agent hand-off inside one PR
- Depends on: already-merged hosted page-view/lazy-section/workflow/run/command contracts

Business outcome: one runnable temporary Dash/FastAPI sidecar with frozen four-page suffixes, component namespaces, typed gateway, shared Plotly conventions, one statistics-run-control presentation contract, deterministic fixtures, and a documented final-cutover target.

Owned paths:

- Agent A: dependency lock changes, temporary `apps/dash/Dockerfile`, temporary Dash service/profile in `compose.yaml`, `src/portfell/dash_ui/app.py`, `src/portfell/dash_ui/runtime.py`.
- Agent B: `src/portfell/dash_ui/contracts.py`, `ids.py`, `plot_contracts.py`, `run_control.py`, `testing.py`, foundation tests.
- Hand-off: Agent B commits/finalizes contracts, IDs, plot contracts, and run-control contract first. Agent A may import but not edit them.
- Forbidden: `apps/web/**`, optimizer math, risk-model formulas, PostgreSQL repositories, provider clients, migrations.

Tasks / Acceptance — identical checklist:

- [ ] Add explicit Dash/FastAPI-compatible dependencies and lock once; no Celery, Redis, DiskCache, pandas, second job queue, or second durable state authority. Lock/check/sync and repository Python-version tests pass.
- [ ] Create importable `portfell.dash_ui` with temporary `/dash/` base path, Dash Pages enabled, strict callback validation, no import-time database/provider/calculation side effect, and base-prefix configuration restricted to `/dash/` during PR264-PR274 or `/` at PR275 cutover.
- [ ] Freeze exactly four workflow IDs and four route suffixes listed above. Tests fail on a missing, duplicate, reordered, or fifth workflow page.
- [ ] Freeze component namespaces for shell, Metadata, Univariate, Bivariate, Multivariate, shared run control, shared universe plots, optimizer-candidate plot, objective selector, decision stages, and typed error regions.
- [ ] Define `StatisticsRunControl` and one pure adapter per run-contract shape so Uni/Bi/Multivariate can render `idle|starting|running|complete|failed|stale`, phase, progress, message, and failure without inventing progress. Add fixed tests for zero-total, partial, failed, complete, stale, and indeterminate progress.
- [ ] Define `DashResearchGateway` methods for project context, four page views, run start/status, lazy sections, selection settings, Multivariate objective/settings, and decision sections. Every project-scoped method requires project identity and accepts no raw SQL/filesystem/provider/repository/lake object.
- [ ] Define presentation-only contracts for `UniversePoint`, `PairwiseUniversePoint`, `PortfolioCandidatePoint`, `DecisionStageSummary`, and section availability. No financial formula implementation enters Dash contracts.
- [ ] Add fixed two-project fixtures covering all three statistics run-control statuses, Univariate 12-listing universe, Bivariate pairs, Multivariate 400-input/<=250-selected universe, all three objective IDs, candidates, winner, and all decision sections.
- [ ] Add architecture tests that fail if `portfell.dash_ui` imports PostgreSQL adapters, `psycopg`, provider/EODHD modules, table/lake readers, risk/portfolio formula modules, or local shared-store authority. Temporary Dash container receives no DB/provider secret.
- [ ] Temporary Dash Docker image/profile, health check, focused tests, Ruff, Pyright, lock check, Compose validation, architecture tests, and `uv run portfell-quality pr` pass from one SHA; docs state that PR275 will remove the temporary Dash container and React web container in favor of one `app` container.

Security: Dash is not authorization authority.

Determinism: fixed route/ID/run-control contracts and fixtures define one runtime shape.

Idempotency: startup/health/reads are non-mutating; duplicate start commands rely on server logical-run identity.

Rollback: remove temporary Dash package/image/profile/dependencies; no persistent migration exists.

---

## PR265 — Dash Shell And Four-Stage Project Navigation

Git metadata:

- Branch: `feat/dash-research-shell`
- Base: exact PR264 merge commit
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested title: `feat(dash): add four-stage research shell`
- Required squash subject: `feat(dash): add four-stage research shell`
- Merge method: squash only
- Parallel wave: 1 / Agent A; parallel with PR266
- Depends on: PR264

Owned paths: `shell.py`, `navigation.py`, shell-only CSS, shell tests/docs. Metadata page/callback files are forbidden.

Tasks / Acceptance — identical checklist:

- [ ] Render one Portfell shell with header, project selector, process overview, left workflow sidebar, and page region using local CSS only.
- [ ] Sidebar contains exactly four links in order: Metadata Builder, Univariate Statistics, Bivariate Statistics, Multivariate Statistics. No separate Optimizer link, badge, pseudo-stage, or route exists.
- [ ] During PR265-PR274, canonical temporary URLs are `/dash/projects/<slug>/<suffix>`; route construction uses frozen suffixes and one base-prefix function so PR275 can remove `/dash` without page rewrites.
- [ ] `/dash/` with current project redirects to earliest navigable stage; without current project renders Metadata Builder no-project state without a write.
- [ ] Selecting another project emits exactly one existing select-project command, reloads target workflow, and never paints old-project counts/status/results after URL change.
- [ ] Unknown/deleted/unauthorized project renders typed unavailable state and never falls back to another project.
- [ ] Process overview shows exactly Metadata, Univariate, Bivariate, and Multivariate stage status; Multivariate status is the optimization run status, not a separate optimizer status.
- [ ] Desktop and 390px mobile retain visible focus and keyboard navigation without custom browser JS.
- [ ] Browser persistent storage contains no credentials, result matrices, financial series, decision artifacts, or optimizer weights.
- [ ] Two-project shell/navigation tests plus Ruff, Pyright, Dash Docker build, and quality gate pass.

Security: URL/project state never grants access.

Determinism: slug + workflow projection determine navigation.

Idempotency: same-project selection emits no command.

Rollback: revert shell/navigation assets/tests/docs.

---

## PR266 — Dash Metadata Builder

Git metadata:

- Branch: `feat/dash-metadata-builder`
- Base: same exact PR264 merge commit as PR265
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested title: `feat(dash): add Metadata Builder page`
- Required squash subject: `feat(dash): add Metadata Builder page`
- Merge method: squash only
- Parallel wave: 1 / Agent B; parallel with PR265
- Depends on: PR264

Owned paths: Metadata page, callbacks/view-model, Metadata-only CSS, tests/docs. Shell files forbidden except registration import.

Tasks / Acceptance — identical checklist:

- [ ] Render one combined metadata panel containing metadata-download progress/status/fetch action followed by the Metadata Builder form.
- [ ] Form contains exactly Exchange, Instrument type, Country, Currency, and `Name contains`; options use server counts and deterministic sort.
- [ ] Metadata fetch invokes existing command once per logical activation, disables while active, restores persisted progress, and never receives provider key.
- [ ] Project creation requires metadata-ready and at least one criterion, submits exactly five values, shows selected unique-ISIN count, and navigates to temporary Dash project URL.
- [ ] Initial-fill states map explicitly to text/progress/retry with no browser inference of completion.
- [ ] Reload restores criteria/current project/initial-fill state and starts no ingestion implicitly.
- [ ] Rapid project switch cancels obsolete reads and cannot paint old criteria/progress.
- [ ] Duplicate callback delivery cannot create duplicate logical metadata/project commands.
- [ ] Two-project/failure fixtures cover disabled/enabled states and exact command counts.
- [ ] Focused tests, Ruff, Pyright, Dash Docker build, and quality gate pass.

Security: provider credential stays server-side.

Determinism: same page-view revision/options produce same UI.

Idempotency: reads are non-mutating; commands retain server idempotency.

Rollback: revert Metadata Dash files.

---

## PR267 — Dash Univariate Statistics, Calculation Control, And Global Return-Risk Plot

Git metadata:

- Branch: `feat/dash-univariate-universe`
- Base: exact `main` commit after PR265 and PR266 merge
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested title: `feat(dash): add Univariate calculation and return-risk universe`
- Required squash subject: `feat(dash): add Univariate calculation and return-risk universe`
- Merge method: squash only
- Parallel wave: 2 / Agent A; parallel with PR268
- Depends on: PR264-PR266

Owned paths: Univariate page/figures/callbacks/view-model/tests/docs and Univariate-only CSS. Bivariate files forbidden.

Tasks / Acceptance — identical checklist:

- [ ] Render the shared calculation control above the universe plot with exact button `Compute univariate statistics`, progress bar, status/phase text, and typed failure message. `idle|starting|running|complete|failed|stale` fixtures map exactly through PR264 `StatisticsRunControl`.
- [ ] Button is disabled while `starting|running`, unavailable when upstream data is not ready with explicit reason, and a logical double-click/duplicate callback creates at most one run ID. Complete/failure status is restored after reload.
- [ ] Preserve dividend-frequency selection, Duration thresholds, metric tabs, saved ranges/labels, revision-bound result paging, and current metric descriptions without recalculating financial values in Dash.
- [ ] Add always-visible `Return / Risk Universe` Plotly scatter above tabs when at least one authorized result exists; while running with no result yet, its region stays visible with explicit waiting state.
- [ ] X=`annualized_volatility`, Y=`annualized_geometric_return`; one point is full listing identity `(isin, exchange, code)` and duplicate ISIN listings remain distinguishable.
- [ ] Separate presentation states are `selected`, `rejected_by_selection`, `data_quality_excluded`; rejected points remain visible by default and `Show rejected` hides presentation traces only.
- [ ] Hover contains listing identity, return, volatility, Sharpe, Sortino, Expected Shortfall, maximum drawdown, distribution frequency, annual dividend yield, and observation count; unavailable is never rendered as zero.
- [ ] Draw deterministic maximize-return/minimize-volatility non-dominated frontier over data-quality-eligible points. Frontier is visual evidence only and cannot mutate persisted selection.
- [ ] Project switch clears/aborts old run/progress/results/frontier before new project data paints; tests cover equal ties, empty/unavailable values, failed run, stale prior result, and two-project isolation.
- [ ] Focused run-control/callback/figure tests, Ruff, Pyright, Dash Docker build, and quality gate pass.

Security: chart/run status consume authorized project data only.

Determinism: stable listing sort + frontier rule + run adapter produce stable display inputs.

Idempotency: viewing/hovering/toggling is read-only; duplicate start converges on one logical run.

Rollback: revert Univariate Dash files.

---

## PR268 — Dash Bivariate Statistics, Calculation Control, And Global Return-Diversification Plot

Git metadata:

- Branch: `feat/dash-bivariate-universe`
- Base: same exact post-PR265/PR266 `main` commit as PR267
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested title: `feat(dash): add Bivariate calculation and diversification universe`
- Required squash subject: `feat(dash): add Bivariate calculation and diversification universe`
- Merge method: squash only
- Parallel wave: 2 / Agent B; parallel with PR267
- Depends on: PR264-PR266

Owned paths: Bivariate page/figures/callbacks/view-model/tests/docs and Bivariate-only CSS. Univariate implementation files forbidden.

Tasks / Acceptance — identical checklist:

- [ ] Render shared calculation control above the universe plot with exact button `Compute bivariate statistics`, progress bar, status/phase text, and failure message; the run consumes the persisted upstream Univariate selection/revision only.
- [ ] Button is disabled while `starting|running` and while no valid Univariate selection exists; duplicate activation yields at most one logical Bivariate run; reload restores complete/failed/running status and progress.
- [ ] Preserve exactly nine detail views: Covariance, Pearson, Spearman, Downside, Tail Dependence, Co-exceedance, Rolling-Correlation, Drawdown Overlap, Tail-Risk Scatter.
- [ ] Detailed pair matrices use Plotly heatmaps from authorized sections; Tail-Risk Scatter uses WebGL above the fixed tested threshold.
- [ ] Add always-visible `Return / Diversification Universe` scatter above tabs after results exist; while a run is active without results, keep explicit waiting region visible.
- [ ] One point is one selected listing; Y is pinned upstream `annualized_geometric_return`; X defaults to median Pearson correlation to all other selected listings, excluding self/unavailable values.
- [ ] X selector has exactly Median Pearson, Median Spearman, Median Downside Correlation, Median Lower-Tail Dependence, Median Co-exceedance, Median Drawdown Overlap. Switching it is presentation-only.
- [ ] Hover contains listing identity, return, selected median metric, usable-pair count, and other five medians when available; pair coverage shows start/end and min/average/max shared observations.
- [ ] Deterministic 201-listing/20,100-pair fixture renders all nine views and universe plot without omission; stale/oversize/unavailable/failure and two-project switch tests prove no old-project pair values paint.
- [ ] Focused run-control/callback/figure tests, Ruff, Pyright, Dash Docker build, and quality gate pass.

Security: section IDs do not authorize access.

Determinism: pair revision + median rule + stable order determine display.

Idempotency: reads/metric switches are non-mutating; duplicate start converges on one run.

Rollback: revert Bivariate Dash files.

---

## PR269 — Multivariate Statistics Decision, Objective, And Run Contract Foundation

Git metadata:

- Branch: `feat/multivariate-optimizer-contracts`
- Base: exact `main` commit after PR267 and PR268 merge
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested title: `feat(multivariate): define optimizer objective and decision contracts`
- Required squash subject: `feat(multivariate): define optimizer objective and decision contracts`
- Merge method: squash only
- Parallel wave: foundation; two-agent hand-off inside one PR
- Depends on: PR267, PR268, existing Multivariate/risk-model/scorecard contracts

Business outcome: freeze one Multivariate Statistics run contract in which objective selection, automatic portfolio construction, progress, and decision evidence are one versioned analytical lifecycle.

Owned paths:

- Agent A: Multivariate optimizer settings, objective/ranking registry, decision contracts/reason enums/IDs.
- Agent B: serialization/property tests, deterministic fixtures, run-progress fixtures, docs.
- Forbidden: selector/solver/orchestrator implementation, UI files, persistence/provider adapters.

Frozen decision stage IDs:

1. `input_eligibility`
2. `univariate_pareto`
3. `bivariate_redundancy`
4. `risk_model_candidates`
5. `portfolio_candidates`
6. `walk_forward_validation`
7. `winner_selection`
8. `final_portfolio`

Tasks / Acceptance — identical checklist:

- [ ] Define `MultivariateOptimizationSettings` with required `objective` exactly one of `return_risk|return_drawdown|minimum_risk`, optional allowed distribution frequencies inherited from pinned Univariate selection, optional `max_weight|min_weight|max_holdings`, transaction-cost rate, and no manual ISIN or single-method selector.
- [ ] Freeze objective labels, default `return_risk`, primary metric and exact tie-break order as specified at top of this document. Objective registry is pure/versioned and tests reject unknown IDs.
- [ ] Define one Multivariate run identity over project, pinned Bivariate revision, objective, settings/profile/algorithm versions. Same inputs/settings yield same logical run; objective change yields different run.
- [ ] Define Multivariate progress phases exactly `select_universe`, `estimate_risk_models`, `build_candidates`, `walk_forward`, `select_winner`, `final_refit`, `publish_decisions`; phase maps into PR264 `StatisticsRunControl` without UI-specific math.
- [ ] Define immutable `DecisionArtifact` with Multivariate run ID, objective, pinned input revisions, stage, candidate/selected/rejected IDs, metrics, status, reason, and algorithm/profile versions.
- [ ] Define `DecisionCandidate`, `DecisionRejection`, and frozen reason codes including data/history/distribution/Pareto/redundancy/risk-model/solver/walk-forward/OOS/not-applicable cases.
- [ ] Define idempotent `DecisionSink`; same ID+canonical content no-op, same ID+different content conflict.
- [ ] Decision IDs are content-addressed over objective, stage, pinned revisions, settings version, ordered candidates and outcome; worker/dictionary order cannot change identity.
- [ ] Add deterministic fixtures for all three objectives, all seven optimizer methods, three risk-model configurations, five walk-forward splits, one winner per objective, final weights/risk/income contributions, and all progress phases; serialization rejects NaN/Inf/secrets/paths/unbounded objects.
- [ ] Focused contract/property/progress tests, Ruff, Pyright, architecture checks, and quality gate pass before PR270/PR271 branch.

Security: artifacts contain analytical evidence only.

Determinism: objective registry + canonical serialization define run/decision identity.

Idempotency: identical run/decision writes converge; conflict fails closed.

Rollback: remove new Multivariate optimizer contracts without changing upstream statistics.

---

## PR270 — Multivariate Automatic Universe Selector From Uni/Bivariate Evidence

Git metadata:

- Branch: `feat/multivariate-universe-selector`
- Base: exact PR269 merge commit
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested title: `feat(multivariate): add automatic optimizer universe selection`
- Required squash subject: `feat(multivariate): add automatic optimizer universe selection`
- Merge method: squash only
- Parallel wave: 3 / Agent A; parallel with PR271
- Depends on: PR269

Owned paths: selector module, selector clustering/ranking helpers, selector tests/fixtures/docs. Solver modules forbidden.

Algorithm contract:

1. Start with exact pinned Bivariate input listing set; remove only, never add.
2. Apply hard data/history/distribution eligibility.
3. Perform deterministic Univariate non-dominated sorting: maximize annualized geometric return, Sharpe, Sortino; minimize annualized volatility, Expected Shortfall, absolute maximum drawdown. Missing required metric is ineligible, never zero.
4. Keep Pareto rank 1; extend rank-by-rank only if needed for minimum feasible portfolio size.
5. If survivors `<=250`, Bivariate redundancy stage is `not_applicable` and membership is unchanged.
6. If survivors `>250`, hierarchical clustering on pinned Pearson matrix cuts to exactly 250 clusters; select one representative by lower Pareto rank, higher Sortino, higher annualized geometric return, lower Expected Shortfall, lower volatility, lexical full listing identity. Tail/downside/drawdown evidence is recorded but does not secretly change tie-breaks.

Tasks / Acceptance — identical checklist:

- [ ] Implement exactly the six-step contract as pure Multivariate selector returning ordered listing identities plus decision evidence for eligibility, Pareto, and redundancy.
- [ ] Hard eligibility emits explicit reason per failed rule; missing values are unavailable, not zero.
- [ ] Pareto tests cover dominated, non-dominated, exact tie, missing, mixed distribution-frequency cases.
- [ ] Selector preserves full listing identity and never adds outside pinned Bivariate membership.
- [ ] `<=250` fixture emits redundancy `not_applicable` with unchanged membership.
- [ ] `>250` fixture produces exactly 250 deterministic representatives with frozen tie-break sequence.
- [ ] Removed cluster member records representative ID and available Pearson/Downside/Tail/Co-exceedance/Drawdown-Overlap evidence.
- [ ] 400-listing fixture uses no subset enumeration and produces identical membership/decision IDs under reversed order and worker-count changes.
- [ ] Property tests prove selected set is feasible, unique, subset of input, and `<=250`.
- [ ] Focused selector tests, Ruff, Pyright, and quality gate pass.

Security: selector sees only authorized pinned inputs.

Determinism: pinned revisions + frozen ranking/clustering determine membership.

Idempotency: pure selector repeats exactly.

Rollback: remove selector module; upstream data unchanged.

---

## PR271 — Multivariate Solver-Backed Portfolio Candidate Set

Git metadata:

- Branch: `feat/multivariate-production-solvers`
- Base: same exact PR269 merge commit as PR270
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested title: `feat(multivariate): add solver-backed portfolio candidates`
- Required squash subject: `feat(multivariate): add solver-backed portfolio candidates`
- Merge method: squash only
- Parallel wave: 3 / Agent B; parallel with PR270
- Depends on: PR269

Candidate methods are exactly `equal_weight`, `minimum_variance`, `maximum_sharpe`, `maximum_diversification`, `equal_risk_contribution`, `hierarchical_risk_parity`, `minimum_cvar`.

Risk-model configurations are exactly `sample`, `ledoit_wolf`, `ewma`; Sample is diagnostic baseline. Exhaustive ISIN-subset permutation and several-hundred-dimensional weight-grid enumeration are forbidden in production.

Tasks / Acceptance — identical checklist:

- [ ] Add production numerical Maximum Sharpe solver with long-only capped-simplex constraints, explicit risk-free rate, deterministic initialization/tolerances, diagnostics, and no weight-grid enumeration.
- [ ] Add production Maximum Diversification solver with same constraint boundary/diagnostics and no grid enumeration.
- [ ] Reuse existing Minimum Variance, ERC, HRP, Minimum CVaR through one candidate-builder interface; do not duplicate formulas.
- [ ] Equal Weight is explicit baseline and never silently substitutes for failed method.
- [ ] Candidate builder returns weights and existing portfolio metrics using existing core functions only.
- [ ] Expected-return map is fitted on training-window daily log returns using existing annualization semantics and is re-estimated inside every walk-forward training split only.
- [ ] Solver failure/non-convergence emits typed unavailable candidate and frozen reason; no plausible fallback under failed method name.
- [ ] Tiny 2-4 asset numerical tests compare objective against exact bounded brute-force test baselines; large-universe tests prove production never calls exhaustive candidate-grid code.
- [ ] Reversed input order maps to same listing weights within named tolerance; all weights finite and satisfy bounds/sum.
- [ ] Focused numerical tests, Ruff, Pyright, and quality gate pass.

Security: numerical code has no tenant/provider/storage authority.

Determinism: fixed solver settings and stable identities.

Idempotency: pure solver calls mutate nothing.

Rollback: remove new adapters without changing existing methods.

---

## PR272 — Multivariate Statistics Run Orchestration And OOS Objective Winner

Git metadata:

- Branch: `feat/multivariate-auto-orchestrator`
- Base: exact `main` commit after PR270 and PR271 merge
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested title: `feat(multivariate): optimize portfolio by selected OOS objective`
- Required squash subject: `feat(multivariate): optimize portfolio by selected OOS objective`
- Merge method: squash only
- Parallel wave: 4 / Agent A; parallel with PR273
- Depends on: PR269-PR271 and existing walk-forward/scorecard infrastructure

Business outcome: the existing Multivariate Statistics lifecycle becomes the automatic portfolio optimizer. There is no separate optimizer run type exposed to the browser.

Owned paths: Multivariate run orchestration, bounded configuration registry, objective ranking, final refit, progress publication, orchestrator tests. Persistence/read API files forbidden except `DecisionSink` calls.

Tasks / Acceptance — identical checklist:

- [ ] One project-scoped `start Multivariate Statistics` command requires pinned Bivariate run/revision plus `MultivariateOptimizationSettings`; it returns one Multivariate run ID and never creates a second browser-visible optimizer lifecycle.
- [ ] Publish PR269 phases and monotonically non-decreasing completed/total units so the Multivariate page can display exact progress/status; failed phase persists failure reason and retry with identical logical inputs reuses/restarts according to existing run policy without duplicate winners.
- [ ] Run PR270 automatic selector before model construction and publish eligibility/Pareto/redundancy decisions through `DecisionSink`.
- [ ] Build bounded configurations only: eligible risk models `ledoit_wolf|ewma`, Sample baseline, seven methods, training windows `252|504|756` when supported. Record configuration count; unrestricted product/permutation dimensions fail a guard test.
- [ ] Every walk-forward split fits risk model/expected returns/weights on training data only and evaluates test period after configured transaction cost; no future leakage.
- [ ] Publish risk-model, portfolio-candidate, and validation decision artifacts for every feasible/blocked configuration with exact reasons/metrics.
- [ ] Rank completed OOS configurations using the selected objective's frozen primary/tie-break policy and choose exactly one winner. Equal Weight wins only when all non-baseline production candidates are blocked, with explicit reason.
- [ ] Refit winner on full selected history and compute final weights, full-history metrics, risk contributions, available income contributions; publish winner/final decision artifacts.
- [ ] Objective changes create distinct Multivariate run IDs and can choose different winners from the same candidate evidence; deterministic fixtures prove `return_risk`, `return_drawdown`, and `minimum_risk` ranking exactly as specified.
- [ ] Focused orchestration/progress/objective/walk-forward tests, Ruff, Pyright, and quality gate pass.

Security: project/run authorization precedes data resolution.

Determinism: objective + bounded registry + split/ranking policy determine winner.

Idempotency: same input/objective/settings converge on one logical Multivariate run/winner.

Rollback: restore previous Multivariate orchestration; upstream Uni/Bi unchanged.

---

## PR273 — Multivariate Decision Artifact Persistence And Lazy Read Sections

Git metadata:

- Branch: `feat/multivariate-decision-sections`
- Base: same exact post-PR270/PR271 `main` commit as PR272
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested title: `feat(multivariate): persist and expose optimizer decision sections`
- Required squash subject: `feat(multivariate): persist and expose optimizer decision sections`
- Merge method: squash only
- Parallel wave: 4 / Agent B; parallel with PR272
- Depends on: PR269-PR271

Section keys are exactly `decision_summary`, `universe`, `risk_models`, `portfolio_candidates`, `validation`, `final_portfolio`.

Tasks / Acceptance — identical checklist:

- [ ] Persist canonical DecisionArtifact bytes through existing content-addressed authority; do not create second filesystem/browser authority.
- [ ] Map Multivariate run -> ordered decision IDs under project/user authorization. No separate optimizer-run mapping exists.
- [ ] Same ID/content write is idempotent; same ID/different content fails closed.
- [ ] Extend compact Multivariate page view with run status/progress phase, selected objective/settings revision, decision-stage availability/revisions, winner ID, and counts only.
- [ ] Add authorized lazy reads for exactly six section keys; resolve project and Multivariate run ownership before artifact bytes.
- [ ] Section status is exactly `available|running|failed|stale|not_applicable|too_large`; no silent truncation or zero substitution.
- [ ] Read models expose exact PR274 plot data: universe points/counts/reasons, clusters/pair evidence, risk diagnostics, candidates/OOS metrics, split series, weight histories, winner, final weights, risk contributions, income contributions.
- [ ] GET/read paths invoke no selector, solver, risk model, walk-forward, ranking, or financial recomputation; architecture tests fail on such calls/imports.
- [ ] Two-project tests prove guessed/cross-project Multivariate run/decision IDs expose nothing.
- [ ] API/OpenAPI/contract/restart/idempotency/size tests, Ruff, Pyright, and quality gate pass.

Security: project/Multivariate-run authorization precedes artifact access.

Determinism: canonical bytes + immutable revisions.

Idempotency: reads never mutate; identical writes no-op.

Rollback: remove persistence/read surfaces without changing optimizer math.

---

## PR274 — Dash Multivariate Statistics Optimizer, Calculation Control, Objective Selector, And Decision Audit

Git metadata:

- Branch: `feat/dash-multivariate-optimizer`
- Base: exact `main` commit after PR272 and PR273 merge
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested title: `feat(dash): make Multivariate Statistics the portfolio optimizer`
- Required squash subject: `feat(dash): make Multivariate Statistics the portfolio optimizer`
- Merge method: squash only
- Parallel wave: final feature integration; two-agent ownership inside one PR
- Depends on: PR264-PR273

Owned paths:

- Agent A: Multivariate Dash page, objective control layout, Plotly figure builders, Multivariate-only CSS.
- Agent B: callbacks/view-model, section adapters, deterministic UI fixtures, run-control/objective/E2E tests, page docs.
- Shared boundary: PR269 objective/run contracts and PR273 section contracts are immutable.

Tabs are exactly `Universe`, `Risk Model`, `Optimization`, `Validation`, `Final Portfolio`.

Tasks / Acceptance — identical checklist:

- [ ] Render `Optimization objective` selector with exactly `Return / Risk`, `Return / Drawdown`, `Minimum Risk`, default `Return / Risk`, immediately before the shared Multivariate calculation control. Changing objective marks current result stale and starts no run.
- [ ] Render shared calculation control with exact button `Optimize portfolio`, progress bar, phase/status text, and typed failure reason. It starts the one Multivariate Statistics run using selected objective/settings; disabled during `starting|running` and when Bivariate input is not complete; duplicate activation yields one logical Multivariate run.
- [ ] Progress displays all PR269 Multivariate phases and persists/restores after browser/API restart. A previous result may remain visible only for same project and is visibly labeled stale/previous when objective/input changed.
- [ ] Above tabs render always-visible `Portfolio Candidate Return / Risk` scatter from persisted decision data: X=OOS annualized volatility, Y=OOS annualized return, hover includes method/risk model/window/objective/OOS Sharpe/Sortino/Calmar/CVaR/max drawdown/turnover, algorithmic winner uniquely highlighted.
- [ ] `Universe` renders exact funnel `input -> eligible -> Pareto -> optimizer universe`, Return/Risk before-vs-after scatter, and redundancy cluster heatmap/map when reduction occurred; rejected items show persisted reason/evidence only.
- [ ] `Risk Model` renders candidate availability/observations/condition/stability/parameter evidence and diagnostics plot; winner's model highlighted from persisted winner.
- [ ] `Optimization` renders all feasible/blocked portfolio candidates and Pareto/efficient trade-off view with return, volatility, Sharpe, Sortino, Calmar, CVaR, max drawdown, diversification, holdings, max weight, method/model/window and block reason.
- [ ] `Validation` renders cumulative OOS performance, OOS Return/Risk scatter, and weight-stability heatmap from persisted validation section only. `Final Portfolio` renders capital weights, risk contributions, income contributions when available, final full-history metrics, selected objective, and OOS scorecard side by side.
- [ ] All eight decision stages map to a visible UI region or explicit `not_applicable` reason; static registry test fails on any uncovered stage. No separate Optimizer page, route, button, run status, or navigation item exists anywhere.
- [ ] Deterministic 400-listing three-objective journey reaches <=250 automatic universe without manual ISIN/method choice, selects objective-specific OOS winner, restores progress/results after restart, renders all required plots, proves two-project isolation, and observes no exhaustive subset/weight-grid production call; focused tests, Docker Dash build, Compose, Ruff, Pyright, contracts, and quality gate pass.

Security: browser receives authorized Multivariate sections only.

Determinism: objective/run revision maps to stable traces and winner.

Idempotency: chart/tab interactions read-only; identical start converges on one Multivariate run.

Rollback: revert Multivariate Dash layer; backend remains testable.

---

## PR275 — Production Dash Cutover, React UI Deletion, And Docker Consolidation

Git metadata:

- Branch: `refactor/dash-production-cutover`
- Base: exact PR274 merge commit
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested title: `refactor(ui): replace React with Dash and consolidate runtime`
- Required squash subject: `refactor(ui): replace React with Dash and consolidate runtime`
- Merge method: squash only
- Parallel wave: final cutover; two-agent ownership inside one PR after one frozen cutover manifest
- Depends on: PR264-PR274 complete and green

Business outcome: delete the old production UI and temporary migration topology. Dash becomes the only browser UI and is mounted in the same Python application process as FastAPI. Final Compose contains exactly three long-running services: `postgres`, `app`, `project-bootstrap-worker`.

Target runtime topology:

```text
Browser
  |
  v
app :8000  (single Python image/process boundary)
  |- /api/*                         -> FastAPI REST
  |- /projects/<slug>/metadata-builder
  |- /projects/<slug>/univariate-statistics
  |- /projects/<slug>/bivariate-statistics
  `- /projects/<slug>/multivariate-statistics -> Dash
        |
        +-> typed DashResearchGateway only

app ----------------> postgres
app ----------------> shared analytical storage as required by existing API authority
project-bootstrap-worker -> postgres + shared data + operations provider credential
```

Final Compose service names are exactly `postgres`, `app`, `project-bootstrap-worker`. There is no `web` service and no `dash` service. `app` replaces the old `api` + Node `web` + temporary Dash UI transport boundary while preserving the existing FastAPI REST contract and worker boundary.

Ownership and weak-agent hand-off:

1. Before parallel work, Agent B commits `docs/backlog/dash-cutover-manifest.md` listing every path/service/route/environment variable to keep, rename, or delete. Both agents use this manifest; neither invents additional cutover scope.
2. Agent A owns deletion/migration of browser UI source and browser-test/docs references: `apps/web/**`, React/TypeScript UI package files, React-specific browser tests/config, React-specific UI docs, and stale Node-only production references. Agent A must not edit Compose, Python runtime factory, or Dockerfile.
3. Agent B owns `compose.yaml`, Python hosted runtime mounting, `apps/app/Dockerfile`, removal of temporary `apps/dash/Dockerfile`, health/readiness wiring, port/env compatibility, Docker/Compose tests, and operations docs. Agent B must not edit page implementation files except the one frozen base-prefix registration hook explicitly named in the manifest.
4. Shared root dependency/CI files are assigned one owner each in the manifest before either agent edits them; no file has dual ownership.

Tasks / Acceptance — identical checklist:

- [ ] Freeze and commit the cutover manifest first. It lists old `web`, old `api`, temporary `dash`, final `app`, all four route mappings, external ports, Dockerfiles, Node/React paths, CI jobs, docs, and rollback mapping. Tests validate every listed path/service against repository state.
- [ ] Delete `apps/web/**` completely and delete all production React/TypeScript/Vite/Plotly.js UI entry points, components, CSS, package/lock artifacts that exist only for that UI, React-specific tests, and React-only docs. Repository search finds no production import/reference to React, Vite, TanStack Query, `apps/web`, or the old Node `server.js`.
- [ ] Mount Dash into the production FastAPI ASGI application and change Dash base prefix from temporary `/dash/projects/<slug>` to canonical `/projects/<slug>` without changing the four frozen page suffixes/component behavior. `/dash/*` returns the documented retired-route outcome and never serves a hidden duplicate UI.
- [ ] Create one `apps/app/Dockerfile` from the existing Python API runtime requirements, serving FastAPI + Dash as an unprivileged process. Remove temporary `apps/dash/Dockerfile`; old `apps/api/Dockerfile` is removed or replaced according to manifest so exactly one production Python app image definition remains. Worker uses the same built image with its own command or a manifest-approved identical base without duplicating UI runtime.
- [ ] Rewrite Compose to exactly `postgres`, `app`, `project-bootstrap-worker`; remove `web`, temporary `dash`, `NODE_ENV`, `PORTFELL_API_BASE_URL`, Node health command, and all web-only watches. `app` depends on healthy PostgreSQL/worker as required by current authority and has the existing required database/shared-data/API secrets; `portfell.dash_ui` still receives only typed gateway injection.
- [ ] Preserve browser compatibility at `${PORTFELL_WEB_PORT:-333}` and REST compatibility at `${PORTFELL_API_PORT:-8000}` by mapping both host ports to the one `app` listener during this cutover unless a checked-in compatibility test proves one mapping is unused and the manifest explicitly removes it. Browser API calls are same-origin where applicable and no reverse Node proxy remains.
- [ ] Replace React/Node browser regression coverage with deterministic Dash browser/E2E coverage for Metadata -> Univariate compute/progress/status -> Bivariate compute/progress/status -> Multivariate objective selection/optimize/progress/status/decision audit, including reload, failure/retry, and two-project isolation. No required merge gate references deleted `apps/web` scripts.
- [ ] Update `README.md`, `ARCHITECTURE.md`, UI docs, deployment/runbook, `GATES.md`, CI workflows, developer commands, Compose examples, and environment-variable inventory to one final topology. Current-state docs must state exactly: Multivariate Statistics is the optimizer; no separate optimizer stage/page exists.
- [ ] Clean checkout evidence proves no Node runtime is required to build or run the production stack: Python dependency sync, Python/Dash tests, API/OpenAPI contracts, architecture tests, `docker compose config`, `docker compose build`, three-service startup/health, four-page browser journey, API smoke tests, worker job, restart/restore, and `uv run portfell-quality pr` all pass from one SHA.
- [ ] Rollback rehearsal from the final three-service stack to the last PR274 coexistence SHA is documented and tested with no database migration/data rewrite; after rollback React and temporary Dash coexistence run as before, and after forward reapply final `app` topology restores the same project/run/decision data.

Security: process consolidation must not widen the `dash_ui` dependency graph. The shared `app` process holds API secrets, but executable architecture/injection tests prove Dash modules cannot import or obtain raw database/provider/storage adapters. Existing RLS/project/run authorization remains the only data authority.

Determinism: frozen cutover manifest + route registry + one image/topology determine runtime shape.

Idempotency: repeated build/start/restart/cutover smoke tests do not duplicate projects/runs/decisions or mutate analytical artifacts outside explicit commands.

Rollback: checkout last PR274 SHA and start its old Compose topology; no schema/data migration is introduced by PR275.

---

## Series completion checklist

The series is finished only when PR264-PR275 are merged and one clean final `main` SHA proves:

- exactly four workflow pages exist: Metadata Builder, Univariate Statistics, Bivariate Statistics, Multivariate Statistics;
- Multivariate Statistics is consistently the only portfolio optimizer page/run; there is no separate Optimizer workflow item, page, route, run-control surface, or post-Multivariate stage;
- Uni, Bi, and Multivariate each have one explicit calculation button, progress bar, phase/status text, persisted failure/complete state, duplicate-start protection, and project-switch isolation;
- Multivariate has the required objective selector with exactly three objective IDs and objective-specific OOS winner ranking;
- Univariate has always-visible Return/Volatility universe plot and frontier; Bivariate has always-visible Return/median-dependence plot plus six-metric selector; Multivariate visualizes every important decision stage and final portfolio;
- automatic universe selection requires no manual per-ISIN picking after run start and returns <=250 optimizer listings without exhaustive subset enumeration;
- production portfolio weights are solver-backed and never use a several-hundred-dimensional exhaustive grid;
- every important Multivariate optimizer decision is persisted as a decision artifact and covered by UI or explicit `not_applicable` reason;
- final winner is selected from OOS walk-forward evidence according to chosen objective, never highest in-sample return;
- old React/TypeScript production UI is deleted, no production Node web container remains, and repository current-state docs contain no instruction to use it;
- final Compose has exactly `postgres`, `app`, `project-bootstrap-worker`; one Python `app` serves FastAPI REST and Dash browser UI;
- canonical browser routes have no `/dash` prefix; existing `/api` REST contract remains available;
- two-project tests prove no run status, progress, universe point, pair value, objective, decision, candidate, winner, weight, or explanation crosses project boundaries;
- all named tests, contracts, architecture checks, Docker/Compose builds, clean three-service startup, browser/E2E journey, and repository quality gates pass from one Git SHA.
