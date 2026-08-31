# Staged analysis read-plane v1

Status: Frozen

This contract is the normative execution, progress, revision, result-read and performance contract for the Portfell Metadata -> Univariate -> Bivariate -> Multivariate workflow. PR384-PR396 must preserve it unless a later explicit contract PR replaces it.

## 1. Scope and authorities

Portfell remains a single-user Python application with Plotly Dash mounted on FastAPI. The current API/Dash container is the only Portfell application runtime. A bounded in-process analytical executor may be owned by that API process. Redis, Celery, RQ, a new Compose worker service, Node, a second application process used as an analytical authority, and a second application-state authority are prohibited.

Application/job state is durable in `portfell_dash`. Market data remains read-only external authority through the existing market gateway. Completed analysis runs, selections, decisions and analytical artifacts remain immutable.

Page rendering, route changes, resize events, status polling, table pagination, chart interaction and filter preview are read operations. None is a computation trigger.

## 2. Exact user workflow

There are exactly two normal-flow user commit actions that can initiate analytical work:

1. Metadata primary action: `Create universe & compute Univariate`.
2. Univariate primary action: `Apply selection & compute downstream`.

No third normal-flow computation trigger is authorized by this contract.

The workflow is:

```text
Metadata predicates
  |
  v
[Create universe & compute Univariate]
  |
  +--> immutable Metadata Universe U
  +--> queued/running Univariate job over every member of U
          |
          v
      immutable Univariate result UNI
          |
          +--> read-only filter preview; no analytical recomputation
          |
          v
      [Apply selection & compute downstream]
          |
          +--> immutable Selection S
          +--> Bivariate job B(S)
                    |
                    v
               Multivariate job M(S, B, return_risk)
```

Univariate is computed once for the complete persisted Metadata universe and exact market snapshot. Univariate filters never reduce compute input and never rerun Univariate.

Filter preview is read-only. A preview may change preview counts, page rows and chart data but must not create a `selection_id`, analysis run, analysis job, DecisionArtifact or analytical artifact.

`Apply selection & compute downstream` is the only v1 filter-commit action. It persists the exact filtered full-identity membership, queues matching Bivariate work, and only after matching Bivariate success queues Multivariate with objective exactly `return_risk`. Alternate Multivariate objectives remain explicit user actions on `/multivariate`; they are not run for every preview or as part of this automatic downstream chain.

## 3. Analysis job state machine

