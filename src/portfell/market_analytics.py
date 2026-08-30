"""Pure market analytics with no storage or provider authority.

The functions in this module operate exclusively on caller supplied rows.  They
are deliberately separate from the removed Bronze/Silver/Gold lake pipeline so
the current PostgreSQL market-source services can reuse the calculations
without acquiring or persisting market data.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import sqrt
from typing import Any

from portfell.gold_pair_stats import (
    DEFAULT_MAX_PAIR_COUNT,
    build_pair_plan,
    correlation_value,
    incremental_pearson,
    index_returns,
    iter_pair_observations,
    limit_top_correlation_edges,
    sample_covariance,
    sort_pair_rows,
    symmetric_pair_rows,
)
from portfell.table_io import JsonRow


def build_returns(quote_rows: Sequence[Mapping[str, Any]]) -> list[JsonRow]:
    """Build log and simple returns from valid caller-provided quote rows."""

    from portfell.return_series import build_returns as build_return_series

    return build_return_series(quote_rows)


def covariance(left_values: Sequence[float], right_values: Sequence[float]) -> float:
    """Return sample covariance without coercing invalid inputs to zero."""

    return sample_covariance(left_values, right_values)


def build_correlation_and_covariance(
    return_rows: Sequence[Mapping[str, Any]],
    *,
    max_pair_count: int = DEFAULT_MAX_PAIR_COUNT,
) -> tuple[list[JsonRow], list[JsonRow]]:
    """Build dense pair statistics in memory; this function never writes rows."""

    returns_by_listing = index_returns(return_rows)
    plan = build_pair_plan(len(returns_by_listing), mode="dense", max_pair_count=max_pair_count)
    if not plan.accepted:
        raise ValueError(f"correlation/covariance build rejected: {plan.rejection_reason}")
    correlations: list[JsonRow] = []
    covariances: list[JsonRow] = []
    for pair in iter_pair_observations(returns_by_listing, include_self=True):
        correlations.extend(
            symmetric_pair_rows(
                pair.left,
                pair.right,
                "correlation",
                incremental_pearson(pair.left_values, pair.right_values),
            )
        )
        covariances.extend(
            symmetric_pair_rows(
                pair.left,
                pair.right,
                "covariance",
                covariance(pair.left_values, pair.right_values),
            )
        )
    return sort_pair_rows(correlations), sort_pair_rows(covariances)


def build_correlation_edges(
    return_rows: Sequence[Mapping[str, Any]],
    *,
    version: str,
    metric: str = "pearson",
    min_abs_correlation: float | None = None,
    top_k_per_left: int | None = None,
    max_pair_count: int = DEFAULT_MAX_PAIR_COUNT,
) -> list[JsonRow]:
    """Build deterministic correlation edges in memory for caller persistence."""

    if metric not in {"pearson", "spearman"}:
        raise ValueError(f"unsupported correlation edge metric: {metric}")
    if min_abs_correlation is not None and not 0 <= min_abs_correlation <= 1:
        raise ValueError("min_abs_correlation must be in [0, 1]")
    if top_k_per_left is not None and top_k_per_left < 1:
        raise ValueError("top_k_per_left must be positive")
    returns_by_listing = index_returns(return_rows)
    mode = "dense" if min_abs_correlation is None and top_k_per_left is None else "sparse"
    plan = build_pair_plan(len(returns_by_listing), mode=mode, max_pair_count=max_pair_count)
    if not plan.accepted:
        raise ValueError(f"correlation edges build rejected: {plan.rejection_reason}")
    rows: list[JsonRow] = []
    for pair in iter_pair_observations(returns_by_listing, include_self=False, skip_same_isin=True):
        value = correlation_value(pair.left_values, pair.right_values, metric)
        if min_abs_correlation is not None and abs(value) < min_abs_correlation:
            continue
        rows.append(
            {
                "version": version,
                "metric": metric,
                "left_id": pair.left_id,
                "right_id": pair.right_id,
                "left_isin": pair.left[0],
                "left_exchange": pair.left[1],
                "left_code": pair.left[2],
                "right_isin": pair.right[0],
                "right_exchange": pair.right[1],
                "right_code": pair.right[2],
                "date_start": pair.dates[0] if pair.dates else "",
                "date_end": pair.dates[-1] if pair.dates else "",
                "n_observations": len(pair.dates),
                "value": value,
            }
        )
    return sorted(
        limit_top_correlation_edges(rows, top_k_per_left),
        key=lambda row: (int(row["left_id"]), -abs(float(row["value"])), int(row["right_id"])),
    )


def build_asset_features(
    quote_rows: Sequence[Mapping[str, Any]], return_rows: Sequence[Mapping[str, Any]]
) -> list[JsonRow]:
    """Build per-listing descriptive features without lake output."""

    quotes_by_listing: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for row in quote_rows:
        key = (str(row["isin"]), str(row["exchange"]), str(row["code"]))
        quotes_by_listing.setdefault(key, []).append(row)
    returns_by_listing: dict[tuple[str, str, str], list[float]] = {}
    for row in return_rows:
        key = (str(row["isin"]), str(row["exchange"]), str(row["code"]))
        returns_by_listing.setdefault(key, []).append(float(row["return"]))
    features: list[JsonRow] = []
    for (isin, exchange, code), quotes in sorted(quotes_by_listing.items()):
        ordered = sorted(quotes, key=lambda row: str(row["date"]))
        returns = returns_by_listing.get((isin, exchange, code), [])
        first_close = float(ordered[0]["adjusted_close"])
        last_close = float(ordered[-1]["adjusted_close"])
        peak: float | None = None
        maximum_drawdown = 0.0
        for row in ordered:
            close = float(row["adjusted_close"])
            peak = close if peak is None else max(peak, close)
            if peak:
                maximum_drawdown = min(maximum_drawdown, close / peak - 1.0)
        features.append(
            {
                "isin": isin,
                "exchange": exchange,
                "code": code,
                "first_quote_date": str(ordered[0]["date"]),
                "last_quote_date": str(ordered[-1]["date"]),
                "quote_observation_count": len(ordered),
                "return_observation_count": len(returns),
                "total_return": 0.0 if first_close == 0 else last_close / first_close - 1.0,
                "mean_return": sum(returns) / len(returns) if returns else 0.0,
                "volatility": sqrt(covariance(returns, returns)) if len(returns) >= 2 else 0.0,
                "max_drawdown": maximum_drawdown,
            }
        )
    return features


__all__ = [
    "build_asset_features",
    "build_correlation_and_covariance",
    "build_correlation_edges",
    "build_returns",
    "covariance",
]
