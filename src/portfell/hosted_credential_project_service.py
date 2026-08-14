"""Credential, entitlement, project, and account application service."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from portfell.entitlements import (
    ProviderDownloadRun,
    delete_user_entitlements,
    publish_user_data_snapshot,
)
from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_api_ports import HostedRuntimePort
from portfell.hosted_api_serializers import (
    credential_status_row,
    download_row,
    project_row,
    selection_row,
)
from portfell.hosted_api_service_support import (
    opaque_id,
    page,
    project_data_loaded,
    stable_hash,
    workflow_row,
)
from portfell.hosted_api_state import HostedApiState, ProjectRecord, SelectionRecord
from portfell.hosted_audit_event_repository import AuditEventRepository, HostedAuditEvent
from portfell.hosted_credentials import EodhdCredentialVault
from portfell.hosted_download_run_repository import DownloadRunRepository
from portfell.hosted_idempotency_repository import (
    IdempotencyRepository,
    LocalIdempotencyRepository,
)
from portfell.hosted_local_audit_event_repository import LocalAuditEventRepository
from portfell.hosted_local_download_run_repository import LocalDownloadRunRepository
from portfell.hosted_local_project_repository import LocalProjectRepository
from portfell.hosted_local_selection_repository import LocalSelectionRepository
from portfell.hosted_project_settings_repository import (
    LocalProjectSettingsRepository,
    ProjectSettingsRepository,
)
from portfell.hosted_repository_importer import (
    ProjectRepository,
    TenantImportError,
    TenantProject,
    TenantSelection,
)
from portfell.hosted_selection_repository import SelectionRepository
from portfell.hosted_workspace_repository import persist_local_workspace
from portfell.table_io import JsonRow


class CredentialProjectService:
    """Own credential, basic download, project, and account state transitions."""

    def __init__(
        self,
        state: HostedApiState,
        runtime: HostedRuntimePort | None = None,
        project_repository: ProjectRepository | None = None,
        selection_repository: SelectionRepository | None = None,
        project_settings_repository: ProjectSettingsRepository | None = None,
        credential_vault: EodhdCredentialVault | None = None,
        audit_repository: AuditEventRepository | None = None,
        download_run_repository: DownloadRunRepository | None = None,
        idempotency_repository: IdempotencyRepository | None = None,
        workflow_reader: Callable[[str, str | None], JsonRow] | None = None,
        project_data_loaded_reader: Callable[[str, str], bool] | None = None,
        project_active_run_reader: Callable[[str, str], JsonRow | None] | None = None,
        navigation_reader: Callable[[str], tuple[JsonRow, str] | None] | None = None,
    ) -> None:
        self.state = state
        self.runtime = runtime
        self._projects = project_repository or LocalProjectRepository(state)
        self._selections = selection_repository or LocalSelectionRepository(state)
        self._project_settings = project_settings_repository or LocalProjectSettingsRepository(
            state
        )
        self._credentials = credential_vault or state.credential_vault()
        self._audit_events = audit_repository or LocalAuditEventRepository(state)
        self._download_runs = download_run_repository or LocalDownloadRunRepository(state)
        self._idempotency = idempotency_repository or LocalIdempotencyRepository(state)
        self._workflow_reader = workflow_reader
        self._project_data_loaded_reader = project_data_loaded_reader
        self._project_active_run_reader = project_active_run_reader
        self._navigation_reader = navigation_reader

    def workflow(self, user_id: str, project_id: str | None = None) -> JsonRow:
        if project_id is None:
            project = self._current_project(user_id)
            project_id = None if project is None else project.project_id
        else:
            self._project(user_id, project_id)
        if self._workflow_reader is not None:
            return self._workflow_reader(user_id, project_id)
        metadata_rows = self.state.all_isins_rows
        if project_id is not None and not metadata_rows and self.runtime is not None:
            metadata_rows = self.runtime.all_isins_rows()
        metadata_downloaded_isins = len(
            {
                str(row.get("isin", "")).strip()
                for row in metadata_rows
                if str(row.get("isin", "")).strip()
            }
        )
        return workflow_row(
            self.state,
            user_id,
            project_id,
            metadata_downloaded_isins=metadata_downloaded_isins,
        )

    def credential_status(self, user_id: str) -> JsonRow:
        try:
            return credential_status_row(self._credentials.status(user_id=user_id))
        except Exception as error:
            raise HostedApplicationError(404, "credential_not_found") from error

    def set_credential(
        self, user_id: str, provider_key: str, idempotency_key: str | None
    ) -> JsonRow:
        request_hash = stable_hash({"provider_key": provider_key})
        cached = self._idempotency.lookup(
            user_id=user_id,
            operation="set-credential",
            key=idempotency_key,
            request_hash=request_hash,
        )
        if cached is not None:
            return self.credential_status(user_id)
        value = self._credentials.set_credential(user_id=user_id, provider_key=provider_key)
        self._idempotency.remember(
            user_id=user_id,
            operation="set-credential",
            key=idempotency_key,
            request_hash=request_hash,
            response_ref=value.credential_id,
        )
        self._audit(user_id, "credential.set")
        return credential_status_row(value)

    def delete_credential(self, user_id: str) -> JsonRow:
        try:
            value = self._credentials.delete(user_id=user_id)
        except Exception as error:
            raise HostedApplicationError(404, "credential_not_found") from error
        self._audit(user_id, "credential.delete")
        return credential_status_row(value)

    def plan_download(self, user_id: str, symbols: list[str]) -> JsonRow:
        request_hash = stable_hash({"user_id": user_id, "symbols": sorted(symbols)})
        return {"download_run_id": opaque_id("download-plan", request_hash), "status": "planned"}

    def run_download(
        self, user_id: str, symbols: list[str], idempotency_key: str | None
    ) -> JsonRow:
        idempotency_hash = stable_hash({"symbols": sorted(symbols)})
        cached = self._idempotency.lookup(
            user_id=user_id,
            operation="download-run",
            key=idempotency_key,
            request_hash=idempotency_hash,
        )
        if cached is not None:
            return download_row(self._require_download_run(user_id, cached))
        observation_ids = tuple(opaque_id("observation", value) for value in sorted(set(symbols)))
        try:
            credential_id = self._credentials.status(user_id=user_id).credential_id
        except Exception as error:
            raise HostedApplicationError(422, "eodhd_credential_required") from error
        request_hash = stable_hash({"user_id": user_id, "symbols": list(observation_ids)})
        run = ProviderDownloadRun(
            download_run_id=opaque_id("download-run", request_hash),
            user_id=user_id,
            credential_id=credential_id,
            provider="eodhd",
            status="succeeded",
            returned_observation_ids=observation_ids,
            request_hash=request_hash,
            requested_scope={"symbols": sorted(set(symbols))},
        )
        run = self._download_runs.create(run)
        publish_user_data_snapshot(store=self.state.entitlements, run=run)
        self._idempotency.remember(
            user_id=user_id,
            operation="download-run",
            key=idempotency_key,
            request_hash=idempotency_hash,
            response_ref=run.download_run_id,
        )
        self._audit(user_id, "download.run")
        return download_row(run)

    def download_status(self, user_id: str, run_id: str) -> JsonRow:
        return download_row(self._require_download_run(user_id, run_id))

    def visible_datasets(self, user_id: str) -> JsonRow:
        return {
            "items": [
                {"dataset_id": row_id, "dataset_type": "eodhd_observation"}
                for row_id in self.state.entitlements.visible_observation_ids(user_id)
            ]
        }

    def create_project(self, user_id: str, name: str, idempotency_key: str | None) -> JsonRow:
        operation = f"project:{name}"
        request_hash = stable_hash({"name": name})
        cached = self._idempotency.lookup(
            user_id=user_id,
            operation=operation,
            key=idempotency_key,
            request_hash=request_hash,
        )
        if cached is not None:
            return project_row(self._project(user_id, cached))
        project_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"portfell:project:{user_id}:{name}"))
        project = self._projects.create_project(TenantProject(project_id, user_id, name))
        self._projects.set_current_project(user_id=user_id, project_id=project.project_id)
        self._idempotency.remember(
            user_id=user_id,
            operation=operation,
            key=idempotency_key,
            request_hash=request_hash,
            response_ref=project_id,
        )
        self._audit(user_id, "project.create")
        return project_row(self._record(project))

    def list_projects(self, user_id: str, limit: int, offset: int) -> JsonRow:
        items = [
            self._project_with_selection_row(row, user_id) for row in self._project_records(user_id)
        ]
        return {"items": page(items, limit=limit, offset=offset)}

    def project_context(self, user_id: str) -> JsonRow:
        if self._navigation_reader is not None:
            projection = self._navigation_reader(user_id)
            if projection is not None:
                return projection[0]
        project = self._current_project(user_id)
        projects = self._project_records(user_id)
        current = None if project is None else self._project_with_selection_row(project, user_id)
        return {
            "current_project_id": None if project is None else project.project_id,
            "current_project": current,
            "projects": [self._project_with_selection_row(item, user_id) for item in projects],
        }

    def select_current_project(self, user_id: str, project_id: str) -> JsonRow:
        self._set_current_project(user_id, project_id)
        self._audit(user_id, "project.current.select")
        return self.project_context(user_id)

    def project_metadata_builder(
        self, user_id: str, project_id: str
    ) -> tuple[ProjectRecord, SelectionRecord]:
        project = self._project(user_id, project_id)
        return project, self._selection_for_project(user_id, project_id)

    def univariate_selection_settings(self, user_id: str, project_id: str) -> JsonRow:
        self._project(user_id, project_id)
        return self._project_settings.univariate(user_id=user_id, project_id=project_id)

    def save_univariate_selection_settings(
        self, user_id: str, project_id: str, settings: JsonRow
    ) -> JsonRow:
        self._project(user_id, project_id)
        value = self._project_settings.save_univariate(
            user_id=user_id, project_id=project_id, settings=settings
        )
        if self.state.workspace_store is not None:
            persist_local_workspace(self.state)
        return value

    def delete_project(self, user_id: str, project_id: str) -> JsonRow:
        self._delete_project(user_id, project_id)
        self.state.selections_by_id = {
            row_id: row
            for row_id, row in self.state.selections_by_id.items()
            if row.project_id != project_id or row.user_id != user_id
        }
        self.state.analyses_by_id = {
            row_id: row
            for row_id, row in self.state.analyses_by_id.items()
            if row.project_id != project_id or row.user_id != user_id
        }
        self._audit(user_id, "project.delete")
        return {"status": "deleted", "project_id": project_id}

    def create_selection(
        self, user_id: str, project_id: str, name: str, member_ids: list[str]
    ) -> JsonRow:
        self._project(user_id, project_id)
        members = tuple(sorted(set(member_ids)))
        selection_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"portfell:selection:{user_id}:{project_id}:{name}:{members}",
            )
        )
        selection = self._selections.create(
            TenantSelection(selection_id, project_id, user_id, name, members)
        )
        self._audit(user_id, "selection.create")
        return selection_row(self._selection_record(selection))

    def selection_detail(self, user_id: str, selection_id: str) -> JsonRow:
        selection = self._selections.by_id(selection_id=selection_id, user_id=user_id)
        if selection is None:
            raise HostedApplicationError(404, "not_found")
        return selection_row(self._selection_record(selection))

    def delete_account(self, user_id: str) -> JsonRow:
        delete_user_entitlements(store=self.state.entitlements, user_id=user_id)
        for project in self._projects.list_projects(user_id):
            self._delete_project(user_id, project.project_id)
        self.state.selections_by_id = {
            key: row for key, row in self.state.selections_by_id.items() if row.user_id != user_id
        }
        self.state.analyses_by_id = {
            key: row for key, row in self.state.analyses_by_id.items() if row.user_id != user_id
        }
        self._audit(user_id, "account.delete")
        return {"status": "deleted"}

    def _project_records(self, user_id: str) -> list[ProjectRecord]:
        return sorted(
            (self._record(project) for project in self._projects.list_projects(user_id)),
            key=lambda project: (project.name.casefold(), project.project_id),
        )

    def _audit(self, user_id: str, event_type: str) -> None:
        self._audit_events.append(
            HostedAuditEvent(
                audit_event_id=str(uuid.uuid4()),
                user_id=user_id,
                event_type=event_type,
                subject_ref=f"user:{user_id}",
                metadata={},
            )
        )

    def _credential_id(self, user_id: str) -> str:
        try:
            return self._credentials.status(user_id=user_id).credential_id
        except Exception as error:
            raise HostedApplicationError(422, "eodhd_credential_required") from error

    def _require_download_run(self, user_id: str, run_id: str) -> ProviderDownloadRun:
        run = self._download_runs.get(user_id=user_id, download_run_id=run_id)
        if run is None:
            raise HostedApplicationError(404, "not_found")
        return run

    @staticmethod
    def _record(project: TenantProject) -> ProjectRecord:
        return ProjectRecord(project.project_id, project.user_id, project.name)

    def _project(self, user_id: str, project_id: str) -> ProjectRecord:
        for project in self._project_records(user_id):
            if project.project_id == project_id:
                return project
        raise HostedApplicationError(404, "not_found")

    def _current_project(self, user_id: str) -> ProjectRecord | None:
        project_id = self._projects.current_project_id(user_id)
        if project_id is not None:
            return self._project(user_id, project_id)
        projects = self._project_records(user_id)
        if not projects:
            return None
        self._set_current_project(user_id, projects[0].project_id)
        return projects[0]

    def _set_current_project(self, user_id: str, project_id: str) -> None:
        try:
            self._projects.set_current_project(user_id=user_id, project_id=project_id)
        except TenantImportError as error:
            raise HostedApplicationError(404, "not_found") from error

    def _delete_project(self, user_id: str, project_id: str) -> None:
        try:
            self._projects.delete_project(user_id=user_id, project_id=project_id)
        except TenantImportError as error:
            raise HostedApplicationError(404, "not_found") from error

    @staticmethod
    def _selection_record(selection: TenantSelection) -> SelectionRecord:
        return SelectionRecord(
            selection.selection_id,
            selection.user_id,
            selection.project_id,
            selection.name,
            selection.member_ids,
            selection.metadata_builder_predicates,
        )

    def _selection_for_project(self, user_id: str, project_id: str) -> SelectionRecord:
        selection = self._selections.for_project(project_id=project_id, user_id=user_id)
        if selection is None:
            raise HostedApplicationError(404, "not_found")
        return self._selection_record(selection)

    def _project_with_selection_row(self, project: ProjectRecord, user_id: str) -> JsonRow:
        selection = self._selections.for_project(project_id=project.project_id, user_id=user_id)
        if selection is None:
            return {**project_row(project), "selected_count": 0, "data_loaded": False}
        return {
            **project_row(project),
            "selection_id": selection.selection_id,
            "selected_count": len(
                {member_id.split(":", 1)[0] for member_id in selection.member_ids}
            ),
            "data_loaded": (
                project_data_loaded(self.state, project.project_id, user_id)
                if self._project_data_loaded_reader is None
                else self._project_data_loaded_reader(user_id, project.project_id)
            ),
            **(
                {}
                if self._project_active_run_reader is None
                else {"active_run": self._project_active_run_reader(user_id, project.project_id)}
            ),
        }