Job status is exactly one of:

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`

Allowed lifecycle transitions are:

```text
queued -> running
queued -> cancelled
running -> succeeded
running -> failed
running -> cancelled
```

Recovery may reclaim a queued or stale running job by starting a new execution attempt. Recovery does not create a new logical job identity for the same active logical input. Terminal jobs are not silently returned to a non-terminal status.

Every job-status payload contains:

- `job_id`
- `stage`
- `status`
- `input_ref`
- optional `run_id`
- `progress_current`
- `progress_total`
- `progress_phase`
- `attempt`
- `failure_code`
- creation/update/start/finish or equivalent persisted timestamps
- immutable source/revision identity sufficient to prevent data from one universe or selection revision from being displayed as another revision

`failure_code` is a typed public code only. Tracebacks, SQL text, DSNs, credentials and private runtime details are not job-state fields and are not returned to Dash.

## 4. Progress semantics

Progress is backend-owned persisted job state. Percentage is logical completed work, never elapsed-time percentage and never an ETA.

When a total is known, both `progress_current` and `progress_total` are defined and satisfy:

```text
0 <= progress_current <= progress_total
```

Within one execution attempt, `progress_current` is monotone non-decreasing and `progress_total` cannot be silently reinterpreted as another unit. A process restart may create a new attempt and may restart work from immutable inputs. That restart increments/exposes `attempt`; the UI must not pretend progress from the previous attempt continued uninterrupted.

When total is not known, progress is indeterminate: `progress_total` is null and percentage is not fabricated. Phase/status text remains available.

### Univariate

Univariate work units are processed members of the persisted Metadata universe. After market materialization makes the exact membership work count known, `progress_total` equals the exact persisted universe-member count. Success reaches that exact total.

### Bivariate

Bivariate work units are planned candidate pairs for the persisted Selection. Once the exact candidate-pair plan is known, `progress_total` equals the exact planned pair count. Success reaches that exact total.

### Multivariate

Multivariate progress is logical phase progress, not remaining-time estimation. The phases are frozen in this exact order and spelling:

1. `inputs`
2. `risk_model_and_candidates`
3. `walk_forward_validation`
4. `scorecards`
5. `structural_diagnostics`
6. `decision`
7. `artifact_persistence`
8. `complete`

No synthetic Bivariate+Multivariate percentage exists. Downstream UI presents Bivariate and Multivariate stage states separately.

## 5. Revision identity and stale-result behavior

A displayable analytical revision is identified by its immutable upstream identities, including the relevant universe/selection/run/job identifiers and market-source snapshot identity. Read DTOs carry sufficient revision identity to reject cross-selection or cross-snapshot display.

While a new selection revision is computing, the last completed downstream revision may remain visible only if it is explicitly labelled `Previous selection`. Old-revision and current-revision values must never be combined in one KPI, chart, table or Decision view.

A completed prior revision is never mutated to represent a new selection. A failed or cancelled current job does not promote the previous revision to current and does not display false completion.

## 6. Durable execution and idempotency

Queued/running jobs are durable. Process startup may scan only queued/stale jobs and reclaim them idempotently. Shutdown stops accepting new work cleanly.

Repeated submit actions for the same logical active input converge on one active logical job. Executor saturation must not block submission or status reads waiting for a compute slot.

Restart during market materialization or computation may restart an attempt from immutable input identities. It must not create duplicate completed analysis artifacts or duplicate DecisionArtifacts. If an exact source-pinned analysis run already succeeded, execution reuses/links that completed run instead of recomputing it.

Status/read calls do not execute jobs and do not access the market gateway.

## 7. Row-addressable result contract

Normal interactive Univariate and Bivariate rows are stored/read in a bounded row-addressable form. A normal page read must not deserialize a complete large JSON array merely to return one page.

Every row preserves the complete listing identity `(isin, exchange, code)` for each represented listing. Pair rows preserve both complete identities. Stable ordering is mandatory so repeated requests for the same immutable revision and paging/filter parameters return the same row order.

Paged row reads use:

- default page size: `100`
- maximum page size: `500`
- Univariate chart-point cap: `500`
- Bivariate chart-point cap: `1000`

Filtering and pagination occur server-side or within the bounded application read plane. The browser is never given all Bivariate pairs only to slice them locally.

The result read plane separates small manifests/summaries from rows. Manifest data includes immutable revision/run identity, artifact/result type, exact item count where known and bounded metadata necessary to interpret the rows. Large market history and complete analytical tables are not browser state.

## 8. Page read API contract

Normal Dash page code uses explicit bounded read operations rather than heavyweight all-artifact reads. The normal page read plane provides the equivalent of:

- job/status read by `job_id`;
- current workflow/revision identifiers and readiness;
- Univariate small summary/manifest;
- paged Univariate rows with bounded filter/sort parameters;
- bounded Univariate chart data;
- Univariate filter-preview count/rows/chart projection without persistence side effects;
- Bivariate small summary/manifest;
- paged Bivariate rows with bounded filter/sort parameters;
- bounded Bivariate chart data;
- Multivariate small summary, winner/Decision projection, bounded scorecards/performance/structure projections needed by the page.

The existing diagnostic `run_detail()` may remain for bounded diagnostic/API use, but normal Dash page rendering and polling must not call it.

A page render/read, route transition or poll must not:

- call `run_detail()` as its normal data source;
- call the market gateway;
- invoke financial computation;
- create or transition analytical jobs/runs/artifacts/selections/decisions;
- deserialize an unbounded row collection;
- place complete market history or complete analytical tables into browser state.

## 9. Dash polling and presentation

Browser state is limited to identifiers, small summaries, filter presentation state, readiness and persisted progress. Complete analytical tables and market history are prohibited.

While a current job is `queued` or `running`, status polling interval is exactly `1000 ms`. Polling is disabled for terminal job states.

Progress presentation includes stage, status, phase and `current / total` plus percentage when total is known. When total is unknown, it uses an indeterminate presentation with phase/status text. Status must be accessible through semantic text; color alone is insufficient.

Terminal success shows 100% only when persisted job state says the logical work completed. Failed or cancelled state preserves its status/typed reason and never shows a false 100% success.

## 10. Performance budgets

PR394 and PR396 measure these budgets on deterministic local PostgreSQL/Dash fixtures, never the live market database. Measurements include latency plus structural evidence such as query count, returned-row count and response-body size so an unbounded implementation cannot pass on timing alone.

Frozen p95 budgets:

| Operation | p95 budget |
| --- | ---: |
| Warm page-content read | `<= 750 ms` |
| Warm filter-preview read | `<= 400 ms` |
| Warm status read | `<= 200 ms` |
| Active-computation navigation | `<= 1000 ms` |

Every page-specific JSON/Dash callback response body on the deterministic performance fixture is `<= 512 KiB`.

A budget is not permission to violate structural caps. A response that meets latency while loading an unbounded result set, touching the market gateway, recomputing finance or exceeding the row/payload contracts fails acceptance.

## 11. Financial and security invariants

This staged execution contract changes orchestration and read boundaries, not financial formulas. Existing Univariate, Bivariate and Multivariate financial semantics, annualization, adjusted-close authority, missing-data behavior, OOS winner selection and DecisionArtifact semantics remain unchanged unless another explicit financial contract changes them.

Full listing identity remains authoritative. Missing adjusted close remains typed unavailable; raw close is not a fallback. No secret, DSN, SQL detail or traceback is persisted in public job failure state or returned to the browser.

## 12. Negative-space acceptance

The following are explicitly prohibited:

- any third normal-flow computation trigger in addition to the two frozen primary actions;
- computing on page render, route change, resize, poll, table pagination, chart interaction or filter preview;
- preview-side selection/run/job/artifact creation;
- queuing Multivariate before the matching Bivariate succeeds;
- silently running alternate objectives during preview/downstream default flow;
- combining previous-selection and current-selection values;
- synthetic combined Bivariate+Multivariate progress;
- elapsed-time/ETA percentages presented as calculation completion;
- normal Dash page use of `run_detail()`;
- unbounded large JSON row-array reads for interactive pages;
- all-pairs Bivariate payloads sent to the browser for local slicing;
- Redis, Celery, RQ, a new Compose worker, Node or another application authority.

These rules, labels, states, units, caps and budgets are frozen for PR384-PR396.