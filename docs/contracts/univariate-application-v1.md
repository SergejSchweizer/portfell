# Univariate application v1

## Contents

- [Input and output](#input-and-output)
- [Selection boundary](#selection-boundary)
- [Isolation](#isolation)

## Input and output

`UnivariateApplication` accepts a persistence-backed `UnivariatePort` and
exposes `/api/univariate/runs`, `/api/univariate/selections` and run history.
The only upstream input is a published Metadata universe identifier.

## Selection boundary

Metric results and checkbox selections are published as immutable Univariate
records. A downstream command carries only the resulting selection ID; no
market rows are sent over HTTP.

## Isolation

```
metadata_universe_id -> UnivariateApplication -> univariate schema/artifacts
                                                   |
                                                   +-> bivariate command ID
```

The process does not import Metadata, Bivariate or Multivariate implementation
packages and can expose its health endpoint while sibling processes are down.
