# Component-Driven React UI Refactor PR Stack

Last reviewed: 2026-07-27

## Purpose

This document is part of the active Camovar backlog. It defines the technical UI refactor that must be completed before the product-facing Research Funnel PRs continue.

The stack is inserted after PR109 and before PR102. It does not replace the product scope of PR102 through PR108. Instead, it ensures those features are implemented on a maintainable React, TypeScript, Vite, component-catalogue, fixture, and browser-test foundation rather than extending the monolithic `apps/web/server.js` renderer.

Execution order:

```text
PR109
  -> PR110 -> PR111 -> PR112 -> PR113 -> PR114
  -> PR115 -> PR116 -> PR117 -> PR118 -> PR119
  -> PR102 -> PR103 -> PR104 -> PR105 -> PR106 -> PR107 -> PR108
```

Every implementation PR must preserve the existing hosted security boundaries: the browser performs presentation and orchestration only, financial calculations remain server-side, authorization remains server-side, and no provider secret or user-entitlement decision is moved into client code.

## PR110. Freeze Current UI Behaviour And Capture Migration Baseline

Branch: `chore/web-ui-migration-baseline`.

Git status: merged. PR: TBD.

Priority: P0 migration safety.

Depends on: PR109.

Scope: Freeze the current Web UI behaviour before framework migration. Catalogue all routes, forms, actions, states, API calls, authentication transitions, responsive breakpoints, accessibility landmarks, visible texts, and persisted browser-visible state. Add deterministic desktop, tablet, and mobile screenshots for the current login, dashboard, project shell, statistics steps, loading, complete, warning, failed, and empty states. Record known defects separately so the migration does not accidentally treat them as required behaviour. The committed baseline inventory lives in `docs/backlog/web-ui-migration-baseline.md` and `docs/backlog/web-ui-migration-baseline.json`.

Acceptance: A committed migration inventory maps every current route and interactive control to its API endpoint, input contract, output state, and screenshot fixture. Baseline tests can open each documented state without real Google or EODHD calls. The baseline identifies which behaviours must remain equivalent, which defects are intentionally retained temporarily, and which obsolete behaviours are explicitly excluded from the migration.

Security: Baseline fixtures and screenshots contain only synthetic users, opaque ids, synthetic market values, and redacted errors. No cookie, token, credential, internal path, provider response, or cross-user data is captured in source, screenshots, traces, or test reports.

Determinism: Fixtures use fixed locale, timezone, viewport, clock, route parameters, and synthetic API responses. Re-running the baseline against unchanged source produces stable screenshots and interaction results.

Idempotency: Running baseline capture or contract tests does not create projects, credentials, refreshes, selections, analyses, reports, or exports.

## PR111. UI Principles, User Flows, Page Specifications, And Component Contracts

Branch: `docs/web-ui-product-specifications`.

Git status: merged. PR: TBD.

Priority: P0 specification foundation.

Depends on: PR110.

Scope: Add versioned UI documentation under `docs/ui/` for design principles, information architecture, user roles, route map, first-run onboarding, persisted Research Funnel flow, page specifications, interaction rules, error and loading semantics, responsive rules, accessibility requirements, chart and table rules, and component contracts. Define the boundary between generic components, feature components, pages, API clients, and server-owned financial logic. Include acceptance-oriented specifications for Data, Metadata, Univariate, Filter, Diversification, Portfolio, Validation, Report, Settings, and account flows.

Acceptance: Every current and planned Research Funnel page has a documented user goal, inputs, outputs, layout regions, states, permitted actions, dependency rules, stale-state behaviour, empty/error/loading behaviour, responsive behaviour, accessibility requirements, and named component dependencies. Documentation checks fail when a registered route lacks a page specification or when a component contract embeds financial calculation or authorization logic.

Security: Specifications explicitly prohibit secrets, provider keys, session tokens, internal storage paths, database ids, unrestricted artifact ids, and authorization decisions in browser components or fixtures.

Determinism: Route names, funnel order, state names, component names, formatting rules, and page-spec identifiers are committed and versioned.

Idempotency: Documentation generation and validation are read-only and produce no runtime or repository changes when inputs are unchanged.

## PR112. Extract Design Tokens And Establish Layered CSS Architecture

