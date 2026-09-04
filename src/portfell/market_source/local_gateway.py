"""Read-only gateway for the locally published market snapshot.

The API process deliberately has no PostgreSQL market connection.  A scheduled
refresh publishes the four files in this directory atomically; readers always
use the last complete publication.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path

from portfell.market_source.contracts import Dividend, EodQuote, Listing, ListingKey, Split
from portfell.market_source.errors import (
    MARKET_SOURCE_CONTRACT_MISMATCH,
    MARKET_SOURCE_UNAVAILABLE,
    MarketSourceError,
)
from portfell.market_source.gateway import MarketDataSnapshot


class LocalMarketDataGateway:
    """Serve market records from an immutable, refresh-published local snapshot."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def _read(self, name: str) -> list[dict[str, object]]:
        path = self._root / f"{name}.jsonl"
        try:
            return [
                json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line
            ]
        except (OSError, json.JSONDecodeError) as error:
            raise MarketSourceError(MARKET_SOURCE_UNAVAILABLE) from error

    def _iter(self, name: str) -> Iterator[dict[str, object]]:
        """Stream a snapshot file so narrow selections never load the universe into RAM."""
        path = self._root / f"{name}.jsonl"
        try:
            with path.open(encoding="utf-8") as handle:
                for line in handle:
                    if line:
                        yield json.loads(line)
        except (OSError, json.JSONDecodeError) as error:
            raise MarketSourceError(MARKET_SOURCE_UNAVAILABLE) from error

    @staticmethod
    def _key(row: dict[str, object]) -> ListingKey:
        return ListingKey(str(row["isin"]), str(row["exchange"]), str(row["code"]))

    @staticmethod
    def _text(row: dict[str, object], name: str) -> str | None:
        value = row.get(name)
        return value if isinstance(value, str) else None

    def read_active_listings(self) -> tuple[Listing, ...]:
        rows = self._read("listings")
        return tuple(
            sorted(
                (
                    Listing(
                        key=self._key(row),
                        name=str(row["name"]),
                        instrument_type=str(row["instrument_type"]),
                        country=self._text(row, "country"),
                        currency=self._text(row, "currency"),
                        is_active=bool(row["is_active"]),
                    )
                    for row in rows
                    if bool(row["is_active"])
                ),
                key=lambda item: item.key,
            )
        )

    def read_snapshot(
        self, keys: Sequence[ListingKey], *, start: date, end: date
    ) -> MarketDataSnapshot:
        wanted = set(keys)
        listings = tuple(item for item in self.read_active_listings() if item.key in wanted)
        if {item.key for item in listings} != wanted:
            raise MarketSourceError(MARKET_SOURCE_CONTRACT_MISMATCH)

        def in_range(row: dict[str, object], field: str) -> bool:
            value = date.fromisoformat(str(row[field]))
            return start <= value <= end

        quotes = tuple(
            EodQuote(
                key=self._key(row),
                trade_date=date.fromisoformat(str(row["trade_date"])),
                adjusted_close=Decimal(str(row["adjusted_close"]))
                if row.get("adjusted_close") is not None
                else None,
                close=Decimal(str(row["close"])) if row.get("close") is not None else None,
                volume=Decimal(str(row["volume"])) if row.get("volume") is not None else None,
            )
            for row in self._iter("quotes")
            if self._key(row) in wanted and in_range(row, "trade_date")
        )
        dividends = tuple(
            Dividend(
                key=self._key(row),
                event_date=date.fromisoformat(str(row["event_date"])),
                event_key=str(row["event_key"]),
                amount=Decimal(str(row["amount"])) if row.get("amount") is not None else None,
                currency=self._text(row, "currency"),
            )
            for row in self._iter("dividends")
            if self._key(row) in wanted and in_range(row, "event_date")
        )
        splits = tuple(
            Split(
                key=self._key(row),
                event_date=date.fromisoformat(str(row["event_date"])),
                split_ratio=str(row["split_ratio"]),
                split_factor=Decimal(str(row["split_factor"]))
                if row.get("split_factor") is not None
                else None,
            )
            for row in self._iter("splits")
            if self._key(row) in wanted and in_range(row, "event_date")
        )
        return MarketDataSnapshot(listings, quotes, dividends, splits)
