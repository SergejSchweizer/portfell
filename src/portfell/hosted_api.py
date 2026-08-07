"""FastAPI hosted API boundary for user-scoped Portfell workflows."""

# pyright: reportUnusedFunction=false
# ruff: noqa: B008

from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Protocol, cast

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from portfell.config import EodhdConfig
from portfell.entitlements import (
    InMemoryEntitlementStore,
    ProviderDownloadRun,
    delete_user_entitlements,
    publish_user_data_snapshot,
)
from portfell.hosted_credentials import (
    CredentialStatus,
    CredentialStore,
    CredentialVaultError,
    EodhdCredentialVault,
    FileCredentialStore,
    InMemoryCredentialStore,
    KeyEncryptionKey,
    load_key_encryption_key,
)
from portfell.hosted_research_workflow import (
    FilterSelection,
    HostedResearchError,
    ResearchRun,
    create_bivariate_run,
    create_filter_selection,
    create_univariate_run,
    page_rows,
    pair_plan,
)
from portfell.hosted_workspace import LocalWorkspaceStore
from portfell.http import EodhdHttpError
from portfell.metadata_filter import write_metadata_selection
from portfell.paths import LakePaths
from portfell.selection_filters import Predicate, filter_rows
from portfell.table_io import JsonRow, read_rows
from portfell.workflow_state import resolve_workflow
from portfell.workflows import (
    run_fetch_all_metadata_workflow,
    run_fetch_all_quotes_workflow,
)

DEFAULT_LOCAL_WORKSPACE_USER_ID = "user-a"
REMOVED_PROJECT_NAMES = frozenset({"Statistics Smoke"})


class HostedApiError(RuntimeError):
    """Raised when the hosted API cannot satisfy a user-scoped request."""


class CredentialSetRequest(BaseModel):
    """Request to set or replace a provider credential."""

    provider_key: str = Field(min_length=1, max_length=4096)


class DownloadRequest(BaseModel):
    """Request to plan or run a user-key-backed download."""

    symbols: list[str] = Field(default_factory=list, max_length=1000)


class ProjectCreateRequest(BaseModel):
    """Request to create one user-owned project."""

    name: str = Field(min_length=1, max_length=120)


class CurrentProjectRequest(BaseModel):
    """Request to select the current local-workspace project."""

    project_id: str = Field(min_length=1, max_length=160)


class MetadataFilterProjectRequest(BaseModel):
    """Request to create one project from metadata-filter criteria."""

    exchange: str = Field(default="", max_length=80)
    name: str = Field(default="", max_length=240)
    instrument_type: str = Field(default="", max_length=80)
    country: str = Field(default="", max_length=80)
    currency: str = Field(default="", max_length=80)


class SelectionCreateRequest(BaseModel):
    """Request to persist one user-owned selection."""

    project_id: str
    name: str = Field(min_length=1, max_length=120)
    member_ids: list[str] = Field(default_factory=list, min_length=1, max_length=1000)


class AnalysisCreateRequest(BaseModel):
    """Request to submit one analysis over an authorized selection."""

    project_id: str
    selection_id: str
    settings: JsonRow = Field(default_factory=dict)


class UnivariateRunRequest(BaseModel):
    """Immutable inputs for one univariate statistics run."""

    metadata_selection_id: str
    quote_run_id: str


class NumericalPredicateRequest(BaseModel):
    """One numerical filter predicate."""

    metric: str
    operator: str
    value: float


class UnivariateFilterRequest(BaseModel):
    """Predicates applied to one user-owned univariate run."""

    source_run_id: str
    selection_name: str | None = None
    predicates: list[NumericalPredicateRequest] = Field(min_length=1, max_length=100)


class BivariateSelectionRequest(BaseModel):
    """Source selection for pair planning and execution."""

    univariate_filter_selection_id: str


class LoadSelectedIsinsRequest(BaseModel):
    """Request to load quote data for one user-owned project selection."""

    project_id: str | None = None
    metadata_selection_id: str | None = None


class UserOwnedRow(Protocol):
    """Protocol for rows that are scoped to one hosted API user."""

    @property
    def user_id(self) -> str:
        """User that owns the row."""
        ...


@dataclass(frozen=True)
class ApiUser:
    """A server-resolved API user."""

    user_id: str


class CurrentUserProvider(Protocol):
    """Resolve the request principal without browser-controlled identity input."""

    def current_user(self) -> ApiUser:
        """Return the server-owned user for the current request."""

        ...


@dataclass(frozen=True)
class LocalWorkspaceUserProvider:
    """Resolve the stable single-user local-workspace principal."""

    user_id: str = DEFAULT_LOCAL_WORKSPACE_USER_ID

    def __post_init__(self) -> None:
        if not self.user_id.strip():
            raise ValueError("local workspace user id is required")

    def current_user(self) -> ApiUser:
        """Return the configured server-side local principal."""

        return ApiUser(user_id=self.user_id)


@dataclass(frozen=True)
class ProjectRecord:
    """User-owned project record."""

    project_id: str
    user_id: str
    name: str


@dataclass(frozen=True)
class SelectionRecord:
    """User-owned selection record."""

    selection_id: str
    user_id: str
    project_id: str
    name: str
    member_ids: tuple[str, ...]


@dataclass(frozen=True)
class AnalysisRecord:
    """User-owned analysis run record."""

    run_id: str
    user_id: str
    project_id: str
    selection_id: str
    logical_hash: str
    status: str
    metrics: tuple[JsonRow, ...]
    returns: tuple[JsonRow, ...]
    weights: tuple[JsonRow, ...]
    report: JsonRow


@dataclass
class HostedApiState:
    """In-memory hosted API repository set for deterministic tests and local dev."""

    credentials: CredentialStore = field(default_factory=InMemoryCredentialStore)
    credential_key_encryption_key: KeyEncryptionKey | None = field(
        default_factory=lambda: KeyEncryptionKey("dev-v1", b"0" * 32)
    )
    credential_fingerprint_secret: bytes = b"portfell-dev-fingerprint-secret"
    entitlements: InMemoryEntitlementStore = field(default_factory=InMemoryEntitlementStore)
    projects_by_id: dict[str, ProjectRecord] = field(
        default_factory=lambda: dict[str, ProjectRecord]()
    )
    selections_by_id: dict[str, SelectionRecord] = field(
        default_factory=lambda: dict[str, SelectionRecord]()
    )
    downloads_by_id: dict[str, ProviderDownloadRun] = field(
        default_factory=lambda: dict[str, ProviderDownloadRun]()
    )
    download_summaries_by_id: dict[str, JsonRow] = field(
        default_factory=lambda: dict[str, JsonRow]()
    )
    metadata_runs_by_id: dict[str, JsonRow] = field(default_factory=lambda: dict[str, JsonRow]())
    analyses_by_id: dict[str, AnalysisRecord] = field(
        default_factory=lambda: dict[str, AnalysisRecord]()
    )
    idempotency_refs: dict[tuple[str, str, str], str] = field(
        default_factory=lambda: dict[tuple[str, str, str], str]()
    )
    audit_events: list[JsonRow] = field(default_factory=lambda: list[JsonRow]())
    all_isins_rows: tuple[JsonRow, ...] = field(default_factory=tuple)
    univariate_statistics_rows: tuple[JsonRow, ...] = field(default_factory=tuple)
    metadata_revisions_by_user: dict[str, str] = field(default_factory=lambda: dict[str, str]())
    quote_rows_by_run_id: dict[str, tuple[JsonRow, ...]] = field(
        default_factory=lambda: dict[str, tuple[JsonRow, ...]]()
    )
    univariate_runs_by_id: dict[str, ResearchRun] = field(
        default_factory=lambda: dict[str, ResearchRun]()
    )
    filter_selections_by_id: dict[str, FilterSelection] = field(
        default_factory=lambda: dict[str, FilterSelection]()
    )
    bivariate_runs_by_id: dict[str, ResearchRun] = field(
        default_factory=lambda: dict[str, ResearchRun]()
    )
    quote_run_by_univariate_run_id: dict[str, str] = field(default_factory=lambda: dict[str, str]())
    current_metadata_selection_by_user: dict[str, str] = field(
        default_factory=lambda: dict[str, str]()
    )
    current_filter_selection_by_user: dict[str, str] = field(
        default_factory=lambda: dict[str, str]()
    )
    current_project_id_by_user: dict[str, str] = field(default_factory=lambda: dict[str, str]())
    workspace_store: LocalWorkspaceStore | None = None

    def credential_vault(self) -> EodhdCredentialVault:
        """Return the vault configured for this API state."""

        return EodhdCredentialVault(
            store=self.credentials,
            key_encryption_key=self.credential_key_encryption_key,
            fingerprint_secret=self.credential_fingerprint_secret,
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
    _restore_local_workspace(state, workspace_store.load())
    return state


def create_runtime_app() -> FastAPI:
    """Create the persistent container runtime application when secrets are configured."""

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
            Path(shared_data_root),
            key_encryption_key=key_encryption_key,
        )
    )


