from __future__ import annotations

from fastapi import FastAPI

from portfell.services.composition import compose_modules, mount_module_routes


class _WorkflowService:
    def workflow_state(self) -> dict[str, object]:
        return {"workspace_id": "default"}


def test_composition_creates_exactly_four_restricted_module_facades() -> None:
    modules = compose_modules(_WorkflowService())
    assert set(modules.__dataclass_fields__) == {
        "metadata",
        "univariate",
        "bivariate",
        "multivariate",
        "workflow",
    }
    for name in ("metadata", "univariate", "bivariate", "multivariate"):
        assert modules.page_service(name)._module == name


def test_module_routes_mount_on_one_fastapi_application() -> None:
    app = FastAPI()
    mount_module_routes(app, compose_modules(_WorkflowService()))
    paths = set(app.openapi()["paths"])
    assert "/api/metadata/workflow" in paths
    assert "/api/univariate/runs" in paths
    assert "/api/bivariate/runs" in paths
    assert "/api/multivariate/runs" in paths
