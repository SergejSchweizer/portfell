# Backlog

Last reviewed: 2026-08-11

## Table Of Contents

- [Backlog Policy](#backlog-policy)
- [Active PostgreSQL Tenant Plane And Shared Data PR Stack](#active-postgresql-tenant-plane-and-shared-data-pr-stack)
- [Active Monthly-Distribution ETF Multivariate PR Stack](#active-monthly-distribution-etf-multivariate-pr-stack)
- [Active Shared Market Data And Nightly Refresh PR Stack](#active-shared-market-data-and-nightly-refresh-pr-stack)
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

## Active PostgreSQL Tenant Plane And Shared Data PR Stack

This series implements D017. PostgreSQL becomes the only hosted source of truth for tenant and
control-plane state. The shared store contains only tenant-neutral market and analytical payloads.
The API authorizes every operation through an owned PostgreSQL project and selection; neither the
browser nor analytical workers receive an unrestricted shared-store root.

The target data flow is:

```text
user + encrypted key metadata + immutable project/selection + lifecycle history
                              |
                              v
                    PostgreSQL tenant plane
                              |
              one user-requested, operations-owned selection delta fill
                              v
       shared quotes / dividends / splits + coverage catalog
                              |
                 content-addressed calculations
                              v
       shared uni / bi / multivariate artifact payloads
                              |
                              v
          PostgreSQL project/run/artifact references

all shared ingestion: dedicated operations credential
after initial fill: nightly cron delta only
```

User EODHD credentials remain envelope-encrypted tenant metadata but never feed the globally shared
corpus. Both the user-requested initial project fill and nightly refresh resolve one dedicated
operations credential inside trusted workers. This removes credential races, billing ambiguity, and
cross-user provenance from shared ingestion. It requires explicit provider-license approval for
cross-customer storage, derived reuse, and service-credential ingestion; PR156 is a blocking
fail-closed gate, not optional documentation.

PR156 through PR167 are sequential. PR170 depends on PR167 and must complete before PR168 installs
the production cron against the final storage paths. PR169 depends on PR167 and may execute in
parallel. PR168, PR169, and PR170 are all required to complete the series. No PR may dual-write
market/statistical payloads into PostgreSQL, put user/project fields into shared payloads, authorize
from object existence, let a browser choose storage paths or credentials, or retain local-workspace
JSON as a second hosted source of truth after cutover.

### PR156. Shared Data Licensing Decision And Plane Contracts

Branch: `docs/shared-data-plane-contracts`.

Git status: merged.

PR: https://github.com/SergejSchweizer/portfell/pull/274.

Priority: P0 architecture and licensing gate.

Depends on: current `main`.

Scope:

- Make D017 the canonical hosted target and mark the per-user market-grant portions of D016 as
  superseded. Define `TenantControlPlane`, `SharedMarketStore`, `SharedArtifactStore`, and
  `SharedCatalog` ports without changing active runtime wiring.
- Classify every persisted field. PostgreSQL owns users, external identities/sessions where enabled,
  encrypted credential envelopes and metadata, projects, soft-deletion state, immutable selection
  versions, full listing membership, current-project preference, bootstrap/refresh/analysis jobs,
  audit events, and project-to-artifact references. Shared storage owns quote, dividend, split, and
  analytical payload bytes only.
- Define full listing identity as `(provider, exchange, isin, code)`. Define market revision identity
  per dataset from schema version, canonical business keys, and content hash. Define analytical
  identity from exact input revisions, parameters, algorithm version, and schema version.
- Define one ingestion credential role: only a separately provisioned operations credential may
  fetch shared market data, for both project bootstrap and cron. User credentials remain encrypted
  tenant metadata for separately licensed future capabilities and are never eligible for shared
  ingestion. Credential identity never enters shared data identity or read authorization.
- Define projects as immutable research scopes after creation. Metadata Builder resolves exactly one
  canonical listing per unique ISIN and persists it as one immutable selection version; changing any
  filter or member creates a new project rather than mutating membership in place.
- Add a provider-license decision record and deployment gate covering shared cross-customer storage,
  derived artifact reuse, retention after project/user deletion, and service-credential refresh.
  Block hosted rollout unless every required permission is explicitly approved.
- Specify deletion and retention: project deletion is a PostgreSQL tombstone plus audit event;
  credential deletion destroys ciphertext/key references under policy; shared payloads survive
  project deletion and are removed only by a separate operations retention/GC policy.
- Synchronize `ARCHITECTURE.md`, `CONTRACTS.md`, `DECISIONS.md`, `RISKS.md`, security docs, and
  architecture checks. Do not add migrations, repositories, endpoints, or UI.

Acceptance:

- A machine-readable ownership matrix assigns every current hosted field/table/file to exactly one
  plane and rejects user/project/credential/session fields in shared payload schemas.
- Contract tests distinguish project authorization from shared physical existence: an unknown or
  unowned project cannot resolve a shared object even when its id is guessed.
- Identity fixtures prove that equal full listing/input identities deduplicate globally, while a
  changed exchange, code, business row, parameter, schema, or algorithm version changes identity.
- A selection fixture with 1,753 unique ISINs produces exactly 1,753 canonical listing members. A
  second listing for one ISIN is resolved by the versioned canonical-listing policy, not persisted as
  a second member.
- Contract tests prove user credentials cannot be selected by bootstrap or cron workers and that
  missing/revoked operations credentials fail before planning or provider calls.
- The licensing readiness check returns a stable blocking result when approval evidence is absent,
  expired, or does not cover all four required uses; no environment defaults to approved.
- Documentation contains one unambiguous owner for initial fill, nightly refresh, project deletion,
  credential deletion, shared retention, backup, and authorization.

Security: Shared-object existence is never an authorization claim. Credential plaintext, wrapped
keys, tenant ids, project ids, and global inventory never enter payload contracts or browser APIs.

Determinism: Ownership classification, identities, reason codes, and licensing-gate output are
versioned and independent of runtime order, locale, wall-clock time, or object-store listing order.

Idempotency: Re-evaluating identical contracts and evidence yields the same identities and readiness
result without writing runtime state.

### PR157. PostgreSQL Tenant Schema And Row-Level Security

Branch: `feat/postgres-tenant-control-schema`.

Git status: merged.

PR: https://github.com/SergejSchweizer/portfell/pull/275.

Priority: P0 durable user-metadata foundation.

Depends on: PR156.

Scope:

- Add forward-only PostgreSQL migrations for `users`, encrypted `provider_credentials`, projects,
  immutable `project_selection_versions`, `project_selection_members`,
  `current_project_preferences`, `analysis_runs`, `project_artifact_refs`, and append-only
  `audit_events`. Reconcile existing tables without destructive migration. Durable job/outbox tables
  belong to PR159 and global catalogs belong to PR160/PR162-PR164.
- Give projects `status`, `created_at`, and `deleted_at`. Project membership is immutable; a project
  has exactly one selection version and one row per unique ISIN containing its canonical provider,
  exchange, code, and listing id. Keep tombstoned project/membership rows under explicit retention.
  Use `audit_events` for lifecycle history instead of a second `project_events` truth source.
- Store credential ciphertext, nonce, wrap nonce, wrapped data key, KEK version, authenticated
  associated data, fingerprint HMAC, masked label, lifecycle timestamps, and status. Never store or
  return plaintext. Enforce at most one active credential per `(user, provider, purpose)`.
- Add separate least-privilege roles for tenant API, ingestion/analysis workers, migration, and
  read-only operations. Force RLS on all tenant tables; global catalogs are inaccessible to browser
  SQL roles and reached only through trusted services.

Acceptance:

- Applying migrations twice to an empty database is a no-op on the second run; upgrading the current
  schema preserves all rows; downgrade is intentionally unsupported and documented.
- PostgreSQL integration tests prove two users can use equal project names and equal listing members
  without seeing each other's project, selection, credential metadata, jobs, runs, or audit events.
- A project create, soft delete, restore where policy permits, and permanent user deletion produce
  exact relational rows and append-only audit events. Attempts to add/remove/replace membership on an
  existing project fail with `project_membership_immutable`.
- Membership has foreign/unique/check constraints that reject duplicate ISINs, blank ISIN,
  missing provider/exchange/code, mutation, and membership owned by another user/project. One project
  reports the same member count from PostgreSQL, API, workflow, and progress contracts.
- Database inspection proves quote, dividend, split, and uni/bi/multivariate payload columns do not
  exist in PostgreSQL tables. Credential plaintext cannot be selected, logged, or reconstructed
  without the external KEK.
- Tenant, worker, migrator, and readonly role tests prove the documented grants and deny cross-role
  writes, RLS bypass, direct shared-catalog browsing, and tenant-table delete outside approved
  procedures.

Security: Every tenant transaction sets one transaction-local user id before any query. RLS is
forced, table owners are not runtime roles, credentials use envelope encryption, and audit metadata
is allow-listed and secret-free.

Determinism: Migration order/checksums, normalized listing ids, selection hashes, constraints, and
event types are stable and schema-versioned.

Idempotency: Migrations, project create keys, immutable selection hashes, lifecycle events, analysis
runs, and artifact references have uniqueness rules that make retries converge without duplicates.

### PR158. PostgreSQL Repositories And Hosted State Importer

Branch: `refactor/postgres-hosted-repositories`.

Git status: merged.

PR: https://github.com/SergejSchweizer/portfell/pull/287.

Priority: P0 remove JSON/in-memory hosted authority.

Depends on: PR157.

Scope:

- Implement repository ports and Psycopg adapters for credentials, projects, selection versions and
  members, preferences, analyses, artifact references, and audit events. Keep application
  services dependent on ports rather than SQL or `HostedApiState` dictionaries.
- Define one transaction boundary per API command. Bind authenticated user context before repository
  access; map constraint/serialization failures to stable non-secret domain errors.
- Add a read-only importer for the current `local-workspace.json`. Validate the complete source,
  canonicalize ids and listing membership, produce a dry-run report, then import all rows in one
  transaction with an import checksum and completion marker. Never import persisted market rows.
- Add parity readers that compare JSON and PostgreSQL projections during migration without serving
  responses from PostgreSQL yet. A mismatch blocks cutover with field-level redacted diagnostics.
- Ensure credentials are imported only through decrypt-and-re-encrypt migration with the current
  external KEK. Refuse missing/legacy wrap metadata rather than copying unverifiable ciphertext.
- Add repository contract suites reusable by in-memory test doubles and PostgreSQL adapters. Do not
  add job/outbox or shared-catalog repositories, switch production dependency injection, or delete
  the JSON adapter in this PR. PR159 extends import/repositories for durable jobs.

Acceptance:

- Repository contract tests produce identical normalized domain results for the test double and a
  real PostgreSQL database across create/read/update/soft-delete/list/idempotency/concurrency cases.
- Importing a two-project fixture preserves user, credential metadata, current project, project
  history, exact full listing members, settings, analyses, and artifact references; job summaries,
  quote rows, and analytical payloads are explicitly deferred/absent from imported PostgreSQL rows.
- Dry-run changes no database row. Repeating a successful import with the same checksum changes no
  row. A changed source after completion fails closed and requires an explicit operator procedure.
- An invalid source, duplicate member, cross-project run reference, credential migration failure,
  or injected transaction failure leaves the destination exactly unchanged.
- Restart and connection-pool tests prove transaction-local user context cannot leak between users,
  failed requests roll back, and serialization retries do not duplicate events or analyses.

Security: SQL is parameterized, user context is transaction-local, errors redact values, importer
reports contain no ciphertext/plaintext, and parity diagnostics reveal no other-user membership.

Determinism: Canonical projection order, import checksum, id mapping, repository result order, and
error codes are fixed by contract.

Idempotency: Every write accepts or derives a stable command key; transaction retries and repeated
imports return the existing logical result.

### PR159. PostgreSQL Durable Jobs, Outbox, And Worker Claims

Branch: `feat/postgres-durable-job-queue`.

Git status: merged.

PR: https://github.com/SergejSchweizer/portfell/pull/288.

Priority: P0 reliable asynchronous execution foundation.

Depends on: PR158.

Scope:

- Add PostgreSQL `jobs`, `job_attempts`, and `outbox_events` migrations and repositories. A job stores
  kind, immutable input hash/reference, status, priority, progress units, attempt count, available
  time, lease owner/expiry, heartbeat, timestamps, and redacted terminal code; it stores no payload.
- Use PostgreSQL as the only initial queue. API transactions atomically persist domain state, one job,
  and one outbox event. Workers claim bounded batches with `FOR UPDATE SKIP LOCKED`, commit the claim,
  execute outside the transaction, checkpoint progress, and complete with compare-and-set ownership.
- Define the exhaustive state machine `queued -> running -> succeeded|partial|failed|cancelled` plus
  lease-expiry recovery. Terminal jobs cannot return to running; retry creates an attempt on the same
  logical job, not a second job.
- Define queue limits, per-kind concurrency, fairness order, backpressure (`429 queue_capacity`),
  graceful shutdown, heartbeat cadence, lease duration, retry/backoff policy, and poison-job handling.
- Add worker health/readiness metrics for queue depth/age, claims, retries, lease expiry, duration,
  failures, and stalled jobs. Do not add provider, shared-storage, or analytical work in this PR.
- Extend the PR158 importer for legacy job summaries with deterministic job ids and attempts. Import
  no provider or analytical payload; invalid job lineage blocks the transaction.

Acceptance:

- One API command and its job/outbox row commit atomically; injected failures before/after each write
  leave either all or none. Outbox delivery is at-least-once and consumers deduplicate by event id.
- Two workers and two API replicas claim every queued job exactly once at a time. A killed worker's
  lease expires, another worker resumes from persisted progress, and the stale owner cannot complete.
- Queue capacity, ordering, per-kind concurrency, retry/backoff, cancellation, graceful shutdown,
  heartbeat loss, poison jobs, and terminal transition rejection return stable tested outcomes.
- Restarting PostgreSQL clients, API, or workers loses no committed job and creates no duplicate
  logical job. Connection-pool tests prove no transaction/user context leaks between claims.
- Architecture tests prove there is no Redis/Celery/in-process production queue and job rows contain
  no provider payload, market row, analytical result, plaintext credential, or storage key.

Security: API users can read only their project-scoped job projection; only worker roles claim/update
jobs. Claims reveal opaque input refs, not credentials, storage locations, or other-user metadata.

Determinism: Logical job id, priority order, state transitions, progress units, retry schedule, and
lease rules are versioned and independent of process order except for documented claim timestamps.

Idempotency: A unique `(job_kind, input_hash)` constraint and compare-and-set lease token make API
retries, outbox redelivery, worker redelivery, and completion retries converge on one logical job.

### PR160. Immutable Shared Market Revisions And Dataset Delta Planner

Branch: `feat/shared-market-revision-delta`.

Git status: merged.

PR: https://github.com/SergejSchweizer/portfell/pull/290.

Priority: P0 shared market-data correctness.

Depends on: PR159.

Scope:

- Introduce a minimal `SharedObjectStore` port with the existing POSIX shared volume as the first
  adapter and immutable object semantics compatible with later object storage. Keep keys opaque to
  tenant services and persist trusted revision/catalog metadata in PostgreSQL.
- Publish immutable quote, dividend, and split revision objects per canonical listing and dataset.
  Stage, checksum, validate, fsync/promote, then transactionally mark the new revision current. Never
  overwrite an object referenced by an analysis; readers pin one explicit revision id.
- Build one delta planner that compares requested selection coverage with existing canonical
  coverage independently for quotes, dividends, and splits. Plan missing history, internal gaps,
  the tail, and a bounded provider-correction overlap; never plan full history when coverage proves
  it is unnecessary.
- Represent each fetch window as a PR159 logical job keyed by
  `(provider,dataset,listing,target_date,policy_version,window)`. Concurrent planners join that job;
  only its current worker lease may publish, and waiters consume its committed revision.
- Make catalog reconciliation bidirectional: detect catalog rows without readable objects, orphan
  staged/final objects, checksum mismatch, and stale leases. Repair only through explicit operations
  commands with dry-run output.
- Retain unused market objects. GC policy is out of scope until retention and provider terms define
  a minimum age and prove no artifact dependency references the revision.

Acceptance:

- A selection with one fully covered, one partially covered, and one new listing produces exact
  per-dataset windows: no request for covered immutable history, gap/overlap/tail only for partial
  coverage, and one full backfill for the new listing.
- Two users creating overlapping projects concurrently cause one provider request per unique
  lease/window and receive the same published content revision; non-overlapping listings proceed in
  parallel.
- Replaying identical or overlapping provider rows yields one canonical business row in the next
  immutable revision. A correction creates a new revision while the previous revision remains
  readable for pinned analyses.
- Tests inject worker death before upload, after upload, before catalog commit, and after commit;
  retries converge, waiters unblock or retry, and readers see only the previous or next valid
  revision.
- Scale tests with at least 10,000 projects and 100,000 repeated memberships prove planning, job
  count, provider work, and catalog rows scale with unique listing/dataset gaps, not project count.
- Architecture tests prove shared payload schemas contain no tenant fields and tenant API code cannot
  enumerate storage keys or bypass the catalog reader.

Security: Storage credentials are worker-only, object keys are not browser-visible, staged objects
are unreadable, and catalogs/logs contain no provider key or tenant membership.

Determinism: Business keys, canonical sorting, coverage, overlap policy, delta windows, content
hashes, leases, and publication identity are versioned and independent of worker order.

Idempotency: Equal plans join one logical job; repeated download, validation, publication, and
reconcile operations converge on one immutable revision per content identity.

### PR161. Exact-Selection One-Time Project Data Bootstrap

Branch: `feat/project-selection-bootstrap`.

Git status: merged.

PR: https://github.com/SergejSchweizer/portfell/pull/292.

Priority: P0 project onboarding behavior.

Depends on: PR160.

Scope:

- Add a bootstrap application service that accepts only an owned immutable project. It resolves the
  operations credential inside the worker, calls PR160 planning, joins PR159 jobs, and records one
  parent `project_initial_fill` job in PostgreSQL.
- Freeze the exact de-duplicated full listing members produced by that project's Metadata Builder
  selection. The initial fill must plan only those members: it must not use all metadata rows, a
  name/filter query rerun, another project, or PR165's active-project union. For example, if
  `xetrac_ucits_etf_etf_eur` persists 1,753 selected ISIN/listing members, the bootstrap input and
  progress denominator are exactly those 1,753 members.
- Define exactly one bootstrap job per project. The Metadata Builder action may enqueue it once and
  thereafter only read/resume/retry that same job; it cannot create another generation or request
  arbitrary listings, dates, datasets, concurrency, credentials, or storage paths.
- Treat existing shared coverage as successful work. A fully covered new project completes without
  a provider request; partial coverage downloads only the delta for quotes, dividends, and splits.
- Persist exact child-job ids, planned windows, shared revision ids, counts, progress, timestamps,
  and redacted failures as control metadata. Do not persist payloads or copied rows in job/project
  state.
- Separate project creation from asynchronous fill execution. A valid project and selection commit
  atomically before enqueue; provider failure leaves a retryable failed bootstrap for that same
  generation and never rolls back or duplicates the project.
- Expose typed start/status contracts and workflow states `not_started`, `planning`, `running`,
  `ready`, `partial`, and `failed`. ETA is derived from persisted progress. Preserve the current
  `Download Historical Data` panel after Metadata Builder only.

Acceptance:

- Creating a project stores the project and exact relational members before any provider call. One
  action starts one job; double-click, reload, API restart, and concurrent identical requests return
  the same job and do not duplicate provider requests.
- A fixture with 1,753 selected members, additional unselected metadata rows, and overlapping members
  in another project plans exactly the 1,753 selected members. It makes no request for an unselected
  row, does not expand to the active-project union, and reports `selected_listing_count=1753`.
- A fully covered selection reaches `ready` with zero provider calls. A mixed selection requests only
  PR159 deltas. Completion requires complete quote, dividend, and split coverage for every member at
  the job target date/policy.
- Missing/revoked operations credential, provider throttling, partial dataset failure, worker
  restart, and lease contention produce stable states. Retrying resumes the same job and preserves
  completed shared publications. User credential state has no effect.
- A user cannot bootstrap another user's project, broaden membership, select a credential, create a
  second bootstrap job, or infer which project supplied existing shared coverage.
- Browser tests cover no project, ready-from-cache, running with ETA, partial/failure with retry,
  completion, project switch, reload restoration, and exact panel placement after Metadata Builder.
- Audit tests record requested, started, resumed, completed, and failed events without credential,
  provider payload, storage key, or global inventory detail.

Security: Only the worker role unwraps the operations credential. API authorization uses PostgreSQL
project ownership and immutable selection membership; cache hits reveal only project readiness.

Determinism: Bootstrap id, request hash, target date, plan, progress denominator, state mapping, and
ETA inputs are persisted and policy-versioned.

Idempotency: One `project_id` has one logical bootstrap job. Requests, outbox redelivery, worker
retries, and restarts join or resume it.

### PR162. Shared Univariate Artifact Cutover

Branch: `feat/shared-univariate-artifacts`.

Git status: merged.

PR: https://github.com/SergejSchweizer/portfell/pull/294.

Priority: P0 first analytical payload migration.

Depends on: PR161.

Scope:

- Define one immutable tenant-neutral Univariate artifact identity per canonical listing, exact
  market revision set, calendar, parameters, schema, and algorithm version. Store payloads and a
  checksum manifest in shared storage; store global catalog/dependencies and tenant run references
  in PostgreSQL.
- Route hosted Univariate compute/read paths through an owned project, pinned input revisions, PR159
  jobs, and atomic shared publication. Remove hosted project-specific Univariate payload writes only;
  leave Bivariate and Multivariate behavior unchanged.
- Preserve negative/unavailable outcomes as typed artifacts. New market revisions create new
  identities; old runs retain exact dependencies. Browser contracts expose results, never keys.

Acceptance:

- Two projects sharing a listing and exact policy execute once, use one physical payload, and obtain
  separate authorized references; changed input/policy creates a distinct artifact.
- Worker failure at each stage leaves no readable partial. Missing/corrupt/checksum-mismatched
  artifacts fail typed and never fall back to `latest` or another project.
- PostgreSQL contains no Univariate values and shared payloads contain no tenant fields. Deleting one
  project removes its reference without affecting another project or the shared payload.
- Existing Univariate numerical, API, frontend, accessibility, restart, and two-user isolation tests
  remain green; Bivariate and Multivariate regression fixtures are unchanged.

Security: Authorization precedes catalog lookup; only owned run references resolve payloads, and
responses do not reveal cache membership, dependencies, or storage locations.

Determinism: Canonical inputs, ordering, policy versions, and dependency hashes fully determine the
artifact id and byte ordering.

Idempotency: Equal requests and job retries reuse one artifact and at most one reference per run.

### PR163. Bucketed Shared Bivariate Artifact Cutover

Branch: `feat/shared-bivariate-artifacts`.

Git status: merged.

PR: https://github.com/SergejSchweizer/portfell/pull/295.

Priority: P0 scalable pairwise payload migration.

Depends on: PR162.

Scope:

- Define a Bivariate run identity from sorted exact universe, pinned Univariate/input revisions,
  common-calendar policy, parameters, schema, and algorithm version. Publish one top-level manifest
  referencing deterministic bucketed Parquet objects; do not create one PostgreSQL row/object per
  pair.
- Define stable pair ordering, bucket partition/hash scheme, row schema, checksums, dependency
  closure, partial/unavailable pair representation, and atomic manifest publication.
- Route hosted Bivariate compute/read paths through owned run references and bounded PR159 jobs.
  Enforce explicit maximum universe, pair count, memory, object size, and execution-time budgets.
  Remove hosted project-specific Bivariate payload writes only.

Acceptance:

- Exact equal runs share one manifest and buckets; changed universe/calendar/input/policy produces a
  new identity. Results are invariant to input order and every unordered pair occurs exactly once.
- PostgreSQL catalog/reference growth is $O(runs)$, not $O(pairs)$; a maximum-size fixture meets
  documented memory/time/object/count budgets and overload fails before enqueueing computation.
- Bucket/worker failure, missing bucket, checksum mismatch, incomplete dependency closure, and
  unavailable pairs return typed outcomes without publishing a partial top-level manifest.
- Existing pairwise scale guards, covariance/statistical invariants, API/frontend, restart, and
  cross-user isolation tests remain green; Multivariate behavior is unchanged.

Security: Only an owned Bivariate run can resolve its manifest; bucket keys and global pair/cache
membership never enter browser contracts or tenant authorization decisions.

Determinism: Sorted universe, pair order, bucket function, dependencies, parameters, and versions
fully determine manifest identity and payload bytes.

Idempotency: Equal runs and retries join one logical job and publish one manifest/bucket set.

### PR164. Shared Multivariate Artifact Cutover

Branch: `feat/shared-multivariate-artifacts`.

Git status: merged.

PR: https://github.com/SergejSchweizer/portfell/pull/282.

Priority: P0 complete analytical payload migration.

Depends on: PR163.

Scope:

- Define one Multivariate identity from exact sorted universe, pinned Uni/Bi manifests, settings,
  estimator, risk model, constraints, solver, schema, and algorithm versions. Publish an immutable
  top-level manifest with bounded payload objects and complete dependency closure.
- Route hosted Multivariate compute/read paths through owned run references and PR159 jobs. Reuse
  only exact identities; never share outputs across changed universes, constraints, or settings.
- Remove hosted project-specific Multivariate payload writes and unrestricted lake scans. Persist
  only run state, settings, input snapshot, progress, diagnostics, and artifact references in
  PostgreSQL. Update API/TypeScript/page restoration contracts without browser financial logic.

Acceptance:

- Exact equal requests across projects execute once and reuse one payload; every change to universe,
  dependency, model, constraint, solver, parameter, schema, or algorithm produces a distinct id.
- Old runs remain reproducible after market corrections. New runs pin one internally consistent
  revision closure and cannot mix old and new Uni/Bi dependencies.
- Minimum-CVaR, HRP, covariance, missing-data fail-closed, recommendation, trading-handoff, and
  solver-boundary fixtures retain their numerical invariants and diagnostics.
- After completion PostgreSQL contains no Uni/Bi/Multi values; shared analytical payloads contain no
  tenant fields. Four-stage API/frontend/Playwright and multi-replica restart tests pass.

Security: Authorization occurs before reference resolution; workers receive scoped content ids and
no user credentials, tenant repositories, or browser-visible storage locations.

Determinism: Exact dependency closure, canonical universe/settings, solver policy, and versions fully
determine the artifact identity and ordered output.

Idempotency: Repeated starts/status calls, redelivery, and restart reuse one run and exact artifact.

### PR165. Cron-Only Ongoing Refresh And User Update Closure

Branch: `fix/cron-only-market-updates`.

Git status: merged.

PR: https://github.com/SergejSchweizer/portfell/pull/283.

Priority: P0 enforce market lifecycle ownership.

Depends on: PR164.

Scope:

- Snapshot the PostgreSQL union of canonical members from non-deleted projects and enqueue PR160
  quote/dividend/split deltas through PR159. Bootstrap and cron share job identities, leases, and the
  same operations credential; cron is the sole creator of later refresh jobs.
- Close every user update path after project bootstrap. Repeated Metadata Builder actions return the
  existing bootstrap status; Uni/Bi/Multi pages cannot request market refresh.
- Expose only project-scoped freshness and update cron scheduling, overlap rules, credential
  rotation, runbooks, metrics, alerts, and recovery. Project changes during a run affect the next
  inventory snapshot only.

Acceptance:

- Browser/API attempts after bootstrap make zero provider calls; only the cron role can create a
  refresh job. Revoking all user credentials does not affect refresh; missing operations credential
  fails before planning/provider access.
- Overlapping projects and concurrent bootstrap/cron produce one job/request per unique gap. No-op,
  tail, internal-gap, correction, partial failure, restart, and credential rotation are tested.
- A 10,000-project fixture proves inventory, planning, requests, and writes scale with unique active
  listings/gaps. Status cannot reveal global customer, project, listing, or cache counts.
- Repository/UI/API searches prove there is one bootstrap action and no later user update action.

Security: Operations credentials are worker-only; user roles cannot enqueue refresh, and status
contains no credential, key, global inventory, or cross-project information.

Determinism: Inventory snapshot, target date, policies, plans, job ids, and next-run calculation are
persisted and versioned.

Idempotency: Repeated cron starts join one job; retries converge on immutable canonical revisions.

### PR166. Operations Readiness, Recovery, And Cutover Rehearsal

Branch: `chore/hosted-cutover-rehearsal`.

Git status: merged.

PR: https://github.com/SergejSchweizer/portfell/pull/296.

Priority: P0 prove production readiness before switching authority.

Depends on: PR165.

Scope:

- Add fail-closed readiness checks for migration head, roles/RLS, external KEK, operations credential,
  shared-store atomic capability, queue/workers, cron freshness, catalog reconciliation, and signed
  PR156 licensing evidence.
- Implement checksummed PostgreSQL/shared-storage backup manifests, restore/reconciliation tooling,
  retention/crypto-shredding jobs, SLOs, dashboards, alerts, and disaster-recovery runbooks. Shared
  payload GC remains disabled without reference/minimum-age proof.
- Rehearse PR158 import, quiesce, parity, dependency switch, smoke checks, and rollback on a
  production-like copy. Record literal commands, owners, timing budgets, commit points, and evidence.
  Do not switch the active runtime or remove legacy paths in this PR.

Acceptance:

- A fixture with two users, active/deleted projects, overlapping selections, jobs, four-stage runs,
  and shared artifacts imports with exact counts, hashes, histories, and authorized references.
- PostgreSQL-only loss, shared-storage-only loss, worker loss, corrupt manifest, stale backup, and
  mismatched publication boundary are detected and recovered/fail closed as documented.
- Multi-replica/10,000-project load tests meet explicit API latency, queue age/depth, connection,
  memory, lease, object-count, and recovery-time/recovery-point budgets.
- Two successful rehearsal cycles prove forward switch and rollback are repeatable; evidence records
  licensing, secret scan, RLS/adversarial tests, backup restore, reconciliation, and operator signoff.

Security: Rehearsal uses sanitized production-like data, encrypted backups, least-privilege roles,
audited secret access, and no browser/storage-key exposure.

Determinism: Import/parity, backup, reconciliation, readiness, and rehearsal evidence are checksummed
against exact code, schema, data boundary, and policy versions.

Idempotency: Backup, restore, import, reconcile, readiness, retention, rehearsal, and rollback are
repeatable and stop before documented commit points on mismatch.

### PR167. Hosted Repository Injection Baseline

Branch: `refactor/hosted-quote-credential-vault`.

Git status: merged. The final hosted runtime cutover merged through PR #326; production authority
remains blocked by the required production-like import, parity, backup/restore, and rollback
rehearsal.

PR: https://github.com/SergejSchweizer/portfell/pull/325.

Depends on implementation branch: `refactor/hosted-research-selection-repository` (PR #320).

Final implementation PR: https://github.com/SergejSchweizer/portfell/pull/326.

Prior planning PR: https://github.com/SergejSchweizer/portfell/pull/300 (merged).

Priority: P0 establish injected persistence boundaries.

Depends on: PR166.

Scope:

- Inject existing project, selection, credential-vault, audit-event, terminal-download, and quote
  credential ports into their owning services; retain explicit local adapters only for local mode.
- Keep `PORTFELL_HOSTED_AUTHORITY=postgres` fail-closed until every later durable port is wired.
- Record the greenfield reset decision: do not import or preserve legacy workspace, credential, run,
  or market data.

Acceptance:

- Each injected service accepts an independently supplied port in tests without using the equivalent
  `HostedApiState` authority; local behavior remains covered.
- PostgreSQL runtime remains unavailable rather than falling back to local state.

Security: Injected credentials and audit events expose no plaintext, and no hosted code silently
falls back from a supplied durable port to local state.

Determinism: UUIDs, request hashes, and local adapter behavior remain stable across injected ports.

Idempotency: Existing command idempotency remains unchanged when a service receives a durable port.

### PR168. Durable Metadata Lifecycle And Request Idempotency

Branch: `feat/hosted-metadata-lifecycle-repository`.

Git status: planned. PR: TBD.

Priority: P0 durable control-plane commands.

Depends on: PR167.

Scope: Add PostgreSQL migrations and repositories for metadata-fetch lifecycle, metadata revision
pointers, and request idempotency. Replace `metadata_runs_by_id`, `metadata_revisions_by_user`, and
hosted command idempotency dictionaries with transactional, user-scoped records; retain local adapters
only in local mode.

Acceptance: Restarting the hosted process preserves running/succeeded/failed metadata status, progress,
revision identity, and idempotent responses. Cross-user reads and replay with conflicting payloads fail
closed under RLS. No hosted route reads or writes the corresponding state dictionaries.

Security: Bind every command to transaction-local user identity; idempotency rows contain no secrets.

Determinism: Request hashes, terminal codes, revision IDs, and progress transitions are versioned and
stable for identical input.

Idempotency: Concurrent equivalent requests produce one lifecycle row and one response identity.

### PR169. Durable Quote Jobs And Shared Market Publication

Branch: `feat/hosted-quote-job-publication`.

Git status: planned. PR: TBD.

Priority: P0 durable ingestion execution.

Depends on: PR168.

Scope: Replace quote-run/progress dictionaries with PostgreSQL jobs, attempts, leases, and terminal
records. Publish quote, dividend, and split bytes through the shared market store with immutable
manifests and coverage revisions; persist only tenant references and lifecycle state in PostgreSQL.

Acceptance: Worker restart resumes or safely reclaims a lease; progress and terminal status survive API
restart; duplicate job requests single-flight by input hash; payload bytes contain no user/project field.
Quote status authorizes through the owned project/selection before reading its control-plane record.

Security: Browser input cannot select worker credentials, storage URIs, lease tokens, or shared roots.

Determinism: Publication uses canonical listing identity, schema version, content hash, and atomic
manifest swap.

Idempotency: Replayed enqueue, claim, completion, and publication operations never duplicate business
keys or expose a partial manifest.

### PR170. Shared Coverage Catalog And Project Bootstrap

Branch: `feat/hosted-shared-coverage-bootstrap`.

Git status: planned. PR: TBD.

Priority: P0 greenfield market bootstrap.

Depends on: PR169.

Scope: Implement a PostgreSQL coverage/catalog reference port and one resumable exact-selection
bootstrap job using the operations credential. Remove per-user market grants, snapshots, copied rows,
and terminal browser download semantics from hosted mode; preserve only local adapters for CLI/dev.

Acceptance: A fresh project completes with zero provider calls when coverage is current, otherwise queues
one operations-owned delta job. Two projects with overlapping listings reuse shared revisions without
cross-project membership disclosure. Deleted projects do not delete shared payloads.

Security: Only the trusted worker reads the operations credential; project authorization precedes every
catalog or shared-store lookup.

Determinism: Coverage is computed from exact canonical selections and revision manifests.

Idempotency: Repeating project bootstrap reuses the same active job or confirmed coverage result.

### PR171. Durable Research Run References

Branch: `feat/hosted-research-run-repository`.

Git status: planned. PR: TBD.

Priority: P0 durable analytical control plane.

Depends on: PR170.

Scope: Persist univariate, bivariate, multivariate, analysis, selection-settings, and project-to-artifact
references in PostgreSQL. Replace hosted research dictionaries and local persistence with repositories;
store only hashes, statuses, input revision references, and artifact references in PostgreSQL.

Acceptance: All research stages survive restart and reject guessed, deleted, stale, or cross-user IDs.
PostgreSQL growth is reference-proportional, not payload- or pair-proportional. Local CLI tests continue
through explicit local repositories.

Security: RLS covers every run/reference query and mutation; payload locations are never client input.

Determinism: Run identity derives from selection revision, market revisions, settings, and algorithm
version.

Idempotency: Equivalent submitted calculations share one run/reference identity per authorized scope.

### PR172. Shared Analytical Artifact Store

Branch: `feat/hosted-shared-analytical-artifacts`.

Git status: planned. PR: TBD.

Priority: P0 tenant-neutral analytical payloads.

Depends on: PR171.

Scope: Move Uni/Bi/Multi payloads, manifests, and result sections from hosted state to content-addressed
shared storage. Add integrity-checked artifact adapters and enforce PostgreSQL-only project visibility
references; remove hosted project-specific analytical payload copies.

Acceptance: Equal exact inputs reuse one shared artifact; payloads contain no tenant fields; corrupt or
missing manifests fail closed; an authorized run can be reproduced after restart and market correction.

Security: Artifact IDs or storage paths never grant access without PostgreSQL authorization.

Determinism: Artifact identity includes exact input manifests, algorithm and schema versions.

Idempotency: Concurrent publication of equal artifacts yields one verified immutable manifest.

### PR173. Operations Refresh And Greenfield Runtime Bootstrap

Branch: `feat/hosted-operations-bootstrap`.

Git status: planned. PR: TBD.

Priority: P0 production-owned ingestion.

Depends on: PR172.

Scope: Wire the operations credential, one initial empty shared-store bootstrap, and cron-only refresh to
the durable catalog/job pipeline. Remove hosted user-triggered provider ingestion and legacy workspace
mounts from Compose; keep local refresh commands explicitly local.

Acceptance: A fresh empty deployment bootstraps deterministically, cron refreshes the unique active
listing union, and browser/API operations cannot trigger a provider call. Missing operations secrets or
coverage manifests fail readiness without fallback.

Security: Operations credentials are mounted only into authorized worker/cron services and never logs,
API responses, or process arguments.

Determinism: Cron input union, window planning, manifests, and freshness status are versioned.

Idempotency: Repeated bootstrap and overlapping cron attempts single-flight and preserve the last valid
shared publication.

### PR174. PostgreSQL Hosted Runtime Composition

Branch: `feat/hosted-postgres-runtime-composition`.

Git status: planned. PR: TBD.

Priority: P0 authority switch implementation.

Depends on: PR173.

Scope: Compose all durable repositories, shared stores, worker boundaries, and hosted authentication in
`create_runtime_app`; enable explicit PostgreSQL authority only when every dependency is configured.
Prevent local adapters, local workspace JSON, and in-memory authority from loading in hosted mode.

Acceptance: `PORTFELL_HOSTED_AUTHORITY=postgres` starts against a fresh migrated catalog and shared
store, repeated restarts retain all hosted state, and missing dependencies fail closed. Local authority
continues to start only its explicit local composition.

Security: Connection/password/KEK/operations secret handling remains file-mounted and redacted.

Determinism: Composition chooses exactly one authority from explicit configuration.

Idempotency: Repeated startup performs no migration, bootstrap, or data mutation outside its explicit
operator command.

### PR175. Greenfield Cutover Evidence And Legacy Authority Removal

Branch: `feat/hosted-greenfield-cutover-evidence`.

Git status: planned. PR: TBD.

Priority: P0 final D017 launch gate.

Depends on: PR174.

Scope: Remove hosted legacy authority paths and prove the greenfield runtime through migrated-catalog,
RLS/adversarial, backup/restore, restart, shared-store integrity, and post-deploy smoke evidence.
Update Compose, runbooks, readiness, observability, API manifests, and architecture docs.

Acceptance: Searches and architecture tests prove one PostgreSQL tenant plane and one shared payload
plane; strict readiness and backup/restore pass; no hosted code reads/writes local workspace or legacy
state dictionaries; local CLI remains explicit and green.

Security: Include forced-RLS, guessed-ID, stale-session, worker-token, secret-scan, and deletion tests.

Determinism: Evidence records exact code, schema, catalog, and shared-manifest versions.

Idempotency: Repeating readiness, smoke, restore, and reconciliation checks is non-mutating or creates
only declared immutable evidence.

### PR176. Dependency Baseline Update

Branch: `chore/dependency-upgrades`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/336.

Priority: P1 maintenance.

Depends on: current `main`.

Scope: Update the Python `uv` lockfile and the Web package manifest/lockfile to their newest compatible
releases. Keep runtime base images on their supported major lines; do not perform an in-place PostgreSQL
major upgrade as part of dependency resolution.

Acceptance: `uv lock --upgrade --dry-run` and `npm outdated` report no resolvable package updates. The
full Python quality gate, clean Web install, TypeScript check, production build, and Web coverage suite pass.

Security: Preserve lockfile integrity and run the existing dependency/security gates; no package update
introduces credentials, mutable package sources, or unpinned application dependencies.

Determinism: Python and Web lockfiles fully determine the installed dependency graphs for the supported
Python and Node runtimes.

Idempotency: Re-resolving an unchanged manifest produces no lockfile changes.

### PR177. Node 26 Runtime Update

Branch: `chore/node-26-runtime`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/337.

Priority: P1 maintenance.

Depends on: PR176.

Scope: Update the Web production Dockerfile and the Web unit-quality containers in both quality workflows
from Node 24 to Node 26 Alpine. Keep the runtime version consistent across build, runtime, PR, and merge
quality environments.

Acceptance: A clean Node 26 install completes the Web TypeScript check, production build, and coverage
suite. The Node 26 Web Docker image builds successfully, and no controlled Dockerfile or workflow retains
a `node:24` reference.

Security: Continue using the official minimal Alpine image and preserve the existing non-root Web runtime
user and CI dependency-installation checks.

Determinism: The declared Node 26 image tag determines the Web build and runtime major version in local and
CI containers.

Idempotency: Rebuilding the unchanged Dockerfile with the same Node 26 image produces the same application
artifact contract.

### PR178. Initial-Fill Status Projection Synchronization

Branch: `fix/initial-fill-status-sync`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/338.

Priority: P1 durable worker correctness.

Depends on: PR167.

Scope: Synchronize the project-owned `project_initial_fills.status` projection with durable
`project_initial_fill` job transitions. Bind the job owner before each projection write so PostgreSQL RLS
remains enforced for claim, terminal completion, and expired-lease recovery.

Acceptance: Claim sets the projection to `running`; successful, partial, failed, and cancelled terminal jobs
map to `ready`, `partial`, and `failed`; an expired lease maps the projection back to `planning`. Existing
active rows are reconciled operationally, and the durable-job, bootstrap repository, and worker tests pass.

Security: Projection updates use the job owner's transaction-local identity and never grant a worker broad
cross-tenant access to initial-fill records.

Determinism: Each durable queue status maps to one fixed initial-fill projection status.

Idempotency: Repeating a synchronization write for the same job status leaves the same projection state.

### PR179. Batched Shared Delta Publication

Branch: `perf/shared-delta-publication`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/339.

Priority: P1 worker throughput.

Depends on: PR178.

Scope: Batch shared quote, dividend, and split coverage-catalog publication during a delta refresh. Keep
provider requests parallel and immutable revision files atomic, but read and replace the full coverage
catalogue once per bounded batch instead of once per provider response.

Acceptance: A batch of multiple listing/dataset updates reads the coverage catalogue once and publishes one
complete catalogue replacement. Existing delta overlap, fully-covered request skipping, business-key merge,
partial-failure reporting, and per-listing progress behavior remain covered by tests.

Security: Shared rows retain their tenant-neutral schema checks, and batch publication never weakens the
single refresh lock or atomic file-replacement guarantees.

Determinism: Catalogue records and immutable revision content remain sorted and identical for the same
request results independent of provider completion order.

Idempotency: Repeating the same batch leaves the active coverage content hashes unchanged.

### PR180. Quote Run Success Reuse

Branch: `fix/quote-run-success-reuse`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/340.

Priority: P1 worker efficiency.

Depends on: PR179.

Scope: Reuse an identical succeeded quote-download run when a caller submits the same project selection
without an idempotency key. Preserve a new run for changed selection membership or any nonterminal state
other than `running`.

Acceptance: A repeated identical request returns the existing succeeded run with no new worker task.
Active run reuse and idempotency-key behavior remain covered by API-service tests.

Security: Reuse remains scoped to the owned project, user, selection membership hash, and provider
credential status; no run becomes visible across tenants.

Determinism: The stable request hash resolves the same project/selection/member set to the same run id.

Idempotency: Equivalent active or succeeded requests produce no duplicate provider task.

### PR181. Initial-Fill Lease Resilience And Observability

Branch: `fix/initial-fill-observability`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/341.

Priority: P1 durable worker reliability.

Depends on: PR180.

Scope: Keep an active initial-fill lease alive during long provider waits, expose the current-attempt
start and last actual progress time through the owned status API, and make the Metadata Builder show a
stable provider-wait state when progress is stale. Standardize runtime, worker, and shared-refresh logs
to include actionable event context, exception causes, and Docker-visible output.

Acceptance: A slow provider request renews its worker lease without changing the progress timestamp;
the initial-fill status reports the current attempt rather than an earlier retry; stale progress no
longer grows the displayed remaining-time estimate; and refresh/worker failures log redacted context
with exception type and traceback.

Security: Logs never include provider tokens, database URLs, or tenant data beyond the owned operational
identifiers required to correlate an authorized job.

Determinism: Job-state projections, response fields, and status labels are determined by the persisted
job and progress timestamps, independent of browser polling cadence.

Idempotency: Lease renewal changes only its existing job lease; repeated status reads and logger setup do
not create work or duplicate log handlers.

### PR182. GitHub Actions Node 24 Runtime

Branch: `chore/checkout-node24-runtime`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/342.

Priority: P1 CI maintenance.

Depends on: PR181.

Scope: Upgrade every SHA-pinned `actions/checkout` workflow reference from v4's Node 20 action runtime
to v5's Node 24 runtime. Preserve immutable action pins, checkout inputs, and the Node 26 application
containers used by Web build and test jobs.

Acceptance: Both PR and merge workflows use only the pinned Checkout v5 commit; no Checkout v4 pin
remains; and the workflow security and governance tests pass.

Security: Workflow actions remain immutable SHA-pinned with unchanged least-privilege permissions.

Determinism: Each workflow resolves the same immutable Checkout action revision.

Idempotency: Re-running an unchanged workflow does not alter repository state beyond its existing CI
artifacts.

### PR183. Empty Market-Response Coverage

Branch: `fix/empty-market-coverage`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/343.

Priority: P1 shared-market refresh efficiency.

Depends on: PR182.

Scope: Persist the successful requested end date separately from the last observed business date for
each shared quote, dividend, and split listing/dataset record. Use that check date when planning deltas
so empty provider responses do not re-fetch full history on every run.

Acceptance: A successful empty dividend or split response is skipped for the same target date on the
next refresh; dated coverage remains backward-compatible; and rebuilding the coverage catalogue preserves
known check dates.

Security: The new marker is tenant-neutral operational metadata and never stores credentials, users,
projects, or provider request secrets.

Determinism: Identical provider results and requested end dates yield the same coverage marker and plan.

Idempotency: Repeating a refresh already checked through its target date creates no provider request or
new market revision.

### PR184. Faster EODHD Shared Refresh

Branch: `fix/market-refresh-rate-limit`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/344.

Priority: P1 shared-market refresh performance.

Depends on: PR183.

Scope: Reduce the default global EODHD request interval from 250 ms to 50 ms while preserving runtime
environment overrides and rate-limit retry behavior. Route the standalone shared refresh through the
same runtime configuration path as the hosted worker.

Acceptance: The default permits 20 request starts per second; an environment override remains effective;
and both hosted and standalone refreshes use the same runtime EODHD configuration.

Security: The change does not expose or persist provider credentials.

Determinism: Given the same configured interval, request pacing remains globally serialized and stable.

Idempotency: Retrying a provider request retains the existing retry and persistence semantics.

### PR185. Remove Default EODHD Client Pacing

Branch: `perf/remove-eodhd-pacing`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/345.

Priority: P1 shared-market refresh performance.

Depends on: PR184.

Scope: Remove the default client-side EODHD request delay so worker throughput is controlled by its
concurrency and provider response times. Retain an explicit environment override and provider-directed
`Retry-After` backoff.

Acceptance: The default request interval is zero; a positive environment override remains effective;
and `429` responses preserve the existing retry behavior.

Security: The change does not expose or persist provider credentials.

Determinism: Explicit positive pacing remains globally serialized; provider-directed retries remain
deterministic for a given response sequence.

Idempotency: Retrying a provider request retains the existing retry and persistence semantics.

### PR186. Per-Fetch Coverage Persistence

Branch: `fix/per-fetch-coverage-persistence`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/346.

Priority: P1 shared-market refresh resilience.

Depends on: PR185.

Scope: Persist shared market coverage immediately after each successful provider response rather than
waiting for a refresh batch. This preserves check dates and data already fetched when a worker is
interrupted during a larger refresh.

Acceptance: A successful fetch remains covered after an interruption before the next request completes;
failed or interrupted provider requests do not receive a check date.

Security: The change does not expose or persist provider credentials.

Determinism: Each successful provider response atomically produces the same coverage record.

Idempotency: Replaying a persisted successful fetch updates no business data beyond its existing canonical
revision and coverage marker.

### PR187. EODHD Event Business Keys

Branch: `fix/eodhd-event-business-keys`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/347.

Priority: P1 shared-market refresh resilience.

Depends on: PR186.

Scope: Accept native EODHD dividend and split fields when deriving canonical event business keys, so
successful provider responses without an event ID, `split_factor`, or `ratio` persist correctly.

Acceptance: Native EODHD dividend rows without an event ID and split rows with `split` persist through
the shared refresh; malformed rows without a required date remain rejected.

Security: The change does not expose or persist provider credentials.

Determinism: Equivalent provider event payloads derive the same canonical business key.

Idempotency: Repeating a provider response replaces the existing event under its stable business key.

### PR188. Retry Failed Initial Fill

Branch: `fix/retry-failed-initial-fill`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/348.

Priority: P1 project data-loading resilience.

Depends on: PR187.

Scope: Requeue a failed or cancelled project initial-fill job when the user resubmits the unchanged
Metadata Builder selection. Reset its progress and terminal state while preserving the project and frozen
selection; label the action as a quote-load retry.

Acceptance: Retrying a failed initial fill returns `not_started`, is claimed by the worker, and resumes
progress polling. Running, partial, and ready fills remain unchanged by duplicate submissions.

Security: Retry remains project-owned and uses no browser-held provider credential.

Determinism: A retry preserves the existing deterministic job and selection identity.

Idempotency: Duplicate submissions during active or successful fills remain no-ops; repeated failed-fill
submissions leave one queued job.

### PR189. Preserve Initial-Fill Attempt History

Branch: `fix/retry-attempt-history`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/349.

Priority: P1 project data-loading resilience.

Depends on: PR188.

Scope: Preserve durable attempt numbering when requeueing a failed initial fill, so the next worker claim
does not conflict with an existing `(job_id, attempt_number)` history record.

Acceptance: A retry resets progress and terminal state without resetting `attempt_count`; its next claim
creates the next sequential attempt record.

Security: Retry remains project-owned and uses no browser-held provider credential.

Determinism: Retries retain a stable job identity and monotonically increasing attempt numbers.

Idempotency: Repeated retries preserve one job and one unique attempt row per claim.

### PR190. Initial-Fill Failed ISIN Status

Branch: `fix/initial-fill-failure-status`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/350.

Priority: P1 project data-loading resilience.

Depends on: PR189.

Scope: Preserve Parquet-normalized shared-market revision hashes and report the unique count of failed
initial-fill ISINs in the Metadata Builder terminal status.

Acceptance: A partial or failed initial fill persists a non-negative unique failed-listing count; the
Metadata Builder status displays that count, and retrying the fill resets it to zero.

Security: The projection stores only a count, never provider credentials, error payloads, or listing IDs.

Determinism: Equivalent canonical rows retain the same revision hash after Parquet persistence.

Idempotency: Replaying a failed fill updates the same project-owned summary; a retry clears the summary
before its next worker claim.

### PR191. Commit Univariate Progress

Branch: `fix/univariate-progress-commit`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/351.

Priority: P1 research workflow reliability.

Depends on: PR190.

Scope: Commit the univariate-run start before background computation, persist listing-level progress as
it completes, and mark unexpected background-computation failures as terminal failed runs.

Acceptance: Starting Univariate Statistics returns a pollable `running` run immediately; completed
listing counts increase during the calculation, and the run reaches `complete` or `failed` rather than
remaining `running`.

Security: Detached computation uses a fresh autocommit connection with the initiating user's RLS context.

Determinism: The existing deterministic run identity remains unchanged across repeated starts.

Idempotency: Re-submitting an active run reuses its identity and can safely resume its computation.

### PR194. Bivariate Compute Lifecycle

Branch: `fix/bivariate-compute-lifecycle`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/354.

Priority: P1 research workflow reliability.

Depends on: PR193.

Scope: Commit Bivariate run creation before detached computation, persist terminal failures, and
cover the browser Compute Bivariate Statistics action through a running-to-complete lifecycle.

Acceptance: A runnable Bivariate selection returns an immediately pollable `running` run; progress
and duplicate-submit prevention remain visible until the run completes or fails; the completed
result window then loads from server-owned data.

Security: Detached computation uses a fresh autocommit connection with the initiating user's RLS context.

Determinism: Re-submitting the same selection retains its deterministic Bivariate run identity.

Idempotency: Repeated active-run starts reuse the same running run without duplicate computation.

### PR195. Sidebar Workflow Status Colors

Branch: `fix/sidebar-workflow-status-colors`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/355.

Priority: P2 workflow usability.

Depends on: PR194.

Scope: Color the server-owned Complete, Ready, and Locked sidebar workflow status labels while
retaining their visible text.

Acceptance: Complete is green, Ready is blue, and Locked is grey in both the desktop sidebar and
mobile drawer; status words remain available without color perception.

Security: The sidebar only renders existing server-owned workflow status values.

Determinism: Equivalent workflow statuses always receive the same visual treatment.

Idempotency: Refreshing or changing projects applies the same status color without mutation.

### PR196. Shared Statistics Tab Layout

Branch: `fix/statistics-tab-layout`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/356.

Priority: P2 research workflow usability.

Depends on: PR195.

Scope: Apply the responsive multi-row statistics tab layout to Bivariate and Multivariate Statistics,
matching Univariate Statistics.

Acceptance: All tabs remain visible without horizontal scrolling and retain keyboard-operable,
visually selected states across desktop, tablet, and mobile viewports.

Security: The shared layout changes no API requests, server-owned values, or workflow state.

Determinism: Each statistics page uses the same tab-layout rules for the same viewport and tab set.

Idempotency: Revisiting a completed statistics result applies the same layout without mutation.

### PR197. Bivariate Filtered Univariate Selection

Branch: `fix/bivariate-filtered-selection`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/357.

Priority: P1 research workflow correctness.

Depends on: PR196.

Scope: Apply project-persisted Univariate frequency and statistic-range filters when deriving the
current durable selection supplied to Bivariate Statistics.

Acceptance: Changing a Univariate filter persists its settings; the next workflow refresh exposes a
selection containing exactly the matching ISINs; Bivariate pair planning and computation use that
selection.

Security: Selection derivation remains user-scoped under RLS and contains no provider credentials.

Determinism: Equal completed Univariate rows and saved filters produce the same selection identity.

Idempotency: Repeating a workflow read reuses the persisted deterministic selection without changing
its members.

### PR198. Desktop-Only UI Tests

Branch: `chore/desktop-ui-tests`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/358.

Priority: P2 test execution efficiency.

Depends on: PR197.

Scope: Run the Playwright UI and real-stack browser suites only with the desktop project.

Acceptance: `npm run e2e` executes every UI scenario once using Desktop Chrome; tablet and mobile
projects are absent from the Playwright configuration and browser-test quality-gate documentation.

Security: Test fixture, browser artifact, and secret-handling boundaries are unchanged.

Determinism: The fixed desktop viewport and browser remain unchanged across local and CI runs.

Idempotency: Re-running the desktop suite creates no product-side mutations beyond its existing
isolated test fixtures.

### PR199. Bivariate Shared-Market Quote Fallback

Branch: `fix/bivariate-shared-market-quotes`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/359.

Priority: P1 research workflow reliability.

Depends on: PR198.

Scope: Let Bivariate Statistics use published Shared-Market quotes when its completed Univariate
input has no project quote-run identifier.

Acceptance: Clicking Compute Bivariate Statistics for a filtered Shared-Market Univariate selection
reaches completed pairwise results without a PostgreSQL invalid-UUID failure or terminal UI error.

Security: The fallback remains project-scoped and reads only server-published market data.

Determinism: The same selection and Shared-Market revision resolve the same Bivariate input rows.

Idempotency: Retrying a previously failed Bivariate run with unchanged inputs reuses its deterministic
run identity and completes once the Shared-Market rows are available.

### PR200. Multivariate Compute Layout

Branch: `fix/multivariate-compute-layout`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/360.

Priority: P2 research workflow usability.

Depends on: PR199.

Scope: Align the Multivariate Statistics progress bar and compute button layout with Bivariate
Statistics.

Acceptance: Multivariate renders the same labelled progress-panel structure, 8px progress bar,
status line, right-aligned primary action, and `Computing…` running label as Bivariate.

Security: The layout consumes existing server-owned run values without new client-side calculations.

Determinism: Equivalent run states render the same compute-panel structure on both statistics pages.

Idempotency: Re-rendering or revisiting a run changes no server state until the existing compute action
is selected.

### PR193. Statistics Result Completion Visibility

Branch: `fix/statistics-completion-visibility`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/353.

Priority: P1 research workflow usability.

Depends on: PR192.

Scope: Show each Univariate, Bivariate, and Multivariate statistics result window only after its
particular server-owned research run has completed.

Acceptance: Pending, running, failed, or unavailable research runs show only their progress and
compute controls; every corresponding statistics window becomes visible after its own run is complete.

Security: The browser renders only persisted run status and result artifacts; it does not infer completion.

Determinism: Equivalent persisted run statuses render the same result-window visibility state.

Idempotency: Refreshing or revisiting a completed run restores its visible result window without mutation.

### PR192. Visual Univariate Progress And Tab Layout

Branch: `fix/univariate-progress-layout`.

Git status: pushed. PR: https://github.com/SergejSchweizer/portfell/pull/352.

Priority: P1 research workflow usability.

Depends on: PR191.

Scope: Render univariate computation progress from processed listing counts and arrange all statistic
tabs in a responsive multi-row grid.

Acceptance: The progress bar visibly advances for every processed listing, including failures, and all
univariate statistic tabs are visible without horizontal scrolling at standard desktop widths.

Security: The browser renders only existing run-count values and does not expose listing-level data.

Determinism: Equivalent run totals and processed counts always render the same progress state.

Idempotency: Revisiting the page preserves the progress state returned by the current persisted run.

### PR168. Production Cron Installation And First Scheduled Run Evidence

Branch: `chore/install-production-market-refresh-cron`.

Git status: in progress. The implementation merged in PR #329; the remaining operational
acceptance is first natural `20:15 Europe/Amsterdam` scheduled-run evidence.

Implementation PR: https://github.com/SergejSchweizer/portfell/pull/329.

Priority: P0 complete the production operations rollout.

Depends on: PR167 and PR170.

Scope:

- Install the already implemented shared-market refresh cron on the production host as service user
  `dev_portfell`, using the absolute checkout `/home/dev_portfell/portfell`. Do not install against a
  feature checkout, unmerged commit, mutable image tag, local-workspace authority, or developer
  credential.
- Require the Compose `shared-market-refresh` job to mount the persistent host lake
  `/volume2/docker/portfell/lake` at `/srv/portfell/shared-data` and set
  `PORTFELL_SHARED_DATA_ROOT=/srv/portfell/shared-data`. The cron may publish quote, dividend, split,
  coverage, manifest, and shared analytical updates only through this mount and may not write a
  repository `lake`, named volume, project directory, or container-local persistent path.
- Record a preflight evidence bundle that pins the deployed Git SHA and container image digest;
  confirms PR156 licensing approval, PR167 PostgreSQL/shared-store authority, migration head, healthy
  PostgreSQL/API/workers, the dedicated operations credential, external secret-file permissions,
  shared-store write/atomic-replace capability, free disk space, and synchronized host time.
- Back up the service user's existing crontab with owner-only permissions and a SHA-256 digest before
  mutation. Provision `/volume2/docker/portfell/logs/shared-market-refresh.log`, its parent
  directory, and logrotate ownership/retention so the non-interactive service user can append logs
  without making configuration or secrets world-writable.
- From the absolute production root, run `docker compose --env-file .env.local config`, then
  `portfell-refresh-shared-market-data --dry-run`. The dry run must resolve the PostgreSQL active-
  project listing union, operations credential, durable queue, shared root, lock, and delta plan
  without making a provider request or mutating market/catalog state.
- Execute `portfell-shared-market-cron run-once --project-root /home/dev_portfell/portfell` before
  installation. Wait for the durable refresh job to reach a successful terminal state and reconcile
  its inventory hash, requested gaps, immutable revisions, coverage catalog, failures, and duplicate
  business keys against PostgreSQL and shared storage.
- Install with
  `portfell-shared-market-cron install --project-root /home/dev_portfell/portfell`, then verify
  `status` and `crontab -l`. The one managed block must use
  `SHELL=/bin/bash`, `CRON_TZ=Europe/Amsterdam`, `15 20 * * *`, `/usr/bin/flock -n`, absolute paths,
  the Compose `operations` profile, and the `shared-market-refresh` one-shot service.
- Repeat installation and prove the crontab digest is unchanged and every unrelated entry remains
  byte-identical. Verify lock contention is side-effect free and that a simultaneous manual start
  cannot create a second logical refresh job.
- Observe one natural cron-triggered execution at `20:15 Europe/Amsterdam`; a manual `run-once` does
  not satisfy this step. Verify start time, terminal success, manifest/catalog freshness, zero secret
  leakage, bounded provider requests, no duplicate revisions, project-scoped freshness, logrotate,
  status/SLO metrics, and alert recovery.
- Commit only redacted operational evidence and checksums. Document exact install, status, log,
  retry, credential-rotation, disk-full, stale-run, uninstall, crontab-restore, and application
  rollback commands with named owner and decision points.

Acceptance:

- The PR identifies one production target with service user `dev_portfell`, root
  `/home/dev_portfell/portfell`, exact merged PR167 Git SHA, exact API/worker image digest, migration
  head, and approved PR156 licensing evidence; all values match the running services before any
  crontab write.
- Preflight is green for PostgreSQL/RLS, API/workers, operations credential, external secret modes,
  shared-store atomic writes, queue claims, at least the documented minimum free disk space, NTP
  synchronization, Docker Compose configuration, log directory, and logrotate. Any failed item stops
  before changing crontab or provider/catalog state.
- The recorded dry run exits `0`, reports the exact deduplicated active-project listing count and
  inventory hash, creates no provider request/job/revision/catalog mutation, prints no credential or
  secret path content, and uses no local-workspace JSON authority.
- The pre-install `run-once` exits `0`; its durable job reaches `succeeded`; requested, succeeded,
  unchanged, and failed counts reconcile; failed count is zero; every active project member has
  quote/dividend/split coverage through the target date or a documented market-closed/not-applicable
  status; and duplicate full business-key count is zero.
- Before installation, `portfell-shared-market-cron status` reports `installed=false`. Afterwards it
  reports `installed=true`, schedule `15 20 * * *`, timezone `Europe/Amsterdam`, and fresh successful
  state; `crontab -l` contains exactly one complete managed Portfell block and no secret value.
- Installing twice yields the same complete crontab SHA-256 digest. The pre-install backup digest is
  recorded, owner-only, restorable, and all unrelated crontab bytes are identical before and after
  install.
- The rendered cron command contains only absolute paths, obtains the non-blocking flock, runs
  `docker compose --profile operations run --rm --no-deps shared-market-refresh`, writes the approved
  log, and exposes no network port or long-running second API process.
- Inspection of the one-shot container proves source `/volume2/docker/portfell/lake`, destination
  `/srv/portfell/shared-data`, and `PORTFELL_SHARED_DATA_ROOT=/srv/portfell/shared-data` agree. A
  controlled refresh changes only expected files below the host lake and creates no persistent data
  in the checkout, another host path, an anonymous/named volume, or the container writable layer.
- A lock-contention test returns the documented non-success/no-op result, starts no provider request,
  publishes no revision, and leaves the active refresh and last valid catalog readable. Repeating a
  logical target date joins/reuses one durable job.
- The first naturally scheduled run starts at the next `20:15 Europe/Amsterdam` cron window, reaches
  `succeeded` within the documented SLO, advances or confirms catalog freshness, processes only
  unique active-listing gaps, records zero duplicate business keys, and leaves all project freshness
  endpoints healthy after API/worker restart.
- Monitoring demonstrates an alert for a synthetic stale/failed status and a clear recovery after a
  successful refresh. Logs rotate with the documented owner/mode/retention and contain no EODHD key,
  KEK, database password, credential envelope, session token, or unrestricted project inventory.
- The redacted evidence bundle contains command, timestamp, exit code, Git/image/schema identities,
  crontab before/after hashes, run/job/manifest identities, reconciliation totals, first scheduled-
  run proof, monitoring proof, operator signoff, and rollback checkpoint. Repository secret scanning
  and every current gate in `GATES.md` pass.
- An operator following only the committed runbook can inspect status, retry a failed refresh, rotate
  the operations credential, recover from disk-full or stale lock, uninstall only the managed block,
  restore the exact prior crontab, and invoke the PR167 application rollback without deleting shared
  market data or PostgreSQL history.

Security: Installation uses the least-privilege production service user and dedicated operations
credential. Secrets remain in external owner-restricted files/mounts and never appear in crontab,
commands, evidence, logs, environment dumps, Git, or CI. Evidence is redacted and secret-scanned
before review.

Determinism: The target root, service user, Git SHA, image digest, migration head, Compose profile,
service name, timezone, schedule, lock, log path, installer command, readiness thresholds, and
evidence schema are explicit and versioned. The cron block does not depend on cwd, shell profile,
PATH lookup, locale, or mutable tags.

Idempotency: Preflight and dry run are non-mutating; repeated installation preserves one managed
block and unrelated crontab bytes; repeated target-date execution joins one durable refresh job and
converges on one immutable revision per content identity. Uninstall/restore can be repeated without
deleting shared payloads, tenant history, or unrelated cron entries.

### PR169. Exhaustive Button Interaction Tests And Required Merge Gates

Branch: `chore/web-button-interaction-gate`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/327.

Priority: P1 prevent untested browser interactions from merging.

Depends on: PR167. May execute in parallel with PR168.

Scope:

- Add a machine-readable Playwright interaction manifest covering every rendered native `button`,
  shared `Button`, `IconButton`, `role="button"`, and `role="tab"` in every production Portfell route
  and reachable workflow state. Each entry records route, viewport applicability, accessible name,
  setup state, expected enabled/disabled state, click action, expected API/navigation/UI effect, and
  duplicate-click behavior.
- Add an inventory guard that renders each registered route/state, discovers controls by semantic
  role and accessible name, and compares the discovered set with the manifest in both directions.
  A newly added, renamed, removed, duplicated, or inaccessible button/tab must fail until its
  interaction case and manifest entry are updated.
- Implement isolated Playwright cases using `getByRole` and deterministic `page.route` fixtures.
  Test visible/accessibility state before interaction and prove the exact API method/path and payload,
  navigation target, dialog/drawer/tab state, persisted setting, or rendered result after interaction.
  Unhandled browser API requests fail the test.
- Cover each action's applicable `ready`, `locked`, `pending`, `running`, `complete`, and `failed`
  states. Disabled controls make no request. Repeated clicks while work is active create no duplicate
  request/run. Retry after a modeled failure follows the documented idempotent behavior.
- Cover navigation/drawer controls, metadata actions, project creation/switching, all Uni/Bi/Multi
  compute actions, settings/candidate controls, tabs, icon-only controls, and responsive-only
  controls. Use `aria-label` fixes only where a control lacks a stable accessible name; do not add
  test ids or change product behavior when a semantic locator is available.
- Run every interaction scenario through the existing Playwright `desktop`, `tablet`, and `mobile`
  projects. Configure a deterministic local Web server lifecycle, fixed timezone/locale, reduced
  motion where relevant, clean state per test, and trace/screenshot/video capture only on failure.
- Add `pr-web-interactions` to `.github/workflows/pr-quality.yml` and
  `merge-web-interactions` to `.github/workflows/merge-gate.yml`. Each job installs pinned Node
  dependencies and the pinned Playwright Chromium runtime, builds/serves the Web application, runs
  the complete interaction inventory on all three viewports, uploads failure artifacts, and is a
  mandatory dependency of the stable aggregate `pr-quality` or `merge-gate` result.
- Update `GATES.md`, local quality commands, workflow/governance tests, and contributor guidance so
  the button inventory cannot be skipped by branch protection, auto-merge, direct main validation,
  or the documented local pre-push procedure.

Acceptance:

- A committed manifest entry exists for every control discovered as `button` or `tab` on Metadata
  Builder, Univariate Statistics, Bivariate Statistics, Multivariate Statistics, and the responsive
  application shell in every registered workflow state. There are zero discovered-but-unregistered
  and zero registered-but-undiscovered controls on desktop, tablet, and mobile.
- Every manifest entry has exactly one deterministic interaction test or an explicit disabled-state
  assertion. Tests locate controls by role and accessible name; no case depends on generated CSS
  classes, DOM child position, visible implementation text without a role, arbitrary sleeps, or a
  production EODHD/PostgreSQL request.
- Enabled action tests assert the exact request method, path, relevant payload, request count, and
  resulting UI state. Navigation, drawer, tab, and purely local controls assert their exact URL,
  focus/expanded/selected state, or visible content and make zero unexpected API calls.
- Locked, pending, and running controls are disabled or absent according to contract and produce
  zero side effects. Double-click or repeated-click tests prove one logical request/run for every
  submitting action. Failure/retry tests show the stable error and one idempotent retry.
- Icon-only controls have a unique non-empty accessible name. Duplicate accessible names are allowed
  only when the test scopes them to a documented semantic region; keyboard activation and focus
  visibility pass for all actionable controls.
- A mutation fixture that adds an unregistered button, removes a registered button, changes an
  accessible name, or changes a button to the wrong enabled state makes the inventory/interaction
  suite fail with a message naming route, state, role, and control name.
- `npm run typecheck`, `npm run test:coverage`, `npm run build`, and `npm run e2e` pass from
  `apps/web`; `npm run e2e` executes and passes the complete manifest on the configured `desktop`,
  `tablet`, and `mobile` projects with no retries required.
- `pr-quality.yml` contains a `pr-web-interactions` job and its aggregate fails when that job is
  failed, cancelled, or skipped. `merge-gate.yml` contains an equivalent `merge-web-interactions`
  job and its aggregate enforces the same result on the exact merged `main` commit.
- A controlled failing interaction test produces Playwright trace, screenshot, and retained video
  artifacts with documented retention; a passing run does not upload unnecessary browser artifacts.
  Fixtures and artifacts contain no credentials, tokens, real customer/project data, or unrestricted
  shared inventory.
- `GATES.md` lists both Web interaction jobs, their exact commands, browser/version pinning, artifact
  behavior, local equivalent, and required aggregate relationship. Governance tests fail if either
  workflow job, aggregate dependency, manifest guard, or documented gate is removed.
- Branch-protection evidence shows the stable required `pr-quality` check cannot succeed without all
  button interaction tests. The final PR reports button/tab counts by route and state, all commands,
  durations, results, and any deliberately non-actionable disabled controls.

Security: Browser fixtures use synthetic opaque ids and values only. No test calls Google, EODHD,
production PostgreSQL, or production shared storage. Traces, screenshots, videos, logs, and CI
artifacts are secret-scanned and cannot contain provider keys, sessions, credentials, internal paths,
or real project membership.

Determinism: Manifest order, route/state fixtures, API responses, accessible names, timezone, locale,
viewport definitions, animation policy, browser version, and expected effects are committed and
pinned. Tests use condition-based assertions rather than sleeps and pass independently of execution
order or worker scheduling.

Idempotency: Every test starts from isolated state and can be retried without retaining projects,
runs, settings, routes, or browser storage. Repeated user actions are asserted to join/reuse one
logical operation where required; CI reruns do not contact production services or mutate external
state.

### PR170. UGREEN NAS Persistent Data Root And Safe Volume Migration

Branch: `chore/ugreen-nas-persistent-data-root`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/330.

Priority: P0 establish final durable storage before cron installation.

Depends on: PR167. Must complete before PR168.

Scope:

- Introduce one explicit production host setting
  `PORTFELL_DATA_ROOT=/volume2/docker/portfell`. Keep container paths unchanged while mapping
  PostgreSQL to `${PORTFELL_DATA_ROOT}/postgres:/var/lib/postgresql/data` and the canonical shared
  lake to `${PORTFELL_DATA_ROOT}/lake:/srv/portfell/shared-data` through the production
  Compose override.
- Mount the exact same persistent-lake bind path into API, project-bootstrap worker, shared-market
  refresh, and every analytical worker that reads or publishes shared payloads. No production
  service may retain a named, anonymous, project-local, or second bind mount for the same persistent
  target.
- Define and provision `${PORTFELL_DATA_ROOT}/postgres`, `lake`, `logs`, and `backups` with
  documented owner, group, mode, ACL, capacity threshold, and backup policy. Resolve required
  container UIDs/GIDs from the pinned images instead of assuming workstation ids, and prove each
  service has only its required read/write access.
- Keep PostgreSQL password, EODHD KEK, operations token, and all other secrets outside
  `${PORTFELL_DATA_ROOT}` in owner-restricted external secret files. Do not relocate Docker's global
  engine `data-root`, container metadata, images, build cache, or sockets; this PR moves Portfell's
  durable application data only.
- Add a fail-closed migration preflight that verifies the absolute UGREEN NAS path, real directory
  resolution, filesystem type and atomic-rename support, free space/inodes, ownership/ACLs, backup
  destination, pinned image digests, migration head, healthy source stack, inactive cron, and no
  concurrent bootstrap/refresh/analysis writer.
- Quiesce API write traffic and workers at a documented checkpoint. Create a checksummed logical
  PostgreSQL backup with roles/schema/data metadata, and copy shared storage with metadata-preserving,
  checksum-verified tooling while all publishers are stopped. Never copy live PostgreSQL data files
  as a database backup.
- Initialize PostgreSQL on the new bind path, restore the logical backup, start services against the
  new paths, and reconcile schema version, tenant/project/selection/job/run/reference counts,
  credential-envelope metadata, shared file/object counts, bytes, manifests, content hashes,
  coverage catalog, and duplicate business keys before resuming writes.
- Preserve the old Docker named volumes read-only and do not run `docker compose down -v`, volume
  prune, or destructive cleanup during migration. Record a rollback checkpoint that stops the new
  stack, restores the old Compose mounts, reconciles source state, and resumes the previous stack
  without deleting either copy.
- Update `.env.example`, production Compose example, deployment/readiness checks, backup/restore and
  UGREEN NAS runbooks, PR168 cron log path, monitoring, and tests. Document NAS/Docker restart behavior,
  NAS volume unavailability, read-only filesystem, disk-full, permission drift, backup retention,
  and eventual named-volume cleanup as a separately approved destructive operation.

Acceptance:

- Rendering production Compose with `PORTFELL_DATA_ROOT=/volume2/docker/portfell` succeeds and shows
  exactly `/volume2/docker/portfell/postgres:/var/lib/postgresql/data` for PostgreSQL and
  `/volume2/docker/portfell/lake:/srv/portfell/shared-data` for every required consumer and
  publisher. No production config contains the old named volumes or a second mount at either target.
- Development Compose remains usable without a UGREEN NAS filesystem and continues to use explicit
  development volumes. Missing, relative, symlink-escaped, root-level, nonexistent, or non-writable
  production `PORTFELL_DATA_ROOT` values fail before a container starts or source data changes.
- The provisioned `postgres`, `lake`, `logs`, and `backups` directories have documented
  numeric owners/groups, restrictive modes/ACLs, sufficient free bytes/inodes, and write probes from
  only the intended container users. Web has no database, shared-data, backup, or secret mount.
- A repository and rendered-Compose scan proves no secret file resides below
  `/volume2/docker/portfell`, no secret value appears in Compose/environment output, and no container
  receives a secret it does not require.
- Migration preflight records source named-volume ids, source/target capacity, Git SHA, image
  digests, migration head, current PostgreSQL counts, shared inventory/catalog hashes, active-job
  count, and cron state. Any active writer, stale backup, failed health check, insufficient capacity,
  permission mismatch, or unsupported atomic rename stops before quiesce/copy/restore.
- The PostgreSQL backup is a successful logical dump with SHA-256 digest and restorable metadata.
  Restoring it into a clean target reproduces migration head and exact normalized counts for users,
  encrypted credential rows, projects, immutable selections/members, jobs/attempts/outbox, analysis
  runs, audit history, and artifact references without exposing credential plaintext.
- The quiesced shared-data copy preserves relative paths, file sizes, modes, and content. Source and
  target have identical file/object counts, total bytes, manifest identities, catalog entries, and
  SHA-256/content hashes; corrupt, missing, extra, partially copied, or tenant-bearing payloads fail
  reconciliation.
- After cutover, API, PostgreSQL, bootstrap worker, analytical workers, and Web become healthy;
  repeated container recreation and one Docker/DSM restart retain projects, encrypted credentials,
  job history, analyses, shared market revisions, coverage, and shared artifacts.
- A synthetic project bootstrap and a shared-market refresh write only below the two approved bind
  roots. Every market-data write lands below `/volume2/docker/portfell/lake`, survives restart,
  remains visible to the authorized project, and creates zero duplicate full business keys or
  project-specific market-data copies.
- Backup/restore tooling writes only to `/volume2/docker/portfell/backups`, verifies checksums before
  restore, applies documented retention, and completes one clean-destination restore drill for both
  PostgreSQL and shared data.
- A rollback rehearsal from the post-cutover checkpoint restores the old named-volume configuration
  and exact pre-cutover state within the documented RTO. Switching forward again is repeatable and
  produces the same reconciled identities and counts.
- Old named volumes still exist, are not mounted by the accepted production config, and are marked
  read-only/retained with ids and expiry criteria. Their deletion requires a later explicit approval
  after backup retention and rollback windows expire; this PR executes no volume deletion.
- PR168's rendered cron command and logrotate configuration use
  `/volume2/docker/portfell/logs/shared-market-refresh.log`; its one-shot refresh sees the same
  PostgreSQL and shared-data bind mounts as the long-running services.
- Compose contract tests, migration dry-run/failure-injection tests, backup/restore tests,
  reconciliation, permission/security checks, repository secret scan, Docker restart smoke test,
  and every current gate in `GATES.md` pass. The redacted evidence bundle records commands, times,
  exit codes, digests, counts, operator signoff, cutover checkpoint, and rollback result.

Security: Bind roots use least-privilege numeric ownership and restrictive ACLs. Database files,
shared payloads, backups, and logs contain no plaintext provider key, KEK, database password, session
token, or unrestricted tenant export. Secrets remain separately mounted and backups are encrypted
with recovery material stored outside the NAS data root.

Determinism: Production root, subdirectories, container targets, image digests, UID/GID resolution,
mount contracts, backup format, copy flags, reconciliation schema, cutover checkpoints, and rollback
commands are explicit and versioned. Equivalent source state produces the same normalized database
counts and shared content hashes.

Idempotency: Provisioning, Compose rendering, preflight, logical backup, quiesced copy, restore into a
clean target, reconciliation, restart, and forward/rollback rehearsal are repeatable. Retries never
delete source volumes, overwrite an unverified backup, duplicate database rows/shared payloads, or
mount two writable authorities at once.

### PostgreSQL Tenant Plane And Shared Data Series Completion Gate

This series is complete only after PR156 through PR167 merge in order, PR170 completes before PR168,
PR168 and PR169 complete, and the current gates in [GATES.md](GATES.md) pass. One production-like
evidence bundle must prove:

- all user metadata, encrypted credential envelopes, immutable projects with exactly one canonical
  member per unique ISIN, jobs/outbox/attempts, runs, audit, and top-level artifact references are
  durable in PostgreSQL and isolated by forced RLS;
- immutable quote/dividend/split revisions and Uni/Bi/Multi manifests/payloads exist only in shared
  storage, contain no tenant fields, and are reused only for exact identities; Bivariate payloads are
  bucketed and PostgreSQL growth is not pair-proportional;
- project creation permits one resumable exact-selection bootstrap through PostgreSQL jobs and the
  operations credential, including zero-provider-call completion; users trigger no later refresh;
- cron uses the same operations credential and applies gap/tail/correction deltas to the unique
  active-listing union through the same durable single-flight jobs;
- the production service user's managed cron block is installed idempotently at
  `20:15 Europe/Amsterdam`, one natural scheduled run succeeds, monitoring/rotation are live, and exact
  uninstall/crontab-restore/application-rollback evidence is approved;
- every production button and tab has a semantic interaction case on desktop, tablet, and mobile;
  the inventory guard and Playwright interaction jobs are mandatory dependencies of both stable
  merge-quality aggregates;
- production PostgreSQL, shared payloads, logs, and backups use the approved
  `/volume2/docker/portfell` bind roots with verified permissions, checksums, restart persistence,
  backup/restore, and a rehearsed non-destructive rollback; secrets remain outside that tree;
- project deletion and user credential deletion preserve shared payloads and other projects, while
  tenant history and crypto-shredding follow explicit retention policy;
- old analysis runs remain reproducible from pinned immutable revisions after market corrections;
- licensing approval, fresh catalog/shared-store bootstrap, multi-replica load, adversarial
  isolation, backup/restore, and post-launch smoke/observability evidence are complete before PR167
  switches authority; legacy data migration, parity, and rollback are intentionally out of scope;
- local CLI mode remains supported through explicit local adapters and cannot be confused with the
  hosted PostgreSQL/shared-storage runtime.

## Active Monthly-Distribution ETF Multivariate PR Stack

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

### PR143. Monthly-Distribution ETF Multivariate Input Snapshot

Branch: `feat/multivariate-input-snapshot-contract`.

Git status: complete. Delivered by the stacked Multivariate implementation PRs #255–#265.

Priority: P0 multivariate correctness foundation.

Depends on: current `main`.

Scope:

- Add a versioned `MultivariateInputSnapshot` contract owned by the Multivariate Statistics
  module. It must pin `project_id`, user-owned project snapshot id, metadata selection id,
  univariate run id, univariate selection id, bivariate run id, full sorted listing keys
  (`isin`, `exchange`, `code`), quote and dividend artifact identities, aligned-calendar identity,
  `date_start`, `date_end`, `observation_count`, policy version, and dependency hashes.
- Add a versioned initial `MonthlyDistributionEtfPolicy`. Require `instrument_type=ETF`, persisted
  `distribution_frequency=monthly`, unique full listing keys, production-eligible quote history,
  at least two listings, and at least 504 common daily return observations. Keep every threshold
  explicit and serializable rather than embedding it in service control flow.
- Resolve the snapshot only from the active project's authorized, persisted Metadata Builder,
  Univariate Statistics, and Bivariate Statistics outputs. Require the bivariate run to be complete
  and to have exactly the same listing membership and aligned-calendar identity as the univariate
  selection used for the snapshot.
- Persist eligibility results and all rejection reasons, including stale upstream run, non-ETF,
  non-monthly distribution, duplicate listing key, missing quote or dividend artifact, missing
  bivariate dependency, membership mismatch, calendar mismatch, insufficient common history, and
  fewer than two eligible listings.
- Define downstream invalidation: a changed project snapshot, metadata selection, quote artifact,
  univariate run or selection, bivariate run, listing membership, common calendar, or policy version
  makes the Multivariate input stale. Reopening an unchanged project restores the same snapshot.
- Provide local-lake and hosted scoped-input adapters behind the same contract. The local adapter
  may resolve explicitly supplied selection/run ids; neither adapter may treat a latest/current
  pointer as authorization or provenance.
- Update schemas, path/catalog helpers, architecture rules, contract documentation, and focused
  tests for this new dormant boundary. Do not add a browser route or run portfolio mathematics.

Acceptance:

- A fixture containing monthly ETFs with at least 504 shared returns produces one eligible snapshot
  with canonically sorted full listing keys and exact upstream artifact identities.
- Non-ETF and non-monthly rows are rejected even when their names contain `ETF`, `income`, or
  `monthly`; eligibility uses typed persisted fields, not name heuristics.
- `unknown`, `accumulating`, `irregular`, quarterly, semiannual, and annual distribution categories
  do not satisfy the monthly policy.
- Tests reject fewer than two eligible listings, fewer than 504 common observations, duplicate full
  listing keys, a missing artifact, an incomplete or failed bivariate run, membership mismatch, and
  aligned-calendar mismatch with stable machine-readable reason codes.
- Two listings sharing an ISIN but differing by exchange or code remain distinct listing keys; the
  snapshot identity includes all three fields and cannot collide with an ISIN-only identity.
- A newer Metadata Builder selection cannot silently replace the older project selection pinned by
  an existing snapshot. Changing any pinned dependency produces a different snapshot id and marks
  downstream Multivariate state stale.
- Local and hosted adapters produce the same normalized snapshot for equivalent authorized inputs.
- Contract, schema, architecture, and integration tests prove that snapshot construction does not
  start quote, univariate, or bivariate work and does not scan unrestricted lake membership.

Security: Hosted snapshot resolution requires access to the project and the complete dependency
closure. Guessed selection, run, listing, calendar, or shared artifact ids cannot reveal membership
or create an authorized snapshot. Provider credentials and internal filesystem paths never appear
in snapshot payloads, logs, errors, or browser-facing contracts.

Determinism: Snapshot identity hashes canonical full listing keys, exact immutable dependency ids,
policy values, aligned-calendar identity, and contract/algorithm versions. Filesystem order, worker
completion order, locale, current pointers, and wall-clock time cannot change it.

Idempotency: Repeating snapshot creation with identical authorized dependencies returns the same
snapshot and eligibility rows. Concurrent identical requests join or reuse one logical result and
never duplicate catalog references.

### PR144. Canonical Multivariate Risk-Model Artifact And Optimizer Wiring

Branch: `fix/multivariate-canonical-risk-model`.

Git status: complete. Delivered by the stacked Multivariate implementation PRs #255–#265.

Priority: P0 numerical correctness.

Depends on: PR143.

Scope:

- Add an immutable, versioned Multivariate risk-model artifact built from the input snapshot's one
  universe-wide aligned log-return matrix. Persist estimator, return type, window policy,
  observation period, full listing order, covariance values, shrinkage intensity, eigenvalue and
  condition diagnostics, PSD status, availability reasons, and algorithm version.
- Use Ledoit-Wolf shrinkage as the initial production estimator while retaining sample covariance
  and EWMA as explicit research alternatives. Never substitute bivariate pairwise-intersection
  covariance for the joint portfolio covariance matrix.
- Convert the selected risk-model result into the typed covariance input consumed by every
  covariance-dependent optimizer, baseline, variance calculation, risk-contribution calculation,
  and comparison. Remove the current path that validates a shrinkage model but passes separately
  read sample-covariance rows to profiles.
- Make candidate evaluation single-pass. Persist and write the exact evaluated candidate rather
  than recomputing it in a writer. Remove implicit Equal Weight substitution from production
  candidate persistence; unavailable or infeasible results remain unavailable or infeasible.
- Include the risk-model artifact id, full listing keys, aligned-calendar id, estimator parameters,
  and solver/constraint versions in candidate and production-adapter identities.
- Keep the public portfolio solver boundary independent of project, user, provider, filesystem,
  and browser concerns. Add conversion helpers at the Multivariate orchestration boundary rather
  than making solvers read artifacts directly.

Acceptance:

- A hand-checkable fixture proves that Ledoit-Wolf covariance passed to HRP, ERC, Minimum Variance,
  portfolio variance, and risk contributions is the exact validated matrix, not the separately
  persisted sample covariance.
- A fixture where sample and shrinkage covariance yield materially different weights proves that
  every reported weight and risk fact follows the selected shrinkage artifact.
- Tests cover sample, Ledoit-Wolf, and EWMA selection; symmetric and PSD matrices; singular and
  ill-conditioned inputs; non-finite values; incomplete listing coverage; and deterministic listing
  ordering.
- A rejected risk model cannot produce weights, a production label, a recommendation, or a silent
  Equal Weight fallback. Requested and actual estimator/method labels always agree.
- The writer persists the already-evaluated candidate exactly once. A test fails if it invokes the
  optimizer again or changes weights between evaluation and persistence.
- Risk-model and candidate identities change when the calendar, returns, membership, estimator,
  estimator parameters, constraints, solver version, or algorithm version changes, and remain
  unchanged otherwise.
- Existing solver tolerances and supported research modes remain backward compatible through
  explicit adapters; no compatibility facade owns production mathematics.

Security: Risk-model and solver functions accept already-scoped numeric rows only. They cannot
resolve users, credentials, project membership, arbitrary artifact ids, or filesystem paths.
Hosted artifact reads remain authorized through the owning input snapshot.

Determinism: Canonical listing/date order, estimator serialization, numerical tolerances, matrix
serialization, and candidate replacement keys are versioned. Identical inputs produce identical
artifact ids and numerically equal outputs within committed tolerances.

Idempotency: Repeating or concurrently requesting an identical risk model or candidate reuses the
artifact and does not append duplicate covariance, diagnostics, weights, or risk-contribution rows.

### PR145. Multivariate Portfolio-Structure Statistics

Branch: `feat/multivariate-portfolio-structure`.

Git status: complete. Delivered by the stacked Multivariate implementation PRs #255–#265.

Priority: P1 explainable joint-system analysis.

Depends on: PR144.

Scope:

- Compute and persist structure statistics from the canonical risk-model artifact: covariance and
  correlation summaries, covariance-stability facts, hierarchical cluster membership, principal
  components, per-component explained variance, cumulative explained variance, effective rank,
  effective number of independent drivers, and component loadings by listing.
- Produce a versioned plain-language structure summary containing candidate ETF count, risk-cluster
  count, dominant-component share, number of components required to explain committed thresholds,
  effective rank, strongest common driver, and the largest redundancy warning supported by the
  available evidence.
- Keep component labels empirical and neutral (`Component 1`, `Component 2`, and so on). Do not
  infer labels such as technology, options, rates, or geography without typed exposure metadata and
  an explicit labeling policy.
- Add bounded API-ready summary and detail serializers. Dense loading matrices remain server-side;
  detail access supports deterministic component/listing pagination and top-absolute-loading views.
- Persist formulas, units, period, observation count, risk-model id, availability state, and reason
  codes with every fact family. Do not construct portfolio weights or add a browser page.

Acceptance:

- Hand-checkable diagonal, perfectly correlated, negatively correlated, and block-correlated
  fixtures prove eigenvalues, explained variance, cumulative variance, effective rank, clusters,
  and stable component sign normalization.
- Input row and listing order permutations produce the same component ids, explained-variance
  sequence, effective rank, cluster assignments, summary facts, and top-loading order.
- Component loadings use a committed sign convention so equivalent eigensolutions do not flip UI
  values between runs. Repeated eigenvalues produce a documented deterministic ordering or an
  explicit ambiguity warning.
- Tests cover one dominant driver, independent assets, near-singular covariance, insufficient
  observations, unavailable risk model, empty component detail pages, pagination boundaries, and
  no fabricated semantic factor labels.
- Every result reports the exact aligned period and observation count inherited from the input
  snapshot and references the canonical risk-model artifact.
- Large-universe serializers return bounded summaries without materializing an unrestricted dense
  matrix in a browser response.

Security: Structure endpoints and serializers require authorization to the owning project run and
risk-model dependency closure. Counts, components, loadings, cluster membership, and errors cannot
reveal inaccessible listings or artifacts.

Determinism: Eigenvalue ordering, eigenvector sign normalization, cluster distance/linkage policy,
tie breaking, threshold serialization, precision, pagination, and fact ordering are versioned.

Idempotency: Identical input-snapshot, risk-model, and structure-policy identities reuse the same
statistics artifacts. Partial retries write only missing partitions and cannot duplicate component,
loading, cluster, or summary rows.

### PR146. Gross Distribution History And Monthly Income Quality

Branch: `feat/monthly-etf-income-quality`.

Git status: complete. Delivered by the stacked Multivariate implementation PRs #255–#265.

Priority: P1 monthly-distribution ETF evidence.

Depends on: PR143.

Scope:

- Implement the initial jurisdiction-neutral `portfell.income` boundary with typed contracts for
  normalized distribution events, monthly buckets, `IncomePolicy`, income metrics, warnings, and
  availability reasons. Consume only pinned dividend, split, quote, currency, and optional genuine
  NAV artifact references from the Multivariate input snapshot.
- Normalize ex-date, payment date with explicit fallback, amount, currency, corrections, deletions,
  duplicates, and split effects. Aggregate events into calendar-month buckets without treating a
  missing event as a zero payment unless coverage proves that month was observed.
- Compute gross trailing-twelve-month distribution amount and yield, mean and median observed
  monthly distribution, conservative lower percentile, coefficient of variation, observed payment
  coverage, cut count, largest cut, longest falling sequence, distribution trend, price return,
  total return, and distribution-to-total-return gap.
- Compute NAV erosion only from an authorized genuine NAV series. Market price, adjusted close, or
  an inferred synthetic value may not be relabeled as NAV. Report NAV erosion as unavailable when
  genuine NAV is absent.
- Persist immutable `income_distribution_events`, `income_monthly_distributions`, `income_metrics`,
  and `income_warnings` artifacts with source identities and policy versions. Expose gross values as
  historical descriptions only; net income, taxes, broker costs, and sustainable-income claims
  remain explicitly unavailable until their verified policy adapters exist.
- Do not change portfolio weights, rank candidates, implement country tax logic, or add UI.

Acceptance:

- Hand-checkable fixtures cover twelve regular monthly payments, skipped months, multiple payments
  in one month, corrections, deletions, duplicates, split-adjusted events, currency mismatch,
  payment-date fallback, partial observation windows, and no distributions.
- Frequency classification alone cannot produce income-quality success. A monthly-classified ETF
  with insufficient event history returns unavailable metrics and a stable reason code.
- The latest payment is never annualized as the sole income estimate. TTM yield uses the documented
  trailing window, eligible positive events, and a dated denominator from the same policy.
- Missing months are distinguished from observed zero-payment months. Distribution cuts and trends
  use comparable covered buckets and do not convert unknown data to zero.
- Price return plus distributions reconciles to the implemented total-return definition on a
  hand-checkable fixture; units and currency are explicit on every monetary value.
- NAV-erosion tests reject adjusted close and market price as NAV, compute only from a genuine NAV
  fixture, and otherwise return unavailable without a numeric zero.
- Gross results never appear under names containing `net`, `after_tax`, `after_cost`, `sustainable`,
  or `spendable`. Unsupported tax/cost inputs cannot create production-income eligibility.
- Corrected source events or changed policy versions produce new artifacts; unchanged overlapping
  project selections reuse the same physical income artifacts through authorized references.

Security: Income services consume authorized artifact references and cannot call providers, mutate
Selection, scan another project's data, or expose raw internal paths. Currency, tax, cost, and NAV
availability errors reveal no inaccessible source rows.

Determinism: Event normalization, duplicate/correction precedence, month assignment, fallback dates,
percentile method, cut detection, trend calculation, precision, warning order, and artifact ids are
versioned and independent of input order.

Idempotency: Reprocessing identical source artifacts and policy reuses normalized events, monthly
buckets, metrics, and warnings. Corrections replace the affected logical revision without appending
duplicate payments or contaminating earlier immutable revisions.

### PR147. Monthly-Distribution ETF Portfolio Candidate Set

Branch: `feat/monthly-etf-portfolio-candidates`.

Git status: complete. Delivered by the stacked Multivariate implementation PRs #255–#265.

Priority: P1 portfolio construction.

Depends on: PR145 and PR146.

Scope:

- Add a versioned initial Monthly Distribution ETF portfolio policy with long-only, fully invested,
  explicit minimum/maximum instrument weights, minimum holding count, and feasibility checks. Use a
  configurable 20 percent maximum-weight default and reject any membership/constraint combination
  that cannot sum to one; do not silently relax constraints.
- Build exactly these initial comparable candidates from the same snapshot, aligned matrix,
  canonical risk model, constraints, and gross income artifacts: Equal Weight, Inverse Volatility,
  Ledoit-Wolf shrinkage Minimum Variance, Equal Risk Contribution, True Hierarchical Risk Parity,
  and historical Minimum CVaR.
- Treat Equal Weight and Inverse Volatility as explicit baselines. Label Minimum CVaR for this
  monthly-distribution universe as a tail-risk-aware income-universe candidate, not as an optimizer
  of income amount, sustainability, tax efficiency, or guaranteed cash flow.
- Persist per-candidate weights, solver diagnostics, feasibility state, baseline status, portfolio
  volatility, variance, historical VaR/CVaR, maximum drawdown, historical total return,
  diversification ratio, maximum weight, Herfindahl concentration, effective holding count,
  marginal and percentage risk contributions, largest risk contributor, gross TTM distribution
  yield, and gross historical monthly distribution estimate where available.
- Use one common evaluation period and one common policy for all candidates. Values requiring tax,
  broker-cost, genuine NAV, or future-return assumptions remain unavailable with reason codes.
- Do not rank candidates, choose a winner, create trades, or add UI. The output is a comparable
  candidate set for later validation.

Acceptance:

- Fixtures produce all six candidates in a stable order and mark the two baselines visibly. No
  candidate is described as universally best or as a recommendation.
- Every feasible candidate's weights are finite, long-only, within bounds, sum to one within the
  committed tolerance, cover only snapshot listings, and reconcile marginal to total risk within
  tolerance.
- Tests cover two, five, and twenty ETF universes; infeasible maximum/minimum weights; solver
  non-convergence; singular covariance; missing income metrics; missing return rows; and an ETF
  removed between upstream artifacts. Failures remain explicit and never become Equal Weight.
- HRP, ERC, and Minimum Variance demonstrably consume the PR144 canonical covariance artifact.
  Minimum CVaR consumes the same aligned return matrix and confidence policy.
- Portfolio volatility, CVaR, drawdown, diversification, concentration, risk contributions, and
  gross income values reconcile to hand-checkable fixtures and report units, period, observations,
  and availability.
- Gross distribution yield can be displayed and compared but cannot affect weights in this PR.
  Increasing a fixture's dividend amount alone leaves every candidate weight unchanged.
- Candidate ids change for membership, market-input, income-artifact, calendar, risk-model,
  constraints, objective, solver, or algorithm changes and remain stable for presentation changes.

Security: Candidate creation resolves only authorized snapshot and artifact dependencies. Constraint
payloads are server-validated and cannot request internal paths, arbitrary objective code, negative
weights, leverage, inaccessible listings, or unbounded resource usage.

Determinism: Candidate order, objective labels, solver configuration and tolerances, constraints,
weight order, risk-contribution order, units, precision, and artifact identity are versioned.

Idempotency: Repeating or concurrently submitting identical candidate-set inputs returns or joins
the same run and reuses its artifacts. No duplicate weight, diagnostic, fact, or risk-contribution
rows are appended.

### PR148. Multivariate Walk-Forward, Stress, And Candidate Scorecard

Branch: `feat/multivariate-candidate-validation`.

Git status: complete. Delivered by the stacked Multivariate implementation PRs #255–#265.

Priority: P1 out-of-sample validation.

Depends on: PR147.

Scope:

- Extend walk-forward evaluation to all six PR147 candidate methods using identical splits,
  estimation inputs, constraints, rebalance policy, and transaction-cost policy. Refit the risk
  model and candidate on training data only for every split.
- Add a versioned production policy with at least 504 training observations, a 21-trading-day test
  window, multiple completed out-of-sample splits, monthly re-estimation/rebalancing, and an
  explicit non-negative transaction-cost assumption. Tiny two-observation/one-observation and zero-
  cost settings remain named test/development fixtures only.
- Persist split-level train/test dates, risk-model id, requested and actual optimizer method,
  weights, pre-cost return, turnover, transaction costs, post-cost return, volatility, Sharpe,
  Sortino, CVaR, drawdown, weight stability, concentration, income availability, and failure
  reasons.
- Run versioned historical stress, seeded block-bootstrap, covariance perturbation, correlation
  convergence, and distribution-cut scenarios for every feasible candidate. A distribution-cut
  scenario affects cash-flow evidence and total-return assumptions explicitly; it must not rewrite
  observed historical source data.
- Produce a candidate scorecard with common out-of-sample metrics, median and adverse quantiles,
  stress results, data sufficiency, and evidence quality. Do not select a final recommendation when
  required evidence is unavailable or weak.
- Do not add UI, report generation, current holdings, tax advice, or broker trade preparation.

Acceptance:

- Tests prove `train_end < test_start` for every split and fail if any test observation influences
  training covariance, constraints, weights, expected-return inputs, or income statistics.
- Simple-return wealth compounds geometrically; log-return accumulation reconciles to simple-return
  wealth within tolerance; volatility, Sharpe, Sortino, and annualization use consistent horizons.
- Every candidate uses identical eligible split calendars and cost assumptions. Failed splits remain
  visible and cannot become zero-valued successes or disappear from the denominator.
- Production eligibility is rejected below 504 training observations, with too few completed
  splits, with zero/undefined production costs, with an ineligible risk model, or with solver,
  constraint, return-semantics, or stress failures.
- Turnover or transaction-cost changes alter post-cost results without altering pre-cost market
  returns. Candidate rankings can change when costs change, and the cause remains inspectable.
- Seeded bootstrap and perturbation fixtures are reproducible. Changed seeds, stress policy,
  splits, costs, or algorithm versions produce new artifact identities.
- The scorecard reports weak or unavailable income evidence rather than treating monthly frequency
  as stable income, and it never ranks solely by in-sample return or gross yield.
- All six methods have explicit walk-forward support or a tested unavailable reason; no method is
  silently omitted.

Security: Validation consumes the authorized candidate set and immutable dependencies only. Split,
stress, and scorecard endpoints enforce project-run ownership and bounded policy values; seeds and
settings cannot be used to access other snapshots or execute arbitrary code.

Determinism: Split construction, information cutoffs, rebalance dates, transaction-cost arithmetic,
scenario definitions, seeds, quantiles, score ordering, tie breaking, units, and identities are
versioned.

Idempotency: Identical validation requests reuse completed splits and scenarios and resume only
missing deterministic work after interruption. Retries never duplicate results or change a
completed scorecard.

### PR149. Project-Persisted Multivariate Service And API Contract

Branch: `feat/multivariate-project-api`.

Git status: complete. Delivered by the stacked Multivariate implementation PRs #255–#265.

Priority: P1 module integration.

Depends on: PR148.

Scope:

- Add a dedicated Multivariate application service, repository port, persistence adapter, FastAPI
  router, and typed API contracts. Replace the generic deterministic Hosted Analysis placeholder
  for this workflow; do not route Multivariate requests through zero-return or Equal Weight
  placeholder behavior.
- Add project-scoped plan, start, status, summary, structure, components, candidates,
  candidate-detail, risk-contribution, validation, and income-evidence endpoints. Responses expose
  persisted values only and use bounded pagination/detail views for large data.
- Implement persisted run states `locked`, `ready`, `running`, `complete`, `failed`, and `stale`,
  monotonic phase progress, completed/total units, current phase, elapsed time, estimated remaining
  time when estimable, warnings, and stable failure reason codes. Use all available CPU cores by
  default with a bounded configurable cap for local debugging.
- Save the project's selected Multivariate policy, constraints, selected comparison candidates,
  input snapshot id, run id, result artifact ids, and validation id immediately and atomically.
  Reopening or switching to the project automatically resolves the completed run without starting
  computation.
- Extend workflow state and the header investment funnel with a dormant Multivariate stage contract.
  It remains absent from production navigation until PR150, but upstream changes already mark its
  persisted state stale deterministically.
- Add normalized Python/TypeScript/API-contract fixtures, restart-persistence coverage, two-project
  isolation, and exact backend/frontend contract tests. Do not add the React page.

Acceptance:

- API contract tests cover every request, response, status, pagination, availability, warning,
  progress, and error shape and reject unknown fields, invalid enums, non-finite numbers, invalid
  constraints, and unbounded limits.
- Starting a valid run uses the exact PR143 snapshot, returns immediately with persisted running
  state, advances progress monotonically through named phases, and exposes the same completed result
  after API restart and project reactivation.
- Identical input/settings requests return or join the same run. Changed upstream dependencies or
  settings create a new run and mark the previous project result stale without deleting it.
- Failed and interrupted runs preserve diagnostics and completed immutable artifacts, can resume
  missing work safely, and never present partial results as complete.
- Project A and Project B can use overlapping physical market/statistics artifacts while retaining
  separate authorized run references, settings, progress, and current results. Cross-project and
  cross-user guessed ids return the standard non-disclosing authorization response.
- Endpoint values reconcile exactly with core artifacts; the API does not recalculate covariance,
  PCA, weights, income, risk, scorecard, or stress metrics.
- The generic hosted placeholder cannot satisfy or be called by any Multivariate route. Contract
  tests fail if zero-return or synthetic Equal Weight placeholder output appears.
- Worker-count tests prove default use of visible CPU capacity and deterministic equality with a
  single-worker run; resource caps and pair/listing limits fail before unbounded work is scheduled.

Security: Every endpoint resolves the authenticated project, snapshot, upstream dependency closure,
run, and artifact entitlement server-side. Browser payloads cannot supply filesystem paths,
credentials, arbitrary code/objective names, ownership fields, or unrestricted shared artifact ids.
Errors, logs, and progress contain no provider key, token, internal path, or inaccessible membership.

Determinism: Route schemas, status transitions, phase order, progress units, settings serialization,
pagination, response ordering, invalidation rules, and run/artifact identities are versioned.

Idempotency: Idempotency keys plus logical input hashes ensure concurrent identical starts join one
run; loads and project switches are read-only; restarts and retries resume without duplicate runs,
settings, project pointers, or artifacts.

### PR150. Multivariate Statistics React Module And Four-Module Cutover

Branch: `feat/multivariate-statistics-ui`.

Git status: complete. Delivered by the stacked Multivariate implementation PRs #255–#265.

Priority: P1 user-facing multivariate workflow.

Depends on: PR149.

Scope:

- Add `multivariate_statistics` as the fourth production `WorkflowModuleId`, route
  `/multivariate-statistics`, typed browser API facade, sidebar entry, workflow unlock/invalidation
  state, header investment-funnel step, page specification, and documentation. It unlocks only for
  a complete matching Bivariate run and never navigates automatically merely because it unlocked.
- Build one Multivariate Statistics page with a compact compute/progress header and these initial
  tabs: Overview, Risk Structure, Portfolio Candidates, Risk Contributions, Income Evidence, and
  Validation. Render only API-produced values and availability states.
- Overview explains candidate ETF count, aligned period, observation count, risk-cluster count,
  effective independent drivers, dominant-component share, candidate count, and warnings in plain
  language. Dense matrices and eigenvalues remain secondary details.
- Risk Structure renders component explained variance, effective rank, clusters, top loadings, and
  covariance diagnostics with keyboard-accessible summaries and bounded detail loading.
- Portfolio Candidates renders the six stable model cards with baseline badges, target-weight bars,
  comparable facts, solver/feasibility status, method trade-offs, and no universal-best label.
  Candidate selection changes project settings immediately but does not imply approval or trading.
- Risk Contributions compares capital weights with percentage risk contributions and highlights the
  largest contributors. Income Evidence distinguishes monthly frequency, gross historical income,
  unavailable net/sustainable figures, distribution cuts, and warnings. Validation renders common
  walk-forward, cost, stress, and evidence-quality results.
- Restore the latest unchanged completed project run automatically on project selection. Show stale,
  unavailable, failed, and partially resumable states explicitly. Consume the existing data-readiness
  state without embedding ingestion or a provider-download action in this module.
- Update `README.md`, `ARCHITECTURE.md`, `docs/ui/workflow-modules.md`, route/page documentation,
  API contracts, unit tests, and Playwright journeys. Rebuild and validate the Web Docker image after
  the UI change as required by `AGENTS.md`.

Acceptance:

- Route and navigation tests prove the application exposes exactly four production modules in the
  required order after cutover and contains no legacy multivariate, portfolio-filter, synthetic
  analysis, or placeholder route.
- The Multivariate entry is locked before a complete matching Bivariate run, becomes available
  without forced navigation after completion, and becomes stale after any pinned upstream or policy
  change. Creating/switching a project never redirects unexpectedly.
- Compute starts one PR149 run, displays server-owned monotonic phase progress and remaining time,
  renders all tabs automatically on completion, and restores the same values after refresh, API/Web
  restart, logout/login, and project switching.
- Unit and browser tests cover eligible monthly ETF data, insufficient history, fewer than two ETFs,
  stale bivariate input, infeasible constraints, solver failure, missing income evidence, unavailable
  genuine NAV, weak validation, interrupted/resumed run, and two projects with different settings.
- Every displayed number, unit, date range, warning, weight, risk contribution, component, income
  value, and validation fact matches the typed API fixture. No JavaScript financial calculation or
  browser-owned filtering determines results.
- Candidate cards remain comparable at desktop, tablet, and mobile widths; tabs, charts, model cards,
  tooltips, detail tables, and summaries are usable by keyboard and screen reader and support reduced
  motion. Charts provide textual/table alternatives.
- Monthly distribution is described as observed historical frequency. Gross yield is visibly gross
  and historical; unavailable net, sustainable, tax, cost, or NAV claims are never displayed as zero.
- Playwright creates two dummy projects through the UI, exercises every Multivariate button, tab,
  field, project switch, stale transition, restore path, and error state, and verifies isolation.
- Vitest and Playwright coverage is included in the repository's 95 percent coverage gate; Ruff,
  formatting, strict Pyright, architecture checks, schema validation, Python tests, TypeScript tests,
  production build, and Docker Web image build all pass.

Security: The page uses only the typed authenticated API facade and stores no provider keys, tokens,
artifact contents, ownership claims, or financial results in browser storage. URLs, tooltips,
screenshots, traces, logs, source maps, and errors expose no secrets, internal paths, or other-project
data. Client-side controls cannot broaden server-authorized membership or constraints.

Determinism: Module/page order, tab order, model-card order, labels, units, precision, colors,
accessibility summaries, chart ordering, responsive fixtures, and project-setting serialization are
versioned and independent of browser locale or response timing.

Idempotency: Refreshing, reopening a tab, changing projects, restoring a completed run, or submitting
unchanged settings never starts another computation or duplicates state. Repeated clicks while a run
is active join the existing run and disable duplicate submission.

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

## Active Shared Market Data And Nightly Refresh PR Stack

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

### PR151. Canonical Shared Market Store And Active Project Inventory

Branch: `feat/shared-market-store-contract`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/269.

Priority: P0 shared-data correctness foundation.

Depends on: PR150.

Scope:

- Define `PORTFELL_SHARED_DATA_ROOT/market-data` as the only hosted/local-app physical source for
  shared quotes, dividends, and splits. Keep local standalone CLI behavior behind an explicit
  adapter so it cannot be mistaken for the hosted project store.
- Replace the overlapping immutable-segment prototype with one canonical Parquet file per
  `(dataset_type, exchange, isin, code)`, for example
  `market-data/quotes/XETRA/IE00...__SYMBOL.parquet`. Do not retain two production shared-store
  models.
- Define a unique business key per dataset. Merge existing and incoming rows by the complete key,
  let a later provider correction replace the previous value for that key, sort canonically, and
  publish with a same-directory temporary file, fsync, and atomic replace.
- Reject `user_id`, `project_id`, credential data, session data, run ids, and authorization claims
  in physical market rows. Store project-independent provider provenance and schema version only.
- Add a rebuildable coverage catalog per listing and dataset containing first/last business date,
  row count, content hash, schema version, and publication timestamp. Parquet rows remain the source
  of truth if the catalog must be rebuilt.
- Read one consistent persistent-workspace snapshot and resolve the current metadata selection for
  every non-deleted project. Validate member ids and create a sorted set union of full listing keys.
  Duplicate members and project overlap must not duplicate inventory entries.
- Document path, key, correction, atomicity, locking, retention, and listing-identity contracts in
  `CONTRACTS.md`, `ARCHITECTURE.md`, and the path/catalog APIs.

Acceptance:

- Three projects where two share a listing and one adds another listing produce exactly two
  inventory entries. Reordering projects, selections, or members does not change the inventory hash.
- Repeatedly writing the same observation leaves exactly one row. A corrected observation replaces
  exactly that row. Different exchange/code listings of the same ISIN remain separate and cannot be
  joined accidentally as one price series.
- An injected failure before atomic replace leaves the previously published Parquet file and
  coverage record readable and mutually consistent; no reader can observe a partial file.
- Tests cover an empty workspace, deleted projects, a project without a selection, malformed member
  ids, duplicate members, duplicate projects, forbidden scoped fields, corrupt Parquet, and catalog
  rebuild from the physical files.
- A repository search and architecture test prove that only one productive shared market-data
  implementation remains and that its storage growth follows unique listing/business keys rather
  than project count.

Security: Shared files contain no credential, owner, entitlement, internal request, or session
metadata. Inventory is built inside the trusted runtime from persisted project state and is never
exposed as an unrestricted cross-project browser endpoint. Introduction of multiple credential
owners fails an explicit single-principal guard until a separately reviewed entitlement design
exists.

Determinism: Inventory order, row order, business keys, path encoding, correction precedence,
schema serialization, and content hashes are versioned and independent of filesystem order, project
order, worker completion order, locale, and wall-clock time.

Idempotency: Rebuilding inventory or upserting identical observations returns the same logical
catalog state and content hashes without adding files or rows. A retry after interruption safely
repeats the incomplete listing only.

### PR152. Idempotent Shared Market Refresh Command And Initial Backfill

Branch: `feat/shared-market-refresh-command`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/269.

Priority: P0 unattended ingestion path.

Depends on: PR151.

Scope:

- Add `portfell refresh-shared-market-data` as a non-interactive entry point. At startup it loads one
  PR151 workspace snapshot, computes the unique active-listing inventory, and refreshes quotes,
  dividends, and splits exactly once per listing.
- Reuse the EODHD client, request pacing, bounded concurrency, `Retry-After`, retries, response
  validation, and redacted logging. Resolve the configured local principal's encrypted credential
  inside the process; never place the key in arguments, environment dumps, manifests, or logs.
- Fully backfill a missing listing. For an existing listing, request only the gap through `end_date`
  plus a documented bounded overlap window for provider corrections, then use PR151's canonical
  upsert. Retain unused listings for later reuse; nightly refresh must not perform destructive GC.
- Acquire one non-blocking global refresh lock under the shared root. Persist a compact run manifest
  with inventory hash, target date, start/end time, requested/updated/unchanged/failed counts,
  per-dataset coverage, and stable redacted error codes.
- Define exit codes for success/empty inventory, lock contention, missing credential, invalid
  workspace, provider partial failure, and storage failure. Partial success keeps atomically
  completed listings but cannot report a successful run.
- Add `--dry-run` for workspace, inventory, delta-plan, credential, lock, and write preflight;
  `--end-date` for deterministic execution; and bounded `--concurrency` with a safe default.

Acceptance:

- Against a deterministic fake provider, the first run backfills every unique active listing and all
  three datasets once. A second run for the same target date creates no duplicate row, file, or full-
  history request.
- Project overlap changes neither provider request count nor stored row count. A correction returned
  inside the overlap window replaces its prior row while preserving the unique-key invariant.
- A project added or deleted while a run is active affects only the next run because the active run
  uses its immutable startup inventory.
- Two concurrent starts cannot write concurrently. The second returns the documented contention
  code, and retry after a simulated crash resumes without corrupting or duplicating completed data.
- Missing/invalid credentials, malformed provider payloads, HTTP partial failure, a read-only shared
  root, and disk-write failure produce stable non-zero outcomes without leaking secret material.
- A scale test with at least 1,000 heavily overlapping projects proves planning memory, request
  count, and storage work scale with unique listings, not `projects * listings`.

Security: Only the ingestion process unwraps the provider credential and only for provider calls.
Run manifests, exceptions, process listings, tests, and logs contain no key or decrypted credential.
The command rejects an unexpected multi-principal workspace rather than selecting a credential
implicitly.

Determinism: A fixed workspace snapshot, provider fixture, schema version, overlap policy, and end
date produce the same plan, canonical files, content hashes, and summary independent of concurrency.

Idempotency: Repeating a complete or partial run with the same target state converges on one row per
business key and one current coverage record per listing/dataset. Stable run identity prevents
duplicate success publication.

### PR153. Project Analysis Cutover To Shared Market Snapshots

Branch: `refactor/project-shared-market-consumers`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/269.

Priority: P0 remove project data duplication.

Depends on: PR152.

Scope:

- Route hosted/local-app quote, dividend, and split reads in Univariate, Bivariate, and Multivariate
  input construction through one read-only PR151 store adapter filtered by the requesting project's
  exact selection. No project workflow may copy shared market rows into project or run state.
- Construct an immutable analysis input snapshot from project id, selection id, sorted listing keys,
  per-listing shared content hashes, schema/policy versions, and one common `as_of`. Persist this
  snapshot identity in every derived run and artifact.
- Derive `project_data_loaded` and workflow readiness from complete shared coverage for all selected
  listings rather than a successful project quote run. Expose stable readiness details including
  `ready`, `pending_nightly_refresh`, missing listings, last successful refresh, and common `as_of`.
- Reject compute with `shared_market_data_pending` when required coverage is absent. A project made
  after the nightly run remains readable and becomes computable after the next successful refresh
  without a manual download.
- Stop persisting `quote_rows_by_run_id` and equivalent copies. Restore legacy workspace payloads,
  preserve selections and analyses, but omit copied quote rows on the next atomic save.
- Ensure project deletion removes project-owned pointers and analysis state only; it never removes
  shared market files or coverage used by another or future project.

Acceptance:

- Two projects with overlapping selections reference identical content hashes for shared listings,
  read only their own members, and produce isolated project analysis results without copied market
  rows.
- An analysis concurrent with atomic publication resolves all inputs from either snapshot N or N+1,
  never a mixed set. Repeating unchanged analysis resolves the same snapshot id after API/Web
  restart.
- A newly created uncovered project reports `pending_nightly_refresh`; compute fails with the stable
  pending code; a PR152 run changes it to ready without any project download request.
- Migrating and re-saving an existing workspace removes persisted quote-row payloads while projects,
  selections, settings, completed analyses, and restart behavior remain intact.
- Deleting one of two overlapping projects does not alter shared files, coverage, hashes, or the
  remaining project's results.
- Unit, API, architecture, and two-project integration tests prove all hosted analytical reads are
  selection-scoped shared reads and no unrestricted global scan is available to browser requests.

Security: The shared reader receives an already authorized project selection and returns no rows
outside it. File paths, inventory membership, hashes for unauthorized listings, and other-project
state do not appear in API responses or errors.

Determinism: Snapshot identity includes exact sorted listing keys, content hashes, common `as_of`,
and contract versions. Current pointers, refresh timing, process order, and unrelated project changes
cannot alter an already resolved analysis snapshot.

Idempotency: Reopening a project, restoring a workspace, or repeating analysis against unchanged
shared content reuses the same snapshot and artifacts without copying rows or starting ingestion.

### PR154. Docker Compose Nightly Cron Installer And Operations Gate

Branch: `feat/nightly-market-refresh-cron`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/269.

Priority: P0 operational prerequisite for removing manual refresh.

Depends on: PR153.

Scope:

- Add a short-lived Compose service `market-data-refresh` using the API image, runtime user,
  encrypted-credential secret, workspace volume, shared market-data volume, and environment contract,
  but no Web port, API server, or unnecessary network exposure. Its only command is PR152.
- Add a versioned idempotent host installer with `install`, `status`, `run-once`, and `uninstall`.
  Validate absolute project, Docker, Compose, lock, and log paths; `docker compose config`; mounted
  secrets; volume write access; and a successful `--dry-run` before changing crontab.
- Manage one delimited Portfell block in the service user's crontab while preserving every unrelated
  byte/entry. Set `SHELL=/bin/bash`, `CRON_TZ=Europe/Amsterdam`, and schedule daily execution at
  `20:15` with absolute paths and `/usr/bin/flock -n`.
- Run `docker compose run --rm --no-deps market-data-refresh`, append stdout/stderr to a dedicated
  rotation-compatible log, propagate the refresh exit code, and include no secret in crontab or the
  host command line.
- Document the exact rollout: build images; start the persistent stack; run installer preflight;
  execute one initial full refresh; verify coverage and duplicate invariants; install cron; inspect
  `crontab -l` and `status`; execute `run-once`; verify the run manifest; only then deploy PR155.
- Document timezone/DST behavior, service user, permissions, log rotation, monitoring threshold,
  host reboot behavior, lock contention, partial-failure retry, disk-full recovery, uninstall, and
  rollback.

Acceptance:

- `docker compose config` is valid and inspection proves the job sees the same required workspace,
  credential, and shared-data mounts as API while exposing no port and starting no API process.
- Installer tests cover empty and populated crontabs. Installing twice leaves exactly one managed
  entry; uninstall removes only that entry and preserves unrelated entries exactly.
- `status` reports installed state, schedule/timezone, last run status, and age of the latest
  successful manifest. Missing, failed, or stale refresh state returns an alertable non-zero status.
- A staging proof with two overlapping projects passes initial backfill, API restart, analysis in
  both projects, a second idempotent `run-once`, and assertions for no duplicate business keys and no
  project-scoped market rows.
- The installed job runs non-interactively as the documented service user. Lock contention, provider
  partial failure, invalid credential, and full/read-only storage return documented exit codes and
  leave the last valid shared snapshot readable.
- The runbook contains literal inspectable commands for install, `crontab -l`, dry run, one-time run,
  status, logs, recovery, uninstall, and rollback; no step depends on undocumented shell state.

Security: The cron line and process arguments contain no EODHD key or KEK. Only the refresh container
mounts the credential secret and shared volume. The installer never prints secret values and refuses
world-writable secret or configuration files.

Determinism: The managed cron block, timezone, schedule, command, absolute paths, Compose service,
preflight sequence, and status thresholds are versioned. Installer output does not depend on current
directory or interactive shell configuration.

Idempotency: Repeated install, status, dry-run, run-once, and uninstall operations do not duplicate
cron entries, containers, manifests, rows, or locks. Failed installation leaves the original crontab
unchanged.

### PR155. Remove Manual Historical-Data Actions And Legacy Quote Runs

Branch: `refactor/remove-manual-historical-data-update`.

Git status: merged. PR: https://github.com/SergejSchweizer/portfell/pull/269.

Priority: P1 final user-facing shared-data cutover.

Depends on: PR154 and a successful target-environment initial refresh.

Scope:

- Remove every `Update Historical Data` button from Univariate Statistics, Bivariate Statistics,
  Multivariate Statistics, and any other Portfell view, including click handlers, project quote-run
  progress state, success labels, helper functions, styles, and obsolete fixtures.
- Replace manual ingestion controls with a read-only shared-data status showing the last successful
  nightly refresh, common `as_of`, covered/missing listing counts, and
  `pending_nightly_refresh` when applicable. Compute buttons remain analysis-only and never trigger a
  provider request.
- Remove project quote-run mutation routes and services, or close unavoidable compatibility routes
  with a stable Gone/deprecated response that cannot invoke EODHD or write market data. Retain only
  read-only central refresh history needed by status and operations.
- Update typed Web/API contracts, OpenAPI snapshots, workflow state, copy, README, architecture/UI
  docs, and E2E fixtures so no current instruction tells a user to download historical data manually.
- Remove dead quote-progress code and legacy workspace serialization after compatibility coverage
  proves PR153 migration is complete.

Acceptance:

- `apps/web/src` contains no visible `Update Historical Data` label, corresponding button, event
  handler, or project download API call. Uni-, Bi-, and Multivariate pages show only analysis actions
  plus the read-only shared-data status.
- Playwright creates two projects with overlapping ISINs, observes a simulated successful nightly
  refresh, computes the available stages for both, switches projects, reloads, and proves no POST to
  the legacy quote-run endpoint occurs.
- Before first coverage, the UI explains `pending_nightly_refresh` without offering a manual
  workaround. After refresh, reload exposes the new readiness and preserves exact project scope.
- Direct legacy mutation requests cannot make an EODHD call, create a run, copy rows, or alter shared
  data. OpenAPI and API contract tests encode the removed/Gone behavior.
- A final source/documentation search finds no active manual historical-update instruction. Ruff,
  formatting, strict Pyright, architecture/schema tests, Python and TypeScript tests, production Web
  build, Playwright, Docker image build, and the current coverage gate all pass.

Security: Removing browser-triggered ingestion eliminates user-controlled provider-download side
effects. Shared status reveals only readiness and freshness for the authorized project's selected
listings, never global inventory, credentials, paths, or other-project membership.

Determinism: Shared-status labels, readiness mapping, dates, counts, API errors, and page state derive
only from versioned server contracts and the selected project snapshot, not browser timing or locale.

Idempotency: Reloading, switching projects, polling shared status, or repeatedly pressing Compute
cannot start ingestion or duplicate analysis. Compatibility-route retries remain side-effect free.

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

Scope: Add `apps/web` with Google login, dashboard, credential settings, data-download workflow, visible-data coverage, metadata selection, univariate statistics and selection, bivariate statistics, multivariate portfolio analysis, report views, and logout/account-deletion flows. The browser consumes API-produced data and performs no financial calculations or authorization decisions. The credential form accepts a new key but never redisplays the stored key.

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

### Completed UI Foundation Record

The following merged record is historical only and contains no active follow-up scope.

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
