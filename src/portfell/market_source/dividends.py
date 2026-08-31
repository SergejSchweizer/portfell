"""Read-only repository for external Xetra dividend events."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Protocol

from portfell.market_source.contracts import Dividend, ListingKey
from portfell.market_source.errors import MARKET_SOURCE_INVALID_VALUE, MarketSourceError

_DIVIDEND_COLUMNS = "isin, exchange, code, event_date, event_key, value AS amount, currency"
_BATCH_SIZE = 500


class DividendsCursor(Protocol):
    def execute(self, query: str, parameters: object = ...) -> object: ...

    def fetchall(self) -> list[tuple[object, ...]]: ...


def _optional_decimal(value: object) -> Decimal | None:
    if value is not None and not isinstance(value, Decimal):
        raise MarketSourceError(MARKET_SOURCE_INVALID_VALUE)
    return value


def _dividend_from_row(row: tuple[object, ...]) -> Dividend:
    if len(row) != 7:
        raise MarketSourceError(MARKET_SOURCE_INVALID_VALUE)
    isin, exchange, code, event_date, event_key, amount, currency = row
    if (
        not isinstance(isin, str)
        or not isinstance(exchange, str)
        or not isinstance(code, str)
        or not isinstance(event_date, date)
        or not isinstance(event_key, str)
        or (currency is not None and not isinstance(currency, str))
    ):
        raise MarketSourceError(MARKET_SOURCE_INVALID_VALUE)
    return Dividend(
        key=ListingKey(isin, exchange, code),
        event_date=event_date,
        event_key=event_key,
        amount=_optional_decimal(amount),
        currency=currency,
    )


class DividendsRepository:
    """Perform parameterized, SELECT-only dividend reads on one supplied cursor."""

    def read_range(
        self,
        cursor: DividendsCursor,
        keys: Sequence[ListingKey],
        *,
        start: date,
        end: date,
    ) -> tuple[Dividend, ...]:
        if start > end:
            raise MarketSourceError(MARKET_SOURCE_INVALID_VALUE)
        dividends: list[Dividend] = []
        for offset in range(0, len(keys), _BATCH_SIZE):
            batch = keys[offset : offset + _BATCH_SIZE]
            if not batch:
                continue
            placeholders = ", ".join("(%s, %s, %s)" for _ in batch)
            parameters = tuple(
                value for key in batch for value in (key.isin, key.exchange, key.code)
            ) + (start, end)
            cursor.execute(
                f"SELECT {_DIVIDEND_COLUMNS} FROM xetra_loader.dividends "
                f"WHERE (isin, exchange, code) IN ({placeholders}) "
                "AND event_date >= %s AND event_date <= %s "
                "ORDER BY isin, exchange, code, event_date, event_key",
                parameters,
            )
            dividends.extend(_dividend_from_row(row) for row in cursor.fetchall())
        return tuple(
            sorted(
                dividends,
                key=lambda dividend: (dividend.key, dividend.event_date, dividend.event_key),
            )
        )
