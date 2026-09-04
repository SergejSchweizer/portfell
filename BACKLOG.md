# Portfell — Authoritative Backlog

Last reviewed: 2026-09-04

## 0. Single executable authority

`BACKLOG.md` is the only executable backlog authority for Portfell. Historical backlog text, old pull-request descriptions and archived planning branches are audit material only when they conflict with this file.

This revision is reconciled against the exact current `main` commit `66d7b7e948bbc58a14688156c3118bc1c8a8eaec` (`show all portfolio performance series`). A GitHub compare against `main` showed that commit to be the current head at review time. The immediately preceding Portfolio Selection v2 planning revision is preserved at `96ca8745b90b847b5abd05e9c6411a78a47f6aa9`; the older draft is preserved at `c352d788dcb75fb01fc280615d2ef55b781783bb`. Neither superseded plan is executable after this revision.

`GATES.md` remains the authority for repository quality and merge requirements. The current Python coverage floor must not be reduced as part of this series.

The labels `PR437` ... `PR459` below are backlog work-order identifiers. GitHub assigns the actual pull-request number when an implementation branch is opened; agents must not assume that the GitHub number equals the work-order identifier.

## 1. Current production architecture — frozen baseline

Portfell is a single-user Python application with exactly one Application container plus PostgreSQL. Plotly Dash exposes exactly four analytical pages: `/metadata`, `/univariate`, `/bivariate`, `/multivariate`. Internal module boundaries remain explicit but are composed in one process.

Market observations are consumed through the current market-data gateway. Multivariate derives returns from the quote rows supplied by that gateway; no PostgreSQL daily-return fallback may be reintroduced.

Current Multivariate baseline at the review SHA:

- `multivariate.candidates@v7`;
- `multivariate.validation@v5`;
- `multivariate.risk_model@v1`;
- `multivariate.structural_walk_forward@v1`;
- `MULTIVARIATE_EXECUTION_VERSION = multivariate_execution.clean.v1`;
- production covariance estimator is Ledoit-Wolf with `window_policy=full`;
- production candidate methods are `equal_weight`, `inverse_volatility`, `minimum_variance`, `equal_risk_contribution`, `hierarchical_risk_parity`, `minimum_cvar`, `highest_monthly_return`;
- walk-forward policy is minimum training 100 observations, test window 21 observations, maximum 8 refits, minimum 2 completed splits, transaction-cost rate 0.0005;
- refits are process-parallel, worker-batched and exchange the large immutable return history through a temporary local file;
- Multivariate has durable resumable checkpoints keyed by dataset digest and execution version;
- a checkpoint with a different execution version is ignored before unpickling its semantic payload;
- Multivariate persists candidate, validation, risk-contribution, performance, structural and decision artifacts;
- the current performance artifact persists instrument cumulative series, candidate portfolio cumulative series and monthly/annual period returns;
- the live Multivariate page renders OOS candidate evidence, all persisted portfolio performance series, allocation, drawdown, risk contribution, structural diagnostics and final-portfolio views.

The active Portfolio Selection v2 work must preserve the single-container architecture, bounded eight-refit production model, process-parallel/tmpfs execution strategy, immutable app-state publication model and persisted-rendering model unless a PR below explicitly changes one of those contracts.

## 2. Current correctness and migration findings

The following findings are verified against the current code and are inputs to the work orders, not optional preferences:

1. `highest_monthly_return` remains a full production candidate although its weights are selected from in-sample calendar-month mean returns; it must be removed from production allocation.
2. Batched walk-forward starts are distributed round-robin across worker batches and worker results are then flattened batch-major. Validation consumes the resulting candidate sets chronologically, so multi-worker execution can associate a refit with the wrong OOS split.
3. `PortfolioCandidate.candidate_id` is fit-specific because its identity includes the fitted risk model and fitted weights. It cannot be the semantic cross-split configuration identity.
4. `PortfolioCandidate` does not persist the fitted `risk_model_id`, so downstream code cannot reconcile a candidate directly to the covariance model that produced it.
5. `ValidationSplit.risk_model_id` is populated from the full-sample model passed into `validate_candidates`, not necessarily from the model used to fit that split's candidate.
6. Current validation assumes method name is identity: `by_method`, metric maps and turnover history are keyed by `method`. That becomes incorrect as soon as Minimum Variance, ERC, HRP or Inverse Volatility exist under more than one risk-model specification.
7. Current stress-return assembly is also keyed by `method`, so multiple configurations sharing a method would overwrite one another.
8. Scorecards aggregate by fit-specific `candidate_id`; repeated refits of one semantic allocator configuration therefore cannot reliably form one multi-split scorecard.
9. Stress `available_with_warning` reasons are merged with blocking reasons. `distribution_cut` deliberately emits `cash_flow_evidence_only`, which can make an otherwise feasible candidate production-ineligible.
10. `return_risk` divides a compounded test-window return by a daily volatility statistic instead of using the already-computed same-split Sharpe evidence.
11. `return_drawdown` divides separately aggregated return and drawdown statistics instead of forming the return/drawdown ratio within each split before aggregation.
12. `covariance_perturbation` and `correlation_convergence` currently deform already aggregated portfolio return paths. They are not covariance-matrix or correlation-matrix stresses and must not retain those names.
13. `src/portfell/scorecard.py` remains a separate legacy walk-forward/ranking authority beside canonical Multivariate validation and decision code.
14. The generic risk-model estimator supports rolling `window_size`, but the Multivariate adapter does not pass one. Generic rolling behavior also shortens to the available history, which is not acceptable for an exact `LW_ROLLING_252` specification.
15. The current risk-model artifact records the source snapshot calendar identity but not a deterministic identity for the exact dates actually used by a training-window fit. Multi-spec/refit lineage needs an exact fit-calendar identity.
16. Structural walk-forward currently zips training windows to the refitted candidate-set sequence, so it inherits the refit ordering defect and uses fit-specific candidate identity.
17. Current performance and risk-contribution rows distinguish candidates by `candidate_id` and `method` only. Once one method exists under several risk specs, all persisted/read-model joins must become configuration/spec aware.
18. The live Multivariate page has recently become substantially richer and now shows all portfolio performance series. Winner highlighting or legend grouping by method name will be ambiguous after risk-model diversification.
19. Checkpoint payloads contain Python dataclass objects from intermediate Multivariate phases. Every semantic change to checkpointed objects must synchronize `MULTIVARIATE_EXECUTION_VERSION`, and the expensive future risk-model-family comparison needs its own explicit checkpoint boundary.
20. Once risk-model-family selection is production, Portfell must not run two independent walk-forward ranking authorities in steady state. The comparison family must become the canonical OOS selection evidence; the preceding six-method path may survive only as deliberately labelled migration/shadow evidence in the PR that switches authority.

