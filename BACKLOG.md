Last reviewed: 2026-08-20

# Active Backlog

## Status authority

This file is the operational status index for the active Plotly Dash / Multivariate optimizer / production cutover / Sunday research series.

For **branch name, pushed head SHA, Git status, and GitHub-PR state**, the work-order table in this file is authoritative. `docs/backlog/parallel-weak-agent-execution-v2.md` remains authoritative for scope, owned paths, dependencies, Tasks / Acceptance, security, determinism, idempotency, and rollback. Older branch/status lines in detailed backlog documents are superseded by this table.

`Git status: pushed; validation pending` means an implementation commit exists on the named remote branch, but the work order is **not** considered green, merged, or accepted until its required quality evidence passes. No implementation branch in this table has been merged to `main` by this implementation run.

## Git naming contract

Every active implementation work order uses its PR key in both branch and Conventional Commit scope:

```text
Branch:  <type>/pr<NNN>-<scope>
Commit:  <type>(pr<NNN>-<scope>): <imperative subject>
```

Examples:

```text
feat/pr270-multivariate-pareto-selector
feat(pr270-multivariate-pareto-selector): add eligibility and pareto selection

refactor/pr275-dash-production-cutover
refactor(pr275-dash-production-cutover): complete python ui cutover
```

Allowed Conventional Commit types follow `GATES.md`. The PR key and branch scope must remain stable for all subsequent commits on a work-order branch.

The pre-existing planning PR #460 was opened before this naming rule on branch `docs/parallelize-open-backlog`; its title and all new commits now use the `pr460-parallelize-open-backlog` Conventional Commit scope. Runtime implementation work orders all use PR-key-bearing branch names.

## Active implementation authority

Implementation requirements, in precedence order:

1. this `BACKLOG.md` for live branch/status/head metadata and series invariants;
2. `docs/backlog/parallel-weak-agent-execution-v2.md` for atomic work orders and dependency/ownership boundaries;
3. `docs/backlog/current-code-correctness-amendment.md`;
4. `docs/backlog/current-code-project-isolation-addendum.md`;
5. `docs/backlog/universe-history-pipeline-amendment.md`;
6. `docs/backlog/plotly-dash-professional-plots-weekly-refresh.md`;
7. `docs/backlog/plotly-dash-multivariate-optimizer-ui.md`;
8. `docs/backlog/plotly-dash-multivariate-optimizer-ui-detailed-v1.md` for product/detail semantics not superseded above.

Historical files under `docs/backlog/archive/` are evidence only.

## Parallel Weak-Agent PR Design

- One atomic outcome per PR-sized work order.
- Parallel sibling branches start from the exact same predecessor integration SHA, never from a sibling branch.
- Siblings own non-overlapping implementation files/modules.
- Shared routes, IDs, objective registry, progress phases, DecisionArtifact stages/reasons, serialization, listing identity, history contracts, plot contracts, scheduler IDs, and fixture identities are frozen by predecessor work orders before siblings start.
- `Tasks / Acceptance` is the only acceptance checklist in the detailed work order.
- Weak agents may not opportunistically refactor unrelated modules, invent compatibility layers, rename unrelated contracts, or weaken gates.
- `GATES.md` is the only quality/coverage authority. Current merge coverage threshold is 95%.
- Integration/wave-base commits are internal dependency bases only; they are not product work orders and do not replace the named work-order branches below.

## Product invariants

The browser workflow is exactly:

```text
Metadata Builder
    -> Univariate Statistics
    -> Bivariate Statistics
    -> Multivariate Statistics
```

Multivariate Statistics is the only portfolio-optimizer page/run/stage. There is no separate Optimizer page.

Required primary controls are exactly:

- Univariate: `Compute univariate statistics`;
- Bivariate: `Compute bivariate statistics`;
- Multivariate: `Optimization objective` plus `Optimize portfolio`.

Multivariate objectives are exactly:

- `return_risk` — Return / Risk — default;
- `return_drawdown` — Return / Drawdown;
- `minimum_risk` — Minimum Risk.

Winner selection uses objective-specific walk-forward out-of-sample evidence only.

Required professional top-level plots remain:

- `Univariate Return / Risk Universe`;
- `Bivariate Return / Diversification Universe`;
- `Portfolio Candidate OOS Return / Risk`.

Full listing identity is `(isin, exchange, code)`. Unique ISIN count is display metadata only.

