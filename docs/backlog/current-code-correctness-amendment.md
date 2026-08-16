# Current-Code Correctness Amendment

Status: active normative amendment to `BACKLOG.md`, `docs/backlog/plotly-dash-multivariate-optimizer-ui.md`, and `docs/backlog/plotly-dash-professional-plots-weekly-refresh.md`.

Review basis: repository `main` at `69d76a108257a9d07dd8e22a918ae789942afc07` on 2026-08-16. The audit covered the current production Python analytical path, hosted Uni/Bi/Multivariate services and routes, request-scope execution, portfolio/evaluation code, risk models, validation/refits, shared-market scheduling, durable-job infrastructure, Compose/runtime health wiring, and the active PR264-PR276 contracts. Historical backlog files remain evidence only.

This amendment records correctness defects found in the current implementation and makes their remediation mandatory inside the already-planned PR series. It does not add a new browser workflow stage. Where this file is more specific than an older PR264-PR276 task, this file wins.

For each affected PR, the rows below are mandatory additions to that PR's existing single `Tasks / Acceptance` checklist. Implementers must not create a second product checklist or infer alternative behavior.

## Non-negotiable correctness invariants

1. A missing, undefined, statistically unavailable, blocked, or insufficient-observation metric is never represented to a new analytical consumer as a plausible numeric zero. A genuine observed zero remains valid and must be distinguishable from unavailable.
2. Portfolio/optimizer identity is the full listing identity `(isin, exchange, code)`. ISIN-only weight maps are forbidden in the production optimizer path because one ISIN may have multiple listings.
3. A candidate configuration is identified by a stable configuration ID, not by optimizer method alone. Method, risk-model configuration, training window, settings/profile versions, and other frozen dimensions required to distinguish two candidates belong to that identity.
4. Long-running Univariate, Bivariate, and Multivariate calculations are durable worker-owned jobs. The production API/Dash process may enqueue and observe them but may not own them in daemon threads or process-local background tasks.
5. Reading run status is non-mutating. A GET/status projection may never decide that a run is abandoned and write a terminal state as a side effect.
6. Worker ownership is lease/heartbeat/attempt based. A stale worker from an earlier attempt may not overwrite a retried or already-terminal run.
7. Browser/API-visible failure reasons are frozen redacted codes. Raw exception strings, SQL, paths, credentials, provider payloads, or solver internals are server-log detail only.
8. A completed analytical revision is immutable evidence. Recomputing identical logical input either reuses that completed run or writes a new explicit attempt/revision and atomically publishes it; starting a recomputation may not erase the last valid result.
9. Bivariate pair counts, progress denominators, and coverage use the exact pair set that is actually scheduled after all pair-exclusion rules, including same-ISIN cross-listing exclusion.
10. A pairwise-calendar covariance surface is not a coherent portfolio covariance matrix. It may not be described, validated, or consumed as positive-semidefinite risk-model covariance unless one explicit common observation policy produced the complete matrix.
11. Risk-model observation-policy metadata must describe the implementation exactly. Listwise complete-case alignment may not be labeled pairwise.
12. OOS metric names and units are explicit. Daily volatility may not be surfaced or ranked as annualized volatility without the documented annualization transform.
13. Production readiness verifies dependencies required to serve requests; configuration presence alone is not readiness.

## Current-code findings and disposition

### CCR-01 — API-process daemon threads own research calculations — P0

Current path: `hosted_routes_research.py` schedules `service.complete(...)`; `hosted_postgres_request_scope.py` executes after-commit callbacks in `Thread(..., daemon=True)`, with FastAPI `BackgroundTasks` as the no-request-scope fallback. A process restart can therefore terminate active research work, and the API can create process-local concurrent research threads without durable lease ownership.

Required disposition: PR269 freezes the durable research-attempt contract; PR272 migrates Uni/Bi/Multivariate execution to the existing durable worker/job authority; PR275 removes the process-local production execution path; PR276 uses the same durable runs rather than bypassing them.

### CCR-02 — Bivariate restart destroys last valid result — P0

Current path: `HostedBivariateResearchService.start()` derives a deterministic run ID, reuses only `running`, then recreates the run and calls `replace_bivariate_rows(..., ())`. Starting the same completed logical run therefore clears its persisted pair rows before the replacement computation succeeds.