## 3. Global weak-agent execution contract

Only PR437–PR459 below are executable. PR308–PR436 are integrated/retired historical work and must not be reopened as dependencies. The superseded PR437–PR458 planning text at `96ca8745b90b847b5abd05e9c6411a78a47f6aa9` is audit material only.

For every active PR:

- start from the exact merged predecessor SHA; stop if the predecessor is not merged;
- record `git status --short --branch` before edits;
- use the exact branch name and Conventional Commit scope shown below;
- change only owned paths plus directly failing focused tests and explicitly named version/persistence synchronization points;
- do not add a new expected-return model, Maximum Sharpe optimizer, Optuna search, Black-Litterman, HERC/NCO, transaction-cost model or structural ranking rule unless explicitly authorized below;
- preserve listing identity `(isin, exchange, code)` everywhere;
- preserve the current adjusted-close/return authority and market-source lineage;
- never use `method` as a unique configuration key after PR453;
- no Equal Weight fallback may hide an unavailable optimizer, unavailable risk-model fit or unavailable comparison configuration;
- every persisted semantic change must have deterministic IDs and explicit contract/execution-version synchronization;
- any PR that changes checkpointed Multivariate state must prove an older execution-version checkpoint is ignored;
- process-parallel work must remain deterministic across worker counts; worker scheduling order may never enter artifact identity or financial output;
- no nested process pools are allowed in the risk-model-family comparison; each outer refit worker fits each required risk specification at most once and reuses it across methods;
- OOS selection evidence and full-history descriptive performance must remain explicitly separated; full-sample curves must never enter winner selection;
- implementation PRs run focused tests plus `uv run portfell-quality pr`;
- QA PR459 also runs `uv run portfell-quality merge`, browser/REST acceptance and the repository `merge-gate` on the exact head;
- do not bypass a failed, skipped, cancelled or zero-step gate.

Dependency graph:

```text
PR437
  -> PR438
  -> PR439
  -> PR440
  -> PR441
  -> PR442
  -> PR443
  -> PR444
  -> PR445
  -> PR446
  -> PR447
  -> PR448
  -> PR449
  -> PR450
  -> PR451
  -> PR452
  -> PR453
  -> PR454
  -> PR455
  -> PR456
  -> PR457
  -> PR458
  -> PR459(QA/PASS)
```

## 4. Portfolio Selection v2 — active PR437–PR459

### PR437 — Re-freeze Portfolio Selection v2 against the current runtime

Branch: `docs/pr437-portfolio-selection-v2-contract`

Commit scope: `docs(pr437-portfolio-selection-v2-current-contract)`

Priority: P0 contract.

Owned paths: `BACKLOG.md` only.

Task: keep this file as the compact execution authority based on current `main`, preserve superseded plans by exact SHA, enumerate the current-code findings above and freeze PR438–PR459 without production code changes.

Acceptance:

- baseline SHA is `66d7b7e948bbc58a14688156c3118bc1c8a8eaec`;
- actual planning branch name matches this work order;
- only PR437–PR459 are executable;
- eight-refit baseline, worker batching, checkpoints, persisted performance artifacts and current Dash behavior are acknowledged;
- the newly inserted configuration-key migration PR and the exact 14-configuration family are frozen;
- no production source/test behavior changes.

### PR438 — Remove `highest_monthly_return` completely

Branch: `refactor/pr438-remove-highest-monthly-return`

Commit scope: `refactor(pr438-remove-highest-monthly-return)`

