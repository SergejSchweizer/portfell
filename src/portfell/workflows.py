"""Operational workflows behind the Portfell CLI modules."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from portfell.bivariate_statistics import resolve_worker_count, write_bivariate_statistics
from portfell.logging import get_logger, log_event
from portfell.metadata_builder import run_metadata_builder
from portfell.multivariate_statistics import (
    MultivariateStatisticsConfig,
    write_multivariate_statistics,
)
from portfell.paths import LakePaths
from portfell.portfolio import PortfolioConstraints
from portfell.run_locks import module_run_lock
from portfell.selection_filters import parse_predicates
from portfell.silver import read_silver_quotes
from portfell.table_io import read_json, read_rows
from portfell.univariate_selection import run_univariate_selection, selection_rows
from portfell.univariate_statistics import (
    DEFAULT_CONFIDENCE_LEVEL,
    build_quote_returns,
    write_univariate_statistics,
)

LOGGER = get_logger(__name__)


def run_metadata_builder_workflow(
    *,
    root: Path,
    predicates: Sequence[str],
    name_contains: Sequence[str] = (),
    selection_name: str | None = None,
) -> dict[str, Any]:
    """Run Metadata Builder over the reference all-ISIN dataset."""
    paths = LakePaths(root=root)
    with module_run_lock(paths, "metadata-builder"):
        resolved_predicates = tuple(predicates) + tuple(
            f"name~{search_text}" for search_text in name_contains
        )
        if not resolved_predicates:
            raise ValueError("metadata-builder requires at least one --where or --name-contains")
        return run_metadata_builder(
            paths,
            parse_predicates(resolved_predicates),
            name=selection_name,
        )


def run_univariate_statistics_workflow(
    *,
    root: Path,
    selection_id: str | None = None,
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
    concurrency: int | None = None,
) -> dict[str, Any]:
    """Build reusable per-listing statistics for one Metadata Builder selection."""
    paths = LakePaths(root=root)
    with module_run_lock(paths, "univariate-statistics"):
        resolved_selection_id = selection_id or _current_metadata_selection_id(paths)
        log_event(
            LOGGER,
            logging.INFO,
            module="univariate-statistics",
            event="started",
            fields={"root": root, "selection_id": resolved_selection_id},
        )
        selected_rows = _metadata_selection_rows(paths, resolved_selection_id)
        quotes = _filter_quotes_to_selection(read_silver_quotes(paths), selected_rows)
        dividends = _filter_quotes_to_selection(_read_bronze_dividends(paths), selected_rows)
        rows = write_univariate_statistics(
            paths,
            quotes,
            dividend_rows=dividends,
            confidence_level=confidence_level,
            concurrency=concurrency,
        )
        workers = _worker_count(concurrency)
        log_event(
            LOGGER,
            logging.INFO,
            module="univariate-statistics",
            event="completed",
            fields={"root": root, "rows": len(rows)},
        )
        return {
            "quote_rows": len(quotes),
            "dividend_rows": len(dividends),
            "concurrency": workers,
            "selected_listing_count": len(selected_rows),
            "selection_id": resolved_selection_id,
            "univariate_statistics_rows": len(rows),
        }


def run_univariate_selection_workflow(
    *,
    root: Path,
    predicates: Sequence[str],
    selection_name: str | None = None,
) -> dict[str, Any]:
    """Run Univariate Selection over persisted Gold univariate statistics."""
    paths = LakePaths(root=root)
    with module_run_lock(paths, "univariate-selection"):
        return run_univariate_selection(
            paths,
            parse_predicates(predicates),
            name=selection_name,
        )


def run_bivariate_statistics_workflow(
    *,
    root: Path,
    selection_id: str | None = None,
    concurrency: int | None = None,
) -> dict[str, Any]:
    """Build reusable pairwise statistics from existing Silver quotes."""
    paths = LakePaths(root=root)
    with module_run_lock(paths, "bivariate-statistics"):
        resolved_selection_id = selection_id or _current_univariate_selection_id(paths)
        log_event(
            LOGGER,
            logging.INFO,
            module="bivariate-statistics",
            event="started",
            fields={"root": root, "selection_id": resolved_selection_id},
        )
        quotes = read_silver_quotes(paths)
        quotes = _filter_quotes_to_selection(quotes, selection_rows(paths, resolved_selection_id))
        returns = build_quote_returns(quotes)
        rows = write_bivariate_statistics(paths, returns, concurrency=concurrency)
        workers = resolve_worker_count(concurrency)
        log_event(
            LOGGER,
            logging.INFO,
            module="bivariate-statistics",
            event="completed",
            fields={"root": root, "rows": len(rows)},
        )
        return {
            "bivariate_statistics_rows": len(rows),
            "concurrency": workers,
            "quote_rows": len(quotes),
            "return_rows": len(returns),
            "selection_id": resolved_selection_id,
        }


def run_multivariate_statistics_workflow(
    *,
    root: Path,
    selection_id: str | None = None,
    evaluation_id: str = "multivariate-latest",
    portfolio_id_prefix: str = "multivariate",
    confidence_level: float = 0.95,
    grid_step: float = 0.1,
    train_window: int = 2,
    test_window: int = 1,
    walk_forward_profile: str = "development",
    rebalance_schedule: str = "monthly",
    transaction_cost_rate: float = 0.0,
    drift_threshold: float | None = None,
    min_weight: float = 0.0,
    max_weight: float = 1.0,
    concurrency: int | None = None,
    use_selection_statistics_cache: bool = False,
) -> dict[str, Any]:
    """Build multivariate portfolio statistics from a Univariate Statistics selection."""
    paths = LakePaths(root=root)
    with module_run_lock(paths, "multivariate-statistics"):
        resolved_selection_id = selection_id or _current_univariate_selection_id(paths)
        log_event(
            LOGGER,
            logging.INFO,
            module="multivariate-statistics",
            event="started",
            fields={"root": root, "selection_id": resolved_selection_id},
        )
        summary = write_multivariate_statistics(
            paths,
            selection_rows(paths, resolved_selection_id),
            config=MultivariateStatisticsConfig(
                evaluation_id=evaluation_id,
                portfolio_id_prefix=portfolio_id_prefix,
                confidence_level=confidence_level,
                grid_step=grid_step,
                train_window=train_window,
                test_window=test_window,
                walk_forward_profile=walk_forward_profile,
                rebalance_schedule=rebalance_schedule,
                transaction_cost_rate=transaction_cost_rate,
                drift_threshold=drift_threshold,
                constraints=PortfolioConstraints(min_weight=min_weight, max_weight=max_weight),
                concurrency=concurrency,
                selection_id=resolved_selection_id,
                selection_source_module="univariate_selection",
                use_selection_statistics_cache=use_selection_statistics_cache,
            ),
        )
        log_event(
            LOGGER,
            logging.INFO,
            module="multivariate-statistics",
            event="completed",
            fields={
                "evaluation_id": evaluation_id,
                "portfolio_count": summary["portfolio_count"],
                "selection_id": resolved_selection_id,
            },
        )
        return {"selection_id": resolved_selection_id, **summary}


def _filter_quotes_to_selection(
    quotes: Sequence[Mapping[str, Any]],
    selected_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    selected = {(str(row["isin"]), str(row["exchange"]), str(row["code"])) for row in selected_rows}
    return [
        dict(row)
        for row in quotes
        if (str(row["isin"]), str(row["exchange"]), str(row["code"])) in selected
    ]


def _metadata_selection_rows(paths: LakePaths, selection_id: str) -> list[dict[str, Any]]:
    selection_path = paths.metadata_builder_isins(selection_id)
    if not selection_path.exists():
        raise FileNotFoundError(f"metadata-builder selection does not exist: {selection_id}")
    return read_rows(selection_path)


def _read_bronze_dividends(paths: LakePaths) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted((paths.bronze / "dividends").glob("*/*/*.parquet")):
        rows.extend(read_rows(path))
    return rows


def _worker_count(concurrency: int | None) -> int:
    if concurrency is not None:
        return max(1, concurrency)
    return max(1, os.cpu_count() or 1)


def _current_metadata_selection_id(paths: LakePaths) -> str:
    pointer_path = paths.current_metadata_builder_selection()
    if pointer_path.exists():
        return str(read_json(pointer_path)["selection_id"])
    return _latest_metadata_selection_id(paths)


def _current_univariate_selection_id(paths: LakePaths) -> str:
    pointer_path = paths.current_univariate_selection()
    if pointer_path.exists():
        return str(read_json(pointer_path)["selection_id"])
    return _latest_univariate_selection_id(paths)


def _latest_metadata_selection_id(paths: LakePaths) -> str:
    manifests = sorted((paths.silver / "metadata_builder").glob("selection_id=*/manifest.json"))
    latest: tuple[str, str] | None = None
    for manifest_path in manifests:
        manifest = read_json(manifest_path)
        selection_id = str(manifest["selection_id"])
        created_at = str(manifest.get("created_at", ""))
        candidate = (created_at, selection_id)
        if latest is None or candidate > latest:
            latest = candidate
    if latest is None:
        raise FileNotFoundError("metadata-builder selection does not exist")
    return latest[1]


def _latest_univariate_selection_id(paths: LakePaths) -> str:
    manifests = sorted((paths.silver / "univariate_selection").glob("selection_id=*/manifest.json"))
    latest: tuple[str, str] | None = None
    for manifest_path in manifests:
        manifest = read_json(manifest_path)
        selection_id = str(manifest["selection_id"])
        created_at = str(manifest.get("created_at", ""))
        candidate = (created_at, selection_id)
        if latest is None or candidate > latest:
            latest = candidate
    if latest is None:
        raise FileNotFoundError(
            "univariate selection does not exist; run univariate-selection first"
        )
    return latest[1]
