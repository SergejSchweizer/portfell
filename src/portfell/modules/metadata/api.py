"""Metadata-only FastAPI routes."""

from __future__ import annotations

from typing import Protocol

from fastapi import APIRouter, Query

from portfell.modules.http import optional_string, service_call
from portfell.table_io import JsonRow


class MetadataPort(Protocol):
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


def metadata_router(service: MetadataPort) -> APIRouter:
    router = APIRouter(prefix="/api/metadata", tags=["metadata"])

    @router.get("/workflow")
    def workflow() -> JsonRow:  # pyright: ignore[reportUnusedFunction]
        return service_call(service.workflow_state)

    @router.get("/options")
    def options() -> JsonRow:  # pyright: ignore[reportUnusedFunction]
        return service_call(service.metadata_options)

    @router.get("/listings")
    def listings(  # pyright: ignore[reportUnusedFunction]
        exchange: str | None = Query(default=None),
        instrument_type: str | None = Query(default=None),
        country: str | None = Query(default=None),
        currency: str | None = Query(default=None),
    ) -> JsonRow:
        items = service_call(
            service.active_listings,
            exchange=exchange,
            instrument_type=instrument_type,
            country=country,
            currency=currency,
        )
        return {"items": list(items), "total": len(items)}

    @router.post("/universes")
    def create_universe(  # pyright: ignore[reportUnusedFunction]
        payload: dict[str, object],
    ) -> JsonRow:
        created = service_call(
            service.create_metadata_universe,
            exchange=optional_string(payload, "exchange"),
            instrument_type=optional_string(payload, "instrument_type"),
            country=optional_string(payload, "country"),
            currency=optional_string(payload, "currency"),
        )
        universe_id = getattr(created, "universe_id", None)
        if not isinstance(universe_id, str):
            from fastapi import HTTPException

            raise HTTPException(status_code=500, detail={"code": "app_state_contract_mismatch"})
        return service_call(service.metadata_universe, universe_id)

    @router.get("/universes/{universe_id}")
    def universe(universe_id: str) -> JsonRow:  # pyright: ignore[reportUnusedFunction]
        return service_call(service.metadata_universe, universe_id)

    @router.get("/history")
    def history() -> JsonRow:  # pyright: ignore[reportUnusedFunction]
        items = service_call(service.metadata_history)
        return {"items": list(items), "total": len(items)}

    return router
