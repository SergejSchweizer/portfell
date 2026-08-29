# Canonical Multivariate Risk Model

## Table Of Contents

- [Purpose](#purpose)
- [Artifact Contents](#artifact-contents)
- [Optimizer Boundary](#optimizer-boundary)

## Purpose

`portfell.multivariate_risk_model` creates one immutable joint covariance
artifact from a valid `MultivariateInputSnapshot`. The initial production
estimator is Ledoit-Wolf shrinkage; sample covariance and EWMA remain explicit
research choices. Pairwise Bivariate covariance is never substituted for this
common-calendar matrix.

## Artifact Contents

The artifact records the estimator, parameters, log-return policy, full listing
order, period, observations, covariance values, shrinkage and eigen diagnostics,
PSD state, availability reasons, and algorithm version. `solver_input()` is the
only conversion boundary for covariance-dependent optimizers.

## Optimizer Boundary

`solver_input()` fails closed for unavailable models and emits rows directly
from the exact pinned matrix. The optimizer cannot replace it with a newer
shared revision or pairwise Bivariate approximation.
