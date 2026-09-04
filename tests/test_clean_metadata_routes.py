from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient

from portfell.app_services.research import ApplicationServiceError
from portfell.modules.metadata import metadata_router
from portfell.table_io import JsonRow


@dataclass(frozen=True)
class _CreatedUniverse:
    universe_id: str


class _MetadataService:
    def workflow_state(self) -> JsonRow:
        return {"stage": "metadata"}

    def metadata_options(self) -> JsonRow:
        return {"exchanges": ["XETRA"]}

    def active_listings(self, **filters: str | None) -> tuple[JsonRow, ...]:
        assert filters == {
            "exchange": "XETRA",
            "instrument_type": None,
            "country": None,
            "currency": None,
        }
        return ({"isin": "IE00QA000001"},)

    def create_metadata_universe(self, **filters: str | None) -> _CreatedUniverse:
        assert filters == {
            "exchange": "XETRA",
            "instrument_type": None,
            "country": None,
            "currency": None,
        }
        return _CreatedUniverse("universe-1")

    def metadata_universe(self, universe_id: str) -> JsonRow:
        if universe_id == "missing":
            raise ApplicationServiceError("universe_not_found")
        return {"universe_id": universe_id}

    def metadata_history(self) -> tuple[JsonRow, ...]:
        return ({"universe_id": "universe-1"},)


def test_clean_metadata_routes_expose_single_workspace_contract() -> None:
    application = FastAPI()
    application.include_router(metadata_router(_MetadataService()))
    client = TestClient(application)

    assert client.get("/api/metadata/workflow").json() == {"stage": "metadata"}
    assert client.get("/api/metadata/options").json() == {"exchanges": ["XETRA"]}
    assert client.get("/api/metadata/listings?exchange=XETRA").json() == {
        "items": [{"isin": "IE00QA000001"}],
        "total": 1,
    }
    assert client.post("/api/metadata/universes", json={"exchange": "XETRA"}).json() == {
        "universe_id": "universe-1"
    }
    assert client.get("/api/metadata/universes/universe-1").json() == {"universe_id": "universe-1"}
    assert client.get("/api/metadata/history").json() == {
        "items": [{"universe_id": "universe-1"}],
        "total": 1,
    }
    response = client.get("/api/metadata/universes/missing")
    assert response.status_code == 404
