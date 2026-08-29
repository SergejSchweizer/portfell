"""FastAPI composition root and stable public exports for the hosted API."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request

from portfell.hosted_api_contracts import (
    AnalysisCreateRequest,
    BivariateSelectionRequest,
    CredentialSetRequest,
    CurrentProjectRequest,
    LoadSelectedIsinsRequest,
    MetadataBuilderProjectRequest,
    MultivariateRunRequest,
    ProjectCreateRequest,
    SelectionCreateRequest,
    UnivariateRunRequest,
    UnivariateSelectionRequest,
)
from portfell.hosted_api_state import (
    DEFAULT_LOCAL_WORKSPACE_USER_ID,
    AnalysisRecord,
    ApiUser,
    ConfiguredUserProvider,
    CurrentUserProvider,
    HostedApiState,
    ProjectRecord,
    SelectionRecord,
    UserOwnedRow,
)
from portfell.hosted_credential_project_service import CredentialProjectService
from portfell.hosted_credentials import load_key_encryption_key
from portfell.hosted_database_connection import connect as connect_database
from portfell.hosted_metadata_project_service import MetadataProjectService
from portfell.hosted_postgres_request_scope import RequestScopedPostgresConnection
from portfell.hosted_postgres_service_composition import build_postgres_services
from portfell.hosted_quote_run_service import QuoteRunService
from portfell.hosted_research_service import ResearchService
from portfell.hosted_routes_credentials import credential_router
from portfell.hosted_routes_metadata_projects import metadata_project_router
from portfell.hosted_routes_quote_runs import quote_run_router
from portfell.hosted_routes_research import research_router
from portfell.hosted_routes_status_events import status_event_router
from portfell.hosted_status_event_stream import StatusEventConnectionLimiter
from portfell.hosted_user_repository import PostgresHostedUserRepository
from portfell.market_source.config import (
    load_app_database_config,
    load_market_source_config,
    validate_app_database_url,
    validate_market_database_url,
)
from portfell.market_source.gateway import MarketDataGateway

__all__ = [
    "AnalysisCreateRequest",
    "AnalysisRecord",
    "ApiUser",
    "BivariateSelectionRequest",
    "CredentialSetRequest",
    "CurrentProjectRequest",
    "CurrentUserProvider",
    "ConfiguredUserProvider",
    "HostedApiError",
    "HostedApiState",
    "LoadSelectedIsinsRequest",
    "MetadataBuilderProjectRequest",
    "MultivariateRunRequest",
    "ProjectCreateRequest",
    "ProjectRecord",
    "SelectionCreateRequest",
    "SelectionRecord",
    "UnivariateSelectionRequest",
    "UnivariateRunRequest",
    "UserOwnedRow",
    "create_app",
    "create_runtime_app",
]


class HostedApiError(RuntimeError):
    """Raised when the hosted API cannot satisfy a user-scoped request."""


def create_app(
    state: HostedApiState | None = None,
    *,
    current_user_provider: CurrentUserProvider | None = None,
    services: tuple[
        CredentialProjectService,
        MetadataProjectService,
        QuoteRunService,
        ResearchService,
    ]
    | None = None,
    request_scope: RequestScopedPostgresConnection | None = None,
    ensure_user: Callable[[str], object] | None = None,
    include_quote_routes: bool = True,
) -> FastAPI:
    """Compose the hosted application and its concern-specific route adapters."""

    resolved_state = state or HostedApiState()
    provider = current_user_provider or ConfiguredUserProvider(
        user_id=os.environ.get("PORTFELL_LOCAL_WORKSPACE_USER_ID", DEFAULT_LOCAL_WORKSPACE_USER_ID)
    )
    if services is None:
        raise HostedApiError("hosted_services_must_be_explicit")
    credentials, metadata, quotes, research = services

    def current_user() -> ApiUser:
        return provider.current_user()

    def workspace_user() -> ApiUser:
        return provider.current_user()

    application = FastAPI(title="Portfell Hosted API", version="0.1.0")
    if request_scope is not None:

        @application.middleware("http")
        async def postgres_request_scope(  # pyright: ignore[reportUnusedFunction]
            request: Request, call_next: Any
        ) -> Any:
            user_id = provider.current_user().user_id
            with request_scope.request(user_id):
                if ensure_user is not None:
                    ensure_user(user_id)
                return await call_next(request)

    application.state.portfell_state = resolved_state
    application.include_router(
        credential_router(credentials, current_user=current_user, workspace_user=workspace_user)
    )
    application.include_router(
        metadata_project_router(
            credentials,
            metadata,
            current_user=current_user,
            workspace_user=workspace_user,
        )
    )
    if include_quote_routes:
        application.include_router(
            quote_run_router(quotes, current_user=current_user, workspace_user=workspace_user)
        )
    application.include_router(
        research_router(
            research,
            credentials,
            current_user=current_user,
            workspace_user=workspace_user,
            request_scope=request_scope,
        )
    )
    if request_scope is not None:
        application.include_router(
            status_event_router(
                request_scope=request_scope,
                current_user=current_user,
                limiter=StatusEventConnectionLimiter(),
            )
        )
    return application


def create_runtime_app() -> FastAPI:
    """Create the persistent container application when secrets are configured."""

    if os.environ.get("PORTFELL_HOSTED_AUTHORITY") != "postgres":
        raise HostedApiError("postgres_hosted_authority_required")
    database_url = os.environ.get("PORTFELL_DATABASE_URL")
    shared_data_root = os.environ.get("PORTFELL_SHARED_DATA_ROOT")
    key_path = os.environ.get("PORTFELL_EODHD_KEK_FILE")
    if not database_url or not shared_data_root or not key_path:
        raise HostedApiError("postgres_hosted_runtime_configuration_required")
    config_path = Path(os.environ.get("PORTFELL_CONFIG_PATH", "config.yaml"))
    app_database = load_app_database_config(config_path)
    market_database = load_market_source_config(config_path)
    database_url = validate_app_database_url(app_database, database_url)
    market_database_url = validate_market_database_url(market_database)
    key_encryption_key = load_key_encryption_key(
        Path(key_path),
        version=os.environ.get("PORTFELL_EODHD_KEK_VERSION", "hosted-v1"),
    )
    request_scope = RequestScopedPostgresConnection(
        lambda: connect_database(database_url, autocommit=False)
    )
    state = HostedApiState()
    return create_app(
        state,
        services=build_postgres_services(
            state,
            request_scope=request_scope,
            shared_data_root=Path(shared_data_root),
            key_encryption_key=key_encryption_key,
            market_gateway=MarketDataGateway(
                lambda: connect_database(
                    market_database_url,
                    autocommit=False,
                    password_secret=market_database.password_secret,
                ),
                role=market_database.role,
                member_of=market_database.member_of,
            ),
        ),
        request_scope=request_scope,
        ensure_user=PostgresHostedUserRepository(request_scope).create,
        include_quote_routes=False,
    )


# The container entry point invokes ``create_runtime_app`` as a Uvicorn factory.
# It accepts PostgreSQL as its only hosted authority.