Required disposition: PR268 makes completed-run reuse and atomic replacement explicit; PR276 verifies that a weekly rerun cannot erase a valid Bivariate result.

### CCR-03 — Multivariate status read can falsely fail a valid long run — P0

Current path: `HostedMultivariateResearchService._require_run()` applies a hard 15-minute wall-clock threshold to a `running` record and persists `abandoned_running_run`; status/read projections call this method. The actual process-local computation can continue and later race with the state written by the reader.

Required disposition: PR269 freezes lease/heartbeat/attempt semantics; PR272 removes read-side lifecycle mutation and uses compare-and-set terminal publication by current attempt; PR275 proves restart/slow-run survival.

### CCR-04 — Raw Multivariate exception strings are client-readable — P0 security/contract

Current path: the generic exception branch in Multivariate completion persists `failure_reason=str(error)`, and the run view exposes `failure_reason`.

Required disposition: PR269 defines redacted error codes; PR272 maps exceptions to safe public reasons and logs raw detail only server-side; PR273 persists/exposes only the safe contract; PR274 renders friendly messages from those codes.

### CCR-05 — Unavailable statistics are encoded as zero in several current paths — P0 analytical correctness

Current examples include insufficient Univariate observations, zero-denominator ratio helpers, empty historical-tail cases, zero-variance Pearson cases, insufficient downside/tail pair cases, Bivariate view fallbacks such as `row.get(metric_key, 0.0)`, and unavailable validation records containing zero-valued performance fields.

The defect is not that a numerical zero can never be valid; the defect is that current storage/projection can make unavailable and genuine zero indistinguishable to a downstream selector, optimizer, plot, or audit.

Required disposition: PR267/PR268 stop presentation layers from treating legacy unavailable sentinels as observations; PR269 freezes typed metric availability; PR270/PR271/PR272 consume availability rather than sentinel values; PR273 persists availability; PR274/PR275 prove the final UI renders `Unavailable` plus reason instead of a misleading zero.

### CCR-06 — Bivariate planned pair count can exceed calculated pair count — P1

Current path: `BivariateExecutionPlan.total_pair_count` uses `n*(n-1)/2` over full listing identities, while pair generation defaults to `skip_same_isin=True`. If the same ISIN appears on multiple exchanges/listings, the denominator includes a pair that calculation deliberately omits.

Required disposition: PR268 materializes the exact eligible pair-key set first and derives calculation, paging, progress, and terminal counts from that same set.

### CCR-07 — Bivariate covariance view assembles incompatible pair calendars as one matrix — P0/P1

Current path: pair covariance is calculated on each pair's own shared calendar. `build_covariance_matrix_from_rows()` assembles those values into one square matrix and repeatedly writes pair-calendar variances onto the diagonal. Such a display can be non-PSD and its diagonal can depend on which pair supplied the last variance; determinant/eigenvalue diagnostics can therefore imply a coherent covariance model that was never estimated.

Required disposition: PR268 treats this as a pairwise covariance surface with explicit per-pair coverage, removes synthesized coherent-matrix claims/diagnostics, or separately computes a true common-calendar diagnostic under one frozen policy. The Multivariate risk model may never consume the pairwise display surface as its covariance estimate.

### CCR-08 — Legacy portfolio/evaluation code collapses full listing identity to ISIN — P0

Current path: `evaluation.py` and substantial parts of `portfolio.py` construct/validate/index weights by `str(isin)` even though returns and newer risk/candidate code use `(isin, exchange, code)`. Two exchange listings sharing one ISIN can therefore receive an ambiguous/repeated weight and be double counted or overwritten.

Required disposition: PR269 freezes canonical full listing identity; PR271 refactors any legacy portfolio/evaluation functions reused by production candidates to full identity before reuse; PR272 validation/refit uses full identity end to end; PR273 persists full identities; PR274 disambiguates duplicate-ISIN listings in the audit UI.

### CCR-09 — Walk-forward validation collapses future candidate configurations by method — P0 planned-optimizer blocker

