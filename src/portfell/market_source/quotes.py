"""Read-only repository for external Xetra end-of-day quotes."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Protocol

from portfell.market_source.contracts import EodQuote, ListingKey
from portfell.market_source.errors import (
    MARKET_SOURCE_DUPLICATE_KEY,
    MARKET_SOURCE_INVALID_VALUE,
    MarketSourceError,
)

_QUOTE_COLUMNS = "isin, exchange, code, trade_date, adjusted_close, close, volume"
_BATCH_SIZE = 500


class QuotesCursor(Protocol):
    def execute(self, query: str, parameters: object = ...) -> object: ...

    def fetchall(self) -> list[tuple[object, ...]]: ...


def _optional_decimal(value: object) -> Decimal | None:
    if value is not None and not isinstance(value, Decimal):
        raise MarketSourceError(MARKET_SOURCE_INVALID_VALUE)
    return value


def _quote_from_row(row: tuple[object, ...]) -> EodQuote:
    if len(row) != 7:
        raise MarketSourceError(MARKET_SOURCE_INVALID_VALUE)
    isin, exchange, code, trade_date, adjusted_close, close, volume = row
    if (
        not isinstance(isin, str)
        or not isinstance(exchange, str)
        or not isinstance(code, str)
        or not isinstance(trade_date, date)
    ):
        raise MarketSourceError(MARKET_SOURCE_INVALID_VALUE)
    return EodQuote(
        key=ListingKey(isin, exchange, code),
        trade_date=trade_date,
        adjusted_close=_optional_decimal(adjusted_close),
        close=_optional_decimal(close),
        volume=_optional_decimal(volume),
    )


class QuotesRepository:
    """Perform parameterized, SELECT-only quote reads on one supplied cursor."""

    def read_range(
        self,
        cursor: QuotesCursor,
        keys: Sequence[ListingKey],
        *,
        start: date,
        end: date,
    ) -> tuple[EodQuote, ...]:
        if start > end:
            raise MarketSourceError(MARKET_SOURCE_INVALID_VALUE)
        quotes: list[EodQuote] = []
        for offset in range(0, len(keys), _BATCH_SIZE):
            batch = keys[offset : offset + _BATCH_SIZE]
            if not batch:
                continue
            placeholders = ", ".join("(%s, %s, %s)" for _ in batch)
            parameters = tuple(
                value for key in batch for value in (key.isin, key.exchange, key.code)
            ) + (start, end)
            cursor.execute(
                f"SELECT {_QUOTE_COLUMNS} FROM xetra_loader.eod_quotes "
                f"WHERE (isin, exchange, code) IN ({placeholders}) "
                "AND trade_date >= %s AND trade_date <= %s "
                "ORDER BY isin, exchange, code, trade_date",
                parameters,
            )
            quotes.extend(_quote_from_row(row) for row in cursor.fetchall())
        ordered = tuple(sorted(quotes, key=lambda quote: (quote.key, quote.trade_date)))
        identities = {(quote.key, quote.trade_date) for quote in ordered}
        if len(identities) != len(ordered):
            raise MarketSourceError(MARKET_SOURCE_DUPLICATE_KEY)
        return ordered
