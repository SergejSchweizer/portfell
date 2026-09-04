# Portfell — Authoritative Backlog

Last reviewed: 2026-09-04

## 0. Single executable authority

`BACKLOG.md` is the only executable backlog authority for Portfell. Historical backlog text, old pull-request descriptions and archived planning branches are audit material only when they conflict with this file.

This revision is reconciled against the exact current `main` commit `66d7b7e948bbc58a14688156c3118bc1c8a8eaec` (`show all portfolio performance series`). The immediately preceding Portfolio Selection v2 planning revision is preserved at `c7faa1fabf138ae975da0dcb3f06280f15d77f37`; earlier revisions are preserved at `96ca8745b90b847b5abd05e9c6411a78a47f6aa9` and `c352d788dcb75fb01fc280615d2ef55b781783bb`. None of those superseded plans is executable after this revision.

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
- a checkpoint with a different execution version is ignored before incompatible checkpoint objects are reused;
- Multivariate persists candidate, validation, risk-contribution, performance, structural and decision artifacts;
- the current performance artifact persists instrument cumulative series, candidate portfolio cumulative series and monthly/annual period returns;
- the live Multivariate page renders OOS candidate evidence, all persisted portfolio performance series, allocation, drawdown, risk contribution, structural diagnostics and final-portfolio views;
- the backend accepts `return_risk`, `return_drawdown` and `minimum_risk`, but the current Dash action hard-codes `return_risk` when a portfolio run is submitted.

The active Portfolio Selection v2 work must preserve the single-container architecture, bounded eight-refit production model, process-parallel/tmpfs execution strategy, immutable app-state publication model and persisted-rendering model unless a PR below explicitly changes one of those contracts.

## 2. Frozen end-to-end portfolio-selection workflow

Portfolio Selection v2 is not a manual optimizer picker. It is a deterministic pipeline from one frozen investable universe to either one auditable production-eligible portfolio or an explicit no-portfolio result.

The production workflow is exactly:

```text
Metadata universe
  -> Univariate eligibility selection
  -> successful Bivariate run for that exact selection
  -> choose portfolio objective
  -> construct the frozen allocator × risk-model configuration family
  -> common walk-forward OOS validation
  -> eligibility / warning / stress evaluation
  -> objective ranking + deterministic tie-breaks
  -> winning configuration
  -> full-current-sample refit of that exact configuration
  -> final production portfolio diagnostics
```

The following workflow rules are frozen across PR437–PR459:

1. **Upstream identity is immutable.** Multivariate consumes one persisted Univariate selection and one successful Bivariate run whose `input_ref` matches that exact selection. If the selection changes, downstream Bivariate/Multivariate evidence is stale and cannot be reused as if it belonged to the new selection.
2. **Bivariate is a diagnostic prerequisite, not a hidden optimizer.** This series does not silently remove assets inside Multivariate based on correlation/tail diagnostics. Any asset exclusion requires a new Univariate selection and therefore a new downstream run.
3. **The user chooses an objective, not an allocator.** Production exposes exactly `return_risk`, `return_drawdown`, and `minimum_risk`; default is `return_risk`. There is no production UI control that manually chooses Minimum Variance, ERC, HRP, a covariance specification, or a winner.
4. **Objective is run identity.** The exact requested objective must reach the job request, logical run identity and Decision artifact. A selected objective may never be silently replaced by `return_risk`.
5. **Configurations compete on common OOS evidence.** All rankable configurations use identical chronological test windows and the same information boundary. Full-history performance never enters winner selection.
6. **Eligibility precedes ranking.** Unavailable risk models, failed fits, missing required comparison splits and blocking stress evidence cannot be hidden by a good primary score. Warnings remain visible but are not blockers unless explicitly classified as blocking.
7. **Ranking is deterministic.** The primary objective always dominates. Tie-breaks are median turnover ascending, median HHI ascending, then configuration ID ascending. No weighted composite is introduced.
8. **OOS chooses the model; current full history supplies current weights.** After the winning configuration is selected from OOS evidence, that exact configuration is fitted on the complete current input. Full-sample curves and structure are descriptive evidence only.
9. **Selection evidence and descriptive diagnostics are distinct artifact/UI roles.** OOS scorecards, common-split validation, eligibility and Decision are `selection` evidence. Full-history performance, current allocation, risk contributions, PCA/clusters/structure and matrix stress diagnostics are `descriptive` evidence unless a work order explicitly says otherwise.
10. **No winner means no final portfolio.** A feasible visual fallback may be shown only as `Candidate Preview — not selected`. The UI may label a portfolio `Final Portfolio` only when the persisted Decision is available and production-eligible. An unavailable or ineligible Decision must render an explicit no-production-portfolio state.
11. **No discretionary override in this series.** If the user dislikes the winner, the remedy is to change an upstream selection/policy/objective and rerun the complete pipeline. The production UI does not provide a `pick runner-up` or `force this optimizer` control.
12. **Saving/exporting comes after selection correctness.** `portfolio.snapshot`, PDF and `.portfell` workflows remain deferred until PR459 proves the selection engine itself.

