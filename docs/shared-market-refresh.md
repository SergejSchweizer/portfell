# Shared Market Refresh Operations


## Table Of Contents

- [One-Time Rollout](#one-time-rollout)
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

## Schedule And Recovery

The managed job runs daily at `02:15` in `Europe/Amsterdam`; DST follows that
timezone's cron behavior. `/usr/bin/flock -n` prevents overlapping runs. A
lock-contention or provider partial failure leaves already atomically published
listing files readable; review the log and re-run `run-once` after correcting the
provider or storage condition.

Use `portfell-shared-market-cron uninstall --project-root "$(pwd)"` to remove
only the managed block. It preserves unrelated crontab entries.
