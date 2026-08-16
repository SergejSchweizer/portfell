# Plotly Dash And Automatic Portfolio Optimizer PR Stack

Status: normative planning contract for `BACKLOG.md` PR264-PR274.

This document is the executable work order for the Plotly Dash research UI and the automatic `return_risk` portfolio optimizer. It supersedes the former three-page-only planning contract, which is archived at `docs/backlog/archive/plotly-dash-three-page-research-ui-v1.md`.

## Fixed architecture

The browser workflow is exactly:

```text
Metadata Builder
    -> Univariate Statistics
    -> Bivariate Statistics
    -> Multivariate Statistics / Automatic Optimizer
```

Dash is a presentation/orchestration adapter under `/dash/`. It consumes existing authorized application-service/page-view/lazy-section/command contracts through a typed gateway. Dash must not read PostgreSQL directly, scan Parquet or shared-market files, call EODHD, own credentials, create a second durable job system, or calculate portfolio statistics in the browser process.

The automatic optimizer executes in the Python analytical/service layer. It consumes immutable project-scoped upstream revisions and persists immutable decision artifacts. The UI renders those artifacts; it never infers reasons from final weights.

Production optimization for several hundred ISINs must not enumerate all unique ISIN subsets and must not enumerate a high-dimensional weight grid. Exact enumeration is allowed only in tiny deterministic tests or already-existing guarded baseline code where the exact candidate count is below the existing safety limit. Production weight selection uses numerical solvers plus bounded automatic universe reduction.

Every important decision must be explainable by a persisted `DecisionArtifact` and visualizable in Multivariate Statistics. If a stage is not applicable, the artifact must carry the explicit reason code `not_applicable` rather than silently omitting the stage.

## Frozen route registry

The only Dash workflow routes are:

- `/dash/projects/<project_slug>/metadata-builder`
- `/dash/projects/<project_slug>/univariate-statistics`
- `/dash/projects/<project_slug>/bivariate-statistics`
- `/dash/projects/<project_slug>/multivariate-statistics`

The route IDs are exactly `metadata_builder`, `univariate_statistics`, `bivariate_statistics`, and `multivariate_statistics`.

## Parallel execution contract

Two weak agents may work in parallel only when they start from the exact same predecessor merge commit. Parallel branches must never be stacked on each other. Shared contracts are frozen by the predecessor before branches start.

```text
PR264 foundation
  |
  +----------------------+----------------------+
  |                                             |
PR265 shell/navigation                         PR266 metadata
  |                                             |
  +----------------------+----------------------+
                         |
                     merge both
                         |
  +----------------------+----------------------+
  |                                             |
PR267 univariate + universe plot              PR268 bivariate + universe plot
  |                                             |
  +----------------------+----------------------+
                         |
                     merge both
                         |
                      PR269
             decision-contract foundation
                         |
  +----------------------+----------------------+
  |                                             |
PR270 automatic universe selector             PR271 production solver set
  |                                             |
  +----------------------+----------------------+
                         |
                     merge both
                         |
  +----------------------+----------------------+
  |                                             |
PR272 auto orchestrator + OOS winner          PR273 decision persistence/API
  |                                             |
  +----------------------+----------------------+
                         |
                     merge both
                         |
                      PR274
          Multivariate Decision Audit + gate
```

For every PR below, `Tasks / Acceptance` is the only checklist. There is no separate acceptance list.

---

## PR264 — Plotly Dash Runtime And Four-Page Contract Foundation

Git metadata:

- Branch: `feat/dash-runtime-foundation`
- Base: `main`
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested title: `feat(dash): add four-page research runtime foundation`
- Required squash subject: `feat(dash): add four-page research runtime foundation`
- Merge method: squash only
- Parallel wave: foundation; two-agent hand-off inside one PR
- Depends on: already-merged hosted page-view/lazy-section/workflow/run/command contracts

Business outcome: one runnable Dash/FastAPI sidecar with immutable four-page IDs, component namespaces, typed gateway, shared Plotly conventions, and deterministic test fixtures.

Owned paths:

- Agent A: dependency lock changes, `apps/dash/Dockerfile`, Dash service/profile in `compose.yaml`, `src/portfell/dash_ui/app.py`, `src/portfell/dash_ui/runtime.py`.
- Agent B: `src/portfell/dash_ui/contracts.py`, `src/portfell/dash_ui/ids.py`, `src/portfell/dash_ui/plot_contracts.py`, `src/portfell/dash_ui/testing.py`, foundation tests.
- Hand-off: Agent B commits/finalizes `contracts.py`, `ids.py`, and `plot_contracts.py` first. Agent A may import them after hand-off and must not edit them.
- Forbidden: `apps/web/**`, optimizer math, risk model formulas, PostgreSQL repositories, provider clients, migrations.

Tasks / Acceptance — identical checklist:

