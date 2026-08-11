from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

from portfell.hosted_runtime import health

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


ComposeMapping = dict[str, Any]


def _compose() -> ComposeMapping:
    return cast(
        ComposeMapping,
        yaml.safe_load((REPOSITORY_ROOT / "compose.yaml").read_text(encoding="utf-8")),
    )


def test_compose_defines_persistent_internal_postgres_and_shared_data() -> None:
    compose = _compose()
    services = cast(ComposeMapping, compose["services"])
    volumes = cast(ComposeMapping, compose["volumes"])
    postgres = cast(ComposeMapping, services["postgres"])
    api = cast(ComposeMapping, services["api"])

    assert "portfell-postgres-data" in volumes
    assert "portfell-shared-data" in volumes
    assert postgres["networks"] == ["portfell-internal"]
    assert "ports" not in postgres
    assert "5432" in postgres["expose"]
    assert "portfell-postgres-data:/var/lib/postgresql/data" in postgres["volumes"]
    assert "portfell-shared-data:/srv/portfell/shared-data" in api["volumes"]
    assert "./lake:/srv/portfell/lake" not in api["volumes"]
    assert api["environment"]["PORTFELL_HOSTED_AUTHORITY"] == "postgres"
    assert api["environment"]["PORTFELL_DATABASE_PASSWORD_FILE"] == "/run/secrets/postgres_password"
    assert api["secrets"] == ["eodhd_kek", "postgres_password"]
    assert api["group_add"] == [
        "${PORTFELL_SECRET_GROUP_ID:-100}",
    ]


def test_compose_exposes_only_api_and_web_development_ports() -> None:
    services = cast(ComposeMapping, _compose()["services"])

    assert cast(ComposeMapping, services["api"])["ports"] == [
        "0.0.0.0:${PORTFELL_API_PORT:-8000}:8000"
    ]
    assert cast(ComposeMapping, services["web"])["ports"] == [
        "0.0.0.0:${PORTFELL_WEB_PORT:-3000}:3000"
    ]
    assert "ports" not in cast(ComposeMapping, services["postgres"])


def test_web_has_no_shared_data_mount_or_authentication_secret() -> None:
    services = cast(ComposeMapping, _compose()["services"])
    web = cast(ComposeMapping, services["web"])

    assert "volumes" not in web
    assert "secrets" not in web
    assert "PORTFELL_API_BASE_URL" in web["environment"]


def test_operations_refresh_is_profiled_and_has_only_the_required_secret_mount() -> None:
    refresh = cast(
        ComposeMapping, cast(ComposeMapping, _compose()["services"])["shared-market-refresh"]
    )
    assert refresh["profiles"] == ["operations"]
    assert refresh["command"] == ["python", "-m", "portfell.shared_market_refresh"]
    assert refresh["volumes"] == ["portfell-shared-data:/srv/portfell/shared-data"]
    assert refresh["secrets"] == ["eodhd_kek", "operations_eodhd_token", "postgres_password"]
    assert refresh["environment"]["PORTFELL_DATABASE_URL"] == "postgresql://portfell_app@postgres:5432/portfell"
    assert "ports" not in refresh


def test_project_initial_fill_worker_is_internal_and_operations_credential_only() -> None:
    worker = cast(
        ComposeMapping, cast(ComposeMapping, _compose()["services"])["project-bootstrap-worker"]
    )
    assert worker["command"] == ["python", "-m", "portfell.hosted_project_bootstrap_worker"]
    assert worker["secrets"] == ["operations_eodhd_token", "postgres_password"]
    assert worker["volumes"] == ["portfell-shared-data:/srv/portfell/shared-data"]
    assert worker["networks"] == ["portfell-internal"]
    assert "ports" not in worker


def test_web_compose_develop_watch_rebuilds_local_ui_changes() -> None:
    services = cast(ComposeMapping, _compose()["services"])
    web = cast(ComposeMapping, services["web"])
    develop = cast(ComposeMapping, web["develop"])
    watch = cast(list[ComposeMapping], develop["watch"])

    assert watch == [
        {"action": "rebuild", "path": "./apps/web"},
        {"action": "rebuild", "path": "./apps/web/Dockerfile"},
        {"action": "rebuild", "path": "./compose.yaml"},
    ]


def test_runtime_secrets_are_external_paths_and_not_build_arguments() -> None:
    compose = _compose()
    secrets = cast(ComposeMapping, compose["secrets"])
    rendered = (REPOSITORY_ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert cast(ComposeMapping, secrets["postgres_password"])["file"].startswith(
        "${PORTFELL_POSTGRES_PASSWORD_FILE:?"
    )
    assert cast(ComposeMapping, secrets["eodhd_kek"])["file"].startswith(
        "${PORTFELL_EODHD_KEK_FILE:?"
    )
    assert cast(ComposeMapping, secrets["operations_eodhd_token"])["file"].startswith(
        "${PORTFELL_OPERATIONS_EODHD_TOKEN_FILE:?"
    )
    assert "api_token" not in rendered.lower()
    assert "build:" in rendered
    assert "args:" not in rendered


def test_compose_uses_health_checks_startup_order_and_hardening() -> None:
    services = cast(ComposeMapping, _compose()["services"])

    for service_name in ("postgres", "api", "web"):
        service = cast(ComposeMapping, services[service_name])
        assert "healthcheck" in service
        assert service["read_only"] is True
        assert service["security_opt"] == ["no-new-privileges:true"]
        assert "deploy" in service

    for service_name in ("api", "web"):
        service = cast(ComposeMapping, services[service_name])
        assert service["cap_drop"] == ["ALL"]

    api_depends = cast(ComposeMapping, cast(ComposeMapping, services["api"])["depends_on"])
    web_depends = cast(ComposeMapping, cast(ComposeMapping, services["web"])["depends_on"])
    assert cast(ComposeMapping, api_depends["postgres"])["condition"] == "service_healthy"
    assert cast(ComposeMapping, web_depends["api"])["condition"] == "service_healthy"


def test_hosted_runtime_health_entrypoint(capsys: Any) -> None:
    assert health() == 0

    assert '"status": "ok"' in capsys.readouterr().out