Branch: `refactor/web-design-tokens-css-layers`.

Git status: not started. PR: TBD.

Priority: P1 visual-system foundation.

Depends on: PR111.

Scope: Extract typography, spacing, colour, border, radius, elevation, focus, motion, density, chart, table, badge, warning, loading, and breakpoint values from `apps/web/server.js` into versioned token files. Introduce a layered CSS architecture for reset, tokens, base elements, components, utilities, feature styles, and responsive overrides. Remove page-specific copies of generic button, input, panel, badge, and table styling while preserving the approved visual baseline.

Acceptance: All migrated pages consume named tokens rather than hard-coded duplicate values for approved design properties. Automated source checks reject new unapproved hard-coded colours, spacing values, radii, and z-index values in component styles. Baseline screenshots remain within the approved visual-diff threshold across desktop, tablet, and mobile.

Security: CSS and token files contain no user-derived values, secret-dependent URLs, inline provider data, or externally loaded unreviewed assets.

Determinism: Token names, fallback values, layer order, breakpoint definitions, and theme resolution are versioned and independent of runtime user data.

Idempotency: Rebuilding styles from unchanged tokens produces byte-stable generated outputs where generation is used and does not mutate source files.

## PR113. React, TypeScript, And Vite Application Scaffold

Branch: `refactor/web-react-typescript-vite-scaffold`.

Git status: not started. PR: TBD.

Priority: P0 application foundation.

Depends on: PR112.

Scope: Create the React and TypeScript application under `apps/web/src/` with Vite development and production builds, strict TypeScript settings, route registration, typed environment access, API-client boundary, test setup, linting, formatting, and Docker integration. Preserve the existing server-side authentication and API boundary during migration. Add a compatibility entry point so the current application remains available while React routes are migrated incrementally.

Acceptance: `npm` or the repository-standard package command can run type checking, linting, unit tests, development server, and production build. Docker Compose serves the React application in development without exposing secrets to the build. A typed health route and one synthetic authenticated shell route render successfully, while the existing non-migrated routes remain reachable through the compatibility boundary.

Security: Only explicitly public configuration is injected into the browser bundle. Build inspection proves Google client secrets, session secrets, EODHD keys, database configuration, internal service credentials, and mounted secret-file paths are absent from source maps and generated assets.

Determinism: Dependency versions, build inputs, route registration, environment schema, and generated asset naming rules are pinned or lockfile-controlled.

Idempotency: Repeated production builds from unchanged source and lockfile produce functionally equivalent assets and do not create runtime entities or alter persisted application state.

## PR114. Base Component Library And Isolated Component Catalogue

Branch: `feat/web-component-library-catalogue`.

Git status: not started. PR: TBD.

Priority: P1 reusable UI foundation.

Depends on: PR113.

Scope: Implement typed reusable components for Button, IconButton, LinkButton, FormField, Select, Checkbox, RadioGroup, Dialog, Drawer, Panel, MetricCard, StatusBadge, ProgressStepper, DataTable shell, EmptyState, ErrorState, LoadingState, Toast, PageHeader, Tabs, Breadcrumbs, and responsive layout primitives. Add an isolated component catalogue with deterministic stories or previews for all supported variants, states, widths, keyboard interactions, and error conditions.

Acceptance: Every base component has typed props, accessibility tests, keyboard tests, loading/disabled/error examples, responsive previews, and documented permitted variants. Feature code can no longer introduce page-specific generic button or form-control implementations without an explicit design-system exception. The catalogue runs without Google, EODHD, PostgreSQL, or the FastAPI service.

Security: Stories and previews use synthetic props only and cannot issue real provider, authentication, analysis, report, or export requests.

Determinism: Component markup, variant mappings, icon names, story ordering, synthetic fixture values, and snapshot viewports are committed and stable.

Idempotency: Opening or testing the component catalogue performs no state-changing API calls and creates no persisted browser or server records.

## PR115. React Application Shell, Navigation, Authentication States, And Server Boundary

Branch: `refactor/web-react-application-shell`.

Git status: not started. PR: TBD.

Priority: P0 first production migration slice.

Depends on: PR114.

