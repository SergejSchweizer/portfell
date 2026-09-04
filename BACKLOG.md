# Portfell — Authoritative Backlog

Last reviewed: 2026-09-04

## 0. Single executable authority

`BACKLOG.md` is the only executable backlog authority for Portfell. Historical backlog text, old pull-request descriptions and archived planning branches are audit material only when they conflict with this file.

This backlog was rebased against `main` commit `66d7b7e948bbc58a14688156c3118bc1c8a8eaec` (`show all portfolio performance series`). The complete pre-rewrite backlog remains auditable at that exact commit. The earlier Portfolio Selection v2 draft at `c352d788dcb75fb01fc280615d2ef55b781783bb` is superseded by this revision and must not be executed.

`GATES.md` remains the authority for repository quality, coverage and merge requirements.

## 1. Current production architecture — frozen baseline

Portfell is a single-user Python application with exactly one Application container plus PostgreSQL. Plotly Dash exposes exactly four analytical pages: `/metadata`, `/univariate`, `/bivariate`, `/multivariate`. Internal module boundaries remain explicit but are composed in one process.

Market observations are consumed from the pinned local/shared market-data path. Multivariate derives returns from the supplied quote rows; no PostgreSQL daily-return fallback may be reintroduced.

Current Multivariate baseline at the review SHA:

- `multivariate.candidates@v7`;
- `multivariate.validation@v5`;
- `multivariate.risk_model@v1`;
- `MULTIVARIATE_EXECUTION_VERSION = multivariate_execution.clean.v1`;
- production covariance estimator is Ledoit-Wolf with `window_policy=full`;
- production candidate methods are `equal_weight`, `inverse_volatility`, `minimum_variance`, `equal_risk_contribution`, `hierarchical_risk_parity`, `minimum_cvar`, `highest_monthly_return`;
- walk-forward policy is minimum training 100 observations, test window 21 observations, maximum 8 refits, minimum 2 completed splits, transaction cost rate 0.0005;
- Multivariate has durable resumable checkpoints keyed by dataset digest and execution version;
- Multivariate persists candidate, validation, risk-contribution, performance, structural and decision artifacts;
- the live Multivariate page renders OOS candidate evidence, cumulative performance, drawdown, allocation, risk contribution, structural diagnostics and final-portfolio views.

The active Portfolio Selection v2 work must preserve the current single-container architecture, bounded eight-refit execution model, checkpoint/restart semantics and persisted-rendering model unless a PR below explicitly changes one of them.

## 2. Current correctness findings — stop-the-line inputs to this series

The following findings are based on the current code and are not optional design preferences:

1. `highest_monthly_return` remains a full production candidate although it is a noisy in-sample mean-return heuristic and is not appropriate as a production allocation method.
2. Batched walk-forward refits are distributed round-robin across workers and flattened by worker batch, while validation consumes precomputed candidate sets in chronological split order. With more than one batch this can associate a refit with the wrong OOS split.
3. `candidate_id` is fit-specific because it includes the fitted risk-model identity and fitted weights. Validation scorecards currently group by this fit-specific ID, so repeated refits of one semantic allocator configuration cannot reliably aggregate into one multi-split scorecard.
4. `ValidationSplit.risk_model_id` is currently populated from the full-sample risk model passed to `validate_candidates`, not necessarily the risk model that actually fitted that split's candidate.
5. current production eligibility treats every stress-scenario reason as blocking. `distribution_cut` deliberately emits `cash_flow_evidence_only`, so a warning can block an otherwise valid candidate.
6. the current `return_risk` objective divides a compounded 21-observation OOS return by a daily volatility statistic instead of using the already-computed same-split Sharpe evidence.
7. the current `return_drawdown` objective uses aggregate return divided by a separately aggregated drawdown statistic instead of forming a same-split return/drawdown ratio before aggregation.
8. `covariance_perturbation` and `correlation_convergence` currently transform already aggregated portfolio return paths; they are not covariance-matrix or correlation-matrix stresses and must not retain those labels.
9. `src/portfell/scorecard.py` is a separate legacy walk-forward/ranking authority and must not coexist indefinitely with the canonical Multivariate validation/decision path.
10. the Multivariate risk-model adapter supports estimator/window arguments but does not expose an immutable semantic risk-model specification and does not pass an explicit rolling window size into the generic estimator.
11. the current code now persists rich Multivariate performance artifacts and renders them in Dash. Any candidate/configuration lineage change must update performance, validation, risk-contribution and UI read models together; a backend-only ID change is insufficient.
12. durable Multivariate checkpoints now persist Python objects from intermediate phases. Every semantic contract change in this series must bump `MULTIVARIATE_EXECUTION_VERSION`; old-version checkpoints must be ignored and resume must reproduce clean-run artifacts exactly.

