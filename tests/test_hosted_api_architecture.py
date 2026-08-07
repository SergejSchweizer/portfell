from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "src" / "portfell"
ROUTE_GLOB = "hosted_routes_*.py"
SERVICE_GLOB = "hosted_*_service.py"
FORBIDDEN_ROUTE_IMPORTS = frozenset(
    {
        "portfell.bronze",
        "portfell.hosted_api_local_runtime",
        "portfell.hosted_credentials",
        "portfell.hosted_workspace",
        "portfell.metadata_filter",
        "portfell.paths",
        "portfell.silver",
        "portfell.table_io",
        "portfell.workflows",
    }
)
FORBIDDEN_SERVICE_IMPORTS = frozenset(
    {
        "fastapi",
        "portfell.hosted_api",
        "portfell.hosted_api_local_runtime",
        "portfell.hosted_routes_common",
        "portfell.hosted_routes_credentials",
        "portfell.hosted_routes_metadata_projects",
        "portfell.hosted_routes_quote_runs",
        "portfell.hosted_routes_research",
        "portfell.metadata_filter",
        "portfell.paths",
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
        if any(imported == value or imported.startswith(f"{value}.") for value in forbidden)
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


def test_hosted_services_are_fastapi_free_and_runtime_port_driven() -> None:
    for path in PACKAGE_ROOT.glob(SERVICE_GLOB):
        source = path.read_text(encoding="utf-8")
        assert _forbidden_imports(source, FORBIDDEN_SERVICE_IMPORTS) == set(), path


@pytest.mark.parametrize(
    ("source", "violation"),
    [
        ("from portfell.paths import LakePaths", "portfell.paths"),
        ("from portfell.workflows import run_fetch_all_quotes_workflow", "portfell.workflows"),
        ("from portfell.table_io import read_rows", "portfell.table_io"),
        (
            "from portfell.hosted_credentials import FileCredentialStore",
            "portfell.hosted_credentials",
        ),
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
            "from portfell.hosted_api_local_runtime import LocalHostedRuntime",
            "portfell.hosted_api_local_runtime",
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
