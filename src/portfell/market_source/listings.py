"""Read-only repository for external Xetra listings."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from portfell.market_source.contracts import Listing, ListingKey
from portfell.market_source.errors import MARKET_SOURCE_INVALID_VALUE, MarketSourceError

_LISTING_COLUMNS = (
    "isin, exchange, code, name, COALESCE(instrument_type, '') AS instrument_type, "
    "country, currency, is_active"
)
_BATCH_SIZE = 500


class ListingsCursor(Protocol):
    def execute(self, query: str, parameters: object = ...) -> object: ...

    def fetchall(self) -> list[tuple[object, ...]]: ...


def _listing_from_row(row: tuple[object, ...]) -> Listing:
    if len(row) != 8:
        raise MarketSourceError(MARKET_SOURCE_INVALID_VALUE)
    isin, exchange, code, name, instrument_type, country, currency, is_active = row
    if (
        not isinstance(isin, str)
        or not isinstance(exchange, str)
        or not isinstance(code, str)
        or not isinstance(name, str)
        or not isinstance(instrument_type, str)
        or (country is not None and not isinstance(country, str))
        or (currency is not None and not isinstance(currency, str))
        or not isinstance(is_active, bool)
    ):
        raise MarketSourceError(MARKET_SOURCE_INVALID_VALUE)
    return Listing(
        key=ListingKey(isin, exchange, code),
        name=name,
        instrument_type=instrument_type,
        country=country,
        currency=currency,
        is_active=is_active,
    )


def _ordered(rows: list[tuple[object, ...]]) -> tuple[Listing, ...]:
    return tuple(sorted((_listing_from_row(row) for row in rows), key=lambda listing: listing.key))


class ListingsRepository:
    """Perform parameterized, SELECT-only listings reads on one supplied cursor."""

    def by_key(self, cursor: ListingsCursor, key: ListingKey) -> Listing | None:
        cursor.execute(
            f"SELECT {_LISTING_COLUMNS} FROM xetra_loader.listings "
            "WHERE isin = %s AND exchange = %s AND code = %s "
            "ORDER BY isin, exchange, code",
            (key.isin, key.exchange, key.code),
        )
        listings = _ordered(cursor.fetchall())
        if len(listings) > 1:
            raise MarketSourceError(MARKET_SOURCE_INVALID_VALUE)
        return listings[0] if listings else None

    def by_keys(self, cursor: ListingsCursor, keys: Sequence[ListingKey]) -> tuple[Listing, ...]:
        rows: list[tuple[object, ...]] = []
        for start in range(0, len(keys), _BATCH_SIZE):
            batch = keys[start : start + _BATCH_SIZE]
            if not batch:
                continue
            placeholders = ", ".join("(%s, %s, %s)" for _ in batch)
            parameters = tuple(
                value for key in batch for value in (key.isin, key.exchange, key.code)
            )
            cursor.execute(
                f"SELECT {_LISTING_COLUMNS} FROM xetra_loader.listings "
                f"WHERE (isin, exchange, code) IN ({placeholders}) "
                "ORDER BY isin, exchange, code",
                parameters,
            )
            rows.extend(cursor.fetchall())
        return _ordered(rows)

    def active(self, cursor: ListingsCursor) -> tuple[Listing, ...]:
        cursor.execute(
            f"SELECT {_LISTING_COLUMNS} FROM xetra_loader.listings "
            "WHERE is_active = true ORDER BY isin, exchange, code"
        )
        return _ordered(cursor.fetchall())
