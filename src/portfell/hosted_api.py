"""FastAPI + Plotly Dash composition over clean app-state and external market data."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI

from portfell.app_services.research import ResearchApplicationService
from portfell.app_state.migration import AppStateMigrationError, migrate_to_head
from portfell.app_state.repository import PostgresAppStateRepository
from portfell.dash_app.app import mount_dash_app
from portfell.hosted_database_connection import connect as connect_database
from portfell.hosted_routes_metadata_projects import metadata_project_router
from portfell.hosted_routes_research import research_router
from portfell.market_source.config import (
    load_app_database_config,
    load_market_source_config,
    validate_app_database_url,
    validate_market_database_url,
)
from portfell.market_source.errors import MarketSourceError
from portfell.market_source.gateway import MarketDataGateway


class HostedApiError(RuntimeError):
    """Redacted runtime composition failure."""


def create_app(service: ResearchApplicationService | None = None) -> FastAPI:
    """Create the final single-workspace HTTP application.

    Tests may omit the service for a composition-only shell. Production always supplies the clean
    app-state/market-source application service and mounts Dash after API routes.
    """
    application = FastAPI(title="Portfell", version="1.0.0")

    @application.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok"}

    if service is not None:
        application.include_router(metadata_project_router(service))
        application.include_router(research_router(service))
        mount_dash_app(application, services=service)
    return application


def create_runtime_app() -> FastAPI:
    """Compose only ``portfell_dash`` app state plus the external xetra-loader read plane."""
    config_path = Path(os.environ.get("PORTFELL_CONFIG_PATH", "config.yaml"))
    try:
        app_config = load_app_database_config(config_path)
        market_config = load_market_source_config(config_path)
        app_url = validate_app_database_url(app_config)
        market_url = validate_market_database_url(market_config)
        app_connection = connect_database(
            app_url,
            autocommit=False,
            password_secret=app_config.password_secret,
        )
        migrate_to_head(app_connection)
        app_state = PostgresAppStateRepository(app_connection)
        market_gateway = MarketDataGateway(
            lambda: connect_database(
                market_url,
                autocommit=False,
                password_secret=market_config.password_secret,
            ),
            role=market_config.role,
            member_of=market_config.member_of,
        )
    except (MarketSourceError, AppStateMigrationError) as error:
        code = getattr(error, "code", None)
        raise HostedApiError(str(code) if isinstance(code, str) else str(error)) from error
    except Exception as error:
        raise HostedApiError("runtime_database_unavailable") from error

    return create_app(ResearchApplicationService(app_state, market_gateway))


__all__ = ["HostedApiError", "create_app", "create_runtime_app"]