- [ ] Add explicit Dash/FastAPI-compatible runtime dependencies and lock them once. `uv lock --check` and `uv sync --frozen` succeed on the repository Python version. Do not add Celery, Redis, DiskCache, pandas, Flask-as-a-second-authority, or another job queue.
- [ ] Create importable `portfell.dash_ui` with ASGI startup, fixed `/dash/` prefix, Dash Pages enabled, callback validation enabled, title `Portfell · Research`, and no import-time database/provider/calculation side effect.
- [ ] Freeze exactly four page IDs and route suffixes listed in this document. Tests fail on a missing, duplicate, reordered, or fifth workflow page.
- [ ] Freeze component-ID namespaces for shell, Metadata, Univariate, Bivariate, Multivariate, shared universe chart, optimizer candidate chart, and error/progress regions. IDs may be extended only through a future explicit backlog PR after PR264 merges.
- [ ] Define `DashResearchGateway` methods for authorized project context, page views, research runs, lazy sections, selection settings, commands, automatic-optimizer start/status, and decision sections. Every project-scoped method requires project identity; no method accepts raw SQL, filesystem path, provider client, repository, or lake object.
- [ ] Define presentation-only contracts for `UniversePoint`, `PairwiseUniversePoint`, `PortfolioCandidatePoint`, `DecisionStageSummary`, and typed section availability. These map server output only and contain no formula implementation.
- [ ] Add fixed fake fixtures for two projects covering no-project, ready, running, complete, failed, stale, unauthorized, Univariate 12-listing universe, Bivariate pair universe, optimizer 400-input/<=250-output universe, model candidates, winner, and every decision section. IDs/timestamps/counts are constant.
- [ ] Add architecture tests that fail if `portfell.dash_ui` imports PostgreSQL adapters, `psycopg`, provider/EODHD modules, `portfell.table_io`, lake paths, risk/portfolio formula modules, or local shared-store readers.
- [ ] Add unprivileged Dash Docker image and opt-in Compose `dash` profile. The container mounts no shared-market data, receives no provider/database secret, and reaches only the API/application boundary required by its gateway implementation. Health endpoint leaks no project/user/storage information.
- [ ] PR evidence records and passes foundation tests, Ruff, Pyright, dependency lock check, Dash Docker build, Compose config check, architecture tests, and `uv run portfell-quality pr` from one Git SHA.

Security: Dash is not authorization authority and has no direct data-plane secret.

Determinism: fixed route/ID/contract registries and fixed fixtures define one runtime shape.

Idempotency: startup/health/reads are non-mutating.

Rollback: remove Dash package/image/profile/dependencies; no persisted-state migration exists.

---

## PR265 — Dash Shell And Four-Stage Project Navigation

Git metadata:

- Branch: `feat/dash-research-shell`
- Base: exact merge commit of PR264
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested title: `feat(dash): add four-stage research shell`
- Required squash subject: `feat(dash): add four-stage research shell`
- Merge method: squash only
- Parallel wave: 1 / Agent A; parallel with PR266
- Depends on: PR264

Owned paths: `shell.py`, `navigation.py`, shell-only CSS, shell tests/docs. PR266 page/callback files are forbidden.

Tasks / Acceptance — identical checklist:

- [ ] Render one Portfell shell with header, project selector, process overview, left workflow sidebar, and page region using local CSS only.
- [ ] Sidebar contains exactly four links in this order: Metadata Builder, Univariate Statistics, Bivariate Statistics, Multivariate Statistics. Locked/running/complete/ready states map exactly from server workflow projection.
- [ ] Canonical URLs use `/dash/projects/<slug>/...`; slug normalization matches existing project behavior for accents, punctuation, whitespace, empty fallback, and deterministic collision display.
- [ ] `/dash/` with a current project redirects to the earliest navigable stage; without a current project it renders Metadata Builder no-project state and performs no write.
- [ ] Selecting another project emits exactly one existing select-project command, reloads the target workflow, chooses the furthest unlocked stage, and never paints the previous project's counts after URL change.
- [ ] Unknown/deleted/unauthorized project slug renders one typed unavailable state and never falls back to another project.
- [ ] Process overview contains only server-owned counts/status. Missing values render unavailable, never invented zero.
- [ ] Desktop and 390px mobile layouts retain visible focus and keyboard navigation; no custom JS file is added.
- [ ] Browser-persisted storage contains no credentials, result matrices, members, financial series, or decision artifacts.
- [ ] Shell/navigation tests prove two-project isolation and all named navigation states; Ruff, Pyright, Dash Docker build, and quality gate pass.

Security: URL/project state never grants access.

Determinism: canonical slug + workflow projection determine one navigation state.

Idempotency: same-project selection issues no command.

Rollback: revert shell/navigation assets/tests/docs.

---

## PR266 — Dash Metadata Builder

Git metadata:

