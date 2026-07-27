# Diversification Window

## Identity

- Route: `/projects/:projectId/diversification`
- Funnel stage: Diversification
- Shared layout: authenticated header and footer

## Purpose

Review redundancy and diversification structure in the candidate set, inspect decision-relevant pairs, and persist a pre-portfolio selection.

## Server-owned inputs

Candidate-set identity, cluster summaries, cluster membership, authorized pair metrics, heatmap data, top redundant pairs, diversification candidates, quality warnings, and persisted preferences or exclusions.

## Layout and states

Provide cluster overview, membership table, correlation heatmap, redundant-pair ranking, diversification candidates, pair inspector, selection controls, warnings, and loading/running/complete/failed/stale/sparse states.

## User actions

Open a cluster, inspect a pair, paginate top-k pairs, compare charts and metrics, mark preferred or excluded instruments, save the pre-portfolio selection, and continue to Portfolio.

## Acceptance

- [ ] Large candidate sets remain usable without materializing a dense matrix in browser memory.
- [ ] Reversed pair orientation resolves to the same canonical pair presentation.
- [ ] Insufficient overlap and unavailable metrics are explicit.
- [ ] Persisted preferences reopen deterministically and do not schedule duplicate computation.
- [ ] Heatmap, ranking, cluster, and pair ordering follow committed stable rules.

## Security

Cluster counts, autocomplete, heatmap cells, pair search, and inspector details require authorization to both underlying instruments and the owning run.

## Components and tests

Use approved ClusterSummary, ClusterTable, Heatmap, RankedPairList, PairInspector, MetricGrid, ComparisonChart, PreferenceControl, and SelectionSummary components. Cover large sparse, reversed pair, insufficient overlap, corrected values, stale run, and persisted decision fixtures.
