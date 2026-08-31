# Plotly Dash UI contract v1

Status: normative implementation contract for PR348–PR355. `BACKLOG.md` remains the sole executable backlog authority.

External visual reference: `https://financial-dashboard-example.plotly.app/`. The reference is documentation/design inspiration only. Portfell must not fetch it at runtime or in deterministic tests, embed it, copy its branding/content/fund data/document links/assets, or add product features merely because they exist in the reference application.

## Table of contents

1. [Product frame](#1-product-frame)
2. [Design tokens](#2-frozen-design-tokens)
3. [Responsive contract](#3-responsive-contract)
4. [Shared primitives](#4-shared-presentation-primitives)
5. [Shared Plotly figures](#5-shared-plotly-figure-contract)
6. [Metadata page](#6-metadata-page)
7. [Univariate page](#7-univariate-page)
8. [Bivariate page](#8-bivariate-page)
9. [Multivariate page](#9-multivariate-page)
10. [Cross-page state](#10-cross-page-state-and-navigation)
11. [Non-goals](#11-explicit-non-goals)

## 1. Product frame

Portfell is one single-user analytical application with exactly four production product pages, in this navigation order:

1. `Metadata` — `/metadata`
2. `Univariate` — `/univariate`
3. `Bivariate` — `/bivariate`
4. `Multivariate` — `/multivariate`

`/` redirects deterministically to `/metadata` and is not a fifth page. There is no dashboard/home page, project picker, user picker, provider-download page, refresh page, resources page, fee page, document page, or separate optimizer page.

Desktop uses a persistent left navigation. The sidebar begins with a small `Portfell` product header, then the four navigation items, then one compact analytical context block. The context block may show only service-derived current universe/version, selected instrument count when available, current source-snapshot short ID, and current stage readiness. Only the current route receives the active navigation style.

Main content uses one consistent vertical hierarchy:

```text
PageHeader
ControlBar
KPI row (when defined for the page)
primary ChartCard/TableCard content
secondary evidence cards
HistoryCard: Universe & History
StageFooter
```

No page creates a page-specific shell, sidebar, card system, figure theme, loading system, or error presentation.

## 2. Frozen design tokens

- desktop sidebar width: `220px`
- desktop main padding: `24px`
- tablet/mobile main padding: `16px`
- layout gap: `16px`
- card radius: `8px`
- application background: `#f7f9fc`
- card/surface: `#ffffff`
- border: `#e3e8ef`
- primary text: `#172033`
- muted text: `#6b7280`
- accent: `#2f80ed`
- active-navigation accent-soft background: `#eaf3ff`
- semantic success: `#198754`
- semantic danger: `#dc3545`
- font stack: `system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`

Normal selection/navigation uses the blue accent family. Green/red are semantic only. There are no decorative gradients, 3D plots, marketing hero blocks, carousels, giant logos, or animation without analytical meaning.

## 3. Responsive contract

### Desktop — `>= 1100px`

- fixed `220px` sidebar;
- fluid main region with `24px` padding;
- four KPI cards use four columns when a page defines four KPIs;
- charts fill their card width;
- no body/page-level horizontal overflow.

### Tablet — `768px–1099px`

- sidebar remains visible at reduced content density;
- main padding `16px`;
- KPI rows become two columns;
- charts remain full-card width;
- tables may scroll only inside their own card.

### Mobile — `< 768px`

- sidebar becomes a compact top navigation region using Dash/CSS only;
- controls stack;
- KPI cards stack to one column;
- content cards and responsive Plotly figures stack to one column;
- tables may horizontally scroll inside their card;
- body/page itself must have no horizontal overflow.

Deterministic browser QA viewports are at least `1440x900`, `1024x768`, and `390x844`.

## 4. Shared presentation primitives

PR348 implements and all page PRs consume exactly these shared primitives:

- `PageHeader` — one page title and one short subtitle;
- `ControlBar` — compact page controls and primary analytical actions;
- `KpiCard` — one label, one primary value, at most one short evidence line;
- `ChartCard` — title + responsive Plotly figure/unavailable state;
- `TableCard` — title + bounded table/empty/unavailable state;
- `StatusBanner` — typed loading/stale/error/unavailable state without internals;
- `HistoryCard` — persisted `Universe & History` lineage/evidence;
- `StageFooter` — downstream readiness/action or final stage eligibility.

Stable component IDs/classes are required for deterministic tests. Loading, empty, unavailable, validation, disabled-action and typed-error states are shared, keyboard reachable, and never use color as their only carrier of meaning.

## 5. Shared Plotly figure contract

All figures use one shared Portfell Plotly template:

- system font;
- transparent plot area on a white card surface;
- restrained grid/axis styling;
- explicit axis labels and units;
- deterministic legend placement/order;
- deterministic hover formatting;
- responsive sizing (`responsive=true` behavior);
- no financial recomputation in Dash solely for plotting;
- missing/unavailable values are unavailable, never plausible zero;
- full listing or pair identity appears in hover where ambiguity exists.

Positive/negative plot colors are used only when metric semantics justify them; normal categorical series use one shared categorical palette.

## 6. Metadata page

Route: `/metadata`

Title: `Metadata`

Subtitle: `Build the active Xetra instrument universe.`

Primary actions: `Reset filters`, `Create universe`, `Continue to Univariate`.

Layout and content:

- `PageHeader` with the frozen title/subtitle;
- one `ControlBar` containing only metadata predicates supported by the backend service contract and the two metadata actions;
- four KPI slots: `Active listings`, `Filtered listings`, `Selected listings`, `Universe version`;
- `TableCard` titled `Xetra Listings`, preserving full identity `(isin, exchange, code)` and exact service-provided metadata fields;
- `HistoryCard` titled `Universe & History`, showing persisted universe version, creation timestamp, source snapshot short ID, and member count;
- `StageFooter` with `Continue to Univariate`, disabled until a persisted Metadata universe is ready.

Unavailable KPI values render `—`, not fabricated zero. New universes use active listings only; inactive historical identities may be resolved but not newly selected. There is no provider fetch/download/refresh control and no decorative chart added merely to resemble the reference application.

## 7. Univariate page

Route: `/univariate`

Title: `Univariate`

Subtitle: `Inspect single-instrument return and risk statistics, then persist the downstream selection.`

Primary actions: `Compute univariate statistics`, `Save selection`, `Continue to Bivariate`.

Layout and content:

- `PageHeader`;
- `ControlBar` with the compute action and only backend-supported result filters/settings;
- KPI slots: `Input instruments`, `Available results`, `Selected instruments`, `Unavailable results`;
- `ChartCard` titled exactly `Univariate Return / Risk Universe`;
- `TableCard` titled `Univariate Statistics` with service metrics and downstream-selection controls;
- `HistoryCard` titled `Universe & History` with input Metadata universe/version, run ID/status, source snapshot short ID, algorithm version, persisted selection version/count;
- `StageFooter` with `Save selection` and `Continue to Bivariate`, continuation disabled until a valid persisted selection exists.

The chart consumes immutable service/artifact values. Hover exposes full listing identity plus backend return/risk fields. Annualized return, volatility, drawdown, yield and other financial statistics remain backend-authoritative. Missing adjusted close is typed unavailable evidence, never raw-close/zero fallback. Persisted selection reloads after restart.

## 8. Bivariate page

Route: `/bivariate`

Title: `Bivariate`

Subtitle: `Inspect pairwise diversification evidence for the persisted Univariate selection.`

Primary actions: `Compute bivariate statistics`, `Continue to Multivariate`.

Layout and content:

- `PageHeader`;
- `ControlBar` with the compute action and only backend-supported pair-result controls;
- KPI slots: `Input instruments`, `Candidate pairs`, `Eligible pairs`, `Unavailable pairs`;
- `ChartCard` titled exactly `Bivariate Return / Diversification Universe`;
- `TableCard` titled `Bivariate Statistics` with both full listing identities and contracted pair evidence;
- explicit unavailable reason/evidence for missing correlation/covariance/common-calendar data;
- `HistoryCard` titled `Universe & History` with upstream selection version/count, Bivariate run ID/status, source snapshot short ID, algorithm version, pair counts;
- `StageFooter` with `Continue to Multivariate`, disabled until the backend marks Bivariate ready.

The page consumes the exact persisted Univariate selection, never a browser-only subset. Common-calendar, minimum-observation, pair-eligibility and same-ISIN rules remain backend-authoritative. Missing correlation/covariance is unavailable, never plotted as zero. Large pair results are bounded/paged by the selected Dash-native table component.

## 9. Multivariate page

Route: `/multivariate`

Title: `Multivariate`

Subtitle: `Optimize candidate portfolios and select the final portfolio from out-of-sample evidence.`

Primary action: `Optimize portfolio`.

Objective selector values are exactly:

- `return_risk` — default;
- `return_drawdown`;
- `minimum_risk`.

Layout and content:

- `PageHeader`;
- `ControlBar` with the exact objective selector and `Optimize portfolio`; additional analytical controls are allowed only if frozen in the backend service contract;
- KPI slots: `Winner OOS return`, `Winner OOS risk`, `Winner max drawdown`, `Production eligibility`;
- `ChartCard` titled `Portfolio Candidate OOS Return / Risk`;
- `ChartCard` titled `Cumulative Performance`;
- `ChartCard` titled `Drawdown`;
- `ChartCard` titled `Allocation` when weight artifacts exist, otherwise a shared unavailable state;
- `ChartCard` titled `Risk Contribution` when risk-contribution artifacts exist, otherwise a shared unavailable state;
- `TableCard` titled `Final Portfolio` with full identity, final weight and only fields supplied by the winner artifact;
- evidence card titled `Decision`, showing objective, winning candidate ID, requested method, actual method, source snapshot short ID, algorithm version, availability, production eligibility, and persisted reason/explanation fields;
- `HistoryCard` titled `Universe & History` with upstream stage identities and Multivariate run history;
- `StageFooter` shows final readiness/eligibility but does not create a fifth stage.

OOS evidence selects the winner. In-sample-best substitution is forbidden. Equal Weight is never a hidden solver fallback. Requested/actual method and all KPI/plot/table values come from persisted artifacts/DecisionArtifact. Rendering, card changes, navigation, or resize never triggers optimization. Objective changes mark a mismatched prior winner stale until a matching completed run is selected/executed.

## 10. Cross-page state and navigation

The browser may store identifiers and presentation state only. It is not business authority for market rows, full financial result tables, credentials, or secrets. Readiness and sidebar/footer state derive from the same typed persisted/service state.

A new Metadata universe invalidates downstream Univariate/Bivariate/Multivariate readiness. A new persisted Univariate selection invalidates Bivariate/Multivariate readiness. A matching new Bivariate run invalidates only downstream Multivariate readiness according to the service contract. Route changes are non-mutating.

Restart reconstructs analytical state from the application-state database and service contracts, not browser cache.

## 11. Explicit non-goals

This UI contract does not add authentication, multi-user/tenant/project switching, provider credentials, market downloads, market refresh controls, benchmarks, fee/tax modeling, document/resource downloads, a fifth dashboard page, a second optimizer page, a first-party React extension, a Node production UI, or direct SQL in callbacks.
