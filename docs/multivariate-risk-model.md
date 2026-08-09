# Canonical Multivariate Risk Model

`portfell.multivariate_risk_model` creates one immutable joint covariance
artifact from a valid `MultivariateInputSnapshot`. The initial production
estimator is Ledoit-Wolf shrinkage; sample covariance and EWMA remain explicit
research choices. Pairwise Bivariate covariance is never substituted for this
common-calendar matrix.

The artifact records the estimator, parameters, log-return policy, full listing
order, period, observations, covariance values, shrinkage and eigen diagnostics,
PSD state, availability reasons, and algorithm version. `solver_input()` is the
only conversion boundary for covariance-dependent optimizers. It fails closed
for unavailable models and emits rows directly from that exact matrix.