## Universe & History invariant

Every workflow page must expose server-produced/persisted Universe & History evidence. The pipeline order is fixed:

```text
Metadata -> Univariate -> Bivariate -> Multivariate -> Final portfolio
```

Observed history envelope is distinct from common usable history. Unavailable/not-run/blocked evidence is typed and is never represented by an invented zero, empty date, or guessed range.

Required evidence includes listing/unique-ISIN counts, stage removals/reasons, Univariate listing coverage, Bivariate exact pair/shared-history evidence, Multivariate aligned optimization history, every walk-forward train/test range, and final-refit common history.

## Production cutover invariant

The target production browser UI is Plotly Dash mounted into FastAPI. React/TypeScript/Vite/Node production UI is removed. Canonical browser routes are `/projects/<project_slug>/<suffix>` and REST remains under `/api`.

Final long-running Compose services are exactly:

```text
postgres
app
project-bootstrap-worker
```

## Scheduled research invariant

Managed schedule is exactly:

```text
CRON_TZ=Europe/Vienna
0 9 * * 0
```

One logical Sunday cycle performs one shared de-duplicated active-project quotes/dividends/splits refresh, then Univariate -> Bivariate -> Multivariate per active project using persisted settings/objective/constraints. Only an absent objective defaults to `return_risk`. Project failures are isolated and restart/resume must not duplicate market business keys, analytical runs, winners, selections, DecisionArtifacts, or ResearchUniverseSnapshots.

## PR458 planning gate

PR458 (`docs/current-code-correctness-backlog-review`) is merged and remains the completed planning gate that registered CCR-01 through CCR-13, project isolation, professional plotting, scheduled research, and Universe & History remediation requirements.

## Revised execution graph

```text
PR458 merged
   |
 PR264
   |
 PR277 || PR278
   |
 PR265 || PR266
   |
 PR267 || PR268
   |
 PR279 || PR280
   |
 PR269
   |
 PR281 || PR282 || PR283
   |
 PR270 || PR271 || PR284 || PR285
   |
 PR286
   |
 PR272 || PR273 -> PR287
   |
 PR288 || PR289 || PR290
   |
 PR274
   |
 PR291 || PR292
   |
 PR275
   |
 PR293 || PR294 || PR295
   |
 PR276
```

## Active Work-Order Index

All entries below have an implementation branch and at least one pushed Conventional Commit. Validation remains pending until the named work order's focused tests and canonical gates pass.

