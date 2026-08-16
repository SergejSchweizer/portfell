# Plotly Dash Three-Page Research UI PR Stack

Status: planning contract for BACKLOG.md PR264-PR268.

This document is the detailed hand-off for a parallel Plotly Dash implementation of only Metadata Builder, Univariate Statistics, and Bivariate Statistics. It deliberately does not replace or delete the current React application. Until the entire PR264-PR268 series is merged and separately accepted for a later cutover, `apps/web` remains the production browser implementation.

## Fixed architecture and non-goals

The Dash implementation is a side-by-side research UI under `/dash/`. It reuses the existing Portfell FastAPI/application-service authority and existing project-scoped page-view, lazy-section, command, workflow, and run contracts. Dash is a presentation/orchestration adapter only: it must not read PostgreSQL directly, scan Parquet/shared-market files, call EODHD, recompute financial statistics, create a second durable job system, or introduce Celery/Redis/DiskCache as a second analysis queue.

The only production pages in this series are:

- `/dash/projects/<project_slug>/metadata-builder`
- `/dash/projects/<project_slug>/univariate-statistics`
- `/dash/projects/<project_slug>/bivariate-statistics`

Multivariate Statistics, portfolio execution, broker integration, React deletion, React route replacement, authentication redesign, financial formula changes, API schema changes, database migrations, and public-production cutover are explicitly out of scope.

Dash must use the FastAPI backend supported by Dash 4.2 or later and Dash Pages for page registration/routing. Plotly figures are generated from already-authorized API/application-service payloads. Large tabular result data uses existing revision-bound lazy-section contracts; if a grid is required, use Dash AG Grid rather than introducing a new table framework. Active long-running calculations continue to be started and persisted by existing Portfell commands/workers; the Dash app only submits the existing command and observes its existing run/progress state.

No custom browser JavaScript is allowed in PR264-PR268. CSS under the Dash app's assets directory is allowed. A later PR may add a narrowly justified clientside callback only if a measured interaction cannot meet its acceptance contract with standard Dash components.

## Parallel execution plan

Two weak agents execute the series in two waves after the foundation:

```text
PR264 foundation
      |
      +-----------------------+
      |                       |
      v                       v
PR265 shell/navigation   PR266 Metadata Builder
      |                       |
      +-----------+-----------+
                  |
          both merged to main
                  |
      +-----------+-----------+
      |                       |
      v                       v
PR267 Univariate       PR268 Bivariate
      |                       |
      +-----------+-----------+
                  |
          series complete
```

PR265 and PR266 branch from the same PR264 merge commit and may run concurrently. PR267 and PR268 branch from the same main commit after PR265 and PR266 merge and may run concurrently. No agent may stack an allegedly parallel PR on the other agent's branch.

For every PR below, the `Tasks / Acceptance` checklist is intentionally a single list. There is no separate task list and acceptance list: checking an item means both implementation and verification evidence exist in that PR.

## PR264 — Plotly Dash Runtime Foundation

Git metadata:

- Branch: `feat/dash-runtime-foundation`
- Base: `main`
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested PR title: `feat(dash): add three-page runtime foundation`
- Required single logical commit subject after squash: `feat(dash): add three-page runtime foundation`
- Merge method: squash merge only after `main` is rebased/merged into the branch and all required checks are green
- Parallel wave: foundation; both agents work inside this PR using the ownership split below
- Depends on: current hosted page-view/lazy-section/status contracts on `main`; no backlog PR dependency beyond already-merged contracts

Business outcome: create a runnable, testable Dash/FastAPI sidecar with frozen route/component/gateway boundaries so later page PRs can be implemented independently without changing the runtime contract.

Owned paths:

- Agent A only: `pyproject.toml`, `uv.lock`, `apps/dash/Dockerfile`, Dash service/profile additions in `compose.yaml`, `src/portfell/dash_ui/app.py`, `src/portfell/dash_ui/runtime.py`.
- Agent B only: `src/portfell/dash_ui/contracts.py`, `src/portfell/dash_ui/ids.py`, `src/portfell/dash_ui/testing.py`, `tests/dash_ui/test_contracts.py`, `tests/dash_ui/test_runtime.py`.
- Shared boundary: Agent B first freezes `contracts.py` and `ids.py`; after that commit Agent A may import but must not edit those two files. Agent B must not edit Agent A-owned runtime/dependency/deployment files.
- Forbidden in this PR: `apps/web/**`, financial calculation modules, hosted repository implementations, database migrations, EODHD/provider clients, Multivariate code.

