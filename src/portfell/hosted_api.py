"""FastAPI + Plotly Dash composition over clean app-state and external market data."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from portfell.app_services.workspace import WorkspaceApplicationService
from portfell.app_state.migration import AppStateMigrationError, migrate_to_head
from portfell.app_state.repository import PostgresAppStateRepository
from portfell.dash_app.app import mount_dash
from portfell.hosted_database_connection import connect as connect_database
from portfell.market_source.config import load_app_database_config, validate_app_database_url
from portfell.market_source.errors import MarketSourceError
from portfell.services.composition import compose_modules, mount_module_routes


class HostedApiError(RuntimeError):
    """Redacted runtime composition failure."""


def create_app(service: WorkspaceApplicationService | None = None) -> FastAPI:
    """Create the final single-workspace HTTP application.

    Tests may omit the service for a composition-only shell. Production always supplies the clean
    app-state/market-source application service and mounts Dash after API routes.
    """

    @asynccontextmanager
    async def lifecycle(_: FastAPI) -> AsyncGenerator[None]:
        if service is not None:
            service.start_background_jobs()
        try:
            yield
        finally:
            if service is not None:
                service.stop_background_jobs()

    application = FastAPI(title="Portfell", version="1.0.0", lifespan=lifecycle)

    @application.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok"}

    if service is not None:
        modules = compose_modules(service)

        @application.get("/api/health", tags=["workflow"])
        def api_health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
            return {"status": "ok", "database": "portfell_dash", "workspace": "default"}

        @application.get("/api/workflow", tags=["workflow"])
        def workflow() -> dict[str, object]:  # pyright: ignore[reportUnusedFunction]
            return modules.workflow.workflow_state()

        mount_module_routes(application, modules)
        mount_dash(application, services=modules)
    return application


def create_runtime_app() -> FastAPI:
    """Compose app state plus the locally published market read plane.

    PostgreSQL market credentials are intentionally not required by the API.
    They belong exclusively to the scheduled ``portfell-market-refresh`` job.
    """
    config_path = Path(os.environ.get("PORTFELL_CONFIG_PATH", "config.yaml"))
    try:
        app_config = load_app_database_config(config_path)
        app_url = validate_app_database_url(app_config)
        app_connection = connect_database(
            app_url,
            autocommit=False,
            password_secret=app_config.password_secret,
        )
        migrate_to_head(app_connection)
        app_state = PostgresAppStateRepository(app_connection)
        from portfell.market_source.local_gateway import LocalMarketDataGateway

        market_root = Path(
            os.environ.get("PORTFELL_MARKET_DATA_ROOT", "/var/lib/portfell/market-data")
        )
        market_gateway = LocalMarketDataGateway(market_root)
    except (MarketSourceError, AppStateMigrationError) as error:
        code = getattr(error, "code", None)
        raise HostedApiError(str(code) if isinstance(code, str) else str(error)) from error
    except Exception as error:
        raise HostedApiError("runtime_database_unavailable") from error

    return create_app(WorkspaceApplicationService(app_state, market_gateway))


__all__ = ["HostedApiError", "create_app", "create_runtime_app"]
