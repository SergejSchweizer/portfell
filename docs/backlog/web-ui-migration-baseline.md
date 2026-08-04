# Web UI Migration Baseline

Last reviewed: 2026-07-27

This baseline freezes the current `apps/web/server.js` experience before the React migration stack starts. It is intentionally descriptive, not aspirational: the inventory records what the current UI actually does, what it depends on, and which current behaviours must remain equivalent until the later PRs replace them.

The machine-readable inventory lives beside this document in `docs/backlog/web-ui-migration-baseline.json`.
The deterministic composite screenshot sheet is `docs/backlog/web-ui-migration-baseline/screenshots/baseline-sheet.svg`.

## Deterministic capture rules

- Locale: `en-US`
- Timezone: `UTC`
- Viewports:
  - Desktop: `1440x1080`
  - Tablet: `1024x1366`
  - Mobile: `390x844`
- Clock: fixed at the capture timestamp encoded in the JSON inventory
- Session data: synthetic only
- Provider data: synthetic only
- Market values: synthetic only
- Error text: redacted before capture

## Route inventory

| Route | Method | Input contract | Output state | Screenshot fixture |
| --- | --- | --- | --- | --- |
| `/` | `GET` | Anonymous request redirects to the login start route. Authenticated request renders the dashboard shell. | Login gate or authenticated shell. | `login.desktop/tablet/mobile`, `dashboard.desktop/tablet/mobile` |
| `/health` | `GET` | No body. | JSON `{ "status": "ok" }`. | `health.desktop/tablet/mobile` |
| `/auth/google/start` | `GET` | No body. Local-dev mode sets a synthetic session; production mode redirects to Google. | Login transition or Google redirect. | `login.desktop/tablet/mobile` |
| `/auth/google/callback` | `GET` | Query string with `code` and `state`. | Authenticated session on success, redacted auth error on failure. | `login.desktop/tablet/mobile` |
| `/auth/logout` | `GET` | No body. | Session cleared and login gate shown. | `login.desktop/tablet/mobile` |
| `/api/session` | `GET` | Cookie-authenticated request. | Session status object with redacted identity fields. | `dashboard.desktop/tablet/mobile` |
| `/api/credentials/eodhd` | `GET` | Cookie-authenticated request. | Saved credential status or inactive state. | `dashboard.desktop/tablet/mobile` |
| `/api/credentials/eodhd` | `POST` | JSON `{ provider_key }` plus CSRF and idempotency key. | Persisted synthetic credential state. | `dashboard.desktop/tablet/mobile` |
| `/api/projects` | `GET` | Cookie-authenticated request. | Project list. | `project-shell-selected.desktop/tablet/mobile` |
| `/api/metadata-filter/options` | `GET` | Cookie-authenticated request. | Select-option sets for exchange, instrument type, country, and currency. | `project-shell-empty.desktop/tablet/mobile` |
| `/api/metadata-filter/fetch-all-metadata` | `POST` | No body, CSRF and idempotency key required. | Enables the project-definition gate and reports a synthetic row count. | `project-shell-empty.desktop/tablet/mobile` |
| `/api/metadata-filter/projects` | `POST` | JSON project-definition filters plus CSRF and idempotency key. | Creates a synthetic project and selection. | `project-shell-empty.desktop/tablet/mobile` |
| `/api/data/load-selected-isins` | `POST` | JSON `{ project_id }` plus CSRF and idempotency key. | Load-data step progress and completion state. | `statistics-load-data.desktop/tablet/mobile` |
| `/api/statistics/univariate/summary` | `GET` | Cookie-authenticated request. | Univariate summary table or empty-state row. | `statistics-univariate.desktop/tablet/mobile` |
| `/api/statistics/{kind}/compute` | `POST` | JSON `{ project_id }` plus CSRF and idempotency key. `kind` is `univariate`, `bivariate`, or `multivariate`. | Step progress, completion, warning, or failure state. | `statistics-{kind}.desktop/tablet/mobile` |

## Interactive controls

