# Portfell

Portfell is a Python-first, single-user ETF research and portfolio-construction application. The production browser interface is Plotly Dash mounted on FastAPI. Market data is read from an external read-only PostgreSQL authority; Portfell owns a separate clean PostgreSQL database for application and analytical state.

## Final production topology

```text
Browser
  |
  v
FastAPI + Plotly Dash
  |
  +--> Portfell application database
  |    database: portfell_dash
  |    schema: portfell
  |
  +--> external market database
       10.10.1.3:54321
       database/schema: xetra_loader
       tables: listings, eod_quotes, dividends, splits
       read-only
```

There is no first-party React/Vite/TypeScript/TanStack application, Node production Web service, provider-download worker, Portfell market-refresh plane, legacy Portfell database fallback, or dual-database authority.

## Browser workflow

The product has exactly four pages and one analytical flow:

1. `/metadata` — build and persist a versioned active-listing universe.
2. `/univariate` — compute single-instrument statistics and persist the downstream selection.
3. `/bivariate` — compute pairwise diversification evidence for the persisted Univariate selection.
4. `/multivariate` — optimize portfolio candidates, rank them by out-of-sample evidence, and persist the final decision artifact.

The route `/` redirects to `/metadata`; it is not a fifth product page. Dash callbacks consume typed application services and do not execute SQL directly.

## Data authorities

### Market source

The canonical market source is external PostgreSQL `xetra_loader` at `10.10.1.3:54321`. Portfell reads only `xetra_loader.listings`, `eod_quotes`, `dividends`, and `splits` through `MarketDataGateway` using short-lived `REPEATABLE READ, READ ONLY` snapshots.

Listing identity is always `(isin, exchange, code)`. Adjusted close is authoritative for return/risk calculations. Missing adjusted close is a typed unavailable condition; raw close is never a fallback. Dividends are income evidence and are not double-counted on top of adjusted-close returns. Split events do not introduce a second return adjustment. Market SQL is confined to `src/portfell/market_source/**`.

### Application state

Portfell owns only database `portfell_dash`, schema `portfell`. The clean v1 state model contains the singleton workspace, immutable market-source snapshot lineage, versioned metadata universes and members, stage-neutral analysis runs/artifacts, versioned Univariate selections, Multivariate decision artifacts, and small UI preferences.

The retired hosted tenant/control-plane database is not a runtime dependency and is never used as a read/write fallback. Application-state SQL is confined to `src/portfell/app_state/**`.

## Local configuration

Repository-root `config.yaml` is the canonical non-secret local PostgreSQL metadata file. It is intentionally gitignored and must not be copied into an image or artifact. Start from the tracked, secret-free `config.example.yaml` and keep separate sections for `postgres.app` and `postgres.market`.

The effective connection authorities are also separate:

- `PORTFELL_DATABASE_URL` — must identify only `portfell_dash`.
- `PORTFELL_MARKET_DATABASE_URL` — must identify only external `xetra_loader`.
- `PORTFELL_POSTGRES_PASSWORD_FILE` — external secret file for the Portfell application login.
- `PORTFELL_MARKET_POSTGRES_PASSWORD_FILE` — external secret file for the market reader login.

Startup verifies that DSN identity matches `config.yaml` and fails closed on missing, malformed, or mismatched configuration. Raw passwords/tokens are never stored in tracked YAML, `.env.example`, logs, browser state, or evidence.

## Run with Docker Compose

Create the ignored root config and external password files, then set the required environment variables documented in `.env.example`.

```bash
docker compose up --build
```

The final local application surface binds by default at `0.0.0.0:8080`; override the port with `PORTFELL_PORT` when required. The Compose stack owns only the Python application and the clean `portfell_dash` PostgreSQL service. The external xetra-loader database is never Compose-owned by Portfell.

For a destructive production transition from the retired deployment, follow `docs/runbooks/dash-production-cutover.md`. Do not improvise the cutover order and do not run old/new Portfell databases as simultaneous business authorities.

## Quality gates

Fast development gate:

```bash
uv run portfell-quality pr
```

Full pre-merge gate:

```bash
uv run portfell-quality merge
```

The merge gate includes lint/format, architecture/schema/security checks, strict Pyright, parallel pytest with at least 90% coverage, the isolated market-source PostgreSQL contract, and clean-working-tree checks. GitHub's `merge-gate` additionally executes the deterministic Dash browser acceptance.

Browser acceptance covers the complete Metadata → Univariate → Bivariate → Multivariate journey, reload persistence, typed failure/retry, upstream invalidation, zero application console/page errors, zero runtime requests to the external visual-reference site, no page-level horizontal overflow, and screenshots for `1440x900`, `1024x768`, and `390x844` across all four routes.

## Repository map

- `src/portfell/app_state/**` — clean `portfell_dash` schema, migrations, repositories, and app-state SQL.
- `src/portfell/market_source/**` — external xetra-loader contracts, read-only PostgreSQL access, coherent snapshots, and market SQL.
- `src/portfell/app_services/**` — typed four-stage application services and analytical orchestration.
- `src/portfell/dash_app/**` — Plotly Dash shell, pages, callbacks, state, figures, and CSS assets.
- `src/portfell/hosted_api.py` — final FastAPI + Dash composition root.
- `tests/browser/**` — Python Playwright browser acceptance.
- `docs/contracts/plotly-dash-ui-v1.md` — frozen visual/product UI contract.
- `docs/contracts/plotly-dash-replacement-v1.md` — replacement/negative-space contract.
- `docs/runbooks/dash-production-cutover.md` — destructive production transition and rollback.
- `BACKLOG.md` — authoritative executable backlog.
- `GATES.md` — quality and merge-gate authority.

## Financial-engineering invariants

Portfell preserves the analytical contracts independently of the UI/runtime replacement. Full listing identity is preserved; missing values are never encoded as plausible zero; covariance availability is explicit; future leakage is prohibited in walk-forward evaluation; requested and actual optimizer methods remain distinguishable; Equal Weight is never a hidden solver fallback; and Multivariate winner selection is driven by out-of-sample evidence with a persisted decision artifact.

No broker execution or provider acquisition is part of the final runtime.
