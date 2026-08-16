# Universe And History Pipeline Amendment

Status: active normative amendment to `BACKLOG.md` PR264-PR276, `docs/backlog/plotly-dash-multivariate-optimizer-ui.md`, `docs/backlog/plotly-dash-professional-plots-weekly-refresh.md`, and the current-code correctness amendments.

Business outcome: throughout Metadata Builder, Univariate Statistics, Bivariate Statistics, and Multivariate Statistics, the user can always see how many listings/unique ISINs remain, how much usable history remains, what was removed since the previous stage, and which exact time range/observation count backs the current analytical revision. The browser renders persisted/server-produced evidence only and never recomputes research history semantics locally.

## Product invariant

Every workflow page renders one compact `Universe & History` summary and one consistent `Research Universe & History Pipeline` visualization before page-specific analytical tabs. The same stage/revision semantics are reused by explicit button-triggered runs and the Sunday refresh.

The display must distinguish all of the following concepts explicitly:

- `listing_count`: count of full listing identities `(isin, exchange, code)`;
- `unique_isin_count`: count of unique ISIN strings;
- `history_envelope_start/end`: earliest/latest usable observation anywhere in the stage universe; this is descriptive coverage only;
- `common_date_start/end`: intersection calendar start/end actually usable jointly by the stage when a common calendar is meaningful;
- `common_observation_count`: number of observations in that common calendar;
- stage-specific individual-listing observation distribution for Univariate;
- stage-specific pairwise shared-observation distribution for Bivariate;
- aligned optimization calendar plus walk-forward train/test ranges for Multivariate;
- `removed_listing_count` and stable `removal_reason_counts` from the previous stage or internal selector phase.

`Observed history envelope` and `Common usable history` are never presented as synonyms. If a concept is not applicable, return/display typed `not_applicable` plus a reason; never substitute `0`, an empty date, or a guessed range.

## Shared persisted contract

PR269 freezes a canonical server-side `ResearchUniverseSnapshot` (or equivalently named immutable contract) with at least:

```text
stage_id
revision_id
project_id
input_listing_count
output_listing_count
unique_isin_count
removed_listing_count
removal_reason_counts
history_envelope_start
history_envelope_end
common_date_start
common_date_end
common_observation_count
minimum_listing_observations
median_listing_observations
maximum_listing_observations
pair_count
minimum_pair_observations
median_pair_observations
maximum_pair_observations
availability_status
availability_reason
```

Fields not applicable to a stage are typed unavailable/not-applicable, not numeric/date sentinels. Counts and dates are computed from the exact immutable input/revision used by the analytical stage. Full listing identity remains authoritative; unique ISIN count is secondary display information only.

Internal Multivariate selector phases additionally persist stage summaries for `input_eligibility`, `univariate_pareto`, `bivariate_redundancy`, `risk_model_candidates`, `portfolio_candidates`, `walk_forward_validation`, `winner_selection`, and `final_portfolio` so the user can see both universe shrinkage and history shrinkage through the optimizer.

## Shared visual contract

PR264 extends `ProfessionalPlotContract` and frozen figure IDs with these figures/components:

- `Universe & History` summary strip/cards;
- `Research Universe & History Pipeline`;
- `Univariate Listing History Coverage`;
- `Pairwise Shared-History Distribution`;
- `Walk-Forward Training / Test Coverage`.

Every figure requires descriptive title, explicit axis labels/units, semantic legend, deterministic hovertemplate, revision/as-of context, stable ordering, typed unavailable states, responsive layout, and accessible text metadata.

### Research Universe & History Pipeline

The persistent cross-stage figure uses one row per visible stage and communicates both dimensions at once:

- exact listing count and unique-ISIN count as labels/annotations;
- horizontal date segment for `Common usable history` when applicable;
- explicit marker/annotation for observation count;
- removed count versus previous stage;
- hover with stage, revision, listings, unique ISINs, removed count/reasons, history envelope, common usable range, and common observations.

