"""Stage-level read gateway for one coherent external market snapshot."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date

from portfell.market_source.connection import Connection, repeatable_read_snapshot
from portfell.market_source.contracts import Dividend, EodQuote, Listing, ListingKey, Split
from portfell.market_source.dividends import DividendsRepository
from portfell.market_source.errors import MARKET_SOURCE_CONTRACT_MISMATCH, MarketSourceError
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
            cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = %s AND table_name = %s "
                "AND column_name = ANY(%s)",
                ("xetra_loader", "dividends", ["amount", "value"]),
            )
            amount_columns = {row[0] for row in cursor.fetchall()}
            amount_column = "amount" if "amount" in amount_columns else "value"
            if not amount_columns.intersection({"amount", "value"}):
                raise MarketSourceError(MARKET_SOURCE_CONTRACT_MISMATCH)
            return MarketDataSnapshot(
                listings=self._listings.by_keys(cursor, keys),
                quotes=self._quotes.read_range(cursor, keys, start=start, end=end),
                dividends=self._dividends.read_range(
                    cursor, keys, start=start, end=end, amount_column=amount_column
                ),
                splits=self._splits.read_range(cursor, keys, start=start, end=end),
            )

    def read_active_listings(self) -> tuple[Listing, ...]:
        """Materialize the active listing universe from one read-only snapshot."""
        with repeatable_read_snapshot(
            self._connection_factory(), role=self._role, member_of=self._member_of
        ) as cursor:
            return self._listings.active(cursor)

    def read_quote_date_range(self, keys: Sequence[ListingKey]) -> tuple[date, date] | None:
        """Return the earliest and latest quote date for the requested keys."""
        if not keys:
            return None
        with repeatable_read_snapshot(
            self._connection_factory(), role=self._role, member_of=self._member_of
        ) as cursor:
            rows = self._quotes.read_range(cursor, keys, start=date.min, end=date.max)
        dates = [item.trade_date for item in rows]
        return (min(dates), max(dates)) if dates else None
