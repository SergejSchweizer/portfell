"""Typed ports used by hosted application services."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any, Protocol

from portfell.selection_filters import Predicate
from portfell.table_io import JsonRow

ProgressCallback = Callable[[int, int, int], None]
Workflow = Callable[..., dict[str, Any]]


class HostedRuntimePort(Protocol):
    """External runtime operations required by hosted services."""

    def all_isins_rows(self) -> tuple[JsonRow, ...]: ...

    def write_metadata_selection(
        self,
        selection_id: str,
        rows: Iterable[Mapping[str, Any]],
        predicates: tuple[Predicate, ...],
    ) -> None: ...

    def metadata_filter_predicates(self, selection_id: str) -> tuple[Predicate, ...]: ...

    def run_quotes(
        self,
        *,
        provider_key: str,
        run_id: str,
        selection_id: str,
        concurrency: int,
        on_progress: ProgressCallback,
    ) -> dict[str, Any]: ...

    def run_metadata(
        self, *, provider_key: str, concurrency: int, on_progress: ProgressCallback
    ) -> dict[str, Any]: ...

    def process_cpu_count(self) -> int: ...
