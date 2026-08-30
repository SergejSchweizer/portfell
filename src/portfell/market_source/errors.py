"""Stable public errors for external market-source operations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Never


class MarketSourceError(RuntimeError):
    """Typed, redacted market-source failure."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


MARKET_SOURCE_CONFIG_MISSING = "market_source_config_missing"
MARKET_SOURCE_UNAVAILABLE = "market_source_unavailable"
MARKET_SOURCE_ROLE_INVALID = "market_source_role_invalid"
MARKET_SOURCE_CONTRACT_MISMATCH = "market_source_contract_mismatch"
MARKET_SOURCE_DUPLICATE_KEY = "market_source_duplicate_key"
MARKET_SOURCE_INVALID_VALUE = "market_source_invalid_value"

FROZEN_ERROR_CODES = frozenset(
    {
        MARKET_SOURCE_CONFIG_MISSING,
        MARKET_SOURCE_UNAVAILABLE,
        MARKET_SOURCE_ROLE_INVALID,
        MARKET_SOURCE_CONTRACT_MISMATCH,
        MARKET_SOURCE_DUPLICATE_KEY,
        MARKET_SOURCE_INVALID_VALUE,
    }
)


def market_source_required() -> Never:
    """Fail closed when a retired local acquisition path is invoked."""

    raise MarketSourceError(MARKET_SOURCE_UNAVAILABLE)


class UnavailableMarketDataClient:
    """Minimal non-network seam for transitional lifecycle owners."""

    def get_json(
        self, path: str, params: Mapping[str, str | int | float] | None = None
    ) -> Never:
        del path, params
        market_source_required()