Priority: P0 correctness/simplification.

Depends on: PR437.

Owned paths: `src/portfell/multivariate_candidates.py`, directly failing candidate/compute serialization tests, execution-version synchronization in `src/portfell/app_services/multivariate_compute.py`.

Task:

- freeze default production methods to exactly `equal_weight`, `inverse_volatility`, `minimum_variance`, `equal_risk_contribution`, `hierarchical_risk_parity`, `minimum_cvar`;
- delete the dispatcher branch and helpers for `highest_monthly_return`;
- remove dedicated tests/fixtures and all production/test references;
- do not alter the mathematics of the remaining six methods.

Acceptance:

- `git grep "highest_monthly_return" -- src tests` returns no matches;
- candidate contract `v7 -> v8`;
- execution version `clean.v1 -> clean.v2`;
- current default risk-model candidate count is exactly six.

### PR439 — Restore chronological walk-forward refit ordering

Branch: `fix/pr439-chronological-refit-order`

Commit scope: `fix(pr439-chronological-refit-order)`

Priority: P0 correctness.

Depends on: PR438.

Owned paths: `src/portfell/multivariate_refits.py`, `src/portfell/multivariate_validation.py` only where the ordering contract is consumed, focused refit/order tests, execution-version synchronization.

Task:

- keep the current process worker-batching and temporary-file history sharing;
- make each worker result carry its original walk-forward start index;
- reassemble all worker results strictly by canonical `_walk_forward_starts(...)` order before validation or structural walk-forward consumes them;
- preserve the current maximum of eight refits and current start-selection algorithm.

Acceptance:

- deterministic fixture with at least four starts and at least two worker batches proves chronological, not batch-major, output;
- every precomputed refit is paired with the intended `train_end` and `test_start`;
- single-worker and multi-worker outputs are identical in order and fitted weights;
- validation contract `v5 -> v6`;
- execution version `clean.v2 -> clean.v3`.

### PR440 — Introduce stable configuration, fit and risk-model lineage

Branch: `fix/pr440-stable-candidate-configuration-lineage`

Commit scope: `fix(pr440-stable-candidate-configuration-lineage)`

Priority: P0 correctness/lineage.

Depends on: PR439.

Owned paths: `src/portfell/multivariate_candidates.py`, `src/portfell/multivariate_validation.py`, `src/portfell/multivariate_refits.py` only where needed, `src/portfell/multivariate_structural_walk_forward.py`, compute serialization/version synchronization, focused lineage tests.

Task:

- introduce `multivariate.candidate_configuration@v1`;
- add `candidate_configuration_id` and fitted `risk_model_id` to `PortfolioCandidate`;
- retain `candidate_id` as fit-specific identity;
- for this PR configuration identity is method + portfolio policy + frozen current `LW_FULL` design specification; it excludes fitted covariance, fitted weights, fit dates, fit `candidate_id` and fitted `risk_model_id`;
- replace ambiguous validation lineage with explicit `candidate_configuration_id`, `fitted_candidate_id`, `full_sample_candidate_id`, `fitted_risk_model_id` and requested method;
- add `candidate_configuration_id` to `ValidationScenario` as well as `ValidationSplit`;
- group split/scenario aggregation and scorecards by configuration ID, not fitted candidate ID;
- keep fit-specific IDs available for audit;
- add configuration ID to structural walk-forward evidence and reconcile it to the exact fitted candidate;
- bump structural walk-forward contract because its persisted lineage changes;
- map a winning configuration back to the exact current full-sample fitted candidate.

Acceptance:

- at least three refits of one method have different fit candidate/risk IDs but one configuration ID;
- one scorecard aggregates all completed splits for that configuration;
- `ValidationSplit.fitted_risk_model_id` equals the model embedded in the refitted candidate;
- scenario rows join to the same configuration without method-name guessing;
- structural walk-forward joins to the intended refit after multi-worker ordering;
- candidates `v8 -> v9`, validation `v6 -> v7`, structural walk-forward `v1 -> v2`, execution `clean.v3 -> clean.v4`.

### PR441 — Enrich the canonical OOS scorecard

Branch: `refactor/pr441-canonical-oos-scorecard`

Commit scope: `refactor(pr441-canonical-oos-scorecard)`

Priority: P0 evidence.

Depends on: PR440.

Owned paths: `src/portfell/multivariate_validation.py`, focused scorecard tests, compute execution-version synchronization.

Add exact `CandidateScorecard` fields:

- `median_sharpe_ratio`;
- `median_sortino_ratio`;
- `median_conditional_value_at_risk`;
- `median_absolute_max_drawdown`;
- `median_turnover`;
- `median_herfindahl_index`.

Rules:

- use completed splits only;
- unavailable values remain `None` and are omitted from their metric's median input; never substitute zero;
- drawdown is converted to absolute magnitude before aggregation;
- scorecard identity is `candidate_configuration_id`;
- no winner/objective logic changes in this PR.

Acceptance: independent fixtures verify every field and configuration aggregation; validation `v7 -> v8`; execution `clean.v4 -> clean.v5`.