Tasks / Acceptance — identical checklist:

- [ ] Add `dash[fastapi]>=4.2,<5` and `dash-ag-grid>=35,<36` as explicit runtime dependencies and use a Uvicorn installation with WebSocket capability; regenerate `uv.lock` once. `uv lock --check` and a clean `uv sync --frozen` succeed on Python 3.14. Do not add Flask, Celery, Redis, DiskCache, pandas, or a second HTTP framework as a direct Portfell dependency.
- [ ] Create importable package `portfell.dash_ui` and an ASGI entry point that starts Dash with a FastAPI backend, `use_pages=True`, `suppress_callback_exceptions=False`, title `Portfell · Dash Research UI`, and a fixed `/dash/` route prefix. Importing the package performs no database connection, provider call, project mutation, or calculation.
- [ ] Freeze exactly three page IDs in `ids.py`: `metadata_builder`, `univariate_statistics`, and `bivariate_statistics`. Freeze exactly three route suffixes: `/metadata-builder`, `/univariate-statistics`, `/bivariate-statistics`. No Multivariate page ID, placeholder, link, callback, route, or import is present anywhere under `portfell.dash_ui`.
- [ ] Define typed Dash-facing contracts in `contracts.py` for project summary/context, workflow stage status, page-view envelope, research run progress, lazy section revision/page, and typed command error. These are presentation contracts only and must map existing server fields without adding financial values or changing server/OpenAPI schemas.
- [ ] Define one `DashResearchGateway` protocol with explicit read/command methods needed by the three pages. The protocol must require project identity for every project-scoped read/command, must never accept a filesystem path or raw SQL, and must expose no provider client, PostgreSQL connection, repository, lake, or calculation object. Add an architecture test that fails if `portfell.dash_ui` imports `psycopg`, `portfell.table_io`, provider/EODHD modules, local lake paths, or hosted PostgreSQL repository implementations.
- [ ] Add deterministic fake gateway fixtures for: no current project, ready project, initial fill running, Univariate run running/complete/failed, Bivariate run running/complete/failed, stale section revision, unauthorized project, and empty result. Every fixture has fixed UUID-like IDs, fixed timestamps, fixed counts, and no real ISIN/provider credential.
- [ ] Add a Dash Docker image in `apps/dash/Dockerfile` that runs the ASGI entry point as an unprivileged process, has a health check, uses the repository lockfile, contains no Node runtime, and contains no secret in the image layers. `docker build --file apps/dash/Dockerfile --tag portfell-dash:pr264 .` succeeds.
- [ ] Add a Compose `dash` profile/service bound by default to `${PORTFELL_DASH_PORT:-8050}:8050`, depending on the healthy API but not on direct PostgreSQL access. The service receives only the minimum API/runtime configuration, mounts no shared-market data volume, receives no EODHD KEK/token secret, and joins only the network required to reach the API. `docker compose --profile dash config` proves these constraints.
- [ ] Add a deterministic `/dash/health` response returning HTTP 200 only after the Dash app is initialized; it contains no project, user, database, file, credential, or market-data information. Runtime tests cover successful startup, missing required API/runtime configuration, and health response.
- [ ] Required evidence is recorded in the PR description: `uv run pytest -q tests/dash_ui/test_contracts.py tests/dash_ui/test_runtime.py`, `uv run ruff check src/portfell/dash_ui tests/dash_ui`, `uv run pyright src/portfell/dash_ui`, `docker build --file apps/dash/Dockerfile --tag portfell-dash:pr264 .`, `docker compose --profile dash config`, and `uv run portfell-quality pr`. All pass from the same Git SHA.

Security: Dash is never an authorization authority. Project/user authorization remains in the existing hosted application boundary. The Dash container receives no provider credential and no direct PostgreSQL/shared-data access.

Determinism: frozen page IDs, route suffixes, component-ID namespace, typed gateway protocol, fixed fixture IDs, and lockfile determine the same runtime structure for the same Git SHA.

Idempotency: importing/startup/health checks do not mutate project state. Repeating identical read calls changes no server state. Existing command idempotency remains server-owned.

Rollback: remove `portfell.dash_ui`, `apps/dash`, the Compose profile/service, and Dash dependencies/lock changes. No database, API, analytical artifact, or React migration exists.

