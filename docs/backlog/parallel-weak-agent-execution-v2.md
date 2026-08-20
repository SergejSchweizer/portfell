# Parallel Weak-Agent Execution Plan v2

Status: active execution addendum for the open `BACKLOG.md` Dash / Multivariate / cutover / Sunday-refresh series.

Last reviewed: 2026-08-20.

This document changes **execution granularity and dependencies only**. Product semantics, calculation semantics, optimizer objectives, professional-plot requirements, correctness amendments, project isolation, Universe & History semantics, and Sunday schedule remain governed by the existing active backlog documents. When an older document describes PR264-PR276 as larger units, this addendum supersedes that older PR boundary and parallelization wording.

## Why this split exists

The prior plan had four serial bottlenecks that were too large for weak agents:

1. PR264 mixed runtime wiring, shared contracts, plot contracts, run-control, fixtures, Docker, and architecture checks.
2. PR267/PR268 mixed page control, callbacks, plots, and history evidence.
3. PR269 mixed objective/run identity, DecisionArtifact contracts, project isolation, and ResearchUniverseSnapshot semantics.
4. PR274/PR275/PR276 each mixed several independent implementation surfaces with one late integration step.

The new plan freezes small contracts first, gives every implementation PR exclusive file ownership, allows sibling PRs to branch from the same predecessor SHA, and leaves only small integration gates on the critical path.

## Parallel Weak-Agent PR Design

Every non-merged PR in this series must satisfy all of these rules before an agent starts:

- One atomic outcome; if the outcome contains two independently testable runtime behaviors, split it.
- Exact predecessor commit or exact predecessor PR set is named. Parallel sibling branches start from the same predecessor SHA.
- Exact owned paths are listed. Sibling PRs may not edit the same file.
- Shared public contracts, IDs, enums, serialization, route suffixes, progress phases, objective IDs, reason codes, snapshot fields, and fixture IDs are frozen in a predecessor PR, never invented independently by sibling agents.
- `Tasks / Acceptance` is the only checklist. Each checkbox states implementation plus the machine-verifiable evidence that proves it.
- Agent A owns implementation paths; Agent B owns tests/fixtures/docs or a disjoint implementation surface. A hand-off is allowed only when stated explicitly.
- No weak agent may perform opportunistic refactors, rename unrelated modules, add compatibility layers, or infer a new architecture.
- Every PR runs focused tests plus the canonical `uv run portfell-quality pr`; UI/runtime PRs also run their named Docker/Compose/E2E evidence.
- Current canonical merge coverage is the repository value in `GATES.md` (currently 95%); backlog PRs must not restate a weaker threshold.
- Sibling PRs merge independently. After all siblings in one wave merge, the next wave branches from that resulting `main` SHA. This series-specific rule overrides any older generic wording that says UI branches must stack on each other.

## File ownership namespace

New files should be placed under these explicit namespaces so sibling work stays merge-safe:

- Dash runtime/core: `src/portfell/dash_ui/runtime/**`, `src/portfell/dash_ui/core/**`
- Dash pages: `src/portfell/dash_ui/pages/<stage>/**`
- Dash figures: `src/portfell/dash_ui/figures/<stage>/**`
- Dash view models/callbacks: `src/portfell/dash_ui/viewmodels/<stage>/**`, `src/portfell/dash_ui/callbacks/<stage>/**`
- Multivariate contracts: `src/portfell/multivariate/contracts/**`
- Multivariate selector: `src/portfell/multivariate/selector/**`
- Multivariate solvers/risk models: `src/portfell/multivariate/candidates/**`
- Multivariate orchestration: `src/portfell/multivariate/orchestration/**`
- Multivariate persistence/API projections: existing persistence/API layers plus new stage-specific modules named by the owning PR.
- Scheduled research: `src/portfell/scheduled_research/**`

If an existing module must be edited, the owning PR must name that exact existing file before implementation. Two active sibling PRs may not both own it.

## Revised execution graph

```text
PR458 merged planning gate
        |
        v
PR264 tiny Dash registry / protocol freeze
        |
  +-----+-------------------+
  |                         |
PR277 Dash runtime        PR278 shared presentation contracts
+ temporary container     + run-control/plots/fixtures/gates
  |                         |
  +-----------+-------------+
              |
         merge both
              |
  +-----------+-------------+
  |                         |
PR265 shell/nav          PR266 metadata page
  |                         |
  +-----------+-------------+
              |
         merge both
              |
  +-----------+-------------+
  |                         |
PR267 Uni control/page   PR268 Bi control/page
  |                         |
  +-----------+-------------+
              |
         merge both
              |
  +-----------+-------------+
  |                         |
PR279 Uni figures/history PR280 Bi figures/history
  |                         |
  +-----------+-------------+
              |
         merge both
              |
         PR269 tiny Multi common registry freeze
              |
  +-----------+-------------+-------------+
  |                         |             |
PR281 objective/run     PR282 decisions  PR283 history/isolation
contracts               contracts        contracts
  |                         |             |
  +-----------+-------------+-------------+
              |
        merge contract siblings
              |
  +-----------+-------------+-------------+-------------+
  |                         |             |             |
PR270 eligibility/Pareto PR271 solvers  PR284 redundancy PR285 risk/history
  |                         |             |             |
  +-----------+-------------+-------------+-------------+
              |
         PR286 algorithm integration gate
              |
  +-----------+---------------------------+
  |                                       |
PR272 walk-forward/OOS orchestration   PR273 persistence/repository
  |                                       |
  |                                  PR287 read API/projections
  |                                       |
  +-------------------+-------------------+
                      |
            +---------+---------+
            |         |         |
          PR288     PR289     PR290
          figures   callbacks  page/layout
            |         |         |
            +---------+---------+
                      |
                    PR274
              Multi UI integration/E2E
                      |
            +---------+---------+
            |                   |
          PR291               PR292
          FastAPI mount       React/Node deletion
            |                   |
            +---------+---------+
                      |
                    PR275
              Compose cutover gate
                      |
          +-----------+-----------+
          |           |           |
        PR293       PR294       PR295
        union       project     scheduler/lock
        refresh     research    summary
          |           |           |
          +-----------+-----------+
                      |
                    PR276
             Sunday integration/E2E
```

Three- and four-way waves are intentionally valid. With only two available agents, schedule any two siblings first, then the remaining sibling(s) from the **same predecessor SHA**; do not rebase the later sibling onto a partially merged sibling.