| Key | Branch | Head SHA | Priority | Depends on | Atomic outcome | Git status | GitHub PR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PR264 | `feat/pr264-dash-contract-registry` | `20e5d3e7c205` | P0 | PR458 | freeze Dash routes/IDs/gateway protocols | pushed; validation pending | not opened |
| PR277 | `feat/pr277-dash-temporary-runtime` | `ec36a3986828` | P0 | PR264 | temporary Dash runtime/container | pushed; validation pending | not opened |
| PR278 | `feat/pr278-dash-presentation-contracts` | `713350aef154` | P0 | PR264 | run-control/plot/availability contracts + fixtures | pushed; validation pending | not opened |
| PR265 | `feat/pr265-dash-research-shell` | `480f1e4bc0d7` | P1 | PR277, PR278 | shell/navigation | pushed; validation pending | not opened |
| PR266 | `feat/pr266-dash-metadata-builder` | `ee1a554e3897` | P1 | PR277, PR278 | Metadata page + initial history | pushed; validation pending | not opened |
| PR267 | `feat/pr267-dash-univariate-control` | `4f11095cdddc` | P0 | PR265, PR266 | Univariate control/page/callbacks | pushed; validation pending | not opened |
| PR268 | `feat/pr268-dash-bivariate-control` | `35686c33e367` | P0 | PR265, PR266 | Bivariate control/page/callbacks | pushed; validation pending | not opened |
| PR279 | `feat/pr279-dash-univariate-figures` | `fc88e0c9a36f` | P0 | PR267 | Univariate professional/history figures | pushed; validation pending | not opened |
| PR280 | `feat/pr280-dash-bivariate-figures` | `f60e54b79b10` | P0 | PR268 | Bivariate professional/history figures | pushed; validation pending | not opened |
| PR269 | `feat/pr269-multivariate-contract-registry` | `11ec6f828ab7` | P0 | PR279, PR280 | common Multivariate identity/serialization/protocol freeze | pushed; validation pending | not opened |
| PR281 | `feat/pr281-multivariate-run-contracts` | `a3a7d1053a2a` | P0 | PR269 | objective/settings/run/progress contracts | pushed; validation pending | not opened |
| PR282 | `feat/pr282-multivariate-decision-contracts` | `1482a4217c3d` | P0 | PR269 | DecisionArtifact/reason/sink contracts | pushed; validation pending | not opened |
| PR283 | `feat/pr283-multivariate-history-contracts` | `60f8d7de7187` | P0 | PR269 | ResearchUniverseSnapshot/history/isolation contracts | pushed; validation pending | not opened |
| PR270 | `feat/pr270-multivariate-pareto-selector` | `855aafe1954d` | P0 | PR281-PR283 | eligibility + Pareto selection | pushed; validation pending | not opened |
| PR271 | `feat/pr271-multivariate-solver-candidates` | `8bce65e11ee9` | P0 | PR281-PR283 | seven optimizer-method adapters | pushed; validation pending | not opened |
| PR284 | `feat/pr284-multivariate-redundancy-reducer` | `33885aac8036` | P0 | PR281-PR283 | deterministic Bivariate redundancy reduction | pushed; validation pending | not opened |
| PR285 | `feat/pr285-multivariate-risk-candidates` | `b6e4eb4eaca8` | P0 | PR281-PR283 | risk models + aligned-history candidate assembly | pushed; validation pending | not opened |
| PR286 | `feat/pr286-multivariate-algorithm-integration` | `257ba4bfb5e4` | P0 | PR270, PR271, PR284, PR285 | selector/candidate composition gate | pushed; validation pending | not opened |
| PR272 | `feat/pr272-multivariate-oos-orchestration` | `9e8ff2d5cdcf` | P0 | PR286 | walk-forward/OOS winner/final refit | pushed; validation pending | not opened |
| PR273 | `feat/pr273-multivariate-decision-persistence` | `191a8dd61292` | P0 | PR286 | decision/history schema + repositories | pushed; validation pending | not opened |
| PR287 | `feat/pr287-multivariate-read-api` | `1519538a9dd3` | P0 | PR273 | authorized read/lazy evidence projections | pushed; validation pending | not opened |
| PR288 | `feat/pr288-dash-multivariate-figures` | `0ca0797dd548` | P0 | PR272, PR287 | Multivariate candidate/Decision/History figures | pushed; validation pending | not opened |
| PR289 | `feat/pr289-dash-multivariate-callbacks` | `37e20e566e2c` | P0 | PR272, PR287 | Multivariate view-model/callbacks | pushed; validation pending | not opened |
| PR290 | `feat/pr290-dash-multivariate-layout` | `9bd27e862d6b` | P0 | PR272, PR287 | Multivariate page layout/CSS | pushed; validation pending | not opened |
| PR274 | `feat/pr274-dash-multivariate-integration` | `65ecb88e3c00` | P0 | PR288-PR290 | Multivariate UI integration gate | pushed; validation pending | not opened |
| PR291 | `refactor/pr291-dash-fastapi-mount` | `826f82cb00ec` | P0 | PR274 | mount Dash into FastAPI/canonical routes | pushed; validation pending | not opened |
| PR292 | `refactor/pr292-remove-react-ui` | `a3040708a848` | P0 | PR274 | delete React/Node production UI | pushed; validation pending | not opened |
| PR275 | `refactor/pr275-dash-production-cutover` | `6249cffa1ba9` | P0 | PR291, PR292 | final Compose/CI/evidence cutover gate | pushed; validation pending | not opened |
| PR293 | `feat/pr293-scheduled-union-refresh` | `f17d1adc47c7` | P0 | PR275 | shared active-union market refresh | pushed; validation pending | not opened |
| PR294 | `feat/pr294-scheduled-project-research` | `04719d06d9eb` | P0 | PR275 | one-project Uni -> Bi -> Multivariate cycle | pushed; validation pending | not opened |
| PR295 | `feat/pr295-scheduled-sunday-runner` | `8ae164e84026` | P0 | PR275 | scheduler/lock/terminal summary | pushed; validation pending | not opened |
| PR276 | `feat/pr276-weekly-full-research-refresh` | `1185f792bff5` | P0 | PR293-PR295 | Sunday integration/restart/operations gate | pushed; validation pending | not opened |