- Branch: `feat/dash-metadata-builder`
- Base: same exact PR264 merge commit as PR265
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested title: `feat(dash): add Metadata Builder page`
- Required squash subject: `feat(dash): add Metadata Builder page`
- Merge method: squash only
- Parallel wave: 1 / Agent B; parallel with PR265
- Depends on: PR264

Owned paths: Metadata page, Metadata callbacks/view-model, metadata-only CSS, tests/docs. Shell files are forbidden except documented registration import.

Tasks / Acceptance — identical checklist:

- [ ] Render one combined metadata panel containing progress/status/fetch action followed by the Metadata Builder form.
- [ ] Form contains exactly Exchange, Instrument type, Country, Currency, and `Name contains`; dropdown options use server counts and deterministic sorting.
- [ ] Metadata fetch uses the existing command exactly once per logical activation, disables while active, restores persisted progress, and never receives a provider key.
- [ ] Project creation requires metadata-ready plus at least one criterion, submits exactly the five values, shows selected unique-ISIN count, and navigates to canonical Dash project URL after success.
- [ ] Initial-fill `not_started|planning|running|ready|partial|failed` states map to explicit text/progress/retry behavior with no browser-side inference of completion.
- [ ] Reload restores persisted criteria/current project/initial-fill state; it never starts metadata or quotes implicitly.
- [ ] Rapid project switch cancels obsolete reads and cannot paint old criteria/progress on the new project.
- [ ] Duplicate callback delivery cannot create duplicate logical metadata/project commands.
- [ ] Two-project and failure fixtures cover all disabled/enabled states and exact command counts.
- [ ] Focused tests, Ruff, Pyright, Dash Docker build, and quality gate pass from one SHA.

Security: provider credential stays server-side.

Determinism: same page-view revision and options produce same UI.

Idempotency: reads are non-mutating; commands retain server idempotency.

Rollback: revert Metadata Dash files.

---

## PR267 — Dash Univariate Statistics With Global Return-Risk Universe Plot

Git metadata:

- Branch: `feat/dash-univariate-universe`
- Base: exact `main` commit after PR265 and PR266 merge
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested title: `feat(dash): visualize Univariate return-risk universe`
- Required squash subject: `feat(dash): visualize Univariate return-risk universe`
- Merge method: squash only
- Parallel wave: 2 / Agent A; parallel with PR268
- Depends on: PR264-PR266

Owned paths: Univariate page/figures/callbacks/view-model/tests/docs and Univariate-only CSS. Bivariate files forbidden.

Tasks / Acceptance — identical checklist:

- [ ] Preserve current Univariate compute/restore/progress, dividend-frequency selection, Duration thresholds, metric tabs, persisted ranges/labels, and revision-bound results without recalculating financial statistics in Dash.
- [ ] Add one always-visible `Return / Risk Universe` Plotly scatter above the tab strip whenever at least one authorized Univariate result exists.
- [ ] X axis is `annualized_volatility`; Y axis is `annualized_geometric_return`; one point is one full listing identity `(isin, exchange, code)` and duplicate ISIN listings remain distinguishable.
- [ ] Plot exposes separate traces/status styling for `selected`, `rejected_by_selection`, and `data_quality_excluded`; rejected points remain visible by default with a `Show rejected` toggle that hides only presentation traces.
- [ ] Hover contains ISIN, code.exchange, annualized geometric return, annualized volatility, Sharpe, Sortino, Expected Shortfall, maximum drawdown, distribution frequency, annual dividend yield, and return-observation count. Unavailable values are labeled unavailable, not zero.
- [ ] Draw the two-dimensional non-dominated frontier for maximize-return/minimize-volatility over data-quality-eligible points. Frontier membership is a presentation fact derived deterministically from server-provided values and does not alter persisted selection.
- [ ] Any selection setting save updates point state after server confirmation; chart click/hover alone never mutates selection.
- [ ] Figure builder accepts only typed Univariate rows and returns stable trace ordering sorted by listing identity; tests cover equal return/risk ties and all-unavailable/empty cases.
- [ ] Two-project tests prove project A points/frontier/selections cannot appear after project B navigation, including cancelled in-flight result paging.
- [ ] Focused Dash tests, figure snapshot/data tests, Ruff, Pyright, Docker build, and quality gate pass.

Security: chart receives only authorized result rows.

Determinism: stable listing sort + fixed frontier rule produce stable trace inputs.

Idempotency: viewing/hovering/toggling traces is read-only.

Rollback: revert Univariate Dash page/figure/tests/docs.

---

## PR268 — Dash Bivariate Statistics With Global Return-Diversification Universe Plot

Git metadata:

- Branch: `feat/dash-bivariate-universe`
- Base: same exact post-PR265/PR266 `main` commit as PR267
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested title: `feat(dash): visualize Bivariate diversification universe`
- Required squash subject: `feat(dash): visualize Bivariate diversification universe`
- Merge method: squash only
- Parallel wave: 2 / Agent B; parallel with PR267
- Depends on: PR264-PR266

