# Independent modules operator runbook

## Contents

- [Topology](#topology)
- [Prerequisites](#prerequisites)
- [Build and deploy](#build-and-deploy)
- [Health and logs](#health-and-logs)
- [Backup and restore](#backup-and-restore)
- [Permissions](#permissions)
- [Cutover and rollback](#cutover-and-rollback)
- [Failure isolation](#failure-isolation)

## Topology

```text
                    +----------------------+
Browser :8080 ---->| portfell-gateway     |
                    +----------+-----------+
       +-----------------------+-----------------------+
       v                       v                       v
 metadata :8000       univariate :8000        bivariate :8000
       |                       |                       |
       +-----------------------+-----------------------+
                               v
                    multivariate :8000
                               |
                         postgres :5432
```

The gateway is the only host-published service. See
[`compose.modules.yaml`](../compose.modules.yaml) for the canonical topology.

## Prerequisites

Set an absolute external password file and verify the market-data root:

```text
export PORTFELL_POSTGRES_PASSWORD_FILE=/secure/portfell/postgres-password
export PORTFELL_MARKET_DATA_ROOT=/volume2/docker/portfell/market-data
test -r "$PORTFELL_POSTGRES_PASSWORD_FILE"
test -d "$PORTFELL_MARKET_DATA_ROOT"
```

Never place the password in Compose, shell history, logs or evidence.

## Build and deploy

```text
docker compose -f compose.modules.yaml config
docker compose -f compose.modules.yaml build
docker compose -f compose.modules.yaml up -d
docker compose -f compose.modules.yaml ps
```

Stop if `config` reports an unresolved secret, unexpected host port or an
unapproved volume. Keep the previous image tag until health checks pass.

## Health and logs

```text
curl --fail http://127.0.0.1:8080/health
docker compose -f compose.modules.yaml ps
docker logs --since=10m portfell-gateway
docker logs --since=10m portfell-metadata
docker logs --since=10m portfell-univariate
docker logs --since=10m portfell-bivariate
docker logs --since=10m portfell-multivariate
```

A stopped analytical module may degrade its own route, but gateway health and
unrelated module routes must remain reachable.

## Backup and restore

Back up PostgreSQL and the content-addressed data share as one release point:

```text
pg_dump --format=custom --file=/secure/backups/portfell.dump portfell_dash
rsync -a --delete /volume2/docker/portfell/market-data/ /secure/backups/market-data/
```

Restore the database first, then restore the matching data-share snapshot, run
the migration preflight, and verify manifest hashes before starting workers.
Never mix snapshots from different releases.

## Permissions

Migration v006 provisions one role per process. Verify that each role writes
only its owner schema and namespace; workers use read-only mounts for upstream
artifacts. Rotate credentials by replacing the external secret and restarting
the affected service.

## Cutover and rollback

1. Build and validate the new images without stopping the previous release.
2. Run `config`, health, migration and smoke checks.
3. Cut over the gateway only after every required prerequisite is published.
4. Stop immediately on failed health, schema mismatch, hash mismatch, data-loss
   signal or unexpected public port.
5. Keep the previous release and backups until the complete journey is PASS.
6. Roll back by restoring the previous gateway/module image set and matching
   database/data-share snapshot; never run a destructive migration implicitly.

## Failure isolation

```text
module failure -> module route unavailable
                -> gateway remains live
                -> other module routes remain usable
                -> retry only after durable job/artifact state is inspected
```

Capture sanitized command IDs, statuses and health output; omit credentials,
SQL statements and raw financial rows.
