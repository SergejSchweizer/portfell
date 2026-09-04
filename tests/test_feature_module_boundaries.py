from __future__ import annotations

from fastapi.testclient import TestClient

from portfell.architecture_checks import check_architecture
from portfell.hosted_api import create_app
from portfell.modules import build_module_registry
from portfell.modules.runtime import ModuleBoundaryError


class _Service:
    def workflow_state(self) -> dict[str, object]:
        return {"workspace_id": "default", "stages": {}}

    def start_background_jobs(self) -> None: ...

    def stop_background_jobs(self) -> None: ...


def test_feature_modules_do_not_import_siblings() -> None:
    assert check_architecture() == []


def test_runtime_facades_reject_cross_module_operations() -> None:
    modules = build_module_registry(_Service())
    assert modules.metadata.workflow_state()["workspace_id"] == "default"
    try:
        forbidden = modules.metadata.run_bivariate
    except ModuleBoundaryError as error:
        assert str(error) == "metadata_module_operation_forbidden:run_bivariate"
    else:
        del forbidden
        raise AssertionError("metadata facade exposed a Bivariate operation")


def test_each_module_can_only_write_its_owned_stage() -> None:
    modules = build_module_registry(_Service())
    forbidden_by_module = {
        "metadata": ("create_univariate_selection", "run_bivariate", "run_multivariate"),
        "univariate": ("create_metadata_universe", "run_bivariate", "run_multivariate"),
        "bivariate": (
            "create_metadata_universe",
            "create_univariate_selection",
            "run_multivariate",
        ),
        "multivariate": (
            "create_metadata_universe",
            "create_univariate_selection",
            "run_bivariate",
        ),
    }
    for module_name, operations in forbidden_by_module.items():
        facade = getattr(modules, module_name)
        for operation in operations:
            try:
                getattr(facade, operation)
            except ModuleBoundaryError as error:
                assert str(error) == f"{module_name}_module_operation_forbidden:{operation}"
            else:
                raise AssertionError(f"{module_name} facade exposed {operation}")


def test_registry_exposes_exactly_the_four_analytical_modules() -> None:
    registry = build_module_registry(_Service())
    assert tuple(registry.__dataclass_fields__) == (
        "metadata",
        "univariate",
        "bivariate",
        "multivariate",
        "workflow",
    )
    assert registry.page_service("metadata") is registry.metadata
    assert registry.page_service("univariate") is registry.univariate
    assert registry.page_service("bivariate") is registry.bivariate
    assert registry.page_service("multivariate") is registry.multivariate
    try:
        registry.page_service("risk")
    except ModuleBoundaryError as error:
        assert str(error) == "unknown_module:risk"
    else:
        raise AssertionError("registry accepted an undocumented fifth page")


def test_http_surface_has_four_physical_module_prefixes_and_no_generic_runs() -> None:
    service = _Service()
    application = create_app(service)  # type: ignore[arg-type]
    paths = set(application.openapi()["paths"])
    assert "/api/metadata/options" in paths
    assert "/api/univariate/runs" in paths
    assert "/api/bivariate/runs" in paths
    assert "/api/multivariate/runs" in paths
    assert "/api/runs" not in paths
    assert "/api/runs/{run_id}" not in paths

    with TestClient(application) as client:
        assert client.get("/healthz").status_code == 200
