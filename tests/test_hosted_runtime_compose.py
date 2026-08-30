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


def test_pr357_compose_uses_clean_app_database_identity() -> None:
    compose = _compose()
    services = cast(ComposeMapping, compose["services"])
    volumes = cast(ComposeMapping, compose["volumes"])
    postgres = cast(ComposeMapping, services["postgres"])
    api = cast(ComposeMapping, services["api"])

    assert set(services) == {"api", "postgres", "web"}
    assert set(volumes) == {"portfell-dash-postgres-data"}
    assert postgres["container_name"] == "portfell-postgres"
    assert cast(ComposeMapping, postgres["environment"])["POSTGRES_DB"] == "portfell_dash"
    assert postgres["volumes"] == ["portfell-dash-postgres-data:/var/lib/postgresql/data"]
    assert "portfell_dash" in str(cast(ComposeMapping, postgres["healthcheck"])["test"])

    environment = cast(ComposeMapping, api["environment"])
    assert "PORTFELL_HOSTED_AUTHORITY" not in environment
    assert environment["PORTFELL_DATABASE_URL"] == "postgresql://portfell_app@postgres:5432/portfell_dash"
    assert "PORTFELL_MARKET_DATABASE_URL" in environment
    assert api["secrets"] == ["postgres_password", "market_postgres_password"]


def test_pr357_keeps_app_database_internal_and_market_database_external() -> None:
    compose = _compose()
    services = cast(ComposeMapping, compose["services"])
    postgres = cast(ComposeMapping, services["postgres"])
    api = cast(ComposeMapping, services["api"])

    assert postgres["networks"] == ["portfell-internal"]
    assert "ports" not in postgres
    assert "5432" in postgres["expose"]
    assert api["volumes"] == ["./config.yaml:/run/portfell/config.yaml:ro"]
    assert api["group_add"] == ["${PORTFELL_SECRET_GROUP_ID:-100}"]


def test_pr357_sibling_branch_does_not_steal_pr356_web_deletion_scope() -> None:
    services = cast(ComposeMapping, _compose()["services"])
    web = cast(ComposeMapping, services["web"])
    assert web["container_name"] == "portfell-web"
    assert cast(ComposeMapping, web["environment"])["PORTFELL_API_BASE_URL"] == "http://api:8000"


def test_runtime_secrets_are_external_paths_and_not_build_arguments() -> None:
    compose = _compose()
    secrets = cast(ComposeMapping, compose["secrets"])
    rendered = (REPOSITORY_ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert cast(ComposeMapping, secrets["postgres_password"])["file"].startswith(
        "${PORTFELL_POSTGRES_PASSWORD_FILE:?"
    )
    assert cast(ComposeMapping, secrets["market_postgres_password"])["file"].startswith(
        "${PORTFELL_MARKET_POSTGRES_PASSWORD_FILE:?"
    )
    assert "args:" not in rendered


def test_compose_health_and_hardening_remain_enabled() -> None:
    services = cast(ComposeMapping, _compose()["services"])
    for service_name in ("postgres", "api", "web"):
        service = cast(ComposeMapping, services[service_name])
        assert "healthcheck" in service
        assert service["read_only"] is True
        assert service["security_opt"] == ["no-new-privileges:true"]
    assert cast(ComposeMapping, services["api"])["cap_drop"] == ["ALL"]
    assert cast(ComposeMapping, services["web"])["cap_drop"] == ["ALL"]


def test_hosted_runtime_health_entrypoint(capsys: Any) -> None:
    assert health() == 0
    assert '"status": "ok"' in capsys.readouterr().out
