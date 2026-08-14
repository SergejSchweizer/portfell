Last reviewed: 2026-08-14

## Table Of Contents

- [Backlog Policy](#backlog-policy)
- [Parallel Weak-Agent PR Design](#parallel-weak-agent-pr-design)
- [Active Multivariate Calculation Correctness Work](#active-multivariate-calculation-correctness-work)
- [Active Mixed Distribution Frequency Portfolio Work](#active-mixed-distribution-frequency-portfolio-work)
- [Active Bivariate Calculation Correctness Work](#active-bivariate-calculation-correctness-work)
- [Active Univariate Calculation Correctness Work](#active-univariate-calculation-correctness-work)
- [Active Univariate Overview Narrow Bars Work](#active-univariate-overview-narrow-bars-work)
- [Active Multivariate Minimum Variance Convergence Work](#active-multivariate-minimum-variance-convergence-work)
- [Active Multivariate Overview Metric Labels Work](#active-multivariate-overview-metric-labels-work)
- [Active Multivariate Overview Portfolio Controls Work](#active-multivariate-overview-portfolio-controls-work)
- [Active Multivariate Overview Cumulative Axis Work](#active-multivariate-overview-cumulative-axis-work)
- [Active Multivariate Overview Portfolio Colors Work](#active-multivariate-overview-portfolio-colors-work)
- [Active Multivariate Overview Facts Removal Work](#active-multivariate-overview-facts-removal-work)
- [Active Multivariate Overview Portfolio Summary Work](#active-multivariate-overview-portfolio-summary-work)
- [Active Multivariate Overview Tabs Work](#active-multivariate-overview-tabs-work)
- [Active Compose Stack Rebuild Work](#active-compose-stack-rebuild-work)
- [Active Multivariate Performance Controls Work](#active-multivariate-performance-controls-work)
- [Active Backlog Maintenance Work](#active-backlog-maintenance-work)
- [Active PostgreSQL Tenant Plane And Shared Data PR Stack](#active-postgresql-tenant-plane-and-shared-data-pr-stack)
- [Active Monthly-Distribution ETF Multivariate PR Stack](#active-monthly-distribution-etf-multivariate-pr-stack)
- [Active Shared Market Data And Nightly Refresh PR Stack](#active-shared-market-data-and-nightly-refresh-pr-stack)
- [Active Hosted Simplicity And Interactive Performance PR Stack](#active-hosted-simplicity-and-interactive-performance-pr-stack)
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

## Active Mixed Distribution Frequency Portfolio Work

### PR245. Mixed Distribution Frequency Portfolios

Branch: `feat/mixed-distribution-frequency-portfolios`.

Git status: merged.

PR: https://github.com/SergejSchweizer/portfell/pull/398.

Priority: P1 portfolio universe correctness.

Depends on: PR244.

Scope: Evolve the versioned Multivariate ETF eligibility policy so one exact portfolio universe may
contain monthly, quarterly, and semiannual distributing ETFs without dropping valid Bivariate members.

Acceptance: A mixed monthly, quarterly, and semiannual Bivariate universe produces one eligible
Multivariate snapshot with unchanged membership. Annual, irregular, accumulating, and unknown
frequencies remain explicitly unavailable, and frequency-policy changes alter snapshot identity.

Security: The policy consumes only typed, authorized Univariate rows and cannot broaden project or
artifact access.

Determinism: Supported frequencies are normalized and serialized in stable sorted order as part of
the policy and snapshot identities.

Idempotency: Recomputing the same mixed-frequency universe and policy resolves the same snapshot.

Series Completion Gate: Before merge, satisfy the applicable validation gates in `GATES.md`.

## Active Multivariate Calculation Correctness Work

### PR244. Multivariate Calculation Correctness

Branch: `fix/multivariate-calculation-correctness`.

Git status: pushed.

PR: https://github.com/SergejSchweizer/portfell/pull/394.

Priority: P0 analytical correctness.

Depends on: PR243.

Scope: Aggregate realized portfolios from weighted simple daily returns across candidate metrics,
Minimum CVaR, Walk-Forward validation, stress evidence, and performance; make monthly performance
dates independent of input row order; invalidate prior candidate, validation, and Hosted runs; and
accept canonical v2 Univariate dependencies while allowing failed v12 runs to restart.

Acceptance: Candidate totals reconcile with Performance, Minimum CVaR receives simple-return
scenarios, Walk-Forward compounds weighted simple returns, and shuffled source rows produce the same
performance artifact. Minimum Variance receives its 100,000-iteration production budget. Contracts
advance to candidate v6, validation v5, and execution v13.

Security: Portfolio calculations remain server-owned and consume only the completed project-scoped
Bivariate hand-off and shared-market revisions.

Determinism: Identical aligned source revisions, constraints, and v12 contracts produce identical
candidate, validation, stress, and performance artifacts.

Idempotency: Repeating v13 with unchanged inputs resolves the same Hosted run and artifacts.

Series Completion Gate: Before merge, satisfy the applicable validation gates in `GATES.md`.

## Active Bivariate Calculation Correctness Work

### PR243. Bivariate Calculation Correctness

Branch: `fix/bivariate-calculation-correctness`.

Git status: pushed.

PR: https://github.com/SergejSchweizer/portfell/pull/393.

Priority: P0 analytical correctness.

Depends on: PR242.

Scope: Replace the approximate Spearman metric with exact average-rank correlation, add aligned
pair-content identities, and invalidate cached or Hosted results under algorithm version `v10`.

Acceptance: Perfect monotonic rank relationships, including ties, return exact Spearman values.
Return-value changes at an unchanged calendar invalidate cached pairs. Independent formula,
downstream, and repository quality tests pass.

Security: Pair calculation remains server-owned and consumes only the persisted selected return
universe.

Determinism: Identical aligned dates and return vectors produce identical v10 rows and input IDs.

Idempotency: Repeating v10 with unchanged pair-content identities reuses the same artifact and
Hosted run.

Series Completion Gate: Before merge, satisfy the applicable validation gates in `GATES.md`.

## Active Univariate Calculation Correctness Work

### PR242. Univariate Calculation Correctness

Branch: `fix/univariate-calculation-correctness`.

Git status: pushed.

PR: https://github.com/SergejSchweizer/portfell/pull/392.

Priority: P0 analytical correctness.

Depends on: current `main`.

Scope: Use one quarantined valid-price series for every Univariate price metric, version the
calculation contract, and invalidate cached or Hosted results when formulas or relevant source
content change.

Acceptance: Invalid edge prices cannot affect return, CAGR, drawdown, trend, or dividend yield.
Legacy and content-mismatched artifacts are recomputed under `univariate.statistics.v2`; independent
formula regressions and the repository quality gate pass.

Security: Recalculation remains server-owned and reads only project-selected or local lake inputs.

Determinism: Identical validated quote/dividend content and confidence level produce identical v2
statistics and content identities.

Idempotency: Repeating v2 with unchanged source identities reuses the same artifact and Hosted run.

Series Completion Gate: Before merge, satisfy the applicable validation gates in `GATES.md`.

## Active Univariate Overview Narrow Bars Work

### PR241. Univariate Overview Narrow Bars

Branch: `feat/univariate-overview-narrow-bars`.

Git status: pushed.

PR: https://github.com/SergejSchweizer/portfell/pull/391.

Priority: P2 univariate visual clarity.

Depends on: PR240.

Scope: Slightly narrow and center the Univariate Overview histogram columns without changing
their values, scales, labels, selections, or interactions.

Acceptance: Dividend and quantitative statistic histogram columns use 84% of each bucket width.

Security: The browser continues to render only server-produced values.

Determinism: Identical persisted statistic rows render the same column geometry.

Idempotency: Viewing or interacting with the charts creates no writes beyond existing selection
updates.

Series Completion Gate: Before merge, satisfy the applicable validation gates in `GATES.md`.

## Active Multivariate Minimum Variance Convergence Work

### PR240. Multivariate Minimum Variance Convergence

Branch: `feat/multivariate-minimum-variance-convergence`.

Git status: pushed.

PR: https://github.com/SergejSchweizer/portfell/pull/390.

Priority: P1 multivariate analytical completeness.

Depends on: PR239.

Scope: Allow the Multivariate Minimum Variance candidate to use the solver's full default
convergence budget and invalidate runs calculated under the former short solver limit.

Acceptance: Minimum Variance does not receive the former 500-iteration cap. A changed execution
contract creates a fresh Multivariate run rather than reusing a result computed with that cap.

Security: The server continues to own all solver execution and persisted candidate artifacts.

Determinism: Identical inputs and the versioned solver budget produce the same candidate result.

Idempotency: Repeating a request with the same v11 execution contract resolves the same run.

Series Completion Gate: Before merge, satisfy the applicable validation gates in `GATES.md`.

## Active Multivariate Overview Metric Labels Work

### PR239. Multivariate Overview Metric Labels

Branch: `feat/multivariate-overview-metric-labels`.

Git status: merged.

PR: https://github.com/SergejSchweizer/portfell/pull/389.

Priority: P1 multivariate analytical clarity.

Depends on: PR238.

Scope: Shorten the requested Multivariate Overview portfolio-metrics table headers without
changing the underlying server-provided values.

Acceptance: The headers read `MD`, `Monthly Return`, `Annual Return`, `Holdings`, and
`Deversifikaton`.

Security: This presentation-only change does not alter analytical values or browser calculations.

Determinism: An unchanged candidate artifact renders the same values under the renamed headers.

Idempotency: Viewing Overview creates no writes or analytical work.

Series Completion Gate: Before merge, satisfy the applicable validation gates in `GATES.md`.

## Active Multivariate Overview Portfolio Controls Work

### PR238. Multivariate Overview Portfolio Controls

Branch: `feat/multivariate-overview-portfolio-controls`.

Git status: pushed.

PR: https://github.com/SergejSchweizer/portfell/pull/388.

Priority: P1 multivariate analytical clarity.

Depends on: PR237.

Scope: Remove instrument activation controls from the Multivariate Overview and retain controls
only for portfolio series.

Acceptance: Instrument reference lines remain visible without checkboxes. Portfolio checkboxes
select their series independently while chart and tooltip values follow the enabled portfolios.

Security: The browser changes only local chart presentation state for server-produced values.

Determinism: An unchanged artifact and portfolio selection produce the same displayed chart.

Idempotency: Toggling portfolios creates no writes or analytical work.

Series Completion Gate: Before merge, satisfy the applicable validation gates in `GATES.md`.

## Active Multivariate Overview Cumulative Axis Work

### PR237. Multivariate Overview Cumulative Axis

Branch: `docs/multivariate-overview-cumulative-axis`.

Git status: pushed.

PR: https://github.com/SergejSchweizer/portfell/pull/387.

Priority: P1 multivariate analytical clarity.

Depends on: PR236.

Scope: Clarify the Multivariate Overview chart y-axis as compounded cumulative relative gain.

Acceptance: The y-axis states `Cumulative relative gain (%)`, matching the server-produced
cumulative monthly performance artifact.

Security: The label adds no client-side analytical calculation or state.

Determinism: An unchanged performance artifact retains the same axis values and label.

Idempotency: Viewing the chart creates no writes or analytical work.

Series Completion Gate: Before merge, satisfy the applicable validation gates in `GATES.md`.

## Active Multivariate Overview Portfolio Colors Work

### PR236. Multivariate Overview Portfolio Colors

Branch: `feat/multivariate-overview-portfolio-colors`.

Git status: pushed.

PR: https://github.com/SergejSchweizer/portfell/pull/386.

Priority: P1 multivariate analytical clarity.

Depends on: PR235.

Scope: Render each Multivariate Overview portfolio series as a distinct solid color rather than a
dashed line.

Acceptance: Portfolio series use distinct computed colors and no `stroke-dasharray`; instrument
series retain their light-gray treatment.

Security: The browser changes only presentation of server-produced performance values.

Determinism: An unchanged performance artifact renders the same series colors and paths.

Idempotency: Rendering the chart creates no writes or analytical work.

Series Completion Gate: Before merge, satisfy the applicable validation gates in `GATES.md`.

## Active Multivariate Overview Facts Removal Work

### PR235. Multivariate Overview Facts Removal

Branch: `feat/multivariate-overview-remove-facts`.

Git status: pushed.

PR: https://github.com/SergejSchweizer/portfell/pull/385.

Priority: P1 multivariate analytical clarity.

Depends on: PR234.

Scope: Remove the Multivariate Overview facts table while retaining the performance chart,
portfolio metrics table, and server-provided availability messages.

Acceptance: Overview does not render `Multivariate overview facts`; its performance chart and
portfolio metrics table remain available after a completed Multivariate run.

Security: The browser continues to display only server-provided analytical values.

Determinism: An unchanged completed run produces the same retained Overview content.

Idempotency: Viewing Overview creates no writes or analytical work.

Series Completion Gate: Before merge, satisfy the applicable validation gates in `GATES.md`.

## Active Multivariate Overview Portfolio Summary Work

### PR234. Multivariate Overview Portfolio Summary

Branch: `feat/multivariate-overview-portfolio-summary`.

Git status: pushed.

PR: https://github.com/SergejSchweizer/portfell/pull/384.

Priority: P1 multivariate analytical clarity.

Depends on: PR233.

Scope: Show only portfolio values in Overview-chart inspection tooltips, label the relative-gain
axis in percent, and add each portfolio's persisted primary metrics below the chart.

Acceptance: The chart tooltip omits instruments, the y-axis title states `Relative gain (%)`, and
the Overview portfolio table includes each portfolio's average monthly and annual relative gain.

Security: The browser renders server-owned candidate and performance values without calculating returns.

Determinism: An unchanged run produces the same chart, tooltip, and portfolio metrics table.

Idempotency: Viewing or inspecting the Overview creates no writes or analytical work.

Series Completion Gate: Before merge, satisfy the applicable validation gates in `GATES.md`.

## Active Multivariate Overview Tabs Work

### PR233. Multivariate Overview Tabs

Branch: `feat/multivariate-overview-tabs`.

Git status: pushed.

PR: https://github.com/SergejSchweizer/portfell/pull/383.

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

PR246 through PR251 are sequential. They optimize the active PostgreSQL authority only and do not
replace React, FastAPI, PostgreSQL, Polars, or Parquet. Local CLI analysis remains supported, but no
local repository, workspace JSON, in-memory dictionary, or shared-file scan may become a fallback
authority for a hosted request. Every latency assertion must use a checked-in deterministic fixture
and report request count, response bytes, database statement count, shared-file reads, and elapsed
time; wall-clock thresholds alone are insufficient evidence.

### PR247. PostgreSQL Navigation Read Model

Branch: `feat/hosted-navigation-read-model`.

Git status: historical; see Completed PR History (PR247).

PR247a (navigation foundation): https://github.com/SergejSchweizer/portfell/pull/401 — schema,
bounded reader/writer, conditional GET, project-command writes, Metadata Builder hand-off, and
side-effect-free absent-current-project handling. The remaining reconciliation, lifecycle, projection,
repair, read instrumentation, and deterministic budget evidence are merged in the linked atomic steps
below.

PR247b branch: `feat/hosted-navigation-reconciliation` (merged as #402). It provides a single-query,
RLS-bound, idempotent reconciliation primitive and wires it into PostgreSQL project commands and every
initial-fill job lifecycle transition in the same durable-job transaction.

PR247c1 branch: `feat/hosted-navigation-workflow-projections` (merged as #403). It removes hidden
univariate-selection and preference writes from PostgreSQL workflow reads; completed worker commands
remain the sole writers for those records.

PR247c2a branch: `feat/hosted-navigation-lifecycle-projections` (merged as #404). It projects metadata
revision/run state and refreshes the navigation in every metadata lifecycle write under the same
connection transaction.

PR247c2b1 branch: `feat/hosted-project-workflow-projection` (merged as #405). It adds a
project-scoped, RLS-bound workflow projection table and deterministic read/write adapter with revision
ETags; no lifecycle command or route behavior changes in this foundational schema step.

PR247c2b2 was split because its prior combination of three analytical lifecycles, project association,
and HTTP route replacement was not safely parallelizable for two weak agents. PR247c2b2a owns only
the durable project-to-research mapping and command-side projection writes; PR247c2b2b owns only the
pure projection readers and route composition. PR247c2b3 was split again: PR247c2b3a owns deterministic
repair plus restart/RLS evidence; PR247c2b3b owns route instrumentation and large-fixture performance
evidence.

PR247c2b2a branch: `feat/hosted-project-workflow-lifecycle` (merged as #406).

- Own exactly one migration and repository boundary for a forced-RLS, user-scoped mapping from each
  univariate, bivariate, or multivariate run to its owning project. The mapping must make a completed
  univariate selection's project explicit; it must not infer ownership from the mutable
  user-wide `current_univariate_selection_preferences` record.
- Add command-only projection reconciliation/writes for univariate start/progress/complete/failure,
  bivariate start/progress/complete/failure, and multivariate start/progress/complete/failure. Each
  write occurs in the same successful PostgreSQL transaction as its source lifecycle update and uses
  the canonical `resolve_workflow` payload shape already exposed by the API.
- The projection payload contains only workflow stages, process-overview counts, run IDs/statuses, and
  a schema version; it must not contain member lists, result rows, credentials, or storage paths.
- Required handoff: expose a typed `read(user_id, project_id)` projection port and a command-side
  `reconcile(user_id, project_id)` callable. Do not modify `/workflow` routes in this PR.

Acceptance for PR247c2b2a:

- Two projects owned by one user can run the same lifecycle concurrently without a run, selection,
  count, or projection becoming visible on the other project. Tests use distinct project IDs and
  identical user IDs to prove this specific isolation case.
- Each lifecycle transition has an exact source-row and projection-row test: start, one progress
  update, completion, failure, retry after failure, and idempotent replay. Replaying unchanged state
  keeps the projection revision and ETag byte-identical.
- Tests force a transaction rollback after the source write and prove neither mapping nor projection
  change is committed. RLS tests prove guessed project IDs and cross-user IDs read/write nothing.
- The local repository implementation remains protocol-compatible; PostgreSQL focused unit tests,
  migration/catalog tests, architecture tests, Ruff, format, Pyright, and the applicable real-stack
  gate pass.

PR247c2b2b branch: `feat/hosted-project-workflow-routes` (merged as #407).

- Depend only on PR247c2b2a's typed projection read port. Replace `/workflow` and
  `/projects/{project_id}/workflow` with side-effect-free, bounded projection reads. The current
  project is resolved from the existing navigation projection without rebuilding a workflow from
  selections, runs, or shared data.
- Define explicit no-current-project and not-yet-projected responses in the same versioned contract;
  they contain empty stages and no implied write. Do not add a GET fallback that reads lifecycle,
  selections, Parquet, or shared-store files.
- Required handoff: expose route-level statement-count/response-size instrumentation only; PR247c2b3
  owns performance fixtures, repair, and the final budget assertions.

Acceptance for PR247c2b2b:

- Both routes make at most two statements including RLS binding, perform zero writes and zero shared
  file/Parquet reads, and return the exact canonical payload/ETag written by PR247c2b2a.
- Tests cover no current project, selected project, guessed/deleted/cross-user project, a `304`
  conditional response where applicable, and prove a GET cannot call lifecycle, selection, research,
  or reconciliation writers.
- API-contract, PostgreSQL adapter, route, architecture, Ruff, format, Pyright, and real-stack
  button gates pass. The PR changes no lifecycle schema or writer.

PR247c2b3a branch: `feat/hosted-project-workflow-repair` (merged as #408).

- Add an explicit deployment/maintenance callable that reconciles one authorized project's workflow
  projection from the existing canonical workflow source. It accepts exact `user_id` and `project_id`,
  owns one transaction, never enumerates users, and returns the canonical payload/ETag.
- Provide a command-level restart repair entrypoint that accepts an explicit, deterministic list of
  `(user_id, project_id)` inputs. It skips deleted or unauthorized projects, records no broad data,
  and is idempotent when invoked repeatedly after a restart or interrupted worker.
- Add PostgreSQL adapter tests for rollback, RLS, deleted projects, restart repair, and byte-identical
  idempotent output. Do not add route timing instrumentation or performance fixtures here.

Acceptance for PR247c2b3a:

- Two consecutive repairs of unchanged source state return the same payload and ETag and do not advance
  projection revision. A source mutation followed by repair advances exactly one revision.
- A forced exception before transaction commit leaves both source and workflow projection unchanged.
  Guessed, cross-user, and deleted project IDs return typed absence without reading another tenant.
- A restart fixture with one missing and one stale workflow projection restores both through only the
  explicit supplied project IDs; it performs no shared-file reads and never creates a selection/run.
- Focused repair, projection adapter, migration/catalog, RLS, architecture, Ruff, format, Pyright, and
  real-stack gates pass.

PR247c2b3b was split for independent verification: PR247c2b3b1 owns only deterministic
instrumentation; PR247c2b3b2 owns only the large-fixture performance evidence.

PR247c2b3b1 branch: `feat/hosted-workflow-read-instrumentation` (merged as #409).

- Instrument only `/workflow` and `/projects/{project_id}/workflow` with statement count, response
  bytes, shared-file-read count, and elapsed time; expose structured test hooks without leaking these
  values in tenant responses.
- Do not add large performance fixtures, change projection schemas, lifecycle writers, or repair
  behavior; PR247c2b3b2 owns that evidence.

Acceptance for PR247c2b3b1:

- Instrumented route tests prove at most two PostgreSQL statements including RLS binding for both
  current and explicit-project paths, zero writes, zero shared-file/Parquet reads, and no lifecycle or
  reconciliation invocation.
- Reader and request-scope tests prove that an already authenticated request does not issue a duplicate
  RLS-binding statement and that metrics are reset after each request/worker context.
- API-contract, architecture, Ruff, format, Pyright, Playwright, and real-stack gates pass.

PR247c2b3b2 branch: `feat/hosted-workflow-read-performance` (merged as #410).

- Depend only on PR247c2b3b1's structured metrics hook. Add deterministic 100-project/25,000-member
  projection fixtures and prove bounded statement counts, zero shared-file reads, no GET writes,
  response size below 256 KiB, idle p95 below 250 ms, and loaded p95 below 1 s.
- Include PR246's worker-contention scenario without changing application schemas, route logic, or
  lifecycle writers. The fixture must build compact precomputed projections rather than 25,000 real
  selection rows in a GET test.

Acceptance for PR247c2b3b2:

- Current-project and explicit-project paths each produce the named deterministic performance report
  from the structured metric hook; all assertion limits above are checked in CI.
- The 100-project fixture proves response bytes are bounded independently of member count and that no
  request touches table I/O or shared market files.
- Performance, API-contract, architecture, Ruff, format, Pyright, Playwright, and real-stack gates
  pass.

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

Branch: split into the atomic PR248a–PR248d sequence below.

Git status: in progress; PR248a landed as #412, PR248b landed as #414, PR248c1 landed as #415, PR248c2 landed as #416, PR248d1 landed as #417, and PR248d2 remains queued.

PR: TBD; each atomic step receives its own PR.

Priority: P1 request fan-out and payload control.

Depends on: PR247.

PR248a branch: `feat/hosted-page-view-contract-foundation`.

PR: https://github.com/SergejSchweizer/portfell/pull/412 (landed 2026-08-14).

- Define the versioned Python and TypeScript-independent JSON contract envelope: `contract_version`,
  `project_id`, navigation/workflow projection ETags, compact module status, immutable section revision
  IDs, `sections` availability, and typed size/availability errors. The envelope must not contain
  result rows, matrices, members, credentials, or storage paths.
- Add only the Metadata Builder initial page-view route and its bounded PostgreSQL projection reader.
  It authorizes the named project in one request, returns a byte-stable compact criteria/selection/
  initial-fill summary, and exposes no file or analytical reads.
- Required handoff: a typed route/service port and checked-in fixture builders for ready, filling, empty,
  unauthorized, and deleted projects. Do not migrate React pages or create Univariate/Bivariate/
  Multivariate routes in this PR.

Acceptance for PR248a:

- `GET /projects/{project_id}/views/metadata-builder` returns one versioned envelope with a project-
  scoped ETag and private revalidation headers; `If-None-Match` returns `304` without a body.
- The route uses at most two PostgreSQL statements including RLS binding, performs zero writes and zero
  shared-file reads, and returns `404` for guessed/deleted/cross-user projects before exposing a view.
- Fixtures assert ready, filling, empty, and unavailable sections; contract, route, RLS, ETag,
  architecture, Ruff, format, Pyright, OpenAPI, and real-stack gates pass.

PR248b branch: `feat/hosted-analysis-page-view-contracts`.

PR: https://github.com/SergejSchweizer/portfell/pull/414 (landed 2026-08-14).

- Depend only on PR248a's envelope and add Univariate, Bivariate, and Multivariate compact initial-view
  routes. Each reads authorized workflow/run projections and compact persisted summaries only; large
  result pages, pair rows, matrices, candidates, validation, and performance stay unavailable until a
  later lazy-section route.
- Required handoff: exact section keys and immutable revision IDs for every large section, plus fixtures
  for absent, running, failed, stale, and complete runs. Do not modify React consumers.

Acceptance for PR248b:

- Each route has one compact response below 256 KiB, at most two PostgreSQL statements including RLS,
  no file reads/writes, and deterministic ETags across repeated reads.
- Two-project, stale-run, missing-run, and cross-user fixtures prove authorization and contract shape;
  focused API, contract, architecture, Ruff, format, Pyright, OpenAPI, and real-stack gates pass.

PR248c was split because tabular pagination and indivisible analytical payload limits have different
authorization, transport, and failure contracts. PR248c1 supplies the tabular hand-off; PR248c2 consumes
its revision/cursor contract for matrices and large analytical detail sections.

PR248c1 branch: `feat/hosted-lazy-tabular-sections`.

PR: https://github.com/SergejSchweizer/portfell/pull/415 (landed 2026-08-14).

- Add only authorized lazy pages for Univariate `results` and `selection_results`, Bivariate `results`,
  and Multivariate `components`. Resolve project and stage ownership before reading the named run or
  selection; do not add matrices, candidate detail, validation, performance, or React changes.
- Each page is exactly 200 rows at most and uses a stable opaque cursor bound to the initial-view section
  revision. A changed revision returns `409 section_revision_mismatch`; malformed cursors return
  `409 section_cursor_invalid`; a locked, running, stale, failed, or absent section returns
  `409 section_not_available`.
- Required hand-off: response shape is `{revision, items, total, limit, next_cursor}` and is bounded to
  2 MiB. It is the only pagination/cursor implementation PR248c2 and PR248d may consume.

Acceptance for PR248c1:

- A completed three-item Univariate fixture returns its authorized project-scoped result page, no cursor
  follows its last page, and a 201-item fixture returns 200 items followed by one immutable cursor that
  returns the remaining item without duplicate or omission.
- Guessed project IDs, cross-user project IDs, run IDs from another project, unknown sections, locked
  stages, malformed cursors, and stale cursors return their exact typed outcomes without reading a result
  payload or recomputing analysis.
- API contract snapshot, focused route/contract tests, security/architecture tests, Ruff, format,
  Pyright, and real-stack button gates pass. The initial-page routes remain byte-identical.

PR248c2 branch: `feat/hosted-lazy-matrix-and-detail-sections`.

PR: https://github.com/SergejSchweizer/portfell/pull/416 (landed 2026-08-14).

- Depend only on PR248c1's section revision and cursor envelope. Add authorized lazy routes for
  covariance/correlation matrices, tail-risk scatter, Bivariate summary, and Multivariate summary,
  structure, candidates, candidate detail, risk contributions, income evidence, validation, artifacts,
  and performance. Do not modify page entry or pagination behavior.
- Enforce the 2 MiB encoded section limit before returning a response. An indivisible oversize matrix or
  detail payload returns `413 section_too_large` with `{section, revision}`; it must never be truncated or
  recomputed. Tabular candidate/component data continues to use only PR248c1 pagination.

Acceptance for PR248c2:

- A non-visible matrix/detail section is not read. A visible authorized section is fetched once per
  immutable revision, while stale/unknown revisions, cross-user IDs, failed runs, missing artifacts, and
  oversized fixtures produce their exact typed result without leakage.
- Matrix and detail fixtures prove the 2 MiB measurement uses encoded response bytes and does not cut
  rows, labels, or values. API, contract, security, Ruff, format, Pyright, and real-stack gates pass.

PR248d was split by module entry point. PR248d1 owns Metadata Builder's compact page-view read; PR248d2
owns Univariate/Bivariate/Multivariate page entries and their lazy visible sections. Both retain only
ephemeral controls/tabs locally, cancel obsolete requests, and introduce no second query cache.

PR248d1 branch: `feat/web-metadata-page-view-adoption`.

PR: https://github.com/SergejSchweizer/portfell/pull/417 (landed 2026-08-14).

- Replace the Metadata Builder project's independent criteria and initial-fill reads with exactly one
  `GET /projects/{project_id}/views/metadata-builder` call. Field options and explicit job-progress
  polling remain separate concerns; no statistics page, cache, or server contract changes are allowed.
- On project-change and unmount, abort the obsolete page-view request and never apply its data to another
  project. The view's unavailable initial-fill state renders the existing empty/status state rather than
  throwing a request failure.

Acceptance for PR248d1:

- A project restore makes one Metadata Builder page-view request instead of the former criteria plus
  initial-fill request pair. Project switching cannot display criteria or fill progress from the previous
  project, and an unavailable fill state remains usable.
- Vitest client/component tests, the Metadata Builder Playwright flow, TypeScript strict checks, Web
  production build, Docker image build, and real-stack button gates pass.

PR248d2 branch: `feat/web-statistics-page-view-adoption`.

- Depend only on PR248d1 and PR248c1/c2. Replace statistics-page entry fan-out with each page's compact
  view route and load only the visible tab/section. Preserve local control drafts and cancel requests on
  project/run/tab/metric/route changes. Do not add TanStack Query; PR249 owns that cache migration.

Acceptance for PR248d2:

- Bivariate first entry makes no non-visible matrix/detail request, a visible tab makes exactly one
  revision-bound lazy request, and rapid project/run changes cannot paint stale data. Univariate and
  Multivariate satisfy the same project-isolation and cancellation contract.
- TypeScript strict checks, Vitest, Playwright request-count coverage, Web build, Docker image build,
  API/UI contract checks, and real-stack gates pass.

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

Branch: split into PR249a–PR249c below.

Git status: in progress; PR249a is being prepared.

PR: TBD.

Priority: P1 instant repeat navigation and frontend simplification.

Depends on: PR248.

PR249a branch: `feat/web-query-cache`.

- Add the exact `@tanstack/react-query` dependency, one memory-only application `QueryClient`, canonical
  typed key factories, and the shared retry/stale/garbage-collection policy. Do not migrate consumers,
  add prefetch, or retain persistent browser storage in this PR.
- Required handoff: `queryClient`, `queryTiming`, and `queryKeys` are the only shared cache primitives;
  PR249b must use them rather than constructing any alternate client or key.

Acceptance for PR249a:

- The root renders under exactly one `QueryClientProvider`; completed data defaults to five-minute
  freshness, volatile page data to 15 seconds at consumer selection, unused entries are collected after
  15 minutes, GET retries cap at two with bounded backoff, and mutations never retry automatically.
- Package lockfile, TypeScript strict check, unit coverage of key identity/default policy, production Web
  build, and storage-safety search prove no persistent tenant cache is introduced.

PR249b branch: `refactor/web-query-cache-consumers`.

- Depend only on PR249a. Migrate all production `useResource` server readers, revision counters, and
  global refresh events to the single QueryClient and delete the superseded hook. Commands invalidate
  only exact project/run keys after server success; logout/session invalidation clears memory.

Acceptance for PR249b:

- No production import of `use-resource` remains. Two concurrent consumers with one canonical key make
  one request; project switching never shows another project's page/section; failed writes create no
  optimistic cache state; focused Vitest assertions cover exact invalidations and cancellation.

PR249c branch: `feat/web-query-cache-prefetch`.

- Depend only on PR249b. Prefetch at most one deliberate sidebar destination/page view after selection
  or hover intent, using the canonical project-specific key and ETag revalidation. Do not speculatively
  fetch all workflow pages.

Acceptance for PR249c:

- Warm deliberate navigation uses fresh memory data without a blocking loader, while project/run changes
  cancel obsolete prefetches and cannot expose old tenant data. Playwright request counts prove one
  bounded destination prefetch only.

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

### PR250a. Durable Status-Event Schema

Branch: `feat/hosted-status-event-schema`.

Git status: merged.

PR: [#421](https://github.com/SergejSchweizer/portfell/pull/421).

Delivered the RLS-protected, compact PostgreSQL event catalog and its versioned migration. The
remaining PR250 work is deliberately split below so each change has one reviewable responsibility.

### PR250b. Bounded Durable Status-Event Repository

Branch: `feat/hosted-status-event-repository`.

Git status: in progress.

PR: TBD.

Priority: P1 live status with bounded request load.

Depends on: PR250a.

Scope:

- Add the PostgreSQL adapter that appends compact events and replays an authorized user's events in
  monotonic ID order. Bind the authenticated RLS principal before every operation and enforce a
  maximum replay page of 1,000 rows in the adapter itself.
- Keep this PR transport- and publisher-free: no route, SSE serialization, polling removal, or
  lifecycle call site belongs here.

Acceptance:

- Adapter tests prove RLS binding precedes writes and reads, append writes only the compact catalog
  fields, replay is strictly ordered after a supplied cursor, and negative, zero, or oversized
  bounds fail with the typed validation error.
- Focused Python tests, Ruff, Pyright, and the applicable `GATES.md` checks pass.

### PR250c1. Transactional Workflow-Projection Event Publication

Branch: `feat/hosted-status-event-publication`.

Git status: in progress.

PR: TBD.

Priority: P1 live status with bounded request load.

Depends on: PR250b.

Scope: Make an upsert of the compact PR247 workflow projection report whether it changed under the
same PostgreSQL statement. Publish exactly one event only for a changed projection, from the same
request/worker transaction and with its returned revision. This covers all Uni/Bi/Multivariate
transitions that already refresh this projection. A no-op reconciliation must publish nothing.

Acceptance: Repository and projector tests prove one changed projection produces one event carrying
the revision, no-op/retry produces none, RLS binding precedes both writes, and a failed request rolls
back projection and event together. Focused Python tests, Ruff, Pyright, and applicable gates pass.

### PR250c2. Bootstrap And Metadata Lifecycle Event Publication

Branch: `feat/hosted-lifecycle-status-event-publication`.

Git status: in progress.

PR: TBD.

Priority: P1 live status with bounded request load.

Depends on: PR250c1.

Scope: Publish compact queued, progress, terminal, and metadata-revision events within the existing
bootstrap-job and metadata-lifecycle transaction boundaries. Define logical transition uniqueness so
retries cannot duplicate a logical lifecycle event; refresh workflow projections where required.

Acceptance: Commit paths atomically persist bootstrap/metadata source state and one event; rollback
persists none; worker and repository tests cover queued, running, successful, partial, failed, retry,
and tenant-isolation cases.

### PR250d. Authenticated SSE Replay Transport

Branch: `feat/hosted-status-event-sse`.

Git status: not started.

PR: TBD.

Priority: P1 live status with bounded request load.

Depends on: PR250c1 and PR250c2.

Scope: Add one authenticated FastAPI SSE endpoint over the durable repository with heartbeats,
`Last-Event-ID` replay, typed reset events, tenant filtering, proxy-safe headers, cleanup, and the
two-stream session limit. Events remain compact invalidation hints, not analytical payloads.

Acceptance: API and adversarial tests prove ordered authorized replay, reset on expired/oversized
cursors, 15-second heartbeats, connection cleanup, no cross-user leakage, and bounded resources.

### PR250e. Browser Status-Stream Adoption

Branch: `feat/web-status-event-stream`.

Git status: not started.

PR: TBD.

Priority: P1 live status with bounded request load.

Depends on: PR250d.

Scope: Connect one browser stream per authenticated application session; map received events through
PR249's exact query keys; then remove fixed-interval polling only for states covered by the stream.

Acceptance: Browser tests prove reconnect backoff, bounded key invalidation, no cross-project flash,
status updates without polling, and no application-data requests during a 15-minute idle session.

### PR250. Durable Server-Sent Job And Workflow Updates

Branch: split into PR250a, PR250b, PR250c1, PR250c2, PR250d, and PR250e above.

Git status: in progress (PR250a/b/c1 merged; PR250c2 in progress).

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

### Hosted Simplicity And Interactive Performance Series Completion Gate

This series is complete only after PR246 through PR251 merge in order and the current gates in
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
| PR246 | Worker Admission Control And Interactive Capacity | merged 2026-08-14. PR: https://github.com/SergejSchweizer/portfell/pull/400; commit `2e2663299ae2e7806774176d8e7f261b6aefac60` |
| PR247 | PostgreSQL Navigation Read Model | merged through atomic PRs #401–#410 on 2026-08-14; includes bounded projection reads, reconciliation, lifecycle repair, instrumentation, and deterministic budget evidence. |
| PR248a | Hosted Page-View Contract Foundation | landed 2026-08-14. PR: https://github.com/SergejSchweizer/portfell/pull/412; versioned Metadata Builder page-view envelope, typed unavailable initial-fill state, conditional GET, and OpenAPI contract evidence. |
| PR248b | Hosted Analysis Page-View Contracts | landed 2026-08-14. PR: https://github.com/SergejSchweizer/portfell/pull/414; compact conditional-GET views for Univariate, Bivariate, and Multivariate stage/section metadata. |
| PR248c1 | Hosted Lazy Tabular Sections | landed 2026-08-14. PR: https://github.com/SergejSchweizer/portfell/pull/415; project-authorized 200-row pages with opaque revision-bound cursors. |
| PR248c2 | Hosted Lazy Matrix And Detail Sections | landed 2026-08-14. PR: https://github.com/SergejSchweizer/portfell/pull/416; authorized analytical detail endpoints with immutable revisions and a 2 MiB encoded-response limit. |
| PR248d1 | Web Metadata Page-View Adoption | landed 2026-08-14. PR: https://github.com/SergejSchweizer/portfell/pull/417; Metadata Builder restores criteria and initial-fill state from one compact page-view response. |
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
