"""User-scoped execution services for the three-module hosted research workflow."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from portfell.bivariate_statistics import BIVARIATE_STATISTICS_VERSION, build_bivariate_statistics
from portfell.gold import build_returns
from portfell.gold_pair_stats import DEFAULT_MAX_PAIR_COUNT
from portfell.selection_filters import Predicate, filter_rows
from portfell.table_io import JsonRow
from portfell.univariate_statistics import (
    UNIVARIATE_CALCULATION_CONTRACT,
    build_univariate_statistics,
)

RunStatus = Literal["running", "complete", "failed"]
_ALLOWED_OPERATORS = frozenset({"=", "!=", ">", ">=", "<", "<="})


class HostedResearchError(RuntimeError):
    """Raised when a scoped hosted research request is invalid."""


@dataclass(frozen=True)
class ResearchRun:
    """One immutable user-owned analytical run."""

    run_id: str
    user_id: str
    source_id: str
    status: RunStatus
    rows: tuple[JsonRow, ...]
    total: int
    completed: int
    failed: int = 0


@dataclass(frozen=True)
class UnivariateSelection:
    """One deterministic selection produced from a univariate run."""

    selection_id: str
    user_id: str
    source_run_id: str
    member_ids: tuple[str, ...]
    predicates: tuple[Predicate, ...]
    rows: tuple[JsonRow, ...]
    input_count: int


def create_univariate_run(
    *,
    user_id: str,
    selection_id: str,
    quote_run_id: str,
    quote_rows: Sequence[Mapping[str, Any]],
    dividend_rows: Sequence[Mapping[str, Any]] = (),
    on_progress: Callable[[int], None] | None = None,
) -> ResearchRun:
    """Compute univariate rows from already scoped quote rows."""

    rows = tuple(
        build_univariate_statistics(
            quote_rows,
            dividend_rows=dividend_rows,
            concurrency=None,
            on_progress=on_progress,
        )
    )
    return create_univariate_run_from_statistics(
        user_id=user_id,
        selection_id=selection_id,
        quote_run_id=quote_run_id,
        rows=rows,
    )


def create_univariate_run_from_statistics(
    *,
    user_id: str,
    selection_id: str,
    quote_run_id: str,
    rows: Sequence[Mapping[str, Any]],
) -> ResearchRun:
    """Create a deterministic run from already computed per-listing rows."""

    source = univariate_source_id(selection_id, quote_run_id)
    return ResearchRun(
        run_id=_opaque_id("univariate-run", f"{user_id}:{source}"),
        user_id=user_id,
        source_id=source,
        status="complete",
        rows=tuple(dict(row) for row in rows),
        total=len(rows),
        completed=len(rows),
    )


def univariate_source_id(selection_id: str, quote_run_id: str) -> str:
    return _stable_hash(
        {
            "selection_id": selection_id,
            "quote_run_id": quote_run_id,
            "calculation_contract": UNIVARIATE_CALCULATION_CONTRACT,
        }
    )


def normalize_predicates(rows: Sequence[Mapping[str, Any]]) -> tuple[Predicate, ...]:
    """Validate and canonically order numerical predicates."""

    predicates: list[Predicate] = []
    seen: dict[str, set[str]] = {}
    for row in rows:
        metric = str(row.get("metric", "")).strip()
        comparison = str(row.get("operator", "")).strip()
        value = row.get("value")
        if not metric or comparison not in _ALLOWED_OPERATORS:
            raise HostedResearchError("invalid_predicate")
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(value)
        ):
            raise HostedResearchError("invalid_predicate_value")
        operators = seen.setdefault(metric, set())
        if comparison in operators:
            raise HostedResearchError("duplicate_predicate")
        operators.add(comparison)
        predicates.append(Predicate(metric, comparison, str(float(value))))
    if not predicates:
        raise HostedResearchError("predicates_required")
    return tuple(sorted(predicates, key=lambda item: (item.field, item.operator, item.expected)))


def create_univariate_selection(
    *, user_id: str, run: ResearchRun, predicate_rows: Sequence[Mapping[str, Any]]
) -> UnivariateSelection:
    """Apply predicates only to rows pinned to the source run."""

    predicates = normalize_predicates(predicate_rows)
    for predicate in predicates:
        if not any(predicate.field in row for row in run.rows):
            raise HostedResearchError("invalid_metric")
    rows = tuple(filter_rows(run.rows, predicates))
    member_ids = tuple(sorted(_listing_id(row) for row in rows))
    identity = _stable_hash(
        {
            "source_run_id": run.run_id,
            "predicates": [predicate.as_text() for predicate in predicates],
        }
    )
    return UnivariateSelection(
        selection_id=_opaque_id("univariate-selection", f"{user_id}:{identity}"),
        user_id=user_id,
        source_run_id=run.run_id,
        member_ids=member_ids,
        predicates=predicates,
        rows=rows,
        input_count=len(run.rows),
    )


def create_full_univariate_selection(
    *, user_id: str, run: ResearchRun, rows: Sequence[Mapping[str, Any]] | None = None
) -> UnivariateSelection:
    """Create the bivariate input selection from completed univariate rows."""

    selected_rows = tuple(dict(row) for row in (run.rows if rows is None else rows))
    member_ids = tuple(sorted(_listing_id(row) for row in selected_rows))
    identity = _stable_hash(
        {
            "source_run_id": run.run_id,
            "selection": "all" if rows is None else list(member_ids),
        }
    )
    return UnivariateSelection(
        selection_id=_opaque_id("univariate-selection", f"{user_id}:{identity}"),
        user_id=user_id,
        source_run_id=run.run_id,
        member_ids=member_ids,
        predicates=(),
        rows=selected_rows,
        input_count=len(selected_rows),
    )


def pair_plan(
    selection: UnivariateSelection, *, max_pair_count: int = DEFAULT_MAX_PAIR_COUNT
) -> JsonRow:
    """Return a fail-fast dense pair plan without materializing pairs."""

    listing_count = len(set(selection.member_ids))
    pair_count = listing_count * (listing_count - 1) // 2
    return {
        "selected_listing_count": listing_count,
        "theoretical_pair_count": pair_count,
        "pair_limit": max_pair_count,
        "allowed": pair_count <= max_pair_count and listing_count >= 2,
    }


def bivariate_source_id(selection: UnivariateSelection) -> str:
    """Hash selection membership together with the active bivariate algorithm."""
    return _stable_hash(
        {
            "selection_id": selection.selection_id,
            "members": list(selection.member_ids),
            "algorithm_version": BIVARIATE_STATISTICS_VERSION,
        }
    )


def create_bivariate_run(
    *,
    user_id: str,
    selection: UnivariateSelection,
    quote_rows: Sequence[Mapping[str, Any]],
    max_pair_count: int = DEFAULT_MAX_PAIR_COUNT,
    on_progress: Callable[[int, int], None] | None = None,
) -> ResearchRun:
    """Compute pair statistics from quote rows restricted to selected listings."""

    plan = pair_plan(selection, max_pair_count=max_pair_count)
    if not plan["allowed"]:
        raise HostedResearchError("pair_plan_not_runnable")
    members = set(selection.member_ids)
    scoped_quotes = tuple(row for row in quote_rows if _listing_id(row) in members)
    return_rows = build_returns(scoped_quotes)
    if {_listing_id(row) for row in return_rows} != members:
        raise HostedResearchError("bivariate_return_history_incomplete")
    rows = tuple(
        build_bivariate_statistics(
            return_rows,
            concurrency=None,
            max_pair_count=max_pair_count,
            on_progress=on_progress,
        )
    )
    if not rows:
        raise HostedResearchError("bivariate_common_history_unavailable")
    ordered = tuple(
        sorted(
            rows,
            key=lambda row: (
                -abs(float(row.get("pearson_correlation", 0.0))),
                str(row["left_id"]),
                str(row["right_id"]),
            ),
        )
    )
    source = bivariate_source_id(selection)
    return ResearchRun(
        run_id=_opaque_id("bivariate-run", f"{user_id}:{source}"),
        user_id=user_id,
        source_id=source,
        status="complete",
        rows=ordered,
        total=len(ordered),
        completed=len(ordered),
    )


def page_rows(rows: Sequence[JsonRow], *, limit: int, offset: int) -> JsonRow:
    """Return deterministic bounded pagination."""

    safe_limit = max(1, min(limit, 200))
    safe_offset = max(0, offset)
    return {
        "items": list(rows[safe_offset : safe_offset + safe_limit]),
        "total": len(rows),
        "limit": safe_limit,
        "offset": safe_offset,
    }


def _listing_id(row: Mapping[str, Any]) -> str:
    return f"{row.get('isin', '')}:{row.get('exchange', '')}:{row.get('code', '')}"


def _stable_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _opaque_id(kind: str, source: str) -> str:
    return f"{kind}-{hashlib.sha256(source.encode()).hexdigest()[:24]}"
