# Page Specifications

## Shared page-spec template

Each page spec must document:

- user goal
- inputs
- outputs
- layout regions
- states
- permitted actions
- dependency rules
- stale-state behaviour
- empty/error/loading behaviour
- responsive behaviour
- accessibility requirements
- named component dependencies

## Data

- User goal: load and inspect the current listing data for a selected project.
- Inputs: selected project, data-load action, server response status.
- Outputs: load progress, selected ISIN count, completion state.
- Layout: page header, progress area, table or summary area.
- Dependency rules: requires an authenticated project context.
- Stale behaviour: downstream funnel steps become stale when data changes.
- Component dependencies: page header, progress banner, status badge, table shell.

## Metadata

- User goal: select the metadata universe and create projects from filter results.
- Inputs: exchange, name, instrument type, country, currency, EODHD gate.
- Outputs: project list, metadata options, created project state.
- Layout: filter form, project selector, status copy.
- Dependency rules: requires a valid EODHD credential or synthetic equivalent in local-dev mode.
- Stale behaviour: project metadata is reloaded when the metadata universe changes.
- Component dependencies: form controls, button, empty state, status banner.

## Univariate

- User goal: inspect single-listing metrics and summary filters.
- Inputs: selected project and loaded univariate summary data.
- Outputs: metrics table, filter selects, summary state.
- Layout: table shell and supporting explanatory copy.
- Dependency rules: requires data-loaded project state.
- Stale behaviour: summary reloads when upstream data changes.
- Component dependencies: table shell, select, empty state, loading state.

## Filter

- User goal: apply reusable metric predicates to produce a narrower research selection.
- Inputs: metric predicates, numeric thresholds, saved selection context.
- Outputs: filtered selection state and summary counts.
- Layout: predicate editor, results summary, dependency hints.
- Dependency rules: requires a valid upstream selection or metrics state.
- Stale behaviour: filter outputs become stale when upstream metrics change.
- Component dependencies: form field primitives, table shell, warning state.

## Diversification

- User goal: inspect pairwise and clustering signals that help compare assets.
- Inputs: selected project and pair-analysis results.
- Outputs: pair table, cluster summary, and comparison states.
- Layout: comparison summary and results blocks.
- Dependency rules: requires stable selected inputs.
- Stale behaviour: pair outputs become stale when the underlying selection changes.
- Component dependencies: table shell, metric cards, status badges.

## Portfolio

- User goal: construct and review portfolio-level outputs.
- Inputs: selection, constraints, server-owned portfolio results.
- Outputs: target weights, portfolio summary, run state.
- Layout: overview header, control area, result regions.
- Dependency rules: uses server-owned calculations only.
- Stale behaviour: portfolio outputs become stale when selection or constraints change.
- Component dependencies: metric cards, table shell, progress state, warning state.

## Validation

- User goal: confirm readiness, risk, and policy checks before reporting.
- Inputs: portfolio outputs, validation outputs, user-selected checks.
- Outputs: pass, warning, failed, and stale states.
- Layout: validation summary and issue list.
- Dependency rules: depends on upstream portfolio state.
- Stale behaviour: validation must recompute when upstream data changes.
- Component dependencies: status badges, empty state, table shell.

## Report

- User goal: review the narrative report and export-ready content.
- Inputs: validated results and report generation status.
- Outputs: report body, export actions, redacted warnings.
- Layout: narrative area and action footer.
- Dependency rules: requires a validated upstream state.
- Stale behaviour: report becomes stale when validation or portfolio outputs change.
- Component dependencies: page header, action buttons, loading and warning states.

## Settings

- User goal: adjust display and workflow preferences.
- Inputs: preference values and saved state.
- Outputs: persisted settings and local confirmation text.
- Layout: grouped settings form.
- Dependency rules: settings may not alter server-owned calculations.
- Stale behaviour: preference cache may be invalidated by user changes.
- Component dependencies: form controls and status messages.

## Account

- User goal: inspect session identity and manage sign-out or account navigation.
- Inputs: session identity and logout action.
- Outputs: redacted identity display and logout behaviour.
- Layout: identity summary and account actions.
- Dependency rules: remains server-owned.
- Stale behaviour: session expiry returns the user to the login gate.
- Component dependencies: brand component, navigation, logout action, status badge.