| Control | Selector or label | Endpoint | Input contract | Output state | Screenshot fixture |
| --- | --- | --- | --- | --- | --- |
| Google Login | `data-form="google-login"` / `Google Login` | `/auth/google/start` | GET form submit. | Login transition. | `login.desktop/tablet/mobile` |
| Google Auth logout | `data-action="google-auth"` / `Google Auth` | `/auth/logout` | Plain GET link. | Login gate restored. | `login.desktop/tablet/mobile` |
| EODHD key field | `name="provider_key"` | `/api/credentials/eodhd` then `/api/metadata-filter/fetch-all-metadata` | Write-only masked password field. | Enables project setup when saved. | `dashboard.desktop/tablet/mobile` |
| Fetch all metadata | `data-action="fetch-all-metadata"` / `Fetch all metadata` | `/api/credentials/eodhd` and `/api/metadata-filter/fetch-all-metadata` | Uses current key, CSRF, and idempotency key. | Project gate opens and projects refresh. | `project-shell-empty.desktop/tablet/mobile` |
| Project selector | `data-project-selector` | `/api/projects` | Change event only. | Shell switches between the empty and selected project states. | `project-shell-selected.desktop/tablet/mobile` |
| Project definition form | `data-form="project-definition"` | `/api/metadata-filter/projects` | Exchange, name, instrument type, country, currency. | Synthetic project created and selected. | `project-shell-empty.desktop/tablet/mobile` |
| Statistics path buttons | `data-statistics-step` | None; client-side state only. | Select the visible step panel. | Updates the active statistics page. | `statistics-step.desktop/tablet/mobile` |
| Compute step buttons | `data-compute-statistics` | `/api/data/load-selected-isins` or `/api/statistics/{kind}/compute` | Project id from the active shell plus CSRF and idempotency key. | Step progress and completion state. | `statistics-{kind}.desktop/tablet/mobile` |
| Univariate filter selects | `data-univariate-summary-body select` | `/api/statistics/univariate/summary` | Read-only selection options from synthetic summary rows. | Table updates without external calls. | `statistics-univariate.desktop/tablet/mobile` |

## State baseline

| State | What the current UI shows | Required fixture panels |
| --- | --- | --- |
| Login | Google login gate, brand, and session-checking status. | Desktop, tablet, mobile |
| Dashboard | Authenticated shell, sidebar, project selector, EODHD key input, and empty shell copy. | Desktop, tablet, mobile |
| Project shell: empty | Project definition form, disabled metadata controls, and no project selected copy. | Desktop, tablet, mobile |
| Project shell: selected | Project selector populated, statistics path visible, and current project title. | Desktop, tablet, mobile |
| Statistics: load-data | Load Data page, progress banner, and selected-ISIN count update. | Desktop, tablet, mobile |
| Statistics: univariate | Univariate page and summary table state. | Desktop, tablet, mobile |
| Statistics: bivariate | Bivariate page shell and progress banner. | Desktop, tablet, mobile |
| Statistics: multivariate | Multivariate page shell and progress banner. | Desktop, tablet, mobile |
| Loading | `Checking session...`, `Loading statistics summary...`, or equivalent progress text. | Desktop, tablet, mobile |
| Complete | `Loaded selected ISINs.` or `Completed ... statistics.` | Desktop, tablet, mobile |
| Warning | Redacted warning status with no provider secrets or internal ids. | Desktop, tablet, mobile |
| Failed | Redacted failure status with retry-safe messaging. | Desktop, tablet, mobile |
| Empty | No project selected, no statistics rows, or no data available. | Desktop, tablet, mobile |

## Known retained defects

The baseline keeps these current behaviours as deliberate migration references instead of silently turning them into new requirements:

1. The UI still uses the monolithic HTML-string renderer and direct DOM mutations.
2. The current shell still multiplexes the statistics workflow through hidden panels instead of real React routes.
3. The login gate still redirects anonymous root requests to the Google start flow instead of rendering a public landing page.
4. The project-definition form remains disabled until the EODHD and metadata gate opens.
5. The sidebar resizer is hidden below the narrow layout breakpoint.

## Explicitly excluded from the migration baseline

- Legacy labels that no longer belong to the current shell, including `Project Snapshot`, `Downloads`, `Metadata Filter`, `Portfolio Analysis`, and `Delete Account Data`.
- Provider secrets, cookies, tokens, raw callback payloads, internal filesystem paths, shared artifact ids, and cross-user data.
- Any browser-side calculation or authorization decision.
- Any expectation that the current Web app will already be React-based.
