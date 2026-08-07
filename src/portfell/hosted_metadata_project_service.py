"""Metadata and metadata-filter project application service."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from portfell.hosted_api_errors import HostedApplicationError, HostedRuntimeError
from portfell.hosted_api_ports import HostedRuntimePort
from portfell.hosted_api_serializers import (
    metadata_fetch_row,
    project_row,
    selection_row,
)
from portfell.hosted_api_service_support import (
    audit,
    idempotent_response,
    opaque_id,
    remember_idempotency,
    selection_for_project,
    set_current_project,
    stable_hash,
)
from portfell.hosted_api_state import HostedApiState, ProjectRecord, SelectionRecord
from portfell.hosted_credentials import CredentialVaultError
from portfell.selection_filters import Predicate, filter_rows
from portfell.table_io import JsonRow


class MetadataProjectService:
    """Own metadata refresh and metadata-derived project transitions."""

    def __init__(self, state: HostedApiState, runtime: HostedRuntimePort) -> None:
        self.state = state
        self.runtime = runtime

    def _all_isins_rows(self) -> tuple[JsonRow, ...]:
        return self.state.all_isins_rows or self.runtime.all_isins_rows()

    def options(self) -> JsonRow:
        rows = self._all_isins_rows()
        return {
            field: sorted(
                {str(row.get(field, "")).strip() for row in rows if str(row.get(field, "")).strip()}
            )
            for field in ("exchange", "instrument_type", "country", "currency")
        }

    def start_metadata_fetch(self, user_id: str) -> tuple[JsonRow, Callable[[], None]]:
        try:
            provider_key = self.state.credential_vault().unwrap_for_provider_call(user_id=user_id)
        except CredentialVaultError as error:
            raise HostedApplicationError(422, "eodhd_key_required") from error
        run_id = opaque_id("metadata-run", f"{user_id}:{uuid.uuid4()}")
        self.state.metadata_runs_by_id[run_id] = {
            "metadata_run_id": run_id,
            "user_id": user_id,
            "status": "running",
            "total": 0,
            "completed": 0,
            "skipped_exchange_count": 0,
            "percent": 0,
        }
        audit(self.state, user_id, "fetch_all_metadata.started")
        return metadata_fetch_row(
            self.state.metadata_runs_by_id[run_id]
        ), lambda: self.run_metadata_fetch(user_id, run_id, provider_key)

    def metadata_fetch_status(self, user_id: str, run_id: str) -> JsonRow:
        run = self.state.metadata_runs_by_id.get(run_id)
        if run is None or run.get("user_id") != user_id:
            raise HostedApplicationError(404, "metadata_run_not_found")
        return metadata_fetch_row(run)

    def run_metadata_fetch(self, user_id: str, run_id: str, provider_key: str) -> None:
        def update_progress(completed: int, total: int, skipped: int) -> None:
            percent = round((completed / total) * 100) if total else 0
            self.state.metadata_runs_by_id[run_id] = {
                **self.state.metadata_runs_by_id[run_id],
                "completed": completed,
                "total": total,
                "skipped_exchange_count": skipped,
                "percent": percent,
            }

        try:
            summary = self.runtime.run_metadata(
                provider_key=provider_key, on_progress=update_progress
            )
        except HostedRuntimeError as error:
            self._fail_metadata_fetch(user_id, run_id, error.code)
            return
        except Exception:
            self._fail_metadata_fetch(user_id, run_id, "metadata_fetch_failed")
            return
        self.state.metadata_revisions_by_user[user_id] = opaque_id(
            "metadata-revision", stable_hash(summary)
        )
        self.state.current_metadata_selection_by_user.pop(user_id, None)
        self.state.current_filter_selection_by_user.pop(user_id, None)
        self.state.metadata_runs_by_id[run_id] = {
            **self.state.metadata_runs_by_id[run_id],
            "status": "succeeded",
            "row_count": int(summary["all_isins_rows"]),
            "exchange_count": int(summary["exchange_count"]),
            "requested_exchange_count": int(summary["requested_exchange_count"]),
            "skipped_exchange_count": int(summary["skipped_exchange_count"]),
            "skipped_exchanges": list(summary["skipped_exchanges"]),
            "percent": 100,
        }
        audit(self.state, user_id, "fetch_all_metadata.completed")

    def _fail_metadata_fetch(self, user_id: str, run_id: str, code: str) -> None:
        self.state.metadata_runs_by_id[run_id] = {
            **self.state.metadata_runs_by_id[run_id],
            "status": "failed",
            "error_code": code,
        }
        audit(self.state, user_id, "fetch_all_metadata.failed")

    def create_filter_project(
        self,
        user_id: str,
        *,
        exchange: str,
        name: str,
        instrument_type: str,
        country: str,
        currency: str,
        idempotency_key: str | None,
    ) -> JsonRow:
        values = (
            ("exchange", "=", exchange),
            ("name", "~", name),
            ("instrument_type", "=", instrument_type),
            ("country", "=", country),
            ("currency", "=", currency),
        )
        predicates = tuple(
            Predicate(field, operator, value.strip())
            for field, operator, value in values
            if value.strip()
        )
        if not predicates:
            raise HostedApplicationError(422, "metadata_filter_required")
        selected_rows = filter_rows(self._all_isins_rows(), predicates)
        if not selected_rows:
            raise HostedApplicationError(422, "metadata_filter_empty")
        project_name = (
            "_".join(
                part
                for part in ("_".join(value.strip().casefold().split()) for _, _, value in values)
                if part
            )
            or "metadata_filter_project"
        )
        operation = f"metadata-filter-project:{project_name}"
        cached = idempotent_response(
            self.state,
            user_id=user_id,
            operation=operation,
            idempotency_key=idempotency_key,
        )
        if cached is not None:
            project = self.state.projects_by_id[cached]
            selection = selection_for_project(self.state, project.project_id, user_id)
            set_current_project(self.state, user_id, project.project_id)
            return self._filter_project_row(project, selection, len(selected_rows))
        project_id = opaque_id("project", f"{user_id}:{project_name}")
        project = ProjectRecord(project_id, user_id, project_name)
        self.state.projects_by_id.setdefault(project_id, project)
        members = tuple(
            sorted(
                {
                    f"{row['isin']}:{row['exchange']}:{row['code']}"
                    for row in selected_rows
                    if row.get("isin") and row.get("exchange") and row.get("code")
                }
            )
        )
        selection_id = opaque_id("selection", f"{user_id}:{project_id}:{project_name}:{members}")
        selection = SelectionRecord(selection_id, user_id, project_id, project_name, members)
        self.state.selections_by_id.setdefault(selection_id, selection)
        self.state.current_metadata_selection_by_user[user_id] = selection_id
        self.state.current_filter_selection_by_user.pop(user_id, None)
        set_current_project(self.state, user_id, project_id)
        self.runtime.write_metadata_selection(selection_id, selected_rows, predicates)
        remember_idempotency(self.state, user_id, operation, idempotency_key, project_id)
        audit(self.state, user_id, "metadata_filter.project.create")
        return self._filter_project_row(project, selection, len(selected_rows))

    @staticmethod
    def _filter_project_row(
        project: ProjectRecord, selection: SelectionRecord, selected_count: int
    ) -> JsonRow:
        return {
            "project": project_row(project),
            "selection": selection_row(selection),
            "selected_count": selected_count,
        }

    def project_filter_row(self, project: ProjectRecord, selection: SelectionRecord) -> JsonRow:
        fields: JsonRow = {
            "exchange": "",
            "instrument_type": "",
            "country": "",
            "currency": "",
            "name": "",
        }
        try:
            predicates = self.runtime.metadata_filter_predicates(selection.selection_id)
        except ValueError as error:
            raise HostedApplicationError(500, "metadata_filter_manifest_invalid") from error
        for predicate in predicates:
            if predicate.field == "name" and predicate.operator == "~":
                fields["name"] = predicate.expected
            elif predicate.field in fields and predicate.operator == "=":
                fields[predicate.field] = predicate.expected
        return {
            "project_id": project.project_id,
            "selection_id": selection.selection_id,
            "selected_count": len(selection.member_ids),
            **fields,
        }
