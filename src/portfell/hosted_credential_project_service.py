"""Credential, entitlement, project, and account application service."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_api_serializers import (
    credential_status_row,
    project_row,
    selection_row,
)
from portfell.hosted_api_service_support import (
    page,
    stable_hash,
)
from portfell.hosted_api_state import ProjectRecord, SelectionRecord
from portfell.hosted_audit_event_repository import AuditEventRepository, HostedAuditEvent
from portfell.hosted_credentials import EodhdCredentialVault
from portfell.hosted_idempotency_repository import IdempotencyRepository
from portfell.hosted_project_settings_repository import ProjectSettingsRepository
from portfell.hosted_repository_importer import (
    ProjectRepository,
    TenantImportError,
    TenantProject,
    TenantSelection,
)
from portfell.hosted_selection_repository import SelectionRepository
from portfell.table_io import JsonRow


class CredentialProjectService:
    """Own credential, basic download, project, and account state transitions."""

    def __init__(
        self,
        project_repository: ProjectRepository,
        selection_repository: SelectionRepository,
        project_settings_repository: ProjectSettingsRepository,
        credential_vault: EodhdCredentialVault,
        audit_repository: AuditEventRepository,
        idempotency_repository: IdempotencyRepository,
        workflow_reader: Callable[[str, str | None], JsonRow],
        project_data_loaded_reader: Callable[[str, str], bool],
        project_active_run_reader: Callable[[str, str], JsonRow | None] | None,
        navigation_reader: Callable[[str], tuple[JsonRow, str] | None],
        navigation_reconciler: Callable[[str], tuple[JsonRow, str]],
        workspace_persister: Callable[[], None] | None,
        local_cache_cleanup: Callable[[str, str | None], None] | None,
    ) -> None:
        self._projects = project_repository
        self._selections = selection_repository
        self._project_settings = project_settings_repository
        self._credentials = credential_vault
        self._audit_events = audit_repository
        self._idempotency = idempotency_repository
        self._workflow_reader = workflow_reader
        self._project_data_loaded_reader = project_data_loaded_reader
        self._project_active_run_reader = project_active_run_reader
        self._navigation_reader = navigation_reader
        self._navigation_reconciler = navigation_reconciler
        self._workspace_persister = workspace_persister
        self._local_cache_cleanup = local_cache_cleanup

    def workflow(self, user_id: str, project_id: str | None = None) -> JsonRow:
        if project_id is not None:
            self._project(user_id, project_id)
        return self._workflow_reader(user_id, project_id)

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
        self._sync_navigation(user_id)
        return project_row(self._record(project))

    def list_projects(self, user_id: str, limit: int, offset: int) -> JsonRow:
        items = [
            self._project_with_selection_row(row, user_id) for row in self._project_records(user_id)
        ]
        return {"items": page(items, limit=limit, offset=offset)}

    def project_context(self, user_id: str) -> JsonRow:
        return self.project_context_with_etag(user_id)[0]

    def project_context_with_etag(self, user_id: str) -> tuple[JsonRow, str]:
        projection = self._navigation_reader(user_id)
        if projection is not None:
            return projection
        context = self._project_context_source(user_id)
        return context, stable_hash(context)

    def _project_context_source(self, user_id: str) -> JsonRow:
        project = self._current_project(user_id)
        projects = self._project_records(user_id)
        current = None if project is None else self._project_with_selection_row(project, user_id)
        context: JsonRow = {
            "current_project_id": None if project is None else project.project_id,
            "current_project": current,
            "projects": [self._project_with_selection_row(item, user_id) for item in projects],
        }
        return context

    def select_current_project(self, user_id: str, project_id: str) -> JsonRow:
        self._set_current_project(user_id, project_id)
        self._audit(user_id, "project.current.select")
        self._sync_navigation(user_id)
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
        if self._workspace_persister is not None:
            self._workspace_persister()
        return value

    def delete_project(self, user_id: str, project_id: str) -> JsonRow:
        self._delete_project(user_id, project_id)
        if self._local_cache_cleanup is not None:
            self._local_cache_cleanup(user_id, project_id)
        self._audit(user_id, "project.delete")
        self._sync_navigation(user_id)
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
        self._sync_navigation(user_id)
        return selection_row(self._selection_record(selection))

    def _sync_navigation(self, user_id: str) -> None:
        self._navigation_reconciler(user_id)

    def refresh_navigation(self, user_id: str) -> None:
        """Refresh the projection after a collaborating command service changes project state."""

        self._sync_navigation(user_id)

    def selection_detail(self, user_id: str, selection_id: str) -> JsonRow:
        selection = self._selections.by_id(selection_id=selection_id, user_id=user_id)
        if selection is None:
            raise HostedApplicationError(404, "not_found")
        return selection_row(self._selection_record(selection))

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
        if project_id is None:
            return None
        return self._project(user_id, project_id)

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
            "data_loaded": self._project_data_loaded_reader(user_id, project.project_id),
            **(
                {}
                if self._project_active_run_reader is None
                else {"active_run": self._project_active_run_reader(user_id, project.project_id)}
            ),
        }
