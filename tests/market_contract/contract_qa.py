"""Executable PostgreSQL contract check for the external market source."""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import psycopg

from portfell.market_source.connection import repeatable_read_snapshot
from portfell.market_source.contracts import Dividend, EodQuote, ListingKey, Split
from portfell.market_source.gateway import MarketDataGateway
from portfell.market_source.projection import project_market_inputs

DATABASE_URL = os.environ["PORTFELL_MARKET_CONTRACT_DATABASE_URL"]
ADMIN_DATABASE_URL = os.environ["PORTFELL_MARKET_CONTRACT_ADMIN_DATABASE_URL"]
CONTRACT_DATE = date(2025, 1, 2)
KEYS = tuple(ListingKey(f"IE{index:010d}", "XETRA", f"ETF{index:04d}") for index in range(1001))


def main() -> None:
    _seed()
    _assert_gateway_batches_and_read_only_role()
    _assert_repeatable_read_snapshot()
    _assert_projection_behavior()
    _assert_negative_space()


def _seed() -> None:
    rows = [
        (key.isin, key.exchange, key.code, "Contract ETF", "ETF", "DE", "EUR", True) for key in KEYS
    ]
    with (
        psycopg.connect(ADMIN_DATABASE_URL, autocommit=True) as connection,
        connection.cursor() as cursor,
    ):
        cursor.executemany(
            "INSERT INTO xetra_loader.listings VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            rows,
        )
        cursor.executemany(
            "INSERT INTO xetra_loader.eod_quotes VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [
                (key.isin, key.exchange, key.code, CONTRACT_DATE, Decimal("100"), None, None)
                for key in KEYS
            ],
        )
        cursor.executemany(
            "INSERT INTO xetra_loader.dividends VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [
                (key.isin, key.exchange, key.code, CONTRACT_DATE, "event", Decimal("1"), "EUR")
                for key in KEYS
            ],
        )
        cursor.executemany(
            "INSERT INTO xetra_loader.splits VALUES (%s, %s, %s, %s, %s, %s)",
            [
                (key.isin, key.exchange, key.code, CONTRACT_DATE, "1:1", Decimal("1"))
                for key in KEYS
            ],
        )


def _assert_gateway_batches_and_read_only_role() -> None:
    gateway = MarketDataGateway(
        lambda: psycopg.connect(DATABASE_URL, autocommit=True),
        role="portfell",
        member_of="portfell_app",
    )
    snapshot = gateway.read_snapshot(KEYS, start=CONTRACT_DATE, end=CONTRACT_DATE)
    records = (snapshot.listings, snapshot.quotes, snapshot.dividends, snapshot.splits)
    assert all(len(rows) == len(KEYS) for rows in records)
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        try:
            connection.execute(
                "INSERT INTO xetra_loader.listings "
                "VALUES ('write', 'X', 'X', 'X', 'ETF', NULL, NULL, true)"
            )
        except psycopg.errors.InsufficientPrivilege:
            return
    raise AssertionError("market reader role unexpectedly wrote to source tables")


def _assert_repeatable_read_snapshot() -> None:
    reader = psycopg.connect(DATABASE_URL, autocommit=True)
    with repeatable_read_snapshot(reader, role="portfell", member_of="portfell_app") as cursor:
        cursor.execute("SELECT count(*) FROM xetra_loader.listings")
        before = cursor.fetchone()
        with psycopg.connect(ADMIN_DATABASE_URL, autocommit=True) as writer:
            writer.execute(
                "INSERT INTO xetra_loader.listings "
                "VALUES ('IECONCURRENT', 'XETRA', 'NEW', 'New', 'ETF', NULL, NULL, true)"
            )
        cursor.execute("SELECT count(*) FROM xetra_loader.listings")
        assert cursor.fetchone() == before


def _assert_projection_behavior() -> None:
    key = KEYS[0]
    inputs = project_market_inputs(
        quotes=(EodQuote(key, CONTRACT_DATE, Decimal("100"), None, None),),
        dividends=(Dividend(key, CONTRACT_DATE, "event", Decimal("2"), "EUR"),),
        splits=(Split(key, CONTRACT_DATE, "2:1", Decimal("2")),),
    )
    assert inputs.quotes[0]["adjusted_close"] == 100.0
    assert inputs.dividends[0]["amount"] == 2.0
    assert inputs.splits[0]["split_ratio"] == "2:1"


def _assert_negative_space() -> None:
    source = Path("src/portfell/market_source")
    text = "\n".join(path.read_text(encoding="utf-8") for path in source.glob("*.py"))
    assert "xetra_loader_sync" not in text
    assert "eodhd" not in text.casefold()


if __name__ == "__main__":
    main()
