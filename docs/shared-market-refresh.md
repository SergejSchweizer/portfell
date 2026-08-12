# Shared Market Refresh Operations


## Table Of Contents

- [One-Time Rollout](#one-time-rollout)
- [On-Demand Metadata Refresh](#on-demand-metadata-refresh)
- [Schedule And Recovery](#schedule-and-recovery)

The `shared-market-refresh` Compose operations service refreshes the canonical
`PORTFELL_SHARED_DATA_ROOT/market-data` store for the de-duplicated active-project
inventory. A newly created project's Metadata Builder may request its initial selected-listing
download; that route is server-owned, idempotent, and separate from the scheduled shared refresh.

## One-Time Rollout

Complete container installation, secret configuration, and base-service health
checks using [DOCKER.md](../DOCKER.md) first. From the absolute repository
root, run the refresh-specific steps:

```bash
export PORTFELL_ROOT=/home/dev_portfell/portfell
export PORTFELL_DATA_ROOT=/volume2/docker/portfell
portfell-ugreen-nas-data-root-preflight --root "$PORTFELL_DATA_ROOT"
portfell-refresh-shared-market-data --dry-run
portfell-shared-market-cron run-once --project-root "$PORTFELL_ROOT" --data-root "$PORTFELL_DATA_ROOT"
portfell-shared-market-cron install --project-root "$PORTFELL_ROOT" --data-root "$PORTFELL_DATA_ROOT"
portfell-shared-market-cron status --project-root "$PORTFELL_ROOT" --data-root "$PORTFELL_DATA_ROOT"
crontab -l
```

`run-once` writes operational output to
`/volume2/docker/portfell/logs/shared-market-refresh.log`. The installer uses
both `compose.yaml` and `compose.production.yaml`, validates the final bind root
and a refresh dry run before replacing only its delimited crontab block.

## On-Demand Metadata Refresh

The **Fetch all metadata** browser action creates a durable PostgreSQL job. It
does not invoke EODHD from the API process and does not depend on a browser or
user-provided provider key. The `portfell-worker` claims that job, uses the
operations credential mounted only into the worker, and atomically publishes
the refreshed shared catalogue.

```text
browser -> API -> PostgreSQL metadata-refresh job
                         |
                         v
                 portfell-worker -> EODHD
                         |
                         v
              shared metadata/current.parquet
                         |
                         v
                   browser status polling
```

If the provider is unavailable, the worker stores the safe status code
`eodhd_metadata_unavailable` in the metadata run. The raw provider response and
operations credential are never sent to the browser.

## Schedule And Recovery

The managed job runs daily at `20:15` in `Europe/Amsterdam`; DST follows that
timezone's cron behavior. `/usr/bin/flock -n` prevents overlapping runs. A
lock-contention or provider partial failure leaves already atomically published
listing files readable; review the log and re-run `run-once` after correcting the
provider or storage condition.

Use `portfell-shared-market-cron uninstall --project-root "$(pwd)"` to remove
only the managed block. It preserves unrelated crontab entries.
