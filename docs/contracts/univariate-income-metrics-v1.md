# Univariate income metrics v1

## Table of contents

- [Purpose](#purpose)
- [Metric contract](#metric-contract)
- [Filtering](#filtering)
- [Presentation](#presentation)

## Purpose

This contract defines the income-first, full-universe Univariate read model. A
row is identified by `(isin, exchange, code)` and is calculated from one coherent
adjusted-close/dividend snapshot.

## Metric contract

The executable registry in `portfell.univariate_metric_catalog` is authoritative.
It contains data-quality, income/distribution, return/risk, risk-adjusted and
distribution-shape metrics. `history_years` is the valid quote span in days
divided by `365.25`; `observation_count` counts valid adjusted-close points;
`missing_ratio` uses observed trade dates in the coherent snapshot. Distribution
cash amounts are trailing positive events only and never receive invented FX.
Unavailable values are `null` with a typed reason, never zero or NaN.

## Filtering

Numeric metrics use inclusive full-precision `lower`/`upper` bounds and categorical
metrics use an allowed-value set. Different metrics combine with AND; values within
one categorical metric combine with OR. Preview is read-only and the sole commit
is `Apply selection & compute downstream`.

## Presentation

Every metric has one card with a distribution plot, summary anchors and selector
rail. Desktop geometry is 60% plot / 30% table / 10% controls; mobile order is
plot, table, controls. The canonical Plotly registry uses histograms plus ECDFs,
with explicit zero/bounded axes where applicable and five-decimal display formatting.
