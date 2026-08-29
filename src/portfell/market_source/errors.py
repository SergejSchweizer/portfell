"""Stable public errors for external market-source operations."""

from __future__ import annotations


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
