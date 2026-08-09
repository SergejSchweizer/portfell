# Backlog

Last reviewed: 2026-08-09

## Table Of Contents

- [Backlog Policy](#backlog-policy)
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

Git status: not started. PR: TBD.

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

Git status: not started. PR: TBD.

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

Git status: not started. PR: TBD.

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

Git status: not started. PR: TBD.

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
  `02:15` with absolute paths and `/usr/bin/flock -n`.
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

Git status: not started. PR: TBD.

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
- PostgreSQL is the primary application database for users, identities, encrypted provider credentials, projects, download provenance, entitlements, selections, analysis runs, and artifact catalogs.
- EODHD keys are encrypted at rest with envelope encryption. The key-encryption key is never stored in Git, PostgreSQL, container images, build artifacts, logs, or GitHub Actions.
- Runtime secrets live outside the repository checkout and are mounted only into services that require them.
- EODHD market observations are stored once in a canonical shared physical store with unique
  dataset/listing/business keys, atomic publication, deterministic hashes, and explicit correction
  semantics.
- A user can see only observations that were returned by an EODHD request executed with that user's own stored key.
- Existing shared observations may prevent a duplicate physical write, but may never create a user entitlement without a successful user-key-backed provider request.
- New observations downloaded by one user do not become visible to another user until that other user performs a successful refresh with their own key.
- Every user analysis is pinned to an immutable User Data Snapshot containing the exact observations and revisions visible to that user.
- Univariate, bivariate, multivariate, portfolio, backtest, and report artifacts are globally deduplicated by exact input hashes and algorithm versions, while visibility is granted only through user-owned analysis runs.
- Hosted analytical code must consume resolved scoped inputs and must never scan unrestricted global Silver or Gold data.
- The local CLI and analytical core remain usable without Google authentication or PostgreSQL through explicit local adapters.
- Public hosting remains blocked until provider licensing, privacy, backup, credential, and security readiness gates pass.

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
