from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _compose() -> dict[str, Any]:
    return cast(dict[str, Any], yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8")))


def test_compose_keeps_app_postgres_local_and_market_postgres_external() -> None:
    compose = _compose()
    services = cast(dict[str, dict[str, Any]], compose["services"])
    postgres = services["postgres"]
    api = services["api"]

    assert postgres["environment"]["POSTGRES_DB"] == "portfell"
    assert (
        api["environment"]["PORTFELL_DATABASE_URL"]
        == "postgresql://portfell_app@postgres:5432/portfell"
    )
    assert api["environment"]["PORTFELL_MARKET_DATABASE_URL"].startswith(
        "${PORTFELL_MARKET_DATABASE_URL:?"
    )
    assert api["environment"]["PORTFELL_MARKET_DATABASE_PASSWORD_FILE"] == (
        "/run/secrets/market_postgres_password"
    )
    assert api["environment"]["PORTFELL_CONFIG_PATH"] == "/run/portfell/config.yaml"
    assert api["volumes"] == ["./config.yaml:/run/portfell/config.yaml:ro"]

    # xetra-loader is an external authority. Compose must never create or own it.
    assert set(services) == {"api", "postgres", "web"}
    assert "xetra-loader" not in services
    assert "market-postgres" not in services
    assert "xetra_loader" not in str(postgres)
    assert "xetra-loader-data" not in cast(dict[str, Any], compose["volumes"])


def test_market_connection_has_no_app_database_fallback() -> None:
    config_source = (ROOT / "src" / "portfell" / "market_source" / "config.py").read_text(
        encoding="utf-8"
    )
    assert 'environment_name="PORTFELL_MARKET_DATABASE_URL"' in config_source
    assert 'environment_name="PORTFELL_DATABASE_URL"' in config_source
    assert "PORTFELL_MARKET_DATABASE_URL" in config_source
    assert "PORTFELL_DATABASE_URL" in config_source
    assert 'or os.environ.get("PORTFELL_DATABASE_URL")' not in config_source


def test_compose_contains_no_provider_or_download_worker_secret() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8").lower()
    forbidden = (
        "eodhd",
        "provider_token",
        "provider_key",
        "download-worker",
        "refresh-worker",
        "xetra_loader_sync",
    )
    for token in forbidden:
        assert token not in compose


def test_market_reader_contract_requires_group_membership_and_denies_superuser() -> None:
    source = (ROOT / "src" / "portfell" / "market_source" / "connection.py").read_text(
        encoding="utf-8"
    )
    assert "pg_has_role" in source
    assert "rolsuper" in source
    assert "row != (True, False, True)" in source
    assert "REPEATABLE READ READ ONLY" in source
