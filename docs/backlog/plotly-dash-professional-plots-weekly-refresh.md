# Professional Plot And Weekly Research Refresh Amendment

Status: active normative amendment to `BACKLOG.md` and `docs/backlog/plotly-dash-multivariate-optimizer-ui.md`.

This amendment has precedence wherever the earlier PR264-PR275 specification is less specific or conflicts with the requirements below. It does not create a separate product workflow: Multivariate Statistics remains the portfolio optimizer.

## Professional Plot Contract

PR264 must freeze one shared `ProfessionalPlotContract` consumed by every Plotly figure built in PR267, PR268, and PR274. No page may introduce a local alternative plot style contract.

Every production Plotly chart must satisfy all of these rules:

- use a human-readable title that describes the analytical question, never a raw metric key;
- use explicit X and Y axis titles including units when the metric has a unit, for example `% p.a.`, `%`, `days`, `observations`, or `correlation`;
- expose an explicit legend whenever color, marker, line style, symbol, or multiple traces encode different semantic classes; legend labels are domain labels such as `Selected`, `Rejected`, `Winner`, `Baseline`, `Pareto frontier`, never `trace 0`;
- provide a deterministic Plotly `hovertemplate` for every point/cell/line. Hover content includes the stable object identity plus the key metrics used to interpret that object, with friendly labels, units, and consistent numeric formatting; raw Python/JSON field names are forbidden in hover text;
- provide labels for categorical color/status encodings and a visible explanation for unavailable/blocked/not-applicable states;
- use responsive/autosized layout, readable margins, non-overlapping titles/legends/axis labels, and no fixed canvas that clips on the tested desktop/tablet/mobile viewports;
- use stable trace names/order and stable `uirevision` or equivalent behavior so a refresh of the same analytical revision does not randomly reset semantic trace identity;
- render unavailable values as `Unavailable`/typed reason, never as zero, infinity, an empty hover field, or an unlabeled missing point;
- show the analytical revision/as-of context in the chart region or adjacent figure caption when two revisions could otherwise be confused;
- expose an accessible text label/description identifying the plot and its X/Y meaning; a plot is not accepted only because it is visually present.

PR264 acceptance is extended with contract tests that reject a production figure missing title, required axis labels, semantic legend metadata, or deterministic hovertemplate. Shared helpers must format percentages, ratios, counts, dates, ISIN/listing identities, and unavailable values consistently.

### PR267 amendment — Univariate plot

The always-visible Univariate plot must be presentation-ready:

- title: `Univariate Return / Risk Universe`;
- X axis: `Annualized volatility (% p.a.)`;
- Y axis: `Annualized geometric return (% p.a.)`;
- legend contains the applicable classes from `Selected`, `Rejected`, `Data-quality excluded`, and `Pareto frontier`;
- point hover contains at minimum ISIN, `code.exchange`, annualized geometric return, annualized volatility, Sharpe, Sortino, Expected Shortfall, maximum drawdown, distribution frequency, annual dividend yield, and return-observation count;
- Pareto-front hover identifies the listing and explicitly labels it `Pareto frontier`;
- visual regression/data tests assert title, axes, legend labels, hover fields, units, trace names/order, and no raw metric-key labels.

### PR268 amendment — Bivariate plots

The global Bivariate plot must be presentation-ready:

- title: `Bivariate Return / Diversification Universe`;
- Y axis: `Annualized geometric return (% p.a.)`;
- X axis title changes exactly with the selected metric and always includes its semantic name, e.g. `Median Pearson correlation`, `Median downside correlation`, `Median lower-tail dependence`;
- legend contains every semantic point/status class currently displayed;
- point hover contains listing identity, annualized return, selected median dependence metric, usable pair count, and the other available median dependence metrics;
- every heatmap has a descriptive title, row/column listing labels, named colorbar metric, and cell hover with both listing identities, metric value, and shared-observation count where available;
- Tail-Risk Scatter has explicit axis labels, legend, and point hover identifying the pair plus all relevant tail-risk values;
- tests assert titles, axis labels, colorbar/legend labels, hover templates, units, and stable ordering for the deterministic 201-listing fixture.

### PR274 amendment — Multivariate optimizer plots

Every optimizer/Decision Audit plot must satisfy the shared contract and use persisted DecisionArtifact evidence only. At minimum:

