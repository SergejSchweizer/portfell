Last reviewed: 2026-08-20

# Active Backlog

## Authority

This file is the active execution index for the Plotly Dash replacement UI, Multivariate Statistics optimizer, Python/FastAPI production cutover, and scheduled Sunday full-research refresh.

Detailed scope, acceptance criteria, dependency rules, and path ownership remain in `docs/backlog/parallel-weak-agent-execution-v2.md` and the active amendments under `docs/backlog/`. `GATES.md` is the only quality-gate and coverage-threshold authority.

## Git execution rules

- Every implementation branch contains its work-order key: `<type>/prNNN-<scope>`.
- Every implementation commit uses Conventional Commits and contains the same PR key in its scope.
- Parallel siblings branch from the same predecessor integration state and never depend on a partially completed sibling.
- Sibling implementation ownership is disjoint; integration PRs compose owner surfaces rather than re-implementing them.
- `implemented` means the work exists on the named branch. It does not mean the work has landed on `main`.
- All work-order PRs remain draft/open until the maintainer explicitly requests landing them.
- Hosted validation is not green while the GitHub Actions jobs fail before executing normal job steps; this status must not be represented as passing CI.

## Product invariants

The browser workflow is exactly:

```text
Metadata Builder
  -> Univariate Statistics
  -> Bivariate Statistics
  -> Multivariate Statistics
```

Multivariate Statistics is the only portfolio-optimizer page/stage. Objectives are exactly `return_risk` (default), `return_drawdown`, and `minimum_risk`; winner selection uses walk-forward out-of-sample evidence.

Full listing identity is `(isin, exchange, code)`. Universe & History evidence is server-produced/persisted and remains project-scoped.

The production browser runtime is Python FastAPI + Plotly Dash. React/TypeScript/Vite/Node production UI is removed. Long-running Compose services are exactly `postgres`, `app`, and `project-bootstrap-worker`.

The managed research schedule is exactly:

```text
CRON_TZ=Europe/Vienna
0 9 * * 0
```

One logical Sunday cycle refreshes the de-duplicated active-project market union once, then runs Univariate -> Bivariate -> Multivariate per active project with project-isolated failure and idempotent restart/resume semantics.

## Open work-order PR index

All 32 work-order PRs are implemented on PR-key-bearing branches and are currently open drafts. `Head` is the current branch head recorded during this execution pass.