### PR442 — Separate stress warnings from blocking eligibility

Branch: `fix/pr442-stress-warning-eligibility`

Commit scope: `fix(pr442-stress-warning-eligibility)`

Priority: P0 correctness.

Depends on: PR441.

Owned paths: `src/portfell/multivariate_validation.py`, `src/portfell/app_services/multivariate_compute.py`, eligibility tests.

Task:

- persist `available_with_warning` scenario reasons separately from blocking unavailability;
- `cash_flow_evidence_only` remains visible as a warning and cannot by itself block production eligibility;
- only unavailable split/scenario evidence creates blocking reasons;
- Decision document persists `warnings` and `blocking_reasons` separately.

Acceptance: a feasible configuration whose only stress issue is the distribution-cut warning can be production-eligible when all other requirements pass; validation `v8 -> v9`; execution `clean.v5 -> clean.v6`.

### PR443 — Add same-split return/drawdown evidence

Branch: `feat/pr443-return-drawdown-split-metric`

Commit scope: `feat(pr443-return-drawdown-split-metric)`

Priority: P0 objective evidence.

Depends on: PR442.

Owned paths: `src/portfell/multivariate_validation.py`, focused numerical tests, execution-version synchronization.

Task: for each completed split compute `post_cost_return / abs(max_drawdown)` only when max drawdown is available and non-zero; aggregate those split-level ratios into `CandidateScorecard.median_return_drawdown_ratio`.

Acceptance:

- ratio is formed within each split before median aggregation;
- zero or unavailable drawdown produces unavailable ratio, never epsilon or infinity;
- no objective switch occurs in this PR;
- validation `v9 -> v10`; execution `clean.v6 -> clean.v7`.

### PR444 — Make `return_risk` use median OOS Sharpe

Branch: `refactor/pr444-return-risk-oos-sharpe`

Commit scope: `refactor(pr444-return-risk-oos-sharpe)`

Priority: P0 decision correctness.

Depends on: PR443.

Owned paths: decision logic in `src/portfell/app_services/multivariate_compute.py`, focused decision tests.

Task:

- `return_risk` primary score is exactly `median_sharpe_ratio`;
- remove compounded-return/daily-volatility ratio from ranking;
- unavailable Sharpe is unrankable;
- preserve current cost semantics for this series: Sharpe comes from the OOS daily path, while one-off turnover cost remains represented in post-cost return and turnover;
- Decision persists `objective_metric = median_sharpe_ratio`.

Acceptance: a lower-return/higher-Sharpe configuration beats a higher-return/lower-Sharpe configuration; execution `clean.v7 -> clean.v8`.

### PR445 — Make `return_drawdown` use median same-split ratio

Branch: `refactor/pr445-return-drawdown-oos-ratio`

Commit scope: `refactor(pr445-return-drawdown-oos-ratio)`

Priority: P0 decision correctness.

Depends on: PR444.

Owned paths: Multivariate decision logic and focused decision tests.

Task: set `return_drawdown` primary score exactly to `median_return_drawdown_ratio`; delete ratio-of-aggregate-return-to-aggregate-drawdown ranking logic.

Acceptance: independent fixture proves same-split-before-median semantics; Decision persists `objective_metric = median_return_drawdown_ratio`; execution `clean.v8 -> clean.v9`.

### PR446 — Freeze deterministic stability tie-breaks

Branch: `refactor/pr446-stability-tiebreaks`

Commit scope: `refactor(pr446-stability-tiebreaks)`

Priority: P1 deterministic selection.

Depends on: PR445.

Owned paths: Multivariate decision logic and focused ordering tests.

Frozen ordering:

1. primary objective score descending;
2. median turnover ascending;
3. median HHI ascending;
4. `candidate_configuration_id` ascending.

Missing secondary metrics rank worse than available values. Primary score always dominates; no weighted composite is allowed.

Acceptance: each tie-break level has an independent fixture; execution `clean.v9 -> clean.v10`.

### PR447 — Remove the legacy standalone scorecard authority

Branch: `chore/pr447-delete-legacy-scorecard`

Commit scope: `chore(pr447-delete-legacy-scorecard)`

Priority: P1 simplification.

Depends on: PR446.

Expected deletion: `src/portfell/scorecard.py` and `tests/test_scorecard.py` if that test file remains dedicated to the module.

Task: run local `git grep` first. If a live production import exists, stop and amend the work order rather than silently widening this PR. Preserve `evaluation.py`; migrate only unique high-value tests to canonical Multivariate validation.

Acceptance: no production import/reference to retired scorecard; no compatibility wrapper; no financial behavior change beyond removal of duplicate dead authority.

### PR448 — Remove false covariance/correlation return-path stress labels

Branch: `fix/pr448-remove-false-risk-stress-labels`

Commit scope: `fix(pr448-remove-false-risk-stress-labels)`

Priority: P0 model correctness.

Depends on: PR447.

Owned paths: `src/portfell/multivariate_validation.py`, stress tests, execution-version synchronization.

Task: return-path stress scenarios become exactly `historical`, `seeded_block_bootstrap`, `distribution_cut`. Delete the current transformations that scale/deform already aggregated portfolio returns; do not rename those transformations.

