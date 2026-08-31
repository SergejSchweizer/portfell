from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast

from portfell.market_source.contracts import ListingKey
from portfell.market_source.dividends import DividendsRepository


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


def _row(key: ListingKey, event_date: date, event_key: str) -> tuple[object, ...]:
    return (key.isin, key.exchange, key.code, event_date, event_key, Decimal("1.25"), None)


def test_dividends_preserve_same_day_events_and_nullable_source_values() -> None:
    key = ListingKey("IE00ONE", "XETRA", "ONE")
    cursor = FakeCursor([[_row(key, date(2024, 1, 2), "b"), _row(key, date(2024, 1, 2), "a")]])

    dividends = DividendsRepository().read_range(
        cursor, (key,), start=date(2024, 1, 1), end=date(2024, 1, 2)
    )

    assert [dividend.event_key for dividend in dividends] == ["a", "b"]
    assert dividends[0].currency is None
    assert dividends[0].amount == Decimal("1.25")
    assert "xetra_loader.dividends" in cursor.queries[0][0]


def test_dividends_repository_adapts_source_value_to_contract_amount() -> None:
    key = ListingKey("IE00ONE", "XETRA", "ONE")
    cursor = FakeCursor([[_row(key, date(2024, 1, 2), "event")]])

    DividendsRepository().read_range(
        cursor, (key,), start=date(2024, 1, 2), end=date(2024, 1, 2)
    )

    assert "value AS amount" in cursor.queries[0][0]


def test_dividends_batch_501_listing_identities() -> None:
    keys = tuple(ListingKey(f"IE{index:010d}", "XETRA", "ETF") for index in range(501))
    cursor = FakeCursor(
        [
            [_row(keys[0], date(2024, 1, 1), "first")],
            [_row(keys[-1], date(2024, 1, 1), "last")],
        ]
    )

    dividends = DividendsRepository().read_range(
        cursor, keys, start=date(2024, 1, 1), end=date(2024, 1, 1)
    )

    assert len(cursor.queries) == 2
    assert len(cursor.queries[0][1]) == 1502
    assert len(cursor.queries[1][1]) == 5
    assert [dividend.key.isin for dividend in dividends] == [keys[0].isin, keys[-1].isin]
