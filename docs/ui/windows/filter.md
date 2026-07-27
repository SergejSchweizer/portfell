# Filter Window

## Identity

- Route: `/projects/:projectId/filter`
- Funnel stage: Filter
- Shared layout: authenticated header and footer

## Purpose

Apply transparent server-side eligibility thresholds to the univariate research results and create a versioned candidate set with inspectable inclusion and exclusion reasons.

## Server-owned inputs

Project, snapshot, universe, univariate run, metric definitions, threshold configuration, eligibility results, exclusion reasons, candidate count, warnings, and candidate-set identity.

## Layout and states

Provide threshold workbench, before-and-after counts, exclusion-reason summary, candidate table, `why excluded` inspector, warnings, save action, and ready/running/complete/failed/stale/infeasible states.

## User actions

Edit supported thresholds, restore profile defaults, preview effects, inspect one or multiple exclusion reasons, save the versioned candidate set, and continue to Diversification.

## Acceptance

- [ ] Boundary values and missing values follow versioned server-defined operators.
- [ ] Every excluded instrument has one or more inspectable reasons.
- [ ] The UI shows how each threshold changes candidate counts without performing financial calculations.
- [ ] Identical thresholds on identical inputs reuse the existing candidate-set identity.
- [ ] Upstream universe or univariate changes mark this stage and downstream stages stale.

## Security

Threshold previews and exclusion details require authorization to the owning project, snapshot, universe, and run. Counts and details cannot reveal inaccessible instruments.

## Components and tests

Use approved ThresholdField, ProfileSelector, CountSummary, ExclusionChart, CandidateTable, ReasonDrawer, StaleBanner, and SaveCandidateSetDialog components. Cover boundary, missing, multiple-reason, unchanged, changed, stale, and failed fixtures.