## PR265 — Dash Portfell Shell And Project Navigation

Git metadata:

- Branch: `feat/dash-research-shell`
- Base: the `main` commit containing merged PR264
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested PR title: `feat(dash): add research shell and project navigation`
- Required single logical commit subject after squash: `feat(dash): add research shell and project navigation`
- Merge method: squash merge only
- Parallel wave: wave 1, Agent A; may run concurrently with PR266
- Depends on: PR264 only

Business outcome: reproduce the current Portfell application shell for the three Dash research pages, including project selection, canonical project URL navigation, workflow locking/status, header, and responsive sidebar, without implementing page-specific financial content.

Owned paths:

- Agent A implementation: `src/portfell/dash_ui/shell.py`, `src/portfell/dash_ui/navigation.py`, `src/portfell/dash_ui/assets/portfell.css`, and shell-only additions to `app.py` if required by the PR264 hand-off.
- Agent B verification: `tests/dash_ui/test_shell.py`, `tests/dash_ui/test_navigation.py`, `docs/ui/dash-shell.md`.
- Shared boundary: PR264 IDs/routes/contracts are immutable. Agent B may not change production shell code; Agent A may not weaken or delete Agent B's fixture assertions after hand-off.
- Forbidden: page-specific calculation controls/figures, `apps/web/**`, API schema changes, Multivariate links, direct database/provider access.

Tasks / Acceptance — identical checklist:

- [ ] Render one shell with the current Portfell brand `Portfell` and subtitle `Portfolio Research Engine`, a header process overview, one project selector, one left workflow sidebar, and one page-content region. CSS reuses the current design values for canvas/surface/text/border/accent/status colors, 272 px desktop sidebar, 1240 px content maximum, and 10 px progress height; no external stylesheet or CDN is required.
- [ ] The sidebar contains exactly three workflow links in this order: Metadata Builder, Univariate Statistics, Bivariate Statistics. A locked stage renders non-navigable, `ready` is navigable, `running` displays running state, and `complete` displays complete state. There is no Multivariate link or hidden fourth Dash page.
- [ ] Canonical Dash project URLs are exactly `/dash/projects/<project_slug>/metadata-builder`, `/dash/projects/<project_slug>/univariate-statistics`, and `/dash/projects/<project_slug>/bivariate-statistics`. Project slug generation matches the existing React normalization semantics for ASCII letters/numbers and hyphen collapse; tests include `Xetra EUR`, accents, repeated spaces/punctuation, and empty-after-normalization fallback `project`.
- [ ] Loading the root `/dash/` with a current project redirects to that project's earliest navigable Dash page; with no current project it renders Metadata Builder in no-project state without creating or selecting a project. A GET/navigation render performs no write.
- [ ] Selecting another project executes exactly one existing `select current project` command, then reloads that project's workflow and navigates to Univariate Statistics when that stage is unlocked, otherwise Metadata Builder. Failure leaves the old project selected and renders one explicit error; it does not partially change URL/project state.
- [ ] The process overview shows only the available server-owned counts/statuses needed for Metadata download, Metadata Builder, Univariate Statistics, and Bivariate Statistics; missing values render an em dash and never render `0` as a substitute for unavailable data.
- [ ] Desktop width >=1024 px shows the fixed sidebar. Width 390 px uses a collapsed navigation control and a full-width page region; the menu can open/close with keyboard Enter/Escape and all links/select controls retain visible focus. No custom JavaScript file is introduced.
- [ ] Project navigation stores only project ID/slug and ephemeral selected-page state in Dash components; no credential, result rows, matrix payload, member list, or financial series is persisted to browser local/session storage.
- [ ] Tests prove two-project isolation with project A and project B having different workflow states/counts: switching to B cannot render A's count/status/link state after the URL changes. Unknown/deleted/unauthorized project slug produces one typed unavailable state and no fallback to another project's data.
- [ ] Required evidence: `uv run pytest -q tests/dash_ui/test_shell.py tests/dash_ui/test_navigation.py`, `uv run ruff check src/portfell/dash_ui tests/dash_ui`, `uv run pyright src/portfell/dash_ui`, `docker build --file apps/dash/Dockerfile --tag portfell-dash:pr265 .`, and `uv run portfell-quality pr` all pass from the same Git SHA.

Security: shell/project values only choose an already authorized project request; URL slug or Dash component state never grants access.

Determinism: canonical slug function plus project/workflow projection yields one URL and sidebar state; unavailable fields have one fixed representation.

