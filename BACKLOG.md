# Backlog

Last reviewed: 2026-08-07

## Table Of Contents

- [Backlog Policy](#backlog-policy)
- [Active Workflow Ingestion UI PR](#active-workflow-ingestion-ui-pr)
- [Active Four-Page Portfell UI PR Stack](#active-four-page-portfell-ui-pr-stack)
- [Active Project Sidebar PR Stack](#active-project-sidebar-pr-stack)
- [Active Platform-Inspired Simple UI PR Stack](#active-platform-inspired-simple-ui-pr-stack)
- [Active Persistent EODHD Credential PR Stack](#active-persistent-eodhd-credential-pr-stack)
- [Active Hosted Multi-Tenant Portfell PR Stack](#active-hosted-multi-tenant-portfell-pr-stack)
- [Active Architectural Refactor PR Stack](#active-architectural-refactor-pr-stack)
- [Current Architectural Decision](#current-architectural-decision)
- [Series Completion Gate](#series-completion-gate)
- [Update Rules](#update-rules)
- [Completed PR History](#completed-pr-history)
- [Completed And Superseded Detailed Records](#completed-and-superseded-detailed-records)

## Backlog Policy

This file is ordered by execution relevance:

1. active, not-yet-finished PR-sized work;
2. current architectural constraints and completion gates;
3. completed and superseded history at the bottom.

Every active item must contain `Branch`, `Git status`, `PR`, `Priority`, `Depends on`, `Scope`, `Acceptance`, `Security`, `Determinism`, and `Idempotency`. A PR is atomic only when it can merge independently with all repository gates green. A PR is complete only when its acceptance criteria are machine-verifiable and no assigned scope is deferred silently.

Completed entries are never deleted. Superseded plans are moved to the historical section and explicitly marked non-active. Backlog identifiers are never reused.

## Active Workflow Ingestion UI PR

### PR132. Stage-Owned Ingestion Controls

Branch: `feat/workflow-ingestion-controls`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/222.

Priority: P1 workflow clarity.

Depends on: current `main`.

Scope:

- Move EODHD credential entry and `Fetch all metadata` from the persistent header into a first white panel on Metadata Filter.
- Move quote fetching from Metadata Filter into a first white panel on Univariate Statistics.
- Navigate to Univariate Statistics after a successful metadata-filter submission.
- Preserve server-owned credentials, metadata refresh, quote ingestion, workflow state, and polling contracts.
- Synchronize page specifications and React scaffold/Playwright regression contracts.

Acceptance:

- Metadata Filter displays the metadata-refresh panel before all filter controls, and the header contains no ingestion form.
- Applying a valid metadata filter navigates to `/univariate-statistics`.
- Univariate Statistics displays determinate quote progress and `Fetch quotes` in its first white panel before the statistics controls.
- Existing server API routes, request payloads, and run-polling semantics remain unchanged.

Security: The browser continues to use only the existing credential and workflow endpoints; no credential or ingestion logic moves client-side.

Determinism: Page placement changes do not alter persisted metadata selections, quote runs, or analytical result identities.

Idempotency: Existing metadata and quote requests retain their server-side idempotency behavior.

### Workflow Ingestion UI Series Completion Gate

This PR is complete only after it is merged with the required checks in [GATES.md](GATES.md) passing, the page specifications and regression tests are synchronized, and no header-owned ingestion control remains.

## Active Four-Page Portfell UI PR Stack

This is the canonical UI implementation stack. It supersedes the former eight-stage research-funnel UI plan. The production application has exactly four pages, in this order:

```text
metadata_filter
    -> univariate_statistics
    -> univariate_filter
    -> bivariate_statistics
```

Metadata Filter begins with the EODHD credential input and metadata refresh action in its own panel, before all metadata dropdowns. Univariate Statistics begins with quote fetching and progress in its own panel. The canonical Python operation is `fetch_all_metadata`; the removed name `fetch_all_isins` must not be reintroduced as a function, module, command, route, alias, compatibility shim, or documentation term.

The stack is deliberately sequential. Each PR must be independently reviewable, must leave the repository green, and must not implement scope assigned to a later PR. Browser code owns presentation and transient interaction state only. Credentials, authorization, workflow status, selections, calculations, persistence, invalidation, and financial/statistical logic remain server-owned.

### PR110. Canonical Workflow State And Four-Page API Contract

Branch: `feat/four-page-workflow-state`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/190.

Priority: P0 workflow foundation.

Depends on: PR189.

Scope:

- Add one backend-owned workflow-state model for the current authenticated user and active project.
- Expose `GET /api/workflow` and return exactly these stages: `metadata_filter`, `univariate_statistics`, `univariate_filter`, and `bivariate_statistics`.
- Use only the statuses `locked`, `ready`, `running`, `complete`, `failed`, and `stale`.
- Include immutable upstream identifiers in every completed stage: metadata revision, metadata selection id, quote run id, univariate run id, univariate-filter selection id, and bivariate run id where applicable.
- Define downstream invalidation rules in one backend module. A metadata refresh invalidates every downstream stage; a metadata-filter change invalidates quote loading and every later stage; a univariate-statistics change invalidates the univariate filter and bivariate statistics; a univariate-filter change invalidates bivariate statistics.
- Add matching TypeScript contracts in `apps/web/src/contracts.ts` and one `loadWorkflow()` client function. Pages must not infer completion from local component state.
- Persist or reconstruct workflow status from existing server-owned project, run, selection, and artifact records. Do not add Redux, Zustand, XState, React Router, WebSockets, Celery, Redis, or a generic workflow engine.

Acceptance:

- `GET /api/workflow` returns the same JSON for the same persisted state across repeated calls and process restarts.
- A new user with no metadata receives `metadata_filter=ready` and the other three stages as `locked`.
- Every upstream mutation produces the exact stale/locked transitions defined above.
- The response never exposes an EODHD key, filesystem path, unrestricted global dataset identifier, or another user's state.
- Unit tests cover every allowed status transition and every invalidation edge.
- API tests prove user isolation and deterministic response ordering.
- TypeScript compiles without casts from `unknown` to the workflow-state type.

Security: Workflow state is resolved inside the authenticated user scope and never from unrestricted global lake scans.

Determinism: Identical persisted identifiers and statuses produce byte-equivalent JSON after canonical serialization.

Idempotency: Repeating `GET /api/workflow` performs no writes and creates no projects, runs, selections, or artifacts.

### PR111. Metadata Header, Metadata Filter, And Real Quote Progress

Branch: `feat/metadata-filter-quote-progress`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/197.

Priority: P0 first runnable page.

Depends on: PR110.

Scope:

- Keep the EODHD key input in the persistent header. Submission must call `POST /api/credentials/eodhd`, clear the input, then call the real metadata workflow through `POST /api/metadata/fetch-all`.
- Inject the authenticated user's decrypted key into `run_fetch_all_metadata_workflow`; do not read a shared plaintext key or return the key to the browser.
- Make `/metadata-filter` the default application route and the first workflow page.
- Load multiple-choice values from `GET /api/metadata-filter/options` for exchange, instrument type, country, and currency; include a name-contains input.
- Submit the filter through `POST /api/metadata-filter` and persist a deterministic metadata selection id.
- Place the quote progress bar after all metadata controls and status text. Place a right-aligned `Fetch quotes` button beneath the progress bar.
- Start quote ingestion with `POST /api/quote-runs` using only the current metadata selection id. Poll `GET /api/quote-runs/{run_id}` until complete or failed.
- Return and render `total`, `completed`, `failed`, and integer `percent` values. The progress bar must represent server progress; it must not jump from zero to 100 solely because one HTTP request returned.
- Disable duplicate metadata, filter, and quote submissions while the corresponding operation is running.
- Refresh workflow state after every successful mutation.

Acceptance:

- The header never stores the provider key in URL parameters, browser storage, HTML, logs, screenshots, analytics, or API responses.
- `fetch_all_metadata` performs a mocked provider request in tests and publishes one deterministic metadata revision.
- The filter button remains disabled when all filter fields are empty, unless an explicit `Select all metadata` action is implemented and documented.
- `Fetch quotes` remains disabled until a non-empty metadata selection exists.
- The DOM order is: metadata controls, apply-filter action, selection status, progress label, progress element, progress status, right-aligned `Fetch quotes` action.
- Polling stops on `complete`, `failed`, component unmount, route change, or request cancellation.
- Repeating the same metadata filter returns the same logical selection id.
- Repeating `Fetch quotes` for an already running or completed identical run returns that run instead of creating a duplicate.
- Browser tests cover successful metadata loading, empty metadata, invalid credential, zero-result filter, partial quote failure, complete quote success, refresh recovery, and secret non-disclosure.

Security: Credential decryption is limited to the provider-call boundary; quote entitlements are granted only after a successful user-key-backed request.

Determinism: Canonical filter serialization and metadata revision pinning produce stable selection and quote-run identities.

Idempotency: Retrying credential save, metadata refresh, identical filtering, polling, or quote-run creation does not duplicate logical state.

### PR112. Functional Univariate Statistics Page

Branch: `feat/univariate-statistics-page`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/192.

Priority: P1 second workflow page.

Depends on: PR111.

Scope:

- Replace the current read-only summary page with a complete execution page.
- Add `POST /api/univariate-statistics/runs` with the current metadata selection id and quote run id as required immutable inputs.
- Add `GET /api/univariate-statistics/runs/{run_id}` for status and `GET /api/univariate-statistics/runs/{run_id}/results` for server-paginated results.
- Require quote completion before execution. Render a locked explanation and link to `/metadata-filter` when prerequisites are absent or stale.
- Provide one `Compute univariate statistics` action, running status, cancellation-safe polling, empty state, failure state, completion summary, sorting, and pagination.
- Render at minimum: listing identity, ISIN, symbol, exchange, observation count, annualized return, annualized volatility, Sharpe ratio, maximum drawdown, and expected shortfall when present in the backend artifact.
- Keep units and numerical precision in typed formatter functions; do not calculate statistics in React.
- Remove the old aggregate-only API dependency when no remaining caller uses it.

Acceptance:

- The page cannot start without a complete quote run for the current metadata selection.
- The POST endpoint invokes the real univariate workflow and never returns a synthetic success response.
- Result rows are scoped exactly to the pinned metadata selection and quote dataset.
- Sorting and pagination are server-owned and deterministic for equal values through a stable listing-id tie-breaker.
- Refreshing during a running job restores the same run and progress.
- Repeating an identical request returns the existing running or completed run id.
- Unit tests verify input pinning, selection scoping, failure propagation, deterministic ordering, and no unrestricted Gold/Silver scan.
- Browser tests verify locked, running, empty, failed, complete, paginated, and refreshed-running states.

Security: Results are resolved through the authenticated user's snapshot and entitlement scope.

Determinism: The artifact id includes exact quote inputs, selection membership, parameters, and algorithm version.

Idempotency: Identical run creation is deduplicated by the canonical input hash.

### PR113. Functional Univariate Filter Page

Branch: `feat/univariate-filter-page`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/193.

Priority: P1 third workflow page.

Depends on: PR112.

Scope:

- Replace the placeholder page with a typed predicate editor and persisted selection result.
- Add `GET /api/univariate-filter/metrics` for allowed numerical metrics, labels, units, and valid operators.
- Add `POST /api/univariate-filter` accepting `source_run_id`, optional `selection_name`, and an ordered predicate list with `metric`, `operator`, and numeric `value`.
- Permit only `=`, `!=`, `>`, `>=`, `<`, and `<=` for numerical metrics. Apply all predicates with logical AND.
- Canonically sort predicates for identity generation while preserving the user-visible edit order separately.
- Return `selection_id`, `input_count`, `selected_count`, `excluded_count`, normalized predicates, and exclusion summaries.
- Render add/remove predicate rows, visible validation, apply action, running state, result counts, and a server-paginated selected-listing table.
- Require a completed, non-stale univariate run. Clear stale results immediately when a predicate changes after completion.
- The backend must filter only rows belonging to the pinned source run; it must not read every persisted univariate row.

Acceptance:

- Invalid metrics, operators, non-finite values, empty predicate lists, and duplicate contradictory predicates return structured 4xx errors.
- A valid predicate set selects exactly the rows produced by applying all predicates to the pinned source run.
- `input_count = selected_count + excluded_count` in every successful response.
- Identical normalized predicates on the same source run return the same selection id.
- Predicate order differences do not create duplicate selections.
- The page renders locked, editing, invalid, running, empty-result, failed, complete, and stale states.
- Tests cover all operators, AND semantics, boundary equality, NaN/infinity rejection, source-run isolation, deterministic identity, and duplicate submission.

Security: Metric discovery and filtering operate only on artifacts visible to the authenticated user.

Determinism: Metric definitions, operator semantics, predicate normalization, and selection ordering are versioned.

Idempotency: Reapplying an identical normalized predicate set reuses the same selection and membership rows.

### PR114. Functional Bivariate Statistics Page

Branch: `feat/bivariate-statistics-page`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/194.

Priority: P1 fourth workflow page.

Depends on: PR113.

Scope:

- Replace the placeholder page with pair-plan, execution, progress, and result views.
- Add `POST /api/bivariate-statistics/plan` accepting the current univariate-filter selection id and returning selected listing count, theoretical pair count, configured pair limit, and whether execution is allowed.
- Add `POST /api/bivariate-statistics/runs`, `GET /api/bivariate-statistics/runs/{run_id}`, and `GET /api/bivariate-statistics/runs/{run_id}/results`.
- Fail before pair generation when the theoretical pair count exceeds the configured maximum.
- Poll real server progress using `total_pairs`, `completed_pairs`, `failed_pairs`, and integer `percent`.
- Render server-paginated pair rows with left/right identity, observation count, Pearson correlation, Spearman correlation, covariance, left-to-right beta, and right-to-left beta where available.
- Default ordering is descending absolute Pearson correlation, then stable left-id/right-id tie-breakers.
- Require a complete, non-empty, non-stale univariate-filter selection.
- Do not transfer the complete pair dataset to the browser and do not calculate correlations in React.

Acceptance:

- Pair count equals `n * (n - 1) / 2` for `n` unique selected listings.
- Same-listing pairs and duplicate reversed pairs never appear.
- Over-limit plans return a clear non-runnable result and create no run or pair artifacts.
- Refreshing a running page reconnects to the existing run.
- Identical run requests reuse the existing running or completed run.
- Result pagination and ordering are stable across repeated requests.
- Tests cover zero, one, two, normal, partially failed, and over-limit selections; source-selection isolation; pair uniqueness; deterministic ordering; and refresh recovery.

Security: Plans, runs, and pair results are scoped to the authenticated user's selected membership and allowed observations.

Determinism: Pair construction, alignment rules, metric versions, ordering, and artifact identity are explicit and versioned.

Idempotency: Identical source selection and algorithm inputs resolve to one logical run and artifact set.

### PR115. Sequential Navigation, Final Legacy Deletion, And End-To-End Gate

Branch: `refactor/four-page-ui-completion-gate`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/195.

Priority: P1 cutover completion.

Depends on: PR114.

Scope:

- Make `apps/web/src/routes.tsx` the only production route registry and keep exactly the four canonical routes.
- Drive navigation status from `GET /api/workflow`. Locked pages remain visible but non-navigable and explain their prerequisite.
- Preserve normal browser refresh, back, forward, and direct-link behavior without adding a global frontend store.
- Delete all unused page components, shell experiments, fixture selectors, catalogues, compatibility adapters, synthetic compute endpoints, obsolete project/dashboard/settings/account/report/portfolio/diversification routes, and stale UI specifications.
- Delete unused `AuthenticatedShell`, old aggregate-only endpoints, old HTML-rendering helpers, duplicate route lists, and any tests whose only purpose is to preserve removed files.
- Add a repository gate that fails when removed route ids, compatibility renderer names, direct page-level `fetch(` calls, the retired metadata-fetch name, or production fixture selectors reappear.
- Update `README.md`, `ARCHITECTURE.md`, `CONTRACTS.md`, `docs/ui/README.md`, `docs/ui/page-development.md`, and the four page specifications to describe only the final implementation.
- Add one Playwright workflow test that completes metadata refresh, metadata filtering, quote loading, univariate statistics, univariate filtering, and bivariate statistics using deterministic mocked provider responses.

Acceptance:

- The production route registry contains exactly four entries in the required order.
- No production file or documentation describes the superseded eight-stage UI as current.
- No placeholder-only production page remains.
- No legacy renderer, compatibility route, duplicate navigation registry, component catalogue, fixture-selection route, or browser-owned financial/statistical computation remains.
- Direct links to locked pages render a prerequisite message without starting work.
- A completed deterministic synthetic workflow survives browser refresh at every stage.
- An upstream change marks all required downstream stages stale and blocks execution until recomputed.
- `npm ci`, TypeScript checking, Vite build, Node syntax checking, Ruff, Pyright, import-linter, the full Python test suite, Playwright, and the repository `pr-quality` gate all pass.
- A repository-wide search for forbidden legacy identifiers returns no tracked production or documentation matches.

Security: The final browser bundle contains no provider secret, authorization rule, raw credential, unrestricted dataset path, or cross-user identifier.

Determinism: The same mocked provider responses and user inputs produce the same workflow ids, page states, progress sequence, selections, and result ordering.

Idempotency: Replaying the complete synthetic workflow creates no duplicate credentials, metadata revisions, selections, quote runs, statistical runs, or artifacts.

### PR116. Remove Google Authentication Runtime

Branch: `refactor/remove-google-authentication`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/196.

Priority: P0 local-runtime simplification.

Depends on: PR115.

Scope: Remove Google OIDC, browser login/session handling, CSRF enforcement, runtime secret mounts, and associated catalog objects. Run the four-page workflow as one explicit local workspace until a replacement identity model is approved.

Acceptance: No supported runtime route, environment variable, secret mount, browser bundle, or active security document exposes Google authentication behavior. Existing catalog volumes remove the retired identity and session tables through an ordered migration.

Security: The local runtime is not a multi-user or public-hosted deployment boundary. EODHD credentials remain server-owned and encrypted.

Determinism: Every request resolves to the fixed local workspace identity without browser-supplied user or session state.

Idempotency: Applying the catalog retirement migration repeatedly leaves the schema unchanged after the first successful application.

## Active Project Sidebar PR Stack

This series adds one persistent application sidebar without changing the four canonical workflow routes. On desktop, the sidebar shows the current project as a dropdown and the workflow as an ordered hierarchy beneath it. On narrow viewports, the same sidebar content appears in an accessible drawer opened from the header. The hierarchy is exactly `Project -> Metadata Filter -> Univariate Statistics -> Univariate Filter -> Bivariate Statistics`; it is not a filesystem tree, an arbitrary nested-project model, or a second route registry.

The series is sequential and must remain on the active UI branch stack until explicitly landed. Each PR must follow [GATES.md](GATES.md), update implementation and UI specifications together, and leave all existing four-page routes directly addressable. Browser code may render and request project context, but project ownership, current-project persistence, workflow status, and stage locking remain server-owned.

### PR117. Persisted Current-Project Context And Project-Scoped Workflow API

Branch: `feat/project-sidebar-context-api`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/199.

Priority: P0 sidebar data foundation.

Depends on: PR116.

Scope:

- Add a server-owned current-project preference for the fixed local workspace user. Store the pointer in the application catalog through a new ordered, checksum-stable migration; do not modify the text of existing migrations. The preference may be absent when no project exists.
- Add `GET /project-context`. Return `{current_project_id, current_project, projects}` where `current_project` is either `null` or `{project_id, name, selected_count, data_loaded}`, and `projects` is a deterministic list of those same project summaries.
- Add `PUT /project-context/current-project` with JSON `{project_id}`. Accept only a project owned by the current local workspace, persist the pointer, and return the same contract as `GET /project-context`.
- Sort projects case-insensitively by `name`, then by `project_id`. Do not use creation time, dictionary iteration order, or browser sorting.
- Define deterministic defaulting: when no preference exists and projects exist, select the first item in the canonical sort order and persist it; when no projects exist, return `current_project_id=null`, `current_project=null`, and `projects=[]` without creating a project.
- When `POST /api/metadata-filter` creates or reuses a project, make that project current in the same successful operation. A failed or zero-result filter must not change the current-project pointer.
- When the current project is deleted, clear the pointer and select the next canonical project if one exists. Deleting a non-current project must not change the pointer.
- Replace implicit latest-selection workflow lookup with `GET /projects/{project_id}/workflow`. Resolve every stage only from records belonging to that project and workspace. Keep `GET /workflow` temporarily as an internal compatibility endpoint only if an existing non-Web caller still requires it; otherwise delete it in this PR.
- Add Python response models or typed row builders for project context rather than assembling different shapes in multiple endpoints. Add matching `ApiProjectSummary`, `ApiProjectContext`, and project-scoped `ApiWorkflow` TypeScript contracts in `apps/web/src/contracts.ts`.
- Add `loadProjectContext()`, `selectCurrentProject(projectId)`, and `loadProjectWorkflow(projectId)` to `apps/web/src/api/client.ts`. Pages and shell code must not call `fetch` directly.
- Update `CONTRACTS.md` and create `docs/ui/layout/sidebar.md` with the server-owned inputs and empty/loading/error contracts needed by PR118. This PR does not render the sidebar.

Acceptance:

- API tests cover zero projects, one project, canonical ordering, explicit selection, repeated selection, process restart with the same catalog, current-project deletion, non-current deletion, unknown project, and a project id owned by another workspace fixture.
- `PUT /project-context/current-project` returns `404` for unknown or inaccessible ids and leaves the previous pointer unchanged.
- Two projects with different selections and runs return different project-scoped workflow identifiers and statuses; switching the current project never leaks identifiers from the previous project.
- Repeating `GET /project-context` and `GET /projects/{project_id}/workflow` performs no writes after the deterministic default has been established.
- Existing project creation, metadata filtering, quote loading, and four workflow-stage tests remain green.
- TypeScript accepts the API responses without `any`, unchecked casts, or duplicated project-summary types.

Out of scope: Sidebar markup, project creation or deletion controls in the Web UI, project renaming, nested projects, drag-and-drop ordering, authentication, and multi-user account switching.

Security: Every project and workflow lookup is resolved inside the fixed local workspace boundary. A supplied project id is an identifier, not authorization; unknown and inaccessible ids return the same `404` shape and never disclose project names or stage identifiers.

Determinism: The current project, project ordering, response serialization, and project-scoped workflow state derive from persisted workspace records and explicit tie-breakers.

Idempotency: Repeating the same current-project selection preserves one preference row and returns byte-equivalent context apart from transport metadata.

### PR118. Desktop Sidebar, Project Dropdown, And Workflow Hierarchy

Branch: `feat/project-sidebar-shell`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/200.

Priority: P0 visible navigation.

Depends on: PR117.

Scope:

- Refactor `apps/web/src/shell/frame.tsx` into a stable application layout with header, sidebar, and main content regions. Keep the EODHD key and `Fetch all metadata` action in the header.
- Add `apps/web/src/shell/project-sidebar.tsx`. At the top render a visible `Project` label and a native `<select>` whose selected option text is the exact current project name. Use project ids only as option values; never display ids as labels.
- Under the dropdown render one `Workflow` navigation landmark as an ordered list. Derive its four entries from `workflowPages` in `apps/web/src/routes.tsx`; do not create a second page array. Render the exact order Metadata Filter, Univariate Statistics, Univariate Filter, Bivariate Statistics.
- Make the hierarchy visually explicit with a project root, one vertical connector, numbered stage markers, and indentation. Use CSS borders and existing text/icon primitives; do not add a chart or tree library.
- Render each stage's server status (`locked`, `ready`, `running`, `complete`, `failed`, or `stale`) as both visible text and a non-color-only marker. The active route uses `aria-current="page"`.
- Keep locked stages visible but render them as non-links with `aria-disabled="true"`. Ready, running, complete, failed, and stale stages remain navigable so users can inspect their state.
- On dropdown change, disable the selector, call `PUT /api/project-context/current-project`, load `GET /api/projects/{project_id}/workflow`, then navigate to the selected project's first non-locked stage. If every later stage is locked, navigate to `/metadata-filter`.
- Dispatch one typed shell context update after a successful switch so all four pages clear project-specific transient state and reload server-owned state. Do not use Redux, Zustand, React Context as a global data cache, browser storage, URL fragments, or a full page reload.
- If switching fails, keep the prior project selected, keep the current page content, expose the server error in an `aria-live` region, and re-enable the selector.
- Define exact shell states: loading skeleton with fixed sidebar width; no-project state showing `No projects yet` and only Metadata Filter as available; ready state; switching state; and recoverable load/switch failure.
- Update all four pages to use the shell's selected `project_id` when invoking project-bound endpoints. A project switch must clear stale run ids, selections, tables, progress, and error messages before the replacement project's requests begin.
- Add styles to the existing production stylesheet `apps/web/styles/app.css`: desktop sidebar width `272px`, header spanning full width, sidebar below the header, independently scrolling main content, and no nested cards. Keep the sidebar visible at viewport widths of `901px` and above.
- Update `docs/ui/header.md`, `docs/ui/layout/sidebar.md`, and all four files under `docs/ui/windows/` with final desktop layout, project-switch behavior, hierarchy states, and page reset rules.

Acceptance:

- At `1440x900` and `1024x768`, the sidebar is visible without user action, is exactly one persistent left column, and does not overlap the header or main content.
- The current project name is visible in the closed dropdown; opening it lists every project once in API order.
- Selecting another project updates the dropdown, hierarchy statuses, route, and page data without reloading the document. Returning to the prior project restores its server-owned workflow state.
- With no projects, the dropdown is disabled, `No projects yet` is visible, Metadata Filter remains navigable, and no synthetic project is created.
- Every workflow item comes from `workflowPages`; tests fail if sidebar labels, paths, order, or count diverge from the canonical route registry.
- Component tests cover loading, empty, ready, locked, switching, failed switch, successful switch, and stale-stage rendering.
- Existing direct links, browser back/forward behavior, EODHD credential submission, metadata refresh, and all four page actions continue to work.
- `npm run typecheck`, `npm run build`, `node --check server.js`, focused Python API tests, and repository `pr-quality` pass.

Out of scope: Mobile drawer behavior, create/rename/delete project controls, free-form hierarchy editing, collapsing individual workflow stages, route additions, and visual-regression baselines.

Security: Project ids are sent only to project-scoped API endpoints. The browser never infers ownership, broadens project access, stores project context persistently, or renders provider credentials in the sidebar.

Determinism: Given the same project-context and workflow responses, the dropdown order, selected project, hierarchy order, status labels, and target route are identical.

Idempotency: Selecting the already-current project performs no navigation reset and creates no duplicate preference, project, selection, run, or artifact.

### PR119. Responsive Sidebar Drawer, Accessibility, And Completion Gate

Branch: `feat/project-sidebar-completion-gate`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/201.

Priority: P1 responsive and regression completion.

Depends on: PR118.

Scope:

- At viewport widths of `900px` and below, replace the persistent sidebar column with a header menu icon button using the existing icon library. Give it the accessible name `Open project navigation`, `aria-expanded`, and `aria-controls` targeting the drawer.
- Render the same `ProjectSidebar` component inside a left drawer; do not duplicate dropdown or hierarchy markup. The drawer width is `min(320px, 88vw)` and main content must remain readable at `320px` viewport width.
- Implement drawer focus management: opening moves focus to the project selector or first available workflow link; `Escape`, backdrop click, successful navigation, and browser route change close it; closing returns focus to the opener. Trap keyboard focus while open and prevent background scrolling.
- Add a backdrop and restrained open/close transition that honors `prefers-reduced-motion`. The drawer must not rely on swipe gestures and must remain usable at 200% browser zoom.
- Use the proper landmarks: one banner, one project-navigation landmark, and one main region. Ensure dropdown label association, visible focus, minimum control size, status text independent of color, and no duplicate navigation landmark while the drawer is closed.
- Add Playwright coverage at `1440x900`, `1024x768`, `768x1024`, and `390x844`. Cover initial project display, project switching, locked hierarchy, direct-link refresh, back/forward navigation, drawer keyboard operation, focus return, no-project state, and failed context request.
- Add screenshot baselines for desktop ready state, desktop no-project state, mobile drawer open, and mobile locked hierarchy. Mask only nondeterministic provider-derived counts; do not mask the project name, stage labels, status labels, or layout geometry.
- Add a canvas/pixel or bounding-box assertion proving the sidebar/drawer is nonblank, inside the viewport, and non-overlapping with header and main content at each tested viewport.
- Extend repository governance tests so the production shell must contain one `ProjectSidebar`, one project dropdown contract, one canonical `workflowPages` registry, and matching `docs/ui/layout/sidebar.md`; forbid a second hard-coded workflow-navigation list.
- Update `README.md` and `docs/ui/page-development.md` with the final responsive shell contract and the rule that future workflow routes automatically flow into the sidebar hierarchy through `workflowPages`.

Acceptance:

- Desktop behavior from PR118 remains unchanged above `900px`; mobile and tablet widths expose the same project name and hierarchy through the drawer.
- Keyboard-only tests can open the drawer, change projects, traverse every available stage, close with `Escape`, and observe focus return without reaching background controls while open.
- Automated accessibility checks report no critical or serious violations on all four routes in desktop and mobile layouts.
- Screenshots show no clipped dropdown text, overlapping landmarks, off-screen drawer content, horizontal page scrolling, or layout shift when statuses change.
- A full synthetic workflow remains project-isolated across two projects before and after refresh, project switching, direct linking, and browser back/forward navigation.
- All commands required by [GATES.md](GATES.md), including Python tests, TypeScript checking, Vite build, Node syntax checking, Playwright, Ruff, Pyright, import-linter, and repository quality checks, pass.

Out of scope: Offline support, touch gestures, user-customizable sidebar width, persisted collapsed state, themes, nested projects, and new workflow pages.

Security: Drawer state and responsive behavior do not change authorization. Browser tests verify that failed or inaccessible project selection reveals no foreign project metadata and leaves the existing project context intact.

Determinism: Fixed fixtures, viewport sizes, reduced-motion settings, project order, and workflow responses produce stable screenshots and focus sequences.

Idempotency: Repeated open/close, route navigation, refresh, and current-project selection leave server state unchanged except for one intentional current-project preference update.

### Project Sidebar Series Completion Gate

The project-sidebar series is complete only after PR117 through PR119 are merged and all required pre-merge and post-merge checks in [GATES.md](GATES.md) pass. Completion additionally requires one server-owned current-project pointer, project-scoped workflow resolution, one canonical `workflowPages` registry, a visible desktop sidebar, an accessible mobile drawer, deterministic project switching, synchronized layout/page specifications, and passing two-project isolation plus visual-regression tests.

## Active Platform-Inspired Simple UI PR Stack

This series applies the shared simplicity principles of modern Google and Apple product interfaces to Portfell without copying either company's branding, proprietary fonts, logos, icons, exact components, trade dress, or full design system. The intended result is a quiet operational interface with strong information hierarchy, restrained color, generous but efficient spacing, familiar controls, immediate feedback, predictable navigation, and accessible motion. Portfell remains visually distinct and optimized for repeated financial research work rather than resembling a consumer marketing page.

The series begins only after the project-sidebar stack is complete. Each PR is independently reviewable, updates implementation and specifications together, and follows [GATES.md](GATES.md). No PR may change financial calculations, server-owned workflow rules, project authorization, API response meaning, or the four canonical route paths.

### PR120. Platform-Inspired Visual Foundations And Core Components

Branch: `refactor/platform-simple-ui-foundations`.

Git status: in progress. PR: TBD.

Priority: P1 visual foundation.

Depends on: PR119.

Scope:

- Create `docs/ui/design-system.md` as the canonical Portfell visual contract. State the principles explicitly: content before decoration, one clear primary action per task region, progressive disclosure, familiar platform behavior, readable density, visible system status, direct manipulation only where reversible, and no decorative elements that compete with financial data.
- Define all production design tokens once in `apps/web/styles/app.css` under `:root`. Use semantic names rather than component-specific names: canvas, surface, surface-subtle, text, text-muted, border, border-strong, accent, accent-hover, focus, success, warning, danger, and disabled.
- Use a neutral canvas and white primary surfaces with one restrained blue accent. Semantic success, warning, and danger colors may appear only for matching status or destructive actions. Forbid gradients, decorative blobs, glassmorphism, tinted page-wide backgrounds, and color-only status communication.
- Define a fixed typography scale with sizes `12`, `14`, `16`, `20`, and `28px`; line heights of at least `1.35`; normal letter spacing of `0`; and weights limited to `400`, `500`, `600`, and `700`. Use a licensed, locally bundled UI typeface or the existing platform stack when bundling would add unjustified weight. Do not reference San Francisco, Product Sans, Google Sans, or remote font CDNs.
- Define spacing tokens on a `4px` base (`4`, `8`, `12`, `16`, `24`, `32`, `48`) and radius tokens limited to `4`, `6`, and `8px`. Shadows are allowed only for floating drawers, menus, dialogs, and focus elevation; ordinary page sections and panels use spacing or a one-pixel border.
- Define stable control heights: `40px` compact desktop fields, `44px` primary/mobile controls, and `32px` icon buttons. All interactive targets remain at least `44x44px` on touch layouts through padding or an invisible target area.
- Add `lucide-react` as the single icon library. Use icons only where they clarify a familiar action or status. Every icon-only button requires an accessible name and tooltip; do not add manually drawn SVGs, emoji, Apple symbols, Google Material Symbols, or mixed icon libraries.
- Refactor `Button`, `Panel`, `StatusBadge`, `LoadingState`, `EmptyState`, and `ProgressStepper` to consume semantic tokens. Keep existing public props unless a typed extension is required. Buttons support primary, secondary, quiet, and danger appearances; only one primary button is allowed per visible task region.
- Add shared `IconButton`, `Field`, and `InlineNotice` components with typed props. `Field` owns label, hint, error, control association, and reserved message height; `InlineNotice` supports information, success, warning, and error without using color alone.
- Replace raw colors, ad hoc border radii, and duplicated focus styles in production CSS with tokens. Do not redesign shell or page layout in this PR beyond changes required to adopt the components.
- Update `docs/ui/page-development.md` so future UI work must use tokens and shared controls, and add a repository test that rejects new raw hexadecimal colors outside the token declaration block.

Acceptance:

- Token documentation lists every semantic token, permitted use, contrast requirement, and prohibited use; production CSS contains one source of truth for each value.
- All shared components render default, hover, active, focus-visible, disabled, loading where applicable, and error where applicable states without layout shift.
- Primary, secondary, quiet, and danger buttons remain distinguishable in forced-colors mode and at 200% zoom.
- Text and controls meet WCAG 2.2 AA contrast; focus indicators have at least a `2px` visible outline with separation from the component edge.
- No route, API call, page order, server-owned status, financial value, or project-switch behavior changes.
- Component tests cover keyboard activation, disabled behavior, accessible names, label/error association, status text, and icon-only tooltips.
- `npm ci`, `npm run typecheck`, `npm run build`, focused UI tests, and repository `pr-quality` pass.

Out of scope: Sidebar layout changes, page-specific form/table redesign, dark mode, user themes, charts, new routes, branded Apple or Google assets, and screenshot baseline replacement.

Security: Shared components never render secret values in hints, errors, tooltips, DOM data attributes, or analytics hooks. Password/provider-key fields preserve their existing write-only behavior.

Determinism: Identical component props and token values produce identical class names, text, icon selection, dimensions, and DOM order.

Idempotency: Re-rendering or repeatedly activating disabled/loading controls performs no duplicate request or state mutation.

### PR121. Platform-Inspired Header, Sidebar, And Navigation Refinement

Branch: `refactor/platform-simple-ui-shell`.

Git status: in progress. PR: TBD.

Priority: P1 shell clarity.

Depends on: PR120.

Scope:

- Apply the foundation tokens and shared components to `ShellFrame` and `ProjectSidebar` without changing the project-context API or canonical route registry.
- Make the desktop header a stable `64px` bar with Portfell as the strongest label, a concise secondary workspace label, and the metadata credential action aligned to the right. Avoid oversized branding, marketing copy, hero treatment, or decorative header backgrounds.
- Keep the desktop sidebar `272px` wide. Use a flat surface separated from main content by one border; do not wrap the sidebar, project selector, or workflow hierarchy in cards.
- Render the project selector as the sidebar's first control with a compact `Project` label, current project name, chevron icon, loading state, empty state, and error state. Long project names truncate visually with a native title/accessible full name and never widen the sidebar.
- Refine the workflow hierarchy to use quiet labels, consistent `40px` rows, one vertical connector, compact status icon plus text, and a restrained accent treatment for the active route. Locked stages remain legible and visible rather than fading below accessible contrast.
- Use familiar symbols from Lucide for menu, chevron, lock, running, complete, warning, and error. Do not place icons in every navigation row unless the icon communicates state.
- Keep the desktop sidebar persistent and the PR119 mobile drawer behavior intact. The mobile header contains only brand, current-project summary, and menu control; credential entry moves into a clearly labeled drawer/header action region if it cannot fit without wrapping.
- Set main content to a readable maximum width between `1120px` and `1280px`, aligned consistently from the sidebar edge. Data tables may use the full available width; forms and status copy should not stretch to unreadable line lengths.
- Preserve normal browser navigation, direct links, visible page titles, sidebar project switching, drawer focus management, and all shell landmarks.
- Update `docs/ui/header.md` and `docs/ui/layout/sidebar.md` with exact desktop/mobile dimensions, truncation, hierarchy styling, icon semantics, and credential-control placement.

Acceptance:

- At `1440x900` and `1024x768`, header, sidebar, and main content align to one spacing grid with no overlap, nested cards, or unexpected horizontal scrolling.
- At `390x844`, the closed shell shows a single menu button and no duplicate hidden navigation landmark; the open drawer exposes the complete project name and hierarchy.
- Project names of 1, 40, 100, and 200 characters do not resize the sidebar, cover controls, or become inaccessible.
- Active, locked, ready, running, complete, failed, and stale hierarchy states are distinguishable by text and shape as well as color.
- Credential entry remains write-only, keyboard reachable, and absent from browser storage, URLs, logs, screenshots, and sidebar content.
- Playwright shell tests cover desktop, tablet, mobile, long names, project switching, all workflow statuses, drawer open/close, and failed context loading.
- Existing four-page route and API regression tests remain green; full frontend build and repository `pr-quality` pass.

Out of scope: Form-field redesign inside pages, table density, new project actions, collapsible desktop sidebar, themes, account controls, and financial visualization.

Security: The refined shell reveals only project names returned by the current workspace context. Truncation and tooltips must not expose ids, foreign names, credentials, or internal error traces.

Determinism: Fixed viewport, project context, route, and workflow state produce stable shell geometry, label order, icon choice, truncation, and focus order.

Idempotency: Reopening navigation, selecting the current route, or selecting the current project creates no duplicate requests or mutations beyond existing explicit refresh behavior.

### PR122. Platform-Inspired Forms, Progress, Tables, And Page States

Branch: `refactor/platform-simple-ui-workspaces`.

Git status: not started. PR: TBD.

Priority: P1 workflow usability.

Depends on: PR121.

Scope:

- Apply the shared visual foundation to all four page components and their specifications without changing API contracts or financial/statistical behavior.
- Give each page one compact title row containing page title, short current-state summary, and at most one primary action. Supporting actions use secondary, quiet, or icon-button appearances according to consequence.
- Replace ad hoc label/input markup with `Field`. Keep labels above controls, hints concise, validation adjacent to the relevant field, and reserved message space where asynchronous validation would otherwise shift the layout.
- Use responsive form grids with explicit minimum widths. Metadata filters use at most four columns on wide desktop, two on tablet, and one on mobile. Predicate rows keep metric, operator, value, and remove action aligned without shrinking text below readable widths.
- Use familiar menus/selects for option sets, icon buttons for add/remove where the symbol is unambiguous, and text plus icon for consequential commands. Destructive removal uses danger styling only when data is actually deleted; removing an unsaved predicate is a quiet action.
- Replace generic paragraphs for locked, empty, failed, stale, and success states with `InlineNotice`, `EmptyState`, or `StatusBadge` as appropriate. Every state includes a concrete next action when one exists; do not add instructional feature-tour copy.
- Keep progress indicators spatially stable. Show label, numeric completion, progress bar, and status summary in that order. Running actions remain in place with a spinner and verb change; they do not resize or move adjacent controls.
- Standardize tables: sticky header only when the table scrolls, tabular numerals for financial values, right alignment for numbers, left alignment for identities, `44px` minimum rows, subtle row hover, visible keyboard focus, and deterministic empty/loading/error rows.
- Add horizontal table scrolling only inside the table region. At narrow widths, preserve column labels and values; do not convert financial tables into nested cards or hide required columns without a documented column-priority rule.
- Centralize formatters for percentages, ratios, counts, covariance, and missing values. Preserve server values and existing precision contracts; do not calculate financial metrics in React.
- Update all four `docs/ui/windows/*.md` specifications with control hierarchy, responsive grids, status components, table alignment, primary-action rules, and exact DOM ordering of progress/action regions.

Acceptance:

- Every visible input has a programmatically associated label; every validation error is associated with its control and announced once.
- Each task region has zero or one primary button. Tests fail when two primary actions appear in the same visible panel.
- Metadata, predicate, univariate, and bivariate controls fit at `1440`, `1024`, `768`, `390`, and `320px` widths without text overlap or page-level horizontal scrolling.
- Numeric table cells use tabular numerals, stable formatting, correct alignment, explicit missing-value text, and unchanged server-provided values.
- Locked, ready, running, complete, failed, stale, empty, and partial-failure states are covered with deterministic fixtures on every applicable page.
- Keyboard tests traverse controls and tables in visual order; icon-only actions expose accessible names and tooltips.
- Existing workflow, project isolation, idempotency, and API tests remain unchanged and green. TypeScript, Vite build, Playwright, and repository `pr-quality` pass.

Out of scope: New calculations, charts, exports, bulk editing, virtualized tables, page routes, API response changes, dark mode, and user-selectable density.

Security: Error and empty states redact provider keys, internal paths, unrestricted dataset ids, and foreign project identifiers. Formatters accept display values only and never broaden data access.

Determinism: Identical server responses and viewport constraints produce identical action hierarchy, field order, status selection, table ordering, formatting, and responsive tracks.

Idempotency: Disabled/running controls reject duplicate activation, and visual state transitions do not create additional projects, selections, runs, or artifacts.

### PR123. Simple UI Motion, Accessibility, Visual Regression, And Completion Gate

Branch: `chore/platform-simple-ui-completion-gate`.

Git status: not started. PR: TBD.

Priority: P1 quality completion.

Depends on: PR122.

Scope:

- Define restrained motion tokens: `120ms` for control feedback, `180ms` for menus/drawers, and no routine transition above `240ms`. Animate only opacity and transform where practical; never animate financial values, table geometry, progress meaning, or layout dimensions.
- Honor `prefers-reduced-motion` by removing nonessential transitions and preserving immediate state feedback. Loading indicators may remain but must not flash faster than accessibility guidance permits.
- Add automated accessibility checks for all four routes and shared shell states using a maintained Playwright-compatible engine. Test keyboard-only navigation, focus visibility, landmark uniqueness, heading order, labels, status announcements, forced colors, 200% zoom, and reduced motion.
- Replace or add visual baselines for desktop (`1440x900`, `1024x768`), tablet (`768x1024`), and mobile (`390x844`, `320x568`) across shell ready/empty/error, drawer open, each page ready, each page running, one representative table, and one validation failure.
- Use deterministic fixtures and mask only genuinely nondeterministic provider-derived values. Never mask project name, route title, controls, workflow statuses, table headers, focus indicator, or geometry under test.
- Add bounding-box and pixel checks proving header, sidebar/drawer, main content, forms, notices, progress, and tables are nonblank, inside the viewport, and non-overlapping. Fail on page-level horizontal scrolling at every target viewport.
- Add governance checks requiring `docs/ui/design-system.md`, semantic token usage, one icon library, one route registry, synchronized layout/page specs, and prohibited-pattern checks for gradients, decorative blobs, raw production colors outside tokens, mixed icon libraries, and Apple/Google brand assets.
- Measure production JavaScript and CSS output. Record a deterministic budget in `docs/ui/design-system.md`; fail CI if the design refinement increases compressed initial JavaScript by more than `25 KiB` or CSS by more than `12 KiB` relative to the PR120 baseline without an approved documented exception.
- Update `README.md` with the final shell description and add a short design review checklist to `docs/ui/page-development.md` covering hierarchy, primary action, token use, responsive fit, keyboard operation, reduced motion, and screenshot review.

Acceptance:

- Automated accessibility scans report no critical or serious violations for every tested route and shared shell state.
- Keyboard-only users can complete project switching and the full four-stage workflow without focus loss, focus traps outside the open drawer, or inaccessible icon controls.
- At 200% zoom and all target viewports, text remains readable, controls remain reachable, and there is no incoherent overlap or page-level horizontal scrolling.
- Reduced-motion tests observe no nonessential animation; standard-motion tests observe only documented durations and properties.
- Visual snapshots are stable across two consecutive clean runs and show a quiet, consistent, content-first Portfell interface rather than Apple or Google branding.
- Bundle budgets, full Playwright suite, Python tests, TypeScript checking, Vite build, Node syntax checking, Ruff, Pyright, import-linter, and every required check in [GATES.md](GATES.md) pass.

Out of scope: Dark mode, custom themes, marketing pages, illustration, 3D, charts, native mobile applications, offline support, analytics, and copying proprietary platform assets or components.

Security: Accessibility, screenshot, and performance artifacts contain only deterministic synthetic fixtures; CI uploads contain no provider credentials, production project names, private data, internal paths, or session material.

Determinism: Pinned browser/runtime versions, fixed fixtures, fixed viewports, reduced-motion settings, token values, and font assets produce stable screenshots, bundle measurements, and accessibility results.

Idempotency: Repeated visual, accessibility, and performance checks do not mutate application state or tracked baselines unless an explicit reviewed update command is run.

### Platform-Inspired Simple UI Series Completion Gate

The platform-inspired simple UI series is complete only after PR120 through PR123 are merged and all required checks in [GATES.md](GATES.md) pass. Completion requires a documented mark-neutral visual language, semantic tokens, one icon library, consistent shared controls, refined shell/sidebar and four workflow pages, responsive and zoom-safe layouts, restrained reduced-motion-aware animation, stable visual baselines, accessibility coverage, bundle budgets, and explicit checks preventing Apple or Google brand assets from entering the product.

## Active Persistent EODHD Credential PR Stack

This series makes one EODHD API key survive browser sessions, API restarts, and Docker recreation for the same server-resolved user. The plaintext key remains write-only: it is never returned to or persisted by the browser. The current local deployment is intentionally single-user after Google authentication removal, so the server owns one stable local principal; future authenticated deployments may supply a session principal through the same typed boundary without changing credential storage.

The implementation order is strict. Persistence and identity land before runtime cutover, and runtime cutover lands before the UI starts relying on saved credential status. Every PR must preserve the existing mocked-provider test path and must not reintroduce Google authentication, browser secret storage, plaintext database columns, or a shared global EODHD key.

### PR124. Stable Local Principal And Credential Repository Ports

Branch: `refactor/persistent-credential-boundaries`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/210.

Priority: P0 identity and persistence boundary.

Depends on: current `main`.

Scope:

- Replace the API-local `LOCAL_WORKSPACE_USER_ID = "user-a"` assumption with a typed `CurrentUserProvider` boundary that resolves a server-owned principal and never accepts a user id from request bodies, query parameters, headers supplied by the browser, or browser storage.
- Add a deterministic single-user `LocalWorkspaceUserProvider` for the current deployment. Its UUID comes from server configuration or an idempotently bootstrapped PostgreSQL local-user row and remains stable across browser sessions, API restarts, and Docker container recreation.
- Define a `CredentialStore` protocol containing only `upsert` and `get`; make `InMemoryCredentialStore` implement it for unit tests without changing its test semantics.
- Change `EodhdCredentialVault` to depend on the protocol rather than the concrete in-memory class. Keep encryption, associated-data ownership checks, masking, revocation, deletion, and provider-call unwrapping inside the vault.
- Add explicit configuration parsing and validation for the local principal. Reject empty, malformed, changing-at-runtime, or browser-provided identities before serving credential routes.
- Document the single-user trust boundary in `ARCHITECTURE.md`, `DECISIONS.md`, and the hosted/local runtime documentation. State that this principal is not multi-user authentication and must not be exposed as an authorization mechanism on a public deployment.

Acceptance:

- Unit tests prove two independently-created `LocalWorkspaceUserProvider` instances resolve the same configured UUID and that two different configured UUIDs never share credential records.
- API tests prove every credential and metadata route obtains identity through `CurrentUserProvider`; no production route references `LOCAL_WORKSPACE_USER_ID` or accepts a caller-selected user id.
- Existing tests continue to inject deterministic test users without PostgreSQL or Docker.
- Static governance tests reject direct construction of production API users from request-controlled values and reject reintroduction of `LOCAL_WORKSPACE_USER_ID`.
- Ruff, Pyright, focused credential/API tests, and the full repository quality gate pass.

Out of scope: PostgreSQL credential SQL, API startup wiring, UI changes, login, cookies, OAuth/OIDC, and multi-user session management.

Security: Identity is resolved exclusively on the server. The local principal is suitable only for the explicitly single-user local deployment and grants no cross-user or public-hosted security guarantee.

Determinism: The same validated server configuration resolves byte-equivalent user identity across processes and container recreation.

Idempotency: Re-resolving or bootstrapping the local principal creates at most one logical active local user and performs no credential mutation.

### PR125. PostgreSQL Encrypted Credential Repository And Schema Migration

Branch: `feat/postgres-credential-repository`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/211.

Priority: P0 durable encrypted storage.

Depends on: PR124.

Scope:

- Add a versioned migration for the complete persistable `EncryptedCredentialRecord`, including credential id, user id, provider, lifecycle status, ciphertext, data nonce, wrapped data key, wrap nonce, key version, canonical associated data, fingerprint HMAC, masked label, and lifecycle timestamps.
- Reconcile the existing `portfell_app.provider_credentials` declaration with the vault model. Add any missing columns, constraints, indexes, and active-record uniqueness rules without destructive table recreation or plaintext migration.
- Implement `PostgresCredentialStore` against the `CredentialStore` protocol using parameterized SQL and the application database role. Serialize associated data structurally and reconstruct it with strict schema/provider/user validation.
- Make credential replacement atomic: one transaction transitions the prior active record and publishes exactly one active `(user_id, provider)` credential. Concurrent replacement must not create multiple active rows.
- Preserve revoked and deleted records for lifecycle audit while `get` returns only the current logical record required by vault status and provider-call operations.
- Add migration, repository, concurrency, malformed-row, and two-user isolation tests against PostgreSQL.

Acceptance:

- A credential encrypted before closing one repository connection is readable and decryptable through a new repository connection with the same user and KEK.
- PostgreSQL contains no plaintext provider key; a database-only test fixture without the external KEK cannot recover the key.
- Wrong-user reads return no record, and manually mismatched associated data fails closed before decryption.
- Concurrent set/replace tests leave exactly one active credential and preserve valid lifecycle history.
- Migration tests succeed from an empty database and from the current schema, and repeated migration execution is a no-op.
- Repository integration tests, schema governance checks, Ruff, Pyright, and the full repository quality gate pass.

Out of scope: FastAPI production wiring, browser behavior, credential validation against live EODHD, key rotation commands, backup procedures, and authentication changes.

Security: SQL is parameterized, PostgreSQL stores only encrypted material and client-safe metadata, and user scope is enforced in every repository query in addition to vault associated data.

Determinism: Row reconstruction and associated-data serialization are canonical; ciphertext remains intentionally nondeterministic.

Idempotency: Retrying an identical logical upsert cannot create a second active credential or alter another user's record.

### PR126. Persistent Credential Runtime Wiring And Secret Configuration

Branch: `feat/persistent-credential-runtime`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/213.

Priority: P0 production cutover.

Depends on: PR125.

Scope:

- Add one production application factory that opens the configured PostgreSQL repository, resolves the stable server-side principal, and injects one persistent `EodhdCredentialVault` into FastAPI dependencies. Keep `HostedApiState` and `InMemoryCredentialStore` available only through explicit test/local-adapter construction.
- Load the versioned key-encryption key and the separate credential-fingerprint HMAC secret from external secret files. Validate exact supported lengths, reject missing/unreadable files, and fail startup without printing paths or secret material.
- Extend Compose secrets and environment contracts for the fingerprint secret and stable local principal while retaining the existing named PostgreSQL volume. Add production-example configuration with placeholders only.
- Make `GET`, `POST`, and `DELETE /api/credentials/eodhd` use the injected persistent vault. Make `POST /api/metadata/fetch-all` unwrap the saved active credential for the current user without requiring a new key submission.
- Return only client-safe credential status fields: provider, lifecycle status, masked label, and key version. Preserve stable structured errors for missing, revoked, deleted, unavailable-key-version, and authentication-failure cases.
- Remove hard-coded development KEK and fingerprint material from the production application path and add governance checks preventing their reintroduction.

Acceptance:

- An integration test saves a synthetic key, destroys the FastAPI application and database connection, creates a new application instance, and successfully performs a mocked metadata fetch without resubmitting the key.
- A Docker integration test recreates the API container while preserving the database volume and proves credential status plus mocked provider use remain available to the same principal.
- Starting with a missing/invalid KEK, missing fingerprint secret, invalid principal, or unavailable database fails closed with redacted diagnostics.
- Changing the principal produces `credential_not_found`; restoring the original principal restores access without rewriting the credential.
- API responses, logs, health output, Compose inspection, and test artifacts contain no plaintext provider key or secret-file contents.
- Focused integration tests, Compose configuration validation, secret-scanning checks, Ruff, Pyright, and the full repository quality gate pass.

Out of scope: UI controls, browser storage, multi-user login, automatic KEK rotation, backup/restore automation, and provider-key recovery or display.

Security: Secrets enter only through external files; plaintext exists only during bounded provider calls; application startup fails closed when durable encryption dependencies are unavailable.

Determinism: The same database, principal, KEK version, and fingerprint secret resolve the same logical credential status across process and container restarts.

Idempotency: Recreating the application or container performs no credential rewrite, duplicate bootstrap, or provider request until an explicit user action occurs.

### PR127. Saved Credential Status, Replace, Delete, And Keyless Refresh UI

Branch: `feat/saved-credential-ui`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/214.

Priority: P1 session-independent credential UX.

Depends on: PR126.

Scope:

- Load `GET /api/credentials/eodhd` when `ShellFrame` starts and model `loading`, `missing`, `active`, `revoked`, `deleted`, and `error` states with typed API contracts.
- Keep the password field empty on every page load. For an active credential, render only the server-provided masked label and a clear `Saved` status; never prefill, reconstruct, cache, or retain plaintext in browser storage.
- Allow `Fetch all metadata` with an active saved credential and an empty input. If the user enters a new key, save it first and then fetch metadata; clear the plaintext field immediately after the successful credential save, before starting the provider workflow.
- Add explicit `Replace key` and `Delete key` actions. Replacement requires a newly-entered value; deletion requires confirmation, calls `DELETE /api/credentials/eodhd`, clears client credential status, and disables keyless metadata refresh.
- Prevent duplicate save/fetch/delete requests, retain accessible progress and error announcements, and distinguish credential errors from metadata-provider errors without exposing response bodies or secret values.
- Update `docs/ui/header.md`, relevant page specifications, and browser fixtures to describe the write-only persisted credential lifecycle.

Acceptance:

- Browser tests cover first entry, successful save, page reload, new browser context, keyless metadata fetch, replacement, deletion, revoked/deleted status, API failure, and recovery.
- After reload or a new browser context, the UI displays only the masked label and can fetch metadata without key re-entry.
- Plaintext keys are absent from `localStorage`, `sessionStorage`, IndexedDB, cookies, URLs, history state, DOM attributes, screenshots, console output, network responses, and persisted test artifacts.
- The fetch button is enabled when either a non-empty replacement value or an active saved credential exists, and disabled for missing/revoked/deleted credentials with an empty input.
- Keyboard and 200% zoom tests cover status, replacement, confirmation, deletion, and error recovery without overlap or focus loss.
- TypeScript checking, Vite build, focused browser tests, accessibility checks, and the full repository quality gate pass.

Out of scope: Showing/copying the saved plaintext key, browser password-manager integration, login/account UI, multiple provider keys, automatic credential validation schedules, and key rotation administration.

Security: The browser receives only masked lifecycle status and never becomes a secret persistence boundary.

Determinism: Identical server status produces identical labels, enabled states, action order, and accessible announcements.

Idempotency: Repeated status loads are read-only; repeated guarded clicks cannot duplicate credential mutation or metadata refresh requests.

### PR128. Credential Restart, Rotation, Backup, And Completion Gate

Branch: `chore/persistent-credential-completion-gate`.

Git status: not started. PR: TBD.

Priority: P1 operational assurance.

Depends on: PR127.

Scope:

- Add an operator-only, non-HTTP command that rewraps active credential data keys from one KEK version to another without EODHD key re-entry. Require explicit old/new external secret files, dry-run output, transaction boundaries, and redacted per-record results.
- Add encrypted-database backup and restore documentation that treats PostgreSQL backup and KEK/fingerprint-secret recovery as separate protected assets. Document that losing the KEK makes credentials unrecoverable and that database backup alone must not decrypt them.
- Add deterministic restart coverage for API process restart, API container recreation, full Compose stop/start with preserved volumes, restored database, unchanged principal, changed principal, valid KEK rotation, missing old KEK, and tampered ciphertext.
- Add repository gates that reject plaintext credential fields, browser secret persistence, hard-coded production cryptographic material, credential responses containing ciphertext/fingerprints, and production use of `InMemoryCredentialStore`.
- Update `README.md`, `ARCHITECTURE.md`, `CONTRACTS.md`, `RISKS.md`, and deployment examples with final credential ownership, lifecycle, restore, deletion, and rotation behavior.
- Record the exact pre-merge and post-merge validation commands required by [GATES.md](GATES.md), including a clean Docker rebuild from the merged branch.

Acceptance:

- Rotation tests prove the plaintext credential remains usable after rewrap, ciphertext data is not decrypted outside the bounded rotation service, and interruption leaves every record usable under either the old or committed new version.
- Backup/restore tests recover credential usability only when database, matching principal, and required KEK version are present.
- Restart tests prove one initial key submission supports later browser sessions and API/container restarts without re-entry.
- Negative tests prove database-only compromise, wrong principal, wrong KEK, missing secret, tampering, revoked/deleted records, and browser storage inspection cannot yield or use plaintext credentials.
- Full pytest, Ruff, Pyright, import checks, TypeScript checking, Vite build, browser tests, secret scanning, Compose validation, and all required gates pass from a clean checkout.

Out of scope: Public multi-user authentication, cloud-specific KMS integration, automated backup scheduling, disaster-recovery infrastructure, multiple EODHD credentials per user, and recovery of a lost provider key.

Security: Rotation and restore are offline operator workflows with redacted output; no new HTTP endpoint exposes cryptographic administration.

Determinism: Fixed synthetic records, principal, key versions, and backup fixtures produce stable rotation plans and restart assertions.

Idempotency: Re-running a completed rotation or restore verification performs no additional rewrap and creates no duplicate active credential.

### Persistent EODHD Credential Series Completion Gate

The persistent EODHD credential series is complete only after PR124 through PR128 are merged and all required checks in [GATES.md](GATES.md) pass. Completion requires a stable server-owned principal, a PostgreSQL-backed encrypted credential repository, external versioned cryptographic secrets, restart-safe API wiring, masked saved-status UI, keyless refresh for an active saved credential, replace/delete lifecycle controls, rotation and restore procedures, and automated proof that plaintext keys never enter browser persistence, PostgreSQL plaintext, logs, responses, images, or repository artifacts.

## Active Hosted Multi-Tenant Portfell PR Stack

Priority policy: security and authorization boundaries precede UI work. No endpoint may expose market or derived data before identity, credential encryption, user entitlement snapshots, and scoped analytical input enforcement exist. Every PR must use synthetic credentials and mocked provider responses in tests.

### PR84. Hosted Architecture Decision, Threat Model, And Active-Backlog Reset

Branch: `docs/hosted-multitenant-security-architecture`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/127.

Priority: P0 governance and security foundation.

Depends on: current `main`.

Scope: Record the PostgreSQL-first hosted architecture, Google-only authentication, encrypted persistent EODHD credentials, shared content-addressed market and statistics stores, per-user entitlements, immutable User Data Snapshots, and local-mode compatibility. Add trust boundaries, data-flow diagrams, attacker model, credential lifecycle, account deletion semantics, backup boundaries, provider-licensing assumptions, and explicit prohibited designs. Update `ARCHITECTURE.md`, `DECISIONS.md`, `RISKS.md`, `GOALS.md`, and documentation checks so future hosted work cannot silently revert to SQLite, session-only keys, global current pointers, or unrestricted lake reads.

Acceptance: Documentation tests verify that every hosted goal maps to an active PR; the architecture identifies Web, API, PostgreSQL, shared storage, external secret storage, Google, and EODHD trust boundaries; all secrets and personal data are classified; unresolved licensing blocks public-hosted readiness; and the local CLI path remains documented.

Security: The decision explicitly forbids secrets in Git, database plaintext, container images, CI artifacts, URLs, browser storage, client analytics, or logs. It requires an external key-encryption key and separates database backups from key recovery backups.

Determinism: Architecture and readiness status derive from versioned static decision records, not the deployment environment or live provider calls.

Idempotency: Re-running documentation validation against unchanged records produces no repository or runtime changes.

### PR85. PostgreSQL Application Catalog, Migrations, Roles, And Row-Level Security

Branch: `feat/postgres-multitenant-catalog`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/128.

Priority: P0 persistence and isolation foundation.

Depends on: PR84.

Scope: Add PostgreSQL dependencies, migration tooling, repository interfaces, and schema for users, external identities, sessions, provider credentials, projects, download runs, market objects, dataset snapshots, user grants, selections, analysis runs, artifacts, artifact inputs, and audit events. Create separate owner, migration, application, and read-only roles. Enable and force Row-Level Security on user-owned tables, pass the authenticated user id through transaction-local PostgreSQL settings, and prevent the application role from owning tables or bypassing RLS.

Acceptance: Migration tests start from an empty database, upgrade to head, exercise downgrade policy where supported, and prove uniqueness, foreign-key, lifecycle, and immutability constraints. Isolation tests prove User A cannot select, insert, update, or delete User B's rows even through repository mistakes. The schema records immutable artifact references without storing EODHD plaintext keys or large analytical tables in PostgreSQL.

Security: Database URLs and passwords are loaded from secret files outside the checkout. PostgreSQL is not published to the public host interface by default. The application role is non-superuser, has no `BYPASSRLS`, and cannot alter security policies.

Determinism: Migration order, constraint names, normalized identifiers, and serialized JSON fields are versioned and stable.

Idempotency: Re-applying migrations to the same schema is a no-op; retries do not duplicate identities, grants, projects, runs, or artifacts.

### PR86. Google-Only OpenID Connect And Server-Side Session Security

Branch: `feat/google-oidc-authentication`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/129.

Priority: P0 authenticated user boundary.

Depends on: PR85.

Scope: Add Google OpenID Connect using authorization code flow with PKCE, state, nonce, strict redirect URI validation, server-side token exchange, issuer/audience/signature/expiry checks, and Google's stable `sub` claim as the external identity key. Create short-lived, rotating server-side sessions with opaque HttpOnly, Secure, SameSite cookies; CSRF protection for state-changing requests; session revocation; login/logout/status routes; and optional domain allowlisting disabled by default.

Acceptance: Tests cover first login, repeat login after months, changed Google email with unchanged `sub`, invalid issuer/audience/signature/nonce/state, replayed callback, expired session, revoked session, CSRF failure, logout, and concurrent sessions. A new user begins with no market-data grants, selections, projects, or analysis access.

Security: Google client secrets, session signing or hashing keys, and callback configuration are runtime secrets or deployment configuration, never committed values. Tokens are never logged or returned after session establishment.

Determinism: One `(provider, subject)` identity resolves to one internal user regardless of mutable email or display-name fields.

Idempotency: Repeated valid login for the same Google `sub` updates permitted profile metadata without creating duplicate users or identities.

### PR87. Encrypted EODHD Credential Vault With External Key Management

Branch: `feat/encrypted-eodhd-credential-vault`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/130.

Priority: P0 credential confidentiality.

Depends on: PR86.

Scope: Persist one EODHD credential per user using envelope encryption: a random per-credential data-encryption key encrypts the provider key with authenticated encryption; the data key is wrapped by a versioned Portfell key-encryption key supplied from a file or secret manager outside Git and PostgreSQL. Bind ciphertext to credential id, user id, provider, and schema version as associated data. Add set, replace, validate, status, revoke, delete, unwrap, and key-rotation services. Return only masked status metadata to clients.

Acceptance: Tests cover encrypt/decrypt round trips, wrong user or associated-data rejection, tampering, wrong key version, replacement, revocation, deletion, KEK rotation without provider-key re-entry, unavailable KEK fail-closed behavior, and redaction in structured logs and exceptions. Database dumps and shared storage contain no plaintext or reversible material without the external KEK.

Security: Plaintext provider keys exist only in bounded process memory during validation and provider calls. The KEK is never exposed to Web, PostgreSQL, CI, test reports, exception payloads, or ordinary application logs. Credential fingerprints use a separate keyed HMAC and are never returned in full.

Determinism: Ciphertext is intentionally nondeterministic; logical credential identity and status transitions are deterministic from user, provider, and versioned lifecycle rules.

Idempotency: Re-submitting the same valid key updates permitted metadata or reuses the logical credential without creating multiple active credentials.

### PR88. Shared Content-Addressed Market Observation Store

Branch: `feat/shared-market-observation-store`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/131.

Priority: P0 shared physical data foundation.

Depends on: PR85.

Scope: Add immutable normalized market observations and append-only Parquet segments for EODHD quotes, dividends, splits, metadata, and later supported datasets. Define a stable business key and payload hash per observation; retain corrected historical values as new revisions rather than overwriting prior observations. Add atomic temporary-write, validation, content-hash, fsync, rename, and PostgreSQL catalog publication. Store segment and manifest paths outside user-specific directories.

Acceptance: Tests cover identical responses, overlapping date ranges, appended dates, corrected rows with unchanged row count and end date, deleted provider rows, duplicate response rows, interrupted publication, corrupt segments, and concurrent writers. Identical normalized observations result in one physical observation and one catalog identity.

Security: Shared physical presence grants no user access. Storage paths and content hashes are not accepted directly as authorization credentials. Parquet data contains no user id, provider key, session token, or credential fingerprint.

Determinism: Observation ids derive from provider, dataset type, listing identity, business key, normalized payload, and schema version. Segment manifests are canonical and independent of worker completion order.

Idempotency: Re-ingesting identical observations produces no duplicate physical rows or catalog objects; retries publish at most one valid object.

### PR89. User Data Entitlements, Download Provenance, And Immutable Snapshots

Branch: `feat/user-data-entitlement-snapshots`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/132.

Priority: P0 authorization semantics.

Depends on: PR87 and PR88.

Scope: Model successful provider-backed download runs, exact returned observation sets, user grants, snapshot manifests, parent snapshots, revision selection, current project snapshot pointers, revocation, account deletion, and garbage-collection references. A grant may be created only after a successful EODHD response using the authenticated user's active credential. Build an entitlement resolver that creates an immutable User Data Snapshot containing the exact observations and revisions visible to that user at that point in time.

Acceptance: Tests prove a new user sees zero data; User A cannot see later observations downloaded by User B; overlapping physical data is shared without shared entitlement; User A gains the newer range only after their own successful refresh; historical corrections from another user's request remain invisible until an own refresh; old analyses retain old snapshots; and account deletion removes credentials and grants without deleting objects still referenced by other users.

Security: Every grant is linked to authenticated user, credential, provider request, normalized response, and immutable snapshot. No API or service may infer access from object existence, listing identity, date range, content hash, or another user's run.

Determinism: Snapshot hashes derive from canonically ordered observation ids and revision rules, not grant timestamps or filesystem order.

Idempotency: Replaying the same successful response for the same user resolves to the same logical snapshot and does not duplicate grants or manifests.

### PR90. User-Key-Backed EODHD Ingestion And Refresh Planner

Branch: `feat/user-scoped-eodhd-ingestion`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/133.

Priority: P0 usable BYOK download path.

Depends on: PR89.

Scope: Refactor EODHD workflows to accept an injected authenticated credential context rather than loading a global token. Add user-scoped full and gap-aware download planning, Free versus paid capability discovery, usage accounting, resumable runs, provider rate-limit handling, per-credential request serialization, shared-object deduplication, and atomic entitlement publication. Even when all requested observations already exist physically, execute the provider request with the current user's key before granting access.

Acceptance: Mocked integration tests cover Free and paid keys, invalid and revoked keys, quota exhaustion, retries, partial symbol failure, resume, overlapping user requests, existing shared objects, newer end dates, corrections, and concurrent identical requests. A successful run publishes a new User Data Snapshot; a partial or failed run cannot grant unreturned data.

Security: Provider URLs, headers, tokens, request diagnostics, and error bodies are centrally redacted. Decryption is performed immediately before the outbound request, and plaintext credentials are never passed to workers that do not perform provider access.

Determinism: Run plans derive from explicit requested scope, prior user snapshot, provider capability contract, and requested as-of date. Operational retry timing cannot affect data identities.

Idempotency: Resuming a run requests only incomplete work, deduplicates shared observations, and publishes no duplicate grants or snapshots.

### PR91. Scoped Analytical Input Boundary And Local Adapter Compatibility

Branch: `refactor/scoped-analytical-inputs`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/134.

Priority: P0 prevention of cross-user analytical leakage.

Depends on: PR90.

Scope: Introduce typed `ScopedMarketInputs`, `UserDataSnapshotRef`, `SelectionInputRef`, and snapshot-reader ports. Refactor hosted workflows so univariate, bivariate, multivariate, production portfolio, backtest, recommendation, and report paths receive already authorized immutable inputs and never call unrestricted `read_silver_quotes`, global current-selection files, or filesystem scans. Preserve current local CLI behavior through a `LocalLakeSnapshotReader`; add a hosted `EntitledSnapshotReader` backed by PostgreSQL and shared manifests.

Acceptance: Architecture tests fail when hosted services import unrestricted lake readers. Multi-user tests inject extra global observations and prove they cannot influence another user's returns, statistics, data-quality checks, optimization, backtests, or recommendations. Local CLI regression tests retain current commands and outputs.

Security: `user_id`, project ownership, snapshot ownership, and selection ownership are checked before resolving physical objects. The mathematical core receives no database credentials and cannot broaden the authorized scope.

Determinism: Scoped input identities derive from immutable snapshot, selection, dataset schema, and revision-policy ids.

Idempotency: Re-resolving unchanged authorized inputs returns the same immutable input references without copying market rows.

### PR94. Content-Addressed Multivariate, Portfolio, Backtest, And Report Artifacts

Branch: `feat/content-addressed-portfolio-artifacts`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/137.

Priority: P1 portfolio-level reuse.

Depends on: PR93.

Scope: Build shared multivariate and downstream artifact identities from the sorted authorized listing-input artifact ids, selection definition and membership, return matrix, risk model, constraints, optimizer settings, costs, walk-forward windows, stress settings, recommendation template, and algorithm versions. Store physical artifacts globally while creating separate user-owned analysis runs and project references. Remove user id from physical cache keys and include it only in authorization and provenance records.

Acceptance: Two users with identical authorized snapshots and settings reuse one physical artifact while retaining separate runs. Different visible end dates, revisions, selections, constraints, costs, risk models, or algorithm versions produce distinct artifacts. Direct artifact-id access, cross-project run access, and stale project pointers are rejected.

Security: Every response resolves through an authenticated user-owned analysis run; no endpoint serves shared artifact paths directly. Artifact dependency closure is checked before reuse.

Determinism: Artifact ids and reports derive only from exact immutable inputs, explicit settings, and versioned algorithms.

Idempotency: Repeated identical analyses return the existing completed result or join the active computation without duplicate artifacts, portfolio rows, or reports.

## Active Architectural Refactor PR Stack

This series addresses the three highest-leverage structural risks in the active codebase. The order is deliberate: first establish a narrow hosted application boundary, then place quote ingestion behind that boundary, and finally isolate the numerical portfolio core. Each PR is independently mergeable and behavior-preserving except for explicitly stated internal contracts. No PR may add a compatibility runtime, duplicate implementation, new external service, or unrelated product behavior.

### PR129. Hosted API Routers, Application Services, And State Ports

Branch: `refactor/hosted-api-boundaries`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/218.

Priority: P0 architecture and change-isolation baseline.

Depends on: current `main`.

Scope:

- Reduce `portfell.hosted_api` to the FastAPI composition root, runtime factory, stable public request/response exports, and `app` entry point.
- Move Pydantic request models and JSON response serializers into one API-contract module with no imports from workflows, lake paths, credential implementations, or mutable repositories.
- Move `HostedApiState`, project/selection/analysis records, ownership checks, idempotency references, audit writes, and local-workspace serialization into explicit state and repository-port modules.
- Move metadata, project/workflow, quote-run, and research orchestration into application-service modules. Services accept typed ports and values; they do not depend on FastAPI `Request`, `Depends`, `BackgroundTasks`, headers, or `HTTPException`.
- Split route registration by credential, metadata/project, quote-run, and research concerns. Routers translate HTTP input/output only and call application services; they do not read the lake or mutate repository dictionaries directly.
- Add import-linter contracts enforcing `routes -> application services -> ports/domain`, forbidding reverse imports and direct route imports of `bronze`, `silver`, `workflows`, `table_io`, or concrete credential stores.
- Keep the existing route paths, methods, status codes, structured error codes, OpenAPI field names, runtime factories, and Docker entry point unchanged. Do not add routes, persistence behavior, authentication behavior, or UI changes.

Acceptance:

- A checked-in normalized OpenAPI snapshot and API contract tests prove the same paths, methods, request schemas, response fields, status codes, and error codes before and after extraction.
- Existing hosted API, credential, project, workflow, security, and Web contract tests pass without weakening assertions or deleting coverage.
- `src/portfell/hosted_api.py` contains only composition/export code and is at most 250 nonblank, non-comment lines; no extracted production module exceeds 500 such lines.
- Route modules contain no direct filesystem calls, `LakePaths`, workflow implementation imports, mutable state-dictionary access, or provider-client construction.
- Import-linter and architecture checks fail on fixture violations of each new dependency rule.
- Ruff, Pyright, all test shards, coverage, architecture checks, schema validation, and every required gate in [GATES.md](GATES.md) pass.

Out of scope: PostgreSQL cutover, run persistence, quote-progress redesign, authentication changes, provider concurrency changes, endpoint additions, browser changes, and analytical refactors.

Security: Ownership, credential redaction, CSRF, idempotency, and audit behavior remain server-owned and are tested at both route and service boundaries; extraction must not introduce a route that can access an unscoped repository or lake path.

Determinism: Identical state and requests produce byte-equivalent normalized JSON and stable ids before and after extraction; module placement cannot enter hashes or persisted rows.

Idempotency: Existing idempotency keys, active-run reuse, project identities, and selection identities retain exactly the same lookup and mutation semantics after extraction.

### PR133. Hosted Research Service Boundary Completion

Branch: `refactor/hosted-research-boundaries`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/238.

Priority: P0 architecture enforcement and restart-safe research orchestration.

Depends on: current `main`.

Scope:

- Replace the hidden monolithic `research_service.py` implementation with one route-facing facade and separate univariate, bivariate, and analysis services.
- Move bivariate matrices, summaries, and portfolio diagnostics into pure typed calculation modules.
- Put mutable hosted research state behind a typed repository port, local lake access behind a research-data port, and workspace writes behind a persistence port.
- Compose concrete local adapters only in `hosted_api`; application services must not import local runtime, lake paths, workspace persistence, or repository adapters.
- Remove dynamic imports and broad Pyright suppressions from the hosted research path.
- Extend import, typing, module-size, and regression gates so the real implementation cannot escape through a compatibility wrapper or filename change.

Acceptance:

- `research_service.py` no longer exists and every route-facing research operation retains its existing method and API behavior through `hosted_research_service.ResearchService`.
- Univariate, bivariate, and analysis services are independently typed, below the hosted module-size limit, and operate through injected ports.
- Bivariate diagnostics and matrix read models are pure functions with no hosted state, filesystem, HTTP, or persistence dependencies.
- Architecture tests fail if a hidden research service, dynamic `import_module` dependency, broad unknown-type suppression, concrete adapter import, or oversized hosted module is introduced.
- Focused hosted and bivariate tests, strict Pyright, Ruff, Import Linter, the full PR quality gate, and Docker health validation pass.

Security: Repository operations retain mandatory user ownership checks, while services cannot open unrestricted lake paths or bypass the scoped data adapter.

Determinism: Existing run identities, selection identities, matrix ordering, diagnostics, and serialized API responses remain stable for identical inputs.

Idempotency: Existing active-run reuse and analysis idempotency remain unchanged; completed univariate filters and bivariate results are persisted after every durable transition.

### PR134. Hosted Research Boundary Coverage Completion

Branch: `fix/hosted-research-coverage`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/240.

Priority: P0 post-merge quality-gate repair.

Depends on: PR133.

Scope: Add focused tests for the extracted hosted-research service transitions, injected persistence and data ports, local univariate adapter fallbacks, and bivariate diagnostic edge cases so the repository-wide coverage gate measures the new architecture directly.

Acceptance: The exact combined coverage command passes the unchanged 95% threshold; strict Pyright, Ruff, architecture checks, and the full PR gate pass without coverage exclusions, pragma suppression, or production-code inflation.

Security: Tests use synthetic users, instruments, and temporary lake roots and do not access credentials or external provider services.

Determinism: All new cases use fixed rows, inline executors, and injected fake ports; no wall clock, network, or process scheduling affects assertions.

Idempotency: Repeated test runs leave repository state unchanged and create artifacts only under pytest-managed temporary directories.

### PR130. Typed Quote Ingestion Stage Pipeline And Progress Contract

Branch: `refactor/quote-ingestion-pipeline`.

Git status: not started. PR: TBD.

Priority: P0 ingestion reliability, observability, and testability.

Depends on: PR129.

Scope:

- Introduce immutable `QuoteIngestionRequest`, `QuoteIngestionPlan`, `QuoteIngestionProgress`, and `QuoteIngestionResult` contracts owned by a quote-ingestion application module.
- Represent the existing work as the ordered stages `planning`, `quotes`, `dividends`, `splits`, `silver`, and `manifests`. Each stage reports its own completed/total counts and contributes to one deterministic aggregate total.
- Move gap-aware per-listing planning, EODHD dataset execution, Silver per-listing conversion, and manifest publication behind typed stage functions. Retain the existing EODHD dataset strategies and table schemas rather than creating parallel quote/dividend/split implementations.
- Resolve worker count once at the application boundary and pass it explicitly to every parallel stage. Keep bounded execution, per-root locking, atomic table writes, and memory-safe per-listing processing.
- Replace positional integer progress callbacks with one typed progress event. The hosted service serializes that event; the CLI may adapt it to logs without owning progress arithmetic.
- Make the final result expose provider successes/failures, selected listing count, Silver row count, coverage count, and exact completed stage totals. Failed items remain isolated and do not discard successful Bronze writes.
- Remove obsolete progress arithmetic and duplicate orchestration from `portfell.workflows` only after all callers use the typed pipeline. Do not add Celery, Redis, a message broker, a scheduler, or a second run-state store.

Acceptance:

- Fixture runs with one, multiple, partially cached, fully cached, and partially failing listings emit the exact documented stage order and monotonic progress; aggregate completed never exceeds aggregate total.
- A fully cached rerun performs no provider request for covered quote intervals and preserves existing Bronze rows, Silver rows, coverage rows, and gap manifests.
- Golden table tests prove byte-equivalent normalized Bronze, Silver, coverage, gap, and run-manifest content for unchanged fixtures.
- Peak-memory regression coverage proves planning and post-processing read at most one selected listing's Silver rows at a time; tests fail if a full-lake quote read returns to the hosted path.
- Concurrency tests prove at most the resolved worker count is active, one logical run owns the module lock, and a duplicate request joins the existing active run rather than starting work.
- Hosted quote status uses the typed stage and counts; the browser contains no independent task-total or progress calculation.
- Ruff, Pyright, all test shards, coverage, architecture checks, schema validation, and every required gate in [GATES.md](GATES.md) pass.

Out of scope: Durable run recovery after process death, database-backed queues, new provider endpoints, schema renames, retention changes, retry-policy changes, and UI redesign.

Security: Provider keys remain bounded to client construction and never enter requests, plans, progress events, results, logs, manifests, hashes, or browser responses; user/project scope is resolved before planning.

Determinism: Canonically ordered listings and fixed stage order produce identical plans, totals, manifests, and result summaries for identical lake state, dates, selection, and configuration.

Idempotency: Repeating an identical request reuses covered data, merges rows by canonical keys, joins an active logical run, and produces no duplicate Bronze observations, manifests, or run records.

### PR131. Portfolio Solver Core, Diagnostics, And Persistence Boundaries

Branch: `refactor/portfolio-core-boundaries`.

Git status: not started. PR: TBD.

Priority: P1 numerical correctness and optimizer extensibility.

Depends on: current `main`.

Scope:

- Keep `portfell.portfolio` as the stable public facade while moving implementation into cohesive modules under `portfell.portfolio_parts`.
- Move `PortfolioConstraints`, validation, covariance completeness, bound activity, and constraint residuals into a constraints module with no lake or CLI dependencies.
- Move objective-independent solver dispatch, production-solver adapters, candidate-limit policy, fallback enumeration, and solver diagnostics into a solver-orchestration module.
- Move minimum variance, minimum CVaR, maximum diversification, risk contribution, and HRP objective calculations into objective modules that consume typed matrices and constraints and perform no file I/O.
- Move row construction, lake reads/writes, and replacement semantics into a portfolio-artifact adapter. It may call the numerical core, but the numerical core cannot import `LakePaths`, schemas, table I/O, CLI, hosted API, or workflows.
- Preserve all current facade function signatures and exported dataclasses used by callers. Re-exports are allowed only from `portfell.portfolio`; no second implementation or compatibility package may remain.
- Add import-linter contracts enforcing `portfolio facade/artifact adapter -> solver orchestration -> objectives/constraints`, with objectives and constraints forbidden from importing persistence or application layers.

Acceptance:

- Golden numerical tests prove identical weights, objective values, diagnostics, constraint violations, linkage rows, cluster rows, and risk-contribution rows for every existing optimizer fixture, including failure and fallback cases.
- Repeated runs preserve current deterministic row ordering, float tolerances, solver selection, candidate limits, and artifact replacement keys.
- `src/portfell/portfolio.py` is at most 300 nonblank, non-comment lines and contains no objective implementation, candidate enumeration, clustering recursion, or direct optimization loop.
- Every objective can be tested from in-memory typed inputs without constructing `LakePaths` or writing files; artifact tests use fake or temporary adapters without invoking private objective functions.
- Import-linter and architecture checks reject objective-to-I/O, objective-to-workflow, and constraints-to-solver-orchestration reverse dependencies.
- No algorithm version, persisted schema, public CLI option, workflow output, or recommendation input changes in this PR.
- Ruff, Pyright, all test shards, coverage, architecture checks, schema validation, and every required gate in [GATES.md](GATES.md) pass.

Out of scope: New optimizers, changed numerical tolerances, performance tuning, GPU/vector-library adoption, portfolio schema changes, profile changes, recommendation changes, and browser features.

Security: The numerical core accepts already-scoped rows and cannot open unrestricted lake paths, resolve users, inspect credentials, or broaden selection membership.

Determinism: Identical ordered matrices, constraints, solver configuration, and algorithm versions produce the same selected method, weights, diagnostics, and artifact rows within the existing exact/tolerance assertions.

Idempotency: Repeating portfolio construction with identical inputs preserves artifact identities and replacement keys and does not append duplicate weight, cluster, linkage, diagnostic, or risk-contribution rows.

### Architectural Refactor Series Completion Gate

The architectural refactor series is complete only after PR129 through PR131, PR133, and PR134 are merged and every required pre-merge and post-merge check in [GATES.md](GATES.md) passes. Completion requires normalized API-contract equivalence, enforced hosted research boundaries, typed and monotonic quote-stage progress, delta-only ingestion, numerical portfolio equivalence, the new import-linter dependency rules, no duplicate implementation or compatibility runtime, and updated [ARCHITECTURE.md](ARCHITECTURE.md) module ownership descriptions.

## Current Architectural Decision

Portfell remains a public open-source repository, while the hosted deployment is a private runtime environment.

The target system has these non-negotiable properties:

- Google is the only end-user authentication provider.
- PostgreSQL is the primary application database for users, identities, encrypted provider credentials, projects, download provenance, entitlements, selections, analysis runs, and artifact catalogs.
- EODHD keys are encrypted at rest with envelope encryption. The key-encryption key is never stored in Git, PostgreSQL, container images, build artifacts, logs, or GitHub Actions.
- Runtime secrets live outside the repository checkout and are mounted only into services that require them.
- EODHD market observations are stored once in a shared, content-addressed, immutable physical store.
- A user can see only observations that were returned by an EODHD request executed with that user's own stored key.
- Existing shared observations may prevent a duplicate physical write, but may never create a user entitlement without a successful user-key-backed provider request.
- New observations downloaded by one user do not become visible to another user until that other user performs a successful refresh with their own key.
- Every user analysis is pinned to an immutable User Data Snapshot containing the exact observations and revisions visible to that user.
- Univariate, bivariate, multivariate, portfolio, backtest, and report artifacts are globally deduplicated by exact input hashes and algorithm versions, while visibility is granted only through user-owned analysis runs.
- Hosted analytical code must consume resolved scoped inputs and must never scan unrestricted global Silver or Gold data.
- The local CLI and analytical core remain usable without Google authentication or PostgreSQL through explicit local adapters.
- Public hosting remains blocked until provider licensing, privacy, backup, credential, and security readiness gates pass.

## Series Completion Gate

The four-page UI series is complete only after PR110 through PR115 are merged and all of the following are true:

- exactly four production pages exist in the required order;
- every page invokes a real backend workflow and has locked, ready, running, complete, failed, and stale behavior where applicable;
- quote and bivariate progress are server-reported rather than simulated in the browser;
- every run and selection is scoped to immutable authenticated-user inputs;
- repeated identical commands reuse existing logical state;
- upstream changes invalidate downstream state deterministically;
- no placeholder page, retired route, compatibility renderer, duplicate registry, synthetic compute endpoint, or legacy documentation remains;
- all Python, TypeScript, build, browser, security, and repository gates pass.

Hosted deployment remains subject to the independent security, licensing, privacy, backup, credential, and readiness requirements in the active hosted PR stack.

## Update Rules

- Put new active PR entries above architecture and history sections.
- Move an entry to completed history immediately after merge or explicit implementation without a dedicated PR.
- Record the final GitHub PR URL and merge status.
- Update `Last reviewed` whenever active ordering, dependencies, status, or acceptance criteria change.
- Never describe a superseded UI plan as current architecture.
- Keep implementation, tests, contracts, and documentation in the same PR when they define one behavior.

## Completed PR History

These entries are historical and not active work. They are kept to preserve completed scope, PR links, and stable
backlog identifiers.

| ID | Title | Final status |
| --- | --- | --- |
| PR01 | Project Package And Quality Baseline | merged. PR: https://github.com/SergejSchweizer/portfell/pull/1 |
| PR02 | Shared Configuration, HTTP, And Contract Primitives | merged. PR: https://github.com/SergejSchweizer/portfell/pull/3 |
| PR03 | Simple Bronze/Silver/Gold Lake Layout Contract | merged. PR: https://github.com/SergejSchweizer/portfell/pull/3 |
| PR04 | Search Module: EODHD Query And Raw Candidate Capture | merged. PR: https://github.com/SergejSchweizer/portfell/pull/3 |
| PR05 | Search Module: Canonical ISIN Selection Contract | merged. PR: https://github.com/SergejSchweizer/portfell/pull/3 |
| PR06 | Search Module: Review Artifacts And Active Universe Pointer | merged. PR: https://github.com/SergejSchweizer/portfell/pull/3 |
| PR07 | Bronze Module: Input Contract Validation And Planning | merged. PR: https://github.com/SergejSchweizer/portfell/pull/3 |
| PR08 | Bronze Module: EOD Quote Download To Bronze | merged. PR: https://github.com/SergejSchweizer/portfell/pull/3 |
| PR09 | Silver Quote Build Baseline | merged. PR: https://github.com/SergejSchweizer/portfell/pull/3 |
| PR10 | Bronze Module: Identifier Mapping Capture | merged. PR: https://github.com/SergejSchweizer/portfell/pull/3 |
| PR11 | Bronze Module: Coverage, Errors, And Monthly Refresh Behavior | merged. PR: https://github.com/SergejSchweizer/portfell/pull/3 |
| PR12 | Gold Inputs: Returns, Correlation, And Covariance Baseline | merged. PR: https://github.com/SergejSchweizer/portfell/pull/3 |
| PR13 | Finalization: End-To-End Dry Run, Docs, And Release Checklist | merged. PR: https://github.com/SergejSchweizer/portfell/pull/3 |
| PR14 | Bronze Process: Cron-Safe Bronze Ingestion And Medallion Builds | merged. PR: https://github.com/SergejSchweizer/portfell/pull/13 |
| PR15 | Gold Evaluation Dataset Contracts And Paths | merged. PR: https://github.com/SergejSchweizer/portfell/pull/20 |
| PR16 | Evaluation Module: Return Matrix And Asset Metrics | merged. PR: https://github.com/SergejSchweizer/portfell/pull/21 |
| PR17 | Evaluation Module: Portfolio Returns And Drawdown Metrics | merged. PR: https://github.com/SergejSchweizer/portfell/pull/24 |
| PR18 | Portfolio Module: Core Optimization Objectives And Target Weights | merged. PR: https://github.com/SergejSchweizer/portfell/pull/26 |
| PR19 | Portfolio Module: Risk Parity And Equal Risk Contribution | merged. PR: https://github.com/SergejSchweizer/portfell/pull/32 |
| PR20 | Evaluation Module: Walk-Forward Backtesting | merged. PR: https://github.com/SergejSchweizer/portfell/pull/34 |
| PR21 | Evaluation Module: Rebalancing Simulation | merged. PR: https://github.com/SergejSchweizer/portfell/pull/34 |
| PR22 | Portfolio Module: Hierarchical Risk Parity | merged. PR: https://github.com/SergejSchweizer/portfell/pull/34 |
| PR23 | Portfolio Module: Maximum Diversification Objective | merged. PR: https://github.com/SergejSchweizer/portfell/pull/34 |
| PR24 | Evaluation Module: Efficient Frontier Generator | merged. PR: https://github.com/SergejSchweizer/portfell/pull/34 |
| PR25 | Portfolio Module: CVaR And Tail-Risk Optimization | merged. PR: https://github.com/SergejSchweizer/portfell/pull/34 |
| PR26 | Evaluation CLI And Dry-Run Integration | merged. PR: https://github.com/SergejSchweizer/portfell/pull/34 |
| PR27 | Gold Correlation Edge Dataset Baseline | merged. PR: https://github.com/SergejSchweizer/portfell/pull/28 |
| PR28 | Gold Spearman Correlation Edges | merged. PR: https://github.com/SergejSchweizer/portfell/pull/30 |
| PR29 | Gold Correlation Edges: Skip Same-ISIN Pairs | merged. PR: https://github.com/SergejSchweizer/portfell/pull/40 |
| PR30 | Gold Pair Statistics Boundary Refactor | merged. PR: https://github.com/SergejSchweizer/portfell/pull/44 |
| PR31 | Dataset Contract Registry Refactor | merged. PR: https://github.com/SergejSchweizer/portfell/pull/44 |
| PR32 | Evaluation And Portfolio Package Boundary Refactor | merged. PR: https://github.com/SergejSchweizer/portfell/pull/44 |
| PR33 | Unified Run State And Job Manifest Refactor | merged. PR: https://github.com/SergejSchweizer/portfell/pull/44 |
| PR34 | Production Optimizer Interface And Diagnostics Refactor | merged. PR: https://github.com/SergejSchweizer/portfell/pull/44 |
| PR35 | Enforce Real Evaluation And Portfolio Package Boundaries | merged. PR: https://github.com/SergejSchweizer/portfell/pull/46 |
| PR36 | Extract Scalable Gold Pair Statistics Engine | merged. PR: https://github.com/SergejSchweizer/portfell/pull/46 |
| PR37 | Type Critical Dataset Rows And Contract Validation | merged. PR: https://github.com/SergejSchweizer/portfell/pull/46 |
| PR38 | Split CLI Parsing From Workflow Execution | merged. PR: https://github.com/SergejSchweizer/portfell/pull/46 |
| PR39 | Add Import-Boundary And Scale-Guard Quality Gates | merged. PR: https://github.com/SergejSchweizer/portfell/pull/46 |
| PR40 | Three-Module Boundaries And Public Contract Skeleton | merged. PR: https://github.com/SergejSchweizer/portfell/pull/51 |
| PR41 | Refresh Catalog Contracts And Stable Instrument Identities | merged. PR: https://github.com/SergejSchweizer/portfell/pull/51 |
| PR42 | Selection Predicate And Metric-Requirement Contracts | merged. PR: https://github.com/SergejSchweizer/portfell/pull/51 |
| PR43 | Selection Identity, Candidate And Final Membership Contracts | merged. PR: https://github.com/SergejSchweizer/portfell/pull/51 |
| PR44 | Update Contracts, Pinned Inputs, And Shared Work Planner | merged. PR: https://github.com/SergejSchweizer/portfell/pull/51 |
| PR45 | Refresh Complete EODHD Catalog Synchronization | merged. PR: https://github.com/SergejSchweizer/portfell/pull/53 |
| PR46 | Refresh All-ISIN Market Data And Versioned Inputs | merged. PR: https://github.com/SergejSchweizer/portfell/pull/53 |
| PR47 | Refresh Service, Standalone CLI, And Atomic Publication | merged. PR: https://github.com/SergejSchweizer/portfell/pull/53 |
| PR48 | Selection Service, Current Pointer, And Standalone CLI | merged. PR: https://github.com/SergejSchweizer/portfell/pull/53 |
| PR49 | Update Incremental Per-ISIN Metric Cache | merged. PR: https://github.com/SergejSchweizer/portfell/pull/53 |
| PR50 | Update Screening Classifications And Selection Finalization | merged. PR: https://github.com/SergejSchweizer/portfell/pull/53 |
| PR51 | Update Selection Calendar And Comparable Metric Cache | merged. PR: https://github.com/SergejSchweizer/portfell/pull/53 |
| PR52 | Update Incremental Pair Metric Cache | merged. PR: https://github.com/SergejSchweizer/portfell/pull/53 |
| PR53 | Update Evaluation Profiles And Selection Analysis Manifests | merged. PR: https://github.com/SergejSchweizer/portfell/pull/53 |
| PR54 | Update Service, Standalone CLI, And Atomic Publication | merged. PR: https://github.com/SergejSchweizer/portfell/pull/53 |
| PR55 | Three-Module Cutover, Legacy Migration, And Documentation | merged. PR: https://github.com/SergejSchweizer/portfell/pull/53 |
| PR56 | Return Semantics And Data-Quality Gate | merged. PR: https://github.com/SergejSchweizer/portfell/pull/83 |
| PR57 | Instrument-Level Rebalancing Drift And Cost Basis | merged. PR: https://github.com/SergejSchweizer/portfell/pull/85 |
| PR58 | Risk Model Package And Covariance Diagnostics | merged. PR: https://github.com/SergejSchweizer/portfell/pull/89 |
| PR59 | Production Numerical Solver Boundary | addressed; no dedicated PR under this branch name |
| PR60 | Production Minimum Variance And Equal Risk Contribution | merged. PR: https://github.com/SergejSchweizer/portfell/pull/101 |
| PR61 | True HRP And Minimum CVaR Optimizers | merged. PR: https://github.com/SergejSchweizer/portfell/pull/104 and https://github.com/SergejSchweizer/portfell/pull/109 |
| PR62A | Jurisdiction-Neutral Tax, Cost, And Cash-Flow Contracts | merged. PR: https://github.com/SergejSchweizer/portfell/pull/112 |
| PR63 | Portfolio Profile Contracts And Balanced Ensemble Candidate | merged. PR: https://github.com/SergejSchweizer/portfell/pull/113 |
| PR64 | Walk-Forward Model Comparison Scorecard | merged. PR: https://github.com/SergejSchweizer/portfell/pull/114 |
| PR65 | Stress, Bootstrap, And Sensitivity Analysis | merged. PR: https://github.com/SergejSchweizer/portfell/pull/115 |
| PR66 | Explainable Recommendation Report | merged. PR: https://github.com/SergejSchweizer/portfell/pull/116 |
| PR69 | Multivariate Statistics Baseline Module And CLI | merged. PR: https://github.com/SergejSchweizer/portfell/pull/79 |
| PR70 | Multivariate Production Portfolio Adapter | merged. PR: https://github.com/SergejSchweizer/portfell/pull/117 |
| PR71 | Multivariate Income And Recommendation Outputs | merged. PR: https://github.com/SergejSchweizer/portfell/pull/118 |
| PR72 | Multivariate Trading And Monitoring Handoff | merged. PR: https://github.com/SergejSchweizer/portfell/pull/119 |
| PR73 | Generic Listing And Pair Statistics Cache | merged. PR: https://github.com/SergejSchweizer/portfell/pull/80 |
| PR74 | Selection Statistics Views | merged. PR: https://github.com/SergejSchweizer/portfell/pull/120 |
| PR75 | Multivariate Selection Cache Consumption | merged. PR: https://github.com/SergejSchweizer/portfell/pull/121 |

## Completed And Superseded Detailed Records

### Completed Hosted Stack Records

### PR92. Content-Addressed Univariate And Return Artifact Cache

Branch: `feat/content-addressed-univariate-cache`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/135.

Priority: P1 reusable analytical cache.

Depends on: PR91.

Scope: Replace hosted cache validity based only on listing, observation counts, and date bounds with exact input fingerprints. Create shared return and univariate artifact identities from listing, quote snapshot hash, dividend snapshot hash, date window, metric parameters, quality-policy version, and algorithm version. Store each artifact once and create user-visible analysis references only after verifying access to every input snapshot.

Acceptance: Tests cover identical inputs across users, different end dates, same row count with corrected historical values, changed dividend payload, changed confidence level, changed quality policy, corrupt artifact, and concurrent computation. Identical input hashes reuse one artifact; any material input change produces a distinct artifact.

Security: Cache discovery never grants access. Artifact reads require a user-owned run or authorized input proof; direct artifact ids and paths are insufficient.

Determinism: Artifact ids derive from canonical input and parameter hashes and produce stable row ordering.

Idempotency: Concurrent or repeated requests compute or publish one artifact and create separate user run references without rewriting valid shared content.

### PR93. Content-Addressed Bivariate Cache And Exact Alignment Identity

Branch: `feat/content-addressed-bivariate-cache`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/136.

Priority: P1 pair-statistics reuse without leakage.

Depends on: PR92.

Scope: Key pair artifacts by ordered input return-artifact ids, exact common-date alignment hash, metric parameters, minimum-observation policy, and algorithm version. Preserve unordered-pair canonicalization, same-ISIN rules, bucketed storage, sparse/top-k modes, and scale guards. Replace hosted cache checks based only on date range and observation count.

Acceptance: Tests cover identical pairs across users, reversed pair order, differing user date ranges, same common-date count with changed values, newly common dates, corrections, no-common-date cases, algorithm upgrades, bucket corruption, and concurrent requests. An artifact is reusable only when both input artifacts and exact alignment identity match.

Security: A user may reuse a pair artifact only when authorized for both underlying return inputs. Pair metadata must not reveal inaccessible listing histories through unauthenticated endpoints.

Determinism: Pair orientation, alignment rows, common-date hash, bucket assignment, and artifact id are independent of selection order and worker scheduling.

Idempotency: Repeated overlapping selections reuse existing pair artifacts and calculate only missing exact keys once.

### PR95. Docker Compose PostgreSQL, API, Web, And Shared Runtime Storage

Branch: `chore/docker-compose-postgres-hosted-runtime`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/140.

Priority: P1 reproducible hosted development environment.

Depends on: PR87 and PR91.

Scope: Add root Docker Compose configuration and Dockerfiles for PostgreSQL, FastAPI, and Next.js. Mount separate persistent PostgreSQL and shared-data volumes; keep PostgreSQL internal; expose only Web and development API ports; add health checks, startup ordering, migration execution, non-root containers, read-only filesystems where feasible, resource limits, and explicit development versus production overrides. Runtime secret source paths must be absolute host paths outside the repository and mounted as Docker secrets only into required services.

Acceptance: Compose validation and smoke tests prove database and shared data persist across restart, `docker compose down` does not erase named data without an explicit volume removal, Web cannot mount shared data or credential secrets, PostgreSQL is not externally published by default, and missing external secrets fail startup clearly.

Security: No real secret appears in Compose, `.env.example`, image layers, build arguments, command lines, logs, or CI artifacts. Production examples require TLS termination and protected host permissions.

Determinism: Service names, ports, volume contracts, image inputs, health checks, and configuration names are explicit and versioned.

Idempotency: Re-running Compose with unchanged source reuses persistent state and does not reset migrations, credentials, grants, snapshots, or artifacts.

### PR96. FastAPI User, Credential, Download, Dataset, Project, And Analysis API

Branch: `feat/hosted-fastapi-service`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/142.

Priority: P1 hosted application service.

Depends on: PR94 and PR95.

Scope: Add `apps/api` with authenticated routes for session status, credential set/status/delete, download plan/run/status, visible datasets, projects, selections, analyses, metrics, returns, weights, reports, and account deletion. Route all data access through repositories with RLS and entitlement services. Add request validation, bounded pagination, opaque public ids, structured errors, audit events, rate limits, and asynchronous-compatible run status while allowing initially small work to execute synchronously.

Acceptance: API tests cover authentication, CSRF, ownership, empty new-user state, credential lifecycle, successful and failed downloads, snapshot visibility, selection creation, analysis cache hit, cross-user ids, pagination, error redaction, account deletion, and restart persistence. No route accepts a storage path or shared artifact id as proof of access.

Security: Sensitive routes require recent authenticated sessions where appropriate. Responses never include provider ciphertext, nonce, wrapped data key, fingerprint, database ids, internal paths, or secret configuration.

Determinism: Public responses use stable opaque run and project identities plus deterministic analytical payload ordering.

Idempotency: Idempotency keys and logical request hashes prevent duplicate credential updates, download grants, projects, selections, or analysis submissions after retries.

### PR97. Google-Authenticated Web UI And User-Scoped Research Funnel

Branch: `feat/hosted-web-user-research-funnel`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/143.

Priority: P2 end-user workflow.

Depends on: PR96.

Scope: Add `apps/web` with Google login, dashboard, credential settings, data-download workflow, visible-data coverage, metadata filtering, univariate statistics/filtering, bivariate statistics, multivariate portfolio analysis, report views, and logout/account-deletion flows. The browser consumes API-produced data and performs no financial calculations or authorization decisions. The credential form accepts a new key but never redisplays the stored key.

Acceptance: UI tests cover first login with empty state, repeat login with persisted state, credential replacement and deletion, Free versus paid capability messaging, progress and partial failure, user-visible date coverage, no visibility of another user's newer data, statistics funnel navigation, cached analysis reuse, responsive layouts, accessibility, and API error handling.

Security: No EODHD key, Google token, session token, ciphertext, fingerprint, or sensitive response is stored in localStorage/sessionStorage, placed in URLs, sent to client analytics, or rendered into logs and error pages.

Determinism: UI state is derived from API contracts and stable route parameters; fixtures never call Google or EODHD.

Idempotency: Page refresh and navigation reload existing runs and snapshots without submitting new downloads or analyses.

### PR98. Public-Repository CI, Supply-Chain, Secret-Scanning, And Deployment Hardening

Branch: `chore/public-repo-security-hardening`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/145.

Priority: P0 before public deployment.

Depends on: PR95 and PR96.

Scope: Harden the public repository and CI: add secret scanners and custom EODHD patterns, pre-commit scanning, repository push-protection documentation, dependency and container scanning, SBOM generation, full-SHA pinning for GitHub Actions, least-privilege workflow permissions, fork-safe PR workflows without production secrets, protected deployment environments, dependency update policy, signed release guidance, and checks preventing secret-like files or runtime data from entering Git. Prohibit privileged `pull_request_target` execution of untrusted fork code.

Acceptance: Tests intentionally inject synthetic secret patterns and fail; fork PR simulation receives no protected secret; Actions are SHA-pinned; workflow permissions are explicit; container and dependency findings are reported; and `.gitignore` plus policy checks reject databases, Parquet runtime data, backups, `.env` files, and secret directories.

Security: GitHub Actions never receives user EODHD keys or the production KEK. NAS deployment uses trusted commits and runtime host secrets; any future cloud deployment uses short-lived OIDC credentials rather than long-lived deployment keys where supported.

Determinism: Security checks use pinned tool versions and committed policy configuration.

Idempotency: Re-running scans against unchanged source produces the same policy result apart from explicitly non-authoritative vulnerability-database timestamps.

### PR99. Licensing, Privacy, Retention, Backup, Restore, And Key-Rotation Gate

Branch: `docs/hosted-readiness-security-gate`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/146.

Priority: P0 public-hosting release gate.

Depends on: PR98.

Scope: Add machine-checkable hosted readiness records for EODHD storage, personal-license boundaries, shared physical deduplication, user-key-backed grants, derived-data display, redistribution, retention, account deletion, GDPR rights, audit retention, incident response, encrypted backups, restore drills, KEK recovery, KEK rotation, session-key rotation, database-role review, and no automatic broker execution. Public-hosted mode remains disabled unless every mandatory decision is approved.

Acceptance: The gate fails for missing or expired legal/security review, plaintext or co-located key backups, untested restore, unresolved provider display/redistribution rights, absent deletion procedure, unsupported country privacy requirements, or any endpoint capable of bypassing user entitlements. A documented local-only mode remains available while hosted readiness is blocked.

Security: Database/shared-store backups and KEK recovery material are encrypted and stored separately. Restore procedures fail closed when the correct KEK version is unavailable and never export decrypted provider keys.

Determinism: Readiness is computed from versioned decision and evidence records with explicit review dates and statuses.

Idempotency: Re-running the gate does not mutate production data, rotate keys, or alter readiness records.

### PR100. End-To-End Multi-User Isolation, Reproducibility, And Hosted Cutover

Branch: `feat/hosted-multitenant-cutover`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/147.

Priority: P0 final integration and release proof.

Depends on: PR97 and PR99.

Scope: Integrate Google identity, encrypted credentials, EODHD ingestion, shared observation storage, user snapshots, scoped selections, shared statistical caches, portfolio artifacts, API, Web, security gates, and recovery procedures. Add complete multi-user scenarios, migration tooling for existing local lake data as administrator-owned local artifacts without inventing user entitlements, operational runbooks, rollback, observability with redaction, and explicit feature flags for local-only versus hosted modes.

Acceptance: End-to-end tests create at least three users with overlapping and non-overlapping provider responses; prove exact date/revision visibility; prove physical market and statistics deduplication; prove uni/bi/multivariate calculations consume only each user's snapshot; prove identical authorized inputs reuse artifacts; reject every cross-user project, run, artifact, and snapshot attempt; survive restart; rotate KEK; restore encrypted backups; delete an account; and preserve local CLI behavior. The hosted feature flag cannot enable public mode unless PR99's gate is green.

Security: Add a final threat-model review, authorization matrix, penetration-test checklist, dependency review, secret scan, and incident-response verification. No production key is required or permitted in CI.

Determinism: Replaying identical user snapshots, selections, settings, and algorithm versions produces identical analytical artifact ids and values across restart and restore.

Idempotency: Retrying the complete workflow creates no duplicate users, credentials, observations, grants, snapshots, calculations, analyses, or reports.

### Superseded Research Funnel UI Stack

Historical only. The following plan is superseded by PR110 through PR115 and must not be implemented as active scope.

## Portfell Research Funnel UI PR Stack

PR97 remains the minimum functional hosted Web UI required by PR100. The following post-cutover series turns that baseline into the approved Portfell product interface: a simple Google- and Apple-inspired research workspace built around the persisted funnel `Data -> Metadata -> Univariate -> Filter -> Diversification -> Portfolio -> Validation -> Report`. These PRs must not move financial calculations or authorization decisions into the browser, weaken the PR99 readiness gate, or replace immutable project, snapshot, selection, and run identities with client-only state.

PR109, then PR102 through PR108 are a stacked UI branch tree. PR109 starts from the current local-login hardening branch, PR102 starts from PR109, and each following UI PR starts from the previous UI branch until the tree is explicitly landed. Do not merge any UI stack branch into `main` unless the maintainer explicitly requests that `main` merge. During UI stack development, run `docker compose --env-file .env.local up --build --watch web` from the active UI branch so every local UI change is visible in Docker; use `uv run portfell-compose-web-watch` when Compose watch is unavailable.

### PR101. Web Design System, Application Shell, And Visual Baseline

Branch: `feat/web-design-system-app-shell`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/152.

Priority: P1 UI foundation.

Depends on: PR100.

Scope: Replace the hosted Web placeholder and ad hoc styles with the production local Web application shell and a small versioned design system. Define typography, spacing, color, border, elevation, focus, motion, density, chart, table, badge, warning, empty-state, and loading-state tokens. Add the responsive sidebar, top bar, project context, snapshot indicator, persistent eight-step funnel navigation, page frame, error boundary, and route skeletons for dashboard, projects, data, metadata, univariate, filter, diversification, portfolio, validation, report, and settings. Use a restrained light-first visual language matching the approved mockup; avoid decorative gradients, neon effects, financial ticker clutter, and business logic inside visual components.

Acceptance: Component and source-contract tests cover desktop, tablet, and mobile shell contracts; funnel states for not-started, ready, running, complete, warning, failed, and stale; keyboard-visible focus; reduced-motion behavior; long project names; narrow viewports; loading and empty states; and consistent chart/table typography. Docker Compose serves the real Portfell shell rather than the prior placeholder.

Security: Fixtures contain only synthetic users, opaque ids, and synthetic financial values. Components never render secrets, internal paths, database ids, provider request details, or raw exception payloads. The Web container continues to mount no credential secret or shared-data volume.

Determinism: Design tokens, route definitions, formatter rules, icon mappings, funnel ordering, and screenshot fixtures are committed and versioned. Identical props produce stable accessible markup and chart-ready layout.

Idempotency: Reloading or revisiting a route reconstructs the same shell from server state without creating projects, selections, downloads, or analyses.

### PR109. Real Google OIDC Runtime Login And Account Identity Display

Branch: `feat/web-google-oidc-runtime-login`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/162.

Priority: P0 authenticated user boundary for the local and hosted Web UI.

Depends on: PR101 and PR #160 local login hardening.

Scope: Replace the local `local-dev-google` session stub as the default Web login path with a real Google OpenID Connect authorization-code flow. Wire `/auth/google/start` to create a PKCE, state, and nonce login request; redirect the browser to Google's account chooser; add `/auth/google/callback` to exchange the authorization code with Google, verify the ID token issuer, audience, signature, expiry, nonce, email verification, and optional hosted-domain rule; resolve the stable Google `sub` into the Portfell user identity; issue opaque HttpOnly session and CSRF cookies; and keep an explicit opt-in local-dev auth mode for offline Docker development. Surface the authenticated Google email or display name in lowercase under `Portfell Research` in every authenticated shell and mark local-dev sessions as `local-dev-google`.

Acceptance: Tests cover Google account chooser redirect construction, callback success, first login, repeat login with changed email and unchanged `sub`, invalid state, replayed state, invalid nonce, invalid issuer, invalid audience, expired ID token, unverified email, optional hosted-domain rejection, token-exchange failure, logout, session status, local-dev fallback disabled by default outside development, and the visible lowercase identity line. Docker documentation shows the required Google OAuth client id, secret-file path, redirect URI, and local-dev override. Browser tests or HTTP-level tests prove the dashboard is not shown before real Google callback completion when local-dev mode is disabled.

Security: Google client secret, session secret, tokens, authorization codes, ID tokens, refresh tokens, code verifier, nonce, state, and session cookies are never committed, logged, rendered, stored in browser storage, or included in URLs after callback completion. State and nonce are single-use and short-lived. Session cookies are HttpOnly, Secure outside local HTTP development, SameSite=Lax or stricter, path-scoped, and revocable. Local-dev auth is visibly labelled and cannot be confused with verified Google OIDC.

Determinism: OIDC request serialization, state hashing, nonce validation, user identity resolution from Google `sub`, session status response shape, identity display formatting, and local-dev gating are versioned and covered by deterministic fake Google providers in tests.

Idempotency: Repeating a valid login for the same Google `sub` updates permitted profile metadata without creating duplicate users. Retrying failed callbacks never creates users or sessions. Refreshing the authenticated page reuses the existing server-side session and does not create projects, selections, downloads, or analyses.

### PR102. Project Dashboard, First-Run Onboarding, And Persisted Funnel State

Branch: `feat/web-project-dashboard-funnel-state`.

Git status: not started. PR: TBD.

Priority: P1 usable product navigation.

Depends on: PR109.

Scope: Implement the project dashboard, recent-project table, continue-research action, data-status summary, portfolio-monitoring summary, warnings, account navigation, and first-run onboarding. Guide a new Google-authenticated user through EODHD credential setup, Free-versus-paid capability discovery, creation of a starter project, first permitted refresh, and entry into the research funnel. Persist and display the current project snapshot, universe version, candidate selection, analysis runs, completed steps, warnings, and stale downstream steps when an upstream snapshot or filter changes. The Free-key starter path must show a meaningful supported example without exposing pre-existing data the user has not refreshed with their own key.

Acceptance: End-to-end tests cover a new empty user, returning user, missing credential, invalid credential, Free key, paid key, interrupted onboarding, multiple projects, continue from each funnel step, stale downstream states after metadata or threshold changes, deleted credential, and account deletion. The dashboard uses real API state and never fabricates portfolio or data availability.

Security: Project and onboarding responses are resolved through the authenticated session and RLS. No project name, snapshot status, warning, or recent activity from another user can appear through guessed ids, browser cache, prefetching, or stale client state.

Determinism: Funnel status is derived from persisted project pointers, immutable snapshots, selections, run status, and explicit dependency rules. The same server state produces the same current step and stale-step markings.

Idempotency: Refreshing, returning after logout, or repeating the continue action reopens the existing project state and does not create duplicate projects, refreshes, selections, or analyses.

### PR103. Data Coverage Workspace And Metadata Universe Builder

Branch: `feat/web-data-metadata-universe-builder`.

Git status: not started. PR: TBD.

Priority: P1 first analytical funnel stages.

Depends on: PR102.

Scope: Implement the Data and Metadata stages. The Data workspace shows credential status, visible dataset coverage, per-dataset date ranges, listing counts, quality warnings, refresh planning, quota/capability messaging, run progress, partial failures, and resulting User Data Snapshot. The Metadata workspace adds server-backed search, faceted filters, sorting, bounded pagination or virtualization, column configuration, bulk selection, filter counts, eligibility warnings, and explicit creation of a versioned universe. Supported facets include instrument type, exchange, listing currency, domicile, distribution policy, history, coverage, and data-quality eligibility where available.

Acceptance: Tests cover empty data, thousands of listings, Free-key limits, refresh success and partial failure, corrected provider rows, a newer user snapshot, server pagination, stable sorting, combined facets, no-result filters, bulk selection across pages, data-quality exclusions, and creation/reopening of a universe version. The UI prominently shows `visible instruments -> eligible instruments` and the exact snapshot used.

Security: Queries operate only on the authenticated user's entitled snapshot. Search counts, facets, autocomplete, exports, and error messages must not disclose instruments, dates, revisions, or coverage visible only to another user.

Determinism: Canonical filter serialization, sort keys, pagination cursors, column formatters, and universe summaries are stable. The same snapshot and filter definition produce the same ordered eligible membership and selection identity.

Idempotency: Reapplying an unchanged filter to the same snapshot reuses the existing logical universe or returns the same identity; repeated refresh-page requests do not submit a provider call or duplicate membership rows.

### PR104. Univariate Research Workspace, Fund Detail, And Metric Filter

Branch: `feat/web-univariate-research-filter`.

Git status: not started. PR: TBD.

Priority: P1 core fund research workflow.

Depends on: PR103.

Scope: Implement separate Univariate Analysis and Univariate Filter stages. Provide overview, return, risk, income, drawdown, and data-quality metric groups; sortable and filterable metric tables; an income-versus-tail-risk scatterplot; fund detail drawer; total-return, price-return, drawdown, rolling-risk, and distribution-history charts; confidence and track-record warnings; metric definitions; and artifact/run provenance. Add a threshold workbench for minimum history, sustainable income, maximum drawdown, Expected Shortfall, distribution variability, NAV erosion, liquidity, and data-quality confidence. Show exclusion counts by reason, multiple reasons per fund, and an inspectable `why excluded` explanation before creating the versioned candidate set.

Acceptance: Tests cover unavailable metrics, short history, invalid-price quality failures, stable and unstable distributions, NAV erosion, multiple simultaneous exclusions, boundary values, changed thresholds, cached artifact reuse, stale results after an upstream universe change, chart keyboard summaries, table exports, and deep links that reopen the same user-owned run. The browser only renders API-produced values and never recalculates financial statistics.

Security: Metric and chart requests require access to the project, snapshot, universe, and user-owned run. Direct shared artifact ids, listing ids outside the snapshot, or stale project pointers cannot retrieve details or influence exclusion counts.

Determinism: Metric group order, units, precision, warning classification, threshold operators, exclusion-reason ordering, and chart series ordering are versioned. Identical snapshot, universe, parameters, and algorithm versions produce the same candidate membership and presentation values.

Idempotency: Reopening the stage or resubmitting identical thresholds returns the existing completed run and candidate selection without duplicate artifacts or analysis records.

### PR105. Diversification Clusters, Redundancy Review, And Pair Inspector

Branch: `feat/web-diversification-pair-analysis`.

Git status: not started. PR: TBD.

Priority: P1 bivariate decision workflow.

Depends on: PR104.

Scope: Implement the Diversification stage around decision-relevant pair analysis rather than a matrix-only dashboard. Add cluster summaries, cluster membership tables, correlation heatmap, top redundant pairs, diversification candidates, and a pair inspector with Pearson, Spearman, covariance, bidirectional beta, downside correlation, stress correlation, rolling correlation, common-observation count, common date range, return comparison, drawdown comparison, and data-quality warnings. Support top-k and threshold-backed API views so large candidate sets never require all pair rows in browser memory. Allow the user to mark preferred or excluded instruments within a cluster and persist the resulting pre-portfolio selection.

Acceptance: Tests cover reversed pair orientation, insufficient overlap, missing metrics, large sparse candidate sets, top-k pagination, heatmap ordering, cluster labels, changed pair artifacts after corrected values, redundant-fund review, preferred-instrument persistence, stale bivariate runs, and reopening the exact pair through a stable project route. The UI remains usable without materializing a dense matrix for the broad universe.

Security: Pair search, cluster counts, heatmap cells, and inspector details require authorization to both underlying return artifacts and the owning project run. Autocomplete and top-k results do not reveal inaccessible instruments or pair histories.

Determinism: Cluster order, within-cluster ordering, pair orientation, heatmap axes, correlation formatting, and redundancy ranking use committed stable rules and exact artifact identities.

Idempotency: Repeating the same pair query or cluster decision reuses existing artifacts and persisted selections; navigation does not schedule new pair computation unless the authorized inputs or parameters changed.

### PR106. Portfolio Model Comparison And Constraint Workbench

Branch: `feat/web-portfolio-model-constraint-workbench`.

Git status: not started. PR: TBD.

Priority: P1 multivariate portfolio decision workflow.

Depends on: PR105.

Scope: Implement the Portfolio stage with comparable model cards for Equal Weight, Inverse Volatility, shrinkage Minimum Variance, Equal Risk Contribution, True HRP, Maximum Diversification, Minimum CVaR, Income, and configured ensemble candidates. Add target-weight bars, risk contributions, concentration diagnostics, expected income, volatility, CVaR, drawdown, turnover, solver diagnostics, and model trade-offs. Add an understandable constraint workbench for instrument, issuer, asset-class, country, sector, currency, strategy, short-history, crypto, liquidity, income, volatility, drawdown, CVaR, turnover, and current-weight limits, with advanced risk-model and estimation settings separated from the default experience. Detect infeasible constraints and explain the conflicting limits without silently relaxing them.

Acceptance: Tests cover every supported model, unavailable models, solver failure, infeasible constraints, constraint boundary values, stable model comparison ordering, selected profile defaults, cached portfolio artifacts, current versus target weights, whole-share preparation inputs, changed settings producing a new run, and unchanged settings reusing the prior run. No model is labelled universally best; baselines remain visible.

Security: Every model and diagnostic response resolves through a user-owned project run and authorized dependency closure. Constraint payloads are validated server-side; the browser cannot request internal paths, override ownership, or use shared artifact ids as authorization.

Determinism: Model-card order, metric definitions, constraint serialization, units, precision, weight and risk-contribution ordering, and selected-candidate rules are versioned and independent of browser locale or worker completion order.

Idempotency: Repeated identical model comparisons return the existing run or join the active computation. Saving unchanged constraints does not create duplicate configurations, runs, weights, or reports.

### PR107. Validation, Report, And Flatex Trade-Preparation Workspace

Branch: `feat/web-validation-report-trade-preparation`.

Git status: not started. PR: TBD.

Priority: P1 final decision and handoff workflow.

Depends on: PR106.

Scope: Implement the Validation and Report stages. Add historical and walk-forward tabs, stress and bootstrap summaries, sensitivity views, costs and turnover, current-versus-target comparison, drawdown and recovery charts, risk-limit checks, model scorecards, assumptions, limitations, and an explicit Portfell assessment with passed checks and warnings. Render the explainable recommendation report and support authorized HTML/PDF download. Add Flatex-oriented trade preparation with current positions, target weights, estimated trades, whole-share rounding, minimum trade size, fees, taxes where configured, residual cash, and export; retain explicit user approval and no automatic broker execution.

Acceptance: Tests cover walk-forward availability, weak out-of-sample evidence, stress failures, cost-sensitive ranking changes, current-portfolio absence, whole-share rounding, insufficient cash, tax/cost adapter differences, report regeneration, authorized download, expired/stale run handling, export contents, and explicit no-order-execution language. Reports include selected and excluded instruments with reasons, target weights, risk contributions, income, drawdown, costs, stress results, assumptions, and warnings.

Security: Report and export downloads require a current authenticated user-owned run and use opaque download routes. Generated documents contain no provider key material, session token, internal path, database identity, hidden cross-user data, or unredacted exception details.

Determinism: Report sections, metric precision, chart ordering, trade-rounding rules, export columns, and file naming derive from versioned templates and exact immutable run inputs.

Idempotency: Repeated report or export generation for the same completed run reuses the existing authorized artifact or produces byte-stable content where timestamps are explicitly excluded; it never creates broker orders.

### PR108. Responsive Accessibility, Visual Regression, Performance, And UI Cutover

Branch: `feat/web-ui-production-cutover`.

Git status: not started. PR: TBD.

Priority: P0 final UI quality and deployment proof.

Depends on: PR107.

Scope: Complete the approved visual baseline across desktop, tablet, and mobile; add mobile-specific layouts rather than scaled desktop pages; finish keyboard navigation, semantic landmarks, accessible names, table and chart alternatives, contrast, focus management, reduced motion, and screen-reader announcements. Add visual-regression coverage, browser end-to-end tests for the full funnel, realistic large-table performance tests, API cancellation/retry behavior, route-level loading and error states, bundle and rendering budgets, supported-browser policy, and clean-host Docker Compose installation proof. Remove obsolete placeholder Web code and make the real Portfell UI the canonical hosted route.

Acceptance: A clean checkout with documented external synthetic secret files can run `docker compose up --build`, complete Google/EODHD-mocked end-to-end scenarios, and reach the responsive GUI. Tests cover new user, returning user, Free key, paid key, two isolated users, all funnel stages, upstream invalidation, cached reuse, restart persistence, mobile navigation, keyboard-only use, automated accessibility checks, visual baselines, large datasets, slow/failed API calls, report download, logout, and account deletion. Documented performance budgets pass on representative fixtures.

Security: Browser storage, URLs, client logs, screenshots, test traces, source maps, analytics, downloaded reports, and CI artifacts are scanned for provider keys, tokens, ciphertext, fingerprints, internal paths, and cross-user content. Production error pages remain redacted and authenticated data is not cached publicly.

Determinism: Visual baselines use pinned browsers, fonts supplied by standard image packages rather than committed proprietary font files, fixed viewport fixtures, stable synthetic data, fixed locale/time zone, and disabled nondeterministic animation. E2E routes resolve exact snapshots, selections, and runs.

Idempotency: Re-running the complete UI funnel against unchanged authorized inputs creates no duplicate projects, refreshes, selections, analyses, reports, or exports; restart and browser refresh resume persisted state.