Stage order is fixed: `Metadata -> Univariate -> Bivariate -> Multivariate -> Final portfolio`. Future/blocked stages remain visible with typed status rather than disappearing. No stage may fabricate a common range before a valid analytical revision exists.

## PR264 mandatory additions — shared presentation contracts

- Freeze immutable presentation models for `UniverseHistorySummary`, `UniverseHistoryPipelineStage`, history range/status values, and the five shared figure/component IDs above.
- Add gateway read methods that receive project identity and return server-owned universe/history snapshots; Dash may not derive dates/counts from raw quote/pair rows.
- Add deterministic two-project fixtures covering different listing counts, duplicate-ISIN listings, different history envelopes/common calendars, unavailable downstream stages, and stale/previous revisions.
- Extend ProfessionalPlotContract tests to reject missing title/axis/legend/hover/revision metadata for all history figures.

## PR265 mandatory additions — shell continuity

- The shell/process overview shows a compact current-stage listing count and common-history indicator sourced from the same snapshot contract; it never becomes a second calculation authority.
- Project switching clears old-project universe/history evidence before the replacement project snapshot paints.

## PR266 mandatory additions — Metadata Builder

- After project metadata/initial market fill is available, show `Universe & History` with project `listing_count`, `unique_isin_count`, history envelope and common usable range if quote history exists.
- Before quote history exists, show history as `Unavailable — market history not loaded`; do not infer dates from metadata issue/inception fields unless those are explicitly the market-observation source.
- Initialize the pipeline figure with Metadata evidence and downstream stages as typed `not_run`/blocked states.

## PR267 mandatory additions — Univariate

- Persist/serve the Univariate `ResearchUniverseSnapshot` for the exact run/selection revision: input/output listing count, unique ISIN count, removed/rejected count and reasons, history envelope, per-listing observation min/median/max, and common overlap that would be available if the surviving listings proceed jointly downstream.
- Extend the always-visible Univariate Return/Risk hover with listing history start/end and return-observation count.
- Add professional `Univariate Listing History Coverage`: every currently relevant full listing is represented, sorted deterministically by first usable observation then listing identity; no random sampling. For large universes use paging/scrolling or an equivalent bounded rendering strategy without hiding records.
- The page summary explicitly labels individual-history distribution separately from the downstream common overlap.

## PR268 mandatory additions — Bivariate

- Persist/serve the Bivariate snapshot using the exact eligible pair set from the correctness amendment: surviving listing/unique-ISIN count, exact pair count, pairwise shared-observation min/median/max, history envelope, and common overlap of the surviving listing universe for Multivariate hand-off.
- Add professional `Pairwise Shared-History Distribution` with X=`Shared observations per pair` and Y=`Pair count`; hover includes observation bucket/range, exact pair count, percentage and analytical revision.
- Every Bivariate pair/heatmap hover that already exposes `shared-observation count` uses the same exact pair evidence as this distribution.
- The page must not describe pairwise history as the Multivariate common optimization calendar.

## PR269 mandatory additions — canonical analytical contract

- Freeze `ResearchUniverseSnapshot`, availability semantics, stage IDs, removal-reason registry, date/observation definitions and canonical serialization before PR270/PR271 branch.
- Freeze exact definitions for `history_envelope` versus `common usable history`; listwise common-date semantics must match the actual Multivariate risk-model observation policy after the correctness fix.
- Snapshot identity includes project/revision/input identities and algorithm/contract version so identical immutable evidence has a stable ID.

## PR270 mandatory additions — automatic universe selector

- Emit deterministic universe/history snapshots after eligibility, Univariate Pareto reduction and Bivariate redundancy reduction, including exact before/after listing counts and removal reason counts.
- For every reduction, recompute the downstream common usable calendar from the surviving full listing set and persist the before/after history effect. This is evidence only and must not be used as an undocumented optimization objective.
- Selector DecisionArtifacts reference the corresponding snapshot IDs so a rejected listing can be traced to both selection evidence and the resulting universe/history state.

