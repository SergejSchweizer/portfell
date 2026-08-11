# Docker Operations

This sidecar explains how to run Portfell's containerized PostgreSQL, API, Web,
and background-worker runtime. It is the canonical Docker guide. For scheduled
market refresh operations, continue with [docs/shared-market-refresh.md](docs/shared-market-refresh.md); for production readiness decisions, see [docs/security/hosted_readiness.md](docs/security/hosted_readiness.md).

## Table Of Contents

- [1. Runtime Model](#1-runtime-model)
- [2. Prerequisites](#2-prerequisites)
- [3. External Secrets](#3-external-secrets)
- [4. Configure The Environment](#4-configure-the-environment)
- [5. Start And Verify](#5-start-and-verify)
- [6. Synology Production Storage](#6-synology-production-storage)
- [7. Day-To-Day Commands](#7-day-to-day-commands)
- [8. Troubleshooting](#8-troubleshooting)

## 1. Runtime Model

Compose starts one PostgreSQL control plane and one immutable shared-data plane.
PostgreSQL is the authority for users, projects, selections, jobs, and research
run metadata. The shared-data volume holds published market-data revisions. No
repository `lake`, user workspace JSON, or user-owned quote download is mounted
into the hosted runtime.

```text
browser
   |
   v
+----------------+       +-------------------+
| portfell-web   | ----> | portfell-api      |
+----------------+       +-------------------+
                                  |
                       request-scoped RLS transaction
                                  |
                                  v
                         +--------------------+
                         | portfell-postgress |
                         | PostgreSQL         |
                         +--------------------+
                                  |
                  durable initial-fill job    |    published revisions
                                  v            v
                 +---------------------+  +-------------------+
| bootstrap worker    |  | shared-data plane |
                 | operations token    |  | market-data/      |
                 +---------------------+  +-------------------+
```

`portfell-postgress`, `portfell-api`, and `portfell-web` are intentional fixed
container names. Development uses Compose-managed durable volumes; production
uses the explicit Synology bind mounts described below.

## 2. Prerequisites

Install Docker Engine and the Docker Compose v2 plugin on the host. The service
user must be able to run `docker compose` and read the external secret files.
Check the installation before configuring Portfell:

```bash
docker --version
docker compose version
docker info
```

Run all commands below from the immutable checkout root:

```bash
cd /home/dev_portfell/portfell
```

## 3. External Secrets

Keep secrets outside the repository and grant read access only to the service
user. Compose mounts their contents as Docker secrets; do not put values in
`compose.yaml`, image layers, command lines, logs, or Git.

```text
/run/host-secrets/portfell/
├── postgres-password.txt          PostgreSQL password
├── eodhd-kek.txt                  credential-vault encryption key
└── operations-eodhd-token.txt     worker/operations EODHD token only
```

The API receives the KEK and database password, but not the operations token.
The `project-bootstrap-worker` and the one-shot `shared-market-refresh` service
receive the operations token, but not the KEK.

## 4. Configure The Environment

Copy the variable names from `.env.example` to the ignored `.env.local` file.
Every secret entry is an absolute host-file path.

```dotenv
PORTFELL_API_PORT=8000
PORTFELL_WEB_PORT=3000
PORTFELL_POSTGRES_PASSWORD_FILE=/run/host-secrets/portfell/postgres-password.txt
PORTFELL_EODHD_KEK_FILE=/run/host-secrets/portfell/eodhd-kek.txt
PORTFELL_OPERATIONS_EODHD_TOKEN_FILE=/run/host-secrets/portfell/operations-eodhd-token.txt
```

Validate interpolation without showing secret values:

```bash
docker compose --env-file .env.local config --quiet
docker compose --env-file .env.local config --services
```

## 5. Start And Verify

Build and start the default runtime. This starts PostgreSQL, the API, the Web
application, and the internal bootstrap worker.

```bash
docker compose --env-file .env.local up --build --detach
docker compose --env-file .env.local ps
docker compose --env-file .env.local logs --tail 100 api web project-bootstrap-worker
```

Wait until `portfell-postgress`, `portfell-api-1`, and `portfell-web` are
healthy. Open `http://localhost:3000` for the Web UI and
`http://localhost:8000/health` for the API health response.

## 6. Synology Production Storage

Production data lives below one host root and is never mixed with repository
files or Docker's global engine data root.

```text
/volume2/docker/portfell
├── postgres/   PostgreSQL bind mount
├── lake/       shared immutable market-data revisions
├── logs/       operations logs
└── backups/    encrypted logical backups
```

Set `PORTFELL_DATA_ROOT=/volume2/docker/portfell` in the production-only
environment file and render the explicit override before starting services:

```bash
docker compose --env-file .env.local -f compose.yaml -f compose.production.yaml config
docker compose --env-file .env.local -f compose.yaml -f compose.production.yaml up --build --detach
```

The override resets the development named-volume declarations. API, bootstrap
worker, and the one-shot refresh service share only `lake/`; Web receives none
of these mounts. Keep secrets outside this tree.

## 7. Day-To-Day Commands

Use these commands for safe routine operations:

```bash
# Follow one service without exposing secrets.
docker compose --env-file .env.local logs --follow api

# Rebuild only the API after backend changes.
docker compose --env-file .env.local up --build --detach api

# Recreate only the Web container after UI changes.
docker compose --env-file .env.local up --detach --no-deps --force-recreate web

# Inspect persistent-volume-backed service status.
docker compose --env-file .env.local ps
```

Do not remove named volumes during normal deployment: they contain the PostgreSQL
catalog and published shared-market revisions. Scheduled refresh, log rotation,
and cron installation are documented only in
[docs/shared-market-refresh.md](docs/shared-market-refresh.md).

## 8. Troubleshooting

If Compose configuration reports a missing secret variable, add the *path* to
`.env.local`, confirm that the path is absolute, and verify that the file is
readable by the service user. Never replace a path variable with a token value.

If an API healthcheck fails after a backend change, rebuild the API and inspect
only the final log lines:

```bash
docker compose --env-file .env.local up --build --detach api
docker compose --env-file .env.local logs --tail 100 api
```

If a worker job is pending, inspect `project-bootstrap-worker` logs and its
durable job status through the UI/API. A worker never needs a browser-provided
credential; missing operations-token access is a deployment configuration error.