Owned paths: Bivariate page/figures/callbacks/view-model/tests/docs and Bivariate-only CSS. Univariate implementation files forbidden; pinned Univariate values are consumed only through gateway contracts.

Tasks / Acceptance — identical checklist:

- [ ] Preserve Bivariate compute/restore/progress and exactly nine detailed views: Covariance, Pearson, Spearman, Downside, Tail Dependence, Co-exceedance, Rolling-Correlation, Drawdown Overlap, Tail-Risk Scatter.
- [ ] Replace detailed pair matrices with Plotly heatmaps built only from authorized section payloads; Tail-Risk Scatter uses WebGL when point count exceeds the deterministic threshold in the test fixture.
- [ ] Add one always-visible `Return / Diversification Universe` Plotly scatter above the tab strip after a completed Bivariate result exists.
- [ ] One point is one selected listing. Y is pinned `annualized_geometric_return` from the exact upstream Univariate selection revision. X defaults to the median Pearson correlation of that listing to all other selected listings; self-pairs and unavailable pair values are excluded from the median.
- [ ] X metric selector has exactly six values: Median Pearson, Median Spearman, Median Downside Correlation, Median Lower-Tail Dependence, Median Co-exceedance, Median Drawdown Overlap. Switching metric changes only the X values/title and makes no server mutation.
- [ ] Hover contains listing identity, return, selected median metric, count of usable pairs for that metric, and medians of the other five metrics when available.
- [ ] Point status supports `selected_for_bivariate` and `redundancy_candidate` presentation states when supplied by later optimizer decision sections, but PR268 itself does not perform optimizer elimination.
- [ ] Pair-coverage facts show start/end and min/average/max shared observations. Oversize/stale/unavailable sections render typed states without truncation or zero substitution.
- [ ] Deterministic 201-listing/20,100-pair fixture renders all nine views and the universe scatter without pair omission; two-project fixture proves no cross-project labels or pair values.
- [ ] Focused tests, figure data tests, Ruff, Pyright, Docker build, and quality gate pass.

Security: section IDs do not authorize access.

Determinism: exact pair revision + median rule + stable listing order determine same plot.

Idempotency: section reads and metric switches are non-mutating.

Rollback: revert Bivariate Dash page/figures/tests/docs.

---

## PR269 — Optimizer Decision Artifact And Profile Contract Foundation

Git metadata:

- Branch: `feat/optimizer-decision-contracts`
- Base: exact `main` commit after PR267 and PR268 merge
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested title: `feat(optimizer): define auditable automatic decision contracts`
- Required squash subject: `feat(optimizer): define auditable automatic decision contracts`
- Merge method: squash only
- Parallel wave: foundation; two-agent hand-off inside one PR
- Depends on: PR267, PR268, existing Multivariate/risk-model/scorecard contracts

Business outcome: immutable contracts that force every automatic optimizer stage to persist machine-readable candidates, chosen items, rejected items, metrics, and reason codes.

Owned paths:

- Agent A: `optimizer_decisions.py`, profile/settings contracts, IDs, enums.
- Agent B: schema/serialization/property tests, deterministic fixtures, documentation.
- Forbidden: actual selector/solver/orchestrator implementation, UI files, provider/storage adapters.

Frozen stage IDs:

1. `input_eligibility`
2. `univariate_pareto`
3. `bivariate_redundancy`
4. `risk_model_candidates`
5. `portfolio_candidates`
6. `walk_forward_validation`
7. `winner_selection`
8. `final_portfolio`

Tasks / Acceptance — identical checklist:

- [ ] Define versioned `AutomaticOptimizerSettings` with profile exactly `return_risk`, optional allowed distribution frequencies inherited from the pinned Univariate selection, optional `max_weight`, optional `min_weight`, optional `max_holdings`, transaction-cost rate, and no field for manually selecting individual ISINs or manually selecting one optimizer method.
- [ ] Define immutable `DecisionArtifact` with decision ID, automatic-run ID, project/run input revision IDs, stage ID, algorithm/profile versions, ordered candidate IDs, ordered selected IDs, ordered rejections, stage metrics, status, and optional `not_applicable` reason.
- [ ] Define `DecisionCandidate` with stable candidate ID, label/type, metric map, rank, selected flag, and source identities; define `DecisionRejection` with candidate ID and one or more frozen reason codes.
- [ ] Freeze reason codes at minimum: `data_quality_ineligible`, `insufficient_history`, `distribution_not_allowed`, `pareto_dominated`, `redundancy_representative_not_selected`, `risk_model_unavailable`, `solver_infeasible`, `solver_not_converged`, `walk_forward_blocked`, `out_of_sample_ranked_lower`, `not_applicable`.
- [ ] Define a `DecisionSink` protocol with idempotent `put(artifact)` and deterministic read-by-run/stage behavior. Same ID+same canonical content is a no-op; same ID+different content raises a conflict.
- [ ] Decision ID is a stable content-addressed ID over stage, pinned input revisions, settings/profile version, ordered candidate payload, and selected/rejected outcome; worker order and dictionary order cannot change it.
- [ ] Add fixtures for all eight stages, including one 400-listing input, one <=250 selected universe, three risk-model configs, seven portfolio methods, five walk-forward splits, one winner, and final weight/risk/income contributions.
- [ ] Serialization rejects NaN/Inf, credentials, SQL text, absolute storage paths, and unbounded arbitrary object payloads; metric keys must be from explicit stage schemas.
- [ ] Architecture tests prove decision contracts depend only on analytical/public types and no Dash/React/hosted repository/provider implementation.
- [ ] Focused contract/property tests, Ruff, Pyright, and quality gate pass; no downstream PR begins before this contract is merged.

