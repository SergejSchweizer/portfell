"""Multivariate-only FastAPI routes."""

from __future__ import annotations

from typing import Protocol

from fastapi import APIRouter, HTTPException, Query

from portfell.modules.http import required_string, service_call
from portfell.table_io import JsonRow


class MultivariatePort(Protocol):
    def run_multivariate(
        self, *, selection_id: str, bivariate_run_id: str, objective: str = "return_risk"
    ) -> JsonRow: ...
    def run_detail(self, run_id: str) -> JsonRow: ...
    def stage_history(self, stage: str, *, limit: int = 100) -> tuple[JsonRow, ...]: ...


def multivariate_router(service: MultivariatePort) -> APIRouter:
    router = APIRouter(prefix="/api/multivariate", tags=["multivariate"])

    @router.post("/runs")
    def run(payload: dict[str, object]) -> JsonRow:  # pyright: ignore[reportUnusedFunction]
        objective = payload.get("objective", "return_risk")
        if not isinstance(objective, str):
            raise HTTPException(status_code=422, detail={"code": "objective_invalid"})
        return service_call(
            service.run_multivariate,
            selection_id=required_string(payload, "selection_id"),
            bivariate_run_id=required_string(payload, "bivariate_run_id"),
            objective=objective,
        )

    @router.get("/runs")
    def history(  # pyright: ignore[reportUnusedFunction]
        limit: int = Query(default=100, ge=1, le=500),
    ) -> JsonRow:
        items = service_call(service.stage_history, "multivariate", limit=limit)
        return {"items": list(items), "total": len(items)}

    @router.get("/runs/{run_id}")
    def detail(run_id: str) -> JsonRow:  # pyright: ignore[reportUnusedFunction]
        return service_call(service.run_detail, run_id)

    return router