Scope: Rebuild the current application shell with React components: login gate, authenticated shell, brand and account identity, responsive sidebar, resizer where retained, top bar, project context, snapshot indicator, Research Funnel navigation, route frame, global loading state, error boundary, logout, and account navigation. Keep session establishment, OIDC callback handling, CSRF validation, and authorization on the server. Replace direct HTML-string generation for the shell while leaving non-migrated feature bodies behind an explicit compatibility adapter.

Acceptance: Browser tests cover unauthenticated login, authenticated session restoration, logout, expired session, local-development authentication labelling, long account names, long project names, sidebar resizing where supported, desktop/tablet/mobile navigation, keyboard-only navigation, route focus management, loading, empty, warning, failed, and stale funnel states. The shell displays the same persisted project and snapshot identities before and after page refresh.

Security: React receives only the redacted session-status and user-facing project context required for display. Tokens, cookies, provider credentials, internal ids, and authorization policy details are not exposed through props, HTML, logs, client storage, or source maps.

Determinism: Shell state derives from typed API responses and registered route metadata. Identical session and project responses produce stable navigation, labels, funnel state, and accessible markup.

Idempotency: Rendering, refreshing, resizing, navigating, or restoring the shell does not create sessions, projects, snapshots, selections, analyses, reports, or exports.

## PR116. Migrate Statistics Workflow To Typed React Feature Components

Branch: `refactor/web-react-statistics-workflow`.

Git status: not started. PR: TBD.

Priority: P1 first complete feature migration.

Depends on: PR115.

Scope: Migrate Load Data, Univariate Statistics, Bivariate Statistics, and Multivariate Statistics from HTML-string rendering and direct DOM manipulation into typed React feature components. Add explicit finite states for idle, ready, running, complete, warning, failed, cancelled, and stale. Preserve persisted run identities, dependency unlocking, progress, status messages, result-table rendering, retries, and server-produced financial values. Do not migrate calculations into the browser.

Acceptance: End-to-end tests prove later stages remain disabled until dependencies complete, running actions cannot be double-submitted, refresh restores the active run, completion unlocks the next stage, upstream changes mark downstream results stale, failures expose redacted details and retry actions, cancellation behaves consistently, and completed univariate result tables match the API payload exactly. The legacy statistics renderer is no longer used on migrated routes.

Security: Statistics requests require authenticated project and snapshot context and use opaque run routes. The UI cannot request unrestricted storage paths, arbitrary shared artifact ids, or inaccessible listing data.

Determinism: State transitions, status labels, result ordering, progress interpretation, units, precision, and dependency rules are versioned and tested against fixed API fixtures.

Idempotency: Reopening or refreshing an existing run reloads it without submitting a new computation. Repeated identical submissions reuse or join the server-owned run according to the API contract.

## PR117. Deterministic UI Scenario Fixtures And Mock API Layer

Branch: `test/web-deterministic-ui-fixtures`.

Git status: not started. PR: TBD.

Priority: P1 development-speed foundation.

Depends on: PR116.

Scope: Add deterministic scenario fixtures and a mock API layer for empty user, missing credential, invalid credential, Free key, paid key, empty project, partial data, statistics running, statistics complete, stale analysis, provider error, authorization error, portfolio comparison, stress warning, recommendation ready, slow API, and offline recovery. Allow fixture selection only in test and explicit local-development modes. Define fixture schemas from the same TypeScript API contracts used by production components.

Acceptance: Every registered page and major component state can be opened through a documented fixture without Google, EODHD, PostgreSQL, or live FastAPI dependencies. Contract tests reject fixtures that omit required fields or contain impossible state combinations. Production builds exclude fixture-selection routes and cannot enable mock responses through user-controlled query parameters or headers.

Security: Fixtures contain no copied production payloads, real identifiers, credentials, tokens, internal paths, or personal information. Test-only fixture controls are unreachable in production mode.

Determinism: Fixture ids, clocks, locale, timezone, random seeds, data ordering, and response delays are fixed and versioned.

Idempotency: Loading, switching, or replaying fixtures changes only in-memory test state and creates no server-side records or persistent browser data outside explicitly disposable test storage.

## PR118. Playwright Interaction, Accessibility, And Visual Regression Suite

Branch: `test/web-playwright-visual-regression`.

Git status: not started. PR: TBD.

