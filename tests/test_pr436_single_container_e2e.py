from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from portfell.hosted_api import create_app

ROOT = Path(__file__).resolve().parents[1]


def test_single_container_has_no_alternate_process_topology() -> None:
    assert not (ROOT / "compose.modules.yaml").exists()
    assert not (ROOT / "src" / "portfell" / "services" / "process.py").exists()
    assert not (ROOT / "docs" / "contracts" / "modular-compose-v1.md").exists()


def test_hosted_shell_health_is_available_without_runtime_adapters() -> None:
    client = TestClient(create_app())
    assert client.get("/healthz").json() == {"status": "ok"}


def test_deployment_evidence_names_exact_application_and_database_containers() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "container_name: portfell-app" in compose
    assert "container_name: portfell-postgres" in compose
    assert compose.count("container_name:") == 2
    assert compose.count("0.0.0.0:${PORTFELL_PORT:-8080}:8000") == 1
