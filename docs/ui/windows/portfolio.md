# Portfolio Window

## Identity

- Route: `/projects/:projectId/portfolio`
- Funnel stage: Portfolio
- Shared layout: authenticated header and footer

## Purpose

Compare authorized server-computed portfolio models, configure constraints, inspect trade-offs and diagnostics, and select a portfolio candidate for validation.

## Server-owned inputs

Pre-portfolio selection, model availability, model results, weights, risk contributions, diagnostics, constraints, current positions where available, artifact provenance, warnings, and run status.

## Layout and states

Provide model comparison cards, baseline visibility, metric comparison, target weights, risk contributions, concentration diagnostics, constraint workbench, advanced settings, solver messages, selection action, and loading/running/complete/failed/infeasible/stale states.

## User actions

Select profiles, configure supported constraints, run or reuse comparison, inspect model details, resolve infeasible constraints, compare current and target weights, choose a candidate, and continue to Validation.

## Acceptance

- [ ] Every supported model uses consistent definitions, units, ordering, and precision.
- [ ] No model is labelled universally best and baseline models remain visible.
- [ ] Infeasible constraints identify conflicting limits without silent relaxation.
- [ ] Identical inputs and settings reuse the existing run; material changes create a distinct run.
- [ ] The browser renders server results and does not optimise or calculate risk locally.

## Security

Every model, diagnostic, constraint, and weight response resolves through the user-owned project run and authorized dependency closure. Client payloads cannot override ownership or request internal artifacts.

## Components and tests

Use approved ModelCard, ModelComparisonTable, WeightChart, RiskContributionChart, DiagnosticPanel, ConstraintWorkbench, InfeasibilitySummary, CurrentTargetTable, and CandidateSelector components. Cover all models, unavailable model, solver failure, infeasibility, boundary values, cache reuse, current positions, and stale inputs.
