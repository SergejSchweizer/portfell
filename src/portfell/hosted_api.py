"""FastAPI composition root and stable public exports for the hosted API."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, Request

from portfell.entitlements import ProviderDownloadRun
from portfell.hosted_analysis_service import HostedAnalysisService
from portfell.hosted_api_contracts import (
    AnalysisCreateRequest,
    BivariateSelectionRequest,
    CredentialSetRequest,
    CurrentProjectRequest,
    DownloadRequest,
    LoadSelectedIsinsRequest,
    MetadataBuilderProjectRequest,
    MultivariateRunRequest,
    ProjectCreateRequest,
    SelectionCreateRequest,
    UnivariateRunRequest,
    UnivariateSelectionRequest,
)
from portfell.hosted_api_local_runtime import LocalHostedRuntime
from portfell.hosted_api_service_support import opaque_id, stable_hash
from portfell.hosted_api_state import (
    DEFAULT_LOCAL_WORKSPACE_USER_ID,
    AnalysisRecord,
    ApiUser,
    ConfiguredUserProvider,
    CurrentUserProvider,
    HostedApiState,
    LocalWorkspaceUserProvider,
    ProjectRecord,
    SelectionRecord,
    UserOwnedRow,
)
from portfell.hosted_bivariate_service import BivariateResearchService
from portfell.hosted_credential_project_service import CredentialProjectService
from portfell.hosted_credentials import (
    EodhdCredentialVault,
    FileCredentialStore,
    KeyEncryptionKey,
    load_key_encryption_key,
)
from portfell.hosted_database_connection import connect as connect_database
from portfell.hosted_download_run_repository import PostgresDownloadRunRepository
from portfell.hosted_metadata_project_service import MetadataProjectService
from portfell.hosted_multivariate_service import MultivariateResearchService
from portfell.hosted_postgres_repository_bundle import PostgresHostedRepositoryBundle
from portfell.hosted_postgres_request_scope import RequestScopedPostgresConnection
from portfell.hosted_postgres_research_repository import PostgresResearchRepository
from portfell.hosted_postgres_runtime import PostgresHostedRuntime
from portfell.hosted_postgres_workflow import PostgresWorkflowReader
from portfell.hosted_project_bootstrap_repository import PostgresProjectBootstrapRepository
from portfell.hosted_quote_run_service import QuoteRunService
from portfell.hosted_research_persistence import (
    LocalResearchPersistence,
    PostgresResearchPersistence,
)
from portfell.hosted_research_ports import ResearchDataPort
from portfell.hosted_research_repository import HostedResearchRepository
from portfell.hosted_research_service import ResearchService
from portfell.hosted_routes_credentials import credential_router
from portfell.hosted_routes_metadata_projects import metadata_project_router
from portfell.hosted_routes_quote_runs import quote_run_router
from portfell.hosted_routes_research import research_router
from portfell.hosted_shared_market_research_data import SharedMarketResearchData
from portfell.hosted_shared_quote_publisher import SharedQuotePublisher
from portfell.hosted_univariate_service import UnivariateResearchService
from portfell.hosted_user_repository import PostgresHostedUserRepository
from portfell.hosted_workspace import LocalWorkspaceStore
from portfell.hosted_workspace_repository import restore_local_workspace
from portfell.shared_market_data import SharedMarketDataStore
from portfell.workflows import (
    run_fetch_all_metadata_workflow,
    run_fetch_all_quotes_workflow,
)

__all__ = [
    "AnalysisCreateRequest",
    "AnalysisRecord",
    "ApiUser",
    "BivariateSelectionRequest",
    "CredentialSetRequest",
    "CurrentProjectRequest",
    "CurrentUserProvider",
    "ConfiguredUserProvider",
    "DownloadRequest",
    "HostedApiError",
    "HostedApiState",
    "LoadSelectedIsinsRequest",
    "LocalWorkspaceUserProvider",
    "MetadataBuilderProjectRequest",
    "MultivariateRunRequest",
    "ProjectCreateRequest",
    "ProjectRecord",
    "SelectionCreateRequest",
    "SelectionRecord",
    "UnivariateSelectionRequest",
    "UnivariateRunRequest",
    "UserOwnedRow",
    "app",
    "create_app",
    "create_persistent_local_workspace_state",
    "create_runtime_app",
    "_opaque_id",
    "_run_quote_fetch",
    "_stable_hash",
]


class HostedApiError(RuntimeError):
    """Raised when the hosted API cannot satisfy a user-scoped request."""


def _quote_workflow_proxy(**kwargs: Any) -> dict[str, Any]:
    return run_fetch_all_quotes_workflow(**kwargs)


def _metadata_workflow_proxy(**kwargs: Any) -> dict[str, Any]:
    return run_fetch_all_metadata_workflow(**kwargs)


def _runtime() -> LocalHostedRuntime:
    return LocalHostedRuntime(
        quote_workflow=_quote_workflow_proxy,
        metadata_workflow=_metadata_workflow_proxy,
        cpu_count=lambda: os.process_cpu_count(),
    )


def _research_service(state: HostedApiState, data: ResearchDataPort) -> ResearchService:
    """Compose the research facade from explicit repository and adapter boundaries."""

    repository = HostedResearchRepository(state)
    persistence = LocalResearchPersistence(state)
    return ResearchService(
        UnivariateResearchService(repository, data, persistence),
        BivariateResearchService(repository, data, persistence),
        MultivariateResearchService(state, data, persistence, repository),
        HostedAnalysisService(repository, persistence),
    )


def _postgres_services(
    state: HostedApiState,
    *,
    request_scope: RequestScopedPostgresConnection,
    shared_data_root: Path,
    key_encryption_key: KeyEncryptionKey,
) -> tuple[CredentialProjectService, MetadataProjectService, QuoteRunService, ResearchService]:
    """Compose hosted services from PostgreSQL control records and shared payloads only."""

    repositories = PostgresHostedRepositoryBundle.from_connection(request_scope)
    credential_vault = EodhdCredentialVault(
        store=repositories.credentials,
        key_encryption_key=key_encryption_key,
        fingerprint_secret=key_encryption_key.material,
    )
    runtime = PostgresHostedRuntime(shared_data_root)
    data = SharedMarketResearchData(SharedMarketDataStore(shared_data_root))
    bootstrap = PostgresProjectBootstrapRepository(request_scope)
    workflow_reader = PostgresWorkflowReader(
        selections=repositories.selections,
        bootstrap=bootstrap,
        metadata_rows=runtime.all_isins_rows,
    )

    def project_data_loaded(user_id: str, project_id: str) -> bool:
        fill = bootstrap.status(user_id=user_id, project_id=project_id)
        return fill is not None and fill.status == "ready"

    def quote_rows(run_id: str) -> tuple[dict[str, object], ...]:
        row = request_scope.execute(
            "select response_manifest from portfell_app.download_runs "
            "where download_run_id = %s::uuid",
            (run_id,),
        ).fetchone()
        if row is None or len(row) != 1 or not isinstance(row[0], dict):
            return ()
        manifest = cast(dict[str, object], row[0])
        scope = cast(object, manifest.get("requested_scope"))
        if not isinstance(scope, dict):
            return ()
        members = cast(object, scope.get("member_ids"))
        if not isinstance(members, list) or not all(isinstance(item, str) for item in members):
            return ()
        return data.selected_rows(tuple(cast(list[str], members)), dataset="quotes")

    research_repository = PostgresResearchRepository(
        request_scope,
        projects=repositories.projects,
        selections=repositories.selections,
        quotes=repositories.quotes,
        quote_rows=quote_rows,
        analyses=repositories.analyses,
    )
    persistence = PostgresResearchPersistence()
    credentials = CredentialProjectService(
        state,
        runtime,
        repositories.projects,
        repositories.selections,
        repositories.settings,
        credential_vault,
        repositories.audit,
        PostgresDownloadRunRepository(request_scope),
        repositories.idempotency,
        workflow_reader,
        project_data_loaded,
    )
    metadata = MetadataProjectService(
        state,
        runtime,
        repositories.projects,
        repositories.selections,
        repositories.metadata,
        credential_vault,
        repositories.audit,
        bootstrap,
    )
    quotes = QuoteRunService(
        state,
        runtime,
        repositories.projects,
        repositories.selections,
        credential_vault,
        repositories.quotes,
        repositories.audit,
        repositories.idempotency,
        SharedQuotePublisher(SharedMarketDataStore(shared_data_root)),
    )
    research = ResearchService(
        UnivariateResearchService(research_repository, data, persistence),
        BivariateResearchService(research_repository, data, persistence),
        MultivariateResearchService(
            state,
            data,
            persistence,
            research_repository,
            repositories.projects,
            repositories.selections,
            repositories.multivariate,
            runtime.all_isins_rows,
        ),
        HostedAnalysisService(research_repository, persistence),
    )
    return credentials, metadata, quotes, research


def create_persistent_local_workspace_state(
    shared_data_root: Path,
    *,
    key_encryption_key: KeyEncryptionKey,
) -> HostedApiState:
    """Load the durable local workspace from the API shared-data volume."""

    workspace_store = LocalWorkspaceStore(shared_data_root / "local-workspace.json")
    state = HostedApiState(
        credentials=FileCredentialStore(shared_data_root / "encrypted-credentials.json"),
        credential_key_encryption_key=key_encryption_key,
        workspace_store=workspace_store,
        shared_market_data_store=SharedMarketDataStore(shared_data_root),
    )
    restore_local_workspace(state, workspace_store.load())
    return state


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
    ensure_user: Callable[[str], None] | None = None,
) -> FastAPI:
    """Compose the hosted application and its concern-specific route adapters."""

    resolved_state = state or HostedApiState()
    provider = current_user_provider or ConfiguredUserProvider(
        user_id=os.environ.get("PORTFELL_LOCAL_WORKSPACE_USER_ID", DEFAULT_LOCAL_WORKSPACE_USER_ID)
    )
    if services is None:
        runtime = _runtime()
        credentials = CredentialProjectService(resolved_state, runtime)
        metadata = MetadataProjectService(resolved_state, runtime)
        quotes = QuoteRunService(resolved_state, runtime)
        research = _research_service(resolved_state, runtime)
    else:
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
    application.include_router(
        quote_run_router(quotes, current_user=current_user, workspace_user=workspace_user)
    )
    application.include_router(
        research_router(research, current_user=current_user, workspace_user=workspace_user)
    )
    return application


def create_runtime_app() -> FastAPI:
    """Create the persistent container application when secrets are configured."""

    configured_authority = os.environ.get("PORTFELL_HOSTED_AUTHORITY")
    if configured_authority is None and os.environ.get("PORTFELL_DATABASE_URL"):
        raise HostedApiError("hosted_authority_must_be_explicit")
    authority = configured_authority or "local"
    if authority == "postgres":
        database_url = os.environ.get("PORTFELL_DATABASE_URL")
        shared_data_root = os.environ.get("PORTFELL_SHARED_DATA_ROOT")
        key_path = os.environ.get("PORTFELL_EODHD_KEK_FILE")
        if not database_url or not shared_data_root or not key_path:
            raise HostedApiError("postgres_hosted_runtime_configuration_required")
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
            services=_postgres_services(
                state,
                request_scope=request_scope,
                shared_data_root=Path(shared_data_root),
                key_encryption_key=key_encryption_key,
            ),
            request_scope=request_scope,
            ensure_user=PostgresHostedUserRepository(request_scope).create,
        )
    if authority != "local":
        raise HostedApiError("hosted_authority_invalid")
    shared_data_root = os.environ.get("PORTFELL_SHARED_DATA_ROOT")
    key_path = os.environ.get("PORTFELL_EODHD_KEK_FILE")
    if not shared_data_root or not key_path:
        return create_app()
    key_encryption_key = load_key_encryption_key(
        Path(key_path),
        version=os.environ.get("PORTFELL_EODHD_KEK_VERSION", "local-v1"),
    )
    return create_app(
        create_persistent_local_workspace_state(
            Path(shared_data_root), key_encryption_key=key_encryption_key
        )
    )


def _run_quote_fetch(
    state: HostedApiState,
    run: ProviderDownloadRun,
    selection_id: str,
    provider_key: str,
) -> None:
    """Compatibility hook for focused quote-progress tests."""

    QuoteRunService(state, _runtime()).run_quote_fetch(run, selection_id, provider_key)


def _opaque_id(kind: str, value: str) -> str:
    return opaque_id(kind, value)


def _stable_hash(payload: dict[str, Any]) -> str:
    return stable_hash(payload)


app = create_runtime_app()
