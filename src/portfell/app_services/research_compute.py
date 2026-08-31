"""Pure deterministic Univariate/Bivariate computation for the clean application service."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from portfell.bivariate_statistics import BIVARIATE_STATISTICS_VERSION, build_bivariate_statistics
from portfell.gold_pair_stats import DEFAULT_MAX_PAIR_COUNT
from portfell.return_series import build_returns
from portfell.selection_filters import Predicate, filter_rows
from portfell.table_io import JsonRow
from portfell.univariate_statistics import (
    UNIVARIATE_CALCULATION_CONTRACT,
    build_univariate_statistics,
)

_ALLOWED_OPERATORS = frozenset({"=", "!=", ">", ">=", "<", "<="})


@dataclass(frozen=True)
class ComputedRun:
    run_id: str
    source_id: str
    algorithm_version: str
    rows: tuple[JsonRow, ...]


@dataclass(frozen=True)
class ComputedSelection:
    selection_id: str
    source_run_id: str
    member_ids: tuple[str, ...]
    predicates: tuple[Predicate, ...]
    rows: tuple[JsonRow, ...]


def stable_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def opaque_id(kind: str, payload: Mapping[str, object]) -> str:
    return f"{kind}-{stable_hash(payload)[:24]}"


def univariate_source_id(*, universe_id: str, market_snapshot_id: str) -> str:
    return stable_hash(
        {
            "universe_id": universe_id,
            "market_snapshot_id": market_snapshot_id,
            "calculation_contract": UNIVARIATE_CALCULATION_CONTRACT.qualified_name,
        }
    )


def bivariate_source_id(
    *, selection_id: str, member_ids: Sequence[str], market_snapshot_id: str
) -> str:
    return stable_hash(
        {
            "selection_id": selection_id,
            "member_ids": list(sorted(member_ids)),
            "market_snapshot_id": market_snapshot_id,
            "algorithm_version": BIVARIATE_STATISTICS_VERSION,
        }
    )


def compute_univariate(
    *,
    universe_id: str,
    market_snapshot_id: str,
    quote_rows: Sequence[Mapping[str, Any]],
    dividend_rows: Sequence[Mapping[str, Any]] = (),
    on_progress: Callable[[int], None] | None = None,
) -> ComputedRun:
    rows = tuple(
        build_univariate_statistics(
            quote_rows,
            dividend_rows=dividend_rows,
            concurrency=None,
            on_progress=on_progress,
        )
    )
    source_id = univariate_source_id(
        universe_id=universe_id, market_snapshot_id=market_snapshot_id
    )
    return ComputedRun(
        run_id=opaque_id("univariate-run", {"source_id": source_id}),
        source_id=source_id,
        algorithm_version=UNIVARIATE_CALCULATION_CONTRACT.qualified_name,
        rows=tuple(dict(row) for row in rows),
    )


def full_univariate_selection(run: ComputedRun) -> ComputedSelection:
    rows = tuple(dict(row) for row in run.rows)
    member_ids = tuple(sorted(_listing_id(row) for row in rows))
    selection_id = opaque_id(
        "univariate-selection",
        {"source_run_id": run.run_id, "member_ids": list(member_ids)},
    )
    return ComputedSelection(
        selection_id=selection_id,
        source_run_id=run.run_id,
        member_ids=member_ids,
        predicates=(),
        rows=rows,
    )


def filtered_univariate_selection(
    run: ComputedRun, predicate_rows: Sequence[Mapping[str, Any]]
) -> ComputedSelection:
    predicates = _normalize_predicates(predicate_rows)
    for predicate in predicates:
        if not any(predicate.field in row for row in run.rows):
            raise ValueError("invalid_metric")
    rows = tuple(filter_rows(run.rows, predicates))
    member_ids = tuple(sorted(_listing_id(row) for row in rows))
    selection_id = opaque_id(
        "univariate-selection",
        {
            "source_run_id": run.run_id,
            "predicates": [predicate.as_text() for predicate in predicates],
        },
    )
    return ComputedSelection(
        selection_id=selection_id,
        source_run_id=run.run_id,
        member_ids=member_ids,
        predicates=predicates,
        rows=rows,
    )


def compute_bivariate(
    *,
    selection: ComputedSelection,
    market_snapshot_id: str,
    quote_rows: Sequence[Mapping[str, Any]],
    max_pair_count: int = DEFAULT_MAX_PAIR_COUNT,
    on_progress: Callable[[int, int], None] | None = None,
) -> ComputedRun:
    listing_count = len(set(selection.member_ids))
    pair_count = listing_count * (listing_count - 1) // 2
    if listing_count < 2 or pair_count > max_pair_count:
        raise ValueError("pair_plan_not_runnable")
    members = set(selection.member_ids)
    scoped_quotes = tuple(row for row in quote_rows if _listing_id(row) in members)
    return_rows = build_returns(scoped_quotes)
    if {_listing_id(row) for row in return_rows} != members:
        raise ValueError("bivariate_return_history_incomplete")
    rows = tuple(
        build_bivariate_statistics(
            return_rows,
            concurrency=None,
            max_pair_count=max_pair_count,
            on_progress=on_progress,
        )
    )
    if not rows:
        raise ValueError("bivariate_common_history_unavailable")
    ordered = tuple(
        sorted(
            (dict(row) for row in rows),
            key=lambda row: (
                -abs(float(row.get("pearson_correlation", 0.0))),
                str(row["left_id"]),
                str(row["right_id"]),
            ),
        )
    )
    source_id = bivariate_source_id(
        selection_id=selection.selection_id,
        member_ids=selection.member_ids,
        market_snapshot_id=market_snapshot_id,
    )
    return ComputedRun(
        run_id=opaque_id("bivariate-run", {"source_id": source_id}),
        source_id=source_id,
        algorithm_version=BIVARIATE_STATISTICS_VERSION,
        rows=ordered,
    )


def _normalize_predicates(rows: Sequence[Mapping[str, Any]]) -> tuple[Predicate, ...]:
    predicates: list[Predicate] = []
    seen: dict[str, set[str]] = {}
    for row in rows:
        metric = str(row.get("metric", "")).strip()
        comparison = str(row.get("operator", "")).strip()
        value = row.get("value")
        if not metric or comparison not in _ALLOWED_OPERATORS:
            raise ValueError("invalid_predicate")
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(value)
        ):
            raise ValueError("invalid_predicate_value")
        operators = seen.setdefault(metric, set())
        if comparison in operators:
            raise ValueError("duplicate_predicate")
        operators.add(comparison)
        predicates.append(Predicate(metric, comparison, str(float(value))))
    if not predicates:
        raise ValueError("predicates_required")
    return tuple(sorted(predicates, key=lambda item: (item.field, item.operator, item.expected)))


def _listing_id(row: Mapping[str, Any]) -> str:
    return f"{row.get('isin', '')}:{row.get('exchange', '')}:{row.get('code', '')}"
