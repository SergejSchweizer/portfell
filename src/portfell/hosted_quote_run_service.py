"""Quote-run application service."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import replace

from portfell.entitlements import ProviderDownloadRun, publish_user_data_snapshot
from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_api_ports import HostedRuntimePort
from portfell.hosted_api_serializers import quote_run_row
from portfell.hosted_api_service_support import (
    opaque_id,
    stable_hash,
)
from portfell.hosted_api_state import HostedApiState, SelectionRecord
from portfell.hosted_audit_event_repository import AuditEventRepository, HostedAuditEvent
from portfell.hosted_credentials import CredentialVaultError, EodhdCredentialVault
from portfell.hosted_idempotency_repository import (
    IdempotencyRepository,
    LocalIdempotencyRepository,
)
from portfell.hosted_local_audit_event_repository import LocalAuditEventRepository
from portfell.hosted_local_project_repository import LocalProjectRepository
from portfell.hosted_local_selection_repository import LocalSelectionRepository
from portfell.hosted_quote_lifecycle_repository import (
    LocalQuoteLifecycleRepository,
    QuoteLifecycleRepository,
)
from portfell.hosted_repository_importer import ProjectRepository, TenantSelection
from portfell.hosted_selection_repository import SelectionRepository
from portfell.hosted_shared_quote_publisher import SharedQuotePublisher
from portfell.hosted_workspace_repository import persist_local_workspace
from portfell.table_io import JsonRow

LOGGER = logging.getLogger(__name__)


class QuoteRunService:
    """Own quote-run planning, execution, progress, and scoped rows."""

    def __init__(
        self,
        state: HostedApiState,
        runtime: HostedRuntimePort,
        project_repository: ProjectRepository | None = None,
        selection_repository: SelectionRepository | None = None,
        credential_vault: EodhdCredentialVault | None = None,
        quote_repository: QuoteLifecycleRepository | None = None,
        audit_repository: AuditEventRepository | None = None,
        idempotency_repository: IdempotencyRepository | None = None,
        quote_publisher: SharedQuotePublisher | None = None,
    ) -> None:
        self.state = state
        self.runtime = runtime
        self._projects = project_repository or LocalProjectRepository(state)
        self._selections = selection_repository or LocalSelectionRepository(state)
        self._credentials = credential_vault or state.credential_vault()
        self._quotes = quote_repository or LocalQuoteLifecycleRepository(state)
        self._audit_events = audit_repository or LocalAuditEventRepository(state)
        self._idempotency = idempotency_repository or LocalIdempotencyRepository(state)
        self._quote_publisher = quote_publisher or (
            None
            if state.shared_market_data_store is None
            else SharedQuotePublisher(state.shared_market_data_store)
        )

    def start(
        self,
        user_id: str,
        *,
        project_id: str | None,
        selection_id: str | None,
        idempotency_key: str | None,
    ) -> tuple[JsonRow, Callable[[], None] | None]:
        if selection_id is not None:
            selection = self._selection_by_id(user_id, selection_id)
            project_id = selection.project_id
        elif project_id is not None:
            selection = self._selection_for_project(user_id, project_id)
        else:
            raise HostedApplicationError(422, "metadata_selection_required")
        self._require_project(user_id, project_id)
        request_hash = stable_hash(
            {
                "project_id": project_id,
                "selection_id": selection.selection_id,
                "member_ids": list(selection.member_ids),
            }
        )
        operation = f"fetch-all-quotes:{project_id}"
        cached = self._idempotency.lookup(
            user_id=user_id,
            operation=operation,
            key=idempotency_key,
            request_hash=request_hash,
        )
        if cached is not None:
            return self.status(user_id, cached), None
        run_id = opaque_id("fetch-all-quotes", f"{user_id}:{request_hash}")
        active = self._quotes.get(user_id=user_id, run_id=run_id)
        if active is not None and active.status == "running":
            self._idempotency.remember(
                user_id=user_id,
                operation=operation,
                key=idempotency_key,
                request_hash=request_hash,
                response_ref=active.download_run_id,
            )
            return self.status(user_id, active.download_run_id), None
        try:
            credential = self._credentials.status(user_id=user_id)
            provider_key = self._credentials.unwrap_for_provider_call(user_id=user_id)
        except CredentialVaultError as error:
            raise HostedApplicationError(422, "eodhd_credential_required") from error
        run = ProviderDownloadRun(
            download_run_id=run_id,
            user_id=user_id,
            credential_id=credential.credential_id,
            provider="eodhd",
            status="running",
            returned_observation_ids=selection.member_ids,
            request_hash=request_hash,
            requested_scope={
                "project_id": project_id,
                "selection_id": selection.selection_id,
                "member_ids": list(selection.member_ids),
            },
        )
        progress = {
            "total": len(selection.member_ids) * 3 + 1,
            "completed": 0,
            "failed": 0,
            "percent": 0,
            "progress": 0,
            "started_at": time.time(),
            "selected_listing_count": len(selection.member_ids),
        }
        self._quotes.create(run, progress=progress)
        self._idempotency.remember(
            user_id=user_id,
            operation=operation,
            key=idempotency_key,
            request_hash=request_hash,
            response_ref=run_id,
        )
        self._audit(user_id, "fetch_all_quotes.started")
        return self.status(user_id, run_id), lambda: self.run_quote_fetch(
            run, selection.selection_id, provider_key
        )

    def status(self, user_id: str, run_id: str) -> JsonRow:
        run = self._quotes.get(user_id=user_id, run_id=run_id)
        if run is None:
            raise HostedApplicationError(404, "not_found")
        return quote_run_row(run, summary=self._quotes.progress(user_id=user_id, run_id=run_id))

    def run_quote_fetch(
        self, run: ProviderDownloadRun, selection_id: str, provider_key: str
    ) -> None:
        last_persisted_at = 0.0

        def update_progress(completed: int, total: int, failed: int) -> None:
            nonlocal last_persisted_at
            percent = (
                min(99, max(1, round((completed / total) * 100))) if completed and total else 0
            )
            previous = self._quotes.progress(user_id=run.user_id, run_id=run.download_run_id) or {}
            self._quotes.update(
                run,
                progress={
                    **previous,
                    "completed": completed,
                    "failed": failed,
                    "percent": percent,
                    "progress": percent,
                    "total": total,
                },
            )
            should_persist = time.monotonic() - last_persisted_at >= 5.0
            if self.state.workspace_store is not None and should_persist:
                persist_local_workspace(self.state)
                last_persisted_at = time.monotonic()

        try:
            summary = self.runtime.run_quotes(
                provider_key=provider_key,
                run_id=opaque_id("fetch-all-quotes", run.request_hash),
                selection_id=selection_id,
                concurrency=self.runtime.process_cpu_count(),
                on_progress=update_progress,
            )
        except Exception as error:
            LOGGER.exception("Quote download failed for selection %s", selection_id)
            failed_run = replace(run, status="failed")
            previous = self._quotes.progress(user_id=run.user_id, run_id=run.download_run_id) or {}
            self._quotes.update(
                failed_run,
                progress={
                    **previous,
                    "percent": 0,
                    "progress": 0,
                    "error_code": f"quote_download_{type(error).__name__.lower()}",
                },
            )
            self._audit(run.user_id, "fetch_all_quotes.failed")
            return
        scoped_rows = tuple(dict(row) for row in summary.pop("scoped_quote_rows", ()))
        if self._quote_publisher is not None:
            self._quote_publisher.publish(scoped_rows)
        progress = self._quotes.progress(user_id=run.user_id, run_id=run.download_run_id) or {}
        failed = int(progress["failed"])
        completed_run = replace(run, status="partial" if failed else "succeeded")
        terminal_progress = {
            **summary,
            "completed": int(progress["completed"]),
            "failed": failed,
            "percent": 100,
            "progress": 100,
            "started_at": float(progress.get("started_at", time.time())),
            "total": int(progress["total"]),
        }
        self._quotes.update(completed_run, progress=terminal_progress)
        # Compatibility cache only: persistent consumers read the canonical store.
        if self._quote_publisher is None:
            self.state.quote_rows_by_run_id[run.download_run_id] = scoped_rows
        if completed_run.status == "succeeded":
            publish_user_data_snapshot(store=self.state.entitlements, run=completed_run)
        self._audit(run.user_id, "fetch_all_quotes.completed")

    def _require_project(self, user_id: str, project_id: str) -> None:
        if not any(
            project.project_id == project_id for project in self._projects.list_projects(user_id)
        ):
            raise HostedApplicationError(404, "not_found")

    def _selection_by_id(self, user_id: str, selection_id: str) -> SelectionRecord:
        selection = self._selections.by_id(selection_id=selection_id, user_id=user_id)
        if selection is None:
            raise HostedApplicationError(404, "not_found")
        return self._selection_record(selection)

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