Idempotency: route loads are read-only. Re-selecting the already-current project issues no command. Duplicate project-change callback delivery converges on one server-owned current-project state.

Rollback: revert shell/navigation/assets/tests/docs. PR264 runtime remains runnable with placeholder content; no server or persistent-state migration exists.

## PR266 — Dash Metadata Builder Page

Git metadata:

- Branch: `feat/dash-metadata-builder`
- Base: the same `main` commit containing merged PR264 used by PR265; do not branch from PR265
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested PR title: `feat(dash): add Metadata Builder page`
- Required single logical commit subject after squash: `feat(dash): add Metadata Builder page`
- Merge method: squash merge only
- Parallel wave: wave 1, Agent B; may run concurrently with PR265
- Depends on: PR264 only; final merge must be rebased on latest `main` after PR265 if PR265 lands first

Business outcome: reproduce current Metadata Builder user behavior in Dash while using existing metadata/project/bootstrap authority and without changing provider ingestion or project semantics.

Owned paths:

- Agent A visual/page ownership: `src/portfell/dash_ui/pages/metadata_builder.py`, metadata-specific CSS selectors only, `src/portfell/dash_ui/figures/metadata.py` only if a figure is actually needed.
- Agent B callback/data ownership: `src/portfell/dash_ui/callbacks/metadata_builder.py`, `src/portfell/dash_ui/view_models/metadata_builder.py`, `tests/dash_ui/test_metadata_builder.py`, `docs/ui/windows/dash-metadata-builder.md`.
- Shared boundary: component IDs are imported only from PR264 `ids.py`; neither agent edits that file. Callback signatures are frozen in a short fixture table in the test file before parallel coding.
- Forbidden: `apps/web/**`, financial-statistic modules, EODHD client code, database/storage code, Multivariate, API contract changes.

Tasks / Acceptance — identical checklist:

- [ ] Render exactly one `Download Metadata` panel containing, in order: metadata progress label/bar, status output, `Fetch all metadata` button, then the Metadata Builder form. Do not render a second standalone Metadata Builder panel.
- [ ] The form has exactly five criteria with the current semantics: Exchange dropdown, Instrument type dropdown, Country dropdown, Currency dropdown, and `Name contains` text input. Each dropdown includes `Any`; non-empty options show `<value> (<count> ISIN/ISINs)` using server-provided counts and deterministic sort order.
- [ ] `Fetch all metadata` invokes the existing metadata command once, disables itself while the returned run is active, renders persisted progress, and never receives or returns an EODHD key. Repeated callback delivery for the same click cannot create two logical metadata runs; server idempotency/error is surfaced rather than retried blindly.
- [ ] Project creation is disabled until metadata is ready and at least one Metadata Builder criterion is non-empty. Submit sends exactly the five form values through the existing project-creation command. Success displays `<N> unique ISINs selected`, changes current project to the returned project through existing server behavior, and navigates to its canonical Dash Metadata Builder URL.
- [ ] Initial-fill states map exactly: `not_started|planning` -> `Preparing historical data...`; `running` -> `Loading quotes: completed / total` plus deterministic remaining-time text when calculable; `ready` -> `Quotes ready - Create new project`; `partial` -> `Quotes partially loaded - Create new project`; `failed` -> `Quote load failed - Retry quote load`. Partial/failed status additionally shows failed ISIN count with singular/plural grammar.
- [ ] While initial fill is active, refresh only the persisted current project ID. A 15-second fallback interval is allowed for this Dash sidecar; it must not first reload project context and must not refresh another project's fill. Navigating away or switching project prevents an old callback result from updating the new page.
- [ ] Loading a saved project restores all five saved criteria, selected count, and initial-fill state from the existing Metadata Builder page-view contract. Unavailable initial-fill remains an explicit empty state rather than a failed request. No page render writes project criteria.
- [ ] Layout at >=1024 px preserves the four-column criteria row and name/action row; at 390 px controls stack vertically, buttons remain at least 40 px high, labels remain associated, and no horizontal page scroll is required.
- [ ] Deterministic tests cover metadata unavailable, metadata ready, zero matching ISINs, successful project creation, API validation error, running/ready/partial/failed initial fill, duplicate click, project switch during refresh, and exact 15-second fallback interval. No test contacts EODHD or requires PostgreSQL outside the existing fake gateway fixture.
- [ ] Required evidence: `uv run pytest -q tests/dash_ui/test_metadata_builder.py`, `uv run ruff check src/portfell/dash_ui tests/dash_ui`, `uv run pyright src/portfell/dash_ui`, `docker build --file apps/dash/Dockerfile --tag portfell-dash:pr266 .`, and `uv run portfell-quality pr` all pass from the same Git SHA.