def create_app(
    state: HostedApiState | None = None,
    *,
    current_user_provider: CurrentUserProvider | None = None,
) -> FastAPI:
    """Create the hosted FastAPI application."""

    resolved_state = state or HostedApiState()
    resolved_user_provider = current_user_provider or LocalWorkspaceUserProvider(
        user_id=os.environ.get("PORTFELL_LOCAL_WORKSPACE_USER_ID", DEFAULT_LOCAL_WORKSPACE_USER_ID)
    )
    app = FastAPI(title="Portfell Hosted API", version="0.1.0")
    app.state.portfell_state = resolved_state

    def current_state() -> HostedApiState:
        return resolved_state

    def current_user() -> ApiUser:
        return resolved_user_provider.current_user()

    def workspace_user(user: ApiUser = Depends(current_user)) -> ApiUser:
        return user

    @app.get("/health")
    def health() -> JsonRow:
        return {"status": "ok"}

    @app.get("/workflow")
    def workflow(
        user: ApiUser = Depends(current_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        project = _current_project(api_state, user.user_id)
        return _workflow_row(
            api_state,
            user.user_id,
            None if project is None else project.project_id,
        )

    @app.get("/projects/{project_id}/workflow")
    def project_workflow(
        project_id: str,
        user: ApiUser = Depends(current_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        _require_user_row(api_state.projects_by_id, project_id, user.user_id)
        return _workflow_row(api_state, user.user_id, project_id)

    @app.get("/credentials/eodhd")
    def credential_status(
        user: ApiUser = Depends(current_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        try:
            return _credential_status_row(api_state.credential_vault().status(user_id=user.user_id))
        except Exception as error:
            raise _http_error(status.HTTP_404_NOT_FOUND, "credential_not_found") from error

    @app.get("/credentials/eodhd/value")
    def credential_value(
        user: ApiUser = Depends(workspace_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        try:
            provider_key = api_state.credential_vault().unwrap_for_provider_call(
                user_id=user.user_id
            )
            return {"provider_key": provider_key}
        except Exception as error:
            raise _http_error(status.HTTP_404_NOT_FOUND, "credential_not_found") from error

    @app.post("/credentials/eodhd")
    def set_credential(
        payload: CredentialSetRequest,
        user: ApiUser = Depends(workspace_user),
        api_state: HostedApiState = Depends(current_state),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JsonRow:
        cached = _idempotent_response(
            api_state,
            user_id=user.user_id,
            operation="set-credential",
            idempotency_key=idempotency_key,
        )
        if cached is not None:
            return credential_status(user, api_state)
        status_row = api_state.credential_vault().set_credential(
            user_id=user.user_id,
            provider_key=payload.provider_key,
        )
        _remember_idempotency(
            api_state,
            user.user_id,
            "set-credential",
            idempotency_key,
            status_row.credential_id,
        )
        _audit(api_state, user.user_id, "credential.set")
        return _credential_status_row(status_row)

    @app.delete("/credentials/eodhd")
    def delete_credential(
        user: ApiUser = Depends(workspace_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        try:
            status_row = api_state.credential_vault().delete(user_id=user.user_id)
        except Exception as error:
            raise _http_error(status.HTTP_404_NOT_FOUND, "credential_not_found") from error
        _audit(api_state, user.user_id, "credential.delete")
        return _credential_status_row(status_row)

    @app.post("/downloads/plan")
    def plan_download(
        payload: DownloadRequest,
        user: ApiUser = Depends(workspace_user),
    ) -> JsonRow:
        request_hash = _stable_hash({"user_id": user.user_id, "symbols": sorted(payload.symbols)})
        return {"download_run_id": _opaque_id("download-plan", request_hash), "status": "planned"}

    @app.post("/downloads/run")
    def run_download(
        payload: DownloadRequest,
        user: ApiUser = Depends(workspace_user),
        api_state: HostedApiState = Depends(current_state),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JsonRow:
        cached_run_id = _idempotent_response(
            api_state,
            user_id=user.user_id,
            operation="download-run",
            idempotency_key=idempotency_key,
        )
        if cached_run_id is not None:
            return _download_row(api_state.downloads_by_id[cached_run_id])
        observation_ids = tuple(
            _opaque_id("observation", symbol) for symbol in sorted(set(payload.symbols))
        )
        request_hash = _stable_hash({"user_id": user.user_id, "symbols": list(observation_ids)})
        run = ProviderDownloadRun(
            download_run_id=_opaque_id("download-run", request_hash),
            user_id=user.user_id,
            credential_id="credential-ref",
            provider="eodhd",
            status="succeeded",
            returned_observation_ids=observation_ids,
            request_hash=request_hash,
        )
        api_state.downloads_by_id[run.download_run_id] = run
        publish_user_data_snapshot(store=api_state.entitlements, run=run)
        _remember_idempotency(
            api_state, user.user_id, "download-run", idempotency_key, run.download_run_id
        )
        _audit(api_state, user.user_id, "download.run")
        return _download_row(run)

    @app.get("/downloads/{download_run_id}")
    def download_status(
        download_run_id: str,
        user: ApiUser = Depends(current_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        run = _require_user_row(api_state.downloads_by_id, download_run_id, user.user_id)
        return _download_row(run)

    @app.get("/datasets")
    def visible_datasets(
        user: ApiUser = Depends(current_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        observation_ids = api_state.entitlements.visible_observation_ids(user.user_id)
        return {
            "items": [
                {"dataset_id": observation_id, "dataset_type": "eodhd_observation"}
                for observation_id in observation_ids
            ]
        }

    @app.post("/projects")
    def create_project(
        payload: ProjectCreateRequest,
        user: ApiUser = Depends(workspace_user),
        api_state: HostedApiState = Depends(current_state),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JsonRow:
        cached_project_id = _idempotent_response(
            api_state,
            user_id=user.user_id,
            operation=f"project:{payload.name}",
            idempotency_key=idempotency_key,
        )
        if cached_project_id is not None:
            return _project_row(api_state.projects_by_id[cached_project_id])
        project_id = _opaque_id("project", f"{user.user_id}:{payload.name}")
        project = ProjectRecord(project_id=project_id, user_id=user.user_id, name=payload.name)
        api_state.projects_by_id.setdefault(project_id, project)
        _set_current_project(api_state, user.user_id, project_id)
        _remember_idempotency(
            api_state, user.user_id, f"project:{payload.name}", idempotency_key, project_id
        )
        _audit(api_state, user.user_id, "project.create")
        return _project_row(api_state.projects_by_id[project_id])

    @app.get("/projects")
    def list_projects(
        user: ApiUser = Depends(current_user),
        api_state: HostedApiState = Depends(current_state),
        limit: int = 100,
        offset: int = 0,
    ) -> JsonRow:
        _remove_discontinued_projects(api_state, user.user_id)
        items = [
            _project_with_selection_row(api_state, project, user.user_id)
            for project in _projects_for_user(api_state, user.user_id)
        ]
        return {"items": _page(items, limit=limit, offset=offset)}

    @app.get("/project-context")
    def project_context(
        user: ApiUser = Depends(current_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        return _project_context_row(api_state, user.user_id)

    @app.put("/project-context/current-project")
    def select_current_project(
        payload: CurrentProjectRequest,
        user: ApiUser = Depends(workspace_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        _set_current_project(api_state, user.user_id, payload.project_id)
        _audit(api_state, user.user_id, "project.current.select")
        return _project_context_row(api_state, user.user_id)

    @app.delete("/projects/{project_id}")
    def delete_project(
        project_id: str,
        user: ApiUser = Depends(workspace_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        _require_user_row(api_state.projects_by_id, project_id, user.user_id)
        api_state.projects_by_id.pop(project_id, None)
        api_state.selections_by_id = {
            row_id: row
            for row_id, row in api_state.selections_by_id.items()
            if row.project_id != project_id or row.user_id != user.user_id
        }
        api_state.analyses_by_id = {
            row_id: row
            for row_id, row in api_state.analyses_by_id.items()
            if row.project_id != project_id or row.user_id != user.user_id
        }
        if api_state.current_project_id_by_user.get(user.user_id) == project_id:
            api_state.current_project_id_by_user.pop(user.user_id, None)
            _current_project(api_state, user.user_id)
        _audit(api_state, user.user_id, "project.delete")
        return {"status": "deleted", "project_id": project_id}

    @app.get("/metadata-filter/options")
    def metadata_filter_options(
        user: ApiUser = Depends(current_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        _ = user
        rows = _all_isins_rows(api_state)
        return {
            "exchange": _distinct_options(rows, "exchange"),
            "instrument_type": _distinct_options(rows, "instrument_type"),
            "country": _distinct_options(rows, "country"),
            "currency": _distinct_options(rows, "currency"),
        }

    @app.post("/metadata/fetch-all")
    def fetch_all_metadata_for_metadata_filter(
        background_tasks: BackgroundTasks,
        user: ApiUser = Depends(workspace_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        try:
            provider_key = api_state.credential_vault().unwrap_for_provider_call(
                user_id=user.user_id
            )
        except CredentialVaultError as error:
            raise _http_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "eodhd_key_required"
            ) from error
        metadata_run_id = _opaque_id("metadata-run", f"{user.user_id}:{uuid.uuid4()}")
        api_state.metadata_runs_by_id[metadata_run_id] = {
            "metadata_run_id": metadata_run_id,
            "user_id": user.user_id,
            "status": "running",
            "total": 0,
            "completed": 0,
            "skipped_exchange_count": 0,
            "percent": 0,
        }
        background_tasks.add_task(
            _run_metadata_fetch,
            api_state,
            user.user_id,
            metadata_run_id,
            provider_key,
        )
        _audit(api_state, user.user_id, "fetch_all_metadata.started")
        return _metadata_fetch_row(api_state.metadata_runs_by_id[metadata_run_id])

    @app.get("/metadata/fetch-all/{metadata_run_id}")
    def metadata_fetch_status(
        metadata_run_id: str,
        user: ApiUser = Depends(workspace_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        metadata_run = api_state.metadata_runs_by_id.get(metadata_run_id)
        if metadata_run is None or metadata_run.get("user_id") != user.user_id:
            raise _http_error(status.HTTP_404_NOT_FOUND, "metadata_run_not_found")
        return _metadata_fetch_row(metadata_run)

    @app.post("/metadata-filter")
    def create_metadata_filter_project(
        payload: MetadataFilterProjectRequest,
        user: ApiUser = Depends(workspace_user),
        api_state: HostedApiState = Depends(current_state),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JsonRow:
        predicates = _metadata_filter_predicates(payload)
        if not predicates:
            raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "metadata_filter_required")
        selected_rows = filter_rows(_all_isins_rows(api_state), predicates)
        if not selected_rows:
            raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "metadata_filter_empty")
        project_name = _metadata_filter_project_name(payload)
        cached_project_id = _idempotent_response(
            api_state,
            user_id=user.user_id,
            operation=f"metadata-filter-project:{project_name}",
            idempotency_key=idempotency_key,
        )
        if cached_project_id is not None:
            project = api_state.projects_by_id[cached_project_id]
            selection = _selection_for_project(api_state, project.project_id, user.user_id)
            _set_current_project(api_state, user.user_id, project.project_id)
            return _metadata_filter_project_row(project, selection, len(selected_rows))
        project_id = _opaque_id("project", f"{user.user_id}:{project_name}")
        project = ProjectRecord(project_id=project_id, user_id=user.user_id, name=project_name)
        api_state.projects_by_id.setdefault(project_id, project)
        member_ids = tuple(
            sorted(
                {
                    f"{row['isin']}:{row['exchange']}:{row['code']}"
                    for row in selected_rows
                    if row.get("isin") and row.get("exchange") and row.get("code")
                }
            )
        )
        selection_id = _opaque_id(
            "selection", f"{user.user_id}:{project_id}:{project_name}:{member_ids}"
        )
        selection = SelectionRecord(
            selection_id=selection_id,
            user_id=user.user_id,
            project_id=project_id,
            name=project_name,
            member_ids=member_ids,
        )
        api_state.selections_by_id.setdefault(selection_id, selection)
        api_state.current_metadata_selection_by_user[user.user_id] = selection_id
        api_state.current_filter_selection_by_user.pop(user.user_id, None)
        _set_current_project(api_state, user.user_id, project_id)
        _write_hosted_metadata_selection(selection_id, selected_rows, predicates)
        _remember_idempotency(
            api_state,
            user.user_id,
            f"metadata-filter-project:{project_name}",
            idempotency_key,
            project_id,
        )
        _audit(api_state, user.user_id, "metadata_filter.project.create")
        return _metadata_filter_project_row(
            api_state.projects_by_id[project_id],
            api_state.selections_by_id[selection_id],
            len(selected_rows),
        )

    @app.post("/selections")
    def create_selection(
        payload: SelectionCreateRequest,
        user: ApiUser = Depends(workspace_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        _require_user_row(api_state.projects_by_id, payload.project_id, user.user_id)
        member_ids = tuple(sorted(set(payload.member_ids)))
        selection_id = _opaque_id(
            "selection", f"{user.user_id}:{payload.project_id}:{payload.name}:{member_ids}"
        )
        selection = SelectionRecord(
            selection_id=selection_id,
            user_id=user.user_id,
            project_id=payload.project_id,
            name=payload.name,
            member_ids=member_ids,
        )
        api_state.selections_by_id.setdefault(selection_id, selection)
        _audit(api_state, user.user_id, "selection.create")
        return _selection_row(api_state.selections_by_id[selection_id])

    @app.get("/selections/{selection_id}")
    def selection_detail(
        selection_id: str,
        user: ApiUser = Depends(current_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        return _selection_row(
            _require_user_row(api_state.selections_by_id, selection_id, user.user_id)
        )

    @app.post("/quote-runs")
    def load_selected_isins(
        payload: LoadSelectedIsinsRequest,
        background_tasks: BackgroundTasks,
        user: ApiUser = Depends(workspace_user),
        api_state: HostedApiState = Depends(current_state),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JsonRow:
        if payload.metadata_selection_id is not None:
            selection = _require_user_row(
                api_state.selections_by_id, payload.metadata_selection_id, user.user_id
            )
            project_id = selection.project_id
        elif payload.project_id is not None:
            project_id = payload.project_id
            _require_user_row(api_state.projects_by_id, project_id, user.user_id)
            selection = _selection_for_project(api_state, project_id, user.user_id)
        else:
            raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "metadata_selection_required")
        cached_run_id = _idempotent_response(
            api_state,
            user_id=user.user_id,
            operation=f"fetch-all-quotes:{project_id}",
            idempotency_key=idempotency_key,
        )
        if cached_run_id is not None:
            return _load_selected_isins_row(
                api_state.downloads_by_id[cached_run_id],
                summary=api_state.download_summaries_by_id.get(cached_run_id),
            )
        request_hash = _stable_hash(
            {
                "project_id": project_id,
                "selection_id": selection.selection_id,
                "member_ids": list(selection.member_ids),
            }
        )
        try:
            provider_key = api_state.credential_vault().unwrap_for_provider_call(
                user_id=user.user_id
            )
        except CredentialVaultError as error:
            raise _http_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "eodhd_credential_required"
            ) from error
        run = ProviderDownloadRun(
            download_run_id=_opaque_id("fetch-all-quotes", f"{user.user_id}:{request_hash}"),
            user_id=user.user_id,
            credential_id="project-selection",
            provider="eodhd",
            status="running",
            returned_observation_ids=selection.member_ids,
            request_hash=request_hash,
        )
        api_state.downloads_by_id[run.download_run_id] = run
        api_state.download_summaries_by_id[run.download_run_id] = {
            "total": len(selection.member_ids) * 3 + 1,
            "completed": 0,
            "failed": 0,
            "percent": 0,
            "progress": 0,
            "selected_listing_count": len(selection.member_ids),
        }
        _remember_idempotency(
            api_state,
            user.user_id,
            f"fetch-all-quotes:{project_id}",
            idempotency_key,
            run.download_run_id,
        )
        background_tasks.add_task(
            _run_quote_fetch,
            api_state,
            run,
            selection.selection_id,
            provider_key,
        )
        _audit(api_state, user.user_id, "fetch_all_quotes.started")
        return _load_selected_isins_row(
            run, summary=api_state.download_summaries_by_id[run.download_run_id]
        )

    @app.get("/quote-runs/{quote_run_id}")
    def quote_run_status(
        quote_run_id: str,
        user: ApiUser = Depends(current_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        run = _require_user_row(api_state.downloads_by_id, quote_run_id, user.user_id)
        return _load_selected_isins_row(
            run,
            summary=api_state.download_summaries_by_id.get(quote_run_id),
        )

    @app.post("/univariate-statistics/runs")
    def start_univariate_run(
        payload: UnivariateRunRequest,
        user: ApiUser = Depends(workspace_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        selection = _require_user_row(
            api_state.selections_by_id, payload.metadata_selection_id, user.user_id
        )
        quote_run = _require_user_row(api_state.downloads_by_id, payload.quote_run_id, user.user_id)
        if quote_run.status != "succeeded":
            raise _http_error(status.HTTP_409_CONFLICT, "quote_run_incomplete")
        quote_rows = api_state.quote_rows_by_run_id.get(quote_run.download_run_id)
        if quote_rows is None:
            raise _http_error(status.HTTP_409_CONFLICT, "scoped_quote_rows_unavailable")
        run = create_univariate_run(
            user_id=user.user_id,
            selection_id=selection.selection_id,
            quote_run_id=quote_run.download_run_id,
            quote_rows=quote_rows,
        )
        api_state.univariate_runs_by_id.setdefault(run.run_id, run)
        api_state.quote_run_by_univariate_run_id.setdefault(run.run_id, quote_run.download_run_id)
        return _research_run_row(api_state.univariate_runs_by_id[run.run_id])

    @app.get("/univariate-statistics/runs/{run_id}")
    def univariate_run_status(
        run_id: str,
        user: ApiUser = Depends(current_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        return _research_run_row(
            _require_user_row(api_state.univariate_runs_by_id, run_id, user.user_id)
        )

    @app.get("/univariate-statistics/runs/{run_id}/results")
    def univariate_run_results(
        run_id: str,
        user: ApiUser = Depends(current_user),
        api_state: HostedApiState = Depends(current_state),
        limit: int = 50,
        offset: int = 0,
    ) -> JsonRow:
        run = _require_user_row(api_state.univariate_runs_by_id, run_id, user.user_id)
        return page_rows(run.rows, limit=limit, offset=offset)

    @app.get("/univariate-filter/metrics")
    def univariate_filter_metrics(
        user: ApiUser = Depends(current_user),
    ) -> JsonRow:
        _ = user
        return {"items": _univariate_metric_rows()}

    @app.post("/univariate-filter")
    def apply_univariate_filter(
        payload: UnivariateFilterRequest,
        user: ApiUser = Depends(workspace_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        source_run = _require_user_row(
            api_state.univariate_runs_by_id, payload.source_run_id, user.user_id
        )
        try:
            selection = create_filter_selection(
                user_id=user.user_id,
                run=source_run,
                predicate_rows=[predicate.model_dump() for predicate in payload.predicates],
            )
        except HostedResearchError as error:
            raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
        api_state.filter_selections_by_id.setdefault(selection.selection_id, selection)
        api_state.current_filter_selection_by_user[user.user_id] = selection.selection_id
        return _filter_selection_row(api_state.filter_selections_by_id[selection.selection_id])

    @app.get("/univariate-filter/{selection_id}/results")
    def univariate_filter_results(
        selection_id: str,
        user: ApiUser = Depends(current_user),
        api_state: HostedApiState = Depends(current_state),
        limit: int = 50,
        offset: int = 0,
    ) -> JsonRow:
        selection = _require_user_row(api_state.filter_selections_by_id, selection_id, user.user_id)
        return page_rows(selection.rows, limit=limit, offset=offset)

    @app.post("/bivariate-statistics/plan")
    def bivariate_plan(
        payload: BivariateSelectionRequest,
        user: ApiUser = Depends(workspace_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        selection = _require_user_row(
            api_state.filter_selections_by_id,
            payload.univariate_filter_selection_id,
            user.user_id,
        )
        return pair_plan(selection)

    @app.post("/bivariate-statistics/runs")
    def start_bivariate_run(
        payload: BivariateSelectionRequest,
        user: ApiUser = Depends(workspace_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        selection = _require_user_row(
            api_state.filter_selections_by_id,
            payload.univariate_filter_selection_id,
            user.user_id,
        )
        source_run = _require_user_row(
            api_state.univariate_runs_by_id, selection.source_run_id, user.user_id
        )
        quote_run_id = api_state.quote_run_by_univariate_run_id.get(source_run.run_id, "")
        quote_rows = api_state.quote_rows_by_run_id.get(quote_run_id)
        if quote_rows is None:
            raise _http_error(status.HTTP_409_CONFLICT, "scoped_quote_rows_unavailable")
        try:
            run = create_bivariate_run(
                user_id=user.user_id, selection=selection, quote_rows=quote_rows
            )
        except HostedResearchError as error:
            raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
        api_state.bivariate_runs_by_id.setdefault(run.run_id, run)
        return _research_run_row(api_state.bivariate_runs_by_id[run.run_id])

    @app.get("/bivariate-statistics/runs/{run_id}")
    def bivariate_run_status(
        run_id: str,
        user: ApiUser = Depends(current_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        return _research_run_row(
            _require_user_row(api_state.bivariate_runs_by_id, run_id, user.user_id)
        )

    @app.get("/bivariate-statistics/runs/{run_id}/results")
    def bivariate_run_results(
        run_id: str,
        user: ApiUser = Depends(current_user),
        api_state: HostedApiState = Depends(current_state),
        limit: int = 50,
        offset: int = 0,
    ) -> JsonRow:
        run = _require_user_row(api_state.bivariate_runs_by_id, run_id, user.user_id)
        return page_rows(run.rows, limit=limit, offset=offset)

    @app.post("/analyses")
    def create_analysis(
        payload: AnalysisCreateRequest,
        user: ApiUser = Depends(workspace_user),
        api_state: HostedApiState = Depends(current_state),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JsonRow:
        selection = _require_user_row(
            api_state.selections_by_id, payload.selection_id, user.user_id
        )
        _require_user_row(api_state.projects_by_id, payload.project_id, user.user_id)
        logical_hash = _stable_hash(
            {
                "selection_id": selection.selection_id,
                "member_ids": list(selection.member_ids),
                "settings": payload.settings,
            }
        )
        cached_run_id = _idempotent_response(
            api_state,
            user_id=user.user_id,
            operation="analysis",
            idempotency_key=idempotency_key,
        )
        cache_hit = cached_run_id is not None
        if cached_run_id is not None:
            return {**_analysis_row(api_state.analyses_by_id[cached_run_id]), "cache_hit": True}
        run_id = _opaque_id("analysis", f"{user.user_id}:{logical_hash}")
        analysis = AnalysisRecord(
            run_id=run_id,
            user_id=user.user_id,
            project_id=payload.project_id,
            selection_id=selection.selection_id,
            logical_hash=logical_hash,
            status="succeeded",
            metrics=({"name": "selection_size", "value": len(selection.member_ids)},),
            returns=tuple(
                {"member_id": member_id, "return": 0.0} for member_id in selection.member_ids
            ),
            weights=tuple(
                {"member_id": member_id, "weight": 1 / len(selection.member_ids)}
                for member_id in selection.member_ids
            ),
            report={"summary": "deterministic hosted analysis placeholder"},
        )
        api_state.analyses_by_id[run_id] = analysis
        _remember_idempotency(api_state, user.user_id, "analysis", idempotency_key, run_id)
        _audit(api_state, user.user_id, "analysis.create")
        return {**_analysis_row(analysis), "cache_hit": cache_hit}

    @app.get("/analyses/{run_id}")
    def analysis_status(
        run_id: str,
        user: ApiUser = Depends(current_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        return _analysis_row(_require_user_row(api_state.analyses_by_id, run_id, user.user_id))

    @app.get("/analyses/{run_id}/metrics")
    def analysis_metrics(
        run_id: str,
        user: ApiUser = Depends(current_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        analysis = _require_user_row(api_state.analyses_by_id, run_id, user.user_id)
        return {"items": list(analysis.metrics)}

    @app.get("/analyses/{run_id}/returns")
    def analysis_returns(
        run_id: str,
        user: ApiUser = Depends(current_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        analysis = _require_user_row(api_state.analyses_by_id, run_id, user.user_id)
        return {"items": list(analysis.returns)}

    @app.get("/analyses/{run_id}/weights")
    def analysis_weights(
        run_id: str,
        user: ApiUser = Depends(current_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        analysis = _require_user_row(api_state.analyses_by_id, run_id, user.user_id)
        return {"items": list(analysis.weights)}

    @app.get("/analyses/{run_id}/report")
    def analysis_report(
        run_id: str,
        user: ApiUser = Depends(current_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        analysis = _require_user_row(api_state.analyses_by_id, run_id, user.user_id)
        return analysis.report

    @app.delete("/account")
    def delete_account(
        user: ApiUser = Depends(workspace_user),
        api_state: HostedApiState = Depends(current_state),
    ) -> JsonRow:
        delete_user_entitlements(store=api_state.entitlements, user_id=user.user_id)
        api_state.projects_by_id = {
            row_id: row
            for row_id, row in api_state.projects_by_id.items()
            if row.user_id != user.user_id
        }
        api_state.selections_by_id = {
            row_id: row
            for row_id, row in api_state.selections_by_id.items()
            if row.user_id != user.user_id
        }
        api_state.analyses_by_id = {
            row_id: row
            for row_id, row in api_state.analyses_by_id.items()
            if row.user_id != user.user_id
        }
        _audit(api_state, user.user_id, "account.delete")
        return {"status": "deleted"}

    return app


def _lake_paths() -> LakePaths:
    return LakePaths(root=Path(os.environ.get("PORTFELL_LAKE_ROOT", "lake")))


def _all_isins_rows(state: HostedApiState) -> tuple[JsonRow, ...]:
    if state.all_isins_rows:
        return state.all_isins_rows
    return tuple(read_rows(_lake_paths().all_isins()))


def _write_hosted_metadata_selection(
    selection_id: str,
    selected_rows: Iterable[Mapping[str, Any]],
    predicates: tuple[Predicate, ...],
) -> None:
    if "PORTFELL_LAKE_ROOT" not in os.environ:
        return
    paths = _lake_paths()
    write_metadata_selection(
        paths,
        selection_id,
        tuple(selected_rows),
        predicates=predicates,
        source_path=str(paths.all_isins()),
    )


def _distinct_options(rows: tuple[JsonRow, ...], field: str) -> list[str]:
    return sorted(
        {str(row.get(field, "")).strip() for row in rows if str(row.get(field, "")).strip()}
    )


def _metadata_filter_predicates(payload: MetadataFilterProjectRequest) -> tuple[Predicate, ...]:
    predicates: list[Predicate] = []
    if payload.exchange.strip():
        predicates.append(Predicate("exchange", "=", payload.exchange.strip()))
    if payload.name.strip():
        predicates.append(Predicate("name", "~", payload.name.strip()))
    if payload.instrument_type.strip():
        predicates.append(Predicate("instrument_type", "=", payload.instrument_type.strip()))
    if payload.country.strip():
        predicates.append(Predicate("country", "=", payload.country.strip()))
    if payload.currency.strip():
        predicates.append(Predicate("currency", "=", payload.currency.strip()))
    return tuple(predicates)


def _metadata_filter_project_name(payload: MetadataFilterProjectRequest) -> str:
    parts = [
        _project_name_part(payload.exchange),
        _project_name_part(payload.name),
        _project_name_part(payload.instrument_type),
        _project_name_part(payload.country),
        _project_name_part(payload.currency),
    ]
    normalized = [part for part in parts if part]
    return "_".join(normalized) or "metadata_filter_project"


def _project_name_part(value: str) -> str:
    return "_".join(str(value).strip().casefold().split())


def _selection_for_project(state: HostedApiState, project_id: str, user_id: str) -> SelectionRecord:
    for selection in state.selections_by_id.values():
        if selection.project_id == project_id and selection.user_id == user_id:
            return selection
    raise _http_error(status.HTTP_404_NOT_FOUND, "not_found")


def _workflow_selection(state: HostedApiState, user_id: str) -> SelectionRecord | None:
    """Choose a stable current selection without examining unrestricted lake data."""

    current_selection_id = state.current_metadata_selection_by_user.get(user_id)
    if current_selection_id is not None:
        selection = state.selections_by_id.get(current_selection_id)
        if selection is not None and selection.user_id == user_id:
            return selection
    if user_id in state.metadata_revisions_by_user:
        return None
    selections = sorted(
        (
            selection
            for selection in state.selections_by_id.values()
            if selection.user_id == user_id
        ),
        key=lambda selection: (selection.project_id, selection.selection_id),
    )
    return selections[0] if selections else None


def _quote_run_id_for_project(state: HostedApiState, project_id: str, user_id: str) -> str | None:
    operation = f"fetch-all-quotes:{project_id}"
    run_ids = sorted(
        run_id
        for (stored_user_id, stored_operation, _), run_id in state.idempotency_refs.items()
        if stored_user_id == user_id
        and stored_operation == operation
        and state.downloads_by_id.get(run_id, None) is not None
        and state.downloads_by_id[run_id].status == "succeeded"
    )
    return run_ids[0] if run_ids else None


def _univariate_run_for_quote(
    state: HostedApiState, quote_run_id: str | None, user_id: str
) -> ResearchRun | None:
    run_ids = sorted(
        run_id
        for run_id, stored_quote_run_id in state.quote_run_by_univariate_run_id.items()
        if stored_quote_run_id == quote_run_id
        and run_id in state.univariate_runs_by_id
        and state.univariate_runs_by_id[run_id].user_id == user_id
    )
    return state.univariate_runs_by_id[run_ids[0]] if run_ids else None


def _filter_selection_for_run(
    state: HostedApiState, run_id: str | None, user_id: str
) -> FilterSelection | None:
    current_selection_id = state.current_filter_selection_by_user.get(user_id)
    if current_selection_id is not None:
        selection = state.filter_selections_by_id.get(current_selection_id)
        if selection is not None and selection.source_run_id == run_id:
            return selection
    selection_ids = sorted(
        selection.selection_id
        for selection in state.filter_selections_by_id.values()
        if selection.source_run_id == run_id and selection.user_id == user_id
    )
    return state.filter_selections_by_id[selection_ids[0]] if selection_ids else None


def _bivariate_run_for_selection(
    state: HostedApiState, selection_id: str | None, user_id: str
) -> ResearchRun | None:
    runs = sorted(
        (
            run
            for run in state.bivariate_runs_by_id.values()
            if run.user_id == user_id
            and selection_id is not None
            and run.source_id
            == _stable_hash(
                {
                    "selection_id": selection_id,
                    "members": list(state.filter_selections_by_id[selection_id].member_ids),
                }
            )
        ),
        key=lambda run: run.run_id,
    )
    return runs[0] if runs else None


def _metadata_filter_project_row(
    project: ProjectRecord, selection: SelectionRecord, selected_count: int
) -> JsonRow:
    return {
        "project": _project_row(project),
        "selection": _selection_row(selection),
        "selected_count": selected_count,
    }


def _credential_status_row(status_row: CredentialStatus) -> JsonRow:
    return {
        "credential_id": status_row.credential_id,
        "provider": status_row.provider,
        "status": status_row.status,
        "key_version": status_row.key_version,
        "masked_label": status_row.masked_label,
    }


def _research_run_row(run: ResearchRun) -> JsonRow:
    percent = 100 if run.total == 0 else int(((run.completed + run.failed) / run.total) * 100)
    return {
        "run_id": run.run_id,
        "status": run.status,
        "total": run.total,
        "completed": run.completed,
        "failed": run.failed,
        "percent": percent,
    }


def _filter_selection_row(selection: FilterSelection) -> JsonRow:
    selected_count = len(selection.rows)
    return {
        "selection_id": selection.selection_id,
        "source_run_id": selection.source_run_id,
        "input_count": selection.input_count,
        "selected_count": selected_count,
        "excluded_count": selection.input_count - selected_count,
        "predicates": [
            {
                "metric": predicate.field,
                "operator": predicate.operator,
                "value": float(predicate.expected),
            }
            for predicate in selection.predicates
        ],
    }


def _univariate_metric_rows() -> list[JsonRow]:
    labels = {
        "quote_observation_count": ("Observations", "count"),
        "annualized_return": ("Annualized return", "ratio"),
        "annualized_volatility": ("Annualized volatility", "ratio"),
        "sharpe_ratio": ("Sharpe ratio", "ratio"),
        "max_drawdown": ("Maximum drawdown", "ratio"),
        "expected_shortfall": ("Expected shortfall", "ratio"),
    }
    return [
        {
            "metric": metric,
            "label": label,
            "unit": unit,
            "operators": ["=", "!=", ">", ">=", "<", "<="],
        }
        for metric, (label, unit) in labels.items()
    ]


def _download_row(run: ProviderDownloadRun) -> JsonRow:
    return {
        "download_run_id": run.download_run_id,
        "provider": run.provider,
        "status": run.status,
        "observation_count": len(run.returned_observation_ids),
    }


def _run_quote_fetch(
    state: HostedApiState,
    run: ProviderDownloadRun,
    selection_id: str,
    provider_key: str,
) -> None:
    def update_progress(completed: int, total: int, failed: int) -> None:
        percent = min(99, round((completed / total) * 100)) if total else 0
        state.download_summaries_by_id[run.download_run_id] = {
            **state.download_summaries_by_id[run.download_run_id],
            "completed": completed,
            "failed": failed,
            "percent": percent,
            "progress": percent,
            "total": total,
        }

    try:
        summary = run_fetch_all_quotes_workflow(
            root=_lake_paths().root,
            run_id=_opaque_id("fetch-all-quotes", run.request_hash),
            selection_id=selection_id,
            concurrency=2,
            eodhd_config=EodhdConfig(api_token=provider_key),
            capture_scoped_rows=True,
            on_progress=update_progress,
        )
    except Exception:
        state.downloads_by_id[run.download_run_id] = replace(run, status="failed")
        state.download_summaries_by_id[run.download_run_id] = {
            **state.download_summaries_by_id[run.download_run_id],
            "percent": 0,
            "progress": 0,
        }
        _audit(state, run.user_id, "fetch_all_quotes.failed")
        return

    scoped_quote_rows = tuple(dict(row) for row in summary.pop("scoped_quote_rows", ()))
    completed = int(state.download_summaries_by_id[run.download_run_id]["completed"])
    total = int(state.download_summaries_by_id[run.download_run_id]["total"])
    failed = int(state.download_summaries_by_id[run.download_run_id]["failed"])
    completed_run = replace(run, status="partial" if failed else "succeeded")
    state.downloads_by_id[run.download_run_id] = completed_run
    state.quote_rows_by_run_id[run.download_run_id] = scoped_quote_rows
    state.download_summaries_by_id[run.download_run_id] = {
        **summary,
        "completed": completed,
        "failed": failed,
        "percent": 100,
        "progress": 100,
        "total": total,
    }
    if completed_run.status == "succeeded":
        publish_user_data_snapshot(store=state.entitlements, run=completed_run)
    _audit(state, run.user_id, "fetch_all_quotes.completed")


def _run_metadata_fetch(
    state: HostedApiState,
    user_id: str,
    metadata_run_id: str,
    provider_key: str,
) -> None:
    def update_progress(completed: int, total: int, skipped: int) -> None:
        percent = round((completed / total) * 100) if total else 0
        state.metadata_runs_by_id[metadata_run_id] = {
            **state.metadata_runs_by_id[metadata_run_id],
            "completed": completed,
            "total": total,
            "skipped_exchange_count": skipped,
            "percent": percent,
        }

    try:
        summary = run_fetch_all_metadata_workflow(
            root=_lake_paths().root,
            eodhd_config=EodhdConfig(api_token=provider_key),
            on_progress=update_progress,
        )
    except EodhdHttpError as error:
        error_code = (
            "eodhd_key_rejected"
            if error.status_code in {401, 403}
            else "eodhd_metadata_unavailable"
        )
        state.metadata_runs_by_id[metadata_run_id] = {
            **state.metadata_runs_by_id[metadata_run_id],
            "status": "failed",
            "error_code": error_code,
        }
        _audit(state, user_id, "fetch_all_metadata.failed")
        return
    except ValueError:
        state.metadata_runs_by_id[metadata_run_id] = {
            **state.metadata_runs_by_id[metadata_run_id],
            "status": "failed",
            "error_code": "eodhd_metadata_invalid_response",
        }
        _audit(state, user_id, "fetch_all_metadata.failed")
        return
    except Exception:
        state.metadata_runs_by_id[metadata_run_id] = {
            **state.metadata_runs_by_id[metadata_run_id],
            "status": "failed",
            "error_code": "metadata_fetch_failed",
        }
        _audit(state, user_id, "fetch_all_metadata.failed")
        return

    state.metadata_revisions_by_user[user_id] = _opaque_id(
        "metadata-revision", _stable_hash(summary)
    )
    state.current_metadata_selection_by_user.pop(user_id, None)
    state.current_filter_selection_by_user.pop(user_id, None)
    state.metadata_runs_by_id[metadata_run_id] = {
        **state.metadata_runs_by_id[metadata_run_id],
        "status": "succeeded",
        "row_count": int(summary["all_isins_rows"]),
        "exchange_count": int(summary["exchange_count"]),
        "requested_exchange_count": int(summary["requested_exchange_count"]),
        "skipped_exchange_count": int(summary["skipped_exchange_count"]),
        "skipped_exchanges": list(summary["skipped_exchanges"]),
        "percent": 100,
    }
    _audit(state, user_id, "fetch_all_metadata.completed")


def _metadata_fetch_row(metadata_run: Mapping[str, Any]) -> JsonRow:
    return {key: value for key, value in metadata_run.items() if key != "user_id"}


def _load_selected_isins_row(
    run: ProviderDownloadRun,
    *,
    summary: Mapping[str, Any] | None = None,
) -> JsonRow:
    workflow_summary = dict(summary or {})
    total = int(workflow_summary.get("total", len(run.returned_observation_ids)))
    completed = int(workflow_summary.get("completed", workflow_summary.get("quote_successes", 0)))
    failed = int(workflow_summary.get("failed", workflow_summary.get("quote_errors", 0)))
    percent = int(workflow_summary.get("percent", 100 if run.status == "succeeded" else 0))
    return {
        **_download_row(run),
        "kind": "load-data",
        "total": total,
        "completed": completed,
        "failed": failed,
        "percent": percent,
        "progress": percent,
        "quote_errors": int(workflow_summary.get("quote_errors", 0)),
        "quote_successes": int(workflow_summary.get("quote_successes", 0)),
        "raw_dataset_errors": int(workflow_summary.get("raw_dataset_errors", 0)),
        "raw_dataset_successes": int(workflow_summary.get("raw_dataset_successes", 0)),
        "run_id": run.download_run_id,
        "selected_listing_count": int(
            workflow_summary.get("selected_listing_count", len(run.returned_observation_ids))
        ),
        "selected_count": len(run.returned_observation_ids),
        "silver_quote_rows": int(workflow_summary.get("silver_quote_rows", 0)),
    }


def _project_row(project: ProjectRecord) -> JsonRow:
    return {"project_id": project.project_id, "name": project.name}


def _projects_for_user(state: HostedApiState, user_id: str) -> list[ProjectRecord]:
    return sorted(
        (project for project in state.projects_by_id.values() if project.user_id == user_id),
        key=lambda project: (project.name.casefold(), project.project_id),
    )


def _current_project(state: HostedApiState, user_id: str) -> ProjectRecord | None:
    project_id = state.current_project_id_by_user.get(user_id)
    project = state.projects_by_id.get(project_id) if project_id is not None else None
    if project is not None and project.user_id == user_id:
        return project
    projects = _projects_for_user(state, user_id)
    if not projects:
        state.current_project_id_by_user.pop(user_id, None)
        return None
    state.current_project_id_by_user[user_id] = projects[0].project_id
    return projects[0]


def _set_current_project(state: HostedApiState, user_id: str, project_id: str) -> None:
    _require_user_row(state.projects_by_id, project_id, user_id)
    state.current_project_id_by_user[user_id] = project_id


def _project_context_row(state: HostedApiState, user_id: str) -> JsonRow:
    _remove_discontinued_projects(state, user_id)
    project = _current_project(state, user_id)
    projects = [
        _project_with_selection_row(state, item, user_id)
        for item in _projects_for_user(state, user_id)
    ]
    current = None if project is None else _project_with_selection_row(state, project, user_id)
    return {
        "current_project_id": None if project is None else project.project_id,
        "current_project": current,
        "projects": projects,
    }


def _workflow_row(state: HostedApiState, user_id: str, project_id: str | None) -> JsonRow:
    if project_id is None:
        return {
            "stages": resolve_workflow(
                metadata_revision_id=None,
                metadata_selection_id=None,
                quote_run_id=None,
            )
        }
    selection = next(
        (
            selection
            for selection in state.selections_by_id.values()
            if selection.project_id == project_id and selection.user_id == user_id
        ),
        None,
    )
    if selection is None:
        return {
            "stages": resolve_workflow(
                metadata_revision_id=None,
                metadata_selection_id=None,
                quote_run_id=None,
            )
        }
    quote_run_id = _quote_run_id_for_project(state, project_id, user_id)
    metadata_revision_id = state.metadata_revisions_by_user.get(
        user_id,
        _opaque_id("metadata-revision", selection.selection_id),
    )
    univariate_run = _univariate_run_for_quote(state, quote_run_id, user_id)
    filter_selection = _filter_selection_for_run(
        state, None if univariate_run is None else univariate_run.run_id, user_id
    )
    bivariate_run = _bivariate_run_for_selection(
        state, None if filter_selection is None else filter_selection.selection_id, user_id
    )
    return {
        "stages": resolve_workflow(
            metadata_revision_id=metadata_revision_id,
            metadata_selection_id=selection.selection_id,
            quote_run_id=quote_run_id,
            univariate_run_id=None if univariate_run is None else univariate_run.run_id,
            univariate_filter_selection_id=(
                None if filter_selection is None else filter_selection.selection_id
            ),
            bivariate_run_id=None if bivariate_run is None else bivariate_run.run_id,
        )
    }


def _remove_discontinued_projects(state: HostedApiState, user_id: str) -> None:
    project_ids = {
        project_id
        for project_id, project in state.projects_by_id.items()
        if project.user_id == user_id and project.name in REMOVED_PROJECT_NAMES
    }
    if not project_ids:
        return
    state.projects_by_id = {
        project_id: project
        for project_id, project in state.projects_by_id.items()
        if project_id not in project_ids
    }
    state.selections_by_id = {
        selection_id: selection
        for selection_id, selection in state.selections_by_id.items()
        if selection.project_id not in project_ids or selection.user_id != user_id
    }
    state.analyses_by_id = {
        analysis_id: analysis
        for analysis_id, analysis in state.analyses_by_id.items()
        if analysis.project_id not in project_ids or analysis.user_id != user_id
    }


def _project_with_selection_row(
    state: HostedApiState, project: ProjectRecord, user_id: str
) -> JsonRow:
    try:
        selection = _selection_for_project(state, project.project_id, user_id)
    except HTTPException:
        return {**_project_row(project), "selected_count": 0, "data_loaded": False}
    return {
        **_project_row(project),
        "selection_id": selection.selection_id,
        "selected_count": len(selection.member_ids),
        "data_loaded": _project_data_loaded(state, project.project_id, user_id),
    }


def _project_data_loaded(state: HostedApiState, project_id: str, user_id: str) -> bool:
    operation_prefix = f"fetch-all-quotes:{project_id}"
    for (
        stored_user_id,
        operation,
        _idempotency_key,
    ), download_run_id in state.idempotency_refs.items():
        if stored_user_id != user_id or operation != operation_prefix:
            continue
        run = state.downloads_by_id.get(download_run_id)
        if run is not None and run.status == "succeeded":
            return True
    return False


def _selection_row(selection: SelectionRecord) -> JsonRow:
    return {
        "selection_id": selection.selection_id,
        "project_id": selection.project_id,
        "name": selection.name,
        "member_ids": list(selection.member_ids),
    }


def _analysis_row(analysis: AnalysisRecord) -> JsonRow:
    return {
        "run_id": analysis.run_id,
        "project_id": analysis.project_id,
        "selection_id": analysis.selection_id,
        "status": analysis.status,
    }


def _require_user_row[UserOwnedRowT: UserOwnedRow](
    rows: Mapping[str, UserOwnedRowT],
    row_id: str,
    user_id: str,
) -> UserOwnedRowT:
    row = rows.get(row_id)
    if row is None or row.user_id != user_id:
        raise _http_error(status.HTTP_404_NOT_FOUND, "not_found")
    return row


def _page(items: list[JsonRow], *, limit: int, offset: int) -> list[JsonRow]:
    if limit < 1 or limit > 500:
        raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_limit")
    if offset < 0:
        raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_offset")
    return items[offset : offset + limit]


def _idempotent_response(
    state: HostedApiState, *, user_id: str, operation: str, idempotency_key: str | None
) -> str | None:
    if idempotency_key is None:
        return None
    return state.idempotency_refs.get((user_id, operation, idempotency_key))


def _remember_idempotency(
    state: HostedApiState,
    user_id: str,
    operation: str,
    idempotency_key: str | None,
    row_id: str,
) -> None:
    if idempotency_key is not None:
        state.idempotency_refs[(user_id, operation, idempotency_key)] = row_id


def _audit(state: HostedApiState, user_id: str, action: str) -> None:
    state.audit_events.append({"user_id": user_id, "action": action})
    _persist_local_workspace(state)


def _persist_local_workspace(state: HostedApiState) -> None:
    if state.workspace_store is None:
        return
    state.workspace_store.save(
        {
            "projects": [
                {"project_id": project.project_id, "user_id": project.user_id, "name": project.name}
                for project in state.projects_by_id.values()
            ],
            "selections": [
                {
                    "selection_id": selection.selection_id,
                    "user_id": selection.user_id,
                    "project_id": selection.project_id,
                    "name": selection.name,
                    "member_ids": list(selection.member_ids),
                }
                for selection in state.selections_by_id.values()
            ],
            "current_project_id_by_user": state.current_project_id_by_user,
            "current_metadata_selection_by_user": state.current_metadata_selection_by_user,
            "metadata_revisions_by_user": state.metadata_revisions_by_user,
        }
    )


def _restore_local_workspace(state: HostedApiState, payload: Mapping[str, object]) -> None:
    projects = payload.get("projects", [])
    selections = payload.get("selections", [])
    if not isinstance(projects, list) or not isinstance(selections, list):
        raise ValueError("local workspace state has an invalid shape")
    for project in cast("list[object]", projects):
        if not isinstance(project, Mapping):
            raise ValueError("local workspace project is invalid")
        project_row = cast("Mapping[str, object]", project)
        project_id = _workspace_text(project_row, "project_id")
        state.projects_by_id[project_id] = ProjectRecord(
            project_id=project_id,
            user_id=_workspace_text(project_row, "user_id"),
            name=_workspace_text(project_row, "name"),
        )
    for selection in cast("list[object]", selections):
        if not isinstance(selection, Mapping):
            raise ValueError("local workspace selection is invalid")
        selection_row = cast("Mapping[str, object]", selection)
        member_ids = selection_row.get("member_ids")
        if not isinstance(member_ids, list):
            raise ValueError("local workspace selection members are invalid")
        member_id_values = cast("list[object]", member_ids)
        if not all(isinstance(value, str) for value in member_id_values):
            raise ValueError("local workspace selection members are invalid")
        selection_id = _workspace_text(selection_row, "selection_id")
        state.selections_by_id[selection_id] = SelectionRecord(
            selection_id=selection_id,
            user_id=_workspace_text(selection_row, "user_id"),
            project_id=_workspace_text(selection_row, "project_id"),
            name=_workspace_text(selection_row, "name"),
            member_ids=tuple(cast("list[str]", member_id_values)),
        )
    state.current_project_id_by_user = _workspace_string_map(
        payload.get("current_project_id_by_user", {})
    )
    state.current_metadata_selection_by_user = _workspace_string_map(
        payload.get("current_metadata_selection_by_user", {})
    )
    state.metadata_revisions_by_user = _workspace_string_map(
        payload.get("metadata_revisions_by_user", {})
    )


def _workspace_text(row: Mapping[str, object], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"local workspace {key} is invalid")
    return value


def _workspace_string_map(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError("local workspace mapping is invalid")
    mapping = cast("Mapping[str, object]", value)
    if not all(isinstance(item, str) for item in mapping.values()):
        raise ValueError("local workspace mapping is invalid")
    return {key: cast(str, item) for key, item in mapping.items()}


def _opaque_id(kind: str, value: str) -> str:
    return f"{kind}_{uuid.uuid5(uuid.NAMESPACE_URL, value).hex}"


def _stable_hash(payload: JsonRow) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def _http_error(status_code: int, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code})


app = create_runtime_app()
