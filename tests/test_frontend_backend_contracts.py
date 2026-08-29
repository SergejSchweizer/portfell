"""Consumer-driven contract checks between the React API client and FastAPI."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

from portfell.hosted_api import HostedApiState, create_app
from portfell.hosted_local_test_composition import local_test_services
from portfell.hosted_postgres_request_scope import RequestScopedPostgresConnection

ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "apps" / "web"
MANIFEST_PATH = WEB_ROOT / "api-contracts.json"
HTTP_METHODS = frozenset({"delete", "get", "patch", "post", "put"})


def _app():
    state = HostedApiState()
    return create_app(
        state,
        services=local_test_services(state),
        request_scope=RequestScopedPostgresConnection(lambda: object()),  # type: ignore[arg-type]
    )


def _normalize_path(path: str) -> str:
    normalized = re.sub(r"\{[^}]+\}", "{param}", path).split("?", maxsplit=1)[0]
    normalized = re.sub(
        r"(?<=/views/)(?:univariate|bivariate|multivariate)[_-]statistics(?=/|$)",
        "{param}",
        normalized,
    )
    normalized = normalized.replace("/sections/results", "/sections/{param}")
    return re.sub(r"(/sections/\{param\})\{param\}$", r"\1", normalized)


def _frontend_api_paths() -> set[str]:
    paths: set[str] = set()
    for source_path in (WEB_ROOT / "src").rglob("*.ts*"):
        source = source_path.read_text(encoding="utf-8")
        for path in re.findall(r"[\"`](/api/.*?)[\"`]", source):
            paths.add(_normalize_path(re.sub(r"\$\{[^}]+\}", "{param}", path)))
    return paths


def _manifest() -> list[dict[str, Any]]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    return cast("list[dict[str, Any]]", payload)


def _resolve_schema(specification: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    reference = schema.get("$ref")
    if not isinstance(reference, str):
        return schema
    name = reference.rsplit("/", maxsplit=1)[-1]
    resolved = specification["components"]["schemas"][name]
    assert isinstance(resolved, dict)
    return cast("dict[str, Any]", resolved)


def test_every_react_api_path_is_catalogued_and_backed_by_fastapi() -> None:
    manifest = _manifest()
    documented_paths = {_normalize_path(str(item["path"])) for item in manifest}

    assert _frontend_api_paths() == documented_paths

    specification = cast("dict[str, Any]", _app().openapi())
    backend_operations = {
        (method.upper(), _normalize_path(path))
        for path, operations in cast("dict[str, dict[str, Any]]", specification["paths"]).items()
        for method in operations
        if method in HTTP_METHODS
    }
    documented_operations = {
        (str(item["method"]).upper(), _normalize_path(str(item["path"])[4:])) for item in manifest
    }
    assert documented_operations <= backend_operations


def test_every_catalogued_response_has_a_named_react_contract() -> None:
    contracts_source = (WEB_ROOT / "src" / "contracts.ts").read_text(encoding="utf-8")

    for contract in _manifest():
        response_type = str(contract["responseType"])
        assert f"export type {response_type}" in contracts_source, (
            f"{contract['method']} {contract['path']} must use an exported React response contract"
        )


def test_react_write_contracts_match_backend_request_schemas_and_query_parameters() -> None:
    specification = cast("dict[str, Any]", _app().openapi())
    paths = cast("dict[str, dict[str, dict[str, Any]]]", specification["paths"])

    for contract in _manifest():
        path = str(contract["path"])[4:]
        operation = paths[path][str(contract["method"]).lower()]
        expected_query = set(cast("list[str]", contract.get("query", [])))
        actual_query = {
            parameter["name"]
            for parameter in cast("list[dict[str, Any]]", operation.get("parameters", []))
            if parameter.get("in") == "query"
        }
        assert expected_query == actual_query, f"{contract['method']} {path} query contract drifted"

        request_schema_name = contract.get("requestSchema")
        if request_schema_name is None:
            assert "requestBody" not in operation, (
                f"{contract['method']} {path} unexpectedly needs a body"
            )
            continue

        request_body = cast("dict[str, Any]", operation["requestBody"])
        schema = _resolve_schema(
            specification,
            cast("dict[str, Any]", request_body["content"]["application/json"]["schema"]),
        )
        properties = set(cast("dict[str, Any]", schema["properties"]))
        assert set(cast("list[str]", contract["requestFields"])) <= properties
        assert schema.get("title") == request_schema_name
