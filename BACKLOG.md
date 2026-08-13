## Table Of Contents

- [Backlog Policy](#backlog-policy)
- [Active Multivariate Overview Tabs Work](#active-multivariate-overview-tabs-work)
- [Active Compose Stack Rebuild Work](#active-compose-stack-rebuild-work)
- [Active Multivariate Performance Controls Work](#active-multivariate-performance-controls-work)
- [Active Backlog Maintenance Work](#active-backlog-maintenance-work)
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

## Active Multivariate Overview Tabs Work

### PR233. Multivariate Overview Tabs

Branch: `feat/multivariate-overview-tabs`.

Git status: in progress.

PR: TBD.

Priority: P1 multivariate analytical clarity.

Depends on: PR232.

Scope: Limit the Multivariate Statistics result navigation to Overview and Portfolio Candidates.

Acceptance: Completed Multivariate runs expose exactly Overview and Portfolio Candidates tabs.
The retained Overview performance chart and candidate cards remain available.

Security: The browser continues to render only server-owned analytical artifacts.

Determinism: An unchanged completed run exposes the same retained result views and values.

Idempotency: Tab selection creates no writes or analytical work.

Series Completion Gate: Before merge, satisfy the applicable validation gates in `GATES.md`.

## Active Compose Stack Rebuild Work

### PR232. Automatic Compose Stack Rebuilds

Branch: `chore/compose-stack-rebuild-watch`.

Git status: pushed.

PR: https://github.com/SergejSchweizer/portfell/pull/382.

Priority: P1 local runtime correctness.

Depends on: PR231.

Scope: Rebuild every locally built Compose service when its image inputs change, and make the
fallback watcher rebuild the complete local application stack.

Acceptance: Compose watch rebuilds Web for Web image inputs and API, migration, and worker
services for shared Python image inputs. The fallback command rebuilds all Compose services.

Security: Rebuild automation uses existing external secret-file configuration and does not expose
or create secrets.

Determinism: An unchanged watched input set causes no rebuild; a changed input invokes the same
Compose rebuild command.

Idempotency: Repeating a rebuild replaces service images without changing persistent volumes.

Series Completion Gate: Before merge, satisfy the applicable validation gates in `GATES.md`.

## Active Multivariate Performance Controls Work

### PR231. Multivariate Performance Series Controls

Branch: `feat/multivariate-performance-series-controls`.

Git status: pushed.

PR: https://github.com/SergejSchweizer/portfell/pull/381.

Priority: P1 multivariate analytical clarity.

Depends on: current `main`.

Scope: Add local visibility controls for every Overview performance-chart instrument and portfolio
series while preserving the server-owned monthly return artifact.

Acceptance: Every chart series has an enabled-by-default checkbox. Any combination of enabled
series controls the SVG and tooltip; hiding all series leaves controls available with an empty state.

Security: The browser changes only local display state and does not calculate or persist returns.

Determinism: An unchanged artifact and visible-series selection produce the same chart and tooltip.

Idempotency: Toggling visibility creates no writes or analytical work.

Series Completion Gate: Before merge, satisfy the applicable validation gates in `GATES.md`.

## Active Backlog Maintenance Work

### PR230. Condense Finished Backlog Records

Branch: `docs/condense-finished-backlog`.

Git status: pushed.

PR: https://github.com/SergejSchweizer/portfell/pull/380.

Priority: P2 repository maintenance.

Depends on: current `main`.

Scope: Replace terminal detailed PR plans with compact history rows while retaining active planned
and operational follow-up records, governance policy, and architectural decisions.

Acceptance: Every finished PR is represented once in `Completed PR History` with its stable
identifier and final status. No terminal detailed PR plan or stale history-table link remains.

Security: This documentation-only maintenance change does not alter runtime code, secrets, or
deployment configuration.

Determinism: The compact history preserves stable PR identifiers, titles, and final statuses.

Idempotency: Reapplying the consolidation does not duplicate historical rows or modify active plans.

Series Completion Gate: Before merge, satisfy the applicable documentation validation in `GATES.md`.

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
