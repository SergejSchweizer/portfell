"""Gateway-backed runtime adapter used by the PostgreSQL hosted application."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from typing import Any

from portfell.hosted_api_errors import HostedRuntimeError
from portfell.hosted_api_ports import ProgressCallback
from portfell.market_source.gateway import MarketDataGateway
from portfell.selection_filters import Predicate
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

    def write_metadata_selection(
        self,
        selection_id: str,
        rows: Iterable[Mapping[str, Any]],
        predicates: tuple[Predicate, ...],
    ) -> None:
        """Selections are relational records; no hosted filesystem manifest is written."""

        del selection_id, rows, predicates

    def metadata_builder_predicates(self, selection_id: str) -> tuple[Predicate, ...]:
        """Legacy filesystem manifests are intentionally unavailable in hosted mode."""

        del selection_id
        return ()

    def run_quotes(
        self,
        *,
        provider_key: str,
        run_id: str,
        selection_id: str,
        concurrency: int,
        on_progress: ProgressCallback,
    ) -> dict[str, Any]:
        """Reject browser-initiated refreshes; bootstrap/cron workers own provider access."""

        del provider_key, run_id, selection_id, concurrency, on_progress
        raise HostedRuntimeError("market_refresh_is_operations_only")

    def run_metadata(
        self, *, provider_key: str, concurrency: int, on_progress: ProgressCallback
    ) -> dict[str, Any]:
        """Reject legacy user metadata fetching in the hosted HTTP process."""

        del provider_key, concurrency, on_progress
        raise HostedRuntimeError("metadata_refresh_is_operations_only")

    def process_cpu_count(self) -> int:
        return max(1, os.process_cpu_count() or os.cpu_count() or 1)
