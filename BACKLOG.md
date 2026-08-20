Last reviewed: 2026-08-20

# Active Backlog

## Backlog Policy

This file is the active index for the Plotly Dash replacement UI, Multivariate Statistics portfolio optimizer, professional decision visualization, continuous Universe & History evidence, React/Docker cutover, scheduled full research refresh, and correctness/project-isolation remediation.

Active implementation authority, in precedence order, is:

1. `docs/backlog/parallel-weak-agent-execution-v2.md` for PR boundaries, dependency graph, branch ownership, parallelization, and exact weak-agent work orders;
2. `docs/backlog/current-code-correctness-amendment.md`;
3. `docs/backlog/current-code-project-isolation-addendum.md`;
4. `docs/backlog/universe-history-pipeline-amendment.md`;
5. `docs/backlog/plotly-dash-professional-plots-weekly-refresh.md`;
6. `docs/backlog/plotly-dash-multivariate-optimizer-ui.md`;
7. `docs/backlog/plotly-dash-multivariate-optimizer-ui-detailed-v1.md` for product/detail semantics not superseded by item 1.

Historical files under `docs/backlog/archive/` are evidence only.

The former PR264-PR276 implementation boundaries were too broad for weak agents. Their business outcomes remain active, but the merge-unit boundaries and dependency graph are now superseded by `parallel-weak-agent-execution-v2.md`.

Every active work-order row below has an exact detailed definition in that addendum containing `Branch`, `Git status`, `PR`, `Suggested PR title`, `Required squash subject`, `Base`, `Merge method`, `Priority`, `Depends on`, `Scope`, `Owned paths`, `Tasks / Acceptance`, `Parallelization`, `Security`, `Determinism`, `Idempotency`, and `Rollback`.

## Parallel Weak-Agent PR Design

Before implementation begins, every active PR must satisfy all of these rules:

- One atomic outcome. Split anything containing two independently testable runtime behaviors.
- Parallel sibling PRs branch from the exact same predecessor merge SHA and never from each other.
- Every sibling owns explicit, non-overlapping files/modules. Overlapping ownership is forbidden.
- Shared routes, component IDs, objective IDs, progress phases, DecisionArtifact stage IDs, reason codes, serialization, listing identity, snapshot fields, plot contracts, cron stage IDs, and fixture IDs are frozen by a predecessor PR before sibling implementation begins.
- `Tasks / Acceptance` is the only checklist. Every checkbox names both implementation and machine-verifiable evidence.
- Agent A and Agent B receive disjoint ownership inside each PR. A hand-off exists only when written in the work order.
- Weak agents may not perform opportunistic refactors, rename unrelated modules, add compatibility layers, weaken a quality gate, or infer a new architecture.
- Focused tests run first; then the canonical `uv run portfell-quality pr`. Runtime/UI PRs also run the Docker/Compose/E2E evidence named in their work order.
- `GATES.md` is the only coverage/quality threshold authority. The current documented merge threshold is 95%; no backlog work order may restate a weaker threshold.
- With only two available agents in a 3-way or 4-way wave, start any two siblings first and then start the remaining sibling(s) from the **same predecessor SHA**, not from a partially merged sibling.

For this active series, the sibling-branch rule above supersedes older generic wording that says UI branches must stack on each other.

## Product And UI Invariants

The browser workflow is exactly:

```text
Metadata Builder
    -> Univariate Statistics
    -> Bivariate Statistics
    -> Multivariate Statistics
```

**Multivariate Statistics is the portfolio optimizer.** There is no separate Optimizer page, route, workflow stage, scheduled stage, status surface, or post-Multivariate step. Selector, risk-model, solver, walk-forward, ranking, DecisionArtifact, and final-refit modules are internal components of one Multivariate Statistics run.

Each statistics page has exactly one explicit calculation surface:

