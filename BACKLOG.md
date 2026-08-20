Last reviewed: 2026-08-20

# Active Backlog

## Authority

This file is the active execution index. Detailed acceptance criteria and path ownership remain in `docs/backlog/parallel-weak-agent-execution-v2.md`; correctness, project-isolation, professional-plot, Universe & History, and Sunday-refresh semantics remain governed by the active documents under `docs/backlog/`.

`GATES.md` is the only quality-gate and coverage-threshold authority.

## Git Execution Rules

- Every implementation branch contains its work-order PR key: `<type>/prNNN-<scope>`.
- Every new implementation commit uses Conventional Commits and contains the same PR key in its scope, for example `feat(pr293-scheduled-union-refresh): ...`.
- Parallel siblings branch from the same predecessor SHA and do not depend on partially completed sibling branches.
- Work remains unmerged until the maintainer explicitly requests a merge to `main`.
- `implemented` means code exists on the named branch. It does not imply that `main` contains the code or that all hosted CI checks have passed.

## Product Invariants

The browser workflow remains exactly:

```text
Metadata Builder
    -> Univariate Statistics
    -> Bivariate Statistics
    -> Multivariate Statistics
```

Multivariate Statistics is the only portfolio-optimizer page/stage. Its objectives remain exactly `return_risk` (default), `return_drawdown`, and `minimum_risk`, with winner selection based on walk-forward out-of-sample evidence.

Every workflow page must preserve persisted/server-produced Universe & History evidence. Full listing identity is `(isin, exchange, code)`; unique ISIN count is display metadata only.

The final runtime target is one Python FastAPI + Dash application with long-running Compose services exactly `postgres`, `app`, and `project-bootstrap-worker`; React/TypeScript/Vite/Node production UI is removed by the cutover work.

The scheduled research contract remains exactly:

```text
CRON_TZ=Europe/Vienna
0 9 * * 0

shared active-project market union refresh once
  -> Univariate per active project
  -> Bivariate after successful Univariate
  -> Multivariate after successful Bivariate
  -> terminal cycle summary
```

## Active Work-Order Index

All work orders now have PR-ID-bearing branches. Git status below reflects repository branch state as of 2026-08-20; none of these implementation branches is represented here as merged to `main`.

