"""Bivariate-only FastAPI routes."""

from __future__ import annotations

from typing import Protocol

from fastapi import APIRouter, Query

from portfell.modules.http import required_string, service_call
from portfell.table_io import JsonRow


class BivariatePort(Protocol):
    def run_bivariate(self, selection_id: str) -> JsonRow: ...
    def run_detail(self, run_id: str) -> JsonRow: ...
    def stage_history(self, stage: str, *, limit: int = 100) -> tuple[JsonRow, ...]: ...


def bivariate_router(service: BivariatePort) -> APIRouter:
    router = APIRouter(prefix="/api/bivariate", tags=["bivariate"])

    @router.post("/runs")
    def run(payload: dict[str, object]) -> JsonRow:  # pyright: ignore[reportUnusedFunction]
        return service_call(service.run_bivariate, required_string(payload, "selection_id"))

    @router.get("/runs")
    def history(  # pyright: ignore[reportUnusedFunction]
        limit: int = Query(default=100, ge=1, le=500),
    ) -> JsonRow:
        items = service_call(service.stage_history, "bivariate", limit=limit)
        return {"items": list(items), "total": len(items)}

    @router.get("/runs/{run_id}")
    def detail(run_id: str) -> JsonRow:  # pyright: ignore[reportUnusedFunction]
        return service_call(service.run_detail, run_id)

    return router