## 3. Current correctness and migration findings

The following findings are verified against the current code and are inputs to the work orders, not optional preferences:

1. `highest_monthly_return` remains a full production candidate although its weights are selected from in-sample calendar-month mean returns; it must be removed from production allocation.
2. Batched walk-forward starts are distributed round-robin across worker batches and worker results are then flattened batch-major. Validation consumes the resulting candidate sets chronologically, so multi-worker execution can associate a refit with the wrong OOS split.
3. `PortfolioCandidate.candidate_id` is fit-specific because its identity includes the fitted risk model and fitted weights. It cannot be the semantic cross-split configuration identity.
4. `PortfolioCandidate` does not persist the fitted `risk_model_id`, so downstream code cannot reconcile a candidate directly to the covariance model that produced it.
5. `ValidationSplit.risk_model_id` is populated from the full-sample model passed into `validate_candidates`, not necessarily from the model used to fit that split's candidate.
6. Current validation assumes method name is identity: candidate lookup, metric lookup and turnover history are keyed by `method`. That becomes incorrect as soon as one allocator exists under more than one risk-model specification.
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
20. Once risk-model-family selection is production, Portfell must not run two independent walk-forward ranking authorities in steady state. The comparison family must become the canonical OOS selection evidence.
21. The current Dash callback accepts an `objective` argument at its boundary but submits Multivariate with hard-coded `objective="return_risk"`; the user therefore cannot execute the three backend objectives through the normal production UI.
22. The current page uses a feasible candidate as a display fallback when no winner exists and passes `winner or display_candidate` into the `Final Portfolio` chart. That is acceptable for diagnostics only if the fallback is never labelled or perceived as a selected final portfolio.

## 4. Global weak-agent execution contract

Only PR437–PR459 below are executable. PR308–PR436 are integrated/retired historical work and must not be reopened as dependencies.

For every active PR:

- start from the exact merged predecessor SHA; stop if the predecessor is not merged;
- record `git status --short --branch` before edits;
- use the exact branch name and Conventional Commit scope shown below;
- change only owned paths plus directly failing focused tests and explicitly named version/persistence synchronization points;
- do not add a new expected-return model, Maximum Sharpe optimizer, Optuna search, Black-Litterman, HERC/NCO, transaction-cost model or structural ranking rule unless explicitly authorized below;
- preserve listing identity `(isin, exchange, code)` everywhere;
- preserve current adjusted-close/return authority and market-source lineage;
- never use `method` as a unique configuration key after PR453;
- no Equal Weight fallback may hide an unavailable optimizer, unavailable risk-model fit or unavailable comparison configuration;
- every persisted semantic change must have deterministic IDs and explicit contract/execution-version synchronization;
- any PR that changes checkpointed Multivariate state must prove an older execution-version checkpoint is ignored;
- process-parallel work must remain deterministic across worker counts; worker scheduling order may never enter artifact identity or financial output;
- no nested process pools are allowed in the risk-model-family comparison; each outer refit worker fits each required risk specification at most once and reuses it across methods;
- OOS selection evidence and full-history descriptive performance must remain explicitly separated; full-sample curves must never enter winner selection;
- production UI may choose the objective but may not manually choose allocator, risk-model specification or winner;
- implementation PRs run focused tests plus `uv run portfell-quality pr`;
- QA PR459 also runs `uv run portfell-quality merge`, browser/REST acceptance and repository `merge-gate` on the exact head;
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

## 5. Portfolio Selection v2 — active PR437–PR459

### PR437 — Re-freeze Portfolio Selection v2 against the current runtime

Branch: `docs/pr437-portfolio-selection-v2-contract`

Commit scope: `docs(pr437-portfolio-selection-v2-current-contract)`

Priority: P0 contract.

Owned paths: `BACKLOG.md` only.