Current path: `multivariate_validation.py` creates `by_method = {candidate.method: candidate ...}`. The current candidate set happens to have one candidate per method, but PR271/PR272 explicitly plan method x risk-model x training-window configurations. Multiple `maximum_sharpe` or `minimum_variance` candidates would overwrite each other in that map and OOS results could be attached to the wrong configuration.

Required disposition: PR269 freezes `configuration_id`; PR271 emits it; PR272 joins validation jobs/results only by configuration ID; PR273/PR274 preserve and display it.

### CCR-10 — Walk-forward validation has policy and unit hazards — P0/P1

Current path: validation reports split volatility as the standard deviation of daily test returns while planned optimizer/UI language uses OOS annualized volatility. `_walk_forward_starts()` also divides by `maximum_refit_count - 1` in the subsampling branch, so a policy value of `1` can divide by zero. The current minimum-training-observation default must also not silently become the production evidence threshold without an explicit versioned policy decision.

Required disposition: PR269 validates walk-forward policy bounds and freezes units/annualization semantics plus the production minimum-history rule; PR272 implements/tests those semantics and never mixes daily with annualized risk in ranking/plots.

### CCR-11 — Risk-model observation-policy metadata does not match implementation — P1 audit correctness

Current path: `risk_model.py` labels the missing-observation policy `pairwise_common_date_intersection`, but `_aligned_matrix()` computes one intersection across all selected listing series before covariance estimation, i.e. listwise complete-case alignment. Pairwise missing counts are diagnostics, not the covariance alignment policy.

Required disposition: PR269/PR271 rename/freeze the actual policy, persist exact observation count/date range and separate pair-coverage diagnostics, and add a three-listing staggered-calendar regression fixture.

### CCR-12 — Production health check can report healthy without proving dependency readiness — P1 operations

Current path: `hosted_runtime.health_check()` validates runtime configuration and returns `status=ok`; current Compose health uses that command. Database connectivity and request-serving readiness are therefore not proven by this health result.

Required disposition: PR275 separates liveness from readiness. Readiness must exercise the minimal dependencies required by the final FastAPI+Dash app, including a bounded PostgreSQL readiness query and initialized application routing; dependency failure returns non-ready.

## PR267 amendment — Univariate availability correctness

Additional rows for the existing PR267 `Tasks / Acceptance` checklist:

- [ ] Treat a legacy Univariate row with a non-success `availability_reason` as unavailable for every affected plot/hover/filter even if persisted numeric columns contain `0.0`; do not convert a valid measured zero into unavailable. Add insufficient-history and genuine-zero fixtures.
- [ ] Do not use a legacy zero-valued unavailable Sharpe/Sortino/tail metric to determine a Pareto/frontier class. Until the typed PR269 metric contract exists, unavailable values are excluded from that comparison with an explicit visible reason.
- [ ] Record an integration follow-up hook for PR269/PR273 typed per-metric availability so PR275 can remove all legacy sentinel interpretation from the production Dash path.

Ownership amendment: PR267 may add presentation/read-model availability adapters and tests but may not introduce a second financial formula implementation.

## PR268 amendment — Bivariate run, pair-set, and covariance correctness

Additional rows for the existing PR268 `Tasks / Acceptance` checklist:

- [ ] Make repeated start of an already-complete identical Bivariate logical input reuse the immutable completed result by default. If an explicit recompute/version requires new calculation, keep the previous complete revision readable until the new revision publishes atomically; failure preserves the last complete rows.
- [ ] Build one deterministic eligible pair-key set after same-ISIN exclusion and all other frozen pair rules. `total_pair_count`, progress, actual calculation, result count, pagination, and completion assertions derive from exactly this set. A fixture with the same ISIN on two exchanges proves the omitted same-ISIN pair is not counted.
- [ ] Introduce typed per-metric Bivariate availability in the Dash/read adapter. Missing row, insufficient observations, zero variance, empty downside set, and empty tail set are explicit reasons; no `row.get(..., 0.0)`-style default may enter a matrix/hover as an observed metric.
- [ ] Redefine the current covariance display as a `Pairwise Covariance Surface` unless one coherent common-calendar matrix is explicitly estimated. The pairwise surface shows per-cell shared-observation coverage and does not publish determinant/eigenvalue/PSD claims. A three-listing mismatched-calendar fixture proves display order cannot change diagonal semantics.
- [ ] Add an architecture/contract test proving the Multivariate risk-model builder cannot consume the pairwise Bivariate display surface as its production covariance estimator.

