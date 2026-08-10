# Shared Market Refresh Operations

The `shared-market-refresh` Compose operations service refreshes the canonical
`PORTFELL_SHARED_DATA_ROOT/market-data` store for the de-duplicated active-project
inventory. Browser pages never invoke provider ingestion.

## One-Time Rollout

From the absolute repository root, with `.env.local` pointing only to external
secret files:

```bash
docker compose --env-file .env.local build api
docker compose --env-file .env.local up --detach postgres api web
portfell-refresh-shared-market-data --dry-run
portfell-shared-market-cron run-once --project-root "$(pwd)"
portfell-shared-market-cron install --project-root "$(pwd)"
portfell-shared-market-cron status --project-root "$(pwd)"
crontab -l
```

`run-once` writes operational output to `/var/log/portfell/shared-market-refresh.log`
by default. Configure host log rotation for that file. The installer validates
Compose configuration and a refresh dry run before replacing only its delimited
crontab block.

## Schedule And Recovery

The managed job runs daily at `02:15` in `Europe/Amsterdam`; DST follows that
timezone's cron behavior. `/usr/bin/flock -n` prevents overlapping runs. A
lock-contention or provider partial failure leaves already atomically published
listing files readable; review the log and re-run `run-once` after correcting the
provider or storage condition.

Use `portfell-shared-market-cron uninstall --project-root "$(pwd)"` to remove
only the managed block. It preserves unrelated crontab entries.