Task: keep this file as compact execution authority based on current `main`, preserve superseded plans by exact SHA, freeze the end-to-end portfolio-selection workflow above and enumerate PR438–PR459 without production code changes.

Acceptance:

- baseline SHA is `66d7b7e948bbc58a14688156c3118bc1c8a8eaec`;
- only PR437–PR459 are executable;
- eight-refit baseline, worker batching, checkpoints, persisted performance artifacts and current Dash behavior are acknowledged;
- the exact 14-configuration family and configuration-key migration are frozen;
- objective selection, evidence-role separation and no-winner semantics are explicit workflow contracts;
- no production source/test behavior changes.

### PR438 — Remove `highest_monthly_return` completely

Branch: `refactor/pr438-remove-highest-monthly-return`

Commit scope: `refactor(pr438-remove-highest-monthly-return)`

Priority: P0 correctness/simplification.

Depends on: PR437.

Owned paths: `src/portfell/multivariate_candidates.py`, directly failing candidate/compute serialization tests, execution-version synchronization in `src/portfell/app_services/multivariate_compute.py`.

Task:

- freeze default production methods to exactly `equal_weight`, `inverse_volatility`, `minimum_variance`, `equal_risk_contribution`, `hierarchical_risk_parity`, `minimum_cvar`;
- delete the dispatcher branch/helpers for `highest_monthly_return`;
- remove dedicated tests/fixtures and all production/test references;
- do not alter mathematics of the remaining six methods.

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

Owned paths: `src/portfell/multivariate_refits.py`, `src/portfell/multivariate_validation.py` only where ordering is consumed, focused refit/order tests, execution-version synchronization.

Task:

- keep current process worker-batching and temporary-file history sharing;
- make each worker result carry its original walk-forward start index;
- reassemble all worker results strictly by canonical `_walk_forward_starts(...)` order before validation or structural walk-forward consumes them;
- preserve maximum eight refits and current start-selection algorithm.

Acceptance:

- fixture with at least four starts and at least two worker batches proves chronological, not batch-major, output;
- every precomputed refit is paired with intended `train_end` and `test_start`;
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
- initial configuration identity is method + portfolio policy + frozen `LW_FULL` design specification; exclude fitted covariance, weights, dates, candidate ID and fitted risk-model ID;
- replace ambiguous validation lineage with explicit configuration ID, fitted candidate ID, full-sample candidate ID, fitted risk-model ID and requested method;
- add configuration ID to `ValidationScenario` and structural walk-forward evidence;
- aggregate scorecards by configuration ID;
- map a winning configuration back to exact current full-sample candidate.

Acceptance:

- at least three refits of one method have different fit candidate/risk IDs but one configuration ID;
- one scorecard aggregates all completed splits for that configuration;
- fitted validation risk-model ID equals the model used by that refit;
- scenario and structural rows reconcile without method-name guessing;
- candidates `v8 -> v9`, validation `v6 -> v7`, structural walk-forward `v1 -> v2`, execution `clean.v3 -> clean.v4`.

### PR441 — Enrich the canonical OOS scorecard

Branch: `refactor/pr441-canonical-oos-scorecard`

Commit scope: `refactor(pr441-canonical-oos-scorecard)`

Priority: P0 evidence.

Depends on: PR440.

Owned paths: `src/portfell/multivariate_validation.py`, focused scorecard tests, execution-version synchronization.

Add exact `CandidateScorecard` fields:

- `median_sharpe_ratio`;
- `median_sortino_ratio`;
- `median_conditional_value_at_risk`;
- `median_absolute_max_drawdown`;
- `median_turnover`;
- `median_herfindahl_index`.

Rules: use completed splits only; unavailable values remain `None`; drawdown is absolute before aggregation; scorecard identity is configuration ID; no winner logic changes.

Acceptance: independent fixtures verify every field and configuration aggregation; validation `v7 -> v8`; execution `clean.v4 -> clean.v5`.

### PR442 — Separate stress warnings from blocking eligibility

Branch: `fix/pr442-stress-warning-eligibility`

Commit scope: `fix(pr442-stress-warning-eligibility)`

Priority: P0 correctness.

Depends on: PR441.

Owned paths: `src/portfell/multivariate_validation.py`, `src/portfell/app_services/multivariate_compute.py`, eligibility tests.

Task:

- persist `available_with_warning` reasons separately from blocking unavailability;
- `cash_flow_evidence_only` remains visible and cannot by itself block production eligibility;
- only unavailable split/scenario evidence creates blocking reasons;
- Decision persists `warnings` and `blocking_reasons` separately.