Ownership amendment: PR268 Agent B may edit only the targeted Bivariate correctness paths needed for these rows: `hosted_bivariate_service.py`, Bivariate execution-plan/pair-set projection, Bivariate view builders, and focused tests. PR267 does not edit those paths.

## PR269 amendment — shared analytical correctness contracts

PR269 must freeze these contracts before PR270/PR271 branch:

- [ ] Define canonical `ListingIdentity` using exactly `isin`, `exchange`, `code`; optimizer weights/candidates/validation/decisions may not use bare ISIN as a unique key. Serialization order and lexical tie-break are frozen.
- [ ] Define typed metric availability with at least `status`, optional finite `value`, `reason`, and `observation_count` where applicable. Freeze reasons for insufficient observations, zero denominator/variance, empty downside/tail sample, unavailable upstream metric, blocked upstream, and legacy unavailable sentinel. An available measured `0.0` remains representable.
- [ ] Define stable `configuration_id` over optimizer method, risk-model configuration, training window, objective/settings/profile/algorithm versions needed to distinguish candidates. Validation/result maps keyed only by `method` are forbidden.
- [ ] Define durable `ResearchJobAttempt`/equivalent semantics for Uni/Bi/Multivariate with logical run ID, attempt/generation ID, lease owner, lease expiry, heartbeat, terminal state, and compare-and-set publication. A stale attempt cannot publish over a newer/terminal attempt.
- [ ] Freeze safe browser-visible research failure codes and a separate server-only diagnostic/correlation field. Canonical public serialization rejects raw exception text, secrets, SQL, filesystem paths, and provider payloads.
- [ ] Freeze walk-forward policy validation: positive training/test/step sizes, explicit behavior for `maximum_refit_count=None`, `1`, and `>=2`, versioned production minimum-history rule, and explicit daily-versus-annualized units for every OOS metric.
- [ ] Freeze the risk-model observation-policy registry using names that match implementation exactly; listwise and pairwise policies are distinct IDs and cannot be mislabeled.

Next wave may not branch until these contracts and deterministic fixtures pass.

## PR270 amendment — selector consumes typed evidence

Additional rows for the existing PR270 `Tasks / Acceptance` checklist:

- [ ] Selector consumes PR269 typed metric availability. An unavailable metric is never coerced to zero for eligibility, Pareto rank, clustering representative tie-break, or rejection evidence.
- [ ] Full `ListingIdentity` is preserved through eligibility/Pareto/redundancy. A deterministic fixture contains two listings with the same ISIN on different exchanges and proves no collapse/overwrite occurs.
- [ ] Every rejection references the exact full listing identity and typed reason/metric evidence; legacy sentinel values cannot become a selection advantage.

## PR271 amendment — full-identity solvers and exact risk-model policy

Additional rows for the existing PR271 `Tasks / Acceptance` checklist:

- [ ] All production solver/candidate input and output weights are keyed by PR269 `ListingIdentity`. Before reusing any existing `portfolio.py` or `evaluation.py` function that accepts/returns ISIN-only weights, refactor that function to full identity or put it behind a tested non-production legacy boundary; silent ISIN conversion is forbidden.
- [ ] Candidate records contain stable `configuration_id`; two candidates sharing one method but using different risk model or training window coexist without overwrite.
- [ ] Correct `risk_model.py` observation-policy metadata to match the actual covariance alignment algorithm. Persist exact aligned observation count/date range and separate pair-coverage diagnostics. A three-listing staggered-calendar test asserts the declared policy and resulting sample.
- [ ] No candidate with an unavailable/fallback synthetic risk model is labeled as an estimated production risk model. Baseline/fallback status is explicit in the candidate evidence.
- [ ] Duplicate-ISIN/multi-exchange numerical fixture proves all listing weights are unique by full identity, finite, satisfy bounds, and sum to exactly the configured portfolio total within the named numerical tolerance; each listing contributes once to portfolio return/risk.

Ownership amendment: PR271 Agent B owns the targeted legacy portfolio/evaluation refactor required for production reuse. PR270 may not edit those files.

