# Callback Contracts

## Table of Contents

- [1. Scope and immutability](#1-scope-and-immutability)
- [2. Shared state](#2-shared-state)
- [3. Callback inventory](#3-callback-inventory)
- [4. Univariate filter contract](#4-univariate-filter-contract)
- [5. Dependency graph](#5-dependency-graph)
- [6. Failure and persistence rules](#6-failure-and-persistence-rules)
- [7. Acceptance checklist](#7-acceptance-checklist)

## 1. Scope and immutability

This document is the normative contract for the Portfell Dash UI callbacks. It covers the shell, Metadata, Univariate, Bivariate, and Multivariate pages. Callback IDs, dependency types, payload semantics, and persistence rules are public UI/backend contracts.

**Do not change this contract or any listed callback dependency without a new, explicitly approved contract revision.** A UI refactor must preserve the exact IDs, input/state/output meaning, and state-transition guarantees. A proposed change must first update this document, add or update contract tests, and be reviewed before implementation.

## 2. Shared state

`pf-browser-state.data` is the sole browser workflow state. It contains opaque identifiers, status, counts, filter values, and presentation metadata; it does not contain quotes, matrices, credentials, or analytical artifacts.

```text
PostgreSQL workflow state
          |
          v
pf-browser-state.data
       /       \
      v         v
  sidebar    route content
              |
              v
      page-specific regions
```

The Univariate page reads the current succeeded Univariate run and its v3 row artifact (falling back to v2 for historical runs). Its filter checklists create durable Univariate selections; they never start Bivariate computation.

## 3. Callback inventory

All outputs targeting `pf-browser-state.data` with `allow_duplicate=True` retain existing state fields unless the callback explicitly changes them. A callback returning `no_update` must not mutate state.

| Callback | Inputs | State | Outputs and guarantee |
| --- | --- | --- | --- |
| `_select_project` | `sidebar-project-selection.value` | `pf-browser-state.data` | Selects the opaque universe record, updates metadata identity, and clears metadata filters. No computation starts. |
| `_update_metadata_filters` | `metadata-filter-exchange.value`, `metadata-filter-instrument-type.value`, `metadata-filter-country.value`, `metadata-filter-currency.value` | `pf-browser-state.data` | Persists all four filters, recalculates the unique-ISIN Metadata count, and persists the corresponding metadata universe when possible. |
| `_refresh_state` | `pf-location.pathname` | `pf-browser-state.data` | Reloads durable workflow state while preserving server- and browser-persisted filter values and recomputing the Metadata count. Empty hydration states are ignored. |
| `_poll_job` | `pf-job-poll.n_intervals` | `pf-browser-state.data` | Reads job status only and updates presentation progress. It never starts or advances a job. |
| `_render_job_progress` | `pf-browser-state.data` | — | Renders `pf-job-progress-region.children` from the state job. |
| `_refresh_univariate_regions` | `pf-browser-state.data` | — | Rebuilds `univariate-data-regions.children` from the current run, selection, and Metadata count. |
| `_refresh_bivariate_continue` | `pf-browser-state.data` | — | Enables the Bivariate-to-Multivariate link only when the current Bivariate result is ready. |
| `_save_univariate_selection` | `univariate-save-selection.n_clicks` | `pf-browser-state.data` | Persists the complete current Univariate selection and starts the explicitly requested downstream transition. It is not triggered by page rendering. |
| `_save_dividend_frequency_selection` | Pattern `{"type":"univariate-dividend-frequency","category":ALL}.value`; pattern `{"type":"univariate-monthly-return-group","category":ALL}.value` | Dividend IDs, age values/IDs, monthly-return IDs, browser state | Converts checked Dividend, ISIN Age, and Monthly Return groups into exclusive predicates and persists the selection only. Empty group means no restriction. |
| `_save_age_selection` | Pattern `{"type":"univariate-age-group","category":ALL}.value` | Age IDs, Dividend values/IDs, Monthly Return values/IDs, browser state | Performs the same exclusive predicate merge when an age checkbox changes. |
| `_compute_bivariate` | `bivariate-compute.n_clicks` | `pf-browser-state.data` | Starts Bivariate computation only on an explicit button click and only with the persisted Univariate selection. |
| `_optimize_multivariate` | `multivariate-optimize.n_clicks` | Browser state, `multivariate-objective.value` | Starts the selected Multivariate objective only on an explicit button click. |
| `_polling_disabled` | `pf-browser-state.data` | — | Disables polling unless the durable job status is `queued` or `running`. |

## 4. Univariate filter contract

The following pattern IDs are immutable:

```text
{"type":"univariate-dividend-frequency","category": <category>}
{"type":"univariate-age-group","category": <age-key>}
{"type":"univariate-monthly-return-group","category": <return-key>}
```

Each checklist uses local persistence. Selected values are converted to one predicate per metric with OR semantics within a metric and AND semantics between metrics:

```text
Dividend A OR Dividend B
        AND
Age group C
        AND
Monthly return band D
```

Categories are:

- Dividend: `accumulating`, `irregular`, `semiannual`, `quarterly`, `annual`, `monthly`, `none / unknown` (`none / unknown` maps to `none` and `unknown`).
- Age: `le3_months`, `gt3-6_months`, `gt6_months-1_year`, `gt1-2_years`, `gt2-3_years`, `gt3-4_years`, `gt4-5_years`, `gt5_years`.
- Monthly simple return: `le_minus10_pct`, `gt_minus10_to_0_pct`, `gt_0_to_2_pct`, `gt_2_to_5_pct`, `gt_5_to_10_pct`, `gt_10_pct`, `unknown`.

The Monthly Return bands are exactly:

```text
monthly_simple_return ≤ -10%
-10% < monthly_simple_return ≤ 0%
0% < monthly_simple_return ≤ 2%
2% < monthly_simple_return ≤ 5%
5% < monthly_simple_return ≤ 10%
monthly_simple_return > 10%
missing/non-numeric = Unknown
```

An empty checklist group means “no filter”; it must not create a zero-member sentinel selection. The Return/Risk plot uses the resulting selected ISIN set. Distribution windows and tables continue to show all Metadata-scoped rows, so a filter does not hide available options.

### 4.1 Cross-browser persistence

Metadata filter values are written to PostgreSQL (`portfell.ui_preferences`, key `metadata.filters`) on every change. Univariate checklist selections are durable Univariate selection artifacts. Browser `localStorage` is only a cache and must never be the sole source of truth. A fresh browser context must render the same filter state as the originating context.

## 5. Dependency graph

```text
filter/checklist click
          |
          v
univariate_checkbox_predicates()
          |
          v
execute_action("univariate-dividend-selection")
          |
          v
create_univariate_selection(run_id, predicates)
          |
          v
PostgreSQL selection + workflow projection
      /       \
     v         v
Sidebar count  Univariate Selected ISINs
                |
                v
       Return/Risk plot ISIN scope
```

The explicit `univariate-save-selection` button is a separate transition and may start downstream work. Checkbox callbacks must never call `run_bivariate`, `run_multivariate`, or an analysis-job starter.

## 6. Failure and persistence rules

- Backend persistence is authoritative and survives page reloads and container redeploys.
- Every count is based on unique ISINs, not listing aliases.
- Callback failures return a typed public message and preserve the last coherent browser state whenever possible.
- Missing current run IDs produce `univariate_not_ready`; missing selections produce the corresponding downstream readiness error.
- Terminal jobs are not treated as active polling jobs.
- Initial checklist synchronization is permitted through Dash's `initial_duplicate` mode because dynamic page components may load after the root layout.

## 7. Acceptance checklist

- Every callback in the inventory exists with the listed Input/State/Output IDs.
- Metadata, Univariate, Sidebar, and workflow counts are derived from one state snapshot and remain equal for the same selection.
- Every Dividend, Age, and Monthly Return checkbox can be activated and deactivated; tests verify both transitions.
- Empty checkbox groups restore the unfiltered run universe.
- Monthly Return groups and table labels exactly match the seven contract bands.
- Checkbox changes persist to PostgreSQL and reload identically.
- Checkbox changes do not start Bivariate or Multivariate computation.
- Explicit compute/optimize buttons remain the only downstream starters.
- Contract tests fail if a callback ID, dependency type, or state-transition guarantee changes without an intentional contract revision.
