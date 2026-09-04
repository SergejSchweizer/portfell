# Workflow commands v1

## Contents

- [Command shape](#command-shape)
- [Claim lifecycle](#claim-lifecycle)
- [Restart behavior](#restart-behavior)
- [Boundary rule](#boundary-rule)

## Command shape

Commands in `workflow.stage_commands` contain only command ID, analytical stage,
upstream input ID, operation, algorithm version, idempotency key and timestamps.
They never contain quotes, returns, matrices, pair rows or portfolio rows.

## Claim lifecycle

```
queued --claim (row lock)--> running --publish--> succeeded
   ^                            |  \--> failed/cancelled
   \---- stale lease recovery --+
```

Workers claim one queued (or expired) command using PostgreSQL
`FOR UPDATE SKIP LOCKED`. The unique idempotency key prevents duplicate active
work for the same stage/input/algorithm tuple.

## Restart behavior

Progress phase, current/total counts and lease expiry are persisted in the
command row. A process restart can recover expired running leases to `queued`;
published immutable artifacts are not duplicated.

## Boundary rule

The workflow repository is a stage-neutral adapter. Analytical modules receive
commands through this repository and communicate only with PostgreSQL IDs and
published artifact manifests; no module calls another module's HTTP endpoint.