Acceptance: persisted return-scenario rows contain exactly the three allowed names; validation `v10 -> v11`; execution `clean.v10 -> clean.v11`.

### PR449 — Add a true 25% volatility-up asset-level risk stress

Branch: `feat/pr449-volatility-scale-risk-stress`

Commit scope: `feat(pr449-volatility-scale-risk-stress)`

Priority: P1 risk diagnostics.

Depends on: PR448.

Owned paths: new `src/portfell/multivariate_risk_stress.py`, compute persistence only, numerical/serialization tests.

Contract: `multivariate.risk_stress@v1`.

Scenario: `volatility_up_25pct`.

Rules:

- input is canonical full-sample `LW_FULL` covariance plus candidate weights;
- every asset standard deviation is multiplied by 1.25;
- covariance entries therefore scale consistently while correlations remain unchanged;
- output contains stressed variance, volatility, status, reason, configuration/candidate identity and source risk-model identity only;
- do not fabricate returns, drawdown, VaR or CVaR;
- diagnostic only; no ranking effect.

Acceptance: independent two-asset matrix oracle and serialization fixture pass; execution `clean.v11 -> clean.v12`.

### PR450 — Add a true 25% correlation-convergence asset-level risk stress

Branch: `feat/pr450-correlation-convergence-risk-stress`

Commit scope: `feat(pr450-correlation-convergence-risk-stress)`

Priority: P1 risk diagnostics.

Depends on: PR449.

Owned paths: `src/portfell/multivariate_risk_stress.py`, focused numerical tests, compute persistence/version synchronization.

Scenario: `correlation_convergence_25pct`.

Rules:

- each off-diagonal stressed correlation equals `0.75 * base_correlation + 0.25`;
- diagonal remains exactly 1;
- preserve original asset standard deviations and reconstruct covariance;
- validate symmetry, finite values, correlation bounds and positive-semidefinite status; do not silently apply a large matrix repair;
- persist convergence strength 0.25;
- diagnostic only; no ranking effect.

Acceptance: independent two-asset oracle passes; risk-stress algorithm/contract version is incremented; execution `clean.v12 -> clean.v13`.

### PR451 — Introduce immutable RiskModelSpecification and exact fit-calendar lineage

Branch: `feat/pr451-risk-model-specification`

Commit scope: `feat(pr451-risk-model-specification)`

Priority: P0 foundation for estimator comparison.

Depends on: PR450.

Owned paths: new `src/portfell/multivariate_risk_spec.py`, `src/portfell/multivariate_risk_model.py`, `src/portfell/risk_model.py` only where exact fitted-window diagnostics are required, focused specification/adapter tests, compute version synchronization.

Freeze exactly three specifications:

- `LW_FULL`: estimator `ledoit_wolf`, window `full`, return type `log`;
- `LW_ROLLING_252`: estimator `ledoit_wolf`, window `rolling`, exact window size 252, return type `log`;
- `EWMA_094`: estimator `ewma`, window `full`, decay 0.94, return type `log`.

Rules:

- each specification has readable `spec_key` plus deterministic `spec_id`;
- rolling requires a positive exact window and the adapter passes `window_size` into `estimate_risk_model`;
- `LW_ROLLING_252` is unavailable with fewer than 252 common training observations; it is never silently shortened;
- full-window specs reject an irrelevant rolling window size;
- risk-model fit persists deterministic `fit_calendar_id` derived from the exact ordered dates actually consumed by that fit, while retaining source snapshot/calendar lineage separately;
- default `LW_FULL` reproduces predecessor covariance numerically on identical input;
- risk-model artifact persists spec key/id, exact estimator parameters, fit calendar, date range and observation count.

Acceptance: risk-model contract `v1 -> v2`; execution `clean.v13 -> clean.v14`; independent tests prove exact 252 observations and stable fit-calendar identity.

### PR452 — Make candidate/refit identity risk-spec aware

Branch: `refactor/pr452-risk-spec-candidate-identity`

Commit scope: `refactor(pr452-risk-spec-candidate-identity)`

Priority: P0 lineage.

Depends on: PR451.

Owned paths: `src/portfell/multivariate_candidates.py`, `src/portfell/multivariate_refits.py`, validation lineage only where required, focused identity tests, compute version synchronization.

Task:

- candidate-configuration contract `v1 -> v2` and include `risk_model_spec_id`;
- `CandidateRefitTask` carries an explicit `RiskModelSpecification`; comparison/refit code may not depend on an implicit default specification;
- exclude fitted covariance, fitted risk-model ID, fit dates and fitted weights from configuration identity;
- same method/policy under different risk specs has different configuration IDs even when weights happen to match;
- same configuration across refits remains stable;
- ValidationSplit persists design spec key/id plus fitted risk-model ID and fit-calendar ID;
- with only `LW_FULL` enabled, predecessor six-method weights and winner semantics remain unchanged apart from IDs.

Acceptance: candidates `v9 -> v10`, validation `v11 -> v12`, execution `clean.v14 -> clean.v15`.

### PR453 — Eliminate method-as-identity collisions before multi-spec execution

