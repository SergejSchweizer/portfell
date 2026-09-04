"""Pure enrichment of legacy Univariate rows with the income-first metric catalog."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from math import sqrt
from statistics import mean, stdev
from typing import Any, cast

from portfell.univariate_metric_catalog import METRIC_IDS


def enrich_univariate_row(
    row: Mapping[str, Any],
    quotes: Sequence[Mapping[str, Any]],
    dividends: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Add v3 metric values while retaining all v2 fields byte-for-byte."""
    enriched = dict(row)
    valid_quote_rows = [item for item in quotes if item.get("adjusted_close")]
    valid_dates = [date.fromisoformat(str(item["date"])) for item in valid_quote_rows]
    simple_returns = [
        float(current["adjusted_close"]) / float(previous["adjusted_close"]) - 1.0
        for previous, current in zip(valid_quote_rows, valid_quote_rows[1:], strict=False)
        if float(previous["adjusted_close"]) > 0
    ]
    positive = [item for item in dividends if _amount(item) > 0 and item.get("date")]
    amounts = [_amount(item) for item in positive]
    first = min(valid_dates) if valid_dates else None
    last = max(valid_dates) if valid_dates else None
    distribution_years = (
        (
            (
                max(date.fromisoformat(str(item["date"])) for item in positive)
                - min(date.fromisoformat(str(item["date"])) for item in positive)
            ).days
            / 365.25
        )
        if len(positive) > 1
        else 0.0
    )
    values: dict[str, Any] = {
        "history_years": 0.0 if first is None or last is None else (last - first).days / 365.25,
        "distribution_history_years": distribution_years,
        "observation_count": len(valid_dates),
        "missing_ratio": 0.0 if valid_dates else 1.0,
        "distribution_frequency": row.get("distribution_frequency", "unknown"),
        "distributions_per_year": row.get("distribution_events_per_year", 0.0),
        "ttm_distribution": row.get("annual_dividend_amount"),
        "ttm_distribution_yield": row.get("annual_dividend_yield"),
        "distribution_cv": _cv(amounts),
        "distribution_regularity": _regularity(
            str(row.get("distribution_frequency", "unknown")), amounts
        ),
        "distribution_cut_ratio": _cut_ratio(amounts),
        "max_distribution_cut": _max_cut(amounts),
        "distribution_growth_positive_year_ratio": _growth_ratio(amounts),
        "distribution_drawdown": _drawdown(amounts),
        "total_return_cagr": row.get("cagr"),
        "cumulative_extended_return": row.get(
            "cumulative_extended_return", row.get("total_return")
        ),
        # Preserve the return metrics calculated from the monthly quote series;
        # the v3 catalog enrichment must not replace them with ``None``.
        "monthly_log_return": row.get("monthly_log_return"),
        "monthly_simple_return": row.get("monthly_simple_return"),
        "monthly_geometric_return": row.get("monthly_geometric_return"),
        "annualized_volatility": row.get("annualized_volatility"),
        "downside_deviation": row.get("downside_deviation"),
        "max_drawdown": row.get("max_drawdown"),
        "current_drawdown": row.get("max_drawdown"),
        "var_95": _tail(simple_returns, 0.95)[0],
        "cvar_95": _tail(simple_returns, 0.95)[1],
        "ulcer_index": abs(float(row.get("max_drawdown", 0.0) or 0.0)) / sqrt(2.0),
        "sharpe": row.get("sharpe_ratio"),
        "sortino": row.get("sortino_ratio"),
        "calmar": _ratio(row.get("cagr"), row.get("max_drawdown")),
    }
    for metric in METRIC_IDS:
        values.setdefault(metric, None)
    enriched.update(values)
    enriched["metric_availability"] = {
        metric: ("ok" if values.get(metric) is not None else "insufficient_history")
        for metric in METRIC_IDS
    }
    enriched["metric_contract"] = "univariate.metrics.v3"
    return enriched


def _amount(row: Mapping[str, Any]) -> float:
    return float(row.get("value", row.get("unadjustedValue", 0.0)) or 0.0)


def _cv(values: Sequence[float]) -> float | None:
    return None if len(values) < 2 or mean(values) == 0 else stdev(values) / mean(values)


def _regularity(frequency: str, values: Sequence[float]) -> float | None:
    return None if not values or frequency in {"unknown", "accumulating"} else 1.0


def _cut_ratio(values: Sequence[float]) -> float | None:
    if len(values) < 2:
        return None
    return sum(1 for before, after in zip(values, values[1:], strict=False) if after < before) / (
        len(values) - 1
    )


def _max_cut(values: Sequence[float]) -> float | None:
    cuts = [
        (after / before) - 1.0
        for before, after in zip(values, values[1:], strict=False)
        if before > 0 and after < before
    ]
    return min(cuts) if cuts else None


def _growth_ratio(values: Sequence[float]) -> float | None:
    return (
        None
        if len(values) < 2
        else sum(after > before for before, after in zip(values, values[1:], strict=False))
        / (len(values) - 1)
    )


def _drawdown(values: Sequence[float]) -> float | None:
    if not values:
        return None
    peak = values[0]
    return min((value / (peak := max(peak, value))) - 1.0 for value in values)


def _tail(values: object, confidence: float) -> tuple[float | None, float | None]:
    if not isinstance(values, (list, tuple)) or not values:
        return None, None
    raw_values = cast(list[object] | tuple[object, ...], values)
    numeric_values = [value for value in raw_values if isinstance(value, (int, float))]
    if not numeric_values:
        return None, None
    losses = sorted(-float(value) for value in numeric_values)
    threshold = losses[min(len(losses) - 1, int(confidence * len(losses)))]
    tail = [value for value in losses if value >= threshold]
    return threshold, mean(tail)


def _ratio(numerator: object, denominator: object) -> float | None:
    if (
        not isinstance(numerator, (int, float))
        or not isinstance(denominator, (int, float))
        or denominator == 0
    ):
        return None
    return float(numerator) / abs(float(denominator))


__all__ = ["enrich_univariate_row"]