Priority: P0 regression protection.

Depends on: PR117.

Scope: Add Playwright browser tests for critical interactions, responsive layouts, keyboard flows, accessibility checks, route restoration, loading/error recovery, and visual baselines. Cover fixed desktop, tablet, and mobile viewports with pinned browser versions and deterministic fixtures. Add CI artefact handling, trace redaction, screenshot review guidance, and explicit visual-diff approval rules.

Acceptance: CI runs browser tests for login gate, authenticated shell, project context, statistics workflow, loading, empty, warning, failure, stale state, session expiry, logout, keyboard navigation, reduced motion, desktop, tablet, and mobile layouts. Visual changes fail unless baselines are deliberately updated. Accessibility checks cover landmarks, names, focus order, dialog focus trapping, table semantics, form errors, contrast, and chart alternatives where charts are present.

Security: Screenshots, videos, traces, HTML reports, and console logs are scanned for provider keys, tokens, cookies, ciphertext, fingerprints, internal paths, and cross-user content before publication as CI artefacts.

Determinism: Tests use pinned browsers, fixed fonts available in the test image, fixed viewports, fixed clock, fixed locale and timezone, disabled nondeterministic animation, stable fixtures, and controlled network timing.

Idempotency: Re-running the suite against unchanged source and fixtures produces the same pass/fail result and does not create durable application records.

## PR119. Migrate Remaining Route Skeletons, Remove Legacy Renderer, And Cut Over The UI Stack

Branch: `refactor/web-react-production-cutover`.

Git status: not started. PR: TBD.

Priority: P0 migration completion and handoff.

Depends on: PR118.

Scope: Migrate the remaining currently implemented route skeletons and shared states to React, including Data, Metadata, Portfolio, Stress or Validation, Recommendation or Report, Settings, and account surfaces. These routes establish typed page boundaries, loading/error/empty states, and API integration contracts only where the later product PRs still own detailed functionality. Remove obsolete HTML-string page rendering, direct DOM mutation, duplicated style blocks, and compatibility adapters. Make the Vite React build the canonical Web application in Docker and local development. Update PR102 to depend on PR119 and require PR102 through PR108 to use the component library, page specifications, fixtures, and Playwright suite.

Acceptance: No production route imports or calls the legacy HTML-string renderer or direct page-level DOM mutation helpers. Docker Compose serves the React application as the canonical UI. All baseline routes either preserve migrated behaviour or display an explicitly specified product-placeholder state owned by PR102 through PR108. Type checking, linting, unit tests, component-catalogue tests, Playwright tests, accessibility checks, visual baselines, and production build pass. The backlog dependency chain is updated to `PR109 -> PR110 through PR119 -> PR102 through PR108`.

Security: Production bundles and source maps contain no secrets or server-only configuration. Removed compatibility code cannot leave unauthenticated legacy routes, alternate authorization paths, or unredacted error rendering reachable.

Determinism: The canonical route map, build entry point, feature-boundary registry, placeholder states, and Docker asset serving are versioned and stable.

Idempotency: Rebuilding, restarting, refreshing, or navigating the cut-over application resumes persisted server-owned state and creates no duplicate user, project, snapshot, selection, analysis, report, or export records.

## Series Completion Gate

The component-driven UI refactor is incomplete while any of these conditions remains true:

- production pages are still assembled through monolithic HTML strings in `apps/web/server.js`;
- generic controls are implemented independently inside feature pages;
- a registered route lacks a page specification, typed API contract, fixture state, or browser coverage;
- visual changes cannot be reviewed through deterministic component previews and screenshots;
- page refresh loses server-owned project, snapshot, selection, or run state;
- the browser performs financial calculations or authorization decisions;
- test fixtures or browser artefacts can contain secrets or cross-user data;
- PR102 through PR108 can proceed by extending the legacy renderer instead of the React component foundation.

Final refactor branch: `refactor/web-react-production-cutover`.

Stack rule: PR110 through PR119 are sequential and start from the predecessor branch until landed. After PR119 merges, PR102 must be rebased on the resulting `main` and its dependency changed from PR109 to PR119.

Merge rule: Each implementation PR is reviewed and landed separately. No implementation PR is merged solely because this planning document has been merged.
