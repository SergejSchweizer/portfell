# Multivariate Statistics


## Table Of Contents

- [Purpose](#purpose)
- [Server-owned inputs](#server-owned-inputs)
- [Layout](#layout)
- [States](#states)
- [Accessibility and responsive behavior](#accessibility-and-responsive-behavior)
- [Security and boundaries](#security-and-boundaries)
- [Tests](#tests)
- [Out of scope](#out-of-scope)

## Purpose

Multivariate Statistics is the fourth research module. It consumes the
project-scoped, completed Bivariate hand-off and renders only persisted API
results for portfolio-level analysis; it never changes the selected universe
or calculates financial values in the browser.

## Server-owned inputs

- the active project;
- its completed Bivariate Statistics run id;
- the Bivariate run's pinned Univariate selection id;
- server-owned workflow status and invalidation state.

## Layout

- Locked state: the compute panel and every result tab remain visible with unavailable fields while the
  Bivariate prerequisite is incomplete.
- Ready state: the Bivariate-style compact server-owned progress panel with a
  labelled 14px determinate progress bar, status line, and right-aligned compute action. The action
  reports starting and server-owned phase progress and remains disabled until the run is complete or failed.
- Project switch: clear the prior project's run and result artifacts before loading
  the active project's workflow state; ignore late responses for the prior project.
- Complete state: Overview and Portfolio Candidates tabs in the responsive statistics tab grid, with
  no horizontal tab scrolling.
- Overview renders the persisted responsive Plotly relative cumulative monthly-return chart before a portfolio-metrics
  table. The chart includes a visible `Cumulative relative gain (%)`
  y-axis title, calendar-time labels, and renders all instruments in
  light gray and every feasible portfolio as a solid method-specific color. Explicit input
  availability reasons remain visible when supplied by the server. Each visible series is rebased
  to zero at its first observation in the selected portfolio-evaluation period, so the chart shows
  relative gain from that period rather than any earlier accumulated return.
- The Overview chart keeps all input-instrument reference lines visible in light gray. Every
  portfolio series has an enabled-by-default native checkbox; users may show or hide any combination
  of portfolios. The plot scale and inspection tooltip include only enabled portfolios alongside the
  fixed instrument references.
- Candidate cards compare every evaluated portfolio variant's VaR/CVaR, maximum weight,
  Herfindahl concentration, effective holdings, diversification, total return, average compounded
  calendar-month and calendar-year returns, drawdown, and gross historical income.
- Portfolio-candidate selection checkboxes update immediately and persist the latest selection through
  one debounced background request. Saving a selection does not reload the workflow or replace the
  displayed Multivariate results.
- Portfolio Candidates includes `highest_monthly_return`, a server-owned portfolio that maximizes
  mean historical compounded calendar-month total return under the same long-only minimum and
  maximum weights as every other candidate. The default 20% maximum applies from five holdings;
  smaller valid universes use the minimum cap that permits full allocation. It is descriptive
  historical evidence, not a forecast or recommendation.
- Minimum Variance uses a dedicated production convergence budget of 100,000 iterations with a
  $10^{-7}$ weight-movement tolerance. It remains an explicitly unavailable candidate only when
  that full solve cannot converge or its inputs are infeasible.
- Execution contract `multivariate_execution.v14` keeps the joint risk model and covariance-based
  optimizers on aligned asset log returns, while all realized portfolio paths use the financially
  exact daily simple return `sum(weight × asset simple return)`. Candidate return/drawdown and
  VaR/CVaR metrics, Minimum CVaR scenarios, Walk-Forward validation, stress evidence, and the
  Performance chart therefore reconcile to the same daily portfolio path. Monthly performance uses
  chronological observations and labels each point with the actual final date in that month. The
  dependency guard resolves the canonical versioned Univariate source identity; a failed v13 run may
  be restarted with the same deterministic run id after its underlying failure is corrected.
- Average monthly and annual returns are arithmetic means of each candidate's compounded
  calendar-month and calendar-year total returns over the aligned historical period. They are
  descriptive historical metrics, not annualized forecasts.
- The Overview portfolio-metrics table lists every portfolio's persisted risk and return metrics.
  Its compact headers include `MD`, `Monthly Return`, `Annual Return`, `Holdings`, and
  `Deversifikaton`.
- Hovering the Plotly Overview chart, or using its arrow keys after focus, opens an inspection tooltip
  for the nearest month with relative cumulative returns for every visible portfolio method. Tooltip
  values use the same method-specific colors as the chart.

## States

- Loading: show the shared loading state.
- Locked: Bivariate Statistics is incomplete, failed, running, or stale.
- Ready: Bivariate Statistics is complete and its immutable run id is shown.
- Running: the server-owned phase and completed/total units are displayed and polled every
  750 milliseconds until the run reaches a terminal state. The action remains disabled while
  the server reports `running`. Independent candidate optimizers and their Walk-Forward refits run
  in a server-owned process pool sized to all CPUs available to the runtime container. A run that
  exceeds the server execution limit transitions to `failed`, exposes its failure reason, and may
  be recomputed rather than remaining indefinitely `running`. Walk-Forward validation uses at most
  24 deterministic windows spanning the available history; refits run in parallel, while turnover
  and transaction costs are evaluated in chronological order.
- Complete: Multivariate result tabs load their server-produced, project-owned summary,
  canonical risk-model facts, candidate metrics, and cumulative monthly performance artifact after
  the particular Multivariate run reaches `complete`, after refresh or project reactivation. The tabs
  are already visible with empty fields before those artifacts load.
- Insufficient common history: retain unavailable facts rather than rendering substitute values, and state
  the required recovery path: select Univariate Duration `> 6 months`, recompute Bivariate Statistics,
  then compute Multivariate Statistics again. The production risk model requires 100 shared daily returns.
- Failure: workflow-state retrieval failed; show a concise alert.
- Stale: later multivariate work must return to Locked/Ready according to the
  server-owned workflow contract after an upstream change.

## Accessibility and responsive behavior

The page uses semantic panels, native progress, keyboard-operable tabs, a
keyboard-operable Performance-chart inspection surface, and captioned tables.
Candidate weights and metrics have textual alternatives. The sidebar remains
the workflow navigation at every viewport width.

## Security and boundaries

The page uses the typed Multivariate API facade. It does not inspect local
storage, render credentials or filesystem paths, infer authorization, or
calculate financial values in React. Every persisted candidate is presented and
evaluated; the browser does not select, approve, or issue trade instructions for
portfolio variants.

## Tests

Route and workflow-state tests prove that it remains locked until Bivariate
Statistics is complete. The desktop two-project workflow test verifies that the
compute action polls from `resolve_inputs` to persisted results and renders exactly the two visible
tabs. Docker builds run TypeScript checking and the production web build after UI changes.

## Out of scope

Investment advice, tax/cost/net-income claims, trading, and browser-side model
calculations remain out of scope.