- global candidate chart title `Portfolio Candidate OOS Return / Risk`, X `OOS annualized volatility (% p.a.)`, Y `OOS annualized return (% p.a.)`, legend distinguishing `Winner`, `Eligible candidate`, `Baseline`, and any other rendered candidate class; hover includes method, risk model, training window, optimization objective, OOS return, volatility, Sharpe, Sortino, Calmar when available, CVaR, maximum drawdown, and turnover;
- Universe funnel has title, stage labels, exact counts, and hover/explanation for each stage; before/after scatter has explicit return/risk axes and legend for retained/rejected classes;
- redundancy heatmap/cluster plot has listing/cluster labels, named metric/color scale, and hover explaining representative/rejected relationship;
- Risk Model diagnostics have a title, named axes, legend identifying risk-model candidates, and hover with observation count, condition number, stability metric, and model parameter where applicable;
- Optimization trade-off plot has named axes/legend and candidate hover with the complete decision metrics needed to compare methods;
- Validation cumulative-performance plot has date/time X label, cumulative wealth/return Y label, candidate legend, and date/value hover; OOS Return/Risk scatter and Weight Stability heatmap have the same complete professional metadata;
- Final Portfolio capital weights, risk contributions, and income contributions each have a descriptive title, units, listing labels, hover values, and explicit unavailable reason instead of an empty chart.

A PR274 registry test must enumerate every production figure ID and prove it satisfies `ProfessionalPlotContract`. A figure added later without registering title/axes/legend/hover metadata must fail the test.

## PR275 amendment — preserve professional plotting at production cutover

PR275 may change deployment paths/container topology but must not regress figure semantics. Its Dash E2E cutover journey verifies the same title/axis/legend/hover contract on at least one Univariate, one Bivariate heatmap/global plot, and the Multivariate global candidate plot after React deletion and `/dash` prefix removal.

## PR276 — Sunday Full Research Refresh

Git metadata:

- Branch: `feat/weekly-full-research-refresh`
- Base: exact `main` commit containing merged PR275
- Git status: `planned`
- GitHub PR: `not opened`
- Suggested title: `feat(cron): refresh market data and all portfolio statistics weekly`
- Required squash subject: `feat(cron): refresh market data and all portfolio statistics weekly`
- Merge method: squash only
- Priority: P0 scheduled research freshness
- Depends on: PR275 and the final Multivariate Statistics optimizer contracts from PR269-PR274

Business outcome: one managed Sunday cycle refreshes canonical market data once and then recomputes/reuses the complete Univariate -> Bivariate -> Multivariate Statistics chain for every active project without browser interaction.

The current repository already schedules `0 9 * * 0` but uses `Europe/Amsterdam` and invokes only `python -m portfell.shared_market_refresh` inside `project-bootstrap-worker`. PR276 changes the managed production schedule to exactly `0 9 * * 0` with `CRON_TZ=Europe/Vienna` and changes the invoked command to the full research-refresh orchestrator.

Fixed stage order for one weekly cycle:

```text
Sunday 09:00 Europe/Vienna
        |
        v
1. shared market refresh
   quotes + dividends + splits
   de-duplicated active-project listing union, exactly once
        |
        v
2. Univariate Statistics for every active project
        |
        v
3. Bivariate Statistics for that project's resulting Uni selection
        |
        v
4. Multivariate Statistics = automatic portfolio optimization
   using the project's persisted Optimization objective/constraints
        |
        v
5. publish terminal per-project/per-stage status and cycle summary
```

If a project has no persisted Multivariate objective, the weekly run uses the frozen default `return_risk`. The cron never exposes or creates a separate Optimizer stage.

Owned paths and weak-agent hand-off:

- Agent A owns scheduler/orchestrator implementation: `src/portfell/shared_market_cron.py`, new `src/portfell/weekly_research_refresh.py`, any single CLI entry-point change in `pyproject.toml`, and orchestration unit tests owned by that module. Agent A must not edit Dash page/figure code.
- Agent B owns independent verification/operations: `tests/test_shared_market_cron.py`, new end-to-end weekly-refresh fixture/tests, `docs/shared-market-refresh.md`, `README.md` scheduled-job section, operational status/log documentation. Agent B must not edit orchestration code.
- Before parallel work, Agent A freezes the `WeeklyResearchCycleResult` and `ProjectResearchCycleResult` dataclasses/protocols plus exact stage IDs `market_refresh`, `univariate`, `bivariate`, `multivariate`; Agent B tests only those frozen contracts.
- Shared files such as `pyproject.toml` are Agent A-only. Documentation is Agent B-only. There is no dual ownership.

Tasks / Acceptance — identical checklist:

