"""Metadata and metadata-builder project application service."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Protocol

from portfell.hosted_api_errors import HostedApplicationError, HostedRuntimeError
from portfell.hosted_api_ports import HostedRuntimePort
from portfell.hosted_api_serializers import (
    metadata_fetch_row,
    project_row,
    selection_row,
)
from portfell.hosted_api_service_support import (
    opaque_id,
    stable_hash,
)
from portfell.hosted_api_state import HostedApiState, ProjectRecord, SelectionRecord
from portfell.hosted_audit_event_repository import AuditEventRepository, HostedAuditEvent
from portfell.hosted_credentials import CredentialVaultError, EodhdCredentialVault
from portfell.hosted_local_audit_event_repository import LocalAuditEventRepository
from portfell.hosted_local_metadata_repository import LocalMetadataLifecycleRepository
from portfell.hosted_local_project_repository import LocalProjectRepository
from portfell.hosted_local_selection_repository import LocalSelectionRepository
from portfell.hosted_metadata_repository import MetadataLifecycleRepository, MetadataRun
from portfell.hosted_project_bootstrap_repository import ProjectBootstrapRepository
from portfell.hosted_repository_importer import (
    ProjectRepository,
    TenantProject,
    TenantSelection,
)
from portfell.hosted_selection_repository import SelectionRepository
from portfell.selection_filters import Predicate, filter_rows, parse_predicates
from portfell.table_io import JsonRow


class MetadataRefreshQueue(Protocol):
    """Enqueue a worker-owned metadata refresh without exposing provider credentials."""

    def enqueue(self, *, metadata_run_id: str, user_id: str) -> None: ...


class MetadataProjectService:
    """Own metadata refresh and metadata-derived project transitions."""

    def __init__(
        self,
        state: HostedApiState,
        runtime: HostedRuntimePort,
        project_repository: ProjectRepository | None = None,
        selection_repository: SelectionRepository | None = None,
        metadata_repository: MetadataLifecycleRepository | None = None,
        credential_vault: EodhdCredentialVault | None = None,
        audit_repository: AuditEventRepository | None = None,
        bootstrap_repository: ProjectBootstrapRepository | None = None,
        metadata_refresh_queue: MetadataRefreshQueue | None = None,
    ) -> None:
        self.state = state
        self.runtime = runtime
        self._projects = project_repository or LocalProjectRepository(state)
        self._selections = selection_repository or LocalSelectionRepository(state)
        self._metadata = metadata_repository or LocalMetadataLifecycleRepository(state)
        self._credentials = credential_vault or state.credential_vault()
        self._audit_events = audit_repository or LocalAuditEventRepository(state)
        self._bootstrap = bootstrap_repository
        self._metadata_refresh_queue = metadata_refresh_queue

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
        if self._metadata_refresh_queue is not None:
            run_id = opaque_id("metadata-run", f"{user_id}:{uuid.uuid4()}")
            run = self._metadata.create(MetadataRun(run_id, user_id, "running", 0, 0, 0, 0, {}))
            self._metadata_refresh_queue.enqueue(metadata_run_id=run_id, user_id=user_id)
            self._audit(user_id, "fetch_all_metadata.queued")
            return metadata_fetch_row(_metadata_row(run)), lambda: None
        try:
            provider_key = self._credentials.unwrap_for_provider_call(user_id=user_id)
        except CredentialVaultError as error:
            raise HostedApplicationError(422, "eodhd_key_required") from error
        run_id = opaque_id("metadata-run", f"{user_id}:{uuid.uuid4()}")
        run = self._metadata.create(MetadataRun(run_id, user_id, "running", 0, 0, 0, 0, {}))
        self._audit(user_id, "fetch_all_metadata.started")
        return metadata_fetch_row(_metadata_row(run)), lambda: self.run_metadata_fetch(
            user_id, run_id, provider_key
        )

    def metadata_fetch_status(self, user_id: str, run_id: str) -> JsonRow:
        run = self._metadata.status(user_id=user_id, run_id=run_id)
        if run is None:
            raise HostedApplicationError(404, "metadata_run_not_found")
        return metadata_fetch_row(_metadata_row(run))

    def run_metadata_fetch(self, user_id: str, run_id: str, provider_key: str) -> None:
        def update_progress(completed: int, total: int, skipped: int) -> None:
            percent = round((completed / total) * 100) if total else 0
            current = self._metadata.status(user_id=user_id, run_id=run_id)
            if current is not None:
                self._metadata.update(
                    MetadataRun(
                        run_id,
                        user_id,
                        "running",
                        total,
                        completed,
                        skipped,
                        percent,
                        current.summary,
                    )
                )

        try:
            summary = self.runtime.run_metadata(
                provider_key=provider_key,
                concurrency=self.runtime.process_cpu_count(),
                on_progress=update_progress,
            )
        except HostedRuntimeError as error:
            self._fail_metadata_fetch(user_id, run_id, error.code)
            return
        except Exception:
            self._fail_metadata_fetch(user_id, run_id, "metadata_fetch_failed")
            return
        revision_id = opaque_id("metadata-revision", stable_hash(summary))
        self._metadata.set_revision(user_id=user_id, revision_id=revision_id)
        current = self._metadata.status(user_id=user_id, run_id=run_id)
        if current is not None:
            self._metadata.update(
                MetadataRun(
                    run_id,
                    user_id,
                    "succeeded",
                    current.total,
                    current.completed,
                    int(summary["skipped_exchange_count"]),
                    100,
                    {
                        "row_count": int(summary["all_isins_rows"]),
                        "exchange_count": int(summary["exchange_count"]),
                        "requested_exchange_count": int(summary["requested_exchange_count"]),
                        "skipped_exchanges": list(summary["skipped_exchanges"]),
                    },
                )
            )
        self._audit(user_id, "fetch_all_metadata.completed")

    def _fail_metadata_fetch(self, user_id: str, run_id: str, code: str) -> None:
        current = self._metadata.status(user_id=user_id, run_id=run_id)
        if current is not None:
            self._metadata.update(
                MetadataRun(
                    run_id,
                    user_id,
                    "failed",
                    current.total,
                    current.completed,
                    current.skipped_exchange_count,
                    current.percent,
                    {**current.summary, "error_code": code},
                )
            )
        self._audit(user_id, "fetch_all_metadata.failed")

    def create_project_from_criteria(
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
            raise HostedApplicationError(422, "metadata_builder_required")
        selected_rows = _unique_listings(filter_rows(self._all_isins_rows(), predicates))
        if not selected_rows:
            raise HostedApplicationError(422, "metadata_builder_empty")
        project_name = (
            "_".join(
                part
                for part in ("_".join(value.strip().casefold().split()) for _, _, value in values)
                if part
            )
            or "metadata_builder_project"
        )
        operation = f"metadata-builder-project:{project_name}"
        request_hash = stable_hash({"operation": operation, "members": selected_rows})
        cached = (
            self._metadata.idempotent_response(
                user_id=user_id, operation=operation, key=idempotency_key, request_hash=request_hash
            )
            if idempotency_key is not None
            else None
        )
        if cached is not None:
            project = self._project(user_id, cached)
            selection = self._selection_for_project(user_id, project.project_id)
            self._projects.set_current_project(user_id=user_id, project_id=project.project_id)
            return self._project_selection_row(project, selection)
        project_id = str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"portfell:project:{user_id}:{project_name}")
        )
        project = self._record(
            self._projects.create_project(TenantProject(project_id, user_id, project_name))
        )
        members = tuple(f"{row['isin']}:{row['exchange']}:{row['code']}" for row in selected_rows)
        selection_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"portfell:selection:{user_id}:{project_id}:{project_name}:{members}",
            )
        )
        selection = self._selection_record(
            self._selections.create(
                TenantSelection(
                    selection_id,
                    project_id,
                    user_id,
                    project_name,
                    members,
                    tuple(predicate.as_text() for predicate in predicates),
                )
            )
        )
        self._projects.set_current_project(user_id=user_id, project_id=project_id)
        self.runtime.write_metadata_selection(selection_id, selected_rows, predicates)
        bootstrap = (
            None
            if self._bootstrap is None
            else self._bootstrap.start(
                user_id=user_id,
                project_id=project_id,
                selection_id=selection_id,
                member_ids=selection.member_ids,
            )
        )
        if idempotency_key is not None:
            self._metadata.remember_idempotency(
                user_id=user_id,
                operation=operation,
                key=idempotency_key,
                request_hash=request_hash,
                response_ref=project_id,
            )
        self._audit(user_id, "metadata_builder.project.create")
        result = self._project_selection_row(project, selection)
        if bootstrap is not None:
            result["initial_fill"] = {
                "bootstrap_id": bootstrap.bootstrap.bootstrap_id,
                "job_id": bootstrap.job_id,
                "status": bootstrap.bootstrap.status,
                "completed_units": 0,
                "total_units": bootstrap.bootstrap.selected_listing_count,
                "selected_listing_count": bootstrap.bootstrap.selected_listing_count,
                "terminal_code": None,
                "started_at": None,
            }
        return result

    @staticmethod
    def _project_selection_row(project: ProjectRecord, selection: SelectionRecord) -> JsonRow:
        return {
            "project": project_row(project),
            "selection": selection_row(selection),
            "selected_count": _unique_isin_count(selection.member_ids),
        }

    def project_criteria_row(self, project: ProjectRecord, selection: SelectionRecord) -> JsonRow:
        fields: JsonRow = {
            "exchange": "",
            "instrument_type": "",
            "country": "",
            "currency": "",
            "name": "",
        }
        try:
            predicates = parse_predicates(list(selection.metadata_builder_predicates))
        except ValueError as error:
            raise HostedApplicationError(500, "metadata_builder_manifest_invalid") from error
        for predicate in predicates:
            if predicate.field == "name" and predicate.operator == "~":
                fields["name"] = predicate.expected
            elif predicate.field in fields and predicate.operator == "=":
                fields[predicate.field] = predicate.expected
        return {
            "project_id": project.project_id,
            "selection_id": selection.selection_id,
            "selected_count": _unique_isin_count(selection.member_ids),
            **fields,
        }

    def initial_fill_status(self, user_id: str, project_id: str) -> JsonRow:
        """Return the owned bootstrap lifecycle without exposing shared inventory."""

        self._project(user_id, project_id)
        if self._bootstrap is None:
            raise HostedApplicationError(404, "initial_fill_not_found")
        status = self._bootstrap.status(user_id=user_id, project_id=project_id)
        if status is None:
            raise HostedApplicationError(404, "initial_fill_not_found")
        return {
            "bootstrap_id": status.bootstrap.bootstrap.bootstrap_id,
            "job_id": status.bootstrap.job_id,
            "status": status.status,
            "completed_units": status.completed_units,
            "total_units": status.total_units,
            "selected_listing_count": status.bootstrap.bootstrap.selected_listing_count,
            "terminal_code": status.terminal_code,
            "started_at": status.started_at_epoch,
            "last_progress_at": status.last_progress_at_epoch,
        }

    @staticmethod
    def _record(project: TenantProject) -> ProjectRecord:
        return ProjectRecord(project.project_id, project.user_id, project.name)

    def _project(self, user_id: str, project_id: str) -> ProjectRecord:
        for project in self._projects.list_projects(user_id):
            if project.project_id == project_id:
                return self._record(project)
        raise HostedApplicationError(404, "not_found")

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


def _metadata_row(run: MetadataRun) -> JsonRow:
    return {
        "metadata_run_id": run.metadata_run_id,
        "user_id": run.user_id,
        "status": run.status,
        "total": run.total,
        "completed": run.completed,
        "skipped_exchange_count": run.skipped_exchange_count,
        "percent": run.percent,
        **run.summary,
    }


def _unique_listings(rows: list[JsonRow]) -> list[JsonRow]:
    """Keep one canonical ticker for each valid ISIN/Exchange instrument."""

    canonical: dict[tuple[str, str], JsonRow] = {}
    for row in sorted(
        rows,
        key=lambda value: (
            str(value.get("isin", "")),
            str(value.get("exchange", "")),
            str(value.get("code", "")),
        ),
    ):
        isin = str(row.get("isin", "")).strip()
        exchange = str(row.get("exchange", "")).strip()
        code = str(row.get("code", "")).strip()
        if isin and exchange and code:
            canonical.setdefault((isin, exchange), row)
    return list(canonical.values())


def _unique_isin_count(member_ids: tuple[str, ...]) -> int:
    """Count selected instruments independently of exchange/code aliases."""

    return len({member_id.split(":", 1)[0] for member_id in member_ids if member_id})