## PR272 amendment — durable execution, validation identity, and safe terminal publication

Additional rows for the existing PR272 `Tasks / Acceptance` checklist:

- [ ] Move production Univariate, Bivariate, and Multivariate heavy completion work off API daemon threads/FastAPI process-local background tasks and onto the existing durable worker/job authority using PR269 attempt/lease contracts. API/Dash start commands only create/reuse durable logical runs and enqueue/reuse work.
- [ ] Worker heartbeat/lease renewal is explicit for long-running stages. Expired work may be reclaimed, but a stale earlier attempt is rejected by compare-and-set when publishing progress or terminal result.
- [ ] Status/read paths are pure reads. Remove the Multivariate 15-minute read-side abandonment mutation; abandonment/recovery is worker/lease-owned. A fake-clock test advances beyond 15 minutes while heartbeat remains valid and proves status stays running.
- [ ] Generic Uni/Bi/Multivariate exceptions map to PR269 redacted public failure codes. A test raises an exception containing a fake token, SQL fragment, and filesystem path and proves none is present in persisted/public failure reason.
- [ ] Walk-forward scheduling, candidate lookup, worker payload, result join, ranking, final refit, and DecisionArtifact linkage use `configuration_id`, never optimizer method alone. A fixture validates two same-method candidates with different model/window simultaneously.
- [ ] Validate `maximum_refit_count` before scheduling and handle the explicitly frozen `1` policy without division by zero. Invalid policies fail before work starts with a typed reason.
- [ ] Compute/store OOS volatility and other risk metrics in the exact PR269 units. If ranking/plot label says annualized, annualization is performed once with the frozen convention and tested against a hand-constructed deterministic series.
- [ ] Production minimum-history eligibility is versioned and explicit; diagnostic short windows may not silently qualify as production OOS winner evidence unless the frozen policy allows them.
- [ ] Final validation/refit uses full `ListingIdentity` end to end and asserts no ISIN-only weight map crosses the production boundary.

Ownership amendment: PR272 Agent A owns the cross-cutting research-run executor migration and `multivariate_validation.py` changes. PR273 does not edit calculation/execution code.

## PR273 amendment — persistence preserves correctness metadata

Additional rows for the existing PR273 `Tasks / Acceptance` checklist:

- [ ] Persist and read full listing identity for weights, candidates, rejections, contributions, and decision evidence. Bare ISIN is descriptive only, never the persistence key.
- [ ] Persist typed metric availability/reason/observation metadata without converting unavailable values to zero. Legacy artifacts are adapted explicitly and retain `legacy_unavailable` provenance.
- [ ] Persist stable `configuration_id` and expose it in candidate/validation lazy sections so same-method configurations remain distinct after restart.
- [ ] Persist safe public failure code plus attempt/generation/lease outcome needed for audit. Raw exception detail is never part of browser-readable run/decision bytes.
- [ ] GET/read endpoints are proven non-mutating, including reads of old running attempts. Repeated reads produce byte-identical stored run/decision state.

## PR274 amendment — Decision Audit exposes corrected semantics

Additional rows for the existing PR274 `Tasks / Acceptance` checklist:

- [ ] Uni/Bi/Multivariate plot/view adapters consume PR269/PR273 typed availability. `Unavailable` plus reason replaces legacy sentinel zero; a true zero is still shown as zero.
- [ ] Where an ISIN has multiple listings, hover/table/weight labels include enough full listing identity (`code.exchange` at minimum) to disambiguate them.
- [ ] Portfolio candidate/validation figures distinguish same-method configurations by model/window/configuration identity and never merge traces/hover evidence by method name alone.
- [ ] Bivariate covariance UI uses the corrected PR268 pairwise-surface terminology/coverage and does not show coherent-matrix diagnostics unless a separately estimated common-calendar matrix backs them.
- [ ] Static registry/E2E fixtures include constant series, insufficient observations, empty downside/tail sample, duplicate-ISIN cross-exchange listings, and same-method multi-configuration candidates.

## PR275 amendment — production cutover must remove process-local research ownership

Additional rows for the existing PR275 `Tasks / Acceptance` checklist:

