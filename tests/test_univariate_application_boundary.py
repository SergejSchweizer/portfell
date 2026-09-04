"""PR414 Univariate process boundary tests."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from portfell.services.univariate import UnivariateApplication


class Service:
    def run_univariate(self, universe_id: str) -> dict[str, object]:
        return {"run_id": f"run-for-{universe_id}"}

    def create_univariate_selection(self, run_id: str, *, predicates=None) -> object:
        return SimpleNamespace(
            selection_id="selection-1",
            source_run_id=run_id,
            version=1,
            content_hash="sha256:x",
            members=(),
        )

    def run_detail(self, run_id: str) -> dict[str, object]:
        return {"run_id": run_id}

    def stage_history(self, stage: str, *, limit: int = 100) -> tuple[dict[str, object], ...]:
        return ({"stage": stage, "limit": limit},)


def test_univariate_app_exposes_only_univariate_routes_and_health() -> None:
    client = TestClient(UnivariateApplication(Service()).create_app())
    assert client.get("/health").json() == {"status": "ok", "module": "univariate"}
    assert client.post("/api/univariate/runs", json={"universe_id": "m-1"}).json() == {
        "run_id": "run-for-m-1"
    }
    assert client.get("/api/metadata/options").status_code == 404


def test_univariate_process_has_no_sibling_implementation_imports() -> None:
    forbidden = {"metadata", "bivariate", "multivariate"}
    for path in (Path("src/portfell/services/univariate")).glob("*.py"):
        tree = ast.parse(path.read_text())
        imports = {
            (node.module or "").split(".")[-1]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        assert not imports & forbidden