Branch: `fix/pr453-configuration-keyed-validation`

Commit scope: `fix(pr453-configuration-keyed-validation)`

Priority: P0 prerequisite/correctness.

Depends on: PR452.

Owned paths: `src/portfell/multivariate_validation.py`, `src/portfell/multivariate_refits.py` only where collection shape must change, stress-return helpers, directly affected structural/read-model adapters, focused collision tests, execution-version synchronization.

Task:

- replace every collection whose uniqueness currently depends on `method` with `candidate_configuration_id` where semantic configurations are being tracked;
- this explicitly includes validation candidate lookup, metric result lookup, previous-weight/turnover state and portfolio return/stress lookup;
- method remains a display/strategy attribute, never a unique key;
- detect duplicate configuration IDs and fail deterministically rather than overwriting one row;
- preserve current one-config-per-method behavior numerically when only `LW_FULL` is passed.

Acceptance:

- three Minimum Variance configurations with one shared method name survive validation as three distinct rows per split;
- the three configs have independent turnover histories and stress evidence;
- no dict overwrite can remove a configuration;
- single-spec predecessor fixtures remain numerically identical;
- validation `v12 -> v13`; execution `clean.v15 -> clean.v16`.

### PR454 — Produce common-split 14-configuration risk-model-family OOS evidence

Branch: `feat/pr454-risk-model-family-evidence`

Commit scope: `feat(pr454-risk-model-family-evidence)`

Priority: P0 empirical comparison.

Depends on: PR453.

Owned paths: a new narrow risk-model-family/comparison coordinator, narrow refit reuse, canonical validation integration, `src/portfell/app_services/multivariate_compute.py` phase/checkpoint persistence, workspace progress synchronization, focused comparison/checkpoint tests.

Contract: `multivariate.risk_model_comparison@v1`.

Exact semantic configuration family:

- Equal Weight @ `LW_FULL` — 1 configuration;
- Inverse Volatility @ `LW_FULL`, `LW_ROLLING_252`, `EWMA_094` — 3 configurations;
- Minimum Variance @ all 3 risk specs — 3 configurations;
- Equal Risk Contribution @ all 3 risk specs — 3 configurations;
- Hierarchical Risk Parity @ all 3 risk specs — 3 configurations;
- Minimum CVaR @ `LW_FULL` — 1 configuration;
- total = exactly 14 configurations.

Rationale for the family boundary:

- Inverse Volatility consumes covariance diagonal information, so risk-spec variation is economically meaningful and cheap once the three risk matrices are already fitted;
- Equal Weight does not consume a risk model for its weights, so duplicate spec variants would be semantically redundant;
- Minimum CVaR weights consume return scenarios rather than covariance; duplicate risk-spec variants would repeat the same allocator while merely changing descriptive risk metrics, so only canonical `LW_FULL` is allowed.

Frozen comparison policy:

- minimum training observations = 252;
- test window = 21;
- maximum refits = 8;
- minimum completed splits = 2;
- transaction-cost rate and turnover semantics equal current production;
- all 14 configurations use exactly the same canonical chronological split starts and test windows;
- `LW_FULL` uses all observations available in that training split;
- `LW_ROLLING_252` uses exactly the trailing 252 common training observations;
- `EWMA_094` uses all training observations with decay 0.94;
- each outer refit worker fits at most three risk models for a split and reuses each fitted artifact across all methods that consume it;
- do not create nested process pools;
- an unavailable risk model/configuration/split is persisted explicitly and never dropped;
- comparison scoring reuses canonical `ValidationSplit` and `CandidateScorecard` metric builders; no second scoring formula/authority is created;
- structural metrics remain non-ranking and alternate-spec Structure-v2 is not recomputed;
- in this PR the family runs as shadow/comparison evidence only; the existing Decision winner is not switched yet;
- add a dedicated `risk_model_comparison` Multivariate phase and durable checkpoint after this expensive evidence is complete;
- synchronize `MULTIVARIATE_PHASES` and workspace progress total with the new phase.

Acceptance:

- artifact contains exactly 14 configuration definitions and their split evidence;
- common split boundaries reconcile across all 14;
- chronological ordering is identical with one or many workers;
- a future-row mutation cannot change any prior fit/config/split evidence;
- instrumentation proves at most three risk-model fits per split, not one per candidate;
- clean vs resumed execution from the new comparison checkpoint yields identical normalized comparison evidence;
- execution `clean.v16 -> clean.v17`.

### PR455 — Make 14-configuration common-split OOS evidence the production selection authority

Branch: `feat/pr455-oos-risk-model-selection`

Commit scope: `feat(pr455-oos-risk-model-selection)`

Priority: P0 production decision.

Depends on: PR454.

Owned paths: comparison/selection coordinator, `src/portfell/app_services/multivariate_compute.py`, narrow structural-walk-forward reuse, Decision persistence/tests.

Introduce Decision document contract `multivariate.decision@v2`.

Rules:

