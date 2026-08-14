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


def tail_dependence_diagnostics(rows: tuple[JsonRow, ...]) -> JsonRow:
    """Portfolio-construction facts for joint lower-tail risk across all ISIN pairs."""
    values = _metric_values(rows, "lower_tail_dependence")
    if not values:
        return _empty_tail_dependence_diagnostics()
    by_listing, edges = _tail_listing_data(rows)
    averages = _listing_averages(by_listing)
    tail_central = _extreme_listing(averages, highest=True)
    clusters = _correlation_clusters(tuple(by_listing), edges)
    worst_pair = _worst_pair(rows, "lower_tail_dependence")
    best_pair = _best_tail_diversifier_pair(rows)
    severity_values = _metric_values(rows, "tail_joint_loss_severity")
    event_counts = _integer_values(rows, "tail_joint_event_count")
    rolling_values = _metric_values(rows, "rolling_tail_dependence_stability")
    ordered = sorted(values)
    return {
        "percentile_90": _percentile(ordered, 0.90),
        "high_30_pairs": sum(value >= 0.30 for value in values),
        "high_50_pairs": sum(value >= 0.50 for value in values),
        "worst_pair": None if worst_pair is None else f"{worst_pair[0]} ↔ {worst_pair[1]}",
        "worst_pair_tail_dependence": None if worst_pair is None else worst_pair[2],
        "best_diversifier_pair": None if best_pair is None else f"{best_pair[0]} ↔ {best_pair[1]}",
        "best_diversifier_tail_dependence": None if best_pair is None else best_pair[2],
        "best_diversifier_coexceedance_rate": None if best_pair is None else best_pair[3],
        "most_tail_exposed_listing": tail_central,
        "most_tail_exposed_average": averages.get(tail_central) if tail_central else None,
        "average_joint_loss_severity": (
            sum(severity_values) / len(severity_values) if severity_values else None
        ),
        "median_joint_tail_events": median(event_counts) if event_counts else None,
        "minimum_joint_tail_events": min(event_counts) if event_counts else None,
        "average_rolling_stability": (
            sum(rolling_values) / len(rolling_values) if rolling_values else None
        ),
        "cluster_threshold": 0.30,
        "cluster_count": len(clusters),
        "largest_cluster_size": max((len(cluster) for cluster in clusters), default=0),
    }


def coexceedance_diagnostics(rows: tuple[JsonRow, ...]) -> JsonRow:
    """Portfolio-construction facts for unconditional simultaneous lower-tail events."""
    values = _metric_values(rows, "tail_coexceedance_rate")
    if not values:
        return _empty_coexceedance_diagnostics()
    by_listing, edges = _coexceedance_listing_data(rows)
    averages = _listing_averages(by_listing)
    most_exposed = _extreme_listing(averages, highest=True)
    clusters = _correlation_clusters(tuple(by_listing), edges)
    worst_pair = _worst_pair(rows, "tail_coexceedance_rate")
    best_pair = _best_coexceedance_diversifier_pair(rows)
    event_counts = _integer_values(rows, "tail_joint_event_count")
    rolling_values = _metric_values(rows, "rolling_tail_coexceedance_stability")
    ordered = sorted(values)
    independence_baseline = 0.0025
    return {
        "percentile_90": _percentile(ordered, 0.90),
        "independence_baseline": independence_baseline,
        "average_independence_multiple": (sum(values) / len(values)) / independence_baseline,
        "high_1_pairs": sum(value >= 0.01 for value in values),
        "high_25_pairs": sum(value >= 0.025 for value in values),
        "high_5_pairs": sum(value >= 0.05 for value in values),
        "worst_pair": None if worst_pair is None else f"{worst_pair[0]} ↔ {worst_pair[1]}",
        "worst_pair_rate": None if worst_pair is None else worst_pair[2],
        "worst_pair_annual_events": None if worst_pair is None else worst_pair[2] * 252,
        "worst_pair_tail_dependence": _pair_metric(rows, worst_pair, "lower_tail_dependence"),
        "best_diversifier_pair": None if best_pair is None else f"{best_pair[0]} ↔ {best_pair[1]}",
        "best_diversifier_rate": None if best_pair is None else best_pair[2],
        "best_diversifier_tail_dependence": None if best_pair is None else best_pair[3],
        "most_coexposed_listing": most_exposed,
        "most_coexposed_average": averages.get(most_exposed) if most_exposed else None,
        "median_joint_tail_events": median(event_counts) if event_counts else None,
        "minimum_joint_tail_events": min(event_counts) if event_counts else None,
        "average_rolling_stability": (
            sum(rolling_values) / len(rolling_values) if rolling_values else None
        ),
        "cluster_threshold": 0.01,
        "cluster_count": len(clusters),
        "largest_cluster_size": max((len(cluster) for cluster in clusters), default=0),
    }


