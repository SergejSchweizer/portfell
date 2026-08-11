"""Shared-store runtime adapter used by the PostgreSQL hosted application.

The hosted HTTP process deliberately has no lake or workspace dependency.  Market
refreshes are worker-owned; this adapter can only read the published shared
catalogue and rejects legacy, user-triggered provider workflows.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from portfell.hosted_api_errors import HostedRuntimeError
from portfell.hosted_api_ports import ProgressCallback
from portfell.selection_filters import Predicate
from portfell.table_io import JsonRow, read_rows


class PostgresHostedRuntime:
    """Read shared metadata while enforcing worker-only market mutations."""

    def __init__(self, shared_data_root: Path) -> None:
        self._metadata_path = shared_data_root / "market-data" / "metadata" / "current.parquet"

    def all_isins_rows(self) -> tuple[JsonRow, ...]:
        """Return the published metadata catalogue, if operations has published one."""

        return tuple(read_rows(self._metadata_path)) if self._metadata_path.exists() else ()

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
