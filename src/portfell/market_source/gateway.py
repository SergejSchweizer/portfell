"""Stage-level read gateway for one coherent external market snapshot."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date

from portfell.market_source.connection import (
    Connection,
    imported_repeatable_read_snapshot,
    repeatable_read_snapshot,
    validate_reader_role,
)
from portfell.market_source.contracts import Dividend, EodQuote, Listing, ListingKey, Split
from portfell.market_source.dividends import DividendsRepository
from portfell.market_source.errors import (
    MARKET_SOURCE_CONTRACT_MISMATCH,
    MARKET_SOURCE_UNAVAILABLE,
    MarketSourceError,
)
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
        parallel_reads: bool = False,
    ) -> None:
        self._connection_factory = connection_factory
        self._role = role
        self._member_of = member_of
        self._parallel_reads = parallel_reads
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
        if self._parallel_reads:
            return self._read_snapshot_parallel(keys, start=start, end=end)
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

    def _read_snapshot_parallel(
        self, keys: Sequence[ListingKey], *, start: date, end: date
    ) -> MarketDataSnapshot:
        """Read independent tables concurrently from one exported DB snapshot."""
        connection = self._connection_factory()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cursor.execute("SET LOCAL TIME ZONE 'UTC'")
            validate_reader_role(cursor, role=self._role, member_of=self._member_of)
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
            cursor.execute("SELECT pg_export_snapshot()")
            exported = cursor.fetchone()
            if not exported or not isinstance(exported[0], str):
                raise MarketSourceError(MARKET_SOURCE_UNAVAILABLE)
            snapshot = exported[0]

            def read_table(table: str) -> object:
                with imported_repeatable_read_snapshot(
                    self._connection_factory(),
                    snapshot=snapshot,
                    role=self._role,
                    member_of=self._member_of,
                ) as imported_cursor:
                    if table == "listings":
                        return self._listings.by_keys(imported_cursor, keys)
                    if table == "quotes":
                        return self._quotes.read_range(imported_cursor, keys, start=start, end=end)
                    if table == "dividends":
                        return self._dividends.read_range(
                            imported_cursor,
                            keys,
                            start=start,
                            end=end,
                            amount_column=amount_column,
                        )
                    return self._splits.read_range(imported_cursor, keys, start=start, end=end)

            with ThreadPoolExecutor(max_workers=4, thread_name_prefix="market-read") as executor:
                listings, quotes, dividends, splits = executor.map(
                    read_table, ("listings", "quotes", "dividends", "splits")
                )
            cursor.execute("COMMIT")
            return MarketDataSnapshot(listings, quotes, dividends, splits)  # type: ignore[arg-type]
        except MarketSourceError:
            if cursor is not None:
                cursor.execute("ROLLBACK")
            raise
        except Exception as error:
            if cursor is not None:
                cursor.execute("ROLLBACK")
            raise MarketSourceError(MARKET_SOURCE_UNAVAILABLE) from error
        finally:
            connection.close()

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
