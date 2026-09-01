"""Compact deterministic metric distributions for the Univariate read plane."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from math import ceil, floor, isfinite
from statistics import mean, median, pstdev
from typing import Any

from portfell.univariate_metric_catalog import CATALOG_BY_ID, METRIC_IDS


def build_metric_distributions(
    rows: Sequence[Mapping[str, Any]], *, chart_limit: int = 500
) -> dict[str, Any]:
    if chart_limit < 1 or chart_limit > 500:
        raise ValueError("chart_limit must be between 1 and 500")
    metrics: dict[str, Any] = {}
    for metric_id in METRIC_IDS:
        definition = CATALOG_BY_ID[metric_id]
        if definition.kind == "categorical":
            counts = Counter(str(row[metric_id]) for row in rows if row.get(metric_id) is not None)
            total = sum(counts.values())
            metrics[metric_id] = {
                "kind": "categorical",
                "available": total,
                "unavailable": len(rows) - total,
                "categories": [
                    {"category": category, "count": count, "share": count / total if total else 0.0}
                    for category, count in sorted(
                        counts.items(), key=lambda item: (-item[1], item[0])
                    )
                ],
            }
            continue
        values = sorted(
            float(row[metric_id])
            for row in rows
            if isinstance(row.get(metric_id), (int, float)) and isfinite(float(row[metric_id]))
        )
        metrics[metric_id] = {
            "kind": "continuous",
            "available": len(values),
            "unavailable": len(rows) - len(values),
            "summary": _summary(values),
            "histogram": _histogram(values, chart_limit),
            "ecdf": _ecdf(values, chart_limit),
        }
    return {"metric_contract": "univariate.metrics.v3", "item_count": len(rows), "metrics": metrics}


def _summary(values: Sequence[float]) -> dict[str, float | None]:
    if not values:
        return {
            name: None
            for name in ("minimum", "p05", "p25", "median", "p75", "p95", "maximum", "mean", "std")
        }
    return {
        "minimum": values[0],
        "p05": _percentile(values, 0.05),
        "p25": _percentile(values, 0.25),
        "median": median(values),
        "p75": _percentile(values, 0.75),
        "p95": _percentile(values, 0.95),
        "maximum": values[-1],
        "mean": mean(values),
        "std": pstdev(values) if len(values) > 1 else 0.0,
    }


def _percentile(values: Sequence[float], q: float) -> float:
    index = (len(values) - 1) * q
    lower, upper = floor(index), ceil(index)
    if lower == upper:
        return values[lower]
    return values[lower] + (values[upper] - values[lower]) * (index - lower)


def _histogram(values: Sequence[float], limit: int) -> list[dict[str, float | int]]:
    if not values:
        return []
    if len(set(values)) == 1:
        return [{"lower": values[0], "upper": values[0], "count": len(values)}]
    bins = min(50, limit, len(set(values)))
    width = (values[-1] - values[0]) / bins
    counts = [0] * bins
    for value in values:
        index = min(bins - 1, int((value - values[0]) / width))
        counts[index] += 1
    return [
        {
            "lower": values[0] + index * width,
            "upper": values[0] + (index + 1) * width,
            "count": count,
        }
        for index, count in enumerate(counts)
        if count
    ]


def _ecdf(values: Sequence[float], limit: int) -> list[dict[str, float]]:
    if not values:
        return []
    step = max(1, len(values) // limit)
    indexes = list(range(0, len(values), step))
    if indexes[-1] != len(values) - 1:
        indexes.append(len(values) - 1)
    return [
        {"value": values[index], "share": (index + 1) / len(values)} for index in indexes[:limit]
    ]


__all__ = ["build_metric_distributions"]
