# Metadata

Route: `/metadata`

Subtitle: `Build the active Xetra instrument universe.`

The final Metadata page is a Plotly Dash page. It reads active listings only through the typed application service/`MarketDataGateway`; callbacks execute no SQL and expose no provider fetch/download action.

## Layout

The shared Portfell shell contains the four ordered navigation items Metadata, Univariate, Bivariate, Multivariate and the current-analysis context block.

The page contains:

- `PageHeader` with the frozen title/subtitle;
- one `ControlBar` with supported metadata predicates plus `Reset filters` and `Create universe`;
- KPI cards `Active listings`, `Filtered listings`, `Selected listings`, `Universe version`;
- `TableCard` `Xetra Listings` preserving full identity `(isin, exchange, code)`;
- `HistoryCard` `Universe & History` with persisted universe version, creation timestamp, source snapshot short ID, and member count;
- `StageFooter` with `Continue to Univariate`, disabled until a persisted universe is ready.

## Behavioral contract

New universes use only `is_active=true` listings. Inactive identities may remain historically resolvable but cannot be newly selected. Metadata predicate semantics are backend-authoritative and must not be redefined by browser state or PostgreSQL collation behavior. Duplicate ISINs remain distinct when exchange/code differ.

Create-universe is idempotent for an identical content identity. A persisted universe reloads after application restart and repopulates page/sidebar/history state. Empty results remain explicit rather than rendering a blank table/card.

## Responsive/accessibility contract

Desktop uses the shared 220px sidebar; tablet keeps navigation visible at reduced density; mobile converts to the shared compact top-navigation layout. Controls stack on narrow screens and table overflow stays inside its card. Page-level horizontal overflow is forbidden. Actions and validation/status states remain keyboard reachable.

No unrelated financial chart/metric is added to Metadata merely to resemble the external visual reference.