# Docker Operations

This sidecar explains how to run Portfell's containerized PostgreSQL, API, and
Web runtime. It is the canonical Docker guide. For deployment readiness
decisions, see [docs/security/hosted_readiness.md](docs/security/hosted_readiness.md).

## Table Of Contents

- [1. Runtime Model](#1-runtime-model)
- [2. Prerequisites](#2-prerequisites)
- [3. External Secrets](#3-external-secrets)
- [4. Configure The Environment](#4-configure-the-environment)
- [5. Deploy And Verify](#5-deploy-and-verify)
- [6. Day-To-Day Commands](#6-day-to-day-commands)
- [7. Troubleshooting](#7-troubleshooting)

## 1. Runtime Model

Compose starts the PostgreSQL control plane used for the Portfell application.
Market observations are read from the configured
external market database; no market NAS or filesystem volume is mounted into the
hosted runtime. The API starts only when
`PORTFELL_HOSTED_AUTHORITY=postgres`; it has no local or in-memory runtime mode.

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
                       read-only gateway query
                                  |
                                  v
                         +--------------------+
                         | configured market  |
                         | PostgreSQL source  |
                         +--------------------+
```

`portfell-postgress`, `portfell-api`, and `portfell-web` are intentional fixed
container names. PostgreSQL is the only Compose-managed durable volume.

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
└── postgres-password.txt          PostgreSQL password
```

The API receives only the application-database password. The external market
database is an independent read-only authority configured through `config.yaml`
and its separate runtime secret reference.

## 4. Configure The Environment

Copy the variable names from `.env.example` to the ignored `.env.local` file.
Every secret entry is an absolute host-file path.

```dotenv
PORTFELL_API_PORT=8000
PORTFELL_WEB_PORT=3000
PORTFELL_HOSTED_AUTHORITY=postgres
PORTFELL_POSTGRES_PASSWORD_FILE=/run/host-secrets/portfell/postgres-password.txt
```

Validate interpolation without showing secret values:

```bash
docker compose --env-file .env.local config --quiet
docker compose --env-file .env.local config --services
```

## 5. Deploy And Verify

Apply the catalog migrations before starting the application stack, then build
and start PostgreSQL, the API, and the Web application. The API and Web images
must come from the same verified source revision;
there is no mixed-version or dual-authority compatibility window.

```bash
uv run python -m portfell.hosted_catalog_migration
uv run python -m portfell.hosted_readiness --require-database
docker compose --env-file .env.local up --build --detach
docker compose --env-file .env.local ps
docker compose --env-file .env.local logs --tail 100 api web
```

Wait until `portfell-postgress`, `portfell-api`, and `portfell-web` are healthy.
Open `http://localhost:3000` for the Web UI and
`http://localhost:8000/health` for the API health response.

Smoke-check the deployed API without exposing credentials:

```bash
curl --fail --silent --show-error http://localhost:8000/health
```

If a deployment fails after migrations or image startup, stop the new stack,
restore the last compatible PostgreSQL backup, then start the matching prior
Web/API image pair. Do not run an old image against a newer catalog head or
introduce a dual-read/dual-write fallback.

## 6. Day-To-Day Commands

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
catalog.

## 7. Troubleshooting

If Compose configuration reports a missing secret variable, add the *path* to
`.env.local`, confirm that the path is absolute, and verify that the file is
readable by the service user. Never replace a path variable with a token value.

If an API healthcheck fails after a backend change, rebuild the API and inspect
only the final log lines:

```bash
docker compose --env-file .env.local up --build --detach api
docker compose --env-file .env.local logs --tail 100 api
```

If an analytical computation is pending, inspect the API logs and its status
through the UI/API.
