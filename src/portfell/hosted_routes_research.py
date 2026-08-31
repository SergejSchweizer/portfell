"""Clean single-workspace research route adapters."""

from __future__ import annotations

from typing import Protocol, cast

from fastapi import APIRouter, HTTPException, Query

from portfell.app_services.research import ApplicationServiceError
from portfell.app_state.contracts import UnivariateSelectionRecord
from portfell.table_io import JsonRow


class ResearchApplicationPort(Protocol):
    def run_univariate(self, universe_id: str) -> JsonRow: ...
    def create_univariate_selection(
        self, run_id: str, *, predicates: list[dict[str, object]] | None = None
    ) -> UnivariateSelectionRecord: ...
    def run_bivariate(self, selection_id: str) -> JsonRow: ...
    def run_multivariate(
        self,
        *,
        selection_id: str,
        bivariate_run_id: str,
        objective: str = "return_risk",
    ) -> JsonRow: ...
    def run_detail(self, run_id: str) -> JsonRow: ...
    def stage_history(self, stage: str, *, limit: int = 100) -> tuple[JsonRow, ...]: ...


def _error(error: ApplicationServiceError) -> HTTPException:
    status = 404 if error.code.endswith("not_found") else 409 if "not_ready" in error.code else 422
    return HTTPException(status_code=status, detail={"code": error.code})


def _required_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=422, detail={"code": f"{key}_required"})
    return value


def _predicates(payload: dict[str, object]) -> list[dict[str, object]] | None:
    raw = payload.get("predicates")
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise HTTPException(status_code=422, detail={"code": "predicates_invalid"})
    items = cast(list[object], raw)
    if not all(isinstance(item, dict) for item in items):
        raise HTTPException(status_code=422, detail={"code": "predicates_invalid"})
    return [cast(dict[str, object], item) for item in items]


def research_router(service: ResearchApplicationPort) -> APIRouter:
    """Expose the four analytical stages over the clean application service only."""
    router = APIRouter(prefix="/api")

    @router.post("/univariate/runs")
    def run_univariate(payload: dict[str, object]) -> JsonRow:  # pyright: ignore[reportUnusedFunction]
        try:
            return service.run_univariate(_required_string(payload, "universe_id"))
        except ApplicationServiceError as error:
            raise _error(error) from error

    @router.post("/univariate/selections")
    def create_univariate_selection(  # pyright: ignore[reportUnusedFunction]
        payload: dict[str, object],
    ) -> JsonRow:
        try:
            selection = service.create_univariate_selection(
                _required_string(payload, "run_id"), predicates=_predicates(payload)
            )
        except ApplicationServiceError as error:
            raise _error(error) from error
        return {
            "selection_id": selection.selection_id,
            "source_run_id": selection.source_run_id,
            "version": selection.version,
            "content_hash": selection.content_hash,
            "members": [
                {"isin": item.isin, "exchange": item.exchange, "code": item.code}
                for item in selection.members
            ],
        }

    @router.post("/bivariate/runs")
    def run_bivariate(payload: dict[str, object]) -> JsonRow:  # pyright: ignore[reportUnusedFunction]
        try:
            return service.run_bivariate(_required_string(payload, "selection_id"))
        except ApplicationServiceError as error:
            raise _error(error) from error

    @router.post("/multivariate/runs")
    def run_multivariate(payload: dict[str, object]) -> JsonRow:  # pyright: ignore[reportUnusedFunction]
        objective_value = payload.get("objective", "return_risk")
        if not isinstance(objective_value, str):
            raise HTTPException(status_code=422, detail={"code": "objective_invalid"})
        try:
            return service.run_multivariate(
                selection_id=_required_string(payload, "selection_id"),
                bivariate_run_id=_required_string(payload, "bivariate_run_id"),
                objective=objective_value,
            )
        except ApplicationServiceError as error:
            raise _error(error) from error

    @router.get("/runs/{run_id}")
    def run_detail(run_id: str) -> JsonRow:  # pyright: ignore[reportUnusedFunction]
        try:
            return service.run_detail(run_id)
        except ApplicationServiceError as error:
            raise _error(error) from error

    @router.get("/runs")
    def stage_history(  # pyright: ignore[reportUnusedFunction]
        stage: str = Query(...), limit: int = Query(default=100, ge=1, le=500)
    ) -> JsonRow:
        if stage not in {"univariate", "bivariate", "multivariate"}:
            raise HTTPException(status_code=422, detail={"code": "stage_invalid"})
        try:
            items = service.stage_history(stage, limit=limit)
        except ApplicationServiceError as error:
            raise _error(error) from error
        return {"items": list(items), "total": len(items)}

    return router
