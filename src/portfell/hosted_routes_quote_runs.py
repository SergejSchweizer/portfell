"""Quote-run route registration."""

# pyright: reportUnusedFunction=false
# ruff: noqa: B008

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException

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
        user: ApiUser = Depends(workspace_user),
    ) -> JsonRow:
        _ = user
        raise HTTPException(
            status_code=410,
            detail="shared_market_refresh_required",
        )

    @router.get("/quote-runs/{quote_run_id}")
    def quote_run_status(quote_run_id: str, user: ApiUser = Depends(current_user)) -> JsonRow:
        return call(service.status, user.user_id, quote_run_id)

    return router