- [ ] Final production `app` process contains no daemon-thread/FastAPI-background-task path that owns Uni/Bi/Multivariate heavy calculations. Start endpoints enqueue/reuse durable worker work only; architecture test fails if production routes invoke heavy `complete()` through process-local background execution.
- [ ] Separate liveness and readiness. Liveness proves the Python process/runtime is alive; readiness performs bounded validation of initialized FastAPI+Dash routing and required PostgreSQL connectivity. Database-unreachable fixture returns non-ready while liveness remains independently meaningful.
- [ ] Restart the `app` container during an active deterministic research run and prove the worker-owned run survives, progress remains queryable after restart, and exactly one terminal result/winner is published.
- [ ] Simulate worker loss/lease expiry/reclaim and prove a stale worker cannot overwrite the reclaimed attempt's progress or terminal result.
- [ ] Final four-page E2E proves unavailable-vs-zero, full listing identity, same-method configuration identity, and safe failure reasons survive the React deletion/base-path cutover.

## PR276 amendment — weekly cycle must use the corrected durable authority

Additional rows for the existing PR276 `Tasks / Acceptance` checklist:

- [ ] Weekly orchestrator starts/reuses the same durable Uni/Bi/Multivariate logical runs and worker attempts used by explicit browser/API commands; it never calls a private process-local calculation shortcut.
- [ ] Identical completed Bivariate input is reused and remains readable; an explicit recompute/version cannot clear the previous completed rows before atomic publication.
- [ ] Cycle resume after app restart and after worker lease reclaim creates no duplicate analytical run, configuration, winner, DecisionArtifact, or market business key.
- [ ] Per-project terminal counts use exact Bivariate eligible pair counts after same-ISIN filtering. The two-project fixture includes a duplicate-ISIN cross-exchange case.
- [ ] Cycle summary reports safe typed failure/blocked codes only. Injected exception detail containing secret-looking text never appears in the summary or browser-readable status.

## Correctness completion gate

PR264-PR276 are not complete until one clean final production-like SHA proves all existing gates plus these regression fixtures:

- duplicate-ISIN fixture: two listings share an ISIN but differ in exchange/code; no selection, weight, return, contribution, pair count, persistence record, hover, or audit row collapses them;
- unavailable-metric fixture: insufficient history, constant returns, zero denominator, no downside observations, and empty tail sample remain typed unavailable rather than plausible zero, while a genuinely observed zero remains visible as zero;
- Bivariate restart fixture: complete result -> repeated start/recompute -> injected failure leaves the prior complete revision readable and unchanged;
- Bivariate pair-set fixture: planned total equals actual scheduled/completed pairs after same-ISIN exclusions;
- pairwise-covariance fixture: three listings with different calendars cannot produce misleading coherent-matrix determinant/eigenvalue claims from pairwise estimates;
- risk-model-calendar fixture: declared observation policy matches actual aligned sample and is stable under reversed listing order;
- candidate-identity fixture: at least two candidates use the same optimizer method with different risk-model/window configuration IDs and both receive the correct independent OOS results;
- walk-forward-policy fixture: `maximum_refit_count=1` follows the frozen valid behavior or is rejected deterministically before scheduling, never divides by zero; reported volatility units match labels/ranking;
- slow-run fake-clock fixture: a healthy heartbeating run remains running beyond the former 15-minute threshold and a read cannot mutate it;
- restart/lease fixture: app restart does not kill worker-owned research; worker loss can be reclaimed; stale attempt cannot overwrite current result;
- failure-redaction fixture: secret/path/SQL-like raw exception text is absent from public/persisted failure reason and cycle summary;
- readiness fixture: PostgreSQL unavailable => app not ready, while liveness has its separately defined result.

Forbidden at final completion:

- ISIN-only production optimizer weight keys;
- method-only candidate identity;
- unavailable-as-zero analytical consumption;
- `row.get(metric, 0.0)` fallbacks for missing Bivariate analytical values;
- coherent covariance diagnostics over independently pairwise-aligned covariance cells;
- API daemon thread or process-local background ownership of heavy research calculations;
- run-state mutation from GET/status/read paths;
- raw `str(exception)` in public/persisted failure reasons;
- stale-attempt terminal overwrite;
- configuration-only production readiness.