- Univariate: `Compute univariate statistics` + progress/status/failure;
- Bivariate: `Compute bivariate statistics` + progress/status/failure;
- Multivariate: `Optimization objective` + `Optimize portfolio` + progress/status/failure.

Multivariate objectives are exactly:

- `return_risk` — `Return / Risk` — default;
- `return_drawdown` — `Return / Drawdown`;
- `minimum_risk` — `Minimum Risk`.

Winner selection is objective-specific and uses walk-forward out-of-sample evidence only.

Required professional top-level plots remain:

- Univariate: `Univariate Return / Risk Universe`, X=`Annualized volatility (% p.a.)`, Y=`Annualized geometric return (% p.a.)`;
- Bivariate: `Bivariate Return / Diversification Universe`, Y=`Annualized geometric return (% p.a.)`, dynamic named median-dependence X axis;
- Multivariate: `Portfolio Candidate OOS Return / Risk`, X=`OOS annualized volatility (% p.a.)`, Y=`OOS annualized return (% p.a.)`.

The replacement Dash UI temporarily coexists with React. The production cutover deletes React/TypeScript/Vite/Node browser UI, mounts Dash into FastAPI, removes `/dash` from canonical browser routes, and leaves exactly `postgres`, `app`, `project-bootstrap-worker` as long-running Compose services.

## Universe And History Invariant

Every workflow page shows one persistent `Universe & History` summary and one `Research Universe & History Pipeline` visualization before page-specific analytical tabs.

The UI must expose server-produced/persisted evidence for:

- current full-listing count and unique-ISIN count;
- removals since the previous stage and exact reason;
- `Observed history envelope` separately from `Common usable history`;
- exact common start/end/observation count when a joint calendar exists;
- Univariate listing-history min/median/max plus `Univariate Listing History Coverage`;
- Bivariate exact pair count, pairwise shared-observation min/median/max plus `Pairwise Shared-History Distribution`;
- Multivariate aligned optimization calendar plus `Walk-Forward Training / Test Coverage`;
- final portfolio holding count plus exact final-refit common range/observation count.

Stage order is fixed:

```text
Metadata -> Univariate -> Bivariate -> Multivariate -> Final portfolio
```

Future/not-run/blocked stages remain visible with typed state. Unavailable/not-applicable history is never represented as `0`, empty date, or guessed value. Dash never derives these ranges/counts from raw rows.

Full listing identity is `(isin, exchange, code)`. Unique ISIN count is display metadata only and may never replace listing identity.

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

Market data is fetched once for the active union, never once per project. Within a project, Bivariate waits for successful Univariate and Multivariate waits for successful Bivariate. Failures are project-isolated. Re-run/resume must not create duplicate market business keys, analytical runs, winners, DecisionArtifacts, selections, or ResearchUniverseSnapshots.

## PR458 Planning Gate

### PR458. Current-Code Correctness Hardening, Project Isolation, And Research-Evidence Contract Registration

Branch: `docs/current-code-correctness-backlog-review`.
Git status: merged.
PR: GitHub PR #458, merged.
Priority: P0 planning gate, complete.
Base: reviewed `main` at `69d76a108257a9d07dd8e22a918ae789942afc07`.
Outcome: CCR-01 through CCR-13, project-scoped selection isolation, professional plotting/weekly-refresh authority, and mandatory Universe & History requirements were registered for implementation.

## Revised Execution Graph

