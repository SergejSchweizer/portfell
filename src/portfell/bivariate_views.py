"""Pure API read models for bivariate statistics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from portfell.bivariate_diagnostics import (
    bivariate_metric_summary,
    coexceedance_diagnostics,
    covariance_diagnostics,
    downside_diagnostics,
    drawdown_overlap_diagnostics,
    pearson_diagnostics,
    rolling_correlation_diagnostics,
    spearman_diagnostics,
    tail_dependence_diagnostics,
)
from portfell.gold import build_returns
from portfell.gold_pair_stats import sample_covariance
from portfell.table_io import JsonRow

_SUMMARY_METRICS = (
    "pearson_correlation",
    "spearman_correlation",
    "downside_correlation",
    "lower_tail_dependence",
    "tail_coexceedance_rate",
    "rolling_correlation_stability",
    "rolling_spearman_stability",
    "drawdown_overlap_rate",
)


def build_bivariate_summary(rows: tuple[JsonRow, ...]) -> JsonRow:
    """Aggregate pair rows for the bivariate-statistics cards."""

    date_start, date_end = _shared_date_range(rows)
    return {
        "pair_count": len(rows),
        "observation_count": _average_observations(rows),
        "date_start": date_start,
        "date_end": date_end,
        "metrics": {
            name: bivariate_metric_summary(
                [float(row[name]) for row in rows if row.get(name) is not None]
            )
            for name in _SUMMARY_METRICS
        },
        "pearson_diagnostics": pearson_diagnostics(rows),
        "spearman_diagnostics": spearman_diagnostics(rows),
        "downside_diagnostics": downside_diagnostics(rows),
        "tail_dependence_diagnostics": tail_dependence_diagnostics(rows),
        "coexceedance_diagnostics": coexceedance_diagnostics(rows),
        "rolling_correlation_diagnostics": rolling_correlation_diagnostics(rows),
        "drawdown_overlap_diagnostics": drawdown_overlap_diagnostics(rows),
    }


def build_correlation_matrix(rows: tuple[JsonRow, ...], metric: str) -> JsonRow:
    """Expose the upper triangle of one pair-metric matrix from pair results."""

    metric_key = {
        "pearson": "pearson_correlation",
        "spearman": "spearman_correlation",
        "downside": "downside_correlation",
        "lower_tail_dependence": "lower_tail_dependence",
        "tail_coexceedance_rate": "tail_coexceedance_rate",
        "drawdown_overlap": "drawdown_overlap_rate",
    }[metric]
    listings = _pair_listings(rows)
    index = {listing: position for position, listing in enumerate(listings)}
    values_by_pair = {
        (
            index[_listing(row, "left")],
            index[_listing(row, "right")],
        ): float(row.get(metric_key, 0.0))
        for row in rows
    }
    date_start, date_end = _shared_date_range(rows)
    return {
        "labels": _labels(listings),
        "values": [
            [
                values_by_pair.get((row, column)) if column > row else None
                for column in range(len(listings))
            ]
            for row in range(len(listings))
        ],
        "observation_count": _average_observations(rows),
        "date_start": date_start,
        "date_end": date_end,
    }


def build_tail_risk_scatter(rows: tuple[JsonRow, ...]) -> JsonRow:
    """Expose all persisted tail-risk pair values for a portfolio-selection scatterplot."""

    date_start, date_end = _shared_date_range(rows)
    points = [
        {
            "left_isin": row["left_isin"],
            "left_exchange": row["left_exchange"],
            "left_code": row["left_code"],
            "right_isin": row["right_isin"],
            "right_exchange": row["right_exchange"],
            "right_code": row["right_code"],
            "tail_dependence": float(row["lower_tail_dependence"]),
            "coexceedance_rate": float(row["tail_coexceedance_rate"]),
        }
        for row in rows
        if row.get("lower_tail_dependence") is not None
        and row.get("tail_coexceedance_rate") is not None
    ]
    tail_summary = bivariate_metric_summary([float(point["tail_dependence"]) for point in points])
    coexceedance_summary = bivariate_metric_summary(
        [float(point["coexceedance_rate"]) for point in points]
    )
    return {
        "points": points,
        "pair_count": len(points),
        "observation_count": _average_observations(rows),
        "date_start": date_start,
        "date_end": date_end,
        "tail_dependence_median": tail_summary["median"],
        "coexceedance_rate_median": coexceedance_summary["median"],
        "diagnostics": _tail_risk_scatter_diagnostics(
            points,
            rows,
            float(tail_summary["median"] or 0.0),
            float(coexceedance_summary["median"] or 0.0),
        ),
    }


def _tail_risk_scatter_diagnostics(
    points: list[JsonRow], rows: tuple[JsonRow, ...], tail_median: float, coexceedance_median: float
) -> JsonRow:
    """Return selection-oriented facts for the complete tail-risk scatter universe."""
    if not points:
        return _empty_tail_risk_scatter_diagnostics()
    quadrants = {
        "best_diversifiers": 0,
        "tail_concentration": 0,
        "high_tail_only": 0,
        "high_coexceedance_only": 0,
    }
    upper_right_edges: list[tuple[str, str]] = []
    centrality: dict[str, list[float]] = {}
    for point in points:
        tail = float(point["tail_dependence"])
        coexceedance = float(point["coexceedance_rate"])
        left, right = _scatter_pair_labels(point)
        score = _tail_risk_score(tail, coexceedance, tail_median, coexceedance_median)
        if tail <= tail_median and coexceedance <= coexceedance_median:
            quadrants["best_diversifiers"] += 1
        elif tail > tail_median and coexceedance > coexceedance_median:
            quadrants["tail_concentration"] += 1
            upper_right_edges.append((left, right))
            centrality.setdefault(left, []).append(score)
            centrality.setdefault(right, []).append(score)
        elif tail > tail_median:
            quadrants["high_tail_only"] += 1
        else:
            quadrants["high_coexceedance_only"] += 1
    pareto = [
        point
        for point in points
        if not any(
            other is not point
            and float(other["tail_dependence"]) <= float(point["tail_dependence"])
            and float(other["coexceedance_rate"]) <= float(point["coexceedance_rate"])
            and (
                float(other["tail_dependence"]) < float(point["tail_dependence"])
                or float(other["coexceedance_rate"]) < float(point["coexceedance_rate"])
            )
            for other in points
        )
    ]
    best_pareto = min(
        pareto,
        key=lambda point: _tail_risk_score(
            float(point["tail_dependence"]),
            float(point["coexceedance_rate"]),
            tail_median,
            coexceedance_median,
        ),
        default=None,
    )
    worst = max(
        points,
        key=lambda point: _tail_risk_score(
            float(point["tail_dependence"]),
            float(point["coexceedance_rate"]),
            tail_median,
            coexceedance_median,
        ),
    )
    clusters = _scatter_clusters(upper_right_edges)
    most_concentrated = max(
        centrality.items(),
        key=lambda item: (len(item[1]), sum(item[1]) / len(item[1])),
        default=None,
    )
    tail_stability = [
        float(row["rolling_tail_dependence_stability"])
        for row in rows
        if row.get("rolling_tail_dependence_stability") is not None
    ]
    coexceedance_stability = [
        float(row["rolling_tail_coexceedance_stability"])
        for row in rows
        if row.get("rolling_tail_coexceedance_stability") is not None
    ]
    tail_events = [
        int(row["tail_joint_event_count"])
        for row in rows
        if row.get("tail_joint_event_count") is not None
    ]
    return {
        **quadrants,
        "pareto_best_pair_count": len(pareto),
        "best_pareto_pair": _scatter_pair_text(best_pareto),
        "worst_tail_risk_pair": _scatter_pair_text(worst),
        "worst_tail_risk_score": _tail_risk_score(
            float(worst["tail_dependence"]),
            float(worst["coexceedance_rate"]),
            tail_median,
            coexceedance_median,
        ),
        "tail_independence_baseline": 0.05,
        "coexceedance_independence_baseline": 0.0025,
        "average_tail_independence_multiple": sum(
            float(point["tail_dependence"]) for point in points
        )
        / len(points)
        / 0.05,
        "average_coexceedance_independence_multiple": sum(
            float(point["coexceedance_rate"]) for point in points
        )
        / len(points)
        / 0.0025,
        "most_concentrated_isin": None if most_concentrated is None else most_concentrated[0],
        "upper_right_links": 0 if most_concentrated is None else len(most_concentrated[1]),
        "upper_right_cluster_count": len(clusters),
        "largest_upper_right_cluster_size": max((len(cluster) for cluster in clusters), default=0),
        "average_tail_stability": sum(tail_stability) / len(tail_stability)
        if tail_stability
        else None,
        "average_coexceedance_stability": sum(coexceedance_stability) / len(coexceedance_stability)
        if coexceedance_stability
        else None,
        "median_joint_tail_events": _median(tail_events),
        "minimum_joint_tail_events": min(tail_events) if tail_events else None,
    }


def _empty_tail_risk_scatter_diagnostics() -> JsonRow:
    return {
        "best_diversifiers": 0,
        "tail_concentration": 0,
        "high_tail_only": 0,
        "high_coexceedance_only": 0,
        "pareto_best_pair_count": 0,
        "best_pareto_pair": None,
        "worst_tail_risk_pair": None,
        "worst_tail_risk_score": None,
        "tail_independence_baseline": 0.05,
        "coexceedance_independence_baseline": 0.0025,
        "average_tail_independence_multiple": None,
        "average_coexceedance_independence_multiple": None,
        "most_concentrated_isin": None,
        "upper_right_links": 0,
        "upper_right_cluster_count": 0,
        "largest_upper_right_cluster_size": 0,
        "average_tail_stability": None,
        "average_coexceedance_stability": None,
        "median_joint_tail_events": None,
        "minimum_joint_tail_events": None,
    }


def _tail_risk_score(
    tail: float, coexceedance: float, tail_median: float, coexceedance_median: float
) -> float:
    return ((tail / max(tail_median, 0.05)) + (coexceedance / max(coexceedance_median, 0.0025))) / 2


def _scatter_pair_labels(point: Mapping[str, Any]) -> tuple[str, str]:
    return (
        f"{point['left_code']}.{point['left_exchange']} · {point['left_isin']}",
        f"{point['right_code']}.{point['right_exchange']} · {point['right_isin']}",
    )


def _scatter_pair_text(point: Mapping[str, Any] | None) -> str | None:
    return None if point is None else " ↔ ".join(_scatter_pair_labels(point))


def _scatter_clusters(edges: list[tuple[str, str]]) -> tuple[tuple[str, ...], ...]:
    adjacency: dict[str, set[str]] = {}
    for left, right in edges:
        adjacency.setdefault(left, set()).add(right)
        adjacency.setdefault(right, set()).add(left)
    remaining = set(adjacency)
    clusters: list[tuple[str, ...]] = []
    while remaining:
        seed = remaining.pop()
        component = {seed}
        frontier = [seed]
        while frontier:
            current = frontier.pop()
            neighbours = adjacency[current] & remaining
            frontier.extend(neighbours)
            component.update(neighbours)
            remaining.difference_update(neighbours)
        clusters.append(tuple(sorted(component)))
    return tuple(clusters)


def _median(values: list[int]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    return (
        float(ordered[middle]) if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
    )


def build_covariance_matrix(
    quote_rows: Sequence[Mapping[str, Any]], member_ids: tuple[str, ...]
) -> JsonRow:
    """Build a common-date daily log-return covariance matrix for selected listings."""

    members = set(member_ids)
    scoped_quotes = tuple(row for row in quote_rows if _member_id(row) in members)
    values_by_listing: dict[tuple[str, str, str], dict[str, float]] = {}
    for row in build_returns(scoped_quotes):
        listing = (str(row["isin"]), str(row["exchange"]), str(row["code"]))
        values_by_listing.setdefault(listing, {})[str(row["date"])] = float(row["return"])
    listings = tuple(sorted(values_by_listing))
    dates = _common_dates(values_by_listing, listings)
    values = [tuple(values_by_listing[listing][date] for date in dates) for listing in listings]
    covariance_values = _dense_covariance(values)
    return {
        "labels": _labels(listings),
        "values": [
            [value if column > row else None for column, value in enumerate(values_row)]
            for row, values_row in enumerate(covariance_values)
        ],
        "observation_count": len(dates),
        "date_start": dates[0] if dates else "",
        "date_end": dates[-1] if dates else "",
        "diagnostics": covariance_diagnostics(listings, covariance_values, len(dates)),
    }


def _pair_listings(rows: tuple[JsonRow, ...]) -> tuple[tuple[str, str, str], ...]:
    return tuple(sorted({_listing(row, side) for row in rows for side in ("left", "right")}))


def _listing(row: JsonRow, side: str) -> tuple[str, str, str]:
    return (
        str(row[side + "_isin"]),
        str(row[side + "_exchange"]),
        str(row[side + "_code"]),
    )


def _member_id(row: Mapping[str, Any]) -> str:
    return f"{row.get('isin', '')}:{row.get('exchange', '')}:{row.get('code', '')}"


def _labels(listings: tuple[tuple[str, str, str], ...]) -> list[JsonRow]:
    return [
        {"isin": isin, "exchange": exchange, "code": code, "label": f"{code}.{exchange}"}
        for isin, exchange, code in listings
    ]


def _average_observations(rows: tuple[JsonRow, ...]) -> int:
    if not rows:
        return 0
    return round(sum(int(row.get("n_observations", 0)) for row in rows) / len(rows))


def _shared_date_range(rows: tuple[JsonRow, ...]) -> tuple[str, str]:
    ranges = {
        (str(row.get("date_start", "")), str(row.get("date_end", "")))
        for row in rows
        if row.get("date_start") and row.get("date_end")
    }
    if len(ranges) > 1:
        raise ValueError("bivariate rows do not share one aligned data period")
    observation_counts = {int(row.get("n_observations", 0)) for row in rows}
    if len(observation_counts) > 1:
        raise ValueError("bivariate rows do not share one aligned observation count")
    return next(iter(ranges), ("", ""))


def _common_dates(
    values_by_listing: dict[tuple[str, str, str], dict[str, float]],
    listings: tuple[tuple[str, str, str], ...],
) -> tuple[str, ...]:
    if not listings:
        return ()
    common = set(values_by_listing[listings[0]])
    for listing in listings[1:]:
        common.intersection_update(values_by_listing[listing])
    return tuple(sorted(common))


def _dense_covariance(values: list[tuple[float, ...]]) -> list[list[float]]:
    covariance = [[0.0] * len(values) for _ in values]
    for row, left in enumerate(values):
        for column in range(row, len(values)):
            value = sample_covariance(left, values[column])
            covariance[row][column] = value
            covariance[column][row] = value
    return covariance