def rolling_correlation_diagnostics(rows: tuple[JsonRow, ...]) -> JsonRow:
    """Portfolio facts for the stability and stress behaviour of pair correlations."""
    values = _metric_values(rows, "rolling_correlation_stability")
    if not values:
        return _empty_rolling_correlation_diagnostics()
    base = _pair_metric_diagnostics(rows, "rolling_correlation_stability", 0.10)
    observations = _integer_values(rows, "n_observations")
    rolling_means = _metric_values(rows, "rolling_correlation_mean")
    worst_windows = _metric_values(rows, "rolling_correlation_maximum")
    trends = _metric_values(rows, "rolling_correlation_trend")
    switches = _integer_values(rows, "rolling_correlation_regime_switches")
    pearson_gaps = [
        abs(float(row["rolling_correlation_mean"]) - float(row["pearson_correlation"]))
        for row in rows
        if row.get("rolling_correlation_mean") is not None
        and row.get("pearson_correlation") is not None
    ]
    stress_correlations = _metric_values(rows, "downside_correlation")
    worst_window_pair = _worst_pair(rows, "rolling_correlation_maximum")
    return {
        **base,
        "high_20_pairs": sum(value >= 0.20 for value in values),
        "high_30_pairs": sum(value >= 0.30 for value in values),
        "window_length": 60,
        "median_shared_observations": median(observations) if observations else None,
        "minimum_shared_observations": min(observations) if observations else None,
        "median_window_count": _median_rolling_window_count(observations),
        "average_rolling_correlation": (
            sum(rolling_means) / len(rolling_means) if rolling_means else None
        ),
        "average_correlation_trend": sum(trends) / len(trends) if trends else None,
        "regime_switch_pairs": sum(value > 0 for value in switches),
        "average_regime_switches": sum(switches) / len(switches) if switches else None,
        "average_stress_correlation": (
            sum(stress_correlations) / len(stress_correlations) if stress_correlations else None
        ),
        "average_pearson_gap": sum(pearson_gaps) / len(pearson_gaps) if pearson_gaps else None,
        "average_worst_window_correlation": (
            sum(worst_windows) / len(worst_windows) if worst_windows else None
        ),
        "worst_window_pair": (
            None
            if worst_window_pair is None
            else f"{worst_window_pair[0]} ↔ {worst_window_pair[1]}"
        ),
        "worst_window_correlation": (None if worst_window_pair is None else worst_window_pair[2]),
    }


def drawdown_overlap_diagnostics(rows: tuple[JsonRow, ...]) -> JsonRow:
    """Portfolio facts for how often and how severely pairs draw down together."""
    values = _metric_values(rows, "drawdown_overlap_rate")
    if not values:
        return _empty_drawdown_overlap_diagnostics()
    base = _pair_metric_diagnostics(rows, "drawdown_overlap_rate", 0.10)
    counts = _integer_values(rows, "drawdown_overlap_count")
    severities = _metric_values(rows, "drawdown_joint_severity")
    stabilities = _metric_values(rows, "rolling_drawdown_overlap_stability")
    pearson = _metric_values(rows, "pearson_correlation")
    downside = _metric_values(rows, "downside_correlation")
    hidden_pearson_risk = sum(
        float(row["drawdown_overlap_rate"]) >= 0.25
        and float(row.get("pearson_correlation", 1.0)) <= 0.30
        for row in rows
        if row.get("drawdown_overlap_rate") is not None
    )
    hidden_downside_risk = sum(
        float(row["drawdown_overlap_rate"]) >= 0.25
        and float(row.get("downside_correlation", 1.0)) <= 0.30
        for row in rows
        if row.get("drawdown_overlap_rate") is not None
    )
    return {
        **base,
        "high_25_pairs": sum(value >= 0.25 for value in values),
        "high_50_pairs": sum(value >= 0.50 for value in values),
        "median_joint_drawdown_days": median(counts) if counts else None,
        "minimum_joint_drawdown_days": min(counts) if counts else None,
        "average_joint_drawdown_severity": (
            sum(severities) / len(severities) if severities else None
        ),
        "average_rolling_stability": sum(stabilities) / len(stabilities) if stabilities else None,
        "average_pearson_correlation": sum(pearson) / len(pearson) if pearson else None,
        "average_downside_correlation": sum(downside) / len(downside) if downside else None,
        "high_overlap_low_pearson_pairs": hidden_pearson_risk,
        "high_overlap_low_downside_pairs": hidden_downside_risk,
    }


