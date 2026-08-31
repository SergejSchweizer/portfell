# Market-source cutover runbook

This runbook covers the Portfell source-series transition to the external read-only xetra-loader PostgreSQL authority. It does not perform the later Plotly Dash / clean `portfell_dash` database replacement; PR344–PR360 own that transition.

## Table of contents

1. [Freeze the release inputs](#1-freeze-the-release-inputs)
2. [Back up surviving application state](#2-back-up-only-surviving-portfell-application-state)
3. [Validate local configuration](#3-validate-local-configuration-metadata)
4. [Validate database authorities](#4-validate-independent-secret-supplied-database-authorities)
5. [Run the privilege preflight](#5-market-source-privilege-preflight)
6. [Start the runtime](#6-start-the-portfell-runtime)
7. [Smoke browser routes](#7-smoke-the-four-canonical-browser-routes)
8. [Run one analytical workflow](#8-run-one-analytical-smoke-workflow)
9. [Post-deployment checks](#9-post-deployment-checks)
10. [Rollback](#10-rollback)
11. [Handoff](#11-handoff-to-pr343)

## 1. Freeze the release inputs

Record, in a secret-free change record, the exact Portfell application SHA, the expected xetra-loader production SHA, the xetra-loader V2 acceptance artifact identity, and the intended deployment configuration revision. Do not record passwords, complete credential-bearing DSNs, secret-file contents, or PostgreSQL authentication material.

## 2. Back up only surviving Portfell application state

Back up the transitional Portfell-owned application/analytical PostgreSQL state that is still required for rollback of this source-series release. Verify that the backup is readable and restorable before deployment.

Do **not** migrate, preserve as authority, or restore old Portfell market Bronze/Silver/Gold files, NAS market caches, provider download artifacts, refresh inventories, or provider credentials. Those market planes are disposable after the source cutover and must never become a rollback source.

The external xetra-loader database is independently operated and is not copied into the Portfell backup.

## 3. Validate local configuration metadata

The repository-root `config.yaml` is local, gitignored, and contains only non-secret PostgreSQL identity metadata. Confirm:

- `postgres.app` identifies the transitional Portfell application PostgreSQL authority used by this source-series release;
- `postgres.market.host` is `10.10.1.3`;
- `postgres.market.port` is `54321`;
- `postgres.market.database` is `xetra_loader`;
- `postgres.market.schema` is `xetra_loader`;
- the market business tables are exactly `listings`, `eod_quotes`, `dividends`, `splits`;
- the configured market LOGIN role is expected to be a member of NOLOGIN `portfell_app`;
- secret references name external secret sources and contain no raw password.

Confirm `git check-ignore config.yaml` succeeds. Never bake `config.yaml` into an image or upload it as an artifact.

## 4. Validate independent secret-supplied database authorities

Set `PORTFELL_DATABASE_URL` for the Portfell-owned application database and `PORTFELL_MARKET_DATABASE_URL` for the external xetra-loader database. They must be different authorities and neither may fall back to the other. Supply their passwords through their distinct external secret-file references.

Run startup configuration validation and stop if host, port, database, schema, or role identity disagrees with `config.yaml`. A redacted typed configuration error is a deployment failure; do not work around it by broadening grants or pointing one DSN at the other database.

## 5. Market-source privilege preflight

Using the application market LOGIN role, verify all of the following before serving analytical traffic:

1. `current_database()` is `xetra_loader` and the business schema is `xetra_loader`.
2. The LOGIN is not a superuser and is a member of NOLOGIN role `portfell_app`.
3. SELECT succeeds for `listings`, `eod_quotes`, `dividends`, and `splits`.
4. A source snapshot starts with `REPEATABLE READ, READ ONLY` and sets the transaction-local time zone to UTC.
5. DML such as a zero-row `UPDATE xetra_loader.listings ... WHERE false` fails with insufficient privilege.
6. DDL in the business schema fails with insufficient privilege.
7. `has_schema_privilege(current_user, 'xetra_loader_sync', 'USAGE')` is false. Sync-schema denial is PASS evidence.

Do not grant CREATE, INSERT, UPDATE, DELETE, TRUNCATE, or sync-schema access to make a preflight pass.

## 6. Start the Portfell runtime

Start the transitional Portfell runtime with its local application database and the external market DSN. Portfell Compose must not start or own xetra-loader, a provider download worker, a market refresh worker, a NAS market service, or a medallion market database.

Wait for PostgreSQL application health and FastAPI health. Treat any market-source startup/configuration error as fail-closed.

## 7. Smoke the four canonical browser routes

Verify the transitional browser serves and can navigate exactly these product routes:

- `/metadata`
- `/univariate`
- `/bivariate`
- `/multivariate`

There is no project/user switcher and no provider download/refresh control. This browser remains transitional until the Dash replacement series.

## 8. Run one analytical smoke workflow

Using a small representative active Xetra universe, run Metadata -> Univariate -> Bivariate -> Multivariate. Verify:

- full listing identity `(isin, exchange, code)` survives all stages;
- new Metadata selection excludes inactive listings;
- analytical source lineage uses a deterministic `market_source_snapshot_*` identity;
- adjusted close is the return/risk authority;
- a missing adjusted close fails as typed unavailable input rather than falling back to raw close;
- dividends remain income evidence and are not added on top of adjusted-close returns;
- split rows do not trigger a new return transformation;
- Bivariate unavailable covariance/correlation evidence is not represented as zero;
- Multivariate consumes the source-pinned upstream input and does not silently replace a failed optimizer with Equal Weight;
- repeated reads leave all four market tables unchanged.

## 9. Post-deployment checks

After restart, rerun health, configuration identity, role membership, SELECT, DML-denial, sync-denial, and one representative `MarketDataGateway` read. Confirm the Portfell application state required by the transitional runtime remains available after restart.

Record only sanitized PASS/FAIL evidence: Git SHAs, contract/version identifiers, table names, role class/membership booleans, snapshot short IDs, and test names. Never record secret values or full DSNs.

## 10. Rollback

Rollback is limited to the Portfell application release and its non-secret local configuration, together with restoration of the surviving transitional application database backup if the application release requires it.

Rollback must **not**:

- reactivate EODHD/provider acquisition;
- restore Bronze/Silver/Gold or NAS market files as market authority;
- start a Portfell market refresh or download worker;
- import the xetra-loader Python package into Portfell;
- broaden the market reader role;
- grant access to `xetra_loader_sync`;
- point the market DSN at the Portfell application DB or vice versa.

If the external xetra-loader authority is unavailable, Portfell remains fail-closed until that authority is restored. Do not substitute a legacy market source.

## 11. Handoff to PR343

Once the source cutover has its required QA evidence, PR343 freezes the exact source/application-service contracts and the legacy deletion inventory seed for the full Plotly Dash + `portfell_dash` replacement series.