Security: decision artifacts contain analytical evidence only.

Determinism: canonical serialization defines artifact identity.

Idempotency: identical put is a no-op; conflict fails closed.

Rollback: remove new contracts without changing existing portfolio outputs.

---

## PR270 — Automatic Universe Selector From Uni/Bivariate Evidence

Git metadata:

- Branch: `feat/optimizer-universe-selector`
- Base: exact PR269 merge commit
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested title: `feat(optimizer): add automatic universe selection`
- Required squash subject: `feat(optimizer): add automatic universe selection`
- Merge method: squash only
- Parallel wave: 3 / Agent A; parallel with PR271
- Depends on: PR269

Owned paths: selector module, selector-specific clustering/ranking helpers, selector tests/fixtures/docs. Solver modules forbidden.

Algorithm contract:

1. Start with the exact pinned Bivariate input listing set; the selector may remove but never add a listing.
2. Apply hard eligibility: `production_eligible`, sufficient common/history policy, allowed distribution frequency if the profile specifies frequencies.
3. Compute deterministic Univariate non-dominated sorting using maximize `annualized_geometric_return`, `sharpe_ratio`, `sortino_ratio`; minimize `annualized_volatility`, `expected_shortfall`, absolute `max_drawdown`. Missing required metrics make the listing ineligible, not zero.
4. Keep Pareto front rank 1. If rank-1 count is below the minimum feasible portfolio count, extend rank by rank until feasibility is reached.
5. If the resulting count is <=250, Bivariate redundancy reduction is `not_applicable` and all surviving listings continue.
6. If count is >250, use deterministic hierarchical correlation clustering from the pinned Pearson matrix and cut to exactly 250 clusters. Within each cluster choose one representative by: lower Pareto rank, higher Sortino, higher annualized geometric return, lower Expected Shortfall, lower annualized volatility, lexical listing identity. Tail/downside/Drawdown metrics are recorded for the representative decision and surfaced in the artifact, but do not silently change the tie-break order.

Tasks / Acceptance — identical checklist:

- [ ] Implement selector exactly in the six-step algorithm contract above; expose one pure function returning ordered selected listing identities plus eight-stage-compatible decision artifacts for eligibility, Pareto, and Bivariate redundancy.
- [ ] Hard eligibility emits one exact rejection reason per failed rule and never substitutes missing metric data with zero.
- [ ] Pareto dominance uses the six named Univariate dimensions and deterministic equality/tie handling; unit tests cover dominated, non-dominated, exact-tie, missing-value, and mixed-frequency cases.
- [ ] Selector never adds a listing absent from the pinned input universe and preserves full listing identity when the same ISIN has multiple exchange listings.
- [ ] <=250 post-Pareto fixture produces `bivariate_redundancy` with status `not_applicable` and unchanged membership.
- [ ] >250 fixture cuts deterministic Pearson-correlation clustering to exactly 250 clusters and chooses exactly one representative per cluster with the frozen tie-break sequence.
- [ ] Every removed cluster member has `redundancy_representative_not_selected` plus representative listing identity and its Pearson, Downside, Lower-Tail, Co-exceedance, and Drawdown-Overlap pair evidence where available.
- [ ] 400-listing deterministic fixture completes within the repository's named test budget, uses no all-subset enumeration, and produces identical membership/decision IDs under reversed input order and worker count 1 vs >1.
- [ ] Property tests prove selected count is feasible, <=250, unique by full listing identity, and a subset of input membership.
- [ ] Focused selector tests, Ruff, Pyright, and quality gate pass.

Security: selector sees only authorized pinned inputs.

Determinism: pinned revisions + frozen ranking/clustering/tie rules determine membership.

Idempotency: pure selector and content-addressed decisions repeat exactly.

Rollback: remove selector module; no upstream data changes.

---

