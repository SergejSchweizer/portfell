"""Credential, entitlement, project, and account application service."""

from __future__ import annotations

import uuid

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
    audit,
    idempotent_response,
    opaque_id,
    page,
    project_data_loaded,
    remember_idempotency,
    require_user_row,
    stable_hash,
    workflow_row,
)
from portfell.hosted_api_state import HostedApiState, ProjectRecord, SelectionRecord
from portfell.hosted_credentials import EodhdCredentialVault
from portfell.hosted_local_project_repository import LocalProjectRepository
from portfell.hosted_local_selection_repository import LocalSelectionRepository
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
        credential_vault: EodhdCredentialVault | None = None,
    ) -> None:
        self.state = state
        self.runtime = runtime
        self._projects = project_repository or LocalProjectRepository(state)
        self._selections = selection_repository or LocalSelectionRepository(state)
        self._credentials = credential_vault or state.credential_vault()

    def workflow(self, user_id: str, project_id: str | None = None) -> JsonRow:
        if project_id is None:
            project = self._current_project(user_id)
            project_id = None if project is None else project.project_id
        else:
            self._project(user_id, project_id)
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

    def credential_value(self, user_id: str) -> JsonRow:
        try:
            value = self._credentials.unwrap_for_provider_call(user_id=user_id)
        except Exception as error:
            raise HostedApplicationError(404, "credential_not_found") from error
        return {"provider_key": value}

    def set_credential(
        self, user_id: str, provider_key: str, idempotency_key: str | None
    ) -> JsonRow:
        cached = idempotent_response(
            self.state,
            user_id=user_id,
            operation="set-credential",
            idempotency_key=idempotency_key,
        )
        if cached is not None:
            return self.credential_status(user_id)
        value = self._credentials.set_credential(user_id=user_id, provider_key=provider_key)
        remember_idempotency(
            self.state, user_id, "set-credential", idempotency_key, value.credential_id
        )
        audit(self.state, user_id, "credential.set")
        return credential_status_row(value)

    def delete_credential(self, user_id: str) -> JsonRow:
        try:
            value = self._credentials.delete(user_id=user_id)
        except Exception as error:
            raise HostedApplicationError(404, "credential_not_found") from error
        audit(self.state, user_id, "credential.delete")
        return credential_status_row(value)

    def plan_download(self, user_id: str, symbols: list[str]) -> JsonRow:
        request_hash = stable_hash({"user_id": user_id, "symbols": sorted(symbols)})
        return {"download_run_id": opaque_id("download-plan", request_hash), "status": "planned"}

    def run_download(
        self, user_id: str, symbols: list[str], idempotency_key: str | None
    ) -> JsonRow:
        cached = idempotent_response(
            self.state,
            user_id=user_id,
            operation="download-run",
            idempotency_key=idempotency_key,
        )
        if cached is not None:
            return download_row(self.state.downloads_by_id[cached])
        observation_ids = tuple(opaque_id("observation", value) for value in sorted(set(symbols)))
        request_hash = stable_hash({"user_id": user_id, "symbols": list(observation_ids)})
        run = ProviderDownloadRun(
            download_run_id=opaque_id("download-run", request_hash),
            user_id=user_id,
            credential_id="credential-ref",
            provider="eodhd",
            status="succeeded",
            returned_observation_ids=observation_ids,
            request_hash=request_hash,
            requested_scope={"symbols": sorted(set(symbols))},
        )
        self.state.downloads_by_id[run.download_run_id] = run
        publish_user_data_snapshot(store=self.state.entitlements, run=run)
        remember_idempotency(
            self.state, user_id, "download-run", idempotency_key, run.download_run_id
        )
        audit(self.state, user_id, "download.run")
        return download_row(run)

    def download_status(self, user_id: str, run_id: str) -> JsonRow:
        return download_row(require_user_row(self.state.downloads_by_id, run_id, user_id))

    def visible_datasets(self, user_id: str) -> JsonRow:
        return {
            "items": [
                {"dataset_id": row_id, "dataset_type": "eodhd_observation"}
                for row_id in self.state.entitlements.visible_observation_ids(user_id)
            ]
        }

    def create_project(self, user_id: str, name: str, idempotency_key: str | None) -> JsonRow:
        operation = f"project:{name}"
        cached = idempotent_response(
            self.state,
            user_id=user_id,
            operation=operation,
            idempotency_key=idempotency_key,
        )
        if cached is not None:
            return project_row(self._project(user_id, cached))
        project_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"portfell:project:{user_id}:{name}"))
        project = self._projects.create_project(TenantProject(project_id, user_id, name))
        self._projects.set_current_project(user_id=user_id, project_id=project.project_id)
        remember_idempotency(self.state, user_id, operation, idempotency_key, project_id)
        audit(self.state, user_id, "project.create")
        return project_row(self._record(project))

    def list_projects(self, user_id: str, limit: int, offset: int) -> JsonRow:
        items = [
            self._project_with_selection_row(row, user_id) for row in self._project_records(user_id)
        ]
        return {"items": page(items, limit=limit, offset=offset)}

    def project_context(self, user_id: str) -> JsonRow:
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
        audit(self.state, user_id, "project.current.select")
        return self.project_context(user_id)

    def project_metadata_builder(
        self, user_id: str, project_id: str
    ) -> tuple[ProjectRecord, SelectionRecord]:
        project = self._project(user_id, project_id)
        return project, self._selection_for_project(user_id, project_id)

    def univariate_selection_settings(self, user_id: str, project_id: str) -> JsonRow:
        self._project(user_id, project_id)
        return {
            "dividend_frequencies": [],
            "statistic_labels": {},
            "statistic_ranges": {},
            **self.state.univariate_selection_settings_by_project.get(project_id, {}),
        }

    def save_univariate_selection_settings(
        self, user_id: str, project_id: str, settings: JsonRow
    ) -> JsonRow:
        self._project(user_id, project_id)
        self.state.univariate_selection_settings_by_project[project_id] = dict(settings)
        persist_local_workspace(self.state)
        return self.univariate_selection_settings(user_id, project_id)

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
        audit(self.state, user_id, "project.delete")
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
        audit(self.state, user_id, "selection.create")
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
        audit(self.state, user_id, "account.delete")
        return {"status": "deleted"}

    def _project_records(self, user_id: str) -> list[ProjectRecord]:
        return sorted(
            (self._record(project) for project in self._projects.list_projects(user_id)),
            key=lambda project: (project.name.casefold(), project.project_id),
        )

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
            "data_loaded": project_data_loaded(self.state, project.project_id, user_id),
        }