Acceptance: a configuration whose only stress issue is the distribution-cut warning can still be production-eligible; validation `v8 -> v9`; execution `clean.v5 -> clean.v6`.

### PR443 — Add same-split return/drawdown evidence

Branch: `feat/pr443-return-drawdown-split-metric`

Commit scope: `feat(pr443-return-drawdown-split-metric)`

Priority: P0 objective evidence.

Depends on: PR442.

Owned paths: `src/portfell/multivariate_validation.py`, focused numerical tests, execution-version synchronization.

Task: for each completed split compute `post_cost_return / abs(max_drawdown)` only when drawdown is available and non-zero; aggregate split ratios into `median_return_drawdown_ratio`.

Acceptance: ratio is formed within split before median; zero/unavailable drawdown is unavailable, never epsilon/infinity; validation `v9 -> v10`; execution `clean.v6 -> clean.v7`.

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
- preserve current cost semantics: Sharpe comes from OOS daily path; one-off turnover cost remains represented in post-cost return and turnover;
- Decision persists `objective_metric = median_sharpe_ratio`.

Acceptance: lower-return/higher-Sharpe configuration beats higher-return/lower-Sharpe configuration; execution `clean.v7 -> clean.v8`.

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

Acceptance: each tie-break level has independent fixture; execution `clean.v9 -> clean.v10`.

### PR447 — Remove the legacy standalone scorecard authority

Branch: `chore/pr447-delete-legacy-scorecard`

Commit scope: `chore(pr447-delete-legacy-scorecard)`

Priority: P1 simplification.

Depends on: PR446.

Expected deletion: `src/portfell/scorecard.py` and `tests/test_scorecard.py` if dedicated.

Task: run `git grep` first. If a live production import exists, stop and amend the work order rather than widening the PR. Preserve `evaluation.py`; migrate only unique high-value tests to canonical Multivariate validation.

Acceptance: no production import/reference to retired scorecard; no compatibility wrapper; no financial behavior change beyond removing duplicate authority.

### PR448 — Remove false covariance/correlation return-path stress labels

Branch: `fix/pr448-remove-false-risk-stress-labels`

Commit scope: `fix(pr448-remove-false-risk-stress-labels)`

Priority: P0 model correctness.

Depends on: PR447.

Owned paths: `src/portfell/multivariate_validation.py`, stress tests, execution-version synchronization.

Task: return-path scenarios become exactly `historical`, `seeded_block_bootstrap`, `distribution_cut`. Delete current transformations that scale/deform already aggregated portfolio returns; do not rename them.

Acceptance: persisted return scenarios contain exactly those names; validation `v10 -> v11`; execution `clean.v10 -> clean.v11`.

### PR449 — Add true 25% volatility-up asset-level risk stress

Branch: `feat/pr449-volatility-scale-risk-stress`

Commit scope: `feat(pr449-volatility-scale-risk-stress)`

Priority: P1 risk diagnostics.

Depends on: PR448.

Owned paths: new `src/portfell/multivariate_risk_stress.py`, compute persistence only, numerical/serialization tests.

Contract: `multivariate.risk_stress@v1`. Scenario: `volatility_up_25pct`.

Rules:

- input is canonical full-sample `LW_FULL` covariance plus candidate weights;
- every asset standard deviation is multiplied by 1.25; correlations remain unchanged;
- output contains stressed variance, volatility, status, reason, configuration/candidate and source risk-model identity only;
- do not fabricate returns, drawdown, VaR or CVaR;
- descriptive diagnostic only; no ranking effect.

Acceptance: independent two-asset matrix oracle and serialization fixture pass; execution `clean.v11 -> clean.v12`.

### PR450 — Add true 25% correlation-convergence asset-level risk stress

Branch: `feat/pr450-correlation-convergence-risk-stress`

Commit scope: `feat(pr450-correlation-convergence-risk-stress)`

Priority: P1 risk diagnostics.

Depends on: PR449.

Owned paths: `src/portfell/multivariate_risk_stress.py`, focused numerical tests, persistence/version synchronization.

Scenario: `correlation_convergence_25pct`.

Rules:

- off-diagonal stressed correlation = `0.75 * base_correlation + 0.25`;
- diagonal remains exactly 1;
- preserve original standard deviations and reconstruct covariance;
- validate symmetry, finite values, correlation bounds and PSD; no silent large repair;
- descriptive diagnostic only; no ranking effect.