## Parallel implementation bases

The implementation used internal multi-parent integration bases to preserve exact same-predecessor sibling semantics without touching `main`. These are dependency bases, not product PRs:

- PR277/PR278 -> `7b637168ab51`;
- PR265/PR266 -> `b916f159aac9`;
- PR267/PR268 -> `33830d036784`;
- PR279/PR280 -> `4c23b7c06008`;
- PR281/PR282/PR283 -> `6c828ba7d068`;
- PR270/PR271/PR284/PR285 -> `03340cd370b4`;
- PR272 plus PR273->PR287 -> `e1089442093e`;
- PR288/PR289/PR290 -> `1ab8b68136be`;
- PR291/PR292 -> `6c6036a7cfe5`;
- PR293/PR294/PR295 -> `6f59a9180039`.

No internal wave-base branch is a substitute for its work-order branches and none is marked accepted merely because the integration commit exists.

## Parallel capacity achieved

- Foundation: 2 siblings — PR277, PR278.
- Basic Dash: 2 siblings — PR265, PR266.
- Statistics controls: 2 siblings — PR267, PR268.
- Statistics figures/history: 2 siblings — PR279, PR280.
- Multivariate contracts: 3 siblings — PR281, PR282, PR283.
- Multivariate algorithms: 4 siblings — PR270, PR271, PR284, PR285.
- Core Multivariate runtime/persistence: PR272 parallel to PR273, with PR287 following the persistence branch.
- Multivariate Dash: 3 siblings — PR288, PR289, PR290.
- Production cutover preparation: 2 siblings — PR291, PR292.
- Sunday research: 3 siblings — PR293, PR294, PR295.

## Series Completion Gate

Implementation branches being pushed is not sufficient for completion. The series becomes complete only after required work-order validation and one clean final `main` evidence run prove:

- CCR-01 through CCR-13 remediation requirements pass;
- exactly four browser workflow pages exist and Multivariate Statistics is the only optimizer page/run/stage;
- Uni/Bi/Multi controls, status, reload, failure, stale-result, duplicate-start, and two-project isolation behavior pass;
- exactly three Multivariate objectives are available and the winner is selected from OOS evidence with frozen tie-breaks;
- every production figure satisfies `ProfessionalPlotContract` and deterministic/unavailable/accessibility requirements;
- Universe & History evidence is revision-backed and keeps history envelope separate from common usable history;
- selector/candidate production paths do not enumerate several-hundred-dimensional asset subsets/weight grids;
- persisted DecisionArtifacts and ResearchUniverseSnapshots are immutable, project scoped, idempotent, and conflict-safe;
- React/TypeScript/Vite/Node production UI is absent;
- final Compose contains exactly `postgres`, `app`, `project-bootstrap-worker`;
- Sunday schedule remains exactly `09:00 Europe/Vienna`, performs one active-union market refresh, and reuses manual analytical/evidence contracts;
- restart/resume and project processing order do not create duplicate or cross-project evidence;
- Ruff, format, Pyright, architecture/schema/security checks, four Unit shards, four Integration shards, production app image/Compose validation, and the current 95% combined merge coverage threshold pass from one SHA.

## Known validation state

The implementation run intentionally does **not** mark these branches green. Before merge, quality evidence must resolve at least the following:

- full focused/unit/integration test coverage for the newly added modules;
- strict Pyright and Ruff/format evidence on each merge candidate;
- production Dash dependency/lock policy validation (the container currently pins Dash explicitly while repository-wide dependency lock synchronization still requires validation);
- final wiring evidence proving the persisted Multivariate read projections are registered in the hosted API runtime;
- final wiring evidence proving the Sunday schedule is instantiated by the existing long-running worker with a concrete production `SundayRuntime` adapter;
- browser/E2E evidence proving the mounted Dash pages consume authorized server data rather than only static/idle presentation placeholders;
- combined 95% coverage after the React test suite is removed and replaced by Dash/Python evidence.

These gaps are validation/integration blockers, not reasons to mark any work-order branch merged or complete prematurely.

## Historical backlog archive

`docs/backlog/archive/BACKLOG-2026-08-16-before-dash-optimizer.md` and `docs/backlog/archive/plotly-dash-three-page-research-ui-v1.md` are historical evidence only and must not override this file or the active authority documents.
