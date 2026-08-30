"""Projection of raw Xetra DTOs into existing analytical row contracts."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from portfell.market_source.contracts import Dividend, EodQuote, Split

type JsonRow = dict[str, object]

MISSING_ADJUSTED_CLOSE = "missing_adjusted_close"


class MarketProjectionError(ValueError):
    """Raised when an external market DTO cannot satisfy an analytical input contract."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class AnalyticalMarketInputs:
    """Independent price and corporate-action rows for existing analytical builders."""

    quotes: tuple[JsonRow, ...]
    dividends: tuple[JsonRow, ...]
    splits: tuple[JsonRow, ...]


def project_market_inputs(
    *,
    quotes: tuple[EodQuote, ...],
    dividends: tuple[Dividend, ...],
    splits: tuple[Split, ...],
) -> AnalyticalMarketInputs:
    """Map raw source DTOs without adjusting prices for dividends or splits."""
    return AnalyticalMarketInputs(
        quotes=tuple(_quote_row(quote) for quote in quotes),
        dividends=tuple(_dividend_row(dividend) for dividend in dividends),
        splits=tuple(_split_row(split) for split in splits),
    )


def _quote_row(quote: EodQuote) -> JsonRow:
    if quote.adjusted_close is None:
        raise MarketProjectionError(MISSING_ADJUSTED_CLOSE)
    return {
        **_identity(quote.key.isin, quote.key.exchange, quote.key.code),
        "date": quote.trade_date.isoformat(),
        "adjusted_close": _as_float(quote.adjusted_close),
        "close": _optional_float(quote.close),
        "volume": _optional_float(quote.volume),
    }


def _dividend_row(dividend: Dividend) -> JsonRow:
    amount = _optional_float(dividend.amount)
    return {
        **_identity(dividend.key.isin, dividend.key.exchange, dividend.key.code),
        "date": dividend.event_date.isoformat(),
        "event_id": dividend.event_key,
        "amount": amount,
        "value": amount,
        "currency": dividend.currency,
    }


def _split_row(split: Split) -> JsonRow:
    return {
        **_identity(split.key.isin, split.key.exchange, split.key.code),
        "date": split.event_date.isoformat(),
        "split_ratio": split.split_ratio,
        "split_factor": _optional_float(split.split_factor),
    }


def _identity(isin: str, exchange: str, code: str) -> JsonRow:
    return {"isin": isin, "exchange": exchange, "code": code}


def _as_float(value: Decimal) -> float:
    return float(value)


def _optional_float(value: Decimal | None) -> float | None:
    return None if value is None else _as_float(value)
