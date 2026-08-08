"""FastAPI composition root and stable public exports for the hosted API."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from portfell.entitlements import ProviderDownloadRun
from portfell.hosted_api_contracts import (
    AnalysisCreateRequest,
    BivariateSelectionRequest,
    CredentialSetRequest,
    CurrentProjectRequest,
    DownloadRequest,
    LoadSelectedIsinsRequest,
    MetadataFilterProjectRequest,
    ProjectCreateRequest,
    SelectionCreateRequest,
    UnivariateFilterRequest,
    UnivariateRunRequest,
)
from portfell.hosted_api_local_runtime import LocalHostedRuntime
from portfell.hosted_api_service_support import opaque_id, stable_hash
from portfell.hosted_api_state import (
    DEFAULT_LOCAL_WORKSPACE_USER_ID,
    AnalysisRecord,
    ApiUser,
    CurrentUserProvider,
    HostedApiState,
    LocalWorkspaceUserProvider,
    ProjectRecord,
    SelectionRecord,
    UserOwnedRow,
)
from portfell.hosted_credential_project_service import CredentialProjectService
from portfell.hosted_credentials import (
    FileCredentialStore,
    KeyEncryptionKey,
    load_key_encryption_key,
)
from portfell.hosted_metadata_project_service import MetadataProjectService
from portfell.hosted_quote_run_service import QuoteRunService
from portfell.hosted_research_service import ResearchService
from portfell.hosted_routes_credentials import credential_router
from portfell.hosted_routes_metadata_projects import metadata_project_router
from portfell.hosted_routes_quote_runs import quote_run_router
from portfell.hosted_routes_research import research_router
from portfell.hosted_workspace import LocalWorkspaceStore
from portfell.hosted_workspace_repository import restore_local_workspace
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
    "DownloadRequest",
    "HostedApiError",
    "HostedApiState",
    "LoadSelectedIsinsRequest",
    "LocalWorkspaceUserProvider",
    "MetadataFilterProjectRequest",
    "ProjectCreateRequest",
    "ProjectRecord",
    "SelectionCreateRequest",
    "SelectionRecord",
    "UnivariateFilterRequest",
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
    )
    restore_local_workspace(state, workspace_store.load())
    return state


def create_app(
    state: HostedApiState | None = None,
    *,
    current_user_provider: CurrentUserProvider | None = None,
) -> FastAPI:
    """Compose the hosted application and its concern-specific route adapters."""

    resolved_state = state or HostedApiState()
    provider = current_user_provider or LocalWorkspaceUserProvider(
        user_id=os.environ.get("PORTFELL_LOCAL_WORKSPACE_USER_ID", DEFAULT_LOCAL_WORKSPACE_USER_ID)
    )
    runtime = _runtime()
    credentials = CredentialProjectService(resolved_state, runtime)
    metadata = MetadataProjectService(resolved_state, runtime)
    quotes = QuoteRunService(resolved_state, runtime)
    research = ResearchService(resolved_state)

    def current_user() -> ApiUser:
        return provider.current_user()

    def workspace_user() -> ApiUser:
        return provider.current_user()

    application = FastAPI(title="Portfell Hosted API", version="0.1.0")
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
