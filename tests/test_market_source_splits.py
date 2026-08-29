from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast

from portfell.market_source.contracts import ListingKey
from portfell.market_source.splits import SplitsRepository


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


def _row(key: ListingKey, event_date: date, split_ratio: str) -> tuple[object, ...]:
    return (key.isin, key.exchange, key.code, event_date, split_ratio, Decimal("2"))


def test_splits_preserve_source_ratio_and_sort_same_day_events() -> None:
    key = ListingKey("IE00ONE", "XETRA", "ONE")
    cursor = FakeCursor([[_row(key, date(2024, 1, 2), "3:1"), _row(key, date(2024, 1, 2), "2:1")]])

    splits = SplitsRepository().read_range(
        cursor, (key,), start=date(2024, 1, 1), end=date(2024, 1, 2)
    )

    assert [split.split_ratio for split in splits] == ["2:1", "3:1"]
    assert splits[0].split_factor == Decimal("2")
    assert "xetra_loader.splits" in cursor.queries[0][0]


def test_splits_batch_501_listing_identities() -> None:
    keys = tuple(ListingKey(f"IE{index:010d}", "XETRA", "ETF") for index in range(501))
    cursor = FakeCursor(
        [
            [_row(keys[0], date(2024, 1, 1), "2:1")],
            [_row(keys[-1], date(2024, 1, 1), "3:1")],
        ]
    )

    splits = SplitsRepository().read_range(
        cursor, keys, start=date(2024, 1, 1), end=date(2024, 1, 1)
    )

    assert len(cursor.queries) == 2
    assert len(cursor.queries[0][1]) == 1502
    assert len(cursor.queries[1][1]) == 5
    assert [split.key.isin for split in splits] == [keys[0].isin, keys[-1].isin]