- only configurations complete on every exact comparison split are rankable; missing any common split yields `incomplete_comparison_evidence`;
- primary objective metrics are exactly the PR444/PR445/minimum-risk rules and PR446 tie-breaks;
- Equal Weight and Inverse Volatility controls may win;
- no in-sample/full-history score may influence the winner;
- after OOS ranking, fit the full exact 14-configuration family on current full input using at most three shared full-sample risk-model fits;
- persist those full-sample fits for descriptive comparison/UI, but do not feed their performance back into ranking;
- the winner must reconcile to the exact full-sample fit of the winning configuration;
- if the winning configuration cannot be fitted on full current input, return an unavailable/ineligible Decision; no Equal Weight fallback;
- once Decision v2 is authoritative, remove duplicate steady-state six-method walk-forward ranking execution. The 14-config family becomes canonical OOS selection evidence rather than a permanent second ranking path;
- structural walk-forward reuses the canonical comparison calendar and the `LW_FULL` subset only; it remains diagnostic and non-ranking.

Decision v2 persists at minimum:

- `winning_candidate_configuration_id`;
- `winning_candidate_id`;
- requested method and actual method;
- `risk_model_spec_key` and `risk_model_spec_id`;
- fitted `risk_model_id` and `fit_calendar_id`;
- `objective_metric` plus sort direction;
- exact comparison split count;
- ordered tie-break list;
- production eligibility, warnings and blocking reasons;
- canonical common risk-stress model identified as `LW_FULL`;
- explicit statement that full-history performance is descriptive/non-selection evidence.

Acceptance:

- restricting available specs to `LW_FULL` reproduces predecessor selection semantics;
- alternate specs can win only through superior common-split OOS evidence;
- one and only one OOS ranking authority remains after this PR;
- every Decision winner joins to its exact full-sample configuration/candidate/risk fit;
- execution `clean.v17 -> clean.v18`.

### PR456 — Reconcile persisted candidate/performance/risk/structure lineage

Branch: `refactor/pr456-multivariate-artifact-lineage-v2`

Commit scope: `refactor(pr456-multivariate-artifact-lineage-v2)`

Priority: P0 persistence/read-model correctness.

Depends on: PR455.

Owned paths: `src/portfell/app_services/multivariate_compute.py`, `src/portfell/multivariate_performance.py`, candidate/risk-contribution serialization helpers, structural artifact adapters only where IDs are propagated, artifact tests.

Task:

- candidate rows persist configuration ID, fitted candidate ID, method, risk-spec key/id, fitted risk-model ID and fit-calendar ID;
- validation and return-stress rows carry the same configuration identity;
- risk-contribution rows carry configuration/spec/risk-model identity because contributions depend on the fitted covariance model;
- performance portfolio series and period-return rows carry configuration/spec identity and remain distinguishable for multiple configs sharing one method;
- introduce an explicit performance document contract/version if needed so the new join fields are machine-verifiable;
- exact Decision v2 winner must exist as a full-sample candidate, risk-contribution set and performance series;
- candidate structural diagnostics, where present, are evaluated against/labeled with canonical `LW_FULL` common diagnostic risk model and remain non-ranking;
- preserve current cumulative-performance and period-return arithmetic.

Acceptance:

- one lineage test joins Decision -> configuration -> fitted candidate -> risk model -> performance -> risk contribution without method-name guessing;
- no orphan winner/configuration IDs;
- all 14 full-sample configurations that fit successfully can coexist in persisted performance evidence;
- full-history descriptive performance is clearly labelled non-selection evidence;
- execution `clean.v18 -> clean.v19`.

### PR457 — Update the live Multivariate page for configuration/spec-aware evidence

Branch: `feat/pr457-multivariate-selection-v2-dash`

Commit scope: `feat(pr457-multivariate-selection-v2-dash)`

Priority: P1 product/UI correctness.

Depends on: PR456.

Owned paths: `src/portfell/dash_app/pages/multivariate.py`, presentation helpers only as needed, focused Dash/browser tests. No financial computation.

Task:

- OOS plots distinguish configurations sharing a method but using different risk specs;
- hover/legend expose method + risk-spec key and a short configuration identifier;
- Decision card shows risk-model spec, objective metric, comparison split count, warnings and blocking reasons;
- performance legend identifies method/spec and highlights the exact persisted Decision v2 winner by configuration/candidate identity, never method name alone;
- label full-history performance as descriptive evidence and OOS scorecards as selection evidence;
- current no-winner display remains explicit and cannot promote a visual fallback into the Decision;
- existing structural, risk-contribution, allocation, drawdown and final-portfolio views continue rendering persisted artifacts;
- browser code performs no financial recomputation.

Acceptance: deterministic Dash fixtures cover one method under `LW_FULL`, `LW_ROLLING_252` and `EWMA_094`; exact winner is highlighted by ID; all current supported plots render at supported viewports.

### PR458 — Harden durable checkpoint/resume semantics for Selection v2

Branch: `fix/pr458-selection-v2-checkpoint-resume`

Commit scope: `fix(pr458-selection-v2-checkpoint-resume)`

Priority: P0 operational correctness.

Depends on: PR457.

Owned paths: Multivariate checkpoint orchestration in `src/portfell/app_services/multivariate_compute.py` and `src/portfell/app_services/workspace.py` only where required, app-state checkpoint tests, focused restart/idempotency tests.