## PR271 — Solver-Backed Return-Risk Portfolio Candidate Set

Git metadata:

- Branch: `feat/optimizer-production-solvers`
- Base: same exact PR269 merge commit as PR270
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested title: `feat(optimizer): add solver-backed return-risk candidates`
- Required squash subject: `feat(optimizer): add solver-backed return-risk candidates`
- Merge method: squash only
- Parallel wave: 3 / Agent B; parallel with PR270
- Depends on: PR269

Owned paths: solver adapters, expected-return adapter, candidate builder, numerical tests. Universe selector files forbidden.

Candidate methods are exactly:

- `equal_weight` baseline
- `minimum_variance`
- `maximum_sharpe`
- `maximum_diversification`
- `equal_risk_contribution`
- `hierarchical_risk_parity`
- `minimum_cvar`

Risk-model configurations are exactly `sample`, `ledoit_wolf`, and `ewma`, using the existing risk-model implementation and diagnostics. `ledoit_wolf` and `ewma` are production candidates; `sample` is a diagnostic baseline and may win only if the final automatic profile policy explicitly permits baseline selection in PR272.

Tasks / Acceptance — identical checklist:

- [ ] Add production numerical Maximum Sharpe solver with long-only capped-simplex constraints, explicit risk-free-rate input, deterministic initialization/tolerances, convergence diagnostics, and no weight-grid enumeration.
- [ ] Add production numerical Maximum Diversification solver with the same constraint boundary and deterministic diagnostics; no grid enumeration.
- [ ] Reuse existing production Minimum Variance, ERC, HRP, and Minimum CVaR implementations through one typed candidate-builder interface rather than duplicating formulas.
- [ ] Equal Weight remains an explicit baseline candidate and is never silently substituted for a failed production solver.
- [ ] Candidate builder accepts the exact selected universe, aligned return rows, one risk-model result, expected-return map, and portfolio constraints; it returns candidate weights plus return/variance/volatility/Sharpe/Sortino/CVaR/max-drawdown/diversification/concentration metrics using existing core functions.
- [ ] Expected-return map for `return_risk` is built from the exact training-window daily log returns and annualized consistently with existing Univariate return semantics; it is re-estimated inside each walk-forward training split and never from future test returns.
- [ ] Solver failure/non-convergence returns typed unavailable candidate plus frozen reason code; it never emits plausible fallback weights under the failed method name.
- [ ] Numerical tests compare solver objective values against exact tiny-universe brute-force baselines within named tolerance for 2-4 assets; large-universe tests prove the production path never calls `_candidate_weights`/exact grid enumeration.
- [ ] Reversing listing input order produces weights mapped to the same listing identities within tolerance; all output weights are finite, satisfy sum/bounds, and no candidate contains a missing listing.
- [ ] Focused numerical tests, Ruff, Pyright, and quality gate pass.

Security: pure numerical code has no tenant/provider/storage access.

Determinism: fixed initialization/tolerances and stable identity mapping.

Idempotency: pure solver calls mutate nothing.

Rollback: remove new solvers/adapters without changing existing methods.

---

## PR272 — Automatic Optimizer Orchestrator And Out-Of-Sample Winner

Git metadata:

- Branch: `feat/optimizer-auto-orchestrator`
- Base: exact `main` commit after PR270 and PR271 merge
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested title: `feat(optimizer): select return-risk portfolio automatically`
- Required squash subject: `feat(optimizer): select return-risk portfolio automatically`
- Merge method: squash only
- Parallel wave: 4 / Agent A; parallel with PR273
- Depends on: PR269-PR271 plus existing walk-forward/scorecard infrastructure

Owned paths: automatic-run orchestration, configuration enumeration, winner ranking, final refit, orchestrator tests. Persistence/API files forbidden except `DecisionSink` calls.

Automatic `return_risk` model search is bounded and deterministic:

- eligible risk models: `ledoit_wolf`, `ewma`; `sample` is reported baseline only;
- optimizer methods: the seven PR271 methods, with Equal Weight baseline reported but not winner-eligible unless every production candidate is blocked;
- training windows attempted in order: 252, 504, 756 observations when the pinned history supports them;
- test window: existing production walk-forward profile default; no future data leakage;
- winner primary metric: median out-of-sample Sharpe across completed splits;
- deterministic tie-break order: higher median OOS Sortino, lower absolute whole-period OOS max drawdown, lower OOS CVaR, lower median turnover, lexical configuration ID;
- a configuration with fewer than the production minimum completed splits is blocked, never ranked.

Tasks / Acceptance — identical checklist:

