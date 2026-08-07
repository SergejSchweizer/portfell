"""Local filesystem and workflow adapter for the hosted application."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any, cast

from portfell.config import EodhdConfig
from portfell.hosted_api_errors import HostedRuntimeError
from portfell.hosted_api_ports import ProgressCallback, Workflow
from portfell.http import EodhdHttpError
from portfell.metadata_filter import write_metadata_selection
from portfell.paths import LakePaths
from portfell.selection_filters import Predicate, parse_predicates
from portfell.table_io import JsonRow, read_json, read_rows


class LocalHostedRuntime:
    """Execute hosted external operations against the configured local lake."""

    def __init__(
        self,
        *,
        quote_workflow: Workflow,
        metadata_workflow: Workflow,
        cpu_count: Callable[[], int | None],
    ) -> None:
        self._quote_workflow = quote_workflow
        self._metadata_workflow = metadata_workflow
        self._cpu_count = cpu_count

    def _paths(self) -> LakePaths:
        return LakePaths(root=Path(os.environ.get("PORTFELL_LAKE_ROOT", "lake")))

    def all_isins_rows(self) -> tuple[JsonRow, ...]:
        return tuple(read_rows(self._paths().all_isins()))

    def write_metadata_selection(
        self,
        selection_id: str,
        rows: Iterable[Mapping[str, Any]],
        predicates: tuple[Predicate, ...],
    ) -> None:
        if "PORTFELL_LAKE_ROOT" not in os.environ:
            return
        paths = self._paths()
        write_metadata_selection(
            paths,
            selection_id,
            tuple(rows),
            predicates=predicates,
            source_path=str(paths.all_isins()),
        )

    def metadata_filter_predicates(self, selection_id: str) -> tuple[Predicate, ...]:
        manifest_path = self._paths().metadata_filter_manifest(selection_id)
        if not manifest_path.exists():
            return ()
        predicates = read_json(manifest_path).get("predicates", [])
        if not isinstance(predicates, list):
            raise ValueError("metadata filter manifest is invalid")
        values = cast("list[object]", predicates)
        if not all(isinstance(item, str) for item in values):
            raise ValueError("metadata filter manifest is invalid")
        return parse_predicates(cast("list[str]", values))

    def run_quotes(
        self,
        *,
        provider_key: str,
        run_id: str,
        selection_id: str,
        concurrency: int,
        on_progress: ProgressCallback,
    ) -> dict[str, Any]:
        return self._quote_workflow(
            root=self._paths().root,
            run_id=run_id,
            selection_id=selection_id,
            concurrency=concurrency,
            eodhd_config=EodhdConfig(api_token=provider_key),
            capture_scoped_rows=True,
            memory_safe=True,
            on_progress=on_progress,
        )

    def run_metadata(self, *, provider_key: str, on_progress: ProgressCallback) -> dict[str, Any]:
        try:
            return self._metadata_workflow(
                root=self._paths().root,
                eodhd_config=EodhdConfig(api_token=provider_key),
                on_progress=on_progress,
            )
        except EodhdHttpError as error:
            code = (
                "eodhd_key_rejected"
                if error.status_code in {401, 403}
                else "eodhd_metadata_unavailable"
            )
            raise HostedRuntimeError(code) from error
        except ValueError as error:
            raise HostedRuntimeError("eodhd_metadata_invalid_response") from error

    def process_cpu_count(self) -> int:
        return max(1, self._cpu_count() or os.cpu_count() or 1)
