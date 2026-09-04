# Bivariate application v1

## Contents

- [Boundary](#boundary)
- [Input](#input)
- [Isolation](#isolation)

## Boundary

`BivariateApplication` owns pair planning, aligned-return calculations and
matrix/scatter result publication behind `/api/bivariate/*` and `/health`.

## Input

The only upstream input is a published `univariate_selection_id` and its
immutable artifact references. Candidate pairs are unique unordered pairs:
`n * (n - 1) / 2`; self-pairs and duplicate reverse pairs are never published.

## Isolation

```
univariate_selection_id -> BivariateApplication -> bivariate schema/artifacts
                                                   |
                                                   +-> multivariate command ID
```

All pair metrics share the frozen aligned time-slice contract. The application
does not import sibling implementation packages or mutate Univariate records.