- [ ] Add one project-scoped automatic `return_risk` command that requires pinned Bivariate run/revision and settings but no manually chosen ISIN list or optimizer method.
- [ ] Authorize project/run first, invoke PR270 selector, and emit `input_eligibility`, `univariate_pareto`, and `bivariate_redundancy` decisions through `DecisionSink` before model construction.
- [ ] Build only the bounded risk-model/method/window configurations defined above; configuration count is recorded and tests fail if an unrestricted permutation/product dimension is introduced.
- [ ] For each split, fit risk model and expected returns using training data only, solve candidate on training data, evaluate test returns after transaction cost, and store split metrics. No test-period return enters training inputs.
- [ ] Emit `risk_model_candidates`, `portfolio_candidates`, and `walk_forward_validation` decision artifacts containing every feasible/blocked configuration, exact metrics, and reason codes.
- [ ] Rank only completed OOS results using the frozen primary/tie-break sequence and select exactly one winner. Equal Weight can win only if all non-baseline production configurations are blocked; this fallback condition is explicit in `winner_selection` artifact.
- [ ] Refit the winning configuration on the full selected history using the same method/risk-model semantics and calculate final weights, portfolio metrics, risk contributions, and available income contributions; emit `final_portfolio` artifact.
- [ ] Duplicate submission with identical project/input/settings resolves to one logical automatic-run ID and one winner; a changed pinned Bivariate revision or settings version yields a different run ID.
- [ ] Deterministic fixture with multiple windows/models/methods proves selection is based on OOS metrics, not highest in-sample return or one best split; reversed worker completion order gives the same winner.
- [ ] Focused orchestration/walk-forward tests, Ruff, Pyright, and quality gate pass.

Security: command resolves authorized project and pinned run before data access.

Determinism: bounded model registry + fixed split/ranking policy determine winner.

Idempotency: same input/settings reuse one logical run.

Rollback: remove automatic orchestration; existing manual Multivariate candidate logic remains.

---

## PR273 — Authorized Decision Artifact Persistence And Lazy Read Sections

Git metadata:

- Branch: `feat/optimizer-decision-sections`
- Base: same exact post-PR270/PR271 `main` commit as PR272
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested title: `feat(optimizer): persist and expose decision audit sections`
- Required squash subject: `feat(optimizer): persist and expose decision audit sections`
- Merge method: squash only
- Parallel wave: 4 / Agent B; parallel with PR272
- Depends on: PR269-PR271

Owned paths: decision artifact repository/adapter, run-to-artifact authorization references, read models, API routes/contracts, persistence/security tests. Optimizer algorithms forbidden.

Section keys are exactly:

- `decision_summary`
- `universe`
- `risk_models`
- `portfolio_candidates`
- `validation`
- `final_portfolio`

Tasks / Acceptance — identical checklist:

- [ ] Persist canonical DecisionArtifact bytes through the existing content-addressed artifact authority or a minimal compatible adapter; do not create a second filesystem authority or browser-owned store.
- [ ] Map automatic run -> ordered decision IDs under project/user authorization. Mapping contains no credential, SQL, storage path, or unrestricted membership data.
- [ ] Same decision ID/content write is idempotent; same ID/different content fails closed and leaves prior artifact unchanged.
- [ ] Add compact project-scoped decision page-view summary containing run status, stage availability/revisions, winner ID, and counts only; no large candidate/weight arrays.
- [ ] Add authorized lazy section reads with exactly the six keys above; project and automatic-run ownership are resolved before artifact bytes are loaded.
- [ ] Section response contains immutable revision ID and typed `available|running|failed|stale|not_applicable|too_large`; it never truncates a large indivisible figure payload silently.
- [ ] Read models expose the exact fields needed by PR274 plots: universe counts/points/reasons, cluster assignments/pair evidence, risk-model diagnostics, candidate OOS metrics, split series, weight histories, winner, final weights, risk contributions, and income contributions when available.
- [ ] GET/read paths invoke no selector, solver, risk-model estimation, walk-forward calculation, or financial recomputation; architecture tests fail on such imports/calls.
- [ ] Two-project tests prove guessed/cross-project run/decision IDs expose nothing and cannot reveal whether another project's artifact exists.
- [ ] API/OpenAPI/contract tests, Ruff, Pyright, size-bound tests, restart/idempotency tests, and quality gate pass.

Security: project/run authorization precedes artifact access.

Determinism: canonical bytes + immutable revision IDs.

Idempotency: reads never mutate; repeated identical writes are no-op.

Rollback: remove new persistence/read surfaces without changing optimizer math.

---

## PR274 — Dash Multivariate Decision Audit And Full Automatic-Optimizer Gate

Git metadata:

- Branch: `feat/dash-multivariate-decision-audit`
- Base: exact `main` commit after PR272 and PR273 merge
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested title: `feat(dash): add automatic optimizer decision audit`
- Required squash subject: `feat(dash): add automatic optimizer decision audit`
- Merge method: squash only
- Parallel wave: final integration; two-agent ownership inside one PR
- Depends on: PR264-PR273

Owned paths:

