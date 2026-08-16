# Plotly Dash And Multivariate Portfolio Optimizer PR Stack

Status: normative base planning contract for `BACKLOG.md` PR264-PR275.

The active implementation authority is the combination of this base specification, `BACKLOG.md`, `docs/backlog/plotly-dash-professional-plots-weekly-refresh.md`, `docs/backlog/current-code-correctness-amendment.md`, and `docs/backlog/current-code-project-isolation-addendum.md`. The professional-plot/weekly-refresh amendment adds mandatory plotting requirements to PR264/PR267/PR268/PR274/PR275 and defines PR276. The current-code amendments add mandatory correctness work to PR267-PR276 based on the 2026-08-16 review of production code. Where an amendment is more specific or conflicts with wording in this base file, the amendment wins. Historical plans under `docs/backlog/archive/` are evidence only.

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

Every plot must also satisfy the active `ProfessionalPlotContract` in `docs/backlog/plotly-dash-professional-plots-weekly-refresh.md`.

## Correctness invariant

The production stack must also satisfy `docs/backlog/current-code-correctness-amendment.md` and `docs/backlog/current-code-project-isolation-addendum.md`. In particular: unavailable analytical values are not numeric-zero sentinels; production optimizer identity is full `(isin, exchange, code)`; candidate identity is configuration-specific; Uni/Bi/Multivariate heavy work is durable-worker owned rather than API-process background work; status reads are non-mutating; Bivariate completed revisions publish atomically and exact pair counts honor exclusions; covariance display semantics distinguish pairwise surfaces from coherent risk matrices; walk-forward units/policies are explicit; public errors are redacted; readiness verifies dependencies; and current Univariate selection state is project-scoped rather than user-global.

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
       Multivariate decision/objective/correctness contracts
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
PR272 durable Multivariate/research run       PR273 Multivariate decision persistence/API
orchestration + OOS objective winner           + project-scoped selection persistence
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
                         |
                         v
                      PR276
 Sunday full research refresh
```

For the original detailed PR264-PR275 task checklists, use `docs/backlog/plotly-dash-multivariate-optimizer-ui-detailed-v1.md` together with the active `BACKLOG.md` summaries and all active amendments. The amendments are mandatory acceptance for their named PRs; an implementation that satisfies the old checklist but violates a current-code amendment is incomplete.