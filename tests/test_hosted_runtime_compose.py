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


def _production_compose_source() -> str:
    return (REPOSITORY_ROOT / "compose.production.yaml").read_text(encoding="utf-8")


def test_production_override_keeps_only_postgres_durable_storage() -> None:
    source = _production_compose_source()

    assert source.count("${PORTFELL_DATA_ROOT:?set an absolute production Portfell data root}") == 1
    assert "}/postgres:/var/lib/postgresql/data" in source
    assert "portfell-postgres-data:" not in source
    assert "shared-data" not in source
    assert "/lake:" not in source
    assert "volumes: !reset {}" in source


def test_compose_defines_persistent_internal_postgres_without_market_filesystem() -> None:
    compose = _compose()
    services = cast(ComposeMapping, compose["services"])
    volumes = cast(ComposeMapping, compose["volumes"])
    postgres = cast(ComposeMapping, services["postgres"])
    api = cast(ComposeMapping, services["api"])

    assert "portfell-postgres-data" in volumes
    assert "portfell-shared-data" not in volumes
    assert postgres["container_name"] == "portfell-postgress"
    assert postgres["networks"] == ["portfell-internal"]
    assert "ports" not in postgres
    assert "5432" in postgres["expose"]
    assert "portfell-postgres-data:/var/lib/postgresql/data" in postgres["volumes"]
    assert set(services) == {"api", "postgres", "web"}
    assert "volumes" not in api
    assert api["container_name"] == "portfell-api"
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
        "0.0.0.0:${PORTFELL_WEB_PORT:-333}:3000"
    ]
    assert "ports" not in cast(ComposeMapping, services["postgres"])


def test_web_has_no_shared_data_mount_or_authentication_secret() -> None:
    services = cast(ComposeMapping, _compose()["services"])
    web = cast(ComposeMapping, services["web"])

    assert web["container_name"] == "portfell-web"
    assert "volumes" not in web
    assert "secrets" not in web
    assert "PORTFELL_API_BASE_URL" in web["environment"]


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
    assert "api_token" not in rendered.lower()
    assert "build:" in rendered
    assert "args:" not in rendered


def test_compose_uses_health_checks_startup_order_hardening_and_no_resource_limits() -> None:
    services = cast(ComposeMapping, _compose()["services"])

    for service_name in ("postgres", "api", "web"):
        service = cast(ComposeMapping, services[service_name])
        assert "healthcheck" in service
        assert service["read_only"] is True
        assert service["security_opt"] == ["no-new-privileges:true"]
    for service in services.values():
        service = cast(ComposeMapping, service)
        assert "deploy" not in service
        assert "cpus" not in service
        assert "memory" not in service
        assert "mem_limit" not in service

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
