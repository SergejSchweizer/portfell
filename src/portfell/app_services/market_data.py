"""Application-service adapter for one coherent external market snapshot."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from portfell.app_state.contracts import ListingIdentity
from portfell.market_source.contracts import Listing, ListingKey
from portfell.market_source.errors import (
    MARKET_SOURCE_CONTRACT_MISMATCH,
    MARKET_SOURCE_UNAVAILABLE,
    MarketSourceError,
)
from portfell.market_source.gateway import MarketDataSnapshot
from portfell.market_source.projection import project_market_inputs
from portfell.market_source.snapshot import build_market_source_snapshot
from portfell.table_io import JsonRow


class MarketSnapshotGateway(Protocol):
    def read_snapshot(
        self, keys: Sequence[ListingKey], *, start: date, end: date
    ) -> MarketDataSnapshot: ...


@dataclass(frozen=True)
class AnalyticalMarketSnapshot:
    snapshot_id: str
    source_fingerprint: str
    listings: tuple[Listing, ...]
    quotes: tuple[JsonRow, ...]
    dividends: tuple[JsonRow, ...]
    splits: tuple[JsonRow, ...]


class AnalyticalMarketData:
    """Read one exact full-identity market snapshot and project it for analytics."""

    def __init__(self, gateway: MarketSnapshotGateway) -> None:
        self._gateway = gateway

    def read(self, members: Sequence[ListingIdentity]) -> AnalyticalMarketSnapshot:
        keys = tuple(sorted(ListingKey(item.isin, item.exchange, item.code) for item in members))
        if len(keys) != len(set(keys)):
            raise MarketSourceError(MARKET_SOURCE_CONTRACT_MISMATCH)
        source = self._gateway.read_snapshot(keys, start=date.min, end=date.max)
        expected = set(keys)
        if {item.key for item in source.listings} != expected:
            raise MarketSourceError(MARKET_SOURCE_CONTRACT_MISMATCH)
        if not expected.issubset({item.key for item in source.quotes}):
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
        return AnalyticalMarketSnapshot(
            snapshot_id=lineage.snapshot_id,
            source_fingerprint=lineage.snapshot_id,
            listings=source.listings,
            quotes=projected.quotes,
            dividends=projected.dividends,
            splits=projected.splits,
        )
