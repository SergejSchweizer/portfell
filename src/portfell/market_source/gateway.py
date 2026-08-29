"""Stage-level read gateway for one coherent external market snapshot."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date

from portfell.market_source.connection import Connection, repeatable_read_snapshot
from portfell.market_source.contracts import Dividend, EodQuote, Listing, ListingKey, Split
from portfell.market_source.dividends import DividendsRepository
from portfell.market_source.listings import ListingsRepository
from portfell.market_source.quotes import QuotesRepository
from portfell.market_source.splits import SplitsRepository


@dataclass(frozen=True)
class MarketDataSnapshot:
    """Materialized source records read from one database snapshot."""

    listings: tuple[Listing, ...]
    quotes: tuple[EodQuote, ...]
    dividends: tuple[Dividend, ...]
    splits: tuple[Split, ...]


class MarketDataGateway:
    """Read required market tables through one short-lived consistent snapshot."""

    def __init__(
        self,
        connection_factory: Callable[[], Connection],
        *,
        role: str,
        member_of: str,
    ) -> None:
        self._connection_factory = connection_factory
        self._role = role
        self._member_of = member_of
        self._listings = ListingsRepository()
        self._quotes = QuotesRepository()
        self._dividends = DividendsRepository()
        self._splits = SplitsRepository()

    def read_snapshot(
        self,
        keys: Sequence[ListingKey],
        *,
        start: date,
        end: date,
    ) -> MarketDataSnapshot:
        """Materialize bounded listing, quote, dividend, and split records together."""
        with repeatable_read_snapshot(
            self._connection_factory(), role=self._role, member_of=self._member_of
        ) as cursor:
            return MarketDataSnapshot(
                listings=self._listings.by_keys(cursor, keys),
                quotes=self._quotes.read_range(cursor, keys, start=start, end=end),
                dividends=self._dividends.read_range(cursor, keys, start=start, end=end),
                splits=self._splits.read_range(cursor, keys, start=start, end=end),
            )
