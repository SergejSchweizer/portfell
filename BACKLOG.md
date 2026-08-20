Last reviewed: 2026-08-20

# Active Backlog

## Backlog policy

The active implementation plan is optimized for **two simple weak agents working in parallel**. Shared contracts are frozen before parallel implementation; sibling PRs branch from the exact same predecessor `main` SHA; sibling PRs own disjoint files; all sibling PRs in a dependency wave merge before the next wave begins.

The authoritative detailed work orders are:

- `docs/backlog/max-parallel-weak-agent-replan.md` — **highest precedence for remaining PR dependencies, scope splits, ownership, branches, and wave scheduling**;
- `docs/backlog/plotly-dash-multivariate-optimizer-ui.md`;
- `docs/backlog/plotly-dash-multivariate-optimizer-ui-detailed-v1.md`;
- `docs/backlog/plotly-dash-professional-plots-weekly-refresh.md`;
- `docs/backlog/current-code-correctness-amendment.md`;
- `docs/backlog/current-code-project-isolation-addendum.md`;
- `docs/backlog/universe-history-pipeline-amendment.md`.

Where the maximum-parallel replan redistributes an old PR's scope or dependency, the replan wins. It does not remove any old correctness, financial, plotting, project-isolation, history, or scheduled-refresh acceptance requirement.

PR458 is merged and complete as a planning gate. There are currently no implementation PRs open; PR264 onward below are planned work orders.

## Product invariants

The user workflow remains exactly:

```text
Metadata Builder
    -> Univariate Statistics
    -> Bivariate Statistics
    -> Multivariate Statistics
       = automatic portfolio optimizer
       + decision audit
       + final portfolio
```

There is no separate Optimizer page or scheduled optimizer stage. Full listing identity is `(isin, exchange, code)`. Dash never recomputes financial statistics, history ranges, selection reasons, or winner logic. Heavy Uni/Bi/Multi work is durable-worker owned. Unavailable values are typed unavailable/not-applicable, never silently represented by zero/infinity/blank dates.

Every workflow page must show revision-pinned `Universe & History` evidence: listing count, unique-ISIN count, removals/reasons, observed history envelope, common usable history where meaningful, and exact observation counts. Professional Plotly figures require descriptive titles, explicit axes/units, semantic legends where applicable, deterministic friendly hover, stable traces, explicit unavailable states, revision context, responsive layout, and accessibility metadata.

The managed weekly schedule remains exactly:

```text
CRON_TZ=Europe/Vienna
0 9 * * 0
```

One Sunday cycle refreshes canonical quotes/dividends/splits once for the de-duplicated active-project union, then executes/reuses Uni -> Bi -> Multi per active project using the same service/evidence contracts as manual runs.

## Maximum-parallel execution graph

```text
PR458 merged planning gate
        |
        v
GATE 0  PR264 contract + fixture freeze
        |
        +--------------------------------------+
        |                                      |
WAVE 1  PR265 Dash runtime/shell               PR269 durable research execution foundation
        |                                      |
        +------------------- merge both -------+
                            |
        +--------------------------------------+
        |                                      |
WAVE 2  PR267 Univariate backend               PR268 Bivariate backend
        |                                      |
        +------------------- merge both -------+
                            |
        +--------------------------------------+
        |                                      |
WAVE 3  PR270 universe selector                PR271 risk models + production solvers
        |                                      |
        +------------------- merge both -------+
                            |
        +--------------------------------------+
        |                                      |
WAVE 4  PR272 durable Multi orchestrator       PR273 decision/history persistence + API
        |                                      |
        +------------------- merge both -------+
                            |
        +--------------------------------------+
        |                                      |
WAVE 5  PR274 Multi page shell                 PR281 production Python runtime preparation
        |                                      |
        +------------------- merge both -------+
                            |
        +--------------------------------------+
        |                                      |
WAVE 6  PR279 Multi Universe/Risk tabs         PR280 Multi Optimization/Validation/Final tabs
        |                                      |
        +------------------- merge both -------+
                            |
        +--------------------------------------+
        |                                      |
WAVE 7  PR277 Univariate Dash                  PR278 Bivariate Dash
        |                                      |
        +------------------- merge both -------+
                            |
        +--------------------------------------+
        |                                      |
WAVE 8  PR266 Metadata Builder Dash            PR276 Sunday full research refresh
        |                                      |
        +------------------- merge both -------+
                            |
                            v
FINAL   PR275 React deletion + canonical Dash/FastAPI/Compose cutover
```

If more than two agents are later allowed, independent presentation/scheduler PRs may start as soon as their explicit dependencies in `max-parallel-weak-agent-replan.md` are satisfied. Under the current two-agent constraint, the graph above is the authoritative schedule.

## Active PR index

