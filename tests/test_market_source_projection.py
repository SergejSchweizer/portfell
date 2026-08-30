from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from portfell.return_series import build_returns
from portfell.market_source.contracts import Dividend, EodQuote, ListingKey, Split
from portfell.market_source.projection import (
    MISSING_ADJUSTED_CLOSE,
    MarketProjectionError,
    project_market_inputs,
)

LISTING = ListingKey("IE00TEST", "XETRA", "TEST")


def test_projection_preserves_existing_adjusted_close_return_formula() -> None:
    inputs = project_market_inputs(
        quotes=(
            EodQuote(LISTING, date(2025, 1, 2), Decimal("100"), None, None),
            EodQuote(LISTING, date(2025, 1, 3), Decimal("110"), None, None),
        ),
        dividends=(Dividend(LISTING, date(2025, 1, 3), "event-1", Decimal("5"), "EUR"),),
        splits=(Split(LISTING, date(2025, 1, 3), "2:1", Decimal("2")),),
    )

    returns = build_returns(inputs.quotes)

    assert returns[0]["simple_return"] == pytest.approx(0.1)
    assert inputs.dividends[0]["amount"] == 5.0
    assert inputs.splits[0]["split_ratio"] == "2:1"
    assert inputs.splits[0]["split_factor"] == 2.0


def test_projection_rejects_missing_adjusted_close_with_typed_error() -> None:
    quote = EodQuote(LISTING, date(2025, 1, 2), None, Decimal("100"), None)

    with pytest.raises(MarketProjectionError, match=MISSING_ADJUSTED_CLOSE) as error:
        project_market_inputs(quotes=(quote,), dividends=(), splits=())

    assert error.value.code == MISSING_ADJUSTED_CLOSE