Acceptance: independent two-asset oracle passes; risk-stress version increments; execution `clean.v12 -> clean.v13`.

### PR451 — Introduce immutable RiskModelSpecification and exact fit-calendar lineage

Branch: `feat/pr451-risk-model-specification`

Commit scope: `feat(pr451-risk-model-specification)`

Priority: P0 foundation.

Depends on: PR450.

Owned paths: new `src/portfell/multivariate_risk_spec.py`, `src/portfell/multivariate_risk_model.py`, `src/portfell/risk_model.py` only where exact fitted-window diagnostics are needed, focused tests, compute version synchronization.

Freeze exactly:

- `LW_FULL`: Ledoit-Wolf, full, log;
- `LW_ROLLING_252`: Ledoit-Wolf, rolling exact 252, log;
- `EWMA_094`: EWMA, full, decay 0.94, log.

Rules:

- readable `spec_key` plus deterministic `spec_id`;
- rolling adapter passes explicit `window_size`;
- rolling-252 is unavailable with fewer than 252 common training observations and is never shortened;
- full-window specs reject irrelevant rolling size;
- risk-model fit persists deterministic `fit_calendar_id` from exact ordered consumed dates, alongside source snapshot/calendar lineage;
- default `LW_FULL` reproduces predecessor covariance on identical input.

Acceptance: risk-model contract `v1 -> v2`; execution `clean.v13 -> clean.v14`; tests prove exact 252 observations and stable fit-calendar identity.

### PR452 — Make candidate/refit identity risk-spec aware

Branch: `refactor/pr452-risk-spec-candidate-identity`

Commit scope: `refactor(pr452-risk-spec-candidate-identity)`

Priority: P0 lineage.

Depends on: PR451.

Owned paths: candidates, refits, validation lineage where required, focused identity tests, execution version.

Task:

- candidate-configuration contract `v1 -> v2` includes `risk_model_spec_id`;
- `CandidateRefitTask` carries explicit `RiskModelSpecification`;
- exclude fitted covariance/risk ID/dates/weights from configuration identity;
- same method/policy under different specs has different configuration IDs;
- same configuration across refits remains stable;
- ValidationSplit persists spec key/id, fitted risk-model ID and fit-calendar ID;
- with only `LW_FULL`, predecessor six-method weights and selection semantics remain unchanged apart from IDs.

Acceptance: candidates `v9 -> v10`, validation `v11 -> v12`, execution `clean.v14 -> clean.v15`.

### PR453 — Eliminate method-as-identity collisions before multi-spec execution

Branch: `fix/pr453-configuration-keyed-validation`

Commit scope: `fix(pr453-configuration-keyed-validation)`

Priority: P0 prerequisite/correctness.

Depends on: PR452.

Owned paths: validation, refit collection shape only where required, stress-return helpers, affected structural/read-model adapters, focused collision tests, execution version.

Task:

- replace every collection whose uniqueness depends on `method` with configuration ID where semantic configurations are tracked;
- explicitly include validation lookup, metric results, previous-weight/turnover state and stress-return lookup;
- method remains display/strategy attribute only;
- duplicate configuration IDs fail deterministically rather than overwrite;
- preserve single-spec numerical behavior.

Acceptance:

- three Minimum Variance configurations survive as three rows per split;
- configs have independent turnover and stress evidence;
- no dict overwrite removes a configuration;
- validation `v12 -> v13`; execution `clean.v15 -> clean.v16`.

### PR454 — Produce common-split 14-configuration risk-model-family OOS evidence

Branch: `feat/pr454-risk-model-family-evidence`

Commit scope: `feat(pr454-risk-model-family-evidence)`

Priority: P0 empirical comparison.

Depends on: PR453.

Owned paths: new narrow comparison coordinator, narrow refit reuse, canonical validation integration, compute phase/checkpoint persistence, workspace progress synchronization, focused comparison/checkpoint tests.

Contract: `multivariate.risk_model_comparison@v1`.

Exact family:

- Equal Weight @ `LW_FULL` — 1;
- Inverse Volatility @ all 3 specs — 3;
- Minimum Variance @ all 3 specs — 3;
- Equal Risk Contribution @ all 3 specs — 3;
- Hierarchical Risk Parity @ all 3 specs — 3;
- Minimum CVaR @ `LW_FULL` — 1;
- total exactly 14.