| PR | Branch | Priority | Depends on | Atomic outcome |
|---|---|---:|---|---|
| PR264 | `feat/research-contract-freeze` | P0 | PR458 | Freeze routes, run/plot/evidence/objective/identity contracts and deterministic two-project fixtures; no runtime implementation. |
| PR265 | `feat/dash-runtime-shell` | P0 | PR264 | Temporary Dash runtime, shell/navigation, shared run-control and Universe/History presentation components; no page-specific analytics. |
| PR269 | `feat/durable-research-execution` | P0 | PR264 | Durable attempts/lease/heartbeat/reclaim, atomic publication primitive, project-scoped current selection, safe errors, real readiness. |
| PR267 | `feat/univariate-durable-research` | P0 | PR264, PR269 | Univariate backend correctness, typed availability, durable run, immutable result and history snapshot; no Dash page. |
| PR268 | `feat/bivariate-durable-research` | P0 | PR264, PR269 | Exact eligible pairs, typed availability, atomic/reusable Bivariate result, durable run and pair-history snapshot; no Dash page. |
| PR270 | `feat/multivariate-universe-selector` | P0 | PR264, PR267, PR268 | Deterministic automatic <=250 universe selector with DecisionArtifacts and history-impact evidence; no solver/UI. |
| PR271 | `feat/multivariate-production-solvers` | P0 | PR264, PR267, PR268 | Sample/Ledoit-Wolf/EWMA configuration registry plus solver-backed portfolio candidates and stable configuration IDs. |
| PR272 | `feat/multivariate-auto-orchestrator` | P0 | PR264, PR269-PR271 | Durable selector->risk->candidate->walk-forward->OOS winner->final-refit orchestration with no-lookahead and exact objectives. |
| PR273 | `feat/multivariate-decision-sections` | P0 | PR264, PR269-PR271 | Immutable DecisionArtifact/Universe-History persistence plus authorized non-mutating lazy read API. |
| PR274 | `feat/dash-multivariate-shell` | P0 | PR265, PR272, PR273 | Multivariate objective/run-control shell, global OOS candidate plot, history pipeline, five frozen tab extension slots. |
| PR281 | `refactor/python-app-runtime-prep` | P0 | PR265, PR269, PR272, PR273 | Prepare one FastAPI+Dash Python app and dependency-aware readiness while React still exists; no final deletion. |
| PR279 | `feat/dash-multivariate-universe-risk` | P1 | PR274, PR273 | Multivariate Universe + Risk Model Decision-Audit tabs only. |
| PR280 | `feat/dash-multivariate-validation-final` | P1 | PR274, PR273 | Multivariate Optimization + Validation + Final Portfolio tabs only. |
| PR277 | `feat/dash-univariate-research` | P1 | PR265, PR267 | Univariate Dash, professional Return/Risk plot, listing-history coverage and existing tabs. |
| PR278 | `feat/dash-bivariate-research` | P1 | PR265, PR268 | Bivariate Dash, professional diversification/matrix/tail plots and pair-history distribution. |
| PR266 | `feat/dash-metadata-builder` | P1 | PR265 | Metadata Builder page and initial Universe/History evidence only. |
| PR276 | `feat/weekly-full-research-refresh` | P0 | PR267, PR268, PR269, PR272, PR273 | Sunday 09:00 Europe/Vienna one-fetch full research orchestrator; **no dependency on PR275/UI cutover**. |
| PR275 | `refactor/dash-production-cutover` | P0 | all relevant prior PRs | Final serial deletion/switch only: remove React/Node/temp Dash, canonical routes, exactly `postgres|app|project-bootstrap-worker`, one-SHA E2E gate. |

## Weak-agent rules per PR

Every planned PR must use the exact metadata, owned paths, checklist, security, determinism, idempotency, and rollback section from `docs/backlog/max-parallel-weak-agent-replan.md`. Agents may not infer missing behavior from older PR titles. An implementation that satisfies an old checklist but violates the replan or an active correctness/plot/history amendment is incomplete.

Every PR checklist must prove its own boundary. In particular:

- backend PRs contain no Dash page/figure changes;
- presentation PRs import no formula/repository/provider/lake modules;
- parallel siblings do not edit the same files;
- no sibling relies on unmerged code from the other sibling;
- no PR moves secrets into the browser;
- no PR creates a fourth long-running production service;
- no PR weakens exact listing/configuration identity, typed availability, project isolation, or immutable revision semantics.

## Final completion gate

The project reaches this target only when final `main` proves from one SHA:

- four and only four workflow pages and no separate Optimizer page;
- durable/restart-safe/project-scoped/idempotent Uni/Bi/Multi runs and non-mutating status reads;
- exact Bivariate pair semantics and atomic completed-result preservation;
- full listing identity, configuration identity, typed unavailable semantics, safe errors, truthful common-calendar risk-model semantics, and dependency-aware readiness;
- professional plots plus revision-pinned Universe/History evidence from Metadata through Final Portfolio;
- deterministic no-lookahead OOS objective winner and no high-dimensional brute-force production path;
- Sunday `09:00 Europe/Vienna` one-fetch -> Uni -> Bi -> Multi execution using the same contracts as manual runs;
- React/TypeScript/Vite/Node production UI absent;
- final services exactly `postgres`, `app`, `project-bootstrap-worker`;
- Ruff, Pyright, unit, integration, PostgreSQL, architecture, Docker/Compose, E2E, coverage and repository merge-quality gates all pass from that SHA.
