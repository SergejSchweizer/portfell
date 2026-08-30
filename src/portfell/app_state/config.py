"""Fail-closed configuration contract for the clean Portfell application database."""

from __future__ import annotations

from pathlib import Path

from portfell.market_source.config import (
    PostgresDatabaseConfig,
    load_app_database_config,
    validate_app_database_url,
)
from portfell.market_source.errors import MARKET_SOURCE_CONTRACT_MISMATCH, MarketSourceError

APP_DATABASE_NAME = "portfell_dash"
APP_SCHEMA_NAME = "portfell"


def validate_app_state_config(
    path: Path = Path("config.yaml"), *, database_url: str | None = None
) -> tuple[PostgresDatabaseConfig, str]:
    """Require local metadata and the secret-supplied DSN to target only the clean app DB."""

    config = load_app_database_config(path)
    if config.database != APP_DATABASE_NAME or config.schema != APP_SCHEMA_NAME:
        raise MarketSourceError(MARKET_SOURCE_CONTRACT_MISMATCH)
    resolved = validate_app_database_url(config, database_url)
    return config, resolved