Security: the page never asks for or stores a provider key. All commands remain project/user scoped by the existing server boundary.

Determinism: persisted page view plus ordered field options yields byte-equivalent visible labels/statuses for the same revision.

Idempotency: metadata fetch and project commands retain server-owned idempotency; render/progress refreshes are read-only and duplicate callback delivery cannot create an extra logical command.

Rollback: revert only Dash Metadata files/tests/docs. React, API, PostgreSQL, shared data, and project state remain unchanged.

## PR267 — Dash Univariate Statistics Page

Git metadata:

- Branch: `feat/dash-univariate-statistics`
- Base: `main` after both PR265 and PR266 are merged
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested PR title: `feat(dash): add Univariate Statistics page`
- Required single logical commit subject after squash: `feat(dash): add Univariate Statistics page`
- Merge method: squash merge only
- Parallel wave: wave 2, Agent A; may run concurrently with PR268
- Depends on: PR264, PR265, PR266

Business outcome: reproduce the current Univariate computation, result inspection, Plotly histogram, and persisted portfolio-filter controls without performing financial calculations in Dash.

Owned paths:

- Agent A visual/figure ownership: `src/portfell/dash_ui/pages/univariate_statistics.py`, `src/portfell/dash_ui/figures/univariate.py`, Univariate-specific CSS only.
- Agent B state/callback ownership: `src/portfell/dash_ui/callbacks/univariate_statistics.py`, `src/portfell/dash_ui/view_models/univariate_statistics.py`, `tests/dash_ui/test_univariate_statistics.py`, `docs/ui/windows/dash-univariate-statistics.md`.
- Shared boundary: one frozen `UnivariateMetricSpec` table in the view-model defines all tab IDs, labels, descriptions, equations, notation, units, and server field names. Agent A consumes it; only Agent B may edit it during this PR.
- Forbidden: any calculation of returns, volatility, VaR, Expected Shortfall, Sharpe, Sortino, drawdown, trend regression, dividends, or selection membership outside formatting/filter-selection logic; `apps/web/**`; API/server schema changes; Bivariate/Multivariate implementation.

Tasks / Acceptance — identical checklist:

- [ ] Render compute action, 10 px progress bar, status text, statistic-tab strip, result/facts region, Plotly distribution figure, and portfolio-selection controls immediately on route entry, using existing unavailable/empty messaging before results exist.
- [ ] Provide exactly ten tabs in this order: `Dividends`, `Duration`, `Annual Return`, `Value at Risk`, `Sortino ratio`, `Expected shortfall`, `Tail observations`, `Sharpe ratio`, `Maximum drawdown`, `Trend R-squared`. Each non-dividend tab displays the current description/equation/notation/unit from one frozen metric table; no alternative formula is introduced.
- [ ] Starting computation invokes exactly one existing Univariate start command for the current project's persisted metadata selection. While active, the button is disabled and progress is `min(total, completed + failed) / total`; terminal `failed` renders the typed failure and terminal `complete` loads the revision-bound result section. Dash does not start a worker/background callback or calculate statistics itself.
- [ ] Restore uses the existing compact Univariate page-view first. Result pages are not requested until a complete run exists and the results region requires them. Pagination consumes the existing `{revision, items, total, limit, next_cursor}` contract and stops exactly when `next_cursor` is absent; stale cursor/revision errors clear only the obsolete result cache and reload the current page view.
- [ ] `Dividends` renders the six current frequency choices: None / unknown, Monthly, Quarterly, Semi-annual, Annual, Irregular. The choice maps only to persisted `distribution_frequency`; no frequency is inferred client-side from dates.
- [ ] Duration exposes exactly these strict thresholds using quote observations: >1 month=22, >2 months=43, >3 months=64, >6 months=127, >12 months=253, >2 years=505, >3 years=757, >5 years=1261, >10 years=2521. Tests assert labels and numeric thresholds byte-for-byte.
- [ ] The nine statistic tabs build Plotly histograms from existing server result values only. Figure builders may select/format values and histogram bins but may not derive an alternative financial statistic. Hover shows code/ISIN and the persisted metric value; missing values remain unavailable and are not converted to zero.
- [ ] Portfolio filter settings round-trip the existing `dividend_frequencies`, `statistic_labels`, and `statistic_ranges` contract. Changes are coalesced with a 250 ms last-value-wins debounce equivalent: ten changes inside one 250 ms window produce one final save. A failed save leaves the prior persisted server selection authoritative and displays one error.
- [ ] Changing project while a run/results/settings request is in flight prevents every old project result from painting or saving into the new project. Tests use two projects with disjoint metric values and assert zero cross-project visible rows after switch.
- [ ] Required evidence: `uv run pytest -q tests/dash_ui/test_univariate_statistics.py`, `uv run ruff check src/portfell/dash_ui tests/dash_ui`, `uv run pyright src/portfell/dash_ui`, `docker build --file apps/dash/Dockerfile --tag portfell-dash:pr267 .`, and `uv run portfell-quality pr` all pass from the same Git SHA.

