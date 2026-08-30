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


def test_combined_replacement_runtime_has_only_clean_python_services() -> None:
    compose = _compose()
    services = cast(ComposeMapping, compose["services"])
    volumes = cast(ComposeMapping, compose["volumes"])
    postgres = cast(ComposeMapping, services["postgres"])
    api = cast(ComposeMapping, services["api"])

    assert set(services) == {"api", "postgres"}
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
    assert api["volumes"] == ["./config.yaml:/run/portfell/config.yaml:ro"]


def test_combined_replacement_runtime_has_no_node_or_legacy_database_plane() -> None:
    rendered = (REPOSITORY_ROOT / "compose.yaml").read_text(encoding="utf-8").lower()
    assert "apps/web" not in rendered
    assert "node" not in rendered
    assert "portfell_web_port" not in rendered
    assert "portfell-postgres-data" not in rendered
    assert "postgresql://portfell_app@postgres:5432/portfell\n" not in rendered


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
    for service_name in ("postgres", "api"):
        service = cast(ComposeMapping, services[service_name])
        assert "healthcheck" in service
        assert service["read_only"] is True
        assert service["security_opt"] == ["no-new-privileges:true"]
    assert cast(ComposeMapping, services["api"])["cap_drop"] == ["ALL"]
    api_depends = cast(ComposeMapping, cast(ComposeMapping, services["api"])["depends_on"])
    assert cast(ComposeMapping, api_depends["postgres"])["condition"] == "service_healthy"


def test_hosted_runtime_health_entrypoint(capsys: Any) -> None:
    assert health() == 0
    assert '"status": "ok"' in capsys.readouterr().out
