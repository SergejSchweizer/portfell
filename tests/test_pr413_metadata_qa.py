"""Black-box Metadata REST and viewport acceptance checks."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from metadata_oracle import expected_option_counts, expected_unique_isins

from portfell.dash_app.visual_contract import VISUAL_VIEWPORTS
from portfell.modules.metadata import metadata_router


class OracleService:
    def workflow_state(self) -> dict[str, object]:
        return {"stage": "metadata"}

    def metadata_options(self) -> dict[str, object]:
        return expected_option_counts()

    def active_listings(self, **filters: str | None) -> tuple[dict[str, object], ...]:
        count = expected_unique_isins(**filters)
        return tuple({"isin": f"fixture-{index}"} for index in range(count))

    def create_metadata_universe(self, **_: str | None) -> object:
        return type("Universe", (), {"universe_id": "oracle-universe"})()

    def metadata_universe(self, universe_id: str) -> dict[str, object]:
        return {"universe_id": universe_id}

    def metadata_history(self) -> tuple[dict[str, object], ...]:
        return ()


def test_metadata_openapi_is_metadata_only_and_counts_follow_previous_filters() -> None:
    app = FastAPI()
    app.include_router(metadata_router(OracleService()))
    client = TestClient(app)
    paths = set(client.get("/openapi.json").json()["paths"])
    assert paths == {
        "/api/metadata/workflow",
        "/api/metadata/options",
        "/api/metadata/listings",
        "/api/metadata/universes",
        "/api/metadata/universes/{universe_id}",
        "/api/metadata/history",
    }
    assert client.get("/api/metadata/listings?exchange=XETRA").json()["total"] == 2
    assert client.get("/api/metadata/listings?exchange=XETRA&country=FR").json()["total"] == 0


def test_metadata_browser_contract_covers_required_viewports() -> None:
    assert {(viewport.width, viewport.height) for viewport in VISUAL_VIEWPORTS} >= {
        (1440, 900),
        (1024, 768),
        (390, 844),
    }
