# Univariate Window

## Identity

- Route: `/projects/:projectId/univariate`
- Funnel stage: Univariate
- Shared layout: authenticated header and footer

## Purpose

Inspect server-computed return, risk, income, drawdown, and data-quality metrics for each eligible instrument before threshold filtering.

## Server-owned inputs

Project, snapshot, universe, user-owned analysis run, metric definitions, summary rows, fund-detail series, warnings, provenance, and artifact status.

## Layout and states

Provide metric-group navigation, sortable and filterable table, selected visual comparison, fund-detail drawer, chart area, definitions, provenance, warnings, and loading/running/complete/failed/stale/unavailable states.

## User actions

Select metric groups, sort and filter rendered values, inspect a fund, change supported analysis parameters, export authorized table data, and continue to Filter.

## Acceptance

- [ ] The browser renders API-produced values and never recalculates financial statistics.
- [ ] Missing, unreliable, short-history, and quality-failed metrics are explicitly represented.
- [ ] Deep links reopen the exact user-owned run and selected fund where valid.
- [ ] Charts provide keyboard-accessible summaries and stable ordering.
- [ ] Changing material parameters creates or resolves the appropriate versioned run.

## Security

Metric and chart access requires the owning project, snapshot, universe, and run. Direct shared artifact ids or inaccessible listing ids cannot retrieve details.

## Components and tests

Use approved MetricTabs, MetricTable, ScatterPlot, FundDetailDrawer, TimeSeriesChart, WarningBadge, DefinitionPopover, ProvenancePanel, and ExportAction components. Cover unavailable metrics, short history, invalid prices, cached reuse, stale input, export, and deep-link fixtures.