Rationale: Inverse Volatility consumes covariance diagonal information; Equal Weight does not consume covariance for weights; Minimum CVaR consumes return scenarios rather than covariance, so duplicate spec variants would be allocator-redundant.

Frozen comparison policy:

- minimum training observations 252;
- test window 21;
- maximum refits 8;
- minimum completed splits 2;
- transaction-cost and turnover semantics match production;
- all 14 configs use identical chronological split starts and test windows;
- `LW_FULL` uses all training observations;
- `LW_ROLLING_252` uses exact trailing 252 common observations;
- `EWMA_094` uses all training observations with decay 0.94;
- each outer refit worker fits at most three risk models per split and reuses them; no nested process pools;
- unavailable config/split is persisted, never dropped;
- scoring reuses canonical ValidationSplit/CandidateScorecard builders; no second scoring authority;
- structural metrics remain descriptive/non-ranking;
- this PR is shadow evidence only; Decision authority does not switch yet;
- add dedicated `risk_model_comparison` phase/checkpoint and synchronize progress totals.

Acceptance:

- artifact contains exactly 14 configuration definitions and split evidence;
- split boundaries reconcile across all 14;
- worker count cannot change ordering/output;
- future-row mutation cannot change prior fit evidence;
- at most three risk-model fits per split;
- clean/resumed comparison evidence is identical;
- execution `clean.v16 -> clean.v17`.

### PR455 — Make common-split OOS evidence the production selection authority

Branch: `feat/pr455-oos-risk-model-selection`

Commit scope: `feat(pr455-oos-risk-model-selection)`

Priority: P0 production decision.

Depends on: PR454.

Owned paths: comparison/selection coordinator, `src/portfell/app_services/multivariate_compute.py`, narrow structural-walk-forward reuse, Decision persistence/tests.

Introduce `multivariate.decision@v2`.

Rules:

- only configurations complete on every exact comparison split are rankable; missing common split -> `incomplete_comparison_evidence`;
- primary metrics are PR444/PR445/minimum-risk plus PR446 tie-breaks;
- Equal Weight and Inverse Volatility controls may win;
- no in-sample/full-history score may influence winner;
- after OOS ranking, fit full exact 14-config family on current input using at most three shared risk-model fits;
- full-sample fits are descriptive only and never feed ranking;
- winning configuration must reconcile to exact full-sample fit;
- if winner cannot fit current input, Decision is unavailable/ineligible; no fallback;
- remove duplicate steady-state six-method walk-forward ranking; one canonical OOS selection authority remains;
- structural walk-forward reuses canonical comparison calendar and `LW_FULL` subset only, descriptive/non-ranking.

Decision v2 persists at minimum:

- exact `objective` requested by the user;
- `objective_metric` and sort direction;
- winning configuration ID and fitted candidate ID;
- requested/actual method;
- risk-model spec key/id;
- fitted risk-model ID and fit-calendar ID;
- exact comparison split count;
- ordered tie-break list;
- production eligibility, warnings and blocking reasons;
- canonical risk-stress model `LW_FULL`;
- explicit statement that full-history performance is descriptive/non-selection evidence.

Acceptance:

- restricting specs to `LW_FULL` reproduces predecessor selection semantics;
- alternate specs win only through superior common-split OOS evidence;
- one and only one OOS ranking authority remains;
- every winner joins to exact full-sample configuration/candidate/risk fit;
- requested objective is unchanged from run request to Decision;
- execution `clean.v17 -> clean.v18`.

### PR456 — Reconcile persisted lineage and machine-readable evidence roles

Branch: `refactor/pr456-multivariate-artifact-lineage-v2`

Commit scope: `refactor(pr456-multivariate-artifact-lineage-v2)`

Priority: P0 persistence/read-model correctness.

Depends on: PR455.

Owned paths: `src/portfell/app_services/multivariate_compute.py`, `src/portfell/multivariate_performance.py`, candidate/risk-contribution serialization helpers, structural adapters only where IDs/roles are propagated, artifact tests.

Task:

- candidate rows persist configuration ID, fitted candidate ID, method, spec key/id, fitted risk-model ID and fit-calendar ID;
- validation and return-stress rows carry configuration identity;
- risk-contribution rows carry configuration/spec/risk-model identity;
- performance series/period rows carry configuration/spec identity so same-method configs remain distinguishable;
- exact Decision winner exists as full-sample candidate, risk-contribution set and performance series;
- introduce machine-readable evidence roles: common-split validation/scorecards/comparison/Decision are `selection`; full-history performance/current allocation/risk contributions/structure/matrix risk stress are `descriptive` unless explicitly overridden by contract;
- candidate structural diagnostics remain labelled canonical `LW_FULL` and non-ranking;
- preserve return arithmetic.

