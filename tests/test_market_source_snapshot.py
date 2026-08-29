from __future__ import annotations

from datetime import date
from decimal import Decimal

from portfell.market_source.contracts import Dividend, EodQuote, Listing, ListingKey, Split
from portfell.market_source.snapshot import (
    MARKET_SOURCE_SNAPSHOT_CONTRACT,
    build_market_source_snapshot,
)


def test_snapshot_hashes_semantic_rows_in_canonical_order() -> None:
    left = ListingKey("IE00LEFT", "XETRA", "LEFT")
    right = ListingKey("IE00RIGHT", "XETRA", "RIGHT")
    listings = (
        Listing(right, "Right", "ETF", None, "EUR", True),
        Listing(left, "Left", "ETF", "DE", "EUR", True),
    )
    quotes = (EodQuote(left, date(2025, 1, 2), Decimal("100.00"), None, None),)
    dividends = (Dividend(left, date(2025, 1, 2), "event", Decimal("1.50"), "EUR"),)
    splits = (Split(left, date(2025, 1, 2), "2:1", Decimal("2")),)

    first = build_market_source_snapshot(
        listings=listings, quotes=quotes, dividends=dividends, splits=splits
    )
    second = build_market_source_snapshot(
        listings=reversed(listings), quotes=quotes, dividends=dividends, splits=splits
    )

    assert first.snapshot_id == second.snapshot_id
    assert first.contract_version == MARKET_SOURCE_SNAPSHOT_CONTRACT
    assert first.listings[0].key == left


def test_snapshot_id_changes_when_a_consumed_semantic_value_changes() -> None:
    key = ListingKey("IE00TEST", "XETRA", "TEST")
    before = build_market_source_snapshot(
        listings=(),
        quotes=(EodQuote(key, date(2025, 1, 2), Decimal("100"), None, None),),
        dividends=(),
        splits=(),
    )
    after = build_market_source_snapshot(
        listings=(),
        quotes=(EodQuote(key, date(2025, 1, 2), Decimal("101"), None, None),),
        dividends=(),
        splits=(),
    )

    assert before.snapshot_id != after.snapshot_id
