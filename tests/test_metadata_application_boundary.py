"""PR412 Metadata process boundary and import-isolation tests."""

from __future__ import annotations

import ast
from pathlib import Path

from fastapi.testclient import TestClient

from portfell.services.metadata import MetadataApplication


class Service:
    def workflow_state(self) -> dict[str, object]:
        return {"stage": "metadata"}

    def metadata_options(self) -> dict[str, object]:
        return {"items": []}

    def active_listings(self, **_: object) -> tuple[dict[str, object], ...]:
        return ()

    def metadata_history(self) -> tuple[dict[str, object], ...]:
        return ()


def test_metadata_app_exposes_only_metadata_routes_and_health() -> None:
    client = TestClient(MetadataApplication(Service()).create_app())
    assert client.get("/health").json() == {"status": "ok", "module": "metadata"}
    assert client.get("/api/metadata/options").status_code == 200
    assert client.get("/api/bivariate/workflow").status_code == 404


def test_metadata_process_does_not_import_sibling_implementation_packages() -> None:
    root = Path("src/portfell/services/metadata")
    forbidden = {"univariate", "bivariate", "multivariate"}
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text())
        imports = {
            (node.module or "").split(".")[-1]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        assert not imports & forbidden