---

## PR264 — Dash route, ID, and gateway protocol freeze

Branch: `feat/dash-contract-registry`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(dash-contract-registry): freeze dash routes ids and gateway protocols`.
Required squash subject: same as PR title.
Base: current `main` after PR458.
Merge method: squash only.
Priority: P0 foundation.
Depends on: PR458.
Scope: declarations only; no running Dash app and no Docker change.
Owned paths: `src/portfell/dash_ui/core/routes.py`, `ids.py`, `gateway.py`, contract-only tests.
Tasks / Acceptance:
- [ ] Freeze exactly four workflow IDs/suffixes and component namespace constants; registry tests fail on duplicate, missing, reordered, or fifth workflow page.
- [ ] Define typed presentation gateway protocols for project context, page reads, run start/status, selection settings, Multivariate settings, decision sections, and Universe & History reads; architecture tests prove the protocol imports no DB/provider/storage authority.
- [ ] Freeze base-prefix abstraction supporting temporary `/dash/` and final `/`; no page implementation exists in this PR.
- [ ] Focused tests, Ruff, Pyright, architecture checks, and `uv run portfell-quality pr` pass from one SHA.
Parallelization: Agent A owns routes/IDs; Agent B owns gateway protocol/tests. No shared implementation file.
Security: protocols carry authorized presentation data only.
Determinism: frozen constants and signatures.
Idempotency: declarations only.
Rollback: delete the new registry/protocol files.

## PR277 — Temporary Dash runtime and container

Branch: `feat/dash-temporary-runtime`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(dash-temporary-runtime): add temporary dash runtime`.
Required squash subject: same as PR title.
Base: exact PR264 merge SHA.
Merge method: squash only.
Priority: P0.
Depends on: PR264.
Scope: runnable temporary Dash/FastAPI sidecar only.
Owned paths: dependency lock, `src/portfell/dash_ui/runtime/**`, temporary `apps/dash/Dockerfile`, temporary Dash Compose profile/service.
Tasks / Acceptance:
- [ ] Add only required Dash-compatible dependencies and lock them; no Celery, Redis, DiskCache, pandas, second queue, or second durable-state authority.
- [ ] Start a Dash Pages app at temporary `/dash/` using PR264 routes with strict callback validation and no import-time DB/provider/calculation side effects.
- [ ] Add temporary health check/container/profile; container receives no DB/provider credential and Compose validation passes.
- [ ] Runtime smoke test, Docker build, Compose validation, Ruff, Pyright, and `uv run portfell-quality pr` pass.
Parallelization: Agent A runtime/dependencies; Agent B Docker/Compose/smoke tests. Contract files from PR264 are read-only.
Security: presentation sidecar has no DB/provider secret.
Determinism: startup shape is config + frozen registry only.
Idempotency: startup/health mutate nothing.
Rollback: remove temporary runtime/container/dependencies.

## PR278 — Shared run-control, plot contracts, fixtures, and architecture gates

Branch: `feat/dash-presentation-contracts`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(dash-presentation-contracts): add shared presentation contracts`.
Required squash subject: same as PR title.
Base: same exact PR264 merge SHA as PR277.
Merge method: squash only.
Priority: P0.
Depends on: PR264.
Scope: pure presentation contracts and deterministic fixtures only.
Owned paths: `src/portfell/dash_ui/core/run_control.py`, `plot_contracts.py`, `availability.py`, `testing.py`, architecture/contract tests.
Tasks / Acceptance:
- [ ] Define `StatisticsRunControl` with exact statuses `idle|starting|running|complete|failed|stale` and typed indeterminate progress; fixed fixtures cover zero-total, partial, failed, complete, stale, and unavailable progress.
- [ ] Freeze `ProfessionalPlotContract`, common figure IDs, availability states, and presentation-only point/section DTOs; no financial formulas are implemented.
- [ ] Add deterministic two-project fixtures with cross-project isolation, three objectives, Uni/Bi/Multi statuses, history states, candidates, winner, and decision sections.
- [ ] Architecture tests fail if `portfell.dash_ui` imports persistence/provider/lake/risk-formula authority; focused tests plus `uv run portfell-quality pr` pass.
Parallelization: Agent A run-control/availability; Agent B plot contracts/fixtures/architecture tests.
Security: fixtures contain no secrets.
Determinism: canonical fixture IDs and ordering.
Idempotency: pure adapters only.
Rollback: remove shared presentation contract modules.

## PR265 — Dash shell and four-stage navigation

Branch: `feat/dash-research-shell`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(dash-research-shell): add four-stage research shell`.
Required squash subject: same as PR title.
Base: exact `main` after PR277+PR278.
Merge method: squash only.
Priority: P1.
Depends on: PR264, PR277, PR278.
Scope: shell/navigation only.
Owned paths: `src/portfell/dash_ui/core/shell.py`, `navigation.py`, shell CSS/tests.
Tasks / Acceptance:
- [ ] Render header, project selector, process overview, four-link sidebar, and page region using frozen routes only.
- [ ] Project switching clears old-project presentation state before new reads; unknown/deleted/unauthorized project is typed unavailable and never falls back.
- [ ] Desktop and 390px keyboard/focus tests pass; browser storage contains no credentials/results/financial series.
- [ ] Focused Dash tests, Docker smoke build, and `uv run portfell-quality pr` pass.
Parallelization: Agent A shell layout; Agent B navigation/project-switch tests and CSS. Metadata files forbidden.
Security: URL/project state never grants authorization.
Determinism: slug + workflow projection.
Idempotency: selecting same project emits no command.
Rollback: revert shell/navigation paths.

## PR266 — Dash Metadata Builder and initial Universe & History

