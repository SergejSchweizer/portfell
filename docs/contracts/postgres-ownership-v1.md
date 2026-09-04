# PostgreSQL ownership v1

## Contents

- [Schemas](#schemas)
- [ID hand-off](#id-hand-off)
- [Immutability](#immutability)
- [Migration](#migration)

## Schemas

The clean app database keeps workflow commands and stage-owned hand-offs in
separate schemas:

```
workflow     commands and leases
metadata     published universes
univariate   runs and selections
bivariate    runs and pair counts
multivariate runs and portfolio decisions (later migration)
```

One table has one owner. A process receives a writer only for its own schema;
upstream data is exposed through a reader protocol.

## ID hand-off

Only identifiers cross stage boundaries. The dependency chain is:

`metadata_universe_id -> univariate_run_id/selection_id -> bivariate_run_id -> multivariate_run_id`.

Quote rows, metrics, matrices and portfolio rows never appear in workflow
commands or hand-off records.

## Immutability

Published universes, selections and analytical runs have database triggers that
reject update and delete. A new result is a new immutable ID. Workflow commands
remain claimable state and are protected by unique idempotency keys.

## Migration

Migration v004 is transactional and repeat-safe. It creates the owner schemas
without changing existing financial contents; subsequent module migrations
move callers to these tables. Its destructive down migration is available only
through the existing explicit operator opt-in.
