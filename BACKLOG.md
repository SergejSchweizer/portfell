# Backlog

Last reviewed: 2026-08-04

## Table Of Contents

- [Backlog Policy](#backlog-policy)
- [Active Four-Page Portfell UI PR Stack](#active-four-page-portfell-ui-pr-stack)
- [Active Hosted Multi-Tenant Portfell PR Stack](#active-hosted-multi-tenant-portfell-pr-stack)
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

## Active Four-Page Portfell UI PR Stack

This is the canonical UI implementation stack. It supersedes the former eight-stage research-funnel UI plan. The production application has exactly four pages, in this order:

```text
metadata_filter
    -> univariate_statistics
    -> univariate_filter
    -> bivariate_statistics
```

The persistent header contains the EODHD credential input and the metadata refresh action. The canonical Python operation is `fetch_all_metadata`; the removed name `fetch_all_isins` must not be reintroduced as a function, module, command, route, alias, compatibility shim, or documentation term.

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
