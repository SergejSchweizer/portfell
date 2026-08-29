# Multivariate Input Snapshot

## Table Of Contents

- [Purpose](#purpose)
- [Eligibility Policy](#eligibility-policy)
- [Pinned Inputs](#pinned-inputs)
- [Authority Boundary](#authority-boundary)

## Purpose

`portfell.multivariate_inputs` owns the immutable hand-off into Multivariate
Statistics. A `MultivariateInputSnapshot` is constructed only from an already
authorised project dependency closure; it never reads a global current
selection, scans unpublished data, or starts bootstrap, Univariate, or Bivariate work.

## Eligibility Policy

The `DistributionEtfPolicy` is explicit and versioned. It requires typed
`instrument_type=ETF`, a typed regular `distribution_frequency` of `monthly`,
`quarterly`, or `semiannual`, production-eligible quote history, two or more
distinct `(isin, exchange, code)` listing keys, and 100 shared daily return
observations. Mixed supported frequencies remain in one exact Bivariate and
Multivariate universe. Annual, irregular, accumulating, and unknown frequencies
remain ineligible. Frequency is an eligibility criterion, not a claim about
income quality or sustainability.

## Pinned Inputs

Each snapshot pins the project snapshot, metadata selection, Univariate run and
selection, Bivariate run, sorted full listing keys, quote/dividend artifact
identities, aligned calendar, period, observation count, policy, and a
deterministic dependency hash. Rejections are persisted as stable reason codes;
there is no implicit fallback to a newer selection or a weaker policy.

## Authority Boundary

The PostgreSQL-hosted service uses `ExplicitMultivariateInputAdapter` only after
it resolves and authorizes its immutable dependency closure. Later Multivariate
services persist and authorize the resulting snapshot id; browser values and
latest/current pointers cannot reconstruct authority.
