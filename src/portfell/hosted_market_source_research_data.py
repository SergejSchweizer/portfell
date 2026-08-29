"""Research-data adapter backed by one coherent external market snapshot."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from portfell.market_source.contracts import ListingKey
from portfell.market_source.errors import (
    MARKET_SOURCE_CONTRACT_MISMATCH,
    MARKET_SOURCE_INVALID_VALUE,
    MARKET_SOURCE_UNAVAILABLE,
    MarketSourceError,
)
from portfell.market_source.gateway import MarketDataSnapshot
from portfell.market_source.projection import project_market_inputs
from portfell.market_source.snapshot import build_market_source_snapshot
from portfell.table_io import JsonRow


class MarketSnapshotGateway(Protocol):
    """Minimal gateway contract required by hosted analytical stages."""

    def read_snapshot(
        self,
        keys: Sequence[ListingKey],
        *,
        start: date,
        end: date,
    ) -> MarketDataSnapshot: ...


@dataclass(frozen=True)
class MarketResearchSnapshot:
    """Projected analytical rows pinned to one deterministic source snapshot."""

    snapshot_id: str
    quotes: tuple[JsonRow, ...]
    dividends: tuple[JsonRow, ...]
    splits: tuple[JsonRow, ...]


class MarketSourceResearchData:
    """Materialize selected listings once, then release the source transaction."""

    def __init__(self, gateway: MarketSnapshotGateway) -> None:
        self._gateway = gateway

    def read(self, member_ids: tuple[str, ...]) -> MarketResearchSnapshot:
        keys = _listing_keys(member_ids)
        source = self._gateway.read_snapshot(keys, start=date.min, end=date.max)
        expected = set(keys)
        actual_listings = {listing.key for listing in source.listings}
        if actual_listings != expected:
            raise MarketSourceError(MARKET_SOURCE_CONTRACT_MISMATCH)
        quote_keys = {quote.key for quote in source.quotes}
        if not expected.issubset(quote_keys):
            raise MarketSourceError(MARKET_SOURCE_UNAVAILABLE)

        lineage = build_market_source_snapshot(
            listings=source.listings,
            quotes=source.quotes,
            dividends=source.dividends,
            splits=source.splits,
        )
        projected = project_market_inputs(
            quotes=source.quotes,
            dividends=source.dividends,
            splits=source.splits,
        )
        return MarketResearchSnapshot(
            snapshot_id=lineage.snapshot_id,
            quotes=projected.quotes,
            dividends=projected.dividends,
            splits=projected.splits,
        )


def _listing_keys(member_ids: tuple[str, ...]) -> tuple[ListingKey, ...]:
    keys: list[ListingKey] = []
    for member_id in member_ids:
        parts = member_id.split(":")
        if len(parts) != 3 or not all(parts):
            raise MarketSourceError(MARKET_SOURCE_INVALID_VALUE)
        keys.append(ListingKey(parts[0], parts[1], parts[2]))
    if len(set(keys)) != len(keys):
        raise MarketSourceError(MARKET_SOURCE_INVALID_VALUE)
    return tuple(sorted(keys))