Security: only authorized project page-view/result/settings contracts enter the page. Component IDs, URL slug, and selection controls never authorize result access.

Determinism: one page-view revision, result revision, frozen metric table, stable server order, and fixed formatting rules produce the same tabs, labels, figures, and saved settings.

Idempotency: reads/figure construction are non-mutating. Duplicate compute/save callback delivery converges through existing command idempotency and 250 ms last-value-wins settings behavior.

Rollback: remove the Dash Univariate page/callback/figure/tests/docs only. Existing server runs/settings and React behavior remain intact.

## PR268 — Dash Bivariate Statistics Page And Three-Page Parity Gate

Git metadata:

- Branch: `feat/dash-bivariate-statistics`
- Base: the same `main` commit after PR265 and PR266 used by PR267; do not branch from PR267
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested PR title: `feat(dash): add Bivariate Statistics page and parity gate`
- Required single logical commit subject after squash: `feat(dash): add Bivariate Statistics page and parity gate`
- Merge method: squash merge only
- Parallel wave: wave 2, Agent B; may run concurrently with PR267; rebase on latest `main` before final parity evidence if PR267 merges first
- Depends on: PR264, PR265, PR266; final parity gate additionally requires merged PR267

Business outcome: reproduce all current Bivariate result views with native Plotly visualizations and prove that the side-by-side Dash app supports the complete three-page research journey without changing React or analytical semantics.

Owned paths:

- Agent A visual/figure ownership: `src/portfell/dash_ui/pages/bivariate_statistics.py`, `src/portfell/dash_ui/figures/bivariate.py`, Bivariate-specific CSS only.
- Agent B state/callback/integration ownership: `src/portfell/dash_ui/callbacks/bivariate_statistics.py`, `src/portfell/dash_ui/view_models/bivariate_statistics.py`, `tests/dash_ui/test_bivariate_statistics.py`, `tests/dash_ui/test_three_page_journey.py`, `docs/ui/windows/dash-bivariate-statistics.md`, `docs/ui/dash-three-page-parity.md`.
- Shared boundary: the nine tab IDs and lazy-section names are frozen in the Bivariate view-model before parallel coding. Agent A consumes them; only Agent B edits that mapping.
- Forbidden: pairwise formula changes, pair membership changes, covariance/risk-model changes, 2 MiB server limit changes, `apps/web/**`, Multivariate UI, API schema changes, direct database/shared-data access.

Tasks / Acceptance — identical checklist:

