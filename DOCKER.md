# Docker operations

This is the canonical container guide for the final Portfell runtime.

## Topology

`compose.yaml` owns exactly two services:

- `postgres`: clean Portfell application database `portfell_dash`;
- `api`: the Python FastAPI + Plotly Dash application.

The external xetra-loader PostgreSQL database is not Compose-owned by Portfell. There is no production Web/Node service, provider/download/refresh worker, or retired Portfell application database service.

## Required local files

Create repository-root `config.yaml` from `config.example.yaml`. `config.yaml` is intentionally gitignored and must remain outside image layers/artifacts. It contains non-secret PostgreSQL identity metadata only.

Create two external password files outside the repository:

- Portfell app-database password file;
- external xetra-loader market-reader password file.

The `api` container runs as its unprivileged `portfell` user and receives group ID
`100`. Both secret files must therefore be readable by that group, without being
world-readable. For example, when the files belong to the host group with ID `100`:

```bash
chmod 640 /absolute/host/path/postgres-password.txt \
  /absolute/host/path/market-postgres-password.txt
```

If the market secret is not group-readable, the application can start but metadata
reads fail closed and the Metadata dropdowns have no available values.

Point the following environment variables at the effective authorities/files:

```text
PORTFELL_PORT=8080
PORTFELL_POSTGRES_PASSWORD_FILE=/absolute/host/path/postgres-password.txt
PORTFELL_MARKET_DATABASE_URL=postgresql://<market-login>@10.10.1.3:54321/xetra_loader
PORTFELL_MARKET_POSTGRES_PASSWORD_FILE=/absolute/host/path/market-postgres-password.txt
```

`PORTFELL_DATABASE_URL` is composed internally for the local Compose-managed `portfell_dash` service. Production may provide an explicit external equivalent only when it still identifies database `portfell_dash`, schema `portfell`, and passes the same config identity validation.

Never place raw passwords in `.env.example`, `config.yaml`, tracked Compose files, image build arguments, logs, or acceptance evidence.

## Start

```bash
docker compose up --build
```

The default application binding is:

```text
0.0.0.0:8080 -> api:8000
```

Override the host port with `PORTFELL_PORT` when required.

The app container mounts only:

```text
./config.yaml:/run/portfell/config.yaml:ro
```

plus the two external Compose secrets. It runs read-only with a tmpfs for `/tmp`, drops all Linux capabilities, and uses `no-new-privileges`.

The PostgreSQL service persists only the clean `portfell_dash` database in `portfell-dash-postgres-data`. The production override may bind this to `${PORTFELL_DATA_ROOT}/postgres`; it must not reactivate a legacy Portfell database volume.

## Startup contract

The Python application:

1. loads `postgres.app` and `postgres.market` from the mounted root config;
2. validates the effective app and market DSN identities independently;
3. connects to `portfell_dash` and migrates `portfell` app-state schema to head;
4. composes `PostgresAppStateRepository`;
5. composes the external read-only `MarketDataGateway`;
6. creates the typed four-stage application service;
7. mounts FastAPI routes and the four Plotly Dash pages.

A missing/malformed/mismatched config or database authority fails closed with a redacted runtime error.

## Health

Container health uses:

```bash
python -m portfell.hosted_runtime health
```

A healthy process is necessary but not sufficient for production acceptance. Production cutover also requires database/config preflight, market read-only checks, full analytical workflow, browser acceptance, and restart persistence.

## Market authority

Expected external identity:

```text
host: 10.10.1.3
port: 54321
database: xetra_loader
schema: xetra_loader
tables: listings, eod_quotes, dividends, splits
```

The Portfell reader must be non-superuser, must receive only the required read privileges through group role `portfell_app`, and must not access `xetra_loader_sync`. Market DML/DDL must fail.

## Local validation

```bash
uv run portfell-quality pr
uv run portfell-quality merge
```

The merge gate includes the isolated market-source PostgreSQL contract. GitHub additionally executes deterministic Python Playwright browser acceptance.

## Production cutover and rollback

Do not remove the retired deployment ad hoc. Follow `docs/runbooks/dash-production-cutover.md` in order. Back up and verify the old database before destructive removal; provision a fresh `portfell_dash`; validate the complete new workflow and restart; only then detach the old UI/database runtime.

Rollback restores the matching retired application release and its encrypted database backup as one unit. Never run old and new Portfell databases in dual-read, dual-write, or fallback mode.