| Key | Git branch | Priority | Depends on | Atomic outcome | Git status | GitHub PR |
| --- | --- | --- | --- | --- | --- | --- |
| PR264 | `feat/pr264-dash-contract-registry` | P0 | PR458 | freeze Dash routes/IDs/gateway protocols | implemented on branch; validation pending | not opened |
| PR277 | `feat/pr277-dash-temporary-runtime` | P0 | PR264 | temporary Dash runtime/container only | implemented on branch; validation pending | not opened |
| PR278 | `feat/pr278-dash-presentation-contracts` | P0 | PR264 | run-control/plot/availability contracts + fixtures | implemented on branch; validation pending | not opened |
| PR265 | `feat/pr265-dash-research-shell` | P1 | PR277, PR278 | shell/navigation only | implemented on branch; validation pending | not opened |
| PR266 | `feat/pr266-dash-metadata-builder` | P1 | PR277, PR278 | Metadata page + initial history only | implemented on branch; validation pending | not opened |
| PR267 | `feat/pr267-dash-univariate-control` | P0 | PR265, PR266 | Univariate control/page/callbacks | implemented on branch; validation pending | not opened |
| PR268 | `feat/pr268-dash-bivariate-control` | P0 | PR265, PR266 | Bivariate control/page/callbacks | implemented on branch; validation pending | not opened |
| PR279 | `feat/pr279-dash-univariate-figures` | P0 | PR267 | Univariate professional/history figures | implemented on branch; validation pending | not opened |
| PR280 | `feat/pr280-dash-bivariate-figures` | P0 | PR268 | Bivariate professional/history figures | implemented on branch; validation pending | not opened |
| PR269 | `feat/pr269-multivariate-contract-registry` | P0 | PR279, PR280 | common Multivariate identity/serialization/protocol freeze | implemented on branch; validation pending | not opened |
| PR281 | `feat/pr281-multivariate-run-contracts` | P0 | PR269 | objective/settings/run/progress contracts | implemented on branch; validation pending | not opened |
| PR282 | `feat/pr282-multivariate-decision-contracts` | P0 | PR269 | DecisionArtifact/reason/sink contracts | implemented on branch; validation pending | not opened |
| PR283 | `feat/pr283-multivariate-history-contracts` | P0 | PR269 | ResearchUniverseSnapshot/history/isolation contracts | implemented on branch; validation pending | not opened |
| PR270 | `feat/pr270-multivariate-pareto-selector` | P0 | PR281-PR283 | eligibility + Pareto stages | implemented on branch; validation pending | not opened |
| PR271 | `feat/pr271-multivariate-solver-candidates` | P0 | PR281-PR283 | seven optimizer-method adapters | implemented on branch; validation pending | not opened |
| PR284 | `feat/pr284-multivariate-redundancy-reducer` | P0 | PR281-PR283 | deterministic Bivariate redundancy stage | implemented on branch; validation pending | not opened |
| PR285 | `feat/pr285-multivariate-risk-candidates` | P0 | PR281-PR283 | risk models + aligned-history candidate assembly | implemented on branch; validation pending | not opened |
| PR286 | `feat/pr286-multivariate-algorithm-integration` | P0 | PR270, PR271, PR284, PR285 | selector/candidate composition gate | implemented on branch; validation pending | not opened |
| PR272 | `feat/pr272-multivariate-oos-orchestration` | P0 | PR286 | walk-forward/OOS winner/final refit | implemented on branch; validation pending | not opened |
| PR273 | `feat/pr273-multivariate-decision-persistence` | P0 | PR286 | decision/history persistence | implemented on branch; validation pending | not opened |
| PR287 | `feat/pr287-multivariate-read-api` | P0 | PR273 | authorized read/lazy evidence projections | implemented on branch; validation pending | not opened |
| PR288 | `feat/pr288-dash-multivariate-figures` | P0 | PR272, PR287 | Multivariate candidate/Decision/History figures | implemented on branch; validation pending | not opened |
| PR289 | `feat/pr289-dash-multivariate-callbacks` | P0 | PR272, PR287 | Multivariate view-model/callbacks | implemented on branch; validation pending | not opened |
| PR290 | `feat/pr290-dash-multivariate-layout` | P0 | PR272, PR287 | Multivariate page layout/CSS | implemented on branch; validation pending | not opened |
| PR274 | `feat/pr274-dash-multivariate-integration` | P0 | PR288-PR290 | Multivariate UI wiring + browser evidence | implemented on branch; validation pending | not opened |
| PR291 | `refactor/pr291-dash-fastapi-mount` | P0 | PR274 | mount Dash into FastAPI/canonical routes | implemented on branch; validation pending | not opened |
| PR292 | `refactor/pr292-remove-react-ui` | P0 | PR274 | delete React/Node production UI | implemented on branch; validation pending | not opened |
| PR275 | `refactor/pr275-dash-production-cutover` | P0 | PR291, PR292 | final Compose/CI/evidence cutover gate | implemented on branch; validation pending | not opened |
| PR293 | `feat/pr293-scheduled-union-refresh` | P0 | PR275 | shared active-union market refresh | implemented + focused tests on branch | not opened |
| PR294 | `feat/pr294-scheduled-project-research` | P0 | PR275 | one-project Uni -> Bi -> Multi cycle | implemented + focused tests on branch | not opened |
| PR295 | `feat/pr295-scheduled-sunday-runner` | P0 | PR275 | scheduler/lock/terminal summary | implemented + focused tests on branch | not opened |
| PR276 | `feat/pr276-weekly-full-research-refresh` | P0 | PR293-PR295 | Sunday integration/restart/ops gate | implemented + integration test on branch | not opened |

## Parallel Execution Waves

```text
PR264
  -> PR277 || PR278
  -> PR265 || PR266
  -> PR267 || PR268
  -> PR279 || PR280
  -> PR269
  -> PR281 || PR282 || PR283
  -> PR270 || PR271 || PR284 || PR285
  -> PR286
  -> PR272 || PR273
  -> PR287
  -> PR288 || PR289 || PR290
  -> PR274
  -> PR291 || PR292
  -> PR275
  -> PR293 || PR294 || PR295
  -> PR276
```

The 3-way and 4-way waves are intentionally safe because their public contracts are frozen by predecessor work orders and their implementation ownership is disjoint.

## Series Completion Gate

Before any request to land the series on `main`, one integrated candidate SHA must prove:

- CCR-01 through CCR-13 remediation requirements pass;
- exactly four workflow pages exist and Multivariate Statistics is the only optimizer page/run/stage;
- Uni/Bi/Multi calculation controls, progress, failure/reload, stale state, and duplicate-start protection work;
- exactly the three frozen Multivariate objectives are available and OOS evidence determines the winner;
- every production Plotly figure satisfies `ProfessionalPlotContract`;
- persisted Universe & History evidence remains project-scoped and deterministic through switching/restart;
- no exhaustive several-hundred-instrument subset/weight-grid production path exists;
- React/TypeScript/Vite/Node production UI is absent;
- final Compose services are exactly `postgres`, `app`, `project-bootstrap-worker`;
- Sunday schedule is exactly 09:00 Europe/Vienna and market data refreshes once for the de-duplicated active-project union;
- scheduled and manual analytical execution reuse the same run/evidence identities;
- project failures are isolated and restart/resume does not duplicate market keys, runs, winners, DecisionArtifacts, selections, or ResearchUniverseSnapshots;
- all canonical checks in `GATES.md` pass from the integrated SHA.

## Historical Backlog Archive

Historical backlog files under `docs/backlog/archive/` are evidence only and do not override this active index or the active execution addendum.
