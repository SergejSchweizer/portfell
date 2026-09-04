# Multivariate application v1

## Contents

- [Boundary](#boundary)
- [Lineage](#lineage)
- [Isolation](#isolation)

## Boundary

`MultivariateApplication` owns candidate generation, portfolio validation,
optimization and decision publication behind `/api/multivariate/*` and
`/health`.

## Lineage

The process accepts a published `bivariate_run_id` together with its exact
Univariate selection reference. Daily cumulative curves resolve persisted
Univariate daily returns; no external market database is queried.

## Isolation

```
bivariate_run_id -> MultivariateApplication -> multivariate schema/artifacts
                                                   |
                                                   +-> immutable decisions
```

All portfolio objectives are evaluated by one durable job. The application does
not import sibling implementation packages or mutate upstream records.
