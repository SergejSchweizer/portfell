"""Quote-run route registration."""

# pyright: reportUnusedFunction=false
# ruff: noqa: B008

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, BackgroundTasks, Depends, Header

from portfell.hosted_api_contracts import LoadSelectedIsinsRequest
from portfell.hosted_api_state import ApiUser
from portfell.hosted_quote_run_service import QuoteRunService
from portfell.hosted_routes_common import JsonRow, call


def quote_run_router(
    service: QuoteRunService,
    *,
    current_user: Callable[[], ApiUser],
    workspace_user: Callable[[], ApiUser],
) -> APIRouter:
    """Build quote-run routes around the quote application service."""

    router = APIRouter()

    @router.post("/quote-runs")
    def start_quote_run(
        payload: LoadSelectedIsinsRequest,
        background_tasks: BackgroundTasks,
        user: ApiUser = Depends(workspace_user),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JsonRow:
        row, task = call(
            service.start,
            user.user_id,
            project_id=payload.project_id,
            selection_id=payload.metadata_selection_id,
            idempotency_key=idempotency_key,
        )
        if task is not None:
            background_tasks.add_task(task)
        return row

    @router.get("/quote-runs/{quote_run_id}")
    def quote_run_status(quote_run_id: str, user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(service.status, user.user_id, quote_run_id)

    return router
