# Multivariate Portfolio Structure

## Table Of Contents

- [Purpose](#purpose)
- [Derived Facts](#derived-facts)
- [Interpretation Boundary](#interpretation-boundary)

## Purpose

`portfell.multivariate_structure` derives neutral, deterministic structure
facts from a canonical Multivariate risk-model artifact: covariance-derived
correlation clusters, principal components, explained and cumulative variance,
effective rank, effective independent drivers, and component loadings.

## Derived Facts

The persisted artifact supplies bounded, ordered component detail and keeps
dense matrices in the shared-artifact plane rather than browser payloads.

## Interpretation Boundary

Components are named only `Component 1`, `Component 2`, and so on. The module
does not infer economic labels without a separate typed exposure policy. Detail
access is bounded and ordered by absolute loading, while dense matrices remain
an artifact concern rather than a browser payload.
