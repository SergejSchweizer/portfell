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
        self._quote_ranges: dict[str, tuple[tuple[int, int], ...]] | None = None

    def _load_quote_ranges(self) -> dict[str, tuple[tuple[int, int], ...]]:
        """Load the refresh-produced byte ranges, with a safe legacy fallback."""
        if self._quote_ranges is not None:
            return self._quote_ranges
        path = self._root / "quotes.index.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            self._quote_ranges = {
                str(isin): tuple((int(item[0]), int(item[1])) for item in ranges)
                for isin, ranges in raw.items()
                if isinstance(ranges, list)
            }
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            # Older snapshots have no sidecar. Build it once by scanning bytes;
            # subsequent reads in this process still avoid rescanning quotes.
            self._quote_ranges = self._build_quote_ranges()
        return self._quote_ranges

    def _build_quote_ranges(self) -> dict[str, tuple[tuple[int, int], ...]]:
        path = self._root / "quotes.jsonl"
        ranges: dict[str, list[tuple[int, int]]] = {}
        try:
            with path.open("rb") as handle:
                while True:
                    start = handle.tell()
                    line = handle.readline()
                    if not line:
                        break
                    end = handle.tell()
                    marker_start = line.find(b'"isin"')
                    if marker_start < 0:
                        continue
                    colon = line.find(b":", marker_start + 6)
                    if colon < 0:
                        continue
                    value_start = colon + 1
                    while value_start < len(line) and line[value_start] in b" \t":
                        value_start += 1
                    if value_start >= len(line) or line[value_start] != ord('"'):
                        continue
                    value_start += 1
                    value_end = line.find(b'"', value_start)
                    if value_end < 0:
                        continue
                    isin = line[value_start:value_end].decode("utf-8")
                    entries = ranges.setdefault(isin, [])
                    if entries and entries[-1][1] == start:
                        entries[-1] = (entries[-1][0], end)
                    else:
                        entries.append((start, end))
        except OSError as error:
            raise MarketSourceError(MARKET_SOURCE_UNAVAILABLE) from error
        return {isin: tuple(items) for isin, items in ranges.items()}

    def _read(self, name: str) -> list[dict[str, object]]:
        path = self._root / f"{name}.jsonl"
        try:
            return [
                json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line
            ]
        except (OSError, json.JSONDecodeError) as error:
            raise MarketSourceError(MARKET_SOURCE_UNAVAILABLE) from error

    def _iter(
        self, name: str, *, wanted_isins: set[str] | None = None
    ) -> Iterator[dict[str, object]]:
        """Stream a snapshot file so narrow selections never load the universe into RAM."""
        path = self._root / f"{name}.jsonl"
        try:
            if name == "quotes" and wanted_isins is not None:
                ranges = self._load_quote_ranges()
                with path.open("rb") as handle:
                    for isin in wanted_isins:
                        for start, end in ranges.get(isin, ()):
                            handle.seek(start)
                            while handle.tell() < end:
                                line = handle.readline()
                                if line:
                                    yield json.loads(line)
                return
            with path.open(encoding="utf-8") as handle:
                for line in handle:
                    if line and (wanted_isins is None or _line_has_isin(line, wanted_isins)):
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

    def read_quote_date_range(self, keys: Sequence[ListingKey]) -> tuple[date, date] | None:
        """Read only quote dates for selected keys from the shared snapshot."""
        wanted = set(keys)
        if not wanted:
            return None
        dates: list[date] = []
        for row in self._iter("quotes", wanted_isins={key.isin for key in wanted}):
            key = self._key(row)
            if key in wanted:
                dates.append(date.fromisoformat(str(row["trade_date"])))
        return (min(dates), max(dates)) if dates else None

    def read_snapshot(
        self, keys: Sequence[ListingKey], *, start: date, end: date
    ) -> MarketDataSnapshot:
        wanted = set(keys)
        wanted_isins = {key.isin for key in wanted}
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
            for row in self._iter("quotes", wanted_isins=wanted_isins)
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
            for row in self._iter("dividends", wanted_isins=wanted_isins)
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
            for row in self._iter("splits", wanted_isins=wanted_isins)
            if self._key(row) in wanted and in_range(row, "event_date")
        )
        return MarketDataSnapshot(listings, quotes, dividends, splits)


def _line_has_isin(line: str, wanted_isins: set[str]) -> bool:
    """Extract the single ISIN field without parsing unrelated JSON rows."""
    marker = line.find('"isin"')
    if marker < 0:
        return False
    colon = line.find(":", marker + 6)
    start = line.find('"', colon + 1)
    end = line.find('"', start + 1)
    return start >= 0 and end > start and line[start + 1 : end] in wanted_isins
