# Portfell architecture

Last reviewed: 2026-09-04

The current deployment authority is [`single-container-modules-v1`](docs/contracts/single-container-modules-v1.md):
all four modules and the gateway run in one Application container. The older
independent-process contract is retained as migration history only.

## 1. System boundary

Portfell is a single-user Python analytical application. The production browser UI is Plotly Dash mounted on FastAPI. The application owns one clean PostgreSQL state database and reads market data from one independent external PostgreSQL database.

```text
Browser
  |
  v
FastAPI + Plotly Dash
  |
  +--> typed application services
         |
         +--> app_state repository --------------------+
         |                                             |
         |                                      portfell_dash
         |                                      schema portfell
         |
         +--> MarketDataGateway -----------------------+
                                                       |
                                                xetra_loader
                                                10.10.1.3:54321
                                                read-only
```

There is no production React/Vite/TypeScript/TanStack application, Node Web service, provider acquisition worker, Portfell-owned market refresh/medallion plane, legacy hosted application database, dual-write adapter, compatibility read fallback, or direct SQL in Dash callbacks.

## 2. Layering

### `dash_app`

`src/portfell/dash_app/**` owns browser composition only: shell/navigation, four pages, typed callback/state adapters, shared presentation components, Plotly figures, and CSS assets. It renders backend/service values and may perform presentation-only formatting. It does not own financial calculations, SQL, credentials, database connections, or market-source identity.

The product routes are exactly:

- `/metadata`
- `/univariate`
- `/bivariate`
- `/multivariate`

`/` redirects to `/metadata` and is not a fifth product route.

### `hosted_api.py`

`src/portfell/hosted_api.py` is the single-process composition root. It validates the app/market configuration, opens the clean application database once, migrates it to the frozen app-state head, creates `PostgresAppStateRepository`, creates the read-only market gateway, composes the restricted module facades, registers FastAPI routes, and mounts Dash.

### Feature modules

`src/portfell/modules/{metadata,univariate,bivariate,multivariate}` owns four physically separate
HTTP boundaries. Each has its own `/api/<module>/*` router and receives a runtime-restricted service
facade. `src/portfell/modules/runtime.py` is the composition registry and rejects calls outside the
owning feature's capability set. Feature packages may not import sibling feature packages.

Dash pages are likewise assigned only their matching module facade. Cross-stage transitions use
the workflow coordinator and immutable persisted IDs. Generic stage endpoints such as `/api/runs`
are forbidden because they obscure ownership.

### `app_services`

`src/portfell/app_services/**` owns the internal four-stage orchestration implementation.
Application services depend on typed app-state ports and market-source contracts, not HTTP/Dash
composition or concrete legacy repositories. Only the composition root gives this implementation
to the restricted feature facades; feature routers and UI pages never receive the unrestricted
service directly in production.

The workflow is strictly:

```text
Metadata -> Univariate -> Bivariate -> Multivariate -> DecisionArtifact
```

A new upstream revision invalidates downstream readiness according to the frozen workflow rules. Published analytical revisions remain immutable.

### `app_state`

`src/portfell/app_state/**` owns all Portfell application-state persistence and all SQL against schema `portfell` in database `portfell_dash`.

V1 canonical state:

- singleton workspace `default`;
- immutable market-source snapshot lineage;
- versioned metadata universes and full-identity members;
- stage-neutral analysis runs and immutable artifacts;
- versioned Univariate selections and members;
- Multivariate decision artifacts;
- small UI preferences.

The schema contains no user/tenant/project-membership/provider-credential/navigation-projection/status-event/legacy-download control plane. Legacy Portfell rows are not silently imported.

### `market_source`

`src/portfell/market_source/**` is the only market SQL boundary. It reads external PostgreSQL `xetra_loader`, schema `xetra_loader`, tables `listings`, `eod_quotes`, `dividends`, and `splits`.

Important invariants:

