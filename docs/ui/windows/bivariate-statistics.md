# Bivariate Statistics page


## Table Of Contents

- [Purpose](#purpose)
- [Module boundary](#module-boundary)
- [Contract](#contract)
- [Acceptance](#acceptance)

- Route: `/bivariate-statistics`
- Page ID: `bivariate_statistics`
- Component: `apps/web/src/pages/bivariate-statistics.tsx`

## Purpose

Run and present server-computed pairwise statistics for the automatic all-results selection produced
when univariate statistics complete. The server's automatic all-results selection is an internal
persistence hand-off, not a separate browser filter module.

## Module boundary

Bivariate Statistics consumes the persisted selected-ISIN set from Univariate Statistics and owns
pairwise rows and matrices. It must not modify the metadata or univariate selections, and portfolio
construction remains a later module.

## Contract

The page preflights through `POST /api/bivariate-statistics/plan`, starts
`POST /api/bivariate-statistics/runs`, reports server progress, and loads bounded results from
`GET /api/bivariate-statistics/runs/{run_id}/results`. Pair construction, limits, calculations,
storage, and ranking remain backend responsibilities.

Historical market data is refreshed centrally by the shared-market operations service. This page
contains no provider-download action and renders pairwise computation only after the selected
project's shared-market coverage is ready.

Every pairwise metric and matrix in one run uses the same universe-wide date intersection. Summary
and matrix contracts expose `date_start` and `date_end`; every facts table renders that aligned data
period so values from different tabs and windows are directly comparable.

The pairwise-dependence window presents Covariance, Pearson, Spearman, Downside Correlation, Tail
Dependence, and Co-exceedance as tabs. Tail Dependence and Co-exceedance use the same
upper-triangular, colour-scaled, hoverable matrix treatment as the correlation tabs. Their facts
tables show the aligned period, pair count, shared observations, and distribution summary. Tail
Dependence additionally exposes its 90th percentile; ≥30% and ≥50% pair counts; worst pair; best
tail diversifier (with its co-exceedance rate); the ISIN with highest average tail dependence;
average simultaneous-tail loss severity; median/minimum joint-tail event counts; rolling
tail-dependence stability; and cluster count/size using λᴸ ≥ 30% edges. These calculations are
server-derived from persisted pair statistics, including the persisted joint-tail loss, event-count,
and rolling-stability fields.

Co-exceedance presents its 90th percentile; the 0.25% independent-pair reference and the average
multiple of it; counts at 1%, 2.5%, and 5%; the worst pair with expected joint-tail days per year
and λᴸ; the best joint-tail diversifier; ISIN co-exceedance centrality; observed event-count
evidence; rolling stability; and clusters joined by a co-exceedance rate of at least 1%.

Rolling-Correlation and Drawdown Overlap are tabs in the same dependence window. Each presents its
distribution alongside the aligned period, average/median, 90th percentile, number of pairs at or
above 10%, best and worst pair, most exposed ISIN, and cluster size. For Rolling-Correlation, lower
values identify more stable diversification relationships; for Drawdown Overlap, lower values
identify pairs less likely to remain in drawdown together.

The Tail-Risk Scatter tab renders one point per ISIN pair, with Tail Dependence on the horizontal
axis and Co-exceedance Rate on the vertical axis. Its server-provided medians form four visually
labelled quadrants: lower-left is the best-diversifier region and upper-right is the joint-tail-risk
concentration region. The plot zooms its axes to the observed pair-value ranges with a small margin,
draws labelled grid ticks, and exposes a hover tooltip with both listing labels, ISINs, and values.
Its facts table exposes all four quadrant counts, Pareto-best diversifier count and leading pair,
the highest combined tail-risk pair, average λᴸ and co-exceedance multiples over independence,
the ISIN with the most upper-right links, upper-right cluster size, rolling stability for both
axes, and the joint-tail-event evidence. It loads the complete persisted pair set rather than the
bounded results page.

The persistent project sidebar identifies the active project and three-module
workflow hierarchy. A project switch clears the local pair plan, run, results,
and status message before this page loads the replacement project workflow.

## Acceptance

The page blocks execution when upstream filtering is incomplete, empty, stale, or over the configured
pair limit. It prevents duplicate runs, represents empty and partial results explicitly, and provides
accessible tabular output on desktop and a usable responsive representation on narrow screens.

The stateful two-project browser journey computes the active project's pair
statistics and selects every pairwise-dependence tab, including Tail Dependence and
Co-exceedance.
