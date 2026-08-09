"""Local filesystem and workflow adapter for the hosted application."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import ProcessPoolExecutor
from itertools import repeat
from pathlib import Path
from typing import Any, cast

from portfell.config import EodhdConfig
from portfell.hosted_api_errors import HostedRuntimeError
from portfell.hosted_api_ports import ProgressCallback, Workflow
from portfell.hosted_research_ports import ResearchDataset, UnivariateProgress
from portfell.http import EodhdHttpError
from portfell.metadata_filter import write_metadata_selection
from portfell.paths import LakePaths
from portfell.selection_filters import Predicate, parse_predicates
from portfell.table_io import JsonRow, read_json, read_rows, write_rows
from portfell.univariate_statistics import (
    annual_dividend_features,
    build_univariate_statistics,
    distribution_features,
    index_distribution_events,
)


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

    def run_metadata(
        self, *, provider_key: str, concurrency: int, on_progress: ProgressCallback
    ) -> dict[str, Any]:
        try:
            return self._metadata_workflow(
                root=self._paths().root,
                eodhd_config=EodhdConfig(api_token=provider_key),
                concurrency=concurrency,
                on_progress=on_progress,
            )
        except EodhdHttpError as error:
            code = (
                "eodhd_key_rejected"
                if error.status_code in {401, 403}
                else "eodhd_metadata_unavailable"
            )
            raise HostedRuntimeError(code) from error
        except PermissionError as error:
            raise HostedRuntimeError("lake_write_permission_denied") from error
        except ValueError as error:
            raise HostedRuntimeError("eodhd_metadata_invalid_response") from error

    def process_cpu_count(self) -> int:
        return max(1, self._cpu_count() or os.cpu_count() or 1)

    def selected_rows(
        self, member_ids: tuple[str, ...], *, dataset: ResearchDataset
    ) -> tuple[JsonRow, ...]:
        """Read only rows belonging to the selected listing identities."""

        paths = self._paths()
        rows: list[JsonRow] = []
        for member_id in member_ids:
            isin, exchange, code = member_id.split(":", 2)
            source_paths = (
                (paths.silver_quote_file(exchange, isin),)
                if dataset == "quotes"
                else tuple((paths.bronze / dataset / exchange).glob(f"*/{isin}.parquet"))
            )
            for path in source_paths:
                rows.extend(row for row in read_rows(path) if str(row.get("code", "")) == code)
        return tuple(rows)

    def build_univariate_rows(
        self,
        member_ids: tuple[str, ...],
        *,
        on_progress: UnivariateProgress | None = None,
    ) -> tuple[JsonRow, ...]:
        """Build selected univariate rows in worker processes using the local lake."""

        rows: list[JsonRow] = []
        with ProcessPoolExecutor(max_workers=self.process_cpu_count()) as executor:
            computed_rows = executor.map(
                _build_scoped_univariate_listing,
                repeat(self._paths().root),
                member_ids,
            )
            for index, row in enumerate(computed_rows, start=1):
                if row is not None:
                    rows.append(row)
                if on_progress is not None:
                    on_progress(index)
        return tuple(rows)


def _build_scoped_univariate_listing(root: Path, member_id: str) -> JsonRow | None:
    """Load or calculate one listing without sharing mutable process state."""

    paths = LakePaths(root=root)
    isin, exchange, code = member_id.split(":", 2)
    dividend_rows = [
        row
        for path in (paths.bronze / "dividends" / exchange).glob(f"*/{isin}.parquet")
        for row in read_rows(path)
        if str(row.get("code", "")) == code
    ]
    cached_rows = read_rows(paths.gold_univariate_statistics(exchange, isin))
    if len(cached_rows) == 1 and str(cached_rows[0].get("code", "")) == code:
        row = dict(cached_rows[0])
        dates = index_distribution_events(dividend_rows).get((isin, exchange, code), ())
        features = {
            **distribution_features(dates),
            **annual_dividend_features(
                dividend_rows,
                str(row["last_quote_date"]),
                float(row["end_adjusted_close"]),
            ),
        }
        if any(row.get(key) != value for key, value in features.items()):
            row.update(features)
            write_rows(paths.gold_univariate_statistics(exchange, isin), [row])
        return row
    quote_rows = [
        row
        for row in read_rows(paths.silver_quote_file(exchange, isin))
        if str(row.get("code", "")) == code
    ]
    if not quote_rows:
        return None
    return build_univariate_statistics(quote_rows, dividend_rows=dividend_rows, concurrency=None)[0]
