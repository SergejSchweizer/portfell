# UI page development

Last reviewed: 2026-10-03

Portfell uses Plotly Dash served by the FastAPI application. There is no separate React,
Vite, Node, or browser-owned financial-logic application in the current codebase.

## Required boundaries

- Page implementations live in `src/portfell/dash_app/pages/`.
- Each visible page has one owning module in `src/portfell/modules/` with its own Python
  service facade and `/api/<module>` router.
- `src/portfell/dash_app/callbacks.py` coordinates transitions but contains no SQL or
  financial calculations.
- Page specifications live beside this file in `docs/ui/windows/` and must match the
  route, visible controls, states, and backend-owned metrics.
- Shared shell behavior belongs in `src/portfell/dash_app/shell.py`; shared components
  belong in `src/portfell/dash_app/components.py`.

## Change checklist

1. Update the owning Python page, module router/service, and matching window sidecar.
2. Keep request/response models in the module API boundary and add focused regression tests.
3. Verify the four visible routes: `/metadata`, `/univariate`, `/bivariate`, and `/multivariate`.
4. Run `uv run portfell-quality pr` and rebuild the Docker image before hand-off.

Financial calculations, ingestion, authentication, authorization, and persistence remain
server-owned. A page may format service-owned values for presentation but must not recreate
those decisions from browser state.
