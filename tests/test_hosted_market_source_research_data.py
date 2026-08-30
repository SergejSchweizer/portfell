from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

import pytest

from portfell.hosted_market_source_research_data import MarketSourceResearchData
from portfell.market_source.contracts import Dividend, EodQuote, Listing, ListingKey, Split
from portfell.market_source.errors import (
    MARKET_SOURCE_CONTRACT_MISMATCH,
    MARKET_SOURCE_INVALID_VALUE,
    MARKET_SOURCE_UNAVAILABLE,
    MarketSourceError,
)
from portfell.market_source.gateway import MarketDataSnapshot
from portfell.market_source.projection import MISSING_ADJUSTED_CLOSE, MarketProjectionError
from portfell.univariate_statistics import build_univariate_statistics


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


def _source_snapshot(*, adjusted_close: Decimal | None = Decimal("100")) -> MarketDataSnapshot:
    key = ListingKey("IE00TEST0001", "XETRA", "TEST")
    return MarketDataSnapshot(
        listings=(Listing(key, "Test ETF", "ETF", "DE", "EUR", True),),
        quotes=(
            EodQuote(key, date(2025, 1, 2), adjusted_close, Decimal("100"), Decimal("10")),
            EodQuote(key, date(2025, 1, 3), Decimal("101"), Decimal("101"), Decimal("11")),
            EodQuote(key, date(2025, 1, 6), Decimal("102"), Decimal("102"), Decimal("12")),
        ),
        dividends=(Dividend(key, date(2025, 1, 3), "div-1", Decimal("1.25"), "EUR"),),
        splits=(Split(key, date(2025, 1, 4), "2:1", Decimal("2")),),
    )


def test_market_source_research_data_materializes_one_full_identity_snapshot() -> None:
    gateway = FakeGateway(_source_snapshot())
    data = MarketSourceResearchData(gateway)

    result = data.read(("IE00TEST0001:XETRA:TEST",))

    assert len(gateway.calls) == 1
    keys, start, end = gateway.calls[0]
    assert keys == (ListingKey("IE00TEST0001", "XETRA", "TEST"),)
    assert start == date.min
    assert end == date.max
    assert result.snapshot_id.startswith("market_source_snapshot_")
    assert [row["adjusted_close"] for row in result.quotes] == [100.0, 101.0, 102.0]
    assert result.dividends == (
        {
            "isin": "IE00TEST0001",
            "exchange": "XETRA",
            "code": "TEST",
            "date": "2025-01-03",
            "event_id": "div-1",
            "amount": 1.25,
            "value": 1.25,
            "currency": "EUR",
        },
    )
    assert result.splits[0]["split_factor"] == 2.0
    assert len(result.quotes) == 3


def test_projected_dividend_rows_preserve_univariate_income_semantics() -> None:
    projected = MarketSourceResearchData(FakeGateway(_source_snapshot())).read(
        ("IE00TEST0001:XETRA:TEST",)
    )
    expected_dividends = (
        {
            "isin": "IE00TEST0001",
            "exchange": "XETRA",
            "code": "TEST",
            "date": "2025-01-03",
            "value": 1.25,
        },
    )

    actual = build_univariate_statistics(
        projected.quotes,
        dividend_rows=projected.dividends,
        concurrency=1,
    )
    expected = build_univariate_statistics(
        projected.quotes,
        dividend_rows=expected_dividends,
        concurrency=1,
    )

    assert actual == expected


def test_market_source_research_data_fails_closed_for_partial_or_invalid_identity() -> None:
    source = _source_snapshot()
    empty_listings = MarketDataSnapshot((), source.quotes, source.dividends, source.splits)
    with pytest.raises(MarketSourceError, match=MARKET_SOURCE_CONTRACT_MISMATCH):
        MarketSourceResearchData(FakeGateway(empty_listings)).read(("IE00TEST0001:XETRA:TEST",))

    empty_quotes = MarketDataSnapshot(source.listings, (), source.dividends, source.splits)
    with pytest.raises(MarketSourceError, match=MARKET_SOURCE_UNAVAILABLE):
        MarketSourceResearchData(FakeGateway(empty_quotes)).read(("IE00TEST0001:XETRA:TEST",))

    with pytest.raises(MarketSourceError, match=MARKET_SOURCE_INVALID_VALUE):
        MarketSourceResearchData(FakeGateway(source)).read(("invalid",))


def test_market_source_research_data_preserves_typed_missing_adjusted_close() -> None:
    with pytest.raises(MarketProjectionError, match=MISSING_ADJUSTED_CLOSE):
        MarketSourceResearchData(FakeGateway(_source_snapshot(adjusted_close=None))).read(
            ("IE00TEST0001:XETRA:TEST",)
        )
