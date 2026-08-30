from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "src" / "portfell"
ROUTE_GLOB = "hosted_routes_*.py"
SERVICE_GLOB = "hosted_*_service.py"
RESEARCH_SERVICE_MODULES = frozenset(
    {
        "hosted_analysis_service.py",
        "hosted_bivariate_service.py",
        "hosted_research_service.py",
        "hosted_univariate_service.py",
    }
)
FORBIDDEN_ROUTE_IMPORTS = frozenset(
    {
        "portfell.bronze",
        "portfell.hosted_workspace",
        "portfell.hosted_workspace_repository",
        "portfell.metadata_builder",
        "portfell.paths",
        "portfell.silver",
        "portfell.table_io",
        "portfell.http",
        "portfell.workflows",
    }
)
FORBIDDEN_SERVICE_IMPORTS = frozenset(
    {
        "fastapi",
        "portfell.hosted_api",
        "portfell.hosted_local_",
        "portfell.hosted_workspace",
        "portfell.hosted_workspace_repository",
        "portfell.hosted_routes_common",
        "portfell.hosted_routes_metadata_projects",
        "portfell.hosted_routes_research",
        "portfell.hosted_research_persistence",
        "portfell.hosted_research_repository",
        "portfell.metadata_builder",
        "portfell.paths",
        "portfell.http",
        "portfell.workflows",
    }
)
FORBIDDEN_PRODUCTION_API_IMPORTS = frozenset(
    {
        "portfell.hosted_workspace",
        "portfell.hosted_workspace_repository",
        "portfell.http",
        "portfell.workflows",
    }
)


def _imports(source: str) -> set[str]:
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


def _forbidden_imports(source: str, forbidden: frozenset[str]) -> set[str]:
    return {
        imported
        for imported in _imports(source)
        if any(
            imported == value
            or imported.startswith(f"{value}.")
            or (value.endswith("_") and imported.startswith(value))
            for value in forbidden
        )
    }


def _route_state_access(source: str) -> set[str]:
    return {
        node.attr
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Attribute)
        and (node.attr.endswith("_by_id") or node.attr in {"idempotency_refs", "audit_events"})
    }


def _production_line_count(path: Path) -> int:
    return sum(
        bool(line.strip()) and not line.lstrip().startswith("#")
        for line in path.read_text(encoding="utf-8").splitlines()
    )


def test_hosted_routes_only_translate_http() -> None:
    for path in PACKAGE_ROOT.glob(ROUTE_GLOB):
        source = path.read_text(encoding="utf-8")
        assert _forbidden_imports(source, FORBIDDEN_ROUTE_IMPORTS) == set(), path
        assert _route_state_access(source) == set(), path


def test_hosted_production_api_has_no_local_or_provider_authority() -> None:
    source = (PACKAGE_ROOT / "hosted_api.py").read_text(encoding="utf-8")
    assert _forbidden_imports(source, FORBIDDEN_PRODUCTION_API_IMPORTS) == set()


def test_provider_credential_backend_modules_are_deleted() -> None:
    assert not (PACKAGE_ROOT / "hosted_credentials.py").exists()
    assert not (PACKAGE_ROOT / "hosted_routes_credentials.py").exists()
    assert not (PACKAGE_ROOT / "provider_credential_schema.py").exists()
    assert not (PACKAGE_ROOT / "user_ingestion.py").exists()


def test_hosted_services_are_fastapi_free_and_runtime_port_driven() -> None:
    for path in PACKAGE_ROOT.glob(SERVICE_GLOB):
        source = path.read_text(encoding="utf-8")
        forbidden = FORBIDDEN_SERVICE_IMPORTS - frozenset(
            {
                "portfell.hosted_local_",
                "portfell.hosted_workspace",
                "portfell.hosted_workspace_repository",
            }
        )
        assert _forbidden_imports(source, forbidden) == set(), path


def test_hosted_services_do_not_hide_dependencies_or_disable_strict_typing() -> None:
    forbidden_type_suppressions = (
        "reportUnknownVariableType=false",
        "reportCallIssue=false",
        "reportArgumentType=false",
        "reportUnknownArgumentType=false",
        "reportUnknownMemberType=false",
    )
    for path in PACKAGE_ROOT.glob(SERVICE_GLOB):
        source = path.read_text(encoding="utf-8")
        assert "import_module(" not in source, path
        assert all(value not in source for value in forbidden_type_suppressions), path


def test_navigation_read_model_has_no_shared_store_or_command_dependencies() -> None:
    source = (PACKAGE_ROOT / "hosted_navigation_read_model_repository.py").read_text(
        encoding="utf-8"
    )
    forbidden = frozenset(
        {
            "portfell.table_io",
            "portfell.shared_market_data",
            "portfell.shared_metadata_catalog",
            "portfell.hosted_credential_project_service",
            "portfell.hosted_metadata_project_service",
            "portfell.hosted_research_service",
        }
    )

    assert _forbidden_imports(source, forbidden) == set()


def test_research_implementation_is_split_and_covered_by_hosted_service_gates() -> None:
    service_names = {path.name for path in PACKAGE_ROOT.glob(SERVICE_GLOB)}
    assert service_names >= RESEARCH_SERVICE_MODULES
    assert not (PACKAGE_ROOT / "research_service.py").exists()


@pytest.mark.parametrize(
    ("source", "violation"),
    [
        ("from portfell.paths import LakePaths", "portfell.paths"),
        ("from portfell.workflows import run_fetch_all_quotes_workflow", "portfell.workflows"),
        ("from portfell.table_io import read_rows", "portfell.table_io"),
    ],
)
def test_route_import_fixture_violations_are_detected(source: str, violation: str) -> None:
    assert _forbidden_imports(source, FORBIDDEN_ROUTE_IMPORTS) == {violation}


@pytest.mark.parametrize(
    "source",
    [
        "def route(state):\n    return state.projects_by_id",
        "def route(state):\n    state.idempotency_refs.clear()",
        "def route(state):\n    state.audit_events.append({})",
    ],
)
def test_route_mutable_state_fixture_violations_are_detected(source: str) -> None:
    assert _route_state_access(source)


@pytest.mark.parametrize(
    ("source", "violation"),
    [
        ("from fastapi import HTTPException", "fastapi"),
        (
            "from portfell.hosted_local_project_repository import LocalProjectRepository",
            "portfell.hosted_local_project_repository",
        ),
        (
            "from portfell.hosted_workspace_repository import persist_local_workspace",
            "portfell.hosted_workspace_repository",
        ),
        ("from portfell.hosted_routes_common import call", "portfell.hosted_routes_common"),
    ],
)
def test_service_import_fixture_violations_are_detected(source: str, violation: str) -> None:
    assert _forbidden_imports(source, FORBIDDEN_SERVICE_IMPORTS) == {violation}


def test_hosted_production_module_size_limits() -> None:
    assert _production_line_count(PACKAGE_ROOT / "hosted_api.py") <= 250
    for path in PACKAGE_ROOT.glob("hosted_*.py"):
        assert _production_line_count(path) <= 500, path
    assert _production_line_count(PACKAGE_ROOT / "bivariate_diagnostics.py") <= 700
    assert _production_line_count(PACKAGE_ROOT / "bivariate_views.py") <= 410