```text
PR458 merged
   |
 PR264 contract registry
   |
   +-----------------------+
   |                       |
 PR277 runtime          PR278 presentation contracts
   |                       |
   +-----------+-----------+
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
        PR272 || PR273
                  |
                PR287
               \ /
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

The exact predecessor SHA, exclusive owned paths, tasks/acceptance, intra-PR Agent A/B split, and validation evidence are defined in `docs/backlog/parallel-weak-agent-execution-v2.md`.

## Active Work-Order Index

`Git status: not started` and `PR: TBD` are intentional until implementation begins.

| Key | Branch | Priority | Depends on | Atomic outcome | Git status | PR |
| --- | --- | --- | --- | --- | --- | --- |
| PR264 | `feat/dash-contract-registry` | P0 | PR458 | freeze Dash routes/IDs/gateway protocols | not started | TBD |
| PR277 | `feat/dash-temporary-runtime` | P0 | PR264 | temporary Dash runtime/container only | not started | TBD |
| PR278 | `feat/dash-presentation-contracts` | P0 | PR264 | run-control/plot/availability contracts + fixtures | not started | TBD |
| PR265 | `feat/dash-research-shell` | P1 | PR277, PR278 | shell/navigation only | not started | TBD |
| PR266 | `feat/dash-metadata-builder` | P1 | PR277, PR278 | Metadata page + initial history only | not started | TBD |
| PR267 | `feat/dash-univariate-control` | P0 | PR265, PR266 | Univariate control/page/callbacks | not started | TBD |
| PR268 | `feat/dash-bivariate-control` | P0 | PR265, PR266 | Bivariate control/page/callbacks | not started | TBD |
| PR279 | `feat/dash-univariate-figures` | P0 | PR267 | Univariate professional/history figures | not started | TBD |
| PR280 | `feat/dash-bivariate-figures` | P0 | PR268 | Bivariate professional/history figures | not started | TBD |
| PR269 | `feat/multivariate-contract-registry` | P0 | PR279, PR280 | common Multi identity/serialization/protocol freeze | not started | TBD |
| PR281 | `feat/multivariate-run-contracts` | P0 | PR269 | objective/settings/run/progress contracts | not started | TBD |
| PR282 | `feat/multivariate-decision-contracts` | P0 | PR269 | DecisionArtifact/reason/sink contracts | not started | TBD |
| PR283 | `feat/multivariate-history-contracts` | P0 | PR269 | ResearchUniverseSnapshot/history/isolation contracts | not started | TBD |
| PR270 | `feat/multivariate-pareto-selector` | P0 | PR281-PR283 | eligibility + Pareto stages | not started | TBD |
| PR271 | `feat/multivariate-solver-candidates` | P0 | PR281-PR283 | seven optimizer-method adapters | not started | TBD |
| PR284 | `feat/multivariate-redundancy-reducer` | P0 | PR281-PR283 | deterministic Bivariate redundancy stage | not started | TBD |
| PR285 | `feat/multivariate-risk-candidates` | P0 | PR281-PR283 | risk models + aligned-history candidate assembly | not started | TBD |
| PR286 | `feat/multivariate-algorithm-integration` | P0 | PR270, PR271, PR284, PR285 | selector/candidate composition gate | not started | TBD |
| PR272 | `feat/multivariate-oos-orchestration` | P0 | PR286 | walk-forward/OOS winner/final refit | not started | TBD |
| PR273 | `feat/multivariate-decision-persistence` | P0 | PR286 | decision/history schema + repositories | not started | TBD |
| PR287 | `feat/multivariate-read-api` | P0 | PR273 | authorized read/lazy evidence projections | not started | TBD |
| PR288 | `feat/dash-multivariate-figures` | P0 | PR272, PR287 | Multi candidate/Decision/History figures | not started | TBD |
| PR289 | `feat/dash-multivariate-callbacks` | P0 | PR272, PR287 | Multi view-model/callbacks | not started | TBD |
| PR290 | `feat/dash-multivariate-layout` | P0 | PR272, PR287 | Multi page layout/CSS | not started | TBD |
| PR274 | `feat/dash-multivariate-integration` | P0 | PR288-PR290 | Multi UI wiring + browser evidence only | not started | TBD |
| PR291 | `refactor/dash-fastapi-mount` | P0 | PR274 | mount Dash into FastAPI/canonical routes | not started | TBD |
| PR292 | `refactor/remove-react-ui` | P0 | PR274 | delete React/Node production UI only | not started | TBD |
| PR275 | `refactor/dash-production-cutover` | P0 | PR291, PR292 | final Compose/CI/evidence cutover gate | not started | TBD |
| PR293 | `feat/scheduled-union-refresh` | P0 | PR275 | shared active-union market refresh only | not started | TBD |
| PR294 | `feat/scheduled-project-research` | P0 | PR275 | one-project Uni->Bi->Multi cycle only | not started | TBD |
| PR295 | `feat/scheduled-sunday-runner` | P0 | PR275 | scheduler/lock/terminal summary only | not started | TBD |
| PR276 | `feat/weekly-full-research-refresh` | P0 | PR293-PR295 | Sunday integration/restart/ops gate | not started | TBD |

## Parallel Capacity By Wave

The plan now exposes the following independent merge-unit capacity after each contract gate:

- Foundation: 2 siblings — PR277, PR278.
- Basic Dash: 2 siblings — PR265, PR266.
- Statistics controls: 2 siblings — PR267, PR268.
- Statistics figures/history: 2 siblings — PR279, PR280.
- Multivariate contracts: **3 siblings** — PR281, PR282, PR283.
- Multivariate algorithms: **4 siblings** — PR270, PR271, PR284, PR285.
- Core Multi runtime/persistence: 2 siblings — PR272, PR273; PR287 follows persistence while PR272 can still be validated independently.
- Multivariate Dash: **3 siblings** — PR288, PR289, PR290.
- Production cutover preparation: 2 siblings — PR291, PR292.
- Sunday research: **3 siblings** — PR293, PR294, PR295.

This is the maximum safe parallelism without allowing weak agents to invent shared contracts or edit overlapping files.

## Series Completion Gate

The target is complete only when every active work order above is merged and one clean final `main` evidence run proves:

- CCR-01 through CCR-13 remediation contracts pass;
- exactly four workflow pages exist and Multivariate Statistics is the only optimizer page/run/stage;
- Uni/Bi/Multi expose exact calculation controls, progress, phase/status, failure/reload behavior, and duplicate-start protection;
- Multivariate exposes exactly the three frozen objectives and chooses the winner from OOS evidence;
- every production Plotly figure satisfies `ProfessionalPlotContract` and has deterministic friendly hover, labeled axes/units, explicit unavailable states, responsiveness, and accessible metadata;
- every workflow page shows exact listing count, unique-ISIN count, and revision-backed Universe & History evidence;
- pipeline order stays `Metadata -> Univariate -> Bivariate -> Multivariate -> Final portfolio` and history envelope remains separate from common usable history;
- Univariate shows per-listing history; Bivariate shows exact pair/shared-history; Multivariate shows aligned risk-model history and every walk-forward train/test range;
- unavailable/not-run/blocked history is typed, never zero/empty/guessed;
- manual and Sunday execution reuse identical analytical/evidence contracts for identical immutable inputs;
- no manual per-ISIN or optimizer-method selection is required after Multivariate starts and no exhaustive several-hundred-ISIN subset/weight-grid production path exists;
- React/TypeScript/Vite/Node production UI is deleted;
- final Compose long-running services are exactly `postgres`, `app`, `project-bootstrap-worker`;
- cron is exactly Sunday 09:00 Europe/Vienna, refreshes active-union market data once, then completes/reuses Uni/Bi/Multivariate in dependency order without a browser;
- two-project isolation covers counts/ranges/selections/results across project switching, restart, and weekly processing order;
- no parallel sibling PR owns overlapping implementation files;
- all current canonical Python/Dash/API/contract/architecture/Docker/Compose/E2E/quality gates in `GATES.md` pass from one SHA.

## Historical Backlog Archive

`docs/backlog/archive/BACKLOG-2026-08-16-before-dash-optimizer.md` and `docs/backlog/archive/plotly-dash-three-page-research-ui-v1.md` are historical evidence only and must not override this file or the active authority documents.