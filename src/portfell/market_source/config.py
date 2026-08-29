"""Fail-closed local configuration for the external market database."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from portfell.market_source.errors import (
    MARKET_SOURCE_CONFIG_MISSING,
    MARKET_SOURCE_CONTRACT_MISMATCH,
    MarketSourceError,
)


@dataclass(frozen=True)
class PostgresDatabaseConfig:
    host: str
    port: int
    database: str
    schema: str
    role: str
    password_secret: str


@dataclass(frozen=True)
class MarketSourceConfig(PostgresDatabaseConfig):
    member_of: str
    tables: tuple[str, ...]


def _parse_scalar(value: str) -> str | int:
    cleaned = value.strip().strip('"').strip("'")
    return int(cleaned) if cleaned.isdigit() else cleaned


def _read_postgres_section(path: Path, name: str) -> dict[str, str | int | list[str]]:
    if not path.exists():
        raise MarketSourceError(MARKET_SOURCE_CONFIG_MISSING)
    section: dict[str, str | int | list[str]] = {}
    in_section = False
    in_tables = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        text = line.strip()
        if indent == 2 and text == f"{name}:":
            in_section, in_tables = True, False
            continue
        if indent <= 2:
            in_section, in_tables = False, False
        if not in_section:
            continue
        if indent == 4 and text == "tables:":
            section["tables"] = []
            in_tables = True
            continue
        if in_tables and indent >= 6 and text.startswith("- "):
            tables = section["tables"]
            if not isinstance(tables, list):
                raise MarketSourceError(MARKET_SOURCE_CONTRACT_MISMATCH)
            tables.append(str(_parse_scalar(text[2:])))
            continue
        if indent == 4 and ":" in text:
            key, value = text.split(":", 1)
            section[key] = _parse_scalar(value)
            in_tables = False
    return section


def _database_config(path: Path, section: str) -> PostgresDatabaseConfig:
    values = _read_postgres_section(path, section)
    required = ("host", "port", "database", "schema", "role", "password_secret")
    if any(not values.get(key) for key in required):
        raise MarketSourceError(MARKET_SOURCE_CONFIG_MISSING)
    port = values["port"]
    if not isinstance(port, int) or port < 1 or port > 65535:
        raise MarketSourceError(MARKET_SOURCE_CONFIG_MISSING)
    return PostgresDatabaseConfig(
        host=str(values["host"]),
        port=port,
        database=str(values["database"]),
        schema=str(values["schema"]),
        role=str(values["role"]),
        password_secret=str(values["password_secret"]),
    )


def load_app_database_config(path: Path = Path("config.yaml")) -> PostgresDatabaseConfig:
    """Load the required non-secret Portfell application PostgreSQL metadata."""
    return _database_config(path, "app")


def load_market_source_config(path: Path = Path("config.yaml")) -> MarketSourceConfig:
    """Load required non-secret Xetra metadata from the ignored root config."""
    values = _read_postgres_section(path, "market")
    base = _database_config(path, "market")
    if not values.get("member_of") or not values.get("tables"):
        raise MarketSourceError(MARKET_SOURCE_CONFIG_MISSING)
    tables = values["tables"]
    if not isinstance(tables, list) or tuple(tables) != (
        "listings",
        "eod_quotes",
        "dividends",
        "splits",
    ):
        raise MarketSourceError(MARKET_SOURCE_CONTRACT_MISMATCH)
    return MarketSourceConfig(
        host=base.host,
        port=base.port,
        database=base.database,
        schema=base.schema,
        role=base.role,
        member_of=str(values["member_of"]),
        tables=tuple(tables),
        password_secret=base.password_secret,
    )


def validate_database_url(
    config: PostgresDatabaseConfig, url: str | None, *, environment_name: str
) -> str:
    """Require a DSN that exactly matches its non-secret local PostgreSQL metadata."""
    resolved = url if url is not None else os.environ.get(environment_name)
    if not resolved:
        raise MarketSourceError(MARKET_SOURCE_CONFIG_MISSING)
    parsed = urlparse(resolved)
    if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname or not parsed.path:
        raise MarketSourceError(MARKET_SOURCE_CONTRACT_MISMATCH)
    database = parsed.path.removeprefix("/")
    if (parsed.hostname, parsed.port or 5432, database, parsed.username) != (
        config.host,
        config.port,
        config.database,
        config.role,
    ):
        raise MarketSourceError(MARKET_SOURCE_CONTRACT_MISMATCH)
    return resolved


def validate_market_database_url(config: MarketSourceConfig, url: str | None = None) -> str:
    """Require an independent market DSN whose identity matches local metadata."""
    return validate_database_url(config, url, environment_name="PORTFELL_MARKET_DATABASE_URL")


def validate_app_database_url(config: PostgresDatabaseConfig, url: str | None = None) -> str:
    """Require the Portfell application DSN to match `postgres.app` in config.yaml."""
    return validate_database_url(config, url, environment_name="PORTFELL_DATABASE_URL")
