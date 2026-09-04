# Modular Compose deployment v1

## Contents

- [Topology](#topology)
- [Network exposure](#network-exposure)
- [Data mounts](#data-mounts)
- [Run](#run)

## Topology

```
Internet :8080 -> portfell-gateway
                    |-- portfell-metadata
                    |-- portfell-univariate
                    |-- portfell-bivariate
                    `-- portfell-multivariate
                    `-- portfell-postgres
```

The `compose.modules.yaml` profile names exactly these six containers.

## Network exposure

Only the gateway binds the host port. All module ports and PostgreSQL are
internal-network services; the internal network is marked `internal: true`.

## Data mounts

Analytical services mount the fetched market-data share read-only. PostgreSQL
uses its named volume. Credentials are injected through the external Compose
secret file.

## Run

Set `PORTFELL_POSTGRES_PASSWORD_FILE` and, if needed,
`PORTFELL_MARKET_DATA_ROOT`, then run:

```text
docker compose -f compose.modules.yaml up -d --build
```
