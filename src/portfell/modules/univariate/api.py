"""Univariate-only FastAPI routes."""

from __future__ import annotations

from typing import Protocol, cast

from fastapi import APIRouter, HTTPException, Query

from portfell.app_state.contracts import UnivariateSelectionRecord
from portfell.modules.http import required_string, service_call
from portfell.table_io import JsonRow


class UnivariatePort(Protocol):
    def run_univariate(self, universe_id: str) -> JsonRow: ...
    def create_univariate_selection(
        self, run_id: str, *, predicates: list[dict[str, object]] | None = None
    ) -> UnivariateSelectionRecord: ...
    def run_detail(self, run_id: str) -> JsonRow: ...
    def stage_history(self, stage: str, *, limit: int = 100) -> tuple[JsonRow, ...]: ...


def _predicates(payload: dict[str, object]) -> list[dict[str, object]] | None:
    raw = payload.get("predicates")
    if raw is None:
        return None
    items = cast(list[object], raw) if isinstance(raw, list) else []
    if not isinstance(raw, list) or not all(isinstance(item, dict) for item in items):
        raise HTTPException(status_code=422, detail={"code": "predicates_invalid"})
    return cast(list[dict[str, object]], items)


def univariate_router(service: UnivariatePort) -> APIRouter:
    router = APIRouter(prefix="/api/univariate", tags=["univariate"])

    @router.post("/runs")
    def run(payload: dict[str, object]) -> JsonRow:  # pyright: ignore[reportUnusedFunction]
        return service_call(service.run_univariate, required_string(payload, "universe_id"))

    @router.get("/runs")
    def history(  # pyright: ignore[reportUnusedFunction]
        limit: int = Query(default=100, ge=1, le=500),
    ) -> JsonRow:
        items = service_call(service.stage_history, "univariate", limit=limit)
        return {"items": list(items), "total": len(items)}

    @router.get("/runs/{run_id}")
    def detail(run_id: str) -> JsonRow:  # pyright: ignore[reportUnusedFunction]
        return service_call(service.run_detail, run_id)

    @router.post("/selections")
    def selection(  # pyright: ignore[reportUnusedFunction]
        payload: dict[str, object],
    ) -> JsonRow:
        selected = service_call(
            service.create_univariate_selection,
            required_string(payload, "run_id"),
            predicates=_predicates(payload),
        )
        return {
            "selection_id": selected.selection_id,
            "source_run_id": selected.source_run_id,
            "version": selected.version,
            "content_hash": selected.content_hash,
            "members": [
                {"isin": item.isin, "exchange": item.exchange, "code": item.code}
                for item in selected.members
            ],
        }

    return router
