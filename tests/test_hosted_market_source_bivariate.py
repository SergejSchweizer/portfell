from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

import pytest

from portfell.hosted_market_source_bivariate_service import BivariateMarketSourceData
from portfell.market_source.contracts import EodQuote, Listing, ListingKey
from portfell.market_source.errors import (
    MARKET_SOURCE_CONTRACT_MISMATCH,
    MARKET_SOURCE_UNAVAILABLE,
    MarketSourceError,
)
from portfell.market_source.gateway import MarketDataSnapshot
from portfell.market_source.projection import MISSING_ADJUSTED_CLOSE, MarketProjectionError


class FakeGateway:
    def __init__(self, snapshot: MarketDataSnapshot) -> None:
        self.snapshot = snapshot
        self.calls: list[tuple[tuple[ListingKey, ...], date, date]] = []

    def read_snapshot(
        self,
        keys: Sequence[ListingKey],
        *,
        start: date,
        end: date,
    ) -> MarketDataSnapshot:
        self.calls.append((tuple(keys), start, end))
        return self.snapshot


def _snapshot(*, missing_adjusted: bool = False) -> MarketDataSnapshot:
    left = ListingKey("IE00LEFT0001", "XETRA", "LEFT")
    right = ListingKey("IE00RIGHT001", "XETRA", "RIGHT")
    listings = (
        Listing(left, "Left ETF", "ETF", "DE", "EUR", True),
        Listing(right, "Right ETF", "ETF", "DE", "EUR", True),
    )
    quotes: list[EodQuote] = []
    for offset, day in enumerate((2, 3, 6, 7)):
        quotes.append(
            EodQuote(
                left,
                date(2025, 1, day),
                None if missing_adjusted and offset == 0 else Decimal(100 + offset),
                Decimal(100 + offset),
                Decimal("10"),
            )
        )
        quotes.append(
            EodQuote(
                right,
                date(2025, 1, day),
                Decimal(200 + 2 * offset),
                Decimal(200 + 2 * offset),
                Decimal("20"),
            )
        )
    return MarketDataSnapshot(listings, tuple(quotes), (), ())


def test_bivariate_market_source_data_uses_one_snapshot_and_full_identity() -> None:
    gateway = FakeGateway(_snapshot())
    data = BivariateMarketSourceData(gateway)

    result = data.read(("IE00RIGHT001:XETRA:RIGHT", "IE00LEFT0001:XETRA:LEFT"))

    assert len(gateway.calls) == 1
    keys, start, end = gateway.calls[0]
    assert keys == (
        ListingKey("IE00LEFT0001", "XETRA", "LEFT"),
        ListingKey("IE00RIGHT001", "XETRA", "RIGHT"),
    )
    assert start == date.min
    assert end == date.max
    assert result.snapshot_id.startswith("market_source_snapshot_")
    assert {f"{row['isin']}:{row['exchange']}:{row['code']}" for row in result.quotes} == {
        "IE00LEFT0001:XETRA:LEFT",
        "IE00RIGHT001:XETRA:RIGHT",
    }
    assert len(result.quotes) == 8


def test_bivariate_market_source_data_fails_closed_for_partial_source() -> None:
    source = _snapshot()
    with pytest.raises(MarketSourceError, match=MARKET_SOURCE_CONTRACT_MISMATCH):
        BivariateMarketSourceData(
            FakeGateway(MarketDataSnapshot(source.listings[:1], source.quotes, (), ()))
        ).read(("IE00LEFT0001:XETRA:LEFT", "IE00RIGHT001:XETRA:RIGHT"))

    left_only_quotes = tuple(quote for quote in source.quotes if quote.key.code == "LEFT")
    with pytest.raises(MarketSourceError, match=MARKET_SOURCE_UNAVAILABLE):
        BivariateMarketSourceData(
            FakeGateway(MarketDataSnapshot(source.listings, left_only_quotes, (), ()))
        ).read(("IE00LEFT0001:XETRA:LEFT", "IE00RIGHT001:XETRA:RIGHT"))


def test_bivariate_market_source_data_preserves_missing_adjusted_close_error() -> None:
    with pytest.raises(MarketProjectionError, match=MISSING_ADJUSTED_CLOSE):
        BivariateMarketSourceData(FakeGateway(_snapshot(missing_adjusted=True))).read(
            ("IE00LEFT0001:XETRA:LEFT", "IE00RIGHT001:XETRA:RIGHT")
        )
