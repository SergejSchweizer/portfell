from __future__ import annotations

import pytest

from portfell.market_source.config import MarketSourceConfig
from portfell.market_source.connection import preflight_market_source
from portfell.market_source.errors import (
    MARKET_SOURCE_CONTRACT_MISMATCH,
    MARKET_SOURCE_ROLE_INVALID,
    MARKET_SOURCE_UNAVAILABLE,
    MarketSourceError,
)


class FakeCursor:
    def __init__(
        self,
        *,
        identity: tuple[object, ...] = ("xetra_loader", "xetra_loader"),
        tables: list[tuple[object, ...]] | None = None,
        role: tuple[object, ...] = (True, False, True),
        fails: bool = False,
    ) -> None:
        self.queries: list[str] = []
        self.index = 0
        self.identity = identity
        self.tables = tables or [("listings",), ("eod_quotes",), ("dividends",), ("splits",)]
        self.role = role
        self.fails = fails

    def execute(self, query: str, parameters: object = None) -> None:
        self.queries.append(query)
        if self.fails:
            raise OSError("database unavailable")

    def fetchone(self) -> tuple[object, ...] | None:
        self.index += 1
        return self.identity if self.index == 1 else self.role

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.tables


class FakeConnection:
    def __init__(self, cursor: FakeCursor | None = None) -> None:
        self.cursor_value = cursor or FakeCursor()
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self.cursor_value

    def close(self) -> None:
        self.closed = True


def market_source_config() -> MarketSourceConfig:
    return MarketSourceConfig(
        host="10.10.1.3",
        port=54321,
        database="xetra_loader",
        schema="xetra_loader",
        role="portfell",
        member_of="portfell_app",
        tables=("listings", "eod_quotes", "dividends", "splits"),
        password_secret="PORTFELL_MARKET_DATABASE_PASSWORD_FILE",
    )


def test_preflight_checks_only_identity_catalog_and_role() -> None:
    config = market_source_config()
    connection = FakeConnection()

    status = preflight_market_source(connection, config)

    assert status.tables == config.tables
    assert connection.closed
    assert all(
        "xetra_loader_sync" not in query
        and "COUNT(" not in query
        and "MAX(" not in query
        and not query.startswith(("CREATE", "ALTER", "DROP", "INSERT", "UPDATE", "DELETE"))
        for query in connection.cursor_value.queries
    )


@pytest.mark.parametrize(
    ("cursor", "error_code"),
    [
        (FakeCursor(identity=("wrong_database", "xetra_loader")), MARKET_SOURCE_CONTRACT_MISMATCH),
        (FakeCursor(tables=[("listings",)]), MARKET_SOURCE_CONTRACT_MISMATCH),
        (FakeCursor(role=(True, False, False)), MARKET_SOURCE_ROLE_INVALID),
        (FakeCursor(fails=True), MARKET_SOURCE_UNAVAILABLE),
    ],
)
def test_preflight_fails_closed_and_closes_connection(cursor: FakeCursor, error_code: str) -> None:
    connection = FakeConnection(cursor)

    with pytest.raises(MarketSourceError, match=error_code):
        preflight_market_source(connection, market_source_config())

    assert connection.closed