- [ ] Keep one managed cron block and set exact schedule `0 9 * * 0` with `CRON_TZ=Europe/Vienna`. Installation is idempotent, preserves unrelated crontab bytes, uses `/usr/bin/flock -n`, and status output reports the exact schedule/timezone. Tests reject daily schedules, Amsterdam timezone, duplicate managed blocks, or a second scheduler.
- [ ] Add one `weekly_research_refresh` orchestrator invoked inside the existing `project-bootstrap-worker`; no fourth long-running Compose service and no browser process is required. The host cron command contains no provider secret.
- [ ] Stage 1 invokes the existing canonical shared-market refresh exactly once for the de-duplicated active-project listing union and refreshes the existing datasets `quotes`, `dividends`, and `splits`. It must not perform a separate provider fetch per project.
- [ ] After successful shared refresh, pin the published/current shared-market revision used by the cycle. Enumerate active projects in stable project-ID order and resolve each project's immutable selection/settings under existing authorization/service boundaries.
- [ ] For each project, start/reuse Univariate Statistics against the fresh pinned market revision and the project's persisted Univariate settings. If no saved filter exists, use the existing documented no-filter/default selection policy; never invent a browser-only default. Wait for a terminal result before Bivariate starts.
- [ ] Apply the project's persisted Univariate selection to the new Univariate result and start/reuse Bivariate Statistics against that exact Univariate selection/revision. Bivariate starts only after Univariate succeeds. Persist/provide the same run progress/status contracts used by the UI.
- [ ] Start/reuse Multivariate Statistics only after Bivariate succeeds. Use the project's persisted `Optimization objective` and constraints; when objective is absent use exactly `return_risk`. Multivariate performs the automatic selector/solver/walk-forward/winner flow already defined by PR269-PR274 and publishes DecisionArtifacts/final portfolio normally.
- [ ] Failure isolation is exact: market-refresh failure blocks all project statistics and ends the cycle failed; a project's Univariate failure marks that project's Bivariate/Multivariate `blocked_upstream` and continues with the next project; Bivariate failure blocks only that project's Multivariate; Multivariate failure does not affect other projects. No failed stage is represented as successful/stale zero data.
- [ ] Re-running the same logical weekly cycle after interruption reuses existing market/statistics runs where input revisions/settings are unchanged, resumes incomplete work, and creates no duplicate logical run, duplicate winner, duplicate DecisionArtifact, or duplicate market business key. Lock contention starts zero provider/statistics work.
- [ ] Publish one redacted cycle summary containing cycle ID, local scheduled date/timezone, pinned market revision, project count, and per-stage `complete|failed|blocked|reused` counts. Logs contain no EODHD token, database password, project membership dump, SQL, or storage payload.
- [ ] Deterministic integration fixture with at least two projects proves one shared provider refresh, Uni -> Bi -> Multivariate ordering per project, persisted-objective use (`return_risk` default on one project and a non-default objective on the other), project-failure isolation, restart/resume, and byte-stable terminal summary. No browser must be open.
- [ ] Update operations docs to state: Sunday `09:00 Europe/Vienna`; one fetch of the active-listing union; then complete Uni/Bi/Multivariate refresh. Remove wording that says the scheduled job performs only shared-market refresh. Preserve a manual `run-once` path using the same orchestrator.
- [ ] Focused scheduler/orchestration tests, PostgreSQL/service integration tests, architecture tests, Ruff, Pyright, `docker compose config`, worker execution smoke test, and `uv run portfell-quality pr` pass from one SHA.

Security: the weekly orchestrator runs in the existing trusted worker with the operations provider credential and existing project/data authority. It must not move provider credentials to Dash/browser or create cross-project visibility.

Determinism: exact schedule/timezone, stable active-project order, immutable input revisions, persisted settings/objective, and existing algorithm versions determine one reproducible cycle plan.

Idempotency: `flock` plus existing logical run/content identities make repeated or resumed cycles converge on one market revision and one Uni/Bi/Multivariate result chain per project/input.

Rollback: revert PR276 to the prior shared-market-only cron behavior and prior scheduler module/docs. No database schema rewrite is required; statistics/DecisionArtifacts already published by a successful weekly run remain immutable/auditable.

## Amended series completion gate

The complete target is not finished until PR264-PR276 are merged and a clean production-like evidence run proves:

- every production Plotly figure complies with the Professional Plot Contract: descriptive title, labeled axes/units, semantic legend where applicable, deterministic hover menu, stable trace names/order, explicit unavailable states, and responsive/accessibility metadata;
- Multivariate Statistics remains the only optimizer page/run and all important optimizer decisions remain visualized;
- final production UI/runtime is the PR275 three-service Dash/FastAPI topology;
- the managed cron is exactly Sunday `09:00 Europe/Vienna` (`0 9 * * 0`), runs without a browser, refreshes shared market data once for the de-duplicated active union, then completes/reuses Univariate, Bivariate, and Multivariate Statistics for every active project in dependency order;
- the weekly Multivariate run respects each project's persisted optimization objective/constraints and defaults only a missing objective to `return_risk`;
- failure isolation, restart/resume, duplicate-run protection, two-project isolation, logs, Docker/worker execution, and all repository quality gates pass.