## PR271 mandatory additions — risk-model/candidate evidence

- Every risk-model configuration exposes aligned date start/end and observation count from its actual covariance estimation sample; these values feed the Multivariate universe/history audit.
- Candidate/configuration evidence retains the training-window identity used by that risk model; no configuration may display another configuration's history range.

## PR272 mandatory additions — Multivariate orchestration and walk-forward

- One Multivariate run publishes immutable universe/history snapshots for every internal decision stage and the final winner.
- Walk-forward validation persists exact train start/end, test start/end, training observation count and test observation count for every split/configuration.
- Final refit/final portfolio records the exact aligned calendar used for the published weights.
- Progress/status and history evidence are attempt-safe: a stale worker cannot overwrite a newer snapshot or published final range.

## PR273 mandatory additions — persistence/API

- Persist universe/history snapshots under project + analytical-run authority and expose one compact current pipeline projection plus lazy detailed history sections.
- Reads are non-mutating and project-scoped; Project A can never receive Project B counts/ranges.
- Historical revisions remain auditable; current projection points to one explicit revision per stage rather than overwriting old evidence.

## PR274 mandatory additions — Multivariate Dash optimizer

- Render `Universe & History` immediately below the Multivariate title/objective and before the progress control/results.
- Render `Research Universe & History Pipeline` above tabs, showing Metadata -> Univariate -> Bivariate -> Multivariate -> Final portfolio with exact counts and common-history ranges.
- Extend `Universe` tab with before/after universe/history evidence for eligibility/Pareto/redundancy.
- Extend `Risk Model` tab with aligned observation range/count for every compared model.
- Add professional `Walk-Forward Training / Test Coverage`: one deterministic row or lane per split/configuration grouping, visually distinct train/test segments, X=`Date`, hover with configuration ID, split ID, train range/count, test range/count and status.
- `Final Portfolio` shows final holding count, unique ISIN count, final refit common range and observation count next to capital/risk/income plots.
- Registry tests enumerate all new figures and enforce the ProfessionalPlotContract.

## PR275 mandatory additions — production cutover

- Final Dash/FastAPI E2E verifies the Universe & History summary and pipeline on Metadata, Univariate, Bivariate and Multivariate routes after React deletion.
- E2E project switching proves counts/ranges never bleed across projects; restart restores the exact persisted revision/range.
- Cutover may change transport/routes but not history semantics, labels, hover content or figure IDs.

## PR276 mandatory additions — Sunday full research refresh

- The weekly orchestrator publishes/reuses the same `ResearchUniverseSnapshot` artifacts as explicit runs; there is no cron-only count/date implementation.
- Per-project terminal cycle summary includes final Uni/Bi/Multivariate snapshot IDs, listing counts and common usable date ranges/observation counts, plus final portfolio holding count.
- Re-running the same immutable weekly cycle yields byte-stable snapshot identities and no duplicate history artifacts.
- Integration fixture proves A->B versus B->A processing order produces identical per-project counts/ranges and that a failed/blocked project exposes typed unavailable downstream history rather than stale previous-project data.

## Series completion additions

The PR264-PR276 series is incomplete until one production-like fixture proves, for at least two projects and one duplicate-ISIN/multi-exchange case:

1. every page shows exact listing count + unique ISIN count + revision-backed time-range evidence;
2. Metadata, Univariate, Bivariate, Multivariate and Final Portfolio pipeline rows remain visible in stable order;
3. Univariate distinguishes per-listing history from common downstream overlap;
4. Bivariate distinguishes pairwise shared-history distribution from Multivariate common calendar;
5. Multivariate displays aligned risk-model history and every walk-forward train/test range;
6. counts/ranges update deterministically after filters/selector reductions and show exact removal reasons;
7. unavailable/not-run/blocked history is typed, never represented as `0`, empty date, or guessed value;
8. manual runs and Sunday refresh produce the same snapshot semantics and identities for the same immutable inputs;
9. every new history figure passes title/axes/legend/hover/revision/responsiveness/accessibility checks.