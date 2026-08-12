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
  labelled determinate progress bar, status line, and right-aligned compute action.
- Complete state: Overview, Risk Structure, Portfolio Candidates, Risk
  Contributions, Income Evidence, and Validation tabs in the responsive multi-row
  statistics tab grid, with no horizontal tab scrolling.
- Overview includes candidate count, dominant-component share, and explicit input
  availability reasons. Risk Structure includes component thresholds, strongest driver,
  redundancy evidence, eigenvalue, condition-number, and PSD diagnostics.
- Candidate cards compare VaR/CVaR, maximum weight, Herfindahl concentration, effective
  holdings, diversification, return, drawdown, and gross historical income. Income Evidence
  includes observed coverage, trend, cuts, total return, and genuine-NAV availability.

## States

- Loading: show the shared loading state.
- Locked: Bivariate Statistics is incomplete, failed, running, or stale.
- Ready: Bivariate Statistics is complete and its immutable run id is shown.
- Running: the server-owned phase and completed/total units are displayed and polled every
  750 milliseconds until the run reaches a terminal state. The action remains disabled while
  the server reports `running`.
- Complete: persisted result tabs load automatically only after the particular Multivariate run reaches
  `complete`, after refresh or project reactivation. Every tab renders a server-produced, project-owned artifact:
  the immutable input snapshot, canonical risk model, empirical
  structure/loadings, candidate metrics and risk contributions, gross income
  evidence, and walk-forward/stress/scorecard evidence.
- Failure: workflow-state retrieval failed; show a concise alert.
- Stale: later multivariate work must return to Locked/Ready according to the
  server-owned workflow contract after an upstream change.

## Accessibility and responsive behavior

The page uses semantic panels, native progress, keyboard-operable tabs, and
captioned tables. Candidate weights, risk contributions, component loadings,
income evidence, and validation evidence all have textual alternatives. The
sidebar remains the workflow navigation at every viewport width.

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
