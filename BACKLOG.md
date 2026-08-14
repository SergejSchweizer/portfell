Last reviewed: 2026-08-14

## Table Of Contents

- [Backlog Policy](#backlog-policy)
- [Parallel Weak-Agent PR Design](#parallel-weak-agent-pr-design)
- [Monthly-Distribution ETF Multivariate Architecture Record](#monthly-distribution-etf-multivariate-architecture-record)
- [Shared Market Data And Nightly Refresh Architecture Record](#shared-market-data-and-nightly-refresh-architecture-record)
- [Active Hosted Simplicity And Interactive Performance PR Stack](#active-hosted-simplicity-and-interactive-performance-pr-stack)
- [Current Architectural Decision](#current-architectural-decision)
- [Series Completion Gate](#series-completion-gate)
- [Update Rules](#update-rules)
- [Completed PR History](#completed-pr-history)

## Backlog Policy

This file is ordered by execution relevance:

1. active, not-yet-finished PR-sized work;
2. current architectural constraints and completion gates;
3. completed and superseded history at the bottom.

Every active item must contain `Branch`, `Git status`, `PR`, `Priority`, `Depends on`, `Scope`, `Acceptance`, `Security`, `Determinism`, and `Idempotency`. A PR is atomic only when it can merge independently with all repository gates green. A PR is complete only when its acceptance criteria are machine-verifiable and no assigned scope is deferred silently.

Completed entries are never deleted. Superseded plans are moved to the historical section and explicitly marked non-active. Backlog identifiers are never reused.

## Parallel Weak-Agent PR Design

Every new backlog PR must be designed so that two independent agents can implement and review it in
parallel. Assume either agent may have limited reasoning ability, incomplete conversation context, and
no ability to infer unstated product or architectural decisions. The PR definition is therefore the
complete executable work order, not a short reminder.

Each PR must state:

- one atomic business outcome and explicit non-goals;
- stable ownership boundaries: exact modules, routes, schemas, contracts, fixtures, and documents each
  parallel agent may change, plus files or abstractions that are shared and must be coordinated first;
- ordered dependencies and concrete hand-off artifacts, including versioned schemas, typed interfaces,
  fixture names, command examples, or committed contract snapshots;
- an implementation sequence that permits independent work without duplicate migrations, conflicting
  public contracts, or incompatible placeholder abstractions;
- a complete acceptance list with observable inputs, expected outputs, error behavior, authorization,
  persistence, restart, determinism, idempotency, performance limits, and exact tests/gates required;
- explicit evidence commands for completion and a rollback or migration note whenever persistent state,
  APIs, or deployment behavior changes.

Acceptance criteria must be precise enough that one weak agent can implement the item and a second
weak agent can verify it solely from the checked-in definition. Vague terms such as “fast”, “robust”,
“update all callers”, or “test thoroughly” are prohibited unless accompanied by measurable limits,
named callers, and exact test assertions. If two agents cannot work safely in parallel, split the item
into smaller sequential PRs and record the dependency and hand-off in this file before implementation.

## Monthly-Distribution ETF Multivariate Architecture Record

This is the canonical first implementation series for the Multivariate Statistics module. Its
initial product profile is a project-scoped universe of ETFs whose persisted Univariate
Statistics selection classifies them as monthly distributing. The module explains the selected
ETFs as one joint risk system, constructs comparable portfolio candidates, and validates those
candidates. Monthly distribution frequency is an eligibility condition, not evidence that an ETF
has a high, stable, sustainable, or tax-efficient income stream.

The active browser workflow remains the existing three-module workflow until PR150 completes the
cutover. PR143 through PR149 add dormant contracts, artifacts, calculations, and API capabilities
without adding an incomplete page or navigation item. PR150 atomically changes the production
workflow to:

```text
metadata_builder
    -> univariate_statistics
    -> bivariate_statistics
    -> multivariate_statistics
```

Every PR in this series must consume immutable project-scoped upstream identifiers. No PR may use
a global `current_selection` pointer as analysis authority, start an upstream calculation as a
side effect, recalculate financial values in React, label a gross historical distribution metric
as sustainable or net income, or expose a portfolio as investment advice.

### Monthly-Distribution ETF Multivariate Series Completion Gate

This series is complete only after PR143 through PR150 are merged in dependency order and every
current pre-merge and post-merge requirement in [GATES.md](GATES.md) passes. Completion additionally
requires all of the following evidence in one clean-main validation:

- a project-scoped monthly-distribution ETF input snapshot with exact authorized dependency closure;
- one canonical validated risk-model covariance used by every covariance-dependent output;
- deterministic structure, PCA, effective-rank, clustering, gross-income, candidate, risk-
  contribution, walk-forward, cost, stress, and scorecard artifacts;
- no global-current-pointer authority, upstream compute side effect, silent optimizer/risk-model
  substitution, unavailable-as-zero behavior, or production use of toy walk-forward defaults;
- persisted restart-safe project state, exact backend/frontend contracts, two-project isolation,
  content-addressed reuse, stale invalidation, and resumable idempotent execution;
- exactly four production modules with the Multivariate page consuming only API-produced values;
- explicit gross/historical and unavailable labels wherever sustainable income, genuine NAV,
  jurisdiction tax, or broker-cost evidence is missing;
- focused numerical fixtures, invariant/property tests, Vitest, two-project Playwright coverage,
  at least 95 percent aggregate coverage, production frontend build, and rebuilt Docker Web image;
- synchronized `README.md`, `ARCHITECTURE.md`, module/page documentation, schemas, API contracts,
  backlog status, and operational runbooks.

## Shared Market Data And Nightly Refresh Architecture Record

This series replaces project-triggered historical-data downloads with one nightly refresh for the
union of listings currently used by all persisted projects in the trusted local Portfell deployment.
All projects then read quotes, dividends, and splits from one shared physical store. Project state
contains selections, immutable input references, and analysis results, but no copied market rows.

Physical deduplication uses the full listing identity `(provider, exchange, code, isin)` because two
exchange listings of the same ISIN can have different currencies, trading calendars, and prices.
The same full listing used by any number of projects is planned, requested, and stored once. The
initial scheduled mode supports the existing single local principal and its encrypted EODHD
credential. It must fail closed rather than silently broadening this model if multiple credential
owners are introduced later.

PR151 through PR155 are sequential. PR151 starts after PR150 to avoid changing shared workflow and
UI contracts underneath the active Multivariate stack. PR155 may be deployed only after PR154's
one-time initial refresh and operational verification succeed in the target environment.

### Shared Market Data And Nightly Refresh Series Completion Gate

This series is complete only after PR151 through PR155 merge in dependency order, all current gates
in [GATES.md](GATES.md) pass, and one target-environment evidence bundle proves:

- one canonical physical market store with unique business keys and atomic correction handling;
- a deduplicated union of all active project listings and request/storage work proportional to unique
  listings rather than project count;
- successful initial backfill, restart, nightly one-shot execution, idempotent repeat, monitored cron
  installation, lock handling, and documented recovery;
- immutable project analysis snapshots, exact selection filtering, no project market-row copies, and
  no cross-project data exposure;
- all project analyses source quotes, dividends, and splits from shared storage;
- no browser manual historical-data action and no legacy mutation capable of provider ingestion;
- synchronized contracts, OpenAPI snapshot, architecture, README, UI docs, runbooks, backlog status,
  and full Python/TypeScript/Playwright/Docker validation.

## Active Hosted Simplicity And Interactive Performance PR Stack

This series makes the hosted application simpler and keeps interactive reads responsive while
ingestion or analysis workers are active. The target has one browser query cache, one FastAPI
application boundary, one PostgreSQL tenant/control-plane read model, and worker-owned Parquet and
analytical payload access:

```text
React + TanStack Query
          |
          v
FastAPI page-view and command routes
          |
          v
PostgreSQL tenant state + UI read projections
          ^
          |
durable workers -> shared Parquet and content-addressed artifacts
```

PR246 through PR252 are sequential. They optimize the active PostgreSQL authority only and do not
replace React, FastAPI, PostgreSQL, Polars, or Parquet. Local CLI analysis remains supported, but no
local repository, workspace JSON, in-memory dictionary, or shared-file scan may become a fallback
authority for a hosted request. Every latency assertion must use a checked-in deterministic fixture
and report request count, response bytes, database statement count, shared-file reads, and elapsed
time; wall-clock thresholds alone are insufficient evidence.

### PR247. PostgreSQL Navigation Read Model

Branch: `feat/hosted-navigation-read-model`.

Git status: in progress; split into mergeable implementation steps.

PR247a (navigation foundation): https://github.com/SergejSchweizer/portfell/pull/401 — schema,
bounded reader/writer, conditional GET, project-command writes, Metadata Builder hand-off, and
side-effect-free absent-current-project handling. PR247b will add worker/research reconciliation,
projection-backed workflow reads, a deterministic repair command, and the performance evidence below.

Priority: P0 page-entry latency and architectural simplicity.

Depends on: PR246.

Scope:

- Add versioned PostgreSQL projections for published metadata summary and project navigation state.
  The projection contains only metadata revision/count/freshness, project identity/name, current
  selection identity and unique-ISIN count, initial-fill status/progress, active analytical stage,
  current run references, and a monotonically increasing projection revision.
- Update projections transactionally from the existing project, selection, durable-job, metadata-
  publication, and research-run command paths. Define a deterministic idempotent reconciliation
  command for deployment, repair, and tests; it must never read tenant membership across RLS scopes.
- Rewrite `/project-context`, `/workflow`, and `/projects/{project_id}/workflow` as side-effect-free,
  bounded PostgreSQL projection reads. Remove Parquet materialization, selection-member scans,
  per-project repository lookups, analytical selection writes, and current-project mutation from GET
  execution. An absent current-project preference is returned explicitly and set only by a command.
- Return projection revision and `ETag`; honor `If-None-Match` with `304` and no response body. Cache
  directives must remain private and revalidation-based because responses are tenant scoped.
- Instrument these routes with statement count, shared-file read count, response size, and elapsed
  time. Add an architecture test that fails if a navigation reader imports table I/O, shared-store,
  analytical calculation, or command-side repository modules.

Out of scope: Returning analytical payload rows, changing project membership, replacing PostgreSQL,
or introducing a general event-sourcing framework.

Acceptance:

- Navigation responses remain contract-equivalent for no-project, selected, filling, ready, running,
  failed, stale, and completed fixtures, with the new revision and ETag fields explicitly versioned.
- Each route uses a constant bounded number of PostgreSQL statements independent of project count,
  uses at most three statements including transaction-local RLS binding, performs zero shared-file/
  Parquet reads and zero writes, and does not construct or persist an analytical selection while
  serving GET.
- A 100-project/25,000-member deterministic fixture satisfies the documented response-size,
  statement-count, and latency budgets both idle and during PR246's worker contention scenario:
  uncompressed JSON stays below 256 KiB, idle p95 stays below 250 ms, and loaded p95 stays below 1 s.
- Every relevant command updates the projection in the same successful transaction; forced rollback
  leaves both source state and projection unchanged. Reconciliation produces byte-equivalent rows.
- RLS, guessed-project, deleted-project, stale-projection, ETag, restart, migration, rollback, focused
  API, and real-stack regression tests pass with the applicable gates in `GATES.md`.

Security: Projection tables use forced RLS and contain no credentials, storage locations, unrestricted
membership, or cross-project analytical payloads. Authorization starts from authenticated user and
owned project on every read.

Determinism: Source record identities plus a versioned projection schema produce one canonical row and
ETag; reconciliation order cannot change serialized output.

Idempotency: Reapplying an event or reconciliation updates the same projection revision only when its
canonical content changes and never duplicates project or workflow rows.

### PR248. Page View Contracts And Lazy Analytical Sections

Branch: `feat/hosted-page-view-contracts`.

Git status: not started.

PR: TBD.

Priority: P1 request fan-out and payload control.

Depends on: PR247.

Scope:

- Define one versioned initial view contract for each Metadata Builder, Univariate, Bivariate, and
  Multivariate page. Each contract includes navigation revision, authorized run identity/status,
  section availability, compact summary values, pagination cursors, and immutable section revision
  IDs; it does not embed every large table or matrix.
- Add project-scoped FastAPI view routes that authorize once and assemble each initial contract from
  PostgreSQL projections plus persisted artifact manifests. Replace the browser's independent initial
  workflow, run, summary, plan, and first-result requests with one route per page.
- Keep large Univariate result pages, pair tables, covariance/correlation matrices, components,
  candidate details, validation series, and performance series behind explicit section endpoints.
  Load a section only when its visible tab/panel requires it; cancel obsolete requests after project,
  run, metric, tab, or route changes.
- Add stable cursor pagination and response-size limits. Do not create one unbounded `full-data`
  endpoint, GraphQL layer, browser-side join, or server-side financial recomputation during GET.
  Initial page views are limited to 256 KiB uncompressed; lazy sections are limited to 2 MiB and
  tabular pages to 200 rows. Contracts return `413 section_too_large` with section metadata when an
  intrinsically indivisible matrix exceeds the limit.
- Synchronize typed Python responses, generated/open API snapshots, TypeScript contracts, route/page
  specifications, fixtures, and interaction tests in the same PR.

Out of scope: Visual redesign, changing analytical values, replacing REST, or moving artifact payloads
into PostgreSQL.

Acceptance:

- Initial entry to each workflow page requires at most one page-view request after an already cached
  project shell; a cold shell plus page requires at most two application-data requests before first
  useful content. Playwright asserts exact request paths and upper bounds.
- Bivariate initial entry no longer issues the current 11-request matrix fan-out. Non-visible matrices
  and Multivariate detail sections issue zero requests until selected, then exactly one request per
  immutable section revision.
- Every response stays below its documented compressed and uncompressed byte budget; oversized tables
  use stable pagination and oversized matrices fail with a typed availability/limit contract rather
  than truncation.
- Two-project authorization, stale run replacement, rapid navigation cancellation, partial section
  failure, empty state, loading state, retry, browser back/forward, desktop, tablet, and mobile tests
  pass without browser-owned financial or authorization logic.
- Focused API/UI tests, OpenAPI drift validation, Playwright request-count assertions, Web image build,
  and the applicable gates in `GATES.md` pass.

Security: Page and section routes resolve user, project, run, and artifact authorization before reading
manifests or payloads. A section or artifact identifier alone never grants access.

Determinism: One projection revision, run identity, artifact manifest, pagination cursor, and contract
version produce byte-stable view and section responses.

Idempotency: All view and section reads are non-mutating; retries and cancelled/restarted requests
return the same revision without starting calculations or ingestion.

### PR249. Shared Browser Query Cache And Navigation Prefetch

Branch: `feat/web-query-cache`.

Git status: not started.

PR: TBD.

Priority: P1 instant repeat navigation and frontend simplification.

Depends on: PR248.

Scope:

- Adopt TanStack Query as the single browser server-state owner. Add one application query client and
  typed key factories for project context, navigation workflow, page views, run revisions, and lazy
  sections; keep ephemeral controls, open tabs, and form drafts as local React state.
- Replace production `useResource` server reads, revision counters, global custom refresh events, and
  duplicated Shell/page fetches. Remove the superseded hook after all production consumers migrate;
  retain no second cache or stale-while-revalidate implementation.
- Define explicit `staleTime`, garbage collection, retry, cancellation, and invalidation rules by
  resource. Navigation and completed immutable runs use a 5-minute `staleTime`; running states and
  page views use 15 seconds until PR250 replaces polling invalidation; unused queries are collected
  after 15 minutes; GET retries are limited to two attempts with capped backoff; commands never retry
  automatically. Mutations update returned canonical data and invalidate only affected user/project/
  run keys after server success; failed or optimistic operations cannot expose uncommitted state.
- Prefetch the destination page view on deliberate sidebar intent and after project selection, bounded
  to one destination. Use ETags from PR247/PR248 for revalidation and preserve last successful data
  during a background refresh without showing it for a different project or run.
- Keep the cache memory-only. Clear it on logout/session invalidation and never persist tenant data,
  credentials, responses, or query keys to localStorage, sessionStorage, IndexedDB, service-worker
  caches, URLs, or logs.

Out of scope: Offline mode, service workers, general client state management, visual redesign, or
speculative prefetch of every workflow page.

Acceptance:

- Shell and page components issue one network request per cold canonical query key, deduplicate
  concurrent consumers, reuse fresh data on back/forward navigation, and revalidate stale data once.
- Switching projects cannot display, flash, retry, or reuse the previous project's page view or lazy
  section. Logout and `401` session invalidation synchronously remove all tenant query data.
- Successful project, selection, ingestion, and analytical commands invalidate exactly the documented
  keys. Unit tests fail on broad global invalidation, duplicate key construction, uncancelled obsolete
  requests, or an unbounded retry loop.
- Playwright proves warm navigation renders from cache without a blocking loader, background refresh
  preserves usable content, errors retain the last matching revision, and request counts satisfy
  PR248's budgets on desktop and mobile.
- Package lockfile, TypeScript strict checks, Vitest, Playwright, production Web build, Docker image
  rebuild, storage-safety checks, and the applicable gates in `GATES.md` pass.

Security: Cache keys include authenticated scope and exact project/run identity; cache data is
memory-only and is destroyed at the authentication boundary.

Determinism: Canonical key factories and server revisions determine cache identity; component mount
order does not alter fetched data or invalidation scope.

Idempotency: Concurrent reads single-flight per key, and repeated successful invalidation converges on
one refetch of the newest server revision.

### PR250. Durable Server-Sent Job And Workflow Updates

Branch: `feat/hosted-status-event-stream`.

Git status: not started.

PR: TBD.

Priority: P1 live status with bounded request load.

Depends on: PR249.

Scope:

- Add a user-scoped durable status-event sequence for project bootstrap, metadata publication, and
  Uni/Bi/Multivariate run transitions. Store only compact event type, authorized aggregate reference,
  projection revision, terminal status, timestamp, and monotonic event ID in PostgreSQL.
- Publish events in the same transaction as source-state and PR247 projection changes. PostgreSQL
  notification may wake stream readers, but durable rows and event IDs remain the source for replay;
  notification delivery alone is never correctness authority.
- Add one authenticated FastAPI Server-Sent Events endpoint with heartbeat comments, `Last-Event-ID`
  resume, tenant filtering, connection cleanup, and proxy-safe headers. Send a heartbeat every 15
  seconds, retain events for 24 hours, replay at most 1,000 events per connection, permit at most two
  streams per authenticated session, and reconnect after 1, 2, 5, 10, then at most 30 seconds with
  jitter. Expired or oversized replay cursors return a typed reset event that triggers bounded query
  invalidation rather than silent state loss.
- Connect one browser stream per authenticated application session. Map events through PR249's key
  factories to exact invalidations or canonical cache updates. Remove fixed-interval metadata,
  bootstrap, and analysis status polling after each migrated state has equivalent stream coverage.
- Add stream connection, reconnect, lag, replay, reset, and active-client metrics plus deployment
  guidance for reverse-proxy buffering and graceful API shutdown.

Out of scope: Streaming analytical tables/matrices, bidirectional WebSockets, command submission over
the stream, browser-selected event topics, or using events as the durable business record.

Acceptance:

- One state transition produces one ordered durable event in the same successful transaction; a
  rolled-back command produces none. Duplicate command delivery cannot create duplicate logical
  transition events.
- Disconnect/reconnect with `Last-Event-ID` replays every authorized missed event in order. Reconnect
  without an ID starts from a bounded current cursor, and retention expiry yields the documented reset
  behavior without leaking the existence of another user's events.
- A complete bootstrap and each analytical run update the correct UI status without periodic polling.
  A 15-minute no-change browser session generates no application-data request beyond stream heartbeat
  traffic and documented auth/session renewal.
- Multi-tab behavior stays within the documented connection limit, abandoned streams release API and
  database resources, API restart reconnects successfully, and a slow client cannot create unbounded
  memory, cursor, or connection growth.
- RLS/adversarial stream tests, transactional event tests, browser reconnect tests, proxy/Compose
  real-stack tests, observability checks, and the applicable gates in `GATES.md` pass.

Security: Authentication and forced RLS scope every connection and replay query. Events contain no
credentials, membership lists, payload values, storage paths, lease tokens, or cross-project details.

Determinism: Commit order and a monotonic PostgreSQL event ID define replay order; event schema and
projection revision mapping are versioned.

Idempotency: Logical transition uniqueness prevents duplicate events, and replaying an event applies
the same cache update/invalidation without duplicate commands or calculations.

### PR251. Single Hosted Authority And Legacy Fallback Removal

Branch: `refactor/hosted-single-authority`.

Git status: not started.

PR: TBD.

Priority: P1 final hosted simplification.

Depends on: PR250.

Scope:

- Make PostgreSQL plus authorized shared-artifact adapters the only production hosted composition.
  Delete hosted fallback selection among in-memory state, workspace JSON, local lake repositories,
  browser-triggered provider workflows, and shared-file-derived navigation state.
- Separate package composition explicitly: local CLI commands may construct local lake adapters;
  production FastAPI routes may construct only PostgreSQL tenant/control-plane repositories and
  authorized shared payload readers; deterministic test compositions live under test-only factories.
- Remove dead compatibility branches, duplicate hosted serializers/repositories, obsolete environment
  switches, migrated polling APIs, superseded `useResource` code, and documentation that describes a
  second hosted authority. Do not remove the mathematical core or local CLI workflows.
- Add import/architecture checks that fail when hosted routes/services depend on local workflow,
  workspace, unrestricted lake, provider-client, or test-composition modules, or when CLI modules
  depend on hosted authentication/runtime composition.
- Publish a migration and rollback note covering removed environment variables/routes, required
  catalog head, minimum Web/API version pairing, deploy order, preflight, smoke checks, and rollback to
  the last compatible complete stack. No dual-read or dual-write compatibility window is permitted.
- Update `ARCHITECTURE.md`, `README.md`, hosted security/readiness documents, Compose configuration,
  OpenAPI snapshot, page specifications, and operational runbooks to one current-state diagram and
  terminology set.

Out of scope: Removing local CLI mode, rewriting mathematical code, migrating shared analytical bytes
into PostgreSQL, replacing the four-container Compose topology, or adopting a new frontend/backend
framework.

Acceptance:

- Production startup has one documented hosted composition and fails closed when PostgreSQL,
  migrations, shared-store manifests, credentials, or required secrets are unavailable. No production
  setting can select local/in-memory/workspace authority.
- Repository searches and executable architecture tests prove that hosted requests cannot read or
  mutate local workspace JSON, unrestricted lake roots, in-memory authority dictionaries, or provider
  clients; browser commands cannot trigger provider ingestion.
- Local CLI commands and focused analytical tests remain functional without PostgreSQL or hosted auth,
  while the Web/API real stack remains functional without a repository-local lake or workspace file.
- The resulting production dependency graph, environment-variable inventory, route inventory, and
  runtime module count are recorded before/after; every removed path has either a replacement named in
  PR246-PR250 or explicit proof that it was unreachable/dead.
- Fresh deployment, rolling-compatible deployment within the documented version window, restart,
  backup/restore, rollback rehearsal, two-project isolation, browser workflow, Web image build, full
  Python/TypeScript/Playwright/Docker validation, and all gates in `GATES.md` pass.

Security: Removing fallback authority must narrow access. Missing tenant records, manifests, config,
or migrations fail closed; local files and object existence can never authorize hosted access.

Determinism: Explicit composition and versioned API/projection/event contracts select one dependency
graph for a given release; startup performs no implicit migration or data import.

Idempotency: Repeated startup, readiness, reconciliation, deployment smoke, and rollback checks do not
duplicate state or mutate analytical payloads outside declared commands.

### PR252. Exhaustive User Interaction Manifest, Real-Stack Journeys, And Latency Merge Gate

Branch: `test/exhaustive-user-interaction-merge-gate`.

Git status: not started.

PR: TBD.

Priority: P0 prevent functional and interactive-performance regressions at merge time.

Depends on: PR251. PR247-PR251 change navigation projections, page contracts, browser caching,
status delivery, and production composition; their final checked-in contracts are mandatory PR252
inputs and PR252 may not preserve superseded controls or fallback routes solely to keep old tests
green.

Business outcome: Every production user-operable Web control has a stable identity and at least one
deterministic browser case that performs the same action a user can perform, verifies its observable
effect, and records bounded interaction latency. An unregistered control, stale manifest entry,
missing behavior assertion, unexpected request, browser error, or exceeded hard budget fails both the
pre-merge and post-merge aggregate gates.

Scope and ownership boundaries:

- Introduce a versioned `ui-interaction-manifest-v1` contract and committed manifest under
  `apps/web/tests/interactions/`. Each record owns exactly one stable interaction ID and declares route,
  viewport applicability, prerequisite fixture state, accessible role/name, control type, enabled or
  disabled state, user operation, sanitized input class, expected UI transition, expected request
  method/path/count, persistence check, keyboard equivalent, and latency-budget ID. IDs are stable
  semantic names and never array indexes, DOM paths, generated CSS selectors, project IDs, or labels
  containing tenant data.
- Add stable `data-portfell-interaction-id` attributes only at production interaction boundaries in
  `apps/web/src/`. The attribute is test identity, not authorization or business state. Buttons, links,
  tabs, text/search/number/date inputs, selects, textareas, checkboxes, radios, menu/drawer controls,
  form submission, retry/cancel actions, draggable controls, and keyboard-only commands are in scope.
  Read-only text, charts without an interaction, browser-native scrolling, and decorative elements are
  excluded by an explicit checked-in allowlist with a reason per exclusion.
- Add test-only structured interaction telemetry with schema
  `ui-interaction-log-v1`. Set `PORTFELL_UI_TEST_LOG_LEVEL=debug` only in Playwright and deterministic
  real-stack jobs; production and ordinary development defaults remain `info`. Browser, Web server,
  API, worker, PostgreSQL-test instrumentation, and Playwright reporters emit JSON Lines containing
  test/run ID, interaction ID, route, fixture state, viewport, operation class, redacted outcome,
  request method plus route template, request/response byte counts, database statement count,
  shared-file read count, timestamps, and elapsed milliseconds. Never log entered values, EODHD keys,
  cookies, authorization headers, request/response bodies, project names, ISIN membership, SQL text,
  filesystem roots, or secrets.
- Implement a deterministic manifest collector that reads only schema-valid redacted test logs,
  normalizes and sorts records, and proposes the committed manifest. Logs are discovery and evidence,
  not runtime or test authority: generation fails on malformed/redaction-unsafe records, and the
  committed reviewed manifest plus live DOM inventory remain authoritative. A missing log cannot remove
  a manifest entry; `--check` fails on additions, removals, changed behavior, or exclusions until the
  committed manifest is deliberately updated.
- Extend Playwright with deterministic fixtures for no-project, project-filling, ready, running,
  complete, failed, stale, empty-result, validation-error, authorization-error, server-error, retry,
  and reconnect states. Exercise desktop `1440x1080`, tablet `1024x1366`, and mobile `390x844` with the
  repository-pinned Chromium version, timezone `Europe/Amsterdam`, fixed locale, reduced motion, fixed
  clock, deterministic IDs, and no production network access.
- Add one case per manifest interaction and distinct behavior state. Fields receive valid, empty,
  malformed, minimum, maximum, over-limit, paste, clear, and keyboard-submit cases where the production
  contract permits them. Actions assert visible feedback, exact canonical request effects, final UI
  state, focus, accessibility state, persisted server state where applicable, reload behavior, project
  isolation, back/forward behavior, and duplicate/double activation. Disabled controls prove zero
  command requests and zero mutation.
- Keep mocked browser tests exhaustive and fast, then run critical complete journeys against the real
  Docker Web, API, PostgreSQL, worker, persistent test lake, and deterministic EODHD stub. The real-stack
  suite covers credential save/replace without exposing plaintext, metadata refresh, project creation
  and bootstrap, project switch, Uni/Bi/Multivariate execution, all result tabs and filters, reload,
  restart/reconnect, one injected failure/retry, and verification that no browser action invokes a real
  provider or writes outside the test data root.
- Add versioned latency budgets under `apps/web/tests/interactions/latency-budgets.v1.json`. Measure ten
  samples after one discarded warm-up per deterministic action class and publish nearest-rank p50/p95
  plus maximum. Immediate validation/loading/disabled feedback has p95 `<=250 ms` and maximum `<=500
  ms`; warm cached navigation has p95 `<=750 ms` and maximum `<=1,500 ms`; cold local page readiness has
  p95 `<=2,000 ms` and maximum `<=4,000 ms`; real-stack command acknowledgement has p95 `<=2,000 ms`
  and maximum `<=4,000 ms`. Long-running analysis completion uses its deterministic fixture SLO rather
  than the acknowledgement budget, but must show progress within `5,000 ms`, complete within `60,000
  ms`, and reconcile its terminal result. A budget may be loosened only by an explicit manifest/budget
  diff with measured before/after evidence and PR rationale.
- Add required `pr-ui-user-journeys` and `merge-ui-user-journeys` jobs, sharded by page and viewport,
  to `.github/workflows/pr-quality.yml` and `.github/workflows/merge-gate.yml`. Both stable aggregates
  depend on their corresponding job. The jobs run manifest generation in `--check` mode, exhaustive
  mocked interactions, keyboard/accessibility checks, real-stack journeys, request/resource counters,
  and latency budgets. Upload sanitized JSONL, coverage, timing summary, trace, screenshot, video,
  console, and network artifacts only on failure with seven-day retention; upload a redacted timing and
  coverage summary on success with thirty-day retention.
- Update `GATES.md`, Web test documentation, UI specifications, real-stack runbook, package scripts,
  `.gitignore`, and branch-protection instructions. Existing focused Vitest and Playwright tests remain;
  remove duplication only when the manifest case asserts the same behavior and the removal is visible
  in the PR diff.

Parallel implementation sequence and hand-off:

1. Agent A owns the versioned manifest/log schemas, redaction validator, stable interaction-ID
   convention, collector, exclusions, and fixtures. Agent B may review but must not independently add a
   second schema, logger, manifest format, or control-ID convention. The first hand-off is committed
   schema examples plus a golden normalized manifest fixture and exact validation command.
2. After that hand-off, Agent A instruments production controls and test-only logging while Agent B
   builds data-driven Playwright executors, action/effect assertions, latency reporter, and mock
   fixtures. Shared edits to `package.json`, Playwright configuration, and existing workflow specs are
   coordinated before either agent changes them.
3. Agent B adds real-stack journeys and CI shards only after Agent A's redaction and deterministic
   collector tests pass. Both agents independently run manifest `--check`, inspect the zero-uncovered
   report, and review sanitized artifacts before the final workflow and documentation update.

Out of scope: Production user analytics, session replay, logging field values or financial payloads,
random monkey testing as acceptance evidence, replacing Playwright, changing financial calculations,
changing product behavior only to simplify tests, contacting production EODHD, or treating screenshots
and wall-clock time alone as proof of functional correctness.

Acceptance:

- A live runtime inventory visits every declared route and fixture state and reports exactly `0`
  unregistered user-operable controls, `0` duplicate interaction IDs, `0` missing manifest controls,
  `0` unexplained exclusions, and `100%` manifest entries with an executed action/effect case. Adding a
  production control without a manifest record and test makes both UI jobs fail with its route, state,
  role, accessible name, and interaction ID; deleting a control leaves a stale-entry failure.
- Every button, link, tab, field, select, checkbox, radio, drawer/menu action, form operation, retry,
  cancel, drag/drop, and keyboard command reachable in the deterministic states is either tested or
  appears once in the reviewed exclusion file with a machine-checked non-empty reason. Dynamic controls
  are covered in each state that changes enabledness, request behavior, or result behavior.
- Every enabled manifest action proves the declared visible intermediate feedback, exact request
  method/template/count, response handling, final accessible UI state, and persistent effect. Every
  disabled or invalid case proves no command request, no database mutation, no shared-store write, and
  a specific accessible explanation. Double-click, Enter, retry, reload, browser back/forward, and
  project-switch cases create no duplicate logical command or cross-project state flash.
- Test logs validate against `ui-interaction-log-v1`, regenerate byte-identically after stable sorting,
  and produce the same manifest proposal from equivalent runs regardless of Playwright worker order.
  Deliberate fixtures containing a provider key, cookie, authorization header, project name, ISIN,
  SQL/body content, or absolute data path are rejected before artifact upload. Repository and artifact
  secret scans report zero findings.
- Desktop, tablet, and mobile cases assert mouse/pointer and keyboard behavior, visible focus,
  accessible names, labels, roles, selected/expanded/disabled states, modal/drawer focus restoration,
  and zero critical or serious automated accessibility violations. Responsive controls are neither
  omitted nor counted as covered by an invisible desktop element.
- The mocked suite blocks every non-local network origin, uses condition-based assertions without
  sleeps, passes with `fullyParallel`, and produces the same control/action coverage under one worker
  and the configured shard count. No test depends on execution order, retained browser state, a real
  provider, production credentials, or an existing developer database/lake.
- The real-stack journey starts from empty isolated PostgreSQL and lake state, reaches successful
  metadata/project/Uni/Bi/Multivariate terminal states, exercises every critical control class, then
  survives browser reload and API/worker recreation with exact project isolation and persisted results.
  The deterministic provider call count, command/job identities, database changes, and lake business
  keys reconcile; duplicate logical command and duplicate full business-key counts are zero.
- Each timed sample records elapsed time together with request count, response bytes, database
  statement count, shared-file reads, fixture state, and runner identity. Every hard p95 and maximum
  budget passes. Navigation assertions preserve PR248 request budgets, PR249 cache behavior, PR250 SSE
  behavior, and PR246 loaded-worker capacity; a timing result without the associated resource counters
  fails evidence validation.
- Browser `pageerror`, unhandled rejection, unexpected `console.error`, failed/unexpected request,
  response contract error, React warning, hydration error, or uncaught API/worker exception fails the
  responsible interaction case. Expected injected failures are matched by interaction ID and exact
  typed error contract rather than globally ignored.
- `pr-quality` cannot succeed unless `pr-ui-user-journeys` succeeds, and `merge-gate` cannot succeed
  unless `merge-ui-user-journeys` succeeds. A workflow contract test proves both dependencies and all
  required shards, real-stack execution, artifact redaction, and latency checks are present; no
  `continue-on-error`, optional job, unpinned browser image, or production secret is used.
- Completion evidence includes successful executions of
  `cd apps/web && npm run interactions:manifest:check`,
  `cd apps/web && npm run test:user-interactions`,
  `cd apps/web && npm run test:user-latency`,
  `bash scripts/run_real_stack_e2e.sh --suite user-interactions`,
  `uv run portfell-quality pr`, and `uv run portfell-quality merge`, plus a redacted coverage/timing
  summary listing total controls, actions, states, viewport shards, exclusions, p50/p95/max, request
  counts, response bytes, database statements, shared-file reads, Git SHA, image/browser digests, and
  zero secret findings.

Security: Interaction IDs and logs are untrusted diagnostics, never authorization input. Test logging
is opt-in and fail-closed outside production defaults; all values, bodies, credentials, tenant
identifiers, market membership, SQL, and paths remain absent or redacted. Real-stack jobs use isolated
ephemeral credentials and test roots, least-privilege containers, no production network, and no
long-lived artifact containing tenant data.

Determinism: Versioned schemas, stable IDs, canonical sorting, fixed fixtures, clock, locale, timezone,
viewport, browser digest, test data, route templates, action semantics, sample count, percentile rule,
and budgets determine byte-stable manifest and evidence output. Equivalent application behavior yields
the same coverage and timing classifications independent of worker/shard order.

Idempotency: Re-running collection, manifest checking, mocked interactions, real-stack journeys, and
latency samples from the same fixture state neither changes the committed manifest nor duplicates
projects, jobs, runs, revisions, settings, or lake business keys. Failed and retried tests clean their
isolated state and never reuse production or another shard's database, lake, browser profile, log, or
artifact directory.

Rollback: PR252 adds no production data migration or user tracking. Rollback removes the two UI jobs,
test-only log switch, reporter, interaction attributes, manifest, and fixtures together; restores the
previous aggregate dependencies and `GATES.md`; and leaves production API/database/shared-store
contracts unchanged. A rollback must not leave verbose test logging enabled in production or retain a
partial manifest as a non-blocking check.

### Hosted Simplicity And Interactive Performance Series Completion Gate

This series is complete only after PR246 through PR252 merge in order and the current gates in
[GATES.md](GATES.md) pass. One clean production-like evidence run must prove:

- health, project navigation, and workflow remain responsive throughout a deterministic large
  bootstrap and analytical workload, with idle/loaded latency, errors, resource occupancy, database
  statements, shared-file reads, response bytes, and worker throughput captured together;
- navigation GETs are bounded, side-effect-free PostgreSQL projection reads with zero Parquet/shared-
  file access, constant statement count, private ETag revalidation, and forced-RLS isolation;
- cold shell/page entry respects the two-request budget, warm navigation does not block on the network,
  and hidden analytical sections perform no request until opened;
- TanStack Query is the only production browser server-state cache, tenant data is memory-only, exact
  invalidation and cancellation prevent cross-project flashes, and logout clears all cached data;
- one resumable SSE stream replaces periodic status polling, survives API/browser reconnect, bounds
  replay and slow-client resources, and leaks no cross-user event or aggregate identity;
- hosted production has one PostgreSQL/shared-artifact authority with no local, in-memory, workspace,
  unrestricted-lake, or provider-client fallback, while local CLI analysis remains independently
  supported;
- synchronized migrations, contracts, OpenAPI, architecture, UI specifications, observability,
  deployment/rollback runbooks, focused regressions, full quality gates, rebuilt Web image, and
  production-like browser evidence are complete.

## Current Architectural Decision

Portfell remains a public open-source repository, while the hosted deployment is a private runtime environment.

The target system has these non-negotiable properties:

- Google is the only end-user authentication provider.
- PostgreSQL is the primary application database for users, identities, encrypted provider
  credentials, project create/delete history, immutable selection versions and listing membership,
  ingestion/analysis jobs, audit events, and project-to-artifact authorization references.
- EODHD keys are encrypted at rest with envelope encryption. The key-encryption key is never stored in Git, PostgreSQL, container images, build artifacts, logs, or GitHub Actions.
- Runtime secrets live outside the repository checkout and are mounted only into services that require them.
- EODHD market observations are stored once in a canonical shared physical store with unique
  dataset/listing/business keys, atomic publication, deterministic hashes, and explicit correction
  semantics.
- A project selection may read globally shared observations for exactly its full listing members.
  Object existence alone grants nothing; API authorization always starts from an owned PostgreSQL
  project and immutable selection version.
- Project creation may request one server-owned initial delta fill for its immutable exact selection,
  using the operations EODHD credential inside the worker. A fully covered selection makes no
  provider request; user credentials never feed the globally shared corpus.
- After initial fill, only the operations-owned nightly cron may refresh quotes, dividends, and
  splits, using a dedicated service credential and the unique active-project listing union.
- Every analysis is pinned to exact immutable shared market revisions and artifact dependencies.
- Univariate, bivariate, multivariate, portfolio, backtest, and report payloads are globally
  deduplicated by exact input hashes and algorithm versions, while visibility is granted only through
  user-owned PostgreSQL project/run references.
- Hosted analytical code must consume resolved scoped inputs and must never scan unrestricted global Silver or Gold data.
- The local CLI and analytical core remain usable without Google authentication or PostgreSQL through explicit local adapters.
- Public hosting remains blocked until provider licensing explicitly permits cross-customer shared
  storage/derived reuse/service-credential refresh and privacy, backup, credential, migration,
  reconciliation, and security readiness gates pass.

## Series Completion Gate

PR143 through PR150 are the first active series. Until PR150 lands, the production browser continues
to expose exactly the current three modules. PR150 may change that invariant to exactly
four modules only after every dormant contract, calculation, artifact, persistence, API, and test
dependency in the preceding PRs is complete. PR151 through PR155 then implement
the shared-data and nightly-refresh cutover without changing the four-module order.

The authoritative completion criteria are both active Series Completion Gates above and the current
pre-merge and post-merge requirements in [GATES.md](GATES.md). Hosted deployment remains
independently subject to the existing security, licensing, privacy, backup, credential, and
readiness gates.

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
| PR245 | Mixed Distribution Frequency Portfolios | completed; merged in PR https://github.com/SergejSchweizer/portfell/pull/398 |
| PR244 | Multivariate Calculation Correctness | completed in PRs https://github.com/SergejSchweizer/portfell/pull/394 and https://github.com/SergejSchweizer/portfell/pull/396 |
| PR243 | Bivariate Calculation Correctness | completed in PR https://github.com/SergejSchweizer/portfell/pull/395; PR #393 closed without merge |
| PR242 | Univariate Calculation Correctness | completed; merged in PR https://github.com/SergejSchweizer/portfell/pull/392 |
| PR241 | Univariate Overview Narrow Bars | completed; merged in PR https://github.com/SergejSchweizer/portfell/pull/391 |
| PR240 | Multivariate Minimum Variance Convergence | completed; merged in PR https://github.com/SergejSchweizer/portfell/pull/390 |
| PR239 | Multivariate Overview Metric Labels | completed; merged in PR https://github.com/SergejSchweizer/portfell/pull/389 |
| PR238 | Multivariate Overview Portfolio Controls | completed; merged in PR https://github.com/SergejSchweizer/portfell/pull/388 |
| PR237 | Multivariate Overview Cumulative Axis | completed; merged in PR https://github.com/SergejSchweizer/portfell/pull/387 |
| PR236 | Multivariate Overview Portfolio Colors | completed; merged in PR https://github.com/SergejSchweizer/portfell/pull/386 |
| PR235 | Multivariate Overview Facts Removal | completed; merged in PR https://github.com/SergejSchweizer/portfell/pull/385 |
| PR234 | Multivariate Overview Portfolio Summary | completed; merged in PR https://github.com/SergejSchweizer/portfell/pull/384 |
| PR233 | Multivariate Overview Tabs | completed; merged in PR https://github.com/SergejSchweizer/portfell/pull/383 |
| PR232 | Automatic Compose Stack Rebuilds | completed; merged in PR https://github.com/SergejSchweizer/portfell/pull/382 |
| PR231 | Multivariate Performance Series Controls | completed; merged in PR https://github.com/SergejSchweizer/portfell/pull/381 |
| PR230 | Condense Finished Backlog Records | completed; merged in PR https://github.com/SergejSchweizer/portfell/pull/380 |
| D017 draft PR168-PR175 | Duplicate durable-authority draft sequence | superseded and discarded as non-active; implemented outcomes are represented by the merged D017 records below |
| PR168 operational follow-up | Production Cron Installation And First Scheduled Run Evidence | remaining operational backlog discarded by user direction on 2026-08-14; implementation PR #329 remains merged and no natural-run acceptance is claimed |
| PR246 | Worker Admission Control And Interactive Capacity | merged 2026-08-14. PR: https://github.com/SergejSchweizer/portfell/pull/400; commit `2e2663299ae2e7806774176d8e7f261b6aefac60` |
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
| PR110 | Canonical Workflow State And Four-Page API Contract | merged. PR: https://github.com/SergejSchweizer/portfell/pull/190 |
| PR111 | Metadata Header, Metadata Builder, And Real Quote Progress | merged. PR: https://github.com/SergejSchweizer/portfell/pull/197 |
| PR112 | Functional Univariate Statistics Page | merged. PR: https://github.com/SergejSchweizer/portfell/pull/192 |
| PR113 | Functional Univariate Selection Page | merged. PR: https://github.com/SergejSchweizer/portfell/pull/193 |
| PR114 | Functional Bivariate Statistics Page | merged. PR: https://github.com/SergejSchweizer/portfell/pull/194 |
| PR115 | Sequential Navigation, Final Legacy Deletion, And End-To-End Gate | merged. PR: https://github.com/SergejSchweizer/portfell/pull/195 |
| PR116 | Remove Google Authentication Runtime | merged. PR: https://github.com/SergejSchweizer/portfell/pull/196 |
| PR124 | Stable Local Principal And Credential Repository Ports | merged. PR: https://github.com/SergejSchweizer/portfell/pull/210 |
| PR125 | PostgreSQL Encrypted Credential Repository And Schema Migration | merged. PR: https://github.com/SergejSchweizer/portfell/pull/211 |
| PR126 | Persistent Credential Runtime Wiring And Secret Configuration | merged. PR: https://github.com/SergejSchweizer/portfell/pull/213 |
| PR127 | Saved Credential Status, Replace, Delete, And Keyless Refresh UI | merged. PR: https://github.com/SergejSchweizer/portfell/pull/214 |
| PR129 | Hosted API Routers, Application Services, And State Ports | merged. PR: https://github.com/SergejSchweizer/portfell/pull/218 |
| PR132 | Stage-Owned Ingestion Controls | merged. PR: https://github.com/SergejSchweizer/portfell/pull/222 |
| PR133 | Hosted Research Service Boundary Completion | merged. PR: https://github.com/SergejSchweizer/portfell/pull/238 |
| PR134 | Hosted Research Boundary Coverage Completion | merged. PR: https://github.com/SergejSchweizer/portfell/pull/240 |
| PR135 | Stateful Two-Project UI Workflow Coverage | merged. PR: https://github.com/SergejSchweizer/portfell/pull/242 |
| PR136 | Result-Driven Dividends Window Visibility | merged. PR: https://github.com/SergejSchweizer/portfell/pull/244 |
| PR137 | Workflow Module Boundaries | merged. PR: https://github.com/SergejSchweizer/portfell/pull/245 |
| PR138 | Parallel Metadata Downloads | merged. PR: https://github.com/SergejSchweizer/portfell/pull/246 |
| PR139 | Browser Module Route Names | merged. PR: https://github.com/SergejSchweizer/portfell/pull/247 |
| PR140 | Three-Module Backend And Persistence Contracts | merged. PR: https://github.com/SergejSchweizer/portfell/pull/248 |
| PR141 | Aligned Statistics Time Ranges | merged. PR: https://github.com/SergejSchweizer/portfell/pull/249 |
| PR92 | Content-Addressed Univariate And Return Artifact Cache | merged. PR: https://github.com/SergejSchweizer/portfell/pull/135 |
| PR93 | Content-Addressed Bivariate Cache And Exact Alignment Identity | merged. PR: https://github.com/SergejSchweizer/portfell/pull/136 |
| PR95 | Docker Compose PostgreSQL, API, Web, And Shared Runtime Storage | merged. PR: https://github.com/SergejSchweizer/portfell/pull/140 |
| PR96 | FastAPI User, Credential, Download, Dataset, Project, And Analysis API | merged. PR: https://github.com/SergejSchweizer/portfell/pull/142 |
| PR97 | Google-Authenticated Web UI And User-Scoped Research Funnel | merged. PR: https://github.com/SergejSchweizer/portfell/pull/143 |
| PR98 | Public-Repository CI, Supply-Chain, Secret-Scanning, And Deployment Hardening | merged. PR: https://github.com/SergejSchweizer/portfell/pull/145 |
| PR99 | Licensing, Privacy, Retention, Backup, Restore, And Key-Rotation Gate | merged. PR: https://github.com/SergejSchweizer/portfell/pull/146 |
| PR100 | End-To-End Multi-User Isolation, Reproducibility, And Hosted Cutover | merged. PR: https://github.com/SergejSchweizer/portfell/pull/147 |
| PR101 | Web Design System, Application Shell, And Visual Baseline | merged. PR: https://github.com/SergejSchweizer/portfell/pull/152 |
| PR143 | Monthly-Distribution ETF Multivariate Input Snapshot | completed. Integrated through the branch reconciliation in PR #377. |
| PR144 | Canonical Multivariate Risk-Model Artifact And Optimizer Wiring | completed. Integrated through the branch reconciliation in PR #377. |
| PR145 | Multivariate Portfolio-Structure Statistics | completed. Integrated through the branch reconciliation in PR #377. |
| PR146 | Gross Distribution History And Monthly Income Quality | completed. Integrated through the branch reconciliation in PR #377. |
| PR147 | Monthly-Distribution ETF Portfolio Candidate Set | completed. Integrated through the branch reconciliation in PR #377. |
| PR148 | Multivariate Walk-Forward, Stress, And Candidate Scorecard | completed. Integrated through the branch reconciliation in PR #377. |
| PR149 | Project-Persisted Multivariate Service And API Contract | completed. Integrated through the branch reconciliation in PR #377. |
| PR150 | Multivariate Statistics React Module And Four-Module Cutover | completed. Integrated through the branch reconciliation in PR #377. |
| PR151 | Canonical Shared Market Store And Active Project Inventory | merged. PR: https://github.com/SergejSchweizer/portfell/pull/269 |
| PR152 | Idempotent Shared Market Refresh Command And Initial Backfill | merged. PR: https://github.com/SergejSchweizer/portfell/pull/269 |
| PR153 | Project Analysis Cutover To Shared Market Snapshots | merged. PR: https://github.com/SergejSchweizer/portfell/pull/269 |
| PR154 | Docker Compose Nightly Cron Installer And Operations Gate | merged. PR: https://github.com/SergejSchweizer/portfell/pull/269 |
| PR155 | Remove Manual Historical-Data Actions And Legacy Quote Runs | merged. PR: https://github.com/SergejSchweizer/portfell/pull/269 |
| PR156 | Shared Data Licensing Decision And Plane Contracts | merged. PR: https://github.com/SergejSchweizer/portfell/pull/274 |
| PR157 | PostgreSQL Tenant Schema And Row-Level Security | merged. PR: https://github.com/SergejSchweizer/portfell/pull/275 |
| PR158 | PostgreSQL Repositories And Hosted State Importer | merged. PR: https://github.com/SergejSchweizer/portfell/pull/287 |
| PR159 | PostgreSQL Durable Jobs, Outbox, And Worker Claims | merged. PR: https://github.com/SergejSchweizer/portfell/pull/288 |
| PR160 | Immutable Shared Market Revisions And Dataset Delta Planner | merged. PR: https://github.com/SergejSchweizer/portfell/pull/290 |
| PR161 | Exact-Selection One-Time Project Data Bootstrap | merged. PR: https://github.com/SergejSchweizer/portfell/pull/292 |
| PR162 | Shared Univariate Artifact Cutover | merged. PR: https://github.com/SergejSchweizer/portfell/pull/294 |
| PR163 | Bucketed Shared Bivariate Artifact Cutover | merged. PR: https://github.com/SergejSchweizer/portfell/pull/295 |
| PR164 | Shared Multivariate Artifact Cutover | merged. PR: https://github.com/SergejSchweizer/portfell/pull/282 |
| PR165 | Cron-Only Ongoing Refresh And User Update Closure | merged. PR: https://github.com/SergejSchweizer/portfell/pull/283 |
| PR166 | Operations Readiness, Recovery, And Cutover Rehearsal | merged. PR: https://github.com/SergejSchweizer/portfell/pull/296 |
| PR167 | Hosted Repository Injection Baseline | merged. PR: https://github.com/SergejSchweizer/portfell/pull/325 |
| PR169 | Exhaustive Button Interaction Tests And Required Merge Gates | merged. PR: https://github.com/SergejSchweizer/portfell/pull/327 |
| PR170 | UGREEN NAS Persistent Data Root And Safe Volume Migration | merged. PR: https://github.com/SergejSchweizer/portfell/pull/330 |
| PR171 | Multivariate Risk Structure Facts Table | completed. PR: https://github.com/SergejSchweizer/portfell/pull/376 |
| PR176 | Dependency Baseline Update | merged. PR: https://github.com/SergejSchweizer/portfell/pull/336 |
| PR177 | Node 26 Runtime Update | merged. PR: https://github.com/SergejSchweizer/portfell/pull/337 |
| PR178 | Initial-Fill Status Projection Synchronization | merged. PR: https://github.com/SergejSchweizer/portfell/pull/338 |
| PR179 | Batched Shared Delta Publication | merged. PR: https://github.com/SergejSchweizer/portfell/pull/339 |
| PR180 | Quote Run Success Reuse | merged. PR: https://github.com/SergejSchweizer/portfell/pull/340 |
| PR181 | Initial-Fill Lease Resilience And Observability | merged. PR: https://github.com/SergejSchweizer/portfell/pull/341 |
| PR182 | GitHub Actions Node 24 Runtime | merged. PR: https://github.com/SergejSchweizer/portfell/pull/342 |
| PR183 | Empty Market-Response Coverage | completed. PR: https://github.com/SergejSchweizer/portfell/pull/343 |
| PR184 | Faster EODHD Shared Refresh | completed. PR: https://github.com/SergejSchweizer/portfell/pull/344 |
| PR185 | Remove Default EODHD Client Pacing | completed. PR: https://github.com/SergejSchweizer/portfell/pull/345 |
| PR186 | Per-Fetch Coverage Persistence | completed. PR: https://github.com/SergejSchweizer/portfell/pull/346 |
| PR187 | EODHD Event Business Keys | completed. PR: https://github.com/SergejSchweizer/portfell/pull/347 |
| PR188 | Retry Failed Initial Fill | completed. PR: https://github.com/SergejSchweizer/portfell/pull/348 |
| PR189 | Preserve Initial-Fill Attempt History | completed. PR: https://github.com/SergejSchweizer/portfell/pull/349 |
| PR190 | Initial-Fill Failed ISIN Status | completed. PR: https://github.com/SergejSchweizer/portfell/pull/350 |
| PR191 | Commit Univariate Progress | completed. PR: https://github.com/SergejSchweizer/portfell/pull/351 |
| PR192 | Visual Univariate Progress And Tab Layout | completed. PR: https://github.com/SergejSchweizer/portfell/pull/352 |
| PR193 | Statistics Result Completion Visibility | completed. PR: https://github.com/SergejSchweizer/portfell/pull/353 |
| PR194 | Bivariate Compute Lifecycle | completed. PR: https://github.com/SergejSchweizer/portfell/pull/354 |
| PR195 | Sidebar Workflow Status Colors | merged. PR: https://github.com/SergejSchweizer/portfell/pull/355 |
| PR196 | Shared Statistics Tab Layout | completed. PR: https://github.com/SergejSchweizer/portfell/pull/356 |
| PR197 | Bivariate Filtered Univariate Selection | merged. PR: https://github.com/SergejSchweizer/portfell/pull/357 |
| PR198 | Desktop-Only UI Tests | merged. PR: https://github.com/SergejSchweizer/portfell/pull/358 |
| PR199 | Bivariate Shared-Market Quote Fallback | completed. PR: https://github.com/SergejSchweizer/portfell/pull/359 |
| PR200 | Multivariate Compute Layout | merged. PR: https://github.com/SergejSchweizer/portfell/pull/360 |
| PR201 | Multivariate Run Recovery | merged. PR: https://github.com/SergejSchweizer/portfell/pull/361 |
| PR202 | Multivariate Statistics Completeness | completed. PR: https://github.com/SergejSchweizer/portfell/pull/362 |
| PR203 | Persisted Univariate Filter Feedback | completed. PR: https://github.com/SergejSchweizer/portfell/pull/363 |
| PR204 | Multivariate History Eligibility | merged. PR: https://github.com/SergejSchweizer/portfell/pull/364 |
| PR205 | Multivariate History Guidance | completed. PR: https://github.com/SergejSchweizer/portfell/pull/365 |
| PR206 | Multivariate Minimum History Policy | completed. Integrated through the branch reconciliation in PR #377. |
| PR207 | Market-Price NAV Proxy | completed. Integrated through the branch reconciliation in PR #377. |
| PR208 | Statistics Progress Height | completed. Integrated through the branch reconciliation in PR #377. |
| PR209 | Metadata Option ISIN Counts | completed. Integrated through the branch reconciliation in PR #377. |
| PR210 | Portfolio Selection Counts | completed. Integrated through the branch reconciliation in PR #377. |
| PR211 | Multivariate CPU Parallelism | completed. Integrated through the branch reconciliation in PR #377. |
| PR212 | Univariate Compute Progress | completed. Integrated through the branch reconciliation in PR #377. |
| PR213 | Project-Scoped Statistics State | completed. Integrated through the branch reconciliation in PR #377. |
| PR214 | Multivariate Stall Recovery | completed. Integrated through the branch reconciliation in PR #377. |
| PR215 | Parallel Walk-Forward Refits | completed. Integrated through the branch reconciliation in PR #377. |
| PR216 | Polars Dataframe Preference | completed. Integrated through the branch reconciliation in PR #377. |
| PR217 | Polars Statistics Pipelines | completed. Integrated through the branch reconciliation in PR #377. |
| PR218 | Multivariate Validation Budget | completed. Integrated through the branch reconciliation in PR #377. |
| PR219 | Main Branch Consolidation | merged. PR: https://github.com/SergejSchweizer/portfell/pull/366 |
| PR220 | Multivariate Performance And CVaR Recovery | merged. PR: https://github.com/SergejSchweizer/portfell/pull/367 |
| PR221 | Multivariate Monthly-Return Candidate And Performance Inspection | merged. PR: https://github.com/SergejSchweizer/portfell/pull/368 |
| PR222 | Multivariate Portfolio Return Averages | merged. PR: https://github.com/SergejSchweizer/portfell/pull/369 |
| PR223 | Multivariate All-Portfolio Performance Plot | merged. PR: https://github.com/SergejSchweizer/portfell/pull/370 |
| PR224 | Multivariate Portfolio Color Hierarchy | merged. PR: https://github.com/SergejSchweizer/portfell/pull/371 |
| PR225 | Multivariate Overview Facts Table | completed. PR: https://github.com/SergejSchweizer/portfell/pull/375 |
| PR225 | Multivariate Performance Aligned-Period X-Axis | merged. PR: https://github.com/SergejSchweizer/portfell/pull/372 |
| PR226 | Project-Scoped Canonical Workflow URLs | completed. PR: https://github.com/SergejSchweizer/portfell/pull/374 |
| PR227 | All Branch Historical Reconciliation | completed. PR: https://github.com/SergejSchweizer/portfell/pull/377 |
| PR228 | Evaluate All Multivariate Portfolio Candidates | completed. PR: https://github.com/SergejSchweizer/portfell/pull/378 |
| PR229 | Multivariate Overview Monthly Performance | completed. PR: https://github.com/SergejSchweizer/portfell/pull/379 |
