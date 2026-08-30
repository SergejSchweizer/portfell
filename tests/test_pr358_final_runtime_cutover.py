from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "portfell"


def test_pr358_root_config_is_runtime_mounted_but_never_baked() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    dockerfile = (ROOT / "apps" / "api" / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "config.yaml" in gitignore
    assert "COPY config.yaml" not in dockerfile
    assert "./config.yaml:/run/portfell/config.yaml:ro" in compose


def test_pr358_runtime_composes_dash_clean_state_and_external_market_source() -> None:
    api = (SRC / "hosted_api.py").read_text(encoding="utf-8")
    for required in (
        "PostgresAppStateRepository",
        "ResearchApplicationService",
        "MarketDataGateway",
        "mount_dash_app",
        "validate_app_database_url",
        "validate_market_database_url",
    ):
        assert required in api
    for forbidden in (
        "PORTFELL_HOSTED_AUTHORITY",
        "hosted_postgres_",
        "hosted_catalog",
        "portfell_private",
    ):
        assert forbidden not in api


def test_pr358_compose_exposes_one_local_application_surface() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert '"127.0.0.1:${PORTFELL_PORT:-8080}:8000"' in compose
    assert "apps/web" not in compose
    assert "NODE_ENV" not in compose
    assert "portfell_dash" in compose
    assert "PORTFELL_MARKET_DATABASE_URL" in compose
