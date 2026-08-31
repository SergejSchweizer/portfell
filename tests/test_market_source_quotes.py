from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast

import pytest

from portfell.market_source.contracts import ListingKey
from portfell.market_source.errors import MARKET_SOURCE_DUPLICATE_KEY, MarketSourceError
from portfell.market_source.quotes import QuotesRepository


class FakeCursor:
    def __init__(self, batches: list[list[tuple[object, ...]]]) -> None:
        self.batches = batches
        self.queries: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, query: str, parameters: object = None) -> None:
        if not isinstance(parameters, tuple):
            raise TypeError("expected tuple parameters")
        self.queries.append((query, cast(tuple[object, ...], parameters)))

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.batches.pop(0)


def _row(key: ListingKey, trade_date: date, adjusted_close: Decimal | None) -> tuple[object, ...]:
    return (
        key.isin,
        key.exchange,
        key.code,
        trade_date,
        adjusted_close,
        Decimal("10"),
        Decimal("5"),
    )


def test_quotes_read_inclusive_range_preserves_missing_adjusted_close() -> None:
    key = ListingKey("IE00ONE", "XETRA", "ONE")
    cursor = FakeCursor([[_row(key, date(2024, 1, 2), None)]])

    quotes = QuotesRepository().read_range(
        cursor, (key,), start=date(2024, 1, 1), end=date(2024, 1, 2)
    )

    assert quotes[0].adjusted_close is None
    query, parameters = cursor.queries[0]
    assert "xetra_loader.eod_quotes" in query
    assert "trade_date >= %s AND trade_date <= %s" in query
    assert parameters[-2:] == (date(2024, 1, 1), date(2024, 1, 2))


def test_quotes_repository_normalizes_bigint_volume_to_decimal() -> None:
    key = ListingKey("IE00ONE", "XETRA", "ONE")
    cursor = FakeCursor([[_row(key, date(2024, 1, 2), Decimal("10"))]])

    QuotesRepository().read_range(cursor, (key,), start=date(2024, 1, 2), end=date(2024, 1, 2))

    assert "volume::numeric AS volume" in cursor.queries[0][0]


def test_quotes_batch_501_listing_identities() -> None:
    keys = tuple(ListingKey(f"IE{index:010d}", "XETRA", "ETF") for index in range(501))
    cursor = FakeCursor(
        [
            [_row(keys[0], date(2024, 1, 1), Decimal("11"))],
            [_row(keys[-1], date(2024, 1, 1), Decimal("12"))],
        ]
    )

    quotes = QuotesRepository().read_range(
        cursor, keys, start=date(2024, 1, 1), end=date(2024, 1, 1)
    )

    assert len(cursor.queries) == 2
    assert len(cursor.queries[0][1]) == 1502
    assert len(cursor.queries[1][1]) == 5
    assert [quote.key.isin for quote in quotes] == [keys[0].isin, keys[-1].isin]


def test_quotes_fail_closed_on_duplicate_identity_and_trade_date() -> None:
    key = ListingKey("IE00ONE", "XETRA", "ONE")
    cursor = FakeCursor(
        [[_row(key, date(2024, 1, 1), Decimal("10")), _row(key, date(2024, 1, 1), Decimal("11"))]]
    )

    with pytest.raises(MarketSourceError, match=MARKET_SOURCE_DUPLICATE_KEY):
        QuotesRepository().read_range(cursor, (key,), start=date(2024, 1, 1), end=date(2024, 1, 1))
