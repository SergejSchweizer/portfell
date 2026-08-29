"""Deterministic lineage for materialized external market-source records."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass

from portfell.contract_versioning import ContractVersion, canonical_json
from portfell.market_source.contracts import Dividend, EodQuote, Listing, Split

MARKET_SOURCE_SNAPSHOT_CONTRACT = ContractVersion("market_source.snapshot", 1)


@dataclass(frozen=True)
class MarketSourceSnapshot:
    """Immutable semantic identity of the market records consumed by analytics."""

    snapshot_id: str
    contract_version: ContractVersion
    listings: tuple[Listing, ...]
    quotes: tuple[EodQuote, ...]
    dividends: tuple[Dividend, ...]
    splits: tuple[Split, ...]


def build_market_source_snapshot(
    *,
    listings: Iterable[Listing],
    quotes: Iterable[EodQuote],
    dividends: Iterable[Dividend],
    splits: Iterable[Split],
) -> MarketSourceSnapshot:
    """Materialize records and derive a streaming hash from semantic source fields only."""
    records = (
        tuple(sorted(listings, key=lambda item: item.key)),
        tuple(sorted(quotes, key=lambda item: (item.key, item.trade_date))),
        tuple(sorted(dividends, key=lambda item: (item.key, item.event_date, item.event_key))),
        tuple(sorted(splits, key=lambda item: (item.key, item.event_date, item.split_ratio))),
    )
    digest = hashlib.sha256()
    for dataset, values in zip(("listings", "quotes", "dividends", "splits"), records, strict=True):
        digest.update(dataset.encode("ascii"))
        digest.update(b"\n")
        for value in values:
            digest.update(canonical_json(_semantic_row(value)).encode("utf-8"))
            digest.update(b"\n")
    return MarketSourceSnapshot(
        snapshot_id=f"market_source_snapshot_{digest.hexdigest()[:16]}",
        contract_version=MARKET_SOURCE_SNAPSHOT_CONTRACT,
        listings=records[0],
        quotes=records[1],
        dividends=records[2],
        splits=records[3],
    )


def _semantic_row(value: Listing | EodQuote | Dividend | Split) -> dict[str, object]:
    key = value.key
    row: dict[str, object] = {"isin": key.isin, "exchange": key.exchange, "code": key.code}
    if isinstance(value, Listing):
        return {
            **row,
            "name": value.name,
            "instrument_type": value.instrument_type,
            "country": value.country,
            "currency": value.currency,
            "is_active": value.is_active,
        }
    if isinstance(value, EodQuote):
        return {
            **row,
            "trade_date": value.trade_date.isoformat(),
            "adjusted_close": _optional_decimal(value.adjusted_close),
            "close": _optional_decimal(value.close),
            "volume": _optional_decimal(value.volume),
        }
    if isinstance(value, Dividend):
        return {
            **row,
            "event_date": value.event_date.isoformat(),
            "event_key": value.event_key,
            "amount": _optional_decimal(value.amount),
            "currency": value.currency,
        }
    return {
        **row,
        "event_date": value.event_date.isoformat(),
        "split_ratio": value.split_ratio,
        "split_factor": _optional_decimal(value.split_factor),
    }


def _optional_decimal(value: object) -> str | None:
    return str(value) if value is not None else None
