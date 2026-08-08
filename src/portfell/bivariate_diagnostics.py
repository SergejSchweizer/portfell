"""Pure portfolio diagnostics derived from bivariate statistics."""

from __future__ import annotations

from math import sqrt
from statistics import median

from portfell.portfolio_parts.solvers import solve_minimum_variance
from portfell.table_io import JsonRow


def bivariate_metric_summary(values: list[float]) -> JsonRow:
    """Compact distribution data for a pairwise metric card."""

    if not values:
        return {"mean": None, "median": None, "minimum": None, "maximum": None, "histogram": []}
    low, high = min(values), max(values)
    bins = 8
    counts = [0] * bins
    if high == low:
        counts[0] = len(values)
        edges = [low, high]
    else:
        width = (high - low) / bins
        edges = [low + width * index for index in range(bins + 1)]
        for value in values:
            counts[min(bins - 1, int((value - low) / width))] += 1
    return {
        "mean": sum(values) / len(values),
        "median": median(values),
        "minimum": low,
        "maximum": high,
        "histogram": [
            {
                "lower": edges[index] if len(edges) > 2 else low,
                "upper": edges[index + 1] if len(edges) > 2 else high,
                "count": count,
            }
            for index, count in enumerate(counts)
            if count > 0
        ],
    }


def pearson_diagnostics(rows: tuple[JsonRow, ...]) -> JsonRow:
    """Portfolio-selection facts derived from the full Pearson pair universe."""

    values = _metric_values(rows, "pearson_correlation")
    if not values:
        return _empty_correlation_diagnostics()
    by_listing: dict[str, list[float]] = {}
    for row in rows:
        value = row.get("pearson_correlation")
        if value is None:
            continue
        for side in ("left", "right"):
            label = _listing_label(row, side)
            by_listing.setdefault(label, []).append(float(value))
    averages = _listing_averages(by_listing)
    most_correlated = _extreme_listing(averages, highest=True)
    best_diversifier = _extreme_listing(averages, highest=False)
    return {
        **_correlation_distribution(values),
        "most_correlated_listing": most_correlated,
        "most_correlated_average": averages.get(most_correlated) if most_correlated else None,
        "best_diversifier_listing": best_diversifier,
        "best_diversifier_average": averages.get(best_diversifier) if best_diversifier else None,
    }


def spearman_diagnostics(rows: tuple[JsonRow, ...]) -> JsonRow:
    """Portfolio-selection facts from rank co-movement and its robustness gap."""

    values = _metric_values(rows, "spearman_correlation")
    if not values:
        return _empty_correlation_diagnostics()
    by_listing, edges, gaps = _correlation_listing_data(
        rows, metric="spearman_correlation", comparison_metric="pearson_correlation"
    )
    averages = _listing_averages(by_listing)
    most_correlated = _extreme_listing(averages, highest=True)
    best_diversifier = _extreme_listing(averages, highest=False)
    clusters = _correlation_clusters(tuple(by_listing), edges)
    rolling_values = _metric_values(rows, "rolling_spearman_stability")
    return {
        **_correlation_distribution(values),
        "average_pearson_gap": sum(gaps) / len(gaps) if gaps else None,
        "large_pearson_gap_pairs": sum(abs(value) >= 0.15 for value in gaps),
        "most_correlated_listing": most_correlated,
        "most_correlated_average": averages.get(most_correlated) if most_correlated else None,
        "best_diversifier_listing": best_diversifier,
        "best_diversifier_average": averages.get(best_diversifier) if best_diversifier else None,
        "average_rolling_stability": (
            sum(rolling_values) / len(rolling_values) if rolling_values else None
        ),
        "cluster_count": len(clusters),
        "largest_cluster_size": max((len(cluster) for cluster in clusters), default=0),
    }


