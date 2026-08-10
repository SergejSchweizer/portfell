"""Quote-run application service."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import replace

from portfell.entitlements import ProviderDownloadRun, publish_user_data_snapshot
from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_api_ports import HostedRuntimePort
from portfell.hosted_api_serializers import quote_run_row
from portfell.hosted_api_service_support import (
    audit,
    idempotent_response,
    opaque_id,
    remember_idempotency,
    require_user_row,
    selection_for_project,
    stable_hash,
)
from portfell.hosted_api_state import HostedApiState
from portfell.hosted_credentials import CredentialVaultError
from portfell.hosted_workspace_repository import persist_local_workspace
from portfell.shared_market_data import SharedListingKey
from portfell.table_io import JsonRow

LOGGER = logging.getLogger(__name__)


class QuoteRunService:
    """Own quote-run planning, execution, progress, and scoped rows."""

    def __init__(self, state: HostedApiState, runtime: HostedRuntimePort) -> None:
        self.state = state
        self.runtime = runtime

    def start(
        self,
        user_id: str,
        *,
        project_id: str | None,
        selection_id: str | None,
        idempotency_key: str | None,
    ) -> tuple[JsonRow, Callable[[], None] | None]:
        if selection_id is not None:
            selection = require_user_row(self.state.selections_by_id, selection_id, user_id)
            project_id = selection.project_id
        elif project_id is not None:
            require_user_row(self.state.projects_by_id, project_id, user_id)
            selection = selection_for_project(self.state, project_id, user_id)
        else:
            raise HostedApplicationError(422, "metadata_selection_required")
        operation = f"fetch-all-quotes:{project_id}"
        cached = idempotent_response(
            self.state,
            user_id=user_id,
            operation=operation,
            idempotency_key=idempotency_key,
        )
        if cached is not None:
            return self.status(user_id, cached), None
        request_hash = stable_hash(
            {
                "project_id": project_id,
                "selection_id": selection.selection_id,
                "member_ids": list(selection.member_ids),
            }
        )
        run_id = opaque_id("fetch-all-quotes", f"{user_id}:{request_hash}")
        active = self.state.downloads_by_id.get(run_id)
        if active is not None and active.status == "running":
            remember_idempotency(
                self.state, user_id, operation, idempotency_key, active.download_run_id
            )
            return self.status(user_id, active.download_run_id), None
        try:
            provider_key = self.state.credential_vault().unwrap_for_provider_call(user_id=user_id)
        except CredentialVaultError as error:
            raise HostedApplicationError(422, "eodhd_credential_required") from error
        run = ProviderDownloadRun(
            download_run_id=run_id,
            user_id=user_id,
            credential_id="project-selection",
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
        self.state.downloads_by_id[run_id] = run
        self.state.download_summaries_by_id[run_id] = {
            "total": len(selection.member_ids) * 3 + 1,
            "completed": 0,
            "failed": 0,
            "percent": 0,
            "progress": 0,
            "started_at": time.time(),
            "selected_listing_count": len(selection.member_ids),
        }
        remember_idempotency(self.state, user_id, operation, idempotency_key, run_id)
        audit(self.state, user_id, "fetch_all_quotes.started")
        return self.status(user_id, run_id), lambda: self.run_quote_fetch(
            run, selection.selection_id, provider_key
        )

    def status(self, user_id: str, run_id: str) -> JsonRow:
        run = require_user_row(self.state.downloads_by_id, run_id, user_id)
        return quote_run_row(
            run, summary=self.state.download_summaries_by_id.get(run.download_run_id)
        )

    def run_quote_fetch(
        self, run: ProviderDownloadRun, selection_id: str, provider_key: str
    ) -> None:
        last_persisted_at = 0.0

        def update_progress(completed: int, total: int, failed: int) -> None:
            nonlocal last_persisted_at
            percent = (
                min(99, max(1, round((completed / total) * 100))) if completed and total else 0
            )
            self.state.download_summaries_by_id[run.download_run_id] = {
                **self.state.download_summaries_by_id[run.download_run_id],
                "completed": completed,
                "failed": failed,
                "percent": percent,
                "progress": percent,
                "total": total,
            }
            if time.monotonic() - last_persisted_at >= 5.0:
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
            self.state.downloads_by_id[run.download_run_id] = replace(run, status="failed")
            self.state.download_summaries_by_id[run.download_run_id] = {
                **self.state.download_summaries_by_id[run.download_run_id],
                "percent": 0,
                "progress": 0,
                "error_code": f"quote_download_{type(error).__name__.lower()}",
            }
            audit(self.state, run.user_id, "fetch_all_quotes.failed")
            return
        scoped_rows = tuple(dict(row) for row in summary.pop("scoped_quote_rows", ()))
        if self.state.shared_market_data_store is not None:
            rows_by_listing: dict[SharedListingKey, list[JsonRow]] = {}
            for row in scoped_rows:
                listing = SharedListingKey.from_row(row)
                rows_by_listing.setdefault(listing, []).append(row)
            for listing, rows in rows_by_listing.items():
                self.state.shared_market_data_store.upsert("quotes", listing, rows)
        progress = self.state.download_summaries_by_id[run.download_run_id]
        failed = int(progress["failed"])
        completed_run = replace(run, status="partial" if failed else "succeeded")
        self.state.downloads_by_id[run.download_run_id] = completed_run
        # Compatibility cache only: persistent consumers read the canonical store.
        if self.state.shared_market_data_store is None:
            self.state.quote_rows_by_run_id[run.download_run_id] = scoped_rows
        self.state.download_summaries_by_id[run.download_run_id] = {
            **summary,
            "completed": int(progress["completed"]),
            "failed": failed,
            "percent": 100,
            "progress": 100,
            "started_at": float(progress.get("started_at", time.time())),
            "total": int(progress["total"]),
        }
        if completed_run.status == "succeeded":
            publish_user_data_snapshot(store=self.state.entitlements, run=completed_run)
        audit(self.state, run.user_id, "fetch_all_quotes.completed")
