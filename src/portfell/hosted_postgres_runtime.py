"""Gateway-backed runtime adapter used by the PostgreSQL hosted application."""

from __future__ import annotations

import os

from portfell.hosted_api_errors import HostedRuntimeError
from portfell.market_source.gateway import MarketDataGateway
from portfell.table_io import JsonRow


class PostgresHostedRuntime:
    """Read source metadata while rejecting legacy user-triggered mutations."""

    def __init__(
        self,
        market_gateway: MarketDataGateway | None = None,
    ) -> None:
        self._market_gateway = market_gateway

    @property
    def market_gateway(self) -> MarketDataGateway:
        """Return the server-owned external market reader when configured."""
        if self._market_gateway is None:
            raise HostedRuntimeError("market_source_not_configured")
        return self._market_gateway

    def all_isins_rows(self) -> tuple[JsonRow, ...]:
        """Return the active source metadata catalogue when configured."""

        return tuple(
            {
                "isin": listing.key.isin,
                "exchange": listing.key.exchange,
                "code": listing.key.code,
                "name": listing.name,
                "instrument_type": listing.instrument_type,
                "country": listing.country,
                "currency": listing.currency,
                "is_active": listing.is_active,
            }
            for listing in self.market_gateway.read_active_listings()
        )

    def process_cpu_count(self) -> int:
        return max(1, os.process_cpu_count() or os.cpu_count() or 1)