| Key | GitHub PR | Git branch | Depends on | Atomic outcome | Head | Git status |
| --- | ---: | --- | --- | --- | --- | --- |
| PR264 | #461 | `feat/pr264-dash-contract-registry` | PR458 | freeze Dash routes/IDs/gateway protocols | `2180ee480781` | implemented; open draft; validation not green |
| PR277 | #462 | `feat/pr277-dash-temporary-runtime` | PR264 | temporary Dash runtime/container only | `008f57230808` | implemented; open draft; validation not green |
| PR278 | #463 | `feat/pr278-dash-presentation-contracts` | PR264 | run-control/plot/availability contracts | `d2a9ad41e0af` | implemented; open draft; validation not green |
| PR265 | #464 | `feat/pr265-dash-research-shell` | PR277, PR278 | shell/navigation only | `14846371f078` | implemented; open draft; validation not green |
| PR266 | #465 | `feat/pr266-dash-metadata-builder` | PR277, PR278 | Metadata page/view-model/callback ownership | `9d64b7358a49` | implemented; open draft; validation not green |
| PR267 | #466 | `feat/pr267-dash-univariate-control` | PR265, PR266 | Univariate control/page/start-poll callbacks | `323a4898e263` | implemented; open draft; validation not green |
| PR268 | #467 | `feat/pr268-dash-bivariate-control` | PR265, PR266 | Bivariate control/page/start-poll callbacks | `823dd79730db` | implemented; open draft; validation not green |
| PR279 | #468 | `feat/pr279-dash-univariate-figures` | PR267 | Univariate professional/history figures | `65a77885ef9e` | implemented; open draft; validation not green |
| PR280 | #469 | `feat/pr280-dash-bivariate-figures` | PR268 | Bivariate professional/history figures | `0d67972b57d7` | implemented; open draft; validation not green |
| PR269 | #470 | `feat/pr269-multivariate-contract-registry` | PR279, PR280 | Multivariate identity/serialization/protocol freeze | `649ad7fd9159` | implemented; open draft; validation not green |
| PR281 | #471 | `feat/pr281-multivariate-run-contracts` | PR269 | objective/settings/run/progress contracts | `1f0a52e68e95` | implemented; open draft; validation not green |
| PR282 | #472 | `feat/pr282-multivariate-decision-contracts` | PR269 | DecisionArtifact/reason contracts | `74105c89d677` | implemented; open draft; validation not green |
| PR283 | #473 | `feat/pr283-multivariate-history-contracts` | PR269 | ResearchUniverseSnapshot/history/isolation contracts | `f8de9ecd9b10` | implemented; open draft; validation not green |
| PR270 | #474 | `feat/pr270-multivariate-pareto-selector` | PR281-PR283 | eligibility + Pareto selector | `0d91bdb4d8d6` | implemented; open draft; validation not green |
| PR271 | #475 | `feat/pr271-multivariate-solver-candidates` | PR281-PR283 | optimizer-method candidate adapters | `a28a84f68aa3` | implemented; open draft; validation not green |
| PR284 | #476 | `feat/pr284-multivariate-redundancy-reducer` | PR281-PR283 | deterministic redundancy reducer | `cadba8d4bb60` | implemented; sibling ownership cleaned; open draft |
| PR285 | #477 | `feat/pr285-multivariate-risk-candidates` | PR281-PR283 | risk models + aligned-history candidates | `484f09dc34f5` | implemented; sibling ownership cleaned; open draft |
| PR286 | #478 | `feat/pr286-multivariate-algorithm-integration` | PR270, PR271, PR284, PR285 | selector/candidate composition | `fbac620c31ad` | implemented; open draft; validation not green |
| PR272 | #479 | `feat/pr272-multivariate-oos-orchestration` | PR286 | walk-forward/OOS winner/final refit | `4661ce6046ab` | implemented; focused tests committed; open draft |
| PR273 | #480 | `feat/pr273-multivariate-decision-persistence` | PR286 | decision/history persistence and migration | `c67f0e93b01b` | implemented; focused tests committed; open draft |
| PR287 | #481 | `feat/pr287-multivariate-read-api` | PR273 | authorized current/run/section/history read API | `b99e7561a630` | implemented; focused tests committed; open draft |
| PR288 | #482 | `feat/pr288-dash-multivariate-figures` | PR272, PR287 | Multivariate candidate/decision/history figures | `e3dca841c5b8` | implemented; open draft; validation not green |
| PR289 | #483 | `feat/pr289-dash-multivariate-callbacks` | PR272, PR287 | objective/settings-aware Multivariate callbacks | `676f9164c7b5` | implemented; owner callbacks/tests committed; open draft |
| PR290 | #484 | `feat/pr290-dash-multivariate-layout` | PR272, PR287 | Multivariate page layout/CSS | `97d0605b5190` | implemented; open draft; validation not green |
| PR274 | #485 | `feat/pr274-dash-multivariate-integration` | PR288-PR290 | Multivariate UI composition/browser evidence | `cc01f1218e56` | implemented; open draft; validation not green |
| PR291 | #486 | `refactor/pr291-dash-fastapi-mount` | PR274 | FastAPI mount/routing + owner callback registration | `96d118064b00` | integrated current owner surfaces; open draft |
| PR292 | #487 | `refactor/pr292-remove-react-ui` | PR274 | delete React/Node production UI | `e1848b14e131` | implemented; open draft; validation not green |
| PR275 | #488 | `refactor/pr275-dash-production-cutover` | PR291, PR292 | final Compose/CI/runtime cutover | `b5b18e1ea4cc` | integrated current PR291/PR292/core owners; open draft |
| PR293 | #489 | `feat/pr293-scheduled-union-refresh` | PR275 | shared active-union market refresh | `63adcd9c87b3` | implemented on current PR275 state; open draft |
| PR294 | #490 | `feat/pr294-scheduled-project-research` | PR275 | one-project Uni -> Bi -> Multi scheduled chain | `cc8826adafea` | implemented on current PR275 state; open draft |
| PR295 | #491 | `feat/pr295-scheduled-sunday-runner` | PR275 | Sunday scheduler/lock/terminal summary | `847f2077cf72` | implemented on current PR275 state; open draft |
| PR276 | #492 | `feat/pr276-weekly-full-research-refresh` | PR293-PR295 | final Sunday integration/restart/ops gate | `9ca82cd10c36` | final owner-head integration assembled; open draft |

## Maximum-parallel execution graph

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

The 3-way and 4-way waves remain independent siblings. Integration branches consume the latest owner heads explicitly; stale internal wave bases must never become a second implementation authority.

## Series completion gate

Before landing the series on `main`, one integrated candidate SHA must prove all canonical `GATES.md` requirements, including:

- exactly four workflow pages and no separate optimizer page;
- exactly the three frozen Multivariate objectives;
- objective-specific OOS winner selection and deterministic final refit;
- project-scoped persistence/read isolation and Universe & History evidence;
- explicit Uni/Bi/Multi start/progress/failure/stale/duplicate-start behavior;
- production Plotly figure contracts;
- FastAPI + Dash only, with React/Node production UI absent;
- Compose services exactly `postgres`, `app`, `project-bootstrap-worker`;
- exact Sunday 09:00 Europe/Vienna scheduling;
- one market refresh for the active-project union per logical cycle;
- manual/scheduled reuse of the same analytical identities;
- project failure isolation and duplicate-free restart/resume;
- combined merge coverage at the `GATES.md` threshold of 95%.

Historical backlog files under `docs/backlog/archive/` remain evidence only.