def downside_diagnostics(rows: tuple[JsonRow, ...]) -> JsonRow:
    """Portfolio-selection facts for dependence conditional on joint negative returns."""

    values = _metric_values(rows, "downside_correlation")
    if not values:
        return _empty_correlation_diagnostics()
    by_listing, edges, gaps = _correlation_listing_data(
        rows, metric="downside_correlation", comparison_metric="pearson_correlation"
    )
    averages = _listing_averages(by_listing)
    most_correlated = _extreme_listing(averages, highest=True)
    best_diversifier = _extreme_listing(averages, highest=False)
    clusters = _correlation_clusters(tuple(by_listing), edges)
    observation_counts = _integer_values(rows, "downside_observation_count")
    stability_values = _metric_values(rows, "rolling_downside_stability")
    worst_pair = _worst_pair(rows, "downside_correlation")
    return {
        **_correlation_distribution(values),
        "average_pearson_gap": sum(gaps) / len(gaps) if gaps else None,
        "large_pearson_gap_pairs": sum(abs(value) >= 0.15 for value in gaps),
        "most_correlated_listing": most_correlated,
        "most_correlated_average": averages.get(most_correlated) if most_correlated else None,
        "best_diversifier_listing": best_diversifier,
        "best_diversifier_average": averages.get(best_diversifier) if best_diversifier else None,
        "worst_pair": None if worst_pair is None else f"{worst_pair[0]} ↔ {worst_pair[1]}",
        "worst_pair_correlation": None if worst_pair is None else worst_pair[2],
        "median_joint_negative_days": median(observation_counts) if observation_counts else None,
        "minimum_joint_negative_days": min(observation_counts) if observation_counts else None,
        "average_rolling_stability": (
            sum(stability_values) / len(stability_values) if stability_values else None
        ),
        "cluster_count": len(clusters),
        "largest_cluster_size": max((len(cluster) for cluster in clusters), default=0),
    }


def covariance_diagnostics(
    listings: tuple[tuple[str, str, str], ...],
    covariance: list[list[float]],
    observation_count: int,
) -> JsonRow:
    """Return portfolio-relevant facts from one dense covariance estimate."""

    count = len(listings)
    if count == 0:
        return {"listing_count": 0, "pair_count": 0, "observation_count": observation_count}
    pairs = [covariance[left][right] for left in range(count) for right in range(left + 1, count)]
    correlations = [
        value / sqrt(covariance[left][left] * covariance[right][right])
        for left in range(count)
        for right, value in enumerate(covariance[left])
        if right > left and covariance[left][left] > 0 and covariance[right][right] > 0
    ]
    weights = [1.0 / count] * count
    covariance_weights = [
        sum(value * weight for value, weight in zip(row, weights, strict=True))
        for row in covariance
    ]
    equal_variance = sum(
        weight * value for weight, value in zip(weights, covariance_weights, strict=True)
    )
    equal_volatility = sqrt(max(0.0, equal_variance))
    weighted_volatility = sum(
        weight * sqrt(max(0.0, covariance[index][index])) for index, weight in enumerate(weights)
    )
    risk_contributions = [
        weight * value for weight, value in zip(weights, covariance_weights, strict=True)
    ]
    risk_shares = (
        [value / equal_variance for value in risk_contributions] if equal_variance > 0 else []
    )
    effective_bets = 1.0 / sum(share * share for share in risk_shares) if risk_shares else None
    covariance_map = {
        (left, right): covariance[left_index][right_index]
        for left_index, left in enumerate(listings)
        for right_index, right in enumerate(listings)
    }
    minimum_variance = solve_minimum_variance(
        listings, covariance_map, min_weight=0.0, max_weight=1.0
    )
    return {
        "listing_count": count,
        "pair_count": len(pairs),
        "observation_count": observation_count,
        "average_pairwise_covariance": (sum(pairs) / len(pairs)) if pairs else None,
        "average_pairwise_correlation": (
            sum(correlations) / len(correlations) if correlations else None
        ),
        "equal_weight_volatility": equal_volatility,
        "minimum_variance_volatility": sqrt(max(0.0, minimum_variance.objective_value)),
        "diversification_ratio": (
            weighted_volatility / equal_volatility if equal_volatility else None
        ),
        "effective_number_of_bets": effective_bets,
        "largest_equal_weight_risk_contribution": max(risk_shares) if risk_shares else None,
    }


