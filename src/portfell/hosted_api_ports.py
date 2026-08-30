"""Typed ports used by hosted application services."""

from __future__ import annotations

from typing import Protocol

from portfell.table_io import JsonRow


class HostedRuntimePort(Protocol):
    """External runtime operations required by hosted services."""

    def all_isins_rows(self) -> tuple[JsonRow, ...]: ...

    def process_cpu_count(self) -> int: ...