def _pair_metric_diagnostics(rows: tuple[JsonRow, ...], metric: str, threshold: float) -> JsonRow:
    values = _metric_values(rows, metric)
    if not values:
        return {
            "percentile_90": None,
            "high_threshold_pairs": 0,
            "worst_pair": None,
            "worst_value": None,
            "best_pair": None,
            "best_value": None,
            "most_exposed_listing": None,
            "most_exposed_average": None,
            "cluster_count": 0,
            "largest_cluster_size": 0,
        }
    by_listing: dict[str, list[float]] = {}
    edges: list[tuple[str, str]] = []
    for row in rows:
        if row.get(metric) is None:
            continue
        value = float(row[metric])
        left, right = _listing_label(row, "left"), _listing_label(row, "right")
        by_listing.setdefault(left, []).append(value)
        by_listing.setdefault(right, []).append(value)
        if value >= threshold:
            edges.append((left, right))
    averages = _listing_averages(by_listing)
    worst = _worst_pair(rows, metric)
    best = min(
        [
            (_listing_label(row, "left"), _listing_label(row, "right"), float(row[metric]))
            for row in rows
            if row.get(metric) is not None
        ],
        key=lambda item: item[2],
        default=None,
    )
    clusters = _correlation_clusters(tuple(by_listing), edges)
    most_exposed = _extreme_listing(averages, highest=True)
    return {
        "percentile_90": _percentile(sorted(values), 0.90),
        "high_threshold_pairs": sum(value >= threshold for value in values),
        "worst_pair": None if worst is None else f"{worst[0]} ↔ {worst[1]}",
        "worst_value": None if worst is None else worst[2],
        "best_pair": None if best is None else f"{best[0]} ↔ {best[1]}",
        "best_value": None if best is None else best[2],
        "most_exposed_listing": most_exposed,
        "most_exposed_average": averages.get(most_exposed) if most_exposed else None,
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
        listings,
        covariance_map,
        min_weight=0.0,
        max_weight=1.0,
        # This is an informational page-view fact, not the production
        # portfolio optimiser.  A bounded, coarse solve keeps a large
        # covariance matrix responsive; the full optimiser runs later in
        # Multivariate Statistics with its own explicit budget.
        max_iterations=80,
        tolerance=1e-6,
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


def _empty_tail_dependence_diagnostics() -> JsonRow:
    return {
        "percentile_90": None,
        "high_30_pairs": 0,
        "high_50_pairs": 0,
        "worst_pair": None,
        "worst_pair_tail_dependence": None,
        "best_diversifier_pair": None,
        "best_diversifier_tail_dependence": None,
        "best_diversifier_coexceedance_rate": None,
        "most_tail_exposed_listing": None,
        "most_tail_exposed_average": None,
        "average_joint_loss_severity": None,
        "median_joint_tail_events": None,
        "minimum_joint_tail_events": None,
        "average_rolling_stability": None,
        "cluster_threshold": 0.30,
        "cluster_count": 0,
        "largest_cluster_size": 0,
    }


def _empty_coexceedance_diagnostics() -> JsonRow:
    return {
        "percentile_90": None,
        "independence_baseline": 0.0025,
        "average_independence_multiple": None,
        "high_1_pairs": 0,
        "high_25_pairs": 0,
        "high_5_pairs": 0,
        "worst_pair": None,
        "worst_pair_rate": None,
        "worst_pair_annual_events": None,
        "worst_pair_tail_dependence": None,
        "best_diversifier_pair": None,
        "best_diversifier_rate": None,
        "best_diversifier_tail_dependence": None,
        "most_coexposed_listing": None,
        "most_coexposed_average": None,
        "median_joint_tail_events": None,
        "minimum_joint_tail_events": None,
        "average_rolling_stability": None,
        "cluster_threshold": 0.01,
        "cluster_count": 0,
        "largest_cluster_size": 0,
    }


def _empty_drawdown_overlap_diagnostics() -> JsonRow:
    return {
        "percentile_90": None,
        "high_threshold_pairs": 0,
        "high_25_pairs": 0,
        "high_50_pairs": 0,
        "worst_pair": None,
        "worst_value": None,
        "best_pair": None,
        "best_value": None,
        "most_exposed_listing": None,
        "most_exposed_average": None,
        "median_joint_drawdown_days": None,
        "minimum_joint_drawdown_days": None,
        "average_joint_drawdown_severity": None,
        "average_rolling_stability": None,
        "average_pearson_correlation": None,
        "average_downside_correlation": None,
        "high_overlap_low_pearson_pairs": 0,
        "high_overlap_low_downside_pairs": 0,
        "cluster_count": 0,
        "largest_cluster_size": 0,
    }


def _empty_rolling_correlation_diagnostics() -> JsonRow:
    return {
        "percentile_90": None,
        "high_threshold_pairs": 0,
        "high_20_pairs": 0,
        "high_30_pairs": 0,
        "worst_pair": None,
        "worst_value": None,
        "best_pair": None,
        "best_value": None,
        "most_exposed_listing": None,
        "most_exposed_average": None,
        "window_length": 60,
        "median_shared_observations": None,
        "minimum_shared_observations": None,
        "median_window_count": None,
        "average_rolling_correlation": None,
        "average_correlation_trend": None,
        "regime_switch_pairs": 0,
        "average_regime_switches": None,
        "average_stress_correlation": None,
        "average_pearson_gap": None,
        "average_worst_window_correlation": None,
        "worst_window_pair": None,
        "worst_window_correlation": None,
        "cluster_count": 0,
        "largest_cluster_size": 0,
    }


def _median_rolling_window_count(observations: list[int]) -> float | None:
    counts = [
        0 if observation < 20 else 1 + max(0, (observation - min(60, observation)) // 20)
        for observation in observations
    ]
    return median(counts) if counts else None


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


def _tail_listing_data(
    rows: tuple[JsonRow, ...],
) -> tuple[dict[str, list[float]], list[tuple[str, str]]]:
    by_listing: dict[str, list[float]] = {}
    edges: list[tuple[str, str]] = []
    for row in rows:
        value = row.get("lower_tail_dependence")
        if value is None:
            continue
        left_label = _listing_label(row, "left")
        right_label = _listing_label(row, "right")
        tail_dependence = float(value)
        by_listing.setdefault(left_label, []).append(tail_dependence)
        by_listing.setdefault(right_label, []).append(tail_dependence)
        if tail_dependence >= 0.30:
            edges.append((left_label, right_label))
    return by_listing, edges


def _coexceedance_listing_data(
    rows: tuple[JsonRow, ...],
) -> tuple[dict[str, list[float]], list[tuple[str, str]]]:
    by_listing: dict[str, list[float]] = {}
    edges: list[tuple[str, str]] = []
    for row in rows:
        value = row.get("tail_coexceedance_rate")
        if value is None:
            continue
        left_label = _listing_label(row, "left")
        right_label = _listing_label(row, "right")
        coexceedance = float(value)
        by_listing.setdefault(left_label, []).append(coexceedance)
        by_listing.setdefault(right_label, []).append(coexceedance)
        if coexceedance >= 0.01:
            edges.append((left_label, right_label))
    return by_listing, edges


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


def _best_tail_diversifier_pair(rows: tuple[JsonRow, ...]) -> tuple[str, str, float, float] | None:
    candidates = [
        (
            _listing_label(row, "left"),
            _listing_label(row, "right"),
            float(row["lower_tail_dependence"]),
            float(row["tail_coexceedance_rate"]),
        )
        for row in rows
        if row.get("lower_tail_dependence") is not None
        and row.get("tail_coexceedance_rate") is not None
    ]
    return min(candidates, key=lambda item: (item[2], item[3]), default=None)


def _best_coexceedance_diversifier_pair(
    rows: tuple[JsonRow, ...],
) -> tuple[str, str, float, float] | None:
    candidates = [
        (
            _listing_label(row, "left"),
            _listing_label(row, "right"),
            float(row["tail_coexceedance_rate"]),
            float(row["lower_tail_dependence"]),
        )
        for row in rows
        if row.get("tail_coexceedance_rate") is not None
        and row.get("lower_tail_dependence") is not None
    ]
    return min(candidates, key=lambda item: (item[2], item[3]), default=None)


def _pair_metric(
    rows: tuple[JsonRow, ...], pair: tuple[str, str, float] | None, metric: str
) -> float | None:
    if pair is None:
        return None
    for row in rows:
        if _listing_label(row, "left") == pair[0] and _listing_label(row, "right") == pair[1]:
            value = row.get(metric)
            return float(value) if value is not None else None
    return None


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
