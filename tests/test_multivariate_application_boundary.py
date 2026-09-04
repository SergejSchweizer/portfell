"""PR418 Multivariate process boundary and lineage tests."""

from __future__ import annotations

import ast
from pathlib import Path

from fastapi.testclient import TestClient

from portfell.services.multivariate import MultivariateApplication


class Service:
    def run_multivariate(
        self, *, selection_id: str, bivariate_run_id: str, objective: str = "return_risk"
    ) -> dict[str, object]:
        return {
            "selection_id": selection_id,
            "bivariate_run_id": bivariate_run_id,
            "objective": objective,
        }

    def run_detail(self, run_id: str) -> dict[str, object]:
        return {"run_id": run_id}

    def stage_history(self, stage: str, *, limit: int = 100) -> tuple[dict[str, object], ...]:
        return ({"stage": stage, "limit": limit},)


def test_multivariate_app_requires_bivariate_lineage_and_has_health() -> None:
    client = TestClient(MultivariateApplication(Service()).create_app())
    assert client.get("/health").json() == {"status": "ok", "module": "multivariate"}
    response = client.post(
        "/api/multivariate/runs",
        json={"selection_id": "u-1", "bivariate_run_id": "b-1"},
    )
    assert response.json() == {
        "selection_id": "u-1",
        "bivariate_run_id": "b-1",
        "objective": "return_risk",
    }
    assert client.get("/api/bivariate/runs").status_code == 404


def test_multivariate_process_has_no_sibling_implementation_imports() -> None:
    forbidden = {"metadata", "univariate", "bivariate"}
    for path in Path("src/portfell/services/multivariate").glob("*.py"):
        tree = ast.parse(path.read_text())
        imports = {
            (node.module or "").split(".")[-1]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        assert not imports & forbidden
