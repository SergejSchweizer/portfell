"""Exact value contracts for the external Xetra market source."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, order=True)
class ListingKey:
    """Full external listing identity; ISIN alone is never a market key."""

    isin: str
    exchange: str
    code: str


@dataclass(frozen=True)
class Listing:
    key: ListingKey
    name: str
    instrument_type: str
    country: str | None
    currency: str | None
    is_active: bool


@dataclass(frozen=True)
class EodQuote:
    key: ListingKey
    trade_date: date
    adjusted_close: Decimal | None
    close: Decimal | None
    volume: Decimal | None


@dataclass(frozen=True)
class Dividend:
    key: ListingKey
    event_date: date
    event_key: str
    amount: Decimal | None
    currency: str | None


@dataclass(frozen=True)
class Split:
    key: ListingKey
    event_date: date
    split_ratio: str
    split_factor: Decimal | None
