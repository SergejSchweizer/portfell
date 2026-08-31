"""Clean single-workspace metadata route adapters."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from fastapi import APIRouter, HTTPException, Query

from portfell.app_services.research import ApplicationServiceError
from portfell.table_io import JsonRow


class MetadataApplicationService(Protocol):
    def workflow_state(self) -> JsonRow: ...
    def metadata_options(self) -> JsonRow: ...
    def active_listings(
        self,
        *,
        exchange: str | None = None,
        instrument_type: str | None = None,
        country: str | None = None,
        currency: str | None = None,
    ) -> tuple[JsonRow, ...]: ...
    def create_metadata_universe(
        self,
        *,
        exchange: str | None = None,
        instrument_type: str | None = None,
        country: str | None = None,
        currency: str | None = None,
    ) -> object: ...
    def metadata_universe(self, universe_id: str) -> JsonRow: ...
    def metadata_history(self) -> tuple[JsonRow, ...]: ...


def _typed_call[ReturnT](operation: Callable[..., ReturnT], *args: Any, **kwargs: Any) -> ReturnT:
    try:
        return operation(*args, **kwargs)
    except ApplicationServiceError as error:
        status = 404 if error.code.endswith("not_found") else 422
        raise HTTPException(status_code=status, detail={"code": error.code}) from error


def _payload_value(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value.strip() else None


def metadata_project_router(service: MetadataApplicationService) -> APIRouter:
    """Expose clean metadata/workflow reads without user, tenant, or legacy DB authority."""
    router = APIRouter(prefix="/api")

    @router.get("/health")
    def health() -> JsonRow:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok", "database": "portfell_dash", "workspace": "default"}

    @router.get("/workflow")
    def workflow() -> JsonRow:  # pyright: ignore[reportUnusedFunction]
        return _typed_call(service.workflow_state)

    @router.get("/metadata/options")
    def metadata_options() -> JsonRow:  # pyright: ignore[reportUnusedFunction]
        return _typed_call(service.metadata_options)

    @router.get("/metadata/listings")
    def active_listings(  # pyright: ignore[reportUnusedFunction]
        exchange: str | None = Query(default=None),
        instrument_type: str | None = Query(default=None),
        country: str | None = Query(default=None),
        currency: str | None = Query(default=None),
    ) -> JsonRow:
        items = _typed_call(
            service.active_listings,
            exchange=exchange,
            instrument_type=instrument_type,
            country=country,
            currency=currency,
        )
        return {"items": list(items), "total": len(items)}

    @router.post("/metadata/universes")
    def create_metadata_universe(  # pyright: ignore[reportUnusedFunction]
        payload: dict[str, object],
    ) -> JsonRow:
        created = _typed_call(
            service.create_metadata_universe,
            exchange=_payload_value(payload, "exchange"),
            instrument_type=_payload_value(payload, "instrument_type"),
            country=_payload_value(payload, "country"),
            currency=_payload_value(payload, "currency"),
        )
        universe_id = getattr(created, "universe_id", None)
        if not isinstance(universe_id, str):
            raise HTTPException(status_code=500, detail={"code": "app_state_contract_mismatch"})
        return _typed_call(service.metadata_universe, universe_id)

    @router.get("/metadata/universes/{universe_id}")
    def metadata_universe(universe_id: str) -> JsonRow:  # pyright: ignore[reportUnusedFunction]
        return _typed_call(service.metadata_universe, universe_id)

    @router.get("/metadata/history")
    def metadata_history() -> JsonRow:  # pyright: ignore[reportUnusedFunction]
        items = _typed_call(service.metadata_history)
        return {"items": list(items), "total": len(items)}

    return router