- [ ] Render compute action, 10 px progress bar, status text, Bivariate facts/distribution region, and exactly nine result tabs in this order: Covariance, Pearson, Spearman, Downside, Tail Dependence, Co-exceedance, Rolling-Correlation, Drawdown Overlap, Tail-Risk Scatter. No tab may silently substitute another metric.
- [ ] Starting computation invokes exactly one existing Bivariate start command using the persisted Univariate selection. Locked/missing Univariate selection disables the action with an explicit reason. Active progress uses existing run totals/completed/failed; Dash creates no background job/queue and performs no pairwise calculation.
- [ ] Initial page entry uses the compact Bivariate page-view. Hidden matrix/scatter sections issue zero lazy-section reads. Selecting a matrix/scatter tab loads exactly that revision-bound section once; switching back to an already loaded unchanged revision reuses it. Project/run/revision change invalidates only sections belonging to the obsolete identity.
- [ ] Covariance, Pearson, Spearman, Downside, Tail Dependence, Co-exceedance, Rolling-Correlation, and Drawdown Overlap render as `plotly.graph_objects.Heatmap` figures with server labels/order and persisted values. Hover shows row label/ISIN, column label/ISIN, metric name, and persisted value. Missing/self/omitted values remain empty rather than zero.
- [ ] Tail-Risk Scatter renders all server-returned indexed points using `Scattergl` (or an equivalently WebGL-backed Plotly trace) with Tail Dependence on x and Co-exceedance Rate on y, median divider lines, and the current three semantic groups: best diversifiers, mixed tail profile, tail-risk concentration. Hover resolves label indices through the same authorized scatter payload and shows both codes/ISINs plus the two persisted percentages.
- [ ] Bivariate metric facts preserve server-provided pair coverage (`date_start`, `date_end`), pair count, mean, median, range, and variable shared-observation min/max/average. The UI uses the label `Pair coverage` and never claims one common observation count when min and max differ.
- [ ] For the current large-universe fixture representing 201 listings/20,100 pairs, each selected matrix remains within the existing lazy-section contract and the compact scatter renders all 20,100 points without truncation. Figure construction completes within 2 seconds in the deterministic Python fixture and does not copy the full payload into browser local/session storage.
- [ ] Stale section revision, `section_not_available`, `section_too_large`, failed run, empty pair universe, and unauthorized project each render distinct explicit states. None trigger a recomputation, direct artifact read, fallback to another project, or alternative metric.
- [ ] The final three-page journey starts with deterministic metadata, creates/selects one project, restores Metadata Builder, completes/restores Univariate, applies at least one dividend-frequency and one numeric filter, completes/restores Bivariate, opens all nine Bivariate tabs, switches to a second project, then returns to the first. It asserts the canonical `/dash/projects/<slug>/...` URLs, no Multivariate route/link, no cross-project flash, no EODHD network call, and no direct PostgreSQL/shared-file access from the Dash container.
- [ ] Required final evidence after rebasing on a `main` that contains PR267: `uv run pytest -q tests/dash_ui`, `uv run ruff check src/portfell/dash_ui tests/dash_ui`, `uv run pyright src/portfell/dash_ui`, `docker build --file apps/dash/Dockerfile --tag portfell-dash:pr268 .`, `docker compose --profile dash config`, a container health smoke at `/dash/health`, and `uv run portfell-quality pr`. The PR description records the exact Git SHA and all command results.

Security: Bivariate lazy-section identities are never authorization. Existing project/run ownership is resolved before any payload reaches Dash; the Dash service receives no database/provider/shared-store credentials.

Determinism: server-provided label/pair order, immutable section revision, fixed tab mapping, fixed Plotly figure builders, and fixed formatting yield the same figures for the same payload.

Idempotency: page and lazy-section reads are non-mutating; repeated tab selection reuses the same revision; duplicate start delivery relies on the existing idempotent Bivariate command and cannot create a second logical run.

Rollback: revert Bivariate/three-page parity files. PR264-PR267 may remain deployed as an incomplete opt-in Dash sidecar; React remains the production UI throughout this series, so rollback requires no route, database, artifact, or user-state migration.

## Series completion gate

PR264-PR268 are complete only when all five backlog items are merged and one clean `main` run proves all of the following:

- the Dash application exposes exactly Metadata Builder, Univariate Statistics, and Bivariate Statistics under `/dash/projects/<project_slug>/...` and no Multivariate page/link;
- the current React app is unchanged by the series and remains independently runnable;
- Dash uses existing Portfell authority/contracts and cannot directly import/use provider clients, PostgreSQL repositories, lake/table I/O, or financial calculation modules;
- metadata/project/bootstrap, Univariate run/settings/results, and Bivariate run/lazy-section behaviors survive reload and project switching with no cross-project state;
- all statistical values shown by Dash are server-provided values; Plotly transforms them into figures but does not define alternative financial calculations;
- one deterministic large Bivariate fixture renders every current metric and the full 20,100-point scatter without truncation;
- `uv run pytest -q tests/dash_ui`, Ruff, Pyright, Dash Docker build, Compose profile validation, health smoke, and `uv run portfell-quality pr` pass from one Git SHA;
- no public-production cutover is implied. Replacing `apps/web`, changing canonical non-`/dash` routes, or deleting React requires a new separately approved backlog series with explicit migration and rollback criteria.
