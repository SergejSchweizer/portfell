# Shared Market Refresh Operations


## Table Of Contents

- [One-Time Rollout](#one-time-rollout)
- [On-Demand Metadata Refresh](#on-demand-metadata-refresh)
- [Schedule And Recovery](#schedule-and-recovery)

The scheduled `portfell-market-refresh` command is the only process allowed to read
xetra-loader PostgreSQL. It publishes the canonical local snapshot under
`PORTFELL_MARKET_DATA_ROOT`; the API consumes that snapshot and never queries the market
database during normal requests.

## One-Time Rollout

Complete container installation, secret configuration, and base-service health
checks using [DOCKER.md](../DOCKER.md) first. From the absolute repository
root, run the refresh-specific steps:

```bash
export PORTFELL_ROOT=/home/dev_portfell/portfell
export PORTFELL_DATA_ROOT=/volume2/docker/portfell
export PORTFELL_MARKET_DATABASE_URL='postgresql://portfell@10.10.1.3:54321/xetra_loader'
export PORTFELL_MARKET_DATABASE_PASSWORD_FILE=/home/dev_portfell/secrets/portfell/market_postgres_password
portfell-ugreen-nas-data-root-preflight --root "$PORTFELL_DATA_ROOT"
export PORTFELL_MARKET_DATA_ROOT="$PORTFELL_DATA_ROOT/market-data"
portfell-market-refresh --config "$PORTFELL_ROOT/config.yaml" \
  --root "$PORTFELL_MARKET_DATA_ROOT"
crontab -l
```

The refresh writes a complete staging directory and swaps it into place only after all four
datasets have been read. A failed run leaves the previous snapshot intact.

## Scheduled Installation

Install a host cron entry at `20:15` (`15 20 * * *`) that invokes the command above with
`PORTFELL_MARKET_DATA_ROOT` set. Keep the market password secret available only to this cron
process; the API container needs neither the market DSN nor that secret.

## Schedule And Recovery

Run the job under `flock` in production to prevent overlapping refreshes. A provider or storage
failure leaves already atomically published listing files readable; review the log and rerun after
correcting the source condition.

Inspect the result with `cat "$PORTFELL_MARKET_DATA_ROOT/manifest.json"`. Never remove the
previous snapshot until the replacement has been fully written.