## 3. Global weak-agent execution contract

Only PR437–PR458 below are executable. PR308–PR436 are integrated/retired historical work and must not be reopened as dependencies.

For every active PR:

- start from the exact merged predecessor SHA; stop if the predecessor is not merged;
- record `git status --short --branch` before edits;
- use the exact branch name and Conventional Commit scope shown below;
- change only owned paths plus directly failing focused tests and explicitly named version/persistence synchronization points;
- do not add a new optimizer, expected-return model, Optuna search, Black-Litterman, HERC/NCO, transaction-cost model or structural ranking rule unless explicitly authorized below;
- preserve listing identity `(isin, exchange, code)` everywhere;
- preserve adjusted-close/return authority and existing market-source lineage;
- no Equal Weight fallback may hide an unavailable optimizer or unavailable comparison configuration;
- every persisted semantic change must have deterministic IDs and an explicit contract/execution version change;
- any PR that changes checkpointed Multivariate state must prove older execution-version checkpoints are ignored;
- implementation PRs run focused tests plus `uv run portfell-quality pr`;
- QA PR458 also runs `uv run portfell-quality merge`, browser/REST acceptance and the repository `merge-gate` on the exact head;
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
  -> PR458(QA/PASS)
```

## 4. Portfolio Selection v2 — active PR437–PR458

### PR437 — Re-freeze Portfolio Selection v2 against the current runtime

Branch: `docs/pr437-portfolio-selection-v2-current-contract`

Commit scope: `docs(pr437-portfolio-selection-v2-current-contract)`

Priority: P0 contract.

Owned paths: `BACKLOG.md` only.

Task: make this file the compact execution authority based on current `main`, archive the prior backlog by exact SHA, enumerate the twelve current-code findings above and freeze PR438–PR458 without changing production code.

Acceptance:

- the baseline SHA is `66d7b7e948bbc58a14688156c3118bc1c8a8eaec`;
- only PR437–PR458 are executable;
- the eight-refit production baseline, checkpoint semantics, current performance artifacts and current Dash page are explicitly acknowledged;
- no production source/test behavior changes;
- documentation diff is self-contained and `uv run portfell-quality pr` passes if documentation contracts require it.

### PR438 — Remove `highest_monthly_return` completely

Branch: `refactor/pr438-remove-highest-monthly-return`

Commit scope: `refactor(pr438-remove-highest-monthly-return)`

Priority: P0 correctness/simplification.

Depends on: PR437.

Owned paths: `src/portfell/multivariate_candidates.py`, direct candidate/compute serialization tests, execution-version synchronization in `src/portfell/app_services/multivariate_compute.py`.

Task:

- freeze production methods to exactly `equal_weight`, `inverse_volatility`, `minimum_variance`, `equal_risk_contribution`, `hierarchical_risk_parity`, `minimum_cvar`;
- delete the dispatcher branch and helpers for `highest_monthly_return`;
- remove dedicated tests/fixtures and all production/test references;
- do not alter the math of the remaining six methods.

Acceptance:

- `git grep "highest_monthly_return" -- src tests` returns no matches;
- candidate contract bumps `v7 -> v8`;
- execution version bumps `clean.v1 -> clean.v2`, invalidating old checkpoints;
- candidate count is exactly six under the current default risk model.

### PR439 — Restore chronological walk-forward refit ordering

Branch: `fix/pr439-chronological-refit-order`

Commit scope: `fix(pr439-chronological-refit-order)`

Priority: P0 correctness.

Depends on: PR438.

Owned paths: `src/portfell/multivariate_refits.py`, `src/portfell/multivariate_validation.py`, focused refit/order tests, execution-version synchronization only.

Task:

- keep the current worker-batched/tmpfs optimization;
- make every worker result carry its original walk-forward start index;
- reassemble worker results strictly by the canonical `_walk_forward_starts(...)` order before validation or structural walk-forward consumes them;
- preserve the current maximum of eight refits and existing start-selection algorithm.

Acceptance:

- a deterministic fixture with at least four starts and at least two worker batches proves returned refits are chronological, not batch-major;
- every precomputed refit is paired with the exact intended `train_end`/`test_start` window;
- single-worker and multi-worker outputs are identical in order and candidate weights;
- validation contract bumps `v5 -> v6`;
- execution version `clean.v2 -> clean.v3`.

### PR440 — Introduce stable candidate-configuration lineage and fitted-risk lineage

Branch: `fix/pr440-stable-candidate-configuration-lineage`

Commit scope: `fix(pr440-stable-candidate-configuration-lineage)`

Priority: P0 correctness.

Depends on: PR439.

Owned paths: `src/portfell/multivariate_candidates.py`, `src/portfell/multivariate_validation.py`, `src/portfell/multivariate_refits.py` only where needed, `src/portfell/multivariate_structural_walk_forward.py`, compute serialization/version synchronization, focused lineage tests.

Task:

- introduce `multivariate.candidate_configuration@v1`;
- add `candidate_configuration_id` and fitted `risk_model_id` to `PortfolioCandidate`;
- for this PR the semantic configuration identity is method + portfolio policy + frozen current `LW_FULL` design specification; it excludes fitted covariance values, fitted weights, fitted `candidate_id`, snapshot dates and fitted risk-model ID;
- retain `candidate_id` as fit-specific identity;
- persist on every `ValidationSplit`: `candidate_configuration_id`, `fitted_candidate_id`, `full_sample_candidate_id`, `fitted_risk_model_id` and requested method;
- group turnover, split aggregation and scorecards by `candidate_configuration_id`, not fit-specific candidate ID;
- map the winning configuration back to the current full-sample fitted candidate;
- preserve fit-specific IDs in structural walk-forward evidence and add configuration ID there; structural diagnostics remain non-ranking evidence.

Acceptance:

- at least three refits of one method produce different fit candidate/risk IDs but one configuration ID;
- one scorecard aggregates all completed splits for that configuration;
- `ValidationSplit.fitted_risk_model_id` equals the model embedded in the refitted candidate, never the unrelated full-sample risk-model ID;
- current six-config production can produce a rankable multi-split scorecard;
- candidates `v8 -> v9`, validation `v6 -> v7`, execution `clean.v3 -> clean.v4`.

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
- unavailable values remain `None` and are omitted from their median input; never substitute zero;
- drawdown is converted to absolute magnitude before aggregation;
- no winner/objective logic changes in this PR.

Acceptance: independent fixtures verify every field; validation `v7 -> v8`; execution `clean.v4 -> clean.v5`.

### PR442 — Separate stress warnings from blocking eligibility

Branch: `fix/pr442-stress-warning-eligibility`

Commit scope: `fix(pr442-stress-warning-eligibility)`

Priority: P0 correctness.

Depends on: PR441.

Owned paths: `src/portfell/multivariate_validation.py`, `src/portfell/app_services/multivariate_compute.py`, eligibility tests.

Task:

- persist stress `available_with_warning` reasons separately from blocking unavailability;
- `cash_flow_evidence_only` remains visible as a warning and cannot by itself block production eligibility;
- only unavailable split/scenario evidence may create blocking reasons;
- Decision document persists `warnings` and `blocking_reasons` separately.

Acceptance: a feasible configuration whose only stress issue is distribution-cut warning is production-eligible when all other requirements pass; validation `v8 -> v9`; execution `clean.v5 -> clean.v6`.

### PR443 — Add same-split return/drawdown evidence

Branch: `feat/pr443-return-drawdown-split-metric`

Commit scope: `feat(pr443-return-drawdown-split-metric)`

Priority: P0 objective evidence.

Depends on: PR442.

Owned paths: `src/portfell/multivariate_validation.py`, focused numerical tests, execution-version synchronization.

Task: for each completed split compute `post_cost_return / abs(max_drawdown)` only when max drawdown is available and non-zero; aggregate the split ratios into `CandidateScorecard.median_return_drawdown_ratio`.

Acceptance:

- ratio is formed per split before median aggregation;
- zero/None drawdown yields unavailable ratio, never epsilon or infinity;
- no objective switch yet;
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
- preserve current per-split Sharpe cost semantics in this series: Sharpe is computed from the OOS daily path, while one-off turnover cost remains represented separately through post-cost return and turnover;
- Decision document persists `objective_metric = median_sharpe_ratio`.

Acceptance: a lower-return/higher-Sharpe configuration beats a higher-return/lower-Sharpe configuration; execution `clean.v7 -> clean.v8`.

### PR445 — Make `return_drawdown` use the median same-split ratio

Branch: `refactor/pr445-return-drawdown-oos-ratio`

Commit scope: `refactor(pr445-return-drawdown-oos-ratio)`

Priority: P0 decision correctness.

Depends on: PR444.

Owned paths: decision logic and focused decision tests.

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

Acceptance: every tie-break level has an independent fixture; execution `clean.v9 -> clean.v10`.

### PR447 — Remove the legacy standalone scorecard authority

Branch: `chore/pr447-delete-legacy-scorecard`

Commit scope: `chore(pr447-delete-legacy-scorecard)`

Priority: P1 simplification.

Depends on: PR446.

Expected deletion: `src/portfell/scorecard.py`, `tests/test_scorecard.py` if still dedicated to that module.

Task: run local `git grep` first. If a live production import exists, stop and create a narrow migration note rather than widening the PR. Preserve `evaluation.py`; migrate only unique high-value tests to the canonical Multivariate validation path.

Acceptance: no production import/reference to the retired scorecard; no compatibility wrapper; no financial behavior changes beyond removing duplicate dead authority.

### PR448 — Remove false covariance/correlation return-path stress labels

Branch: `fix/pr448-remove-false-risk-stress-labels`

Commit scope: `fix(pr448-remove-false-risk-stress-labels)`

Priority: P0 model correctness.

Depends on: PR447.

Owned paths: `src/portfell/multivariate_validation.py`, stress tests, execution-version synchronization.

Task: return-path stress scenarios become exactly `historical`, `seeded_block_bootstrap`, `distribution_cut`. Delete the current transformations that scale/deform already aggregated portfolio returns; do not rename them.

Acceptance: `_SCENARIO_NAMES` and persisted return-scenario rows contain exactly those three names; validation `v10 -> v11`; execution `clean.v10 -> clean.v11`.

### PR449 — Add a true 25% volatility-up asset-level risk stress

Branch: `feat/pr449-volatility-scale-risk-stress`

Commit scope: `feat(pr449-volatility-scale-risk-stress)`

Priority: P1 risk diagnostics.

Depends on: PR448.

Owned paths: new `src/portfell/multivariate_risk_stress.py`, compute persistence only, numerical/serialization tests.

Contract: `multivariate.risk_stress@v1`.

Scenario: `volatility_up_25pct`.

Rules:

- input is the canonical full-sample `LW_FULL` covariance plus candidate weights;
- every asset standard deviation is multiplied by 1.25;
- covariance therefore scales by `1.25**2` with correlations unchanged;
- output only stressed variance, volatility, status, reason and source risk-model ID;
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

- for every off-diagonal pair use `rho_stressed = 0.75 * rho + 0.25`;
- diagonal remains exactly 1;
- preserve original asset standard deviations and reconstruct covariance;
- validate symmetry, finite values, correlation bounds and PSD; do not silently apply a large repair;
- persist convergence strength 0.25;
- diagnostic only; no ranking effect.

Acceptance: independent two-asset oracle passes; risk-stress algorithm version increments; execution `clean.v12 -> clean.v13`.

### PR451 — Introduce immutable RiskModelSpecification

Branch: `feat/pr451-risk-model-specification`

Commit scope: `feat(pr451-risk-model-specification)`

Priority: P0 foundation for estimator comparison.

Depends on: PR450.

Owned paths: new `src/portfell/multivariate_risk_spec.py`, `src/portfell/multivariate_risk_model.py`, focused specification/adapter tests, compute version synchronization.

Freeze exactly three specifications:

- `LW_FULL`: estimator `ledoit_wolf`, window `full`, return type `log`;
- `LW_ROLLING_252`: estimator `ledoit_wolf`, window `rolling`, exact window size 252, return type `log`;
- `EWMA_094`: estimator `ewma`, window `full`, decay 0.94, return type `log`.

Rules:

- each spec has a readable `spec_key` and deterministic `spec_id`;
- rolling requires a positive window and the adapter must pass `window_size` to `estimate_risk_model`;
- `LW_ROLLING_252` is unavailable with fewer than 252 training observations; it is never silently shortened;
- full-window specs reject an irrelevant rolling window size;
- default `LW_FULL` reproduces predecessor covariance numerically on the same input;
- risk-model artifact persists spec key/id/window/parameters.

Acceptance: risk-model contract `v1 -> v2`; execution `clean.v13 -> clean.v14`.

### PR452 — Make candidate configuration identity risk-spec aware

Branch: `refactor/pr452-risk-spec-candidate-identity`

Commit scope: `refactor(pr452-risk-spec-candidate-identity)`

Priority: P0 lineage.

Depends on: PR451.

Owned paths: candidates, refits, validation lineage, focused identity tests, compute version synchronization.

Task:

- candidate-configuration contract `v1 -> v2` and include `risk_model_spec_id`;
- exclude fitted covariance, fitted risk-model ID and fitted weights from configuration identity;
- same method/policy under different risk specs must have different configuration IDs even when weights happen to match;
- same configuration across refits remains stable;
- ValidationSplit persists design spec key/id plus fitted risk-model ID;
- previous-weight/turnover tracking is keyed by configuration ID.

Acceptance: with only `LW_FULL` enabled, predecessor six-config weights and winner semantics remain unchanged apart from IDs; candidates `v9 -> v10`, validation `v11 -> v12`, execution `clean.v14 -> clean.v15`.

### PR453 — Produce common-split 12-configuration risk-model-family OOS evidence

Branch: `feat/pr453-risk-model-family-evidence`

Commit scope: `feat(pr453-risk-model-family-evidence)`

Priority: P0 empirical comparison.

Depends on: PR452.

Owned paths: new narrow risk-model comparison module, narrow refit/candidate-factory reuse, compute persistence, focused comparison tests.

Contract: `multivariate.risk_model_comparison@v1`.

Exact semantic configuration family:

- Equal Weight @ `LW_FULL` — 1;
- Inverse Volatility @ `LW_FULL` — 1;
- Minimum Variance @ each of the 3 risk specs — 3;
- Equal Risk Contribution @ each of the 3 risk specs — 3;
- Hierarchical Risk Parity @ each of the 3 risk specs — 3;
- Minimum CVaR @ `LW_FULL` — 1;
- total = exactly 12 configurations.

Frozen comparison policy:

- minimum training observations = 252;
- test window = 21;
- maximum refits = 8, matching the current bounded production execution model;
- minimum completed splits = 2;
- transaction-cost rate and turnover semantics match current production;
- all configurations use exactly the same chronological split starts and test windows;
- `LW_FULL` uses all training observations;
- `LW_ROLLING_252` uses exactly the trailing 252 training observations;
- `EWMA_094` uses all training observations with decay 0.94;
- fit each risk spec at most once per split and reuse that fitted risk artifact across all methods that consume the spec; do not refit the same covariance separately for MinVar/ERC/HRP;
- an unavailable configuration/split is persisted explicitly and never dropped;
- non-`LW_FULL` configurations are evidence-only in this PR; winner remains the six current `LW_FULL` production configurations;
- structural metrics are not ranking inputs and alternate-spec Structure-v2 is not recomputed here.

Acceptance:

- artifact contains exactly 12 configuration definitions;
- common split boundaries reconcile across all 12;
- chronological ordering remains identical with one or many workers;
- a future-row mutation cannot change any prior fitted config or split evidence;
- runtime tests assert at most three risk-model fits per split, not one per candidate;
- execution `clean.v15 -> clean.v16`.

### PR454 — Select production winner across allocator × risk-model configurations

Branch: `feat/pr454-oos-risk-model-selection`

Commit scope: `feat(pr454-oos-risk-model-selection)`

Priority: P0 production decision.

Depends on: PR453.

Owned paths: risk-model comparison/selection module, `src/portfell/app_services/multivariate_compute.py`, narrow Decision persistence tests.

Introduce Decision document contract `multivariate.decision@v2`.

Rules:

- only configurations complete on every exact comparison split are rankable; missing any common split yields `incomplete_comparison_evidence`;
- use PR444/PR445/minimum-risk primary metrics plus PR446 tie-breaks;
- Equal Weight and Inverse Volatility remain valid controls and may win;
- no in-sample score may select the winner;
- fit the exact winning configuration on the complete current input to produce production weights;
- no Equal Weight fallback;
- Structure-v2 remains absent from ranking.

Decision v2 persists at minimum:

- `winning_candidate_configuration_id`;
- `winning_candidate_id`;
- `requested_method` and `actual_method`;
- `risk_model_spec_key` and `risk_model_spec_id`;
- fitted `risk_model_id`;
- `objective_metric`;
- `comparison_split_count`;
- ordered tie-break list;
- production eligibility, warnings and blocking reasons;
- canonical common risk-stress model identified as `LW_FULL`.

Acceptance: limiting available specs to `LW_FULL` reproduces the preceding selection result; alternate specs can win only through superior common-split OOS evidence; execution `clean.v16 -> clean.v17`.

### PR455 — Reconcile persisted candidate/performance/structure lineage with Decision v2

Branch: `refactor/pr455-multivariate-artifact-lineage-v2`

Commit scope: `refactor(pr455-multivariate-artifact-lineage-v2)`

Priority: P0 persistence/read-model correctness.

Depends on: PR454.

Owned paths: `src/portfell/app_services/multivariate_compute.py`, `src/portfell/multivariate_performance.py`, candidate/risk-contribution serialization helpers, structural artifact adapter only where IDs are propagated, artifact tests.

Task:

- persist configuration ID, fitted candidate ID, method and risk-spec key/id consistently in candidate, validation, performance and risk-contribution artifacts;
- ensure the exact Decision v2 winner exists as a full-sample candidate artifact and has a performance series;
- performance series for configurations with the same method must remain distinguishable by configuration/spec identity;
- evaluate candidate structural diagnostics, when present, against the canonical `LW_FULL` common diagnostic risk model and label that fact explicitly; structural diagnostics remain non-ranking;
- preserve the current cumulative-performance and period-return behavior; do not change return arithmetic in this PR.

Acceptance: one lineage reconciliation test joins Decision -> candidate -> performance -> risk contribution without method-name guessing; no orphan winner IDs; execution `clean.v17 -> clean.v18`.

### PR456 — Update the live Multivariate page for configuration/spec-aware evidence

Branch: `feat/pr456-multivariate-selection-v2-dash`

Commit scope: `feat(pr456-multivariate-selection-v2-dash)`

Priority: P1 product/UI correctness.

Depends on: PR455.

Owned paths: `src/portfell/dash_app/pages/multivariate.py`, presentation helpers only as needed, focused Dash/browser tests. No financial computation.

Task:

- OOS candidate plot distinguishes configurations that share a method but use different risk specs;
- hover/legend expose method + risk-spec key + configuration ID without exposing raw private data;
- Decision card shows risk-model spec, objective metric, comparison split count, warnings and blocking reasons;
- performance legend identifies method/spec and highlights the persisted Decision v2 winner;
- current no-winner display behavior remains explicit and must not promote a display fallback into the Decision;
- existing structural, risk contribution, allocation, drawdown and final-portfolio plots keep rendering persisted artifacts.

Acceptance: deterministic Dash fixtures cover an `LW_FULL`, `LW_ROLLING_252` and `EWMA_094` configuration sharing one method; the correct winner is highlighted by ID, not by method name; no browser-side financial recomputation.

### PR457 — Harden durable checkpoint/resume semantics for Selection v2

Branch: `fix/pr457-selection-v2-checkpoint-resume`

Commit scope: `fix(pr457-selection-v2-checkpoint-resume)`

Priority: P0 operational correctness.

Depends on: PR456.

Owned paths: Multivariate checkpoint orchestration in `src/portfell/app_services/multivariate_compute.py` / `workspace.py` only where required, app-state checkpoint tests, focused restart/idempotency tests.

Task:

- verify every new intermediate object needed after PR453–PR455 is saved/restored at the correct phase;
- a checkpoint whose execution version differs from the current version is ignored without attempting to reuse incompatible pickled dataclasses;
- resume after candidate/refit, validation and scorecard/comparison phases produces the same final normalized artifacts and Decision v2 as a clean run;
- repeated resume/publication remains idempotent and does not create duplicate immutable artifacts;
- corrupt checkpoint payload remains typed-unavailable and causes clean recomputation rather than partial reuse.

Acceptance: clean-run vs resumed-run artifact hashes/normalized documents reconcile for all supported resume phases; execution bumps to `clean.v19` only if production checkpoint semantics require a code change, otherwise this PR may remain test-only and records the already-current version as evidence.

### PR458 — Independent Portfolio Selection v2 QA and immutable PASS evidence

Branch: `test/pr458-portfolio-selection-v2-closeout`

Commit scope: `test(pr458-portfolio-selection-v2-closeout)`

Priority: P0 final QA/PASS.

Depends on: PR457.

Owned paths: tests, evidence assembler, synchronized QA documentation only. No production fixes; defects require a corrective implementation PR and a fresh PR458 run.

Acceptance must independently prove on the exact head SHA:

- `highest_monthly_return` absent from `src` and `tests`; exactly six legacy/default methods remain under `LW_FULL`;
- multi-worker refit ordering equals canonical chronological starts;
- stable configuration IDs vs fit-specific candidate/risk IDs across at least three refits;
- scorecard aggregation spans multiple completed splits and every new metric matches an independent oracle;
- stress warning vs blocking semantics, including non-blocking `cash_flow_evidence_only`;
- `return_risk` uses median OOS Sharpe and `return_drawdown` uses same-split ratio before median;
- all four deterministic tie-break levels;
- legacy standalone scorecard authority absent;
- return-path stress names exactly historical/bootstrap/distribution-cut;
- independent matrix oracles for 25% volatility-up and 25% correlation-convergence stresses;
- all three risk-model specifications and exact rolling-252 behavior;
- exactly 12 semantic configurations and at most three risk-model fits per comparison split;
- identical common 252-start/21-test/eight-refit schedule across configs;
- future-data mutation cannot change prior fit evidence;
- incomplete comparison configuration is unrankable;
- fixtures in which `LW_FULL`, `LW_ROLLING_252` and `EWMA_094` can each win only through OOS evidence;
- Decision v2 lineage reconciles to exact full-sample candidate, performance and risk-contribution artifacts;
- structural diagnostics are labeled canonical-`LW_FULL` diagnostics and remain absent from ranking;
- clean vs resumed checkpoint execution is artifact-equivalent and publication-idempotent;
- the live Multivariate page renders configuration/spec-aware OOS, performance and Decision evidence at supported viewports with no console/page errors;
- `uv run portfell-quality pr`, `uv run portfell-quality merge` and GitHub `merge-gate` pass on the exact head;
- produce one immutable sanitized `portfolio-selection-v2` PASS artifact containing exact Git SHA, contract/execution versions, configuration-family fingerprint, split policy, numerical-oracle references, restart evidence, browser evidence and gate evidence without credentials, DSNs, private paths or raw market rows.

## 5. Explicitly deferred work — non-executable

The following topics are deliberately outside PR437–PR458 and require a new backlog contract after PR458 PASS:

- redesign of the `max_weight = 0.20` constraint and the exact-five-holdings degeneracy where a fully invested long-only five-asset portfolio is forced to 20% each;
- Maximum Sharpe or any other expected-return optimizer;
- Black-Litterman, factor, momentum or regime-conditioned expected-return priors;
- HERC/NCO or additional portfolio allocators;
- CVaR scenario-generation redesign;
- transaction-cost-aware daily Sharpe reconstruction;
- structural PCA/cluster metrics as ranking objectives or hard constraints;
- Optuna/hyperparameter search;
- saved-portfolio/PDF/`.portfell` export/import workflow;
- Bivariate page visualization redesign.

## 6. Historical status

PR308–PR436 are integrated/retired historical backlog items. Their detailed work orders are preserved at `66d7b7e948bbc58a14688156c3118bc1c8a8eaec`. Do not implement them from this compact file.

The only active execution sequence is PR437 -> ... -> PR458.