- Agent A: Multivariate Dash page, Plotly figure builders, Multivariate-only CSS.
- Agent B: callbacks/view-model, section adapters, deterministic UI fixtures, end-to-end tests, page documentation.
- Shared boundary: PR273 section contracts are immutable during this PR.

Tabs are exactly:

1. `Universe`
2. `Risk Model`
3. `Optimization`
4. `Validation`
5. `Final Portfolio`

Tasks / Acceptance — identical checklist:

- [ ] Add Multivariate Statistics as the fourth Dash page and an `Optimize portfolio automatically` action for profile `return_risk`; the action accepts only allowed profile settings/constraints and never asks the user to choose individual ISINs or one optimizer method.
- [ ] Above the tabs render one always-visible `Portfolio Candidate Return / Risk` Plotly scatter from PR273 decision data: X = OOS annualized volatility, Y = OOS annualized return for scored configurations, hover includes method/risk model/window/OOS Sharpe/Sortino/CVaR/max drawdown/turnover, and the algorithmic winner is uniquely highlighted.
- [ ] `Universe` tab renders an exact funnel `input -> eligible -> Pareto -> optimizer universe`, a Return/Risk before-vs-after scatter, and when Bivariate reduction occurred a cluster/redundancy heatmap or cluster map. Clicking/hovering a rejected point reveals its persisted reason and evidence; no UI-generated reason is allowed.
- [ ] `Risk Model` tab renders all persisted risk-model candidates with availability, observation count, condition number/stability, shrinkage or EWMA parameter where applicable, and at least one diagnostics plot comparing candidate conditioning/stability. Selected winning model configuration is highlighted from the winner artifact.
- [ ] `Optimization` tab renders scored portfolio candidates and an efficient/Pareto trade-off view from persisted candidate metrics; candidate hover shows return, volatility, Sharpe, Sortino, CVaR, max drawdown, diversification ratio, holdings/effective holdings, maximum weight, and method/risk-model/window identity. Blocked candidates remain inspectable with reason code.
- [ ] `Validation` tab renders cumulative OOS performance by candidate, OOS Return/Risk scatter, and weight-stability heatmap across walk-forward refits. All series are from PR273 validation section; Dash performs no backtest or return calculation.
- [ ] `Final Portfolio` tab renders final capital weights, percent risk contributions, and income contributions when available. If income is unavailable, render explicit unavailable reason and no zero-income chart. Also show final full-history metrics and the winner's OOS scorecard metrics side by side with labels distinguishing them.
- [ ] Every one of the eight PR269 decision stages is represented by at least one visible plot/table/decision explanation on this page or an explicit visible `not_applicable` stage reason. A static registry test maps each stage ID to its UI region and fails if any stage is uncovered.
- [ ] Deterministic several-hundred-ISIN journey starts from a prebuilt 400-listing project fixture, reaches <=250 automatic optimizer universe without manual per-ISIN picking, evaluates bounded model configurations, selects one OOS winner, restores after browser/API restart, and renders every required plot from persisted artifacts. No exhaustive subset/weight-grid call is observed.
- [ ] Four-page two-project journey proves project B cannot display project A Universe points, clusters, candidates, validation series, winner, final weights, or decision reasons; Dash Docker build, Compose profile, focused tests, contract checks, architecture tests, Ruff, Pyright, and `uv run portfell-quality pr` all pass from one SHA.

Security: decision sections are already authorized; browser state never authorizes a run/artifact.

Determinism: immutable decision revisions map one-to-one to stable trace inputs and winner highlight.

Idempotency: chart/tab interactions are read-only; identical optimizer start reuses logical run.

Rollback: revert Multivariate Dash page/end-to-end layer; optimizer backend and prior Dash pages remain independently usable.

---

## Series completion checklist

The planning series is finished only when PR264-PR274 are merged and all statements below are proven from one clean `main` SHA:

- exactly four Dash workflow pages exist and route/project isolation tests pass;
- Univariate has the always-visible Return/Volatility universe scatter and Return/Risk frontier;
- Bivariate has the always-visible Return/median-dependence universe scatter plus six-metric selector and nine detail views;
- automatic `return_risk` optimization requires no manual per-ISIN selection or manual optimizer-method choice after input universe/settings are fixed;
- automatic universe selection never adds an out-of-universe listing and produces <=250 optimizer listings;
- production weight optimization never enumerates all ISIN subsets or a several-hundred-dimensional weight grid;
- every important decision is persisted as a PR269 DecisionArtifact and covered by PR274 UI or explicit `not_applicable` reason;
- winner selection is OOS walk-forward based with the frozen ranking/tie rules;
- final output contains weights, OOS metrics, full-history metrics, risk contributions, and income contributions when evidence exists;
- no Dash module reads database/provider/lake/table-I/O or recomputes financial formulas;
- all named tests, contracts, architecture checks, Docker/Compose checks, and repository quality gates pass.