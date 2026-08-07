"""Credential, entitlement, project, and account application service."""

from __future__ import annotations

from portfell.entitlements import (
    ProviderDownloadRun,
    delete_user_entitlements,
    publish_user_data_snapshot,
)
from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_api_serializers import (
    credential_status_row,
    download_row,
    project_row,
    selection_row,
)
from portfell.hosted_api_service_support import (
    audit,
    current_project,
    idempotent_response,
    opaque_id,
    page,
    project_context_row,
    project_with_selection_row,
    projects_for_user,
    remember_idempotency,
    remove_discontinued_projects,
    require_user_row,
    selection_for_project,
    set_current_project,
    stable_hash,
    workflow_row,
)
from portfell.hosted_api_state import HostedApiState, ProjectRecord, SelectionRecord
from portfell.table_io import JsonRow


class CredentialProjectService:
    """Own credential, basic download, project, and account state transitions."""

    def __init__(self, state: HostedApiState) -> None:
        self.state = state

    def workflow(self, user_id: str, project_id: str | None = None) -> JsonRow:
        if project_id is None:
            project = current_project(self.state, user_id)
            project_id = None if project is None else project.project_id
        else:
            require_user_row(self.state.projects_by_id, project_id, user_id)
        return workflow_row(self.state, user_id, project_id)

    def credential_status(self, user_id: str) -> JsonRow:
        try:
            return credential_status_row(self.state.credential_vault().status(user_id=user_id))
        except Exception as error:
            raise HostedApplicationError(404, "credential_not_found") from error

    def credential_value(self, user_id: str) -> JsonRow:
        try:
            value = self.state.credential_vault().unwrap_for_provider_call(user_id=user_id)
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
        value = self.state.credential_vault().set_credential(
            user_id=user_id, provider_key=provider_key
        )
        remember_idempotency(
            self.state, user_id, "set-credential", idempotency_key, value.credential_id
        )
        audit(self.state, user_id, "credential.set")
        return credential_status_row(value)

    def delete_credential(self, user_id: str) -> JsonRow:
        try:
            value = self.state.credential_vault().delete(user_id=user_id)
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
            return project_row(self.state.projects_by_id[cached])
        project_id = opaque_id("project", f"{user_id}:{name}")
        self.state.projects_by_id.setdefault(
            project_id, ProjectRecord(project_id=project_id, user_id=user_id, name=name)
        )
        set_current_project(self.state, user_id, project_id)
        remember_idempotency(self.state, user_id, operation, idempotency_key, project_id)
        audit(self.state, user_id, "project.create")
        return project_row(self.state.projects_by_id[project_id])

    def list_projects(self, user_id: str, limit: int, offset: int) -> JsonRow:
        remove_discontinued_projects(self.state, user_id)
        items = [
            project_with_selection_row(self.state, row, user_id)
            for row in projects_for_user(self.state, user_id)
        ]
        return {"items": page(items, limit=limit, offset=offset)}

    def project_context(self, user_id: str) -> JsonRow:
        return project_context_row(self.state, user_id)

    def select_current_project(self, user_id: str, project_id: str) -> JsonRow:
        set_current_project(self.state, user_id, project_id)
        audit(self.state, user_id, "project.current.select")
        return project_context_row(self.state, user_id)

    def project_metadata_filter(
        self, user_id: str, project_id: str
    ) -> tuple[ProjectRecord, SelectionRecord]:
        project = require_user_row(self.state.projects_by_id, project_id, user_id)
        return project, selection_for_project(self.state, project_id, user_id)

    def delete_project(self, user_id: str, project_id: str) -> JsonRow:
        require_user_row(self.state.projects_by_id, project_id, user_id)
        self.state.projects_by_id.pop(project_id, None)
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
        if self.state.current_project_id_by_user.get(user_id) == project_id:
            self.state.current_project_id_by_user.pop(user_id, None)
            current_project(self.state, user_id)
        audit(self.state, user_id, "project.delete")
        return {"status": "deleted", "project_id": project_id}

    def create_selection(
        self, user_id: str, project_id: str, name: str, member_ids: list[str]
    ) -> JsonRow:
        require_user_row(self.state.projects_by_id, project_id, user_id)
        members = tuple(sorted(set(member_ids)))
        selection_id = opaque_id("selection", f"{user_id}:{project_id}:{name}:{members}")
        self.state.selections_by_id.setdefault(
            selection_id,
            SelectionRecord(selection_id, user_id, project_id, name, members),
        )
        audit(self.state, user_id, "selection.create")
        return selection_row(self.state.selections_by_id[selection_id])

    def selection_detail(self, user_id: str, selection_id: str) -> JsonRow:
        return selection_row(require_user_row(self.state.selections_by_id, selection_id, user_id))

    def delete_account(self, user_id: str) -> JsonRow:
        delete_user_entitlements(store=self.state.entitlements, user_id=user_id)
        self.state.projects_by_id = {
            key: row for key, row in self.state.projects_by_id.items() if row.user_id != user_id
        }
        self.state.selections_by_id = {
            key: row for key, row in self.state.selections_by_id.items() if row.user_id != user_id
        }
        self.state.analyses_by_id = {
            key: row for key, row in self.state.analyses_by_id.items() if row.user_id != user_id
        }
        audit(self.state, user_id, "account.delete")
        return {"status": "deleted"}