Branch: `feat/dash-metadata-builder`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(dash-metadata-builder): add metadata builder and initial history`.
Required squash subject: same as PR title.
Base: same exact predecessor SHA as PR265.
Merge method: squash only.
Priority: P1.
Depends on: PR264, PR277, PR278.
Scope: Metadata page only.
Owned paths: `src/portfell/dash_ui/pages/metadata_builder/**`, `viewmodels/metadata_builder/**`, `callbacks/metadata_builder/**`, Metadata CSS/tests.
Tasks / Acceptance:
- [ ] Render metadata fetch status/action plus exactly Exchange, Instrument type, Country, Currency, and `Name contains` builder criteria using server-owned counts/sort.
- [ ] Project creation/fill uses existing idempotent commands, never receives provider key, restores persisted progress on reload, and duplicate callbacks create at most one logical command.
- [ ] Show listing count, unique-ISIN count, initial observed-history evidence when available, and typed downstream not-run/blocked states without browser recomputation.
- [ ] Two-project/failure fixtures, focused Dash tests, Docker smoke build, and `uv run portfell-quality pr` pass.
Parallelization: Agent A page/view-model; Agent B callbacks/tests. Shell files read-only except one registration import owned by Agent A.
Security: provider credential remains server-side.
Determinism: revision/options determine display.
Idempotency: read-only render; command identity remains server-owned.
Rollback: revert Metadata paths.

## PR267 — Univariate page, calculation control, and callbacks

Branch: `feat/dash-univariate-control`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(dash-univariate-control): add univariate run control`.
Required squash subject: same as PR title.
Base: exact `main` after PR265+PR266.
Merge method: squash only.
Priority: P0.
Depends on: PR265, PR266.
Scope: control/view-model/callbacks/tabs wiring; professional figures/history are PR279.
Owned paths: `pages/univariate_statistics/**`, `viewmodels/univariate_statistics/**`, `callbacks/univariate_statistics/**` excluding `figures/**`.
Tasks / Acceptance:
- [ ] Render exact `Compute univariate statistics` control using PR278 run-control; disable correctly for unavailable/starting/running and restore persisted complete/failed/stale status.
- [ ] Preserve existing dividend-frequency selection, threshold settings, metric tabs, revision-bound paging, labels, and descriptions without recomputing statistics.
- [ ] Duplicate activation creates at most one logical run; project switch clears obsolete progress/results before replacement reads.
- [ ] Run-control/callback/two-project tests plus `uv run portfell-quality pr` pass.
Parallelization: Agent A page/view-model; Agent B callbacks/tests. Figure factory paths are forbidden.
Security: authorized project results only.
Determinism: server revision + frozen adapters.
Idempotency: duplicate start converges.
Rollback: revert Univariate control paths.

## PR268 — Bivariate page, calculation control, and callbacks

Branch: `feat/dash-bivariate-control`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(dash-bivariate-control): add bivariate run control`.
Required squash subject: same as PR title.
Base: same exact predecessor SHA as PR267.
Merge method: squash only.
Priority: P0.
Depends on: PR265, PR266.
Scope: control/view-model/callbacks/detail-tab wiring; professional figures/history are PR280.
Owned paths: `pages/bivariate_statistics/**`, `viewmodels/bivariate_statistics/**`, `callbacks/bivariate_statistics/**` excluding `figures/**`.
Tasks / Acceptance:
- [ ] Render exact `Compute bivariate statistics` control using persisted upstream Univariate selection/revision and PR278 run-control.
- [ ] Preserve exactly nine named detail views and their section availability; no browser-side pair/statistic calculation.
- [ ] Duplicate activation creates at most one logical run; reload/project switch restores or clears correct project-scoped state.
- [ ] Run-control/callback/two-project tests plus `uv run portfell-quality pr` pass.
Parallelization: Agent A page/view-model; Agent B callbacks/tests. Figure paths forbidden.
Security: section IDs do not authorize access.
Determinism: pinned revision + stable section order.
Idempotency: duplicate start converges.
Rollback: revert Bivariate control paths.

## PR279 — Univariate professional figures and listing-history evidence

Branch: `feat/dash-univariate-figures`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(dash-univariate-figures): add univariate risk and history figures`.
Required squash subject: same as PR title.
Base: exact `main` after PR267+PR268.
Merge method: squash only.
Priority: P0.
Depends on: PR267, PR278 and active professional-plot/history contracts.
Scope: pure Univariate figure builders and history presentation only.
Owned paths: `src/portfell/dash_ui/figures/univariate_statistics/**`, figure tests.
Tasks / Acceptance:
- [ ] Build always-visible `Univariate Return / Risk Universe` with frozen axes/units, full listing identity, selected/rejected/data-quality states, friendly hover, and deterministic Pareto frontier.
- [ ] Build `Univariate Listing History Coverage` plus min/median/max per-listing history evidence from server snapshots; unavailable values are typed, never zero/guessed.
- [ ] Figure registry, equal-tie, unavailable, duplicate-ISIN-listing, large-fixture, and deterministic-order tests pass.
- [ ] Ruff, Pyright, figure tests, and `uv run portfell-quality pr` pass.
Parallelization: Agent A return/risk figure; Agent B history figure/registry tests. Page/callback paths forbidden.
Security: figures consume presentation DTOs only.
Determinism: stable listing/trace sort + frozen frontier rule.
Idempotency: pure figure functions.
Rollback: remove Univariate figure modules.

## PR280 — Bivariate professional figures and pair-history evidence

Branch: `feat/dash-bivariate-figures`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(dash-bivariate-figures): add diversification and pair history figures`.
Required squash subject: same as PR title.
Base: same exact predecessor SHA as PR279.
Merge method: squash only.
Priority: P0.
Depends on: PR268, PR278 and active professional-plot/history contracts.
Scope: pure Bivariate figure builders and history presentation only.
Owned paths: `src/portfell/dash_ui/figures/bivariate_statistics/**`, figure tests.
Tasks / Acceptance:
- [ ] Build always-visible `Bivariate Return / Diversification Universe` with exact metric selector registry, named dynamic X axis, upstream return Y, full listing identity, and deterministic hover.
- [ ] Build nine detail figures using authorized sections and `Pairwise Shared-History Distribution` with exact pair count/shared-observation evidence; unavailable values remain typed.
- [ ] Deterministic 201-listing/20,100-pair fixture, WebGL threshold, stale/unavailable, and registry tests pass.
- [ ] Ruff, Pyright, figure tests, and `uv run portfell-quality pr` pass.
Parallelization: Agent A universe/selector figure; Agent B detailed/history figures/tests. Page/callback paths forbidden.
Security: figures are presentation-only.
Determinism: pair revision + stable metric/trace order.
Idempotency: pure figure functions.
Rollback: remove Bivariate figure modules.

## PR269 — Multivariate common IDs, canonical serialization, and protocol freeze

Branch: `feat/multivariate-contract-registry`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(multivariate-contract-registry): freeze multivariate common contracts`.
Required squash subject: same as PR title.
Base: exact `main` after PR279+PR280.
Merge method: squash only.
Priority: P0 foundation.
Depends on: PR279, PR280.
Scope: common primitives only; no objective ranking, decision payload, history payload, selector, solver, orchestration, or persistence implementation.
Owned paths: `src/portfell/multivariate/contracts/common.py`, `serialization.py`, `protocols.py`, common tests.
Tasks / Acceptance:
- [ ] Freeze full `ListingIdentity=(isin, exchange, code)`, configuration identity primitives, algorithm/profile version primitives, and canonical finite JSON serialization.
- [ ] Freeze exact eight decision-stage IDs and common typed availability/attempt/error envelope; public serialization rejects NaN/Inf/secrets/paths/unbounded objects.
- [ ] Define protocol boundaries used by objective, decisions, history, selector, candidates, orchestration, sink, and read projections so sibling contract PRs need no shared file edits.
- [ ] Canonical-order/property tests, Ruff, Pyright, architecture checks, and `uv run portfell-quality pr` pass.
Parallelization: Agent A common identities/protocols; Agent B serialization/property tests. No sibling may edit these files.
Security: public errors are redacted.
Determinism: canonical bytes define identities.
Idempotency: declarations only.
Rollback: remove common Multivariate registry modules.

## PR281 — Multivariate objective, settings, run identity, and progress contracts

Branch: `feat/multivariate-run-contracts`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(multivariate-run-contracts): define objectives runs and progress`.
Required squash subject: same as PR title.
Base: exact PR269 merge SHA.
Merge method: squash only.
Priority: P0.
Depends on: PR269.
Scope: objective/settings/run/progress contracts only.
Owned paths: `multivariate/contracts/objectives.py`, `settings.py`, `runs.py`, tests.
Tasks / Acceptance:
- [ ] Define exactly `return_risk`, `return_drawdown`, `minimum_risk`, default `return_risk`, exact labels, primary metrics, and tie-break orders from active backlog semantics.
- [ ] Define settings with allowed constraints and no manual ISIN/single-method selector; objective/settings are immutable run identity inputs.
- [ ] Freeze exact progress phases `select_universe|estimate_risk_models|build_candidates|walk_forward|select_winner|final_refit|publish_decisions` and map them to shared run-control without UI math.
- [ ] All-objective identity/tie/unknown-ID/progress tests plus `uv run portfell-quality pr` pass.
Parallelization: Agent A objective/settings; Agent B run/progress/tests.
Security: analytical settings only.
Determinism: objective registry + canonical serialization.
Idempotency: same identity inputs produce same logical run ID.
Rollback: remove objective/run contract modules.

## PR282 — DecisionArtifact, reason registry, and sink contracts

Branch: `feat/multivariate-decision-contracts`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(multivariate-decision-contracts): define auditable decision artifacts`.
Required squash subject: same as PR title.
Base: same exact PR269 merge SHA as PR281/PR283.
Merge method: squash only.
Priority: P0.
Depends on: PR269.
Scope: immutable decision evidence contracts only.
Owned paths: `multivariate/contracts/decisions.py`, `decision_reasons.py`, tests.
Tasks / Acceptance:
- [ ] Define immutable DecisionArtifact/Candidate/Rejection payloads using PR269 stage/common identities and pinned revisions/versions.
- [ ] Freeze reason codes covering eligibility/history/distribution/Pareto/redundancy/risk-model/solver/walk-forward/OOS/not-applicable cases.
- [ ] Define content-addressed decision ID and sink semantics: same ID+same canonical bytes no-op; same ID+different bytes conflicts closed.
- [ ] All-stage/reason/content-order/conflict tests plus `uv run portfell-quality pr` pass.
Parallelization: Agent A payload/reason enums; Agent B ID/sink/property tests.
Security: analytical evidence only.
Determinism: canonical bytes + ordered candidates/outcome.
Idempotency: identical writes converge.
Rollback: remove decision contract modules.

## PR283 — ResearchUniverseSnapshot, history semantics, and project-isolation contracts

Branch: `feat/multivariate-history-contracts`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(multivariate-history-contracts): define universe history and isolation`.
Required squash subject: same as PR title.
Base: same exact PR269 merge SHA as PR281/PR282.
Merge method: squash only.
Priority: P0.
Depends on: PR269.
Scope: snapshot/removal/history/project-scoped selection contracts only.
Owned paths: `multivariate/contracts/history.py`, `project_selection.py`, tests.
Tasks / Acceptance:
- [ ] Freeze canonical ResearchUniverseSnapshot fields/stage order and exact separation of observed history envelope vs common usable history.
- [ ] Freeze listing/unique-ISIN counts, removal reason registry, pair/shared-history fields, aligned optimization calendar, walk-forward train/test ranges, final-refit range, and typed not-run/blocked/unavailable states.
- [ ] Freeze project-scoped immutable current-selection/revision contract; full listing identity is mandatory and cross-project fallback is forbidden.
- [ ] Two-project/reordered-input/unavailable-state/snapshot-identity tests plus `uv run portfell-quality pr` pass.
Parallelization: Agent A history snapshot/reasons; Agent B project isolation/tests.
Security: project identity required for scoped state.
Determinism: canonical snapshot serialization.
Idempotency: identical state writes converge.
Rollback: remove history/isolation contract modules.

## PR270 — Eligibility and Univariate Pareto selector

Branch: `feat/multivariate-pareto-selector`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(multivariate-pareto-selector): add eligibility and pareto selection`.
Required squash subject: same as PR title.
Base: exact `main` after PR281+PR282+PR283.
Merge method: squash only.
Priority: P0.
Depends on: PR281, PR282, PR283.
Scope: selector stages `input_eligibility` + `univariate_pareto` only; no clustering.
Owned paths: `multivariate/selector/eligibility.py`, `pareto.py`, tests.
Tasks / Acceptance:
- [ ] Start from exact pinned Bivariate listing set, remove only, preserve full listing identity, and emit explicit hard-eligibility reasons; missing required values are unavailable, not zero.
- [ ] Implement deterministic non-dominated sorting with the six frozen metrics and rank-by-rank minimum-feasibility extension.
- [ ] Emit DecisionArtifacts and before/after ResearchUniverseSnapshots for both stages.
- [ ] Dominated/non-dominated/tie/missing/mixed-frequency/reversed-order/property tests plus `uv run portfell-quality pr` pass.
Parallelization: Agent A eligibility; Agent B Pareto/tests. Redundancy modules forbidden.
Security: authorized pinned input only.
Determinism: frozen metric/tie rules.
Idempotency: pure selection.
Rollback: remove eligibility/Pareto modules.

## PR271 — Solver adapters and portfolio method candidates

Branch: `feat/multivariate-solver-candidates`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(multivariate-solver-candidates): add solver backed candidates`.
Required squash subject: same as PR title.
Base: same exact predecessor SHA as PR270/PR284/PR285.
Merge method: squash only.
Priority: P0.
Depends on: PR281, PR282, PR283.
Scope: seven optimizer-method adapters only; risk-model alignment is PR285.
Owned paths: `multivariate/candidates/solvers.py`, `methods.py`, solver tests.
Tasks / Acceptance:
- [ ] Support exactly Equal Weight, Minimum Variance, Maximum Sharpe, Maximum Diversification, ERC, HRP, Minimum CVaR through one typed candidate interface, reusing existing formulas where present.
- [ ] Maximum Sharpe and Maximum Diversification use deterministic numerical solvers with long-only capped-simplex constraints; no large-universe weight-grid/subset enumeration.
- [ ] Failure/non-convergence is typed unavailable and never silently replaced by Equal Weight under another method name.
- [ ] 2-4 asset bounded brute-force comparison, reversed-input, finite/bounds/sum, and large-universe no-grid tests plus `uv run portfell-quality pr` pass.
Parallelization: Agent A Maximum Sharpe/Diversification adapters; Agent B remaining adapter wiring/tests.
Security: numerical code has no storage/provider authority.
Determinism: fixed solver initialization/tolerances.
Idempotency: pure candidate methods.
Rollback: remove solver adapter modules.

## PR284 — Deterministic Bivariate redundancy reducer

Branch: `feat/multivariate-redundancy-reducer`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(multivariate-redundancy-reducer): add deterministic redundancy reduction`.
Required squash subject: same as PR title.
Base: same exact predecessor SHA as PR270/PR271/PR285.
Merge method: squash only.
Priority: P0.
Depends on: PR281, PR282, PR283.
Scope: `bivariate_redundancy` pure stage only.
Owned paths: `multivariate/selector/redundancy.py`, clustering helpers, tests.
Tasks / Acceptance:
- [ ] If input `<=250`, emit `not_applicable` with unchanged membership and snapshot.
- [ ] If input `>250`, deterministic Pearson hierarchical clustering produces exactly 250 representatives using the frozen representative tie-break sequence.
- [ ] Rejection evidence records representative and available dependence/tail/drawdown evidence plus before/after common-history impact.
- [ ] 400-listing, reversed-order, worker-count, exact-250, uniqueness/subset tests plus `uv run portfell-quality pr` pass.
Parallelization: Agent A clustering/membership; Agent B evidence/history/tests.
Security: input is authorized pinned pair evidence only.
Determinism: frozen clustering/tie rules.
Idempotency: pure reducer.
Rollback: remove redundancy modules.

## PR285 — Risk-model configurations, aligned-history diagnostics, and candidate assembly

Branch: `feat/multivariate-risk-candidates`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(multivariate-risk-candidates): add risk models and aligned history`.
Required squash subject: same as PR title.
Base: same exact predecessor SHA as PR270/PR271/PR284.
Merge method: squash only.
Priority: P0.
Depends on: PR281, PR282, PR283.
Scope: risk-model preparation + candidate configuration assembly; no solver formulas from PR271.
Owned paths: `multivariate/candidates/risk_models.py`, `builder.py`, aligned-history tests.
Tasks / Acceptance:
- [ ] Support exactly Sample, Ledoit-Wolf, EWMA and freeze configuration identity over risk model + optimizer method + settings/version.
- [ ] Align training-window data once per configuration and emit exact aligned start/end/observation count; missing/insufficient data yields typed unavailable candidate evidence.
- [ ] Expected-return map is estimated from training-window daily log returns using existing annualization semantics and is split-local during walk-forward use.
- [ ] Configuration-identity/aligned-history/reversed-order/insufficient-history tests plus `uv run portfell-quality pr` pass.
Parallelization: Agent A risk-model adapters/alignment; Agent B builder/diagnostics/tests. Solver implementation files forbidden.
Security: pure numerical/presentation evidence inputs.
Determinism: fixed configuration identities/alignment rule.
Idempotency: pure preparation.
Rollback: remove risk/builder modules.

## PR286 — Multivariate selector/candidate integration gate

Branch: `feat/multivariate-algorithm-integration`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(multivariate-algorithm-integration): integrate selector and candidates`.
Required squash subject: same as PR title.
Base: exact `main` after PR270+PR271+PR284+PR285.
Merge method: squash only.
Priority: P0 integration gate.
Depends on: PR270, PR271, PR284, PR285.
Scope: composition only; no new algorithm.
Owned paths: `multivariate/selector/pipeline.py`, `multivariate/candidates/pipeline.py`, integration fixtures/tests.
Tasks / Acceptance:
- [ ] Compose eligibility -> Pareto -> redundancy using frozen stage artifacts/snapshots without changing child algorithms.
- [ ] Compose risk model -> seven method candidates using frozen configuration IDs and typed unavailable states.
- [ ] Deterministic 400-input/<=250-selected fixture produces stable decisions/configurations under reversed input and worker-count changes.
- [ ] Focused integration tests plus `uv run portfell-quality pr` pass; any algorithm change is rejected back to its owning PR/module.
Parallelization: Agent A selector composition; Agent B candidate composition/integration tests.
Security: composition adds no new authority.
Determinism: child identities preserved.
Idempotency: pure composition.
Rollback: remove pipeline composition modules.

## PR272 — Walk-forward, OOS objective ranking, winner, and final refit orchestration

Branch: `feat/multivariate-oos-orchestration`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(multivariate-oos-orchestration): select portfolio by oos objective`.
Required squash subject: same as PR title.
Base: exact PR286 merge SHA.
Merge method: squash only.
Priority: P0.
Depends on: PR286, PR281-PR283.
Scope: one in-memory/durable-service orchestration implementation; persistence writes go only through protocols and PR282 sink.
Owned paths: `multivariate/orchestration/walk_forward.py`, `ranking.py`, `runner.py`, orchestration tests.
Tasks / Acceptance:
- [ ] Execute frozen Multivariate phases in order, re-estimating split-local expected returns/risk inputs and emitting exact train/test ranges for every walk-forward split.
- [ ] Rank candidates by selected objective using only OOS evidence and exact tie-breaks; one winner is selected or typed failure/unavailable is emitted.
- [ ] Final refit uses selected configuration on final eligible aligned history and emits final portfolio decision + exact final-refit history snapshot.
- [ ] Same immutable inputs/settings converge on one logical result; restart/duplicate invocation does not duplicate decisions/snapshots.
- [ ] All-objective/five-split/failure/restart/reversed-order tests plus `uv run portfell-quality pr` pass.
Parallelization: Agent A walk-forward/ranking; Agent B runner/final-refit/idempotency tests.
Security: authorize project/run before loading inputs.
Determinism: objective registry + split policy + candidate registry.
Idempotency: logical run identity + content-addressed decisions.
Rollback: remove orchestration modules.

## PR273 — Multivariate persistence and repository layer

Branch: `feat/multivariate-decision-persistence`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(multivariate-decision-persistence): persist decisions and history snapshots`.
Required squash subject: same as PR title.
Base: same exact PR286 merge SHA as PR272.
Merge method: squash only.
Priority: P0.
Depends on: PR282, PR283, PR286.
Scope: schema/migrations/repositories only; no GET API projection and no calculation.
Owned paths: new Multivariate decision/history migration files and repository modules explicitly listed before implementation, repository tests.
Tasks / Acceptance:
- [ ] Persist immutable project-scoped run/configuration/DecisionArtifact/ResearchUniverseSnapshot/current-selection records with canonical uniqueness/conflict semantics.
- [ ] Same canonical write is no-op; same logical ID with different canonical content fails closed; cross-project lookup cannot fall back.
- [ ] Repository reads return stored evidence only and perform no financial/history calculation.
- [ ] Migration up/idempotent replay/repository isolation/conflict/restart tests plus `uv run portfell-quality pr` pass.
Parallelization: Agent A migration/schema; Agent B repositories/tests. They may share only the frozen schema contract agreed before coding.
Security: project/run identity in every scoped repository call.
Determinism: canonical persisted bytes/revisions.
Idempotency: unique constraints + no-op identical writes.
Rollback: reversible migration/remove repository surface without deleting unrelated data.

## PR287 — Multivariate read API and lazy evidence projections

Branch: `feat/multivariate-read-api`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(multivariate-read-api): expose decision and history projections`.
Required squash subject: same as PR title.
Base: exact PR273 merge SHA; may run in parallel with late PR272 validation because it reads repository protocols only.
Merge method: squash only.
Priority: P0.
Depends on: PR273, PR282, PR283.
Scope: authorized GET/read projections only; no calculation/start command.
Owned paths: stage-specific API route/projection modules and API tests named before implementation.
Tasks / Acceptance:
- [ ] Expose compact pipeline projection, current Multivariate run/selection summary, and lazy decision/history sections using persisted repository evidence only.
- [ ] Every project/run read authorizes before repository access; unavailable/not-run/blocked states remain typed and public errors redacted.
- [ ] GET paths are non-mutating and make zero calls to selector/solver/statistics/history calculators.
- [ ] Two-project/auth/unavailable/lazy-section/no-calculation tests plus `uv run portfell-quality pr` pass.
Parallelization: Agent A projections/serialization; Agent B route/auth/tests.
Security: authorization before data.
Determinism: persisted revision -> stable projection.
Idempotency: GET only.
Rollback: remove read routes/projections.

## PR288 — Multivariate professional and Decision Audit figures

Branch: `feat/dash-multivariate-figures`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(dash-multivariate-figures): add optimizer decision figures`.
Required squash subject: same as PR title.
Base: exact `main` after PR272+PR287.
Merge method: squash only.
Priority: P0.
Depends on: PR272, PR287, professional-plot/history contracts.
Scope: pure Multivariate figure factories only.
Owned paths: `src/portfell/dash_ui/figures/multivariate_statistics/**`, tests.
Tasks / Acceptance:
- [ ] Build always-visible `Portfolio Candidate OOS Return / Risk` with frozen axes/units and objective/winner semantics.
- [ ] Build Decision Audit figures/tables for all eight decision stages, including not-applicable/unavailable reason presentation; UI never reconstructs reasons.
- [ ] Build aligned risk-model history, reduction history, `Walk-Forward Training / Test Coverage`, and final-refit history figures from persisted snapshots.
- [ ] Figure registry/all-stage/all-objective/unavailable/deterministic-order tests plus `uv run portfell-quality pr` pass.
Parallelization: Agent A candidate/winner figures; Agent B decision/history figures/registry tests.
Security: presentation DTOs only.
Determinism: run/objective/revision -> stable traces.
Idempotency: pure figure functions.
Rollback: remove Multivariate figures.

## PR289 — Multivariate view-model and callbacks

Branch: `feat/dash-multivariate-callbacks`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(dash-multivariate-callbacks): add optimizer callbacks`.
Required squash subject: same as PR title.
Base: same exact predecessor SHA as PR288/PR290.
Merge method: squash only.
Priority: P0.
Depends on: PR272, PR287, PR278.
Scope: objective/settings/start/status/lazy-section callbacks and view-models only.
Owned paths: `dash_ui/viewmodels/multivariate_statistics/**`, `callbacks/multivariate_statistics/**`, callback tests.
Tasks / Acceptance:
- [ ] Expose exactly three objectives, default `return_risk`, optional allowed constraints, exact `Optimize portfolio` action, and PR278 run-control states.
- [ ] Objective/settings changes mark current result stale but never auto-start; duplicate activation creates at most one logical run.
- [ ] Poll/read callbacks consume authorized persisted API projections and lazy sections only; project switch clears old-project status/results before replacement paint.
- [ ] All-objective/stale/duplicate/project-switch/failure/lazy-section tests plus `uv run portfell-quality pr` pass.
Parallelization: Agent A view-model/settings; Agent B callbacks/tests.
Security: browser receives no DB/provider/storage authority.
Determinism: run/objective/revision projection.
Idempotency: duplicate start converges.
Rollback: remove Multivariate callbacks/view-models.

## PR290 — Multivariate page layout and responsive Decision/History Audit shell

Branch: `feat/dash-multivariate-layout`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(dash-multivariate-layout): add optimizer page layout`.
Required squash subject: same as PR title.
Base: same exact predecessor SHA as PR288/PR289.
Merge method: squash only.
Priority: P0.
Depends on: PR272, PR287, PR278.
Scope: layout/CSS/figure placeholders only; no callbacks and no figure calculations.
Owned paths: `dash_ui/pages/multivariate_statistics/**`, Multivariate-only CSS/layout tests.
Tasks / Acceptance:
- [ ] Layout order is objective selector -> run control -> persistent Universe & History summary/pipeline -> candidate plot -> tabs exactly `Universe|Risk Model|Optimization|Validation|Final Portfolio`.
- [ ] Decision Audit regions for all eight stages remain visible with typed availability; no separate Optimizer route/page/stage exists.
- [ ] Desktop and 390px responsive/focus/keyboard/accessibility metadata tests pass using frozen component IDs.
- [ ] Focused layout tests, Docker smoke build, and `uv run portfell-quality pr` pass.
Parallelization: Agent A page composition; Agent B CSS/accessibility/layout tests.
Security: layout contains no data authority.
Determinism: frozen component registry/order.
Idempotency: static layout.
Rollback: revert Multivariate page/CSS.

## PR274 — Multivariate Dash integration and browser evidence gate

Branch: `feat/dash-multivariate-integration`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(dash-multivariate-integration): integrate auditable optimizer ui`.
Required squash subject: same as PR title.
Base: exact `main` after PR288+PR289+PR290.
Merge method: squash only.
Priority: P0 integration gate.
Depends on: PR288, PR289, PR290.
Scope: registration/wiring/E2E only; no new financial algorithm or figure semantics.
Owned paths: page registration import, Multivariate integration tests/E2E docs only.
Tasks / Acceptance:
- [ ] Wire page + callbacks + figures without changing their frozen child contracts; all tabs/Decision Audit/history regions render authorized persisted evidence.
- [ ] End-to-end test starts one run, observes progress, reloads, switches project, returns, and sees stable winner/decisions/history with no cross-project paint.
- [ ] Registry test proves every production figure uses ProfessionalPlotContract and exactly four workflow pages exist.
- [ ] Dash Docker build, focused browser E2E, Ruff, Pyright, and `uv run portfell-quality pr` pass from one SHA.
Parallelization: Agent A registration/integration wiring; Agent B E2E/registry evidence. Child implementation files are forbidden.
Security: integration adds no authority.
Determinism: child revision contracts preserved.
Idempotency: one logical start; reads/charts non-mutating.
Rollback: remove integration wiring/tests and return to three sibling components.

## PR291 — Mount Dash into FastAPI and expose canonical routes

Branch: `refactor/dash-fastapi-mount`.
Git status: not started.
PR: TBD.
Suggested PR title: `refactor(dash-fastapi-mount): mount dash into python app`.
Required squash subject: same as PR title.
Base: exact PR274 merge SHA.
Merge method: squash only.
Priority: P0 cutover preparation.
Depends on: PR274.
Scope: Python app mount/routing only; React deletion and Compose topology are separate.
Owned paths: FastAPI app mount module, Dash base-prefix/runtime config, route tests.
Tasks / Acceptance:
- [ ] Mount Dash into the existing Python app and change canonical browser routes to `/projects/<slug>/<suffix>` while REST stays under `/api`.
- [ ] Remove temporary `/dash` dependency from route generation without page-specific rewrites; four canonical routes and redirects pass.
- [ ] `portfell.dash_ui` still imports only typed gateway/presentation contracts even though the containing app has DB/provider secrets.
- [ ] App startup/route/auth/smoke tests plus `uv run portfell-quality pr` pass.
Parallelization: Agent A mount/base-prefix wiring; Agent B route/architecture tests.
Security: presentation package receives no direct secret/storage authority.
Determinism: canonical route registry.
Idempotency: startup/reads non-mutating.
Rollback: restore PR274 temporary sidecar routing.

## PR292 — Delete React/TypeScript/Vite and obsolete Node UI assets

Branch: `refactor/remove-react-ui`.
Git status: not started.
PR: TBD.
Suggested PR title: `refactor(remove-react-ui): delete legacy react production ui`.
Required squash subject: same as PR title.
Base: same exact PR274 merge SHA as PR291.
Merge method: squash only.
Priority: P0 cutover preparation.
Depends on: PR274.
Scope: deletion/cleanup only; do not edit Compose final topology or Python mount.
Owned paths: `apps/web/**` deletion and directly obsolete Node/Vite/React-only scripts/tests/docs identified in a pre-commit deletion manifest.
Tasks / Acceptance:
- [ ] Produce reviewed deletion manifest proving every removed file is React/Node-only or superseded by Dash evidence.
- [ ] Delete React/TS/Vite production UI and obsolete Node-only UI tests/config without deleting API/database/worker assets.
- [ ] Repository searches prove no production React/Vite/browser route implementation remains; Python tests unaffected by deletion pass.
- [ ] `uv run portfell-quality pr` passes for the deletion branch; expected obsolete web gate references are explicitly handed to PR275 for CI/Compose cleanup.
Parallelization: Agent A deletion manifest/files; Agent B repository-search/regression tests/docs. PR291/Compose files forbidden.
Security: deletion only.
Determinism: manifest defines exact removed paths.
Idempotency: deletion has no runtime write semantics.
Rollback: restore deleted paths from PR274 SHA.

## PR275 — Production Compose/CI cutover and evidence-preservation gate

Branch: `refactor/dash-production-cutover`.
Git status: not started.
PR: TBD.
Suggested PR title: `refactor(dash-production-cutover): complete python ui cutover`.
Required squash subject: same as PR title.
Base: exact `main` after PR291+PR292.
Merge method: squash only.
Priority: P0 mandatory cutover.
Depends on: PR291, PR292.
Scope: final Compose/CI/docs integration only.
Owned paths: `compose.yaml`, obsolete web CI/script references, runtime docs and cutover E2E only.
Tasks / Acceptance:
- [ ] Final long-running Compose services are exactly `postgres`, `app`, `project-bootstrap-worker`; temporary Dash and Node web services/profiles are removed.
- [ ] CI/local gate references that assumed React/Node are replaced with equivalent four-page Dash browser evidence without weakening Ruff/Pyright/unit/integration/coverage/architecture gates.
- [ ] Restart/project-switch evidence preserves project isolation, professional plots, DecisionArtifacts, typed availability, and Universe & History snapshots.
- [ ] Compose build/up/restart, browser E2E, architecture checks, and `uv run portfell-quality pr` pass from one SHA.
Parallelization: Agent A Compose/runtime cleanup; Agent B CI/E2E/docs. PR291/PR292 implementation files are read-only.
Security: final app secret boundary documented/tested.
Determinism: cutover manifest + route/evidence contracts.
Idempotency: build/start/restart create no duplicate business state.
Rollback: return to PR274 coexistence SHA.

## PR293 — Shared active-union market refresh

Branch: `feat/scheduled-union-refresh`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(scheduled-union-refresh): refresh active project market union once`.
Required squash subject: same as PR title.
Base: exact PR275 merge SHA.
Merge method: squash only.
Priority: P0 scheduled research.
Depends on: PR275.
Scope: shared market refresh stage only; no per-project statistics orchestration or cron trigger.
Owned paths: `src/portfell/scheduled_research/market_refresh.py`, tests.
Tasks / Acceptance:
- [ ] Build de-duplicated full-listing union across active projects and refresh quotes+dividends+splits once for the union.
- [ ] Preserve full listing identity, fetch each business key at most once per logical cycle, and emit immutable revision/count/failure summary.
- [ ] Re-run/resume reuses existing market business keys and does not duplicate rows.
- [ ] Two-project-overlap/failure/restart/idempotency tests plus `uv run portfell-quality pr` pass.
Parallelization: Agent A union/planner; Agent B idempotency/failure tests.
Security: trusted worker credential only; browser gets none.
Determinism: active project set + market window/revision.
Idempotency: business-key uniqueness/resume.
Rollback: remove shared scheduled refresh wrapper.

## PR294 — Per-project Uni -> Bi -> Multivariate research cycle

Branch: `feat/scheduled-project-research`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(scheduled-project-research): run project research dependency chain`.
Required squash subject: same as PR title.
Base: same exact PR275 merge SHA as PR293/PR295.
Merge method: squash only.
Priority: P0 scheduled research.
Depends on: PR275 and final manual run/evidence contracts.
Scope: one project cycle only; no market fetch and no cron trigger.
Owned paths: `scheduled_research/project_cycle.py`, tests.
Tasks / Acceptance:
- [ ] For one active project run/reuse Univariate -> Bivariate -> Multivariate strictly in dependency order using persisted settings/objective/constraints; default objective only when absent is `return_risk`.
- [ ] Reuse the same manual-run progress, DecisionArtifact, ResearchUniverseSnapshot, selection, and logical-run identities; no scheduler-only analytical implementation exists.
- [ ] Failure blocks only downstream stages for that project and returns typed terminal summary; restart/resume reuses unchanged successful logical runs.
- [ ] All-three-objective/failure/restart/two-project-order-independence fixtures plus `uv run portfell-quality pr` pass.
Parallelization: Agent A dependency orchestration; Agent B resume/failure/evidence tests.
Security: authorize project worker context before data.
Determinism: project revision/settings/algorithm versions.
Idempotency: logical run reuse.
Rollback: remove project-cycle wrapper.

## PR295 — Sunday scheduler, lock, and terminal cycle summary

Branch: `feat/scheduled-sunday-runner`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(scheduled-sunday-runner): add sunday schedule lock and summary`.
Required squash subject: same as PR title.
Base: same exact PR275 merge SHA as PR293/PR294.
Merge method: squash only.
Priority: P0 scheduled research.
Depends on: PR275.
Scope: schedule/lock/cycle coordination protocol only; detailed stages are PR293/PR294.
Owned paths: `scheduled_research/scheduler.py`, `cycle_summary.py`, schedule tests/docs.
Tasks / Acceptance:
- [ ] Freeze exact managed schedule `CRON_TZ=Europe/Vienna` and `0 9 * * 0`; no browser/fourth long-running service is introduced.
- [ ] Acquire one non-overlapping cycle lock, invoke shared market-refresh protocol once, then invoke project-cycle protocol in stable project order with failure isolation.
- [ ] Emit terminal cycle summary with stage reuse/run/failure counts and no secrets; concurrent trigger is rejected/reused rather than duplicated.
- [ ] Timezone/DST/concurrent-lock/stable-order/redaction tests plus `uv run portfell-quality pr` pass.
Parallelization: Agent A scheduler/lock; Agent B summary/timezone/concurrency tests.
Security: operations credential remains worker-side.
Determinism: exact cron + stable project order.
Idempotency: cycle lock + child logical identities.
Rollback: remove Sunday scheduler wrapper.

## PR276 — Sunday full-research integration, restart, and operations gate

Branch: `feat/weekly-full-research-refresh`.
Git status: not started.
PR: TBD.
Suggested PR title: `feat(weekly-full-research-refresh): integrate sunday research refresh`.
Required squash subject: same as PR title.
Base: exact `main` after PR293+PR294+PR295.
Merge method: squash only.
Priority: P0 final series gate.
Depends on: PR293, PR294, PR295.
Scope: integration/E2E/operations docs only; no new analytical algorithm.
Owned paths: scheduled-research integration tests, operations docs, final Compose cron entry/wiring if required by existing worker model.
Tasks / Acceptance:
- [ ] One Sunday-cycle integration test proves exactly one shared market refresh followed by Uni -> Bi -> Multivariate per active project, with project failures isolated.
- [ ] Restart/resume test proves no duplicate market keys, runs, winners, DecisionArtifacts, selections, or ResearchUniverseSnapshots.
- [ ] Manual and scheduled execution of identical immutable inputs expose identical evidence identities/semantics; two-project processing order does not change project results.
- [ ] Exact schedule, final three-service Compose topology, browser independence, operations docs, full quality gate, and final series completion evidence pass from one SHA.
Parallelization: Agent A integration wiring; Agent B restart/E2E/ops evidence. Child stage implementations are read-only.
Security: no browser credential path.
Determinism: child identities + exact schedule.
Idempotency: lock + logical identities + canonical sinks.
Rollback: disable/remove scheduled integration; published evidence remains auditable.

## Series completion gate

The series is complete only when every PR named in this addendum is merged and one final `main` evidence run proves all existing `BACKLOG.md` product/correctness/history/cutover/Sunday invariants plus:

- no active sibling PR owns an overlapping implementation file;
- no shared public contract was invented in a sibling implementation branch;
- exactly four browser workflow pages exist;
- final Compose services are exactly `postgres`, `app`, `project-bootstrap-worker`;
- the current canonical quality gates in `GATES.md` pass, including the current coverage threshold;
- no React/Node production UI remains;
- manual and Sunday runs reuse the same logical analytical/evidence contracts;
- two-project isolation survives project switching, restart, and scheduled processing order.
