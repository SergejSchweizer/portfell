# Validation Window

## Identity

- Route: `/projects/:projectId/validation`
- Funnel stage: Validation
- Shared layout: authenticated header and footer

## Purpose

Evaluate the selected portfolio candidate through historical, walk-forward, stress, bootstrap, sensitivity, cost, turnover, and risk-limit evidence before report generation.

## Server-owned inputs

Selected portfolio run, validation configurations, historical and walk-forward results, stress and bootstrap summaries, sensitivity results, costs, turnover, current-versus-target comparison, risk-limit checks, warnings, provenance, and run status.

## Layout and states

Provide validation tabs, scorecard, evidence quality, drawdown and recovery charts, stress summaries, sensitivity views, cost and turnover panels, passed checks, warnings, assumptions, limitations, and loading/running/complete/failed/stale/unavailable states.

## User actions

Run or reuse validation, switch evidence views, inspect failed checks and assumptions, compare sensitivity scenarios, acknowledge warnings, and continue to Report.

## Acceptance

- [ ] Weak or unavailable out-of-sample evidence is explicitly labelled.
- [ ] Stress failures and cost-sensitive ranking changes remain visible and are not hidden by an aggregate score.
- [ ] All displayed calculations come from the authorized API run.
- [ ] Reopening or refreshing restores the exact validation run without duplicate computation.
- [ ] Charts and scorecards have accessible textual alternatives.

## Security

Validation data requires access to the owning project, selected portfolio run, and dependency closure. Download, chart, and detail routes cannot be accessed through shared artifact ids alone.

## Components and tests

Use approved ValidationTabs, Scorecard, EvidenceBadge, DrawdownChart, StressTable, SensitivityPanel, CostTurnoverPanel, RiskCheckList, AssumptionPanel, and WarningSummary components. Cover unavailable walk-forward data, weak evidence, stress failure, cost ranking changes, stale run, and cached reuse fixtures.
