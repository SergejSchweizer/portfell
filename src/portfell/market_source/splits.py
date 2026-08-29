"""Read-only repository for external Xetra split events."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Protocol

from portfell.market_source.contracts import ListingKey, Split
from portfell.market_source.errors import MARKET_SOURCE_INVALID_VALUE, MarketSourceError

_SPLIT_COLUMNS = "isin, exchange, code, event_date, split_ratio, split_factor"
_BATCH_SIZE = 500


class SplitsCursor(Protocol):
    def execute(self, query: str, parameters: object = ...) -> object: ...

    def fetchall(self) -> list[tuple[object, ...]]: ...


def _optional_decimal(value: object) -> Decimal | None:
    if value is not None and not isinstance(value, Decimal):
        raise MarketSourceError(MARKET_SOURCE_INVALID_VALUE)
    return value


def _split_from_row(row: tuple[object, ...]) -> Split:
    if len(row) != 6:
        raise MarketSourceError(MARKET_SOURCE_INVALID_VALUE)
    isin, exchange, code, event_date, split_ratio, split_factor = row
    if (
        not isinstance(isin, str)
        or not isinstance(exchange, str)
        or not isinstance(code, str)
        or not isinstance(event_date, date)
        or not isinstance(split_ratio, str)
    ):
        raise MarketSourceError(MARKET_SOURCE_INVALID_VALUE)
    return Split(
        key=ListingKey(isin, exchange, code),
        event_date=event_date,
        split_ratio=split_ratio,
        split_factor=_optional_decimal(split_factor),
    )


class SplitsRepository:
    """Perform parameterized, SELECT-only split reads on one supplied cursor."""

    def read_range(
        self,
        cursor: SplitsCursor,
        keys: Sequence[ListingKey],
        *,
        start: date,
        end: date,
    ) -> tuple[Split, ...]:
        if start > end:
            raise MarketSourceError(MARKET_SOURCE_INVALID_VALUE)
        splits: list[Split] = []
        for offset in range(0, len(keys), _BATCH_SIZE):
            batch = keys[offset : offset + _BATCH_SIZE]
            if not batch:
                continue
            placeholders = ", ".join("(%s, %s, %s)" for _ in batch)
            parameters = tuple(
                value for key in batch for value in (key.isin, key.exchange, key.code)
            ) + (start, end)
            cursor.execute(
                f"SELECT {_SPLIT_COLUMNS} FROM xetra_loader.splits "
                f"WHERE (isin, exchange, code) IN ({placeholders}) "
                "AND event_date >= %s AND event_date <= %s "
                "ORDER BY isin, exchange, code, event_date, split_ratio",
                parameters,
            )
            splits.extend(_split_from_row(row) for row in cursor.fetchall())
        return tuple(
            sorted(splits, key=lambda split: (split.key, split.event_date, split.split_ratio))
        )
