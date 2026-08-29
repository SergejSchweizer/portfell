from pathlib import Path

import pytest

from portfell.market_source.config import load_market_source_config, validate_market_database_url
from portfell.market_source.connection import repeatable_read_snapshot
from portfell.market_source.errors import (
    MARKET_SOURCE_CONFIG_MISSING,
    MARKET_SOURCE_CONTRACT_MISMATCH,
    MARKET_SOURCE_ROLE_INVALID,
    MarketSourceError,
)


def write_config(path: Path) -> None:
    path.write_text(
        """postgres:
  market:
    host: 10.10.1.3
    port: 54321
    database: xetra_loader
    schema: xetra_loader
    role: portfell
    member_of: portfell_app
    tables:
      - listings
      - eod_quotes
      - dividends
      - splits
    password_secret: PORTFELL_MARKET_DATABASE_PASSWORD_FILE
""",
        encoding="utf-8",
    )


def test_market_source_config_requires_ignored_local_file(tmp_path: Path) -> None:
    with pytest.raises(MarketSourceError, match=MARKET_SOURCE_CONFIG_MISSING):
        load_market_source_config(tmp_path / "config.yaml")


def test_market_source_config_requires_exact_market_contract(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    write_config(path)
    config = load_market_source_config(path)

    assert config.tables == ("listings", "eod_quotes", "dividends", "splits")
    assert validate_market_database_url(
        config, "postgresql://portfell@10.10.1.3:54321/xetra_loader"
    ).startswith("postgresql://")


def test_market_source_dsn_mismatch_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    write_config(path)

    with pytest.raises(MarketSourceError, match=MARKET_SOURCE_CONTRACT_MISMATCH):
        validate_market_database_url(
            load_market_source_config(path),
            "postgresql://portfell_reader@localhost:5432/portfell_dash",
        )


class FakeCursor:
    def __init__(self, role: tuple[object, ...] | None) -> None:
        self.role = role
        self.queries: list[tuple[str, object]] = []

    def execute(self, query: str, parameters: object = None) -> None:
        self.queries.append((query, parameters))

    def fetchone(self) -> tuple[object, ...] | None:
        return self.role


class FakeConnection:
    def __init__(self, role: tuple[object, ...] | None) -> None:
        self.cursor_value = FakeCursor(role)
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self.cursor_value

    def close(self) -> None:
        self.closed = True


def test_snapshot_uses_read_only_repeatable_read_utc_and_closes_connection() -> None:
    connection = FakeConnection((True, False, True))

    with repeatable_read_snapshot(connection, role="portfell", member_of="portfell_app"):
        pass

    assert [query for query, _ in connection.cursor_value.queries] == [
        "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY",
        "SET LOCAL TIME ZONE 'UTC'",
        "SELECT rolcanlogin, rolsuper, pg_has_role(current_user, %s, 'member') "
        "FROM pg_roles WHERE rolname = current_user",
        "COMMIT",
    ]
    assert connection.closed


def test_snapshot_rejects_superuser_or_missing_group_membership() -> None:
    connection = FakeConnection((True, True, True))

    with (
        pytest.raises(MarketSourceError, match=MARKET_SOURCE_ROLE_INVALID),
        repeatable_read_snapshot(connection, role="portfell", member_of="portfell_app"),
    ):
        pass

    assert connection.closed
