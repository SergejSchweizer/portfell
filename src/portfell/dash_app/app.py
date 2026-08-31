"""Dash/FastAPI composition for the final four-page browser application."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dash import Dash, Input, Output
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from starlette.middleware.wsgi import WSGIMiddleware

from portfell.dash_app.contracts import DEFAULT_ROUTE
from portfell.dash_app.shell import root_layout, route_renderer


def create_dash_app(*, services: object | None = None) -> Dash:
    """Create one Dash application with no Node/npm runtime boundary."""
    assets = Path(__file__).with_name("assets")
    app = Dash(
        __name__,
        assets_folder=str(assets),
        suppress_callback_exceptions=True,
        title="Portfell",
        update_title=None,
    )
    app.layout = root_layout()
    render = route_renderer(services)

    @app.callback(Output("pf-route-content", "children"), Input("pf-location", "pathname"))
    def _render_route(pathname: str | None) -> Any:
        return render(pathname)

    return app


def mount_dash_app(
    api: FastAPI,
    *,
    services: object | None = None,
    dash_app: Dash | None = None,
) -> Dash:
    """Mount Dash after FastAPI routes so API/health endpoints remain authoritative."""
    application = dash_app or create_dash_app(services=services)

    @api.get("/", include_in_schema=False)
    def _dash_root_redirect() -> RedirectResponse:
        return RedirectResponse(DEFAULT_ROUTE, status_code=307)

    api.mount("/", WSGIMiddleware(application.server), name="portfell-dash")
    return application


__all__ = ["create_dash_app", "mount_dash_app"]
