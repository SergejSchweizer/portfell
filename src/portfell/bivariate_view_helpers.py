"""Shared row and label helpers for bivariate API view models."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from portfell.table_io import JsonRow


def pair_listings(rows: tuple[JsonRow, ...]) -> tuple[tuple[str, str, str], ...]:
    return tuple(sorted({listing(row, side) for row in rows for side in ("left", "right")}))


def listing(row: JsonRow, side: str) -> tuple[str, str, str]:
    return (str(row[side + "_isin"]), str(row[side + "_exchange"]), str(row[side + "_code"]))


def member_id(row: Mapping[str, Any]) -> str:
    return f"{row.get('isin', '')}:{row.get('exchange', '')}:{row.get('code', '')}"


def labels(listings: tuple[tuple[str, str, str], ...]) -> list[JsonRow]:
    return [
        {"isin": isin, "exchange": exchange, "code": code, "label": f"{code}.{exchange}"}
        for isin, exchange, code in listings
    ]


def pareto_points(points: list[JsonRow]) -> list[JsonRow]:
    ordered = sorted(
        points,
        key=lambda point: (
            float(point["tail_dependence"]),
            float(point["coexceedance_rate"]),
        ),
    )
    frontier: list[JsonRow] = []
    best_coexceedance = float("inf")
    position = 0
    while position < len(ordered):
        tail = float(ordered[position]["tail_dependence"])
        end = position + 1
        while end < len(ordered) and float(ordered[end]["tail_dependence"]) == tail:
            end += 1
        group = ordered[position:end]
        group_minimum = min(float(point["coexceedance_rate"]) for point in group)
        frontier.extend(
            point
            for point in group
            if float(point["coexceedance_rate"]) == group_minimum
            and best_coexceedance > group_minimum
        )
        best_coexceedance = min(best_coexceedance, group_minimum)
        position = end
    return frontier


def tail_risk_score(
    tail: float, coexceedance: float, tail_median: float, coexceedance_median: float
) -> float:
    return ((tail / max(tail_median, 0.05)) + (coexceedance / max(coexceedance_median, 0.0025))) / 2