Task:

- verify every intermediate object introduced by PR440–PR456 is checkpointed/restored at the intended phase;
- specifically exercise resume after candidate/refit preparation, canonical validation, risk-model-family comparison and final selection preparation;
- checkpoint whose execution version differs from current version is ignored before incompatible pickled dataclasses are reused;
- clean run and resumed run produce identical normalized artifacts and Decision v2;
- repeated resume/publication remains idempotent and does not duplicate immutable artifacts;
- corrupt checkpoint payload causes clean recomputation rather than partial semantic reuse;
- progress phase/total is monotone and consistent with `MULTIVARIATE_PHASES`.

Acceptance: clean-vs-resumed artifact hashes or canonical normalized documents reconcile at every supported resume boundary. Bump to `clean.v20` only if this PR changes production checkpoint semantics; if it is test-only, retain `clean.v19` and record that as evidence.

### PR459 — Independent Portfolio Selection v2 QA and immutable PASS evidence

Branch: `test/pr459-portfolio-selection-v2-closeout`

Commit scope: `test(pr459-portfolio-selection-v2-closeout)`

Priority: P0 final QA/PASS.

Depends on: PR458.

Owned paths: tests, evidence assembler and synchronized QA documentation only. No production fixes; discovered defects require a corrective implementation PR inserted before a fresh PR459 run.

Acceptance must independently prove on the exact head SHA:

- `highest_monthly_return` absent from `src` and `tests`; exactly six default methods remain;
- multi-worker refit ordering equals canonical chronological starts;
- stable configuration identity vs fit-specific candidate/risk identity across at least three refits;
- scenario, validation and structural lineage reconcile to configuration IDs;
- scorecards aggregate multiple completed splits and every enriched metric matches an independent oracle;
- stress warnings vs blocking semantics, including non-blocking `cash_flow_evidence_only`;
- `return_risk` uses median OOS Sharpe and `return_drawdown` uses same-split ratio before median;
- every deterministic tie-break level;
- legacy standalone scorecard authority absent;
- return-path stress names exactly historical/bootstrap/distribution-cut;
- independent matrix oracles for 25% volatility-up and 25% correlation-convergence stresses;
- all three immutable risk specifications, exact rolling-252 behavior and exact fit-calendar lineage;
- no method-key overwrite with multiple specs;
- exactly 14 semantic configurations: 1 Equal Weight, 3 Inverse Volatility, 3 Minimum Variance, 3 ERC, 3 HRP and 1 Minimum CVaR;
- at most three risk-model fits per comparison split and per full-sample family fit;
- identical common 252-start/21-test/eight-refit schedule across all configs;
- future-data mutation cannot change prior fit evidence;
- unavailable/missing common-split configuration is unrankable;
- fixtures in which `LW_FULL`, `LW_ROLLING_252` and `EWMA_094` can each win only through OOS evidence;
- exactly one canonical OOS selection authority remains after Decision v2 migration;
- Decision v2 lineage joins to exact full-sample candidate, risk model, performance and risk-contribution artifacts;
- full-history performance is persisted for successful configurations but absent from ranking inputs;
- structural diagnostics are explicitly canonical-`LW_FULL` diagnostics and absent from ranking;
- clean vs resumed execution is artifact-equivalent and publication-idempotent;
- live Multivariate page renders configuration/spec-aware OOS, performance and Decision evidence at supported viewports with no page/console errors;
- `uv run portfell-quality pr`, `uv run portfell-quality merge` and GitHub `merge-gate` pass on the exact head;
- produce one immutable sanitized `portfolio-selection-v2` PASS artifact containing exact Git SHA, contract/execution versions, 14-configuration family fingerprint, split policy, numerical-oracle references, restart evidence, browser evidence and gate evidence without credentials, DSNs, private paths or raw market rows.

## 5. Explicitly deferred work — non-executable

The following topics are deliberately outside PR437–PR459 and require a new backlog contract after PR459 PASS:

- redesign of `max_weight = 0.20`, including the exact-five-holdings degeneracy where a fully invested long-only five-asset portfolio is forced to 20% each;
- Maximum Sharpe or any other expected-return optimizer;
- Black-Litterman, factor, momentum or regime-conditioned expected-return priors;
- HERC/NCO or additional allocation methods;
- CVaR scenario-generation redesign;
- transaction-cost-aware daily Sharpe reconstruction;
- structural PCA/cluster metrics as ranking objectives or hard constraints;
- Optuna/hyperparameter search;
- saved-portfolio/PDF/`.portfell` export/import workflow;
- Bivariate page visualization redesign, including full-universe heatmaps, tail-risk scatter and pair drill-down;
- changes to Bivariate sampling/read models required by that future visualization series.

## 6. Historical status

PR308–PR436 are integrated/retired historical backlog items. Their detailed historical work remains recoverable from repository history. The Portfolio Selection v2 plan at `96ca8745b90b847b5abd05e9c6411a78a47f6aa9` is superseded by this revision.

The only active execution sequence is PR437 -> ... -> PR459.