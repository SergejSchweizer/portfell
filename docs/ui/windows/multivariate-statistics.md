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

- Locked state: one `Multivariate Statistics` panel explains that Bivariate
  Statistics must complete first.
- Ready state: the Bivariate-style compact server-owned progress panel with a
  labelled 14px determinate progress bar, status line, and right-aligned compute action.
- Project switch: clear the prior project's run and result artifacts before loading
  the active project's workflow state; ignore late responses for the prior project.
- Complete state: Overview, Risk Structure, Portfolio Candidates, Risk
  Contributions, Income Evidence, Performance, and Validation tabs in the responsive multi-row
  statistics tab grid, with no horizontal tab scrolling.
- Overview and Risk Structure present their facts in two-column Fact/Value tables. Overview includes
  candidate count, dominant-component share, and explicit input availability reasons. Risk Structure
  includes effective rank, component thresholds, strongest driver, redundancy evidence, eigenvalue,
  condition-number, and PSD diagnostics.
- Candidate cards compare VaR/CVaR, maximum weight, Herfindahl concentration, effective
  holdings, diversification, total return, average compounded calendar-month and calendar-year
  returns, drawdown, and gross historical income. Income Evidence
  includes observed coverage, trend, cuts, total return, and quoted market-price capital change
  as the NAV proxy.
- Portfolio Candidates includes `highest_monthly_return`, a server-owned portfolio that maximizes
  mean historical compounded calendar-month total return under the same long-only minimum and
  maximum weights as every other candidate. It is descriptive historical evidence, not a forecast
  or recommendation.
- Average monthly and annual returns are arithmetic means of each candidate's compounded
  calendar-month and calendar-year total returns over the aligned historical period. They are
  descriptive historical metrics, not annualized forecasts.
- Performance renders persisted cumulative daily returns for every input instrument and every
  feasible portfolio on one chart. Instrument adjusted-price return lines are gray; portfolio lines
  are dashed, coloured, and labelled by method. The chart does not require a portfolio selection.
  Its x-axis is bounded to the server-owned aligned historical period from the summary artifact, the
  same common-history window Univariate Statistics' Duration selection ultimately produces, rather
  than each instrument's full individual price history.
  It also presents persisted compounded monthly and calendar-year returns for every feasible
  portfolio.
- Hovering the Performance chart, or using its arrow keys after focus, opens an inspection tooltip
  for the nearest date with cumulative returns for every visible instrument and portfolio method.
  Tooltip values use the same gray instrument and method-specific portfolio colors as the chart.

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
- Complete: persisted result tabs load automatically only after the particular Multivariate run reaches
  `complete`, after refresh or project reactivation. Every tab renders a server-produced, project-owned artifact:
  the immutable input snapshot, canonical risk model, empirical
  structure/loadings, candidate metrics and risk contributions, gross income
  evidence, cumulative and calendar-period performance, and walk-forward/stress/scorecard evidence.
- Insufficient common history: retain unavailable facts rather than rendering substitute values, and state
  the required recovery path: select Univariate Duration `> 6 months`, recompute Bivariate Statistics,
  then compute Multivariate Statistics again. The production risk model requires 100 shared daily returns.
- Failure: workflow-state retrieval failed; show a concise alert.
- Stale: later multivariate work must return to Locked/Ready according to the
  server-owned workflow contract after an upstream change.

## Accessibility and responsive behavior

The page uses semantic panels, native progress, keyboard-operable tabs, a
keyboard-operable Performance-chart inspection surface, and captioned tables.
Candidate weights, risk contributions, component loadings, income evidence, and
validation evidence all have textual alternatives. The sidebar remains the
workflow navigation at every viewport width.

## Security and boundaries

The page uses the typed Multivariate API facade. It does not inspect local
storage, render credentials or filesystem paths, infer authorization, or
calculate financial values in React. Candidate checkboxes are presentation
choices only: the selection is validated against persisted candidate ids and
saved immediately with the project; it is never a recommendation, approval,
or trade instruction.

## Tests

Route and workflow-state tests prove that it remains locked until Bivariate
Statistics is complete. The desktop two-project workflow test verifies that the
compute action polls from `resolve_inputs` to persisted results. API-contract tests cover the bounded artifact,
component, risk-contribution, income-evidence, validation, and candidate
selection routes. Docker builds run TypeScript checking and the production web
build after UI changes.

## Out of scope

Investment advice, tax/cost/net-income claims, trading, and browser-side model
calculations remain out of scope.