- listing key is `(isin, exchange, code)`;
- reader is non-superuser and read-only;
- `xetra_loader_sync` is inaccessible and never a source;
- analytical snapshot reads use `REPEATABLE READ, READ ONLY` with UTC semantics;
- connections/transactions close after materialization and before CPU-heavy analytics;
- batch size is bounded at 500 listing identities per SQL statement;
- PostgreSQL `NUMERIC` stays `Decimal` until the centralized analytical projection;
- `adjusted_close` is authoritative;
- missing adjusted close fails with typed unavailable evidence;
- dividends are income evidence and are not double-counted into adjusted-close returns;
- split events do not introduce a second return transformation.

### Analytical modules

Portfolio/statistical modules remain pure analytical code where practical. They accept typed/materialized data and do not acquire market data or UI state. OOS evaluation remains authoritative for production winner selection. Missing covariance/analytical values are never silently encoded as zero, and Equal Weight is never a hidden solver-failure fallback.

## 3. Database authorities

### Application database

- database: `portfell_dash`
- schema: `portfell`
- owned by Portfell
- read/write only for application-state persistence
- migrations: `src/portfell/app_state/migrations/**`
- SQL authority: `src/portfell/app_state/**`

### Market database

- host: `10.10.1.3`
- port: `54321`
- database/schema: `xetra_loader`
- read-only external authority
- business tables: `listings`, `eod_quotes`, `dividends`, `splits`
- SQL authority: `src/portfell/market_source/**`

The two DSNs are independent and cannot fall back to one another.

## 4. Configuration and secrets

Repository-root `config.yaml` is the canonical local non-secret PostgreSQL metadata file. It is ignored by Git and excluded from application images/artifacts. `config.example.yaml` is tracked and contains only the contract shape/placeholders.

The runtime receives secret-bearing authorities separately:

- `PORTFELL_DATABASE_URL`
- `PORTFELL_MARKET_DATABASE_URL`
- `PORTFELL_POSTGRES_PASSWORD_FILE`
- `PORTFELL_MARKET_POSTGRES_PASSWORD_FILE`

Startup validates DSN identity against the corresponding `postgres.app`/`postgres.market` metadata and fails closed on mismatch. Passwords/tokens never become browser state, error payloads, tracked config, logs, or acceptance evidence.

## 5. Runtime topology

The final Compose runtime owns only:

1. `postgres` — clean `portfell_dash` application database.
2. `api` — one FastAPI + Dash Python process/container.

The market database remains external. The local application surface binds to all host interfaces by default, matching `compose.yaml`; operators can choose another host port with `PORTFELL_PORT`. There is no Web/Node container and no provider/download/refresh worker.

The production-only Compose override may relocate the clean PostgreSQL volume to operator-managed storage. It must not resurrect the retired database authority.

## 6. Visual/UI contract

`docs/contracts/plotly-dash-ui-v1.md` is the normative visual contract. The reference application at `https://financial-dashboard-example.plotly.app/` is used only as design grammar; Portfell never embeds it, requests it at runtime, copies its branding/assets, or depends on it for deterministic tests.

Shared presentation primitives are `PageHeader`, `ControlBar`, `KpiCard`, `ChartCard`, `TableCard`, `StatusBanner`, `HistoryCard`, and `StageFooter`. Supported deterministic browser viewports are `1440x900`, `1024x768`, and `390x844`.

## 7. Quality architecture

`uv run portfell-quality pr` is the fast local gate. `uv run portfell-quality merge` is the complete pre-merge gate and includes at least 90% Python coverage. GitHub's `merge-gate` adds deterministic browser/container acceptance and is the only merge authority.

QA must prove negative space as well as happy paths: no legacy Web runtime, no legacy Portfell database runtime, no provider acquisition, no direct Dash SQL, correct SQL ownership, config/image hygiene, read-only market privileges, four-stage persistence/restart, and no external reference-site network dependency.

## 8. Production cutover

The destructive cutover and coordinated rollback procedure is frozen in `docs/runbooks/dash-production-cutover.md`. The retired database is backed up before removal and may only be restored together with the matching retired application release. Old and new Portfell databases must never run as simultaneous business authorities.
