# Single-container operator runbook

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
                    +----------------------------------+
Browser :8080 ---->| portfell-app (one container)      |
                    | gateway + Metadata               |
                    | + Univariate + Bivariate         |
                    | + Multivariate                   |
                    +----------------+-----------------+
                                     |
                         +-----------+-----------+
                         v                       v
                 PostgreSQL :5432       read-only market share
```

[`compose.yaml`](../compose.yaml) is the sole supported topology. It starts
exactly one Application container (`portfell-app`) and one PostgreSQL
container; only the Application publishes port 8080. The four modules remain
separate source-level boundaries inside the Application process.

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
docker compose -f compose.yaml config
docker compose -f compose.yaml build
docker compose -f compose.yaml up -d
docker compose -f compose.yaml ps
```

Stop if `config` reports an unresolved secret, unexpected host port or an
unapproved volume. Keep the previous image tag until health checks pass.

## Health and logs

```text
curl --fail http://127.0.0.1:8080/healthz
curl --fail http://127.0.0.1:8080/api/health
docker compose -f compose.yaml ps
docker logs --since=10m portfell-app
docker logs --since=10m portfell-postgres
```

The process is one container, but a failed module callback must not bypass the
typed module facade or write directly to PostgreSQL.

## Backup and restore

Back up PostgreSQL and the content-addressed data share as one release point:

```text
pg_dump --format=custom --file=/secure/backups/portfell.dump portfell_dash
rsync -a --delete /volume2/docker/portfell/market-data/ /secure/backups/market-data/
```

Restore the database first, then the matching data-share snapshot, run the
migration preflight, and verify manifest hashes before starting the container.
Never mix snapshots from different releases.

## Permissions

The Application uses the Portfell application role and a read-only market data
mount. Verify that PostgreSQL and the data-share permissions match the
repository contract; no module-specific container role is required.

## Cutover and rollback

1. Build and validate the image without stopping the previous release.
2. Run `config`, health, migration and smoke checks.
3. Cut over only after all four routes respond from the one container.
4. Stop immediately on failed health, schema mismatch, hash mismatch, data-loss
   signal or an unexpected public port.
5. Keep the previous release and backups until the complete journey is PASS.
6. Roll back by restoring the previous Application image and matching
   database/data-share snapshot; never run a destructive migration implicitly.

## Failure isolation

```text
module boundary failure -> typed error at that module's route
                         -> gateway process remains live
                         -> unrelated routes remain reachable
                         -> durable job/artifact state remains authoritative
```

Capture sanitized command IDs, statuses and health output; omit credentials,
SQL statements and raw financial rows.
