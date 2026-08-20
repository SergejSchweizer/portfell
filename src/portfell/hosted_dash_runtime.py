"""Hosted composition root that mounts the presentation-only Dash application."""

from __future__ import annotations

from typing import cast

from portfell.dash_ui.runtime.mount import mount_dash_application
from portfell.hosted_api import create_runtime_app
from portfell.hosted_api_state import CurrentUserProvider
from portfell.hosted_credential_project_service import CredentialProjectService
from portfell.hosted_dash_gateway import HostedDashGateway
from portfell.hosted_metadata_project_service import MetadataProjectService
from portfell.hosted_postgres_request_scope import RequestScopedPostgresConnection
from portfell.hosted_quote_run_service import QuoteRunService
from portfell.hosted_research_service import ResearchService


def create_runtime_app_with_dash() -> object:
    """Compose FastAPI once, inject its services into the hosted Dash gateway, then mount Dash."""

    application = create_runtime_app()
    services = cast(
        tuple[
            CredentialProjectService,
            MetadataProjectService,
            QuoteRunService,
            ResearchService,
        ],
        application.state.portfell_services,
    )
    request_scope = cast(
        RequestScopedPostgresConnection | None,
        application.state.portfell_request_scope,
    )
    if request_scope is None:
        raise RuntimeError("dash_requires_postgres_request_scope")
    provider = cast(CurrentUserProvider, application.state.portfell_current_user_provider)
    projects, metadata, _quotes, research = services
    gateway = HostedDashGateway(
        projects=projects,
        metadata=metadata,
        research=research,
        request_scope=request_scope,
        current_user_provider=provider,
    )
    return mount_dash_application(application, gateway)