Acceptance:

- Decision -> configuration -> candidate -> risk model -> performance -> risk contribution joins without method-name guessing;
- no orphan winner/config IDs;
- all successful 14 full-sample configs may coexist in performance evidence;
- selection vs descriptive evidence role is machine-verifiable and covered by tests;
- no descriptive artifact field is consumed by ranking code;
- execution `clean.v18 -> clean.v19`.

### PR457 — Implement the clean Portfolio Selection workflow in Dash

Branch: `feat/pr457-multivariate-selection-v2-dash`

Commit scope: `feat(pr457-multivariate-selection-v2-dash)`

Priority: P0 product/workflow correctness.

Depends on: PR456.

Owned paths: `src/portfell/dash_app/pages/multivariate.py`, `src/portfell/dash_app/callbacks.py`, Dash contracts/presentation helpers only where needed, focused Dash/browser tests. No financial computation.

Task:

- replace the production action label `Optimize portfolio` with `Run portfolio selection`;
- expose exactly three objective choices: `return_risk`, `return_drawdown`, `minimum_risk`; default `return_risk`;
- remove the current hard-coded `objective="return_risk"` in Multivariate action submission and forward the exact selected objective through the existing service/job boundary;
- queued/running state displays the job's `requested_objective`; completed state displays Decision objective and objective metric;
- changing objective creates/requests the corresponding logically distinct Multivariate run; the UI never silently substitutes another objective;
- show a compact readiness/contract block before execution containing current selection identity/count, matching Bivariate status, selected objective, and frozen comparison policy (14 configs, 252 training observations, 21-observation OOS test, maximum 8 refits);
- disable `Run portfolio selection` until current Univariate selection and matching successful Bivariate evidence are ready; changing upstream selection makes old downstream evidence visibly stale;
- do not expose a production control to choose allocator, risk-model spec, candidate or runner-up manually;
- split the rendered result into two explicit sections:
  - `Selection Evidence`: common-split OOS evidence, objective scorecards, eligibility, warnings/blockers and Decision;
  - `Portfolio Diagnostics`: full-history performance, allocation, drawdown, risk contribution, PCA/clusters/structure and descriptive risk stress;
- OOS plots distinguish same-method configurations by spec/config ID;
- Decision card shows objective, objective metric, method, risk spec, comparison split count, tie-breaks, warnings and blockers;
- performance legend identifies method/spec and exact Decision winner, never method alone;
- full-history charts are visibly labelled descriptive/non-selection evidence;
- a feasible visual fallback is labelled `Candidate Preview — not selected` and must not be passed to a component titled `Final Portfolio`;
- `Final Portfolio` renders only if Decision is available **and** production-eligible; otherwise render explicit `No production-eligible portfolio selected` plus, if useful, a separately labelled preview;
- browser code performs no financial recomputation.

Acceptance:

- browser fixtures execute each of the three objectives and prove the exact value reaches the Multivariate job request; no hard-coded `return_risk` remains in the action path;
- one method under all three risk specs is distinguishable in OOS/performance views;
- changing selection invalidates readiness until matching Bivariate run exists;
- unavailable and production-ineligible Decisions never render a fallback as `Final Portfolio`;
- there is no allocator/spec/manual-winner control in the production selection path;
- section labels and evidence-role labels match persisted semantics;
- all existing supported plots continue rendering persisted artifacts at supported viewports.

### PR458 — Harden durable checkpoint/resume semantics for Selection v2

Branch: `fix/pr458-selection-v2-checkpoint-resume`

Commit scope: `fix(pr458-selection-v2-checkpoint-resume)`

Priority: P0 operational correctness.

Depends on: PR457.

Owned paths: Multivariate checkpoint orchestration in compute/workspace only where required, app-state checkpoint tests, restart/idempotency tests.

Task:

- verify every intermediate object introduced by PR440–PR456 is checkpointed/restored at intended phase;
- exercise resume after candidate/refit preparation, canonical validation, risk-model-family comparison and final selection preparation;
- mismatched execution-version checkpoint is ignored before incompatible objects are reused;
- clean run and resumed run produce identical normalized artifacts and Decision v2;
- repeated resume/publication is idempotent;
- corrupt checkpoint triggers clean recomputation, not partial semantic reuse;
- progress phase/total is monotone and consistent with Multivariate phases.

