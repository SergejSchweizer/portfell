"""PR416 Bivariate process boundary and pair-input tests."""

from __future__ import annotations

import ast
from pathlib import Path

from fastapi.testclient import TestClient

from portfell.services.bivariate import BivariateApplication


class Service:
    def run_bivariate(self, selection_id: str) -> dict[str, object]:
        return {"run_id": f"run-for-{selection_id}"}

    def run_detail(self, run_id: str) -> dict[str, object]:
        return {"run_id": run_id}

    def stage_history(self, stage: str, *, limit: int = 100) -> tuple[dict[str, object], ...]:
        return ({"stage": stage, "limit": limit},)


def test_bivariate_app_exposes_only_bivariate_routes_and_health() -> None:
    client = TestClient(BivariateApplication(Service()).create_app())
    assert client.get("/health").json() == {"status": "ok", "module": "bivariate"}
    assert client.post("/api/bivariate/runs", json={"selection_id": "u-1"}).json() == {
        "run_id": "run-for-u-1"
    }
    assert client.get("/api/univariate/runs").status_code == 404


def test_bivariate_process_has_no_sibling_implementation_imports() -> None:
    forbidden = {"metadata", "univariate", "multivariate"}
    for path in Path("src/portfell/services/bivariate").glob("*.py"):
        tree = ast.parse(path.read_text())
        imports = {
            (node.module or "").split(".")[-1]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        assert not imports & forbidden
