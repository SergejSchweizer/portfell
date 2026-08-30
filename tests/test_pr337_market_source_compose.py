from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_compose_keeps_app_postgres_local_and_market_postgres_external() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert "  postgres:\n" in compose
    assert "POSTGRES_DB: portfell" in compose
    assert "PORTFELL_DATABASE_URL: postgresql://portfell_app@postgres:5432/portfell" in compose
    assert "PORTFELL_MARKET_DATABASE_URL: ${PORTFELL_MARKET_DATABASE_URL:?" in compose
    assert "PORTFELL_MARKET_DATABASE_PASSWORD_FILE: /run/secrets/market_postgres_password" in compose
    assert "PORTFELL_CONFIG_PATH: /run/portfell/config.yaml" in compose
    assert "./config.yaml:/run/portfell/config.yaml:ro" in compose

    # xetra-loader is an external authority. Compose must never create or own it.
    assert "  xetra-loader:" not in compose
    assert "  market-postgres:" not in compose
    assert "POSTGRES_DB: xetra_loader" not in compose
    assert "xetra-loader-data" not in compose


def test_market_connection_has_no_app_database_fallback() -> None:
    config_source = (ROOT / "src" / "portfell" / "market_source" / "config.py").read_text(
        encoding="utf-8"
    )
    assert 'environment_name="PORTFELL_MARKET_DATABASE_URL"' in config_source
    assert 'environment_name="PORTFELL_DATABASE_URL"' in config_source
    assert "PORTFELL_MARKET_DATABASE_URL" in config_source
    assert "PORTFELL_DATABASE_URL" in config_source
    assert "or os.environ.get(\"PORTFELL_DATABASE_URL\")" not in config_source


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