def _metric_values(rows: tuple[JsonRow, ...], metric: str) -> list[float]:
    return [float(row[metric]) for row in rows if row.get(metric) is not None]


def _integer_values(rows: tuple[JsonRow, ...], metric: str) -> list[int]:
    return [int(row[metric]) for row in rows if row.get(metric) is not None]


def _empty_correlation_diagnostics() -> JsonRow:
    return {"high_70_pairs": 0, "high_90_pairs": 0, "low_30_pairs": 0, "negative_pairs": 0}


def _correlation_distribution(values: list[float]) -> JsonRow:
    ordered = sorted(values)
    return {
        "high_70_pairs": sum(value >= 0.70 for value in values),
        "high_90_pairs": sum(value >= 0.90 for value in values),
        "low_30_pairs": sum(value <= 0.30 for value in values),
        "negative_pairs": sum(value < 0.0 for value in values),
        "percentile_10": _percentile(ordered, 0.10),
        "percentile_50": _percentile(ordered, 0.50),
        "percentile_90": _percentile(ordered, 0.90),
    }


def _correlation_listing_data(
    rows: tuple[JsonRow, ...], *, metric: str, comparison_metric: str
) -> tuple[dict[str, list[float]], list[tuple[str, str]], list[float]]:
    by_listing: dict[str, list[float]] = {}
    edges: list[tuple[str, str]] = []
    gaps: list[float] = []
    for row in rows:
        value = row.get(metric)
        if value is None:
            continue
        left_label = _listing_label(row, "left")
        right_label = _listing_label(row, "right")
        correlation = float(value)
        by_listing.setdefault(left_label, []).append(correlation)
        by_listing.setdefault(right_label, []).append(correlation)
        if correlation >= 0.70:
            edges.append((left_label, right_label))
        comparison = row.get(comparison_metric)
        if comparison is not None:
            gaps.append(correlation - float(comparison))
    return by_listing, edges, gaps


def _listing_label(row: JsonRow, side: str) -> str:
    return f"{row[side + '_code']}.{row[side + '_exchange']} · {row[side + '_isin']}"


def _listing_averages(by_listing: dict[str, list[float]]) -> dict[str, float]:
    return {label: sum(values) / len(values) for label, values in by_listing.items() if values}


def _extreme_listing(values: dict[str, float], *, highest: bool) -> str | None:
    if not values:
        return None
    chooser = max if highest else min
    return chooser(values.items(), key=lambda item: item[1])[0]


def _worst_pair(rows: tuple[JsonRow, ...], metric: str) -> tuple[str, str, float] | None:
    candidates = [
        (_listing_label(row, "left"), _listing_label(row, "right"), float(row[metric]))
        for row in rows
        if row.get(metric) is not None
    ]
    return max(candidates, key=lambda item: item[2], default=None)


def _correlation_clusters(
    labels: tuple[str, ...], edges: list[tuple[str, str]]
) -> tuple[tuple[str, ...], ...]:
    adjacency: dict[str, set[str]] = {label: set() for label in labels}
    for left, right in edges:
        adjacency[left].add(right)
        adjacency[right].add(left)
    remaining = set(labels)
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


def _percentile(ordered_values: list[float], probability: float) -> float | None:
    if not ordered_values:
        return None
    index = (len(ordered_values) - 1) * probability
    lower = int(index)
    upper = min(lower + 1, len(ordered_values) - 1)
    fraction = index - lower
    return ordered_values[lower] + (ordered_values[upper] - ordered_values[lower]) * fraction
