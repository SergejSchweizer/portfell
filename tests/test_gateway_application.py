"""PR420 stateless gateway routing and capability-boundary tests."""

from __future__ import annotations

import ast
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from portfell.services.gateway import GatewayApplication


def module_app(name: str) -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        return {"module": name, "status": "ok"}

    return app


def test_gateway_routes_exactly_four_modules_and_workflow_projection() -> None:
    app = GatewayApplication(
        modules={
            name: module_app(name)
            for name in ("metadata", "univariate", "bivariate", "multivariate")
        },
        workflow_reader=lambda: {"metadata_count": 2, "status": "succeeded"},
    ).create_app()
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok", "module": "gateway"}
    assert client.get("/api/workflow").json() == {"metadata_count": 2, "status": "succeeded"}
    assert client.get("/metadata/health").json() == {"module": "metadata", "status": "ok"}
    assert client.get("/unknown/health").status_code == 404


def test_gateway_rejects_missing_or_extra_module() -> None:
    modules = {name: module_app(name) for name in ("metadata", "univariate", "bivariate")}
    try:
        GatewayApplication(modules=modules, workflow_reader=lambda: {})
    except ValueError as error:
        assert str(error) == "gateway_requires_exactly_four_modules"
    else:
        raise AssertionError("gateway accepted an incomplete module set")


def test_gateway_source_has_no_calculation_or_repository_imports() -> None:
    tree = ast.parse(Path("src/portfell/services/gateway/app.py").read_text())
    forbidden = {"app_services", "portfolio", "statistics", "repository", "numpy", "polars"}
    imported = {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not imported & forbidden