Acceptance: clean-vs-resumed normalized artifacts reconcile at every supported boundary. Bump to `clean.v20` only if production checkpoint semantics change; otherwise retain `clean.v19`.

### PR459 — Independent Portfolio Selection v2 QA and immutable PASS evidence

Branch: `test/pr459-portfolio-selection-v2-closeout`

Commit scope: `test(pr459-portfolio-selection-v2-closeout)`

Priority: P0 final QA/PASS.

Depends on: PR458.

Owned paths: tests, evidence assembler and synchronized QA docs only. No production fixes; defects require corrective implementation PR before a fresh PR459 run.

Acceptance must independently prove on exact head SHA:

- `highest_monthly_return` absent; exactly six default allocator methods remain;
- multi-worker refit ordering equals canonical chronological starts;
- stable configuration identity vs fit-specific candidate/risk identity across at least three refits;
- scenario, validation and structural lineage reconcile to configuration IDs;
- enriched scorecards match independent numerical oracles;
- warning vs blocking semantics including non-blocking `cash_flow_evidence_only`;
- `return_risk` uses median OOS Sharpe; `return_drawdown` uses same-split ratio before median;
- all deterministic tie-break levels;
- legacy standalone scorecard authority absent;
- return-path stress names exactly historical/bootstrap/distribution-cut;
- independent matrix oracles for volatility-up and correlation-convergence stresses;
- all three immutable risk specs, exact rolling-252 behavior and fit-calendar lineage;
- no method-key overwrite with multiple specs;
- exactly 14 semantic configurations: 1 EW, 3 IV, 3 MinVar, 3 ERC, 3 HRP, 1 MinCVaR;
- at most three risk-model fits per comparison split and full-sample family fit;
- identical common 252-train/21-test/eight-refit schedule across configs;
- future-data mutation cannot change prior fit evidence;
- unavailable/missing common-split config is unrankable;
- fixtures in which each risk spec can win only through OOS evidence;
- exactly one canonical OOS selection authority remains;
- Decision v2 joins to exact full-sample candidate/risk/performance/risk contribution;
- full-history performance is absent from ranking inputs and marked descriptive;
- structural diagnostics are canonical-`LW_FULL` and non-ranking;
- all three UI objectives submit and persist exactly, with default `return_risk` but no hard-coded override;
- objective is part of run/Decision identity and a different objective cannot reuse a Decision as if it were the same request;
- Multivariate readiness requires matching current Selection + Bivariate lineage;
- no manual allocator/spec/winner selector exists in production workflow;
- UI clearly separates `Selection Evidence` from `Portfolio Diagnostics`;
- unavailable/ineligible Decision never renders candidate fallback as `Final Portfolio`;
- clean vs resumed execution is artifact-equivalent and publication-idempotent;
- live Multivariate page renders configuration/spec-aware OOS, performance and Decision evidence without page/console errors;
- `uv run portfell-quality pr`, `uv run portfell-quality merge` and GitHub `merge-gate` pass on exact head;
- produce one immutable sanitized `portfolio-selection-v2` PASS artifact containing exact Git SHA, contract/execution versions, 14-configuration family fingerprint, objective workflow evidence, split policy, numerical-oracle references, restart evidence, browser evidence and gate evidence without credentials, DSNs, private paths or raw market rows.

## 6. Explicitly deferred work — non-executable

The following topics are outside PR437–PR459 and require a new backlog contract after PR459 PASS:

- redesign of `max_weight = 0.20`, including exact-five-holdings degeneracy;
- Maximum Sharpe or any expected-return optimizer;
- Black-Litterman, factor, momentum or regime-conditioned expected-return priors;
- HERC/NCO or additional allocation methods;
- CVaR scenario-generation redesign;
- transaction-cost-aware daily Sharpe reconstruction;
- structural PCA/cluster metrics as ranking objectives or hard constraints;
- Optuna/hyperparameter search;
- saved-portfolio / `portfolio.snapshot` / PDF / `.portfell` export-import workflow;
- Bivariate page visualization redesign, including full-universe heatmaps, tail-risk scatter and pair drill-down;
- changes to Bivariate sampling/read models required by that future visualization series.

## 7. Historical status

PR308–PR436 are integrated/retired historical backlog items. Their detailed history remains recoverable from repository history. Superseded Portfolio Selection v2 plans are audit material only.

The only active execution sequence is PR437 -> ... -> PR459.
