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
class MarketSourceConfig:
    host: str
    port: int
    database: str
    schema: str
    role: str
    member_of: str
    tables: tuple[str, ...]
    password_secret: str


def _parse_scalar(value: str) -> str | int:
    cleaned = value.strip().strip('"').strip("'")
    return int(cleaned) if cleaned.isdigit() else cleaned


def _read_market_section(path: Path) -> dict[str, str | int | list[str]]:
    if not path.exists():
        raise MarketSourceError(MARKET_SOURCE_CONFIG_MISSING)
    section: dict[str, str | int | list[str]] = {}
    in_market = False
    in_tables = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        text = line.strip()
        if indent == 2 and text == "market:":
            in_market, in_tables = True, False
            continue
        if indent <= 2:
            in_market, in_tables = False, False
        if not in_market:
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


def load_market_source_config(path: Path = Path("config.yaml")) -> MarketSourceConfig:
    """Load required non-secret Xetra metadata from the ignored root config."""
    values = _read_market_section(path)
    required = (
        "host",
        "port",
        "database",
        "schema",
        "role",
        "member_of",
        "tables",
        "password_secret",
    )
    if any(not values.get(key) for key in required):
        raise MarketSourceError(MARKET_SOURCE_CONFIG_MISSING)
    tables = values["tables"]
    if not isinstance(tables, list) or tuple(tables) != (
        "listings",
        "eod_quotes",
        "dividends",
        "splits",
    ):
        raise MarketSourceError(MARKET_SOURCE_CONTRACT_MISMATCH)
    port = values["port"]
    if not isinstance(port, int) or port < 1 or port > 65535:
        raise MarketSourceError(MARKET_SOURCE_CONFIG_MISSING)
    return MarketSourceConfig(
        host=str(values["host"]),
        port=port,
        database=str(values["database"]),
        schema=str(values["schema"]),
        role=str(values["role"]),
        member_of=str(values["member_of"]),
        tables=tuple(tables),
        password_secret=str(values["password_secret"]),
    )


def validate_market_database_url(config: MarketSourceConfig, url: str | None = None) -> str:
    """Require an independent market DSN whose identity matches local metadata."""
    resolved = url if url is not None else os.environ.get("PORTFELL_MARKET_DATABASE_URL")
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
