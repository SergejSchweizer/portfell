"""Bivariate Statistics for approved ISIN listing pairs."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from math import exp, sqrt
from typing import Any

from portfell.gold_pair_stats import (
    DEFAULT_BUCKET_COUNT,
    DEFAULT_MAX_PAIR_COUNT,
    DEFAULT_PAIR_CHUNK_SIZE,
    PairObservation,
    PairPlan,
    build_pair_plan,
    chunked_pairs,
    correlation_value,
    index_returns,
    iter_pair_observations,
    resolve_worker_count,
    sample_covariance,
    sort_pair_rows,
)
from portfell.paths import LakePaths
from portfell.run_state import build_job_manifest, write_job_manifest
from portfell.schemas import validate_rows
from portfell.table_io import JsonRow, read_rows, write_rows

BIVARIATE_STATISTICS_VERSION = "v9"


def build_bivariate_statistics(
    return_rows: Sequence[Mapping[str, Any]],
    *,
    skip_same_isin: bool = True,
    concurrency: int | None = None,
    max_pair_count: int = DEFAULT_MAX_PAIR_COUNT,
    chunk_size: int = DEFAULT_PAIR_CHUNK_SIZE,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[JsonRow]:
    """Compute pairwise statistics from aligned return rows.

    The output intentionally contains only two-listing statistics. Single-listing
    return summaries belong in the separate univariate statistics module. A
    universe whose theoretical pair count exceeds ``max_pair_count`` is rejected
    before any pair is enumerated.
    """
    returns_by_listing = index_returns(return_rows)
    plan = build_pair_plan(
        len(returns_by_listing),
        mode="dense",
        max_pair_count=max_pair_count,
        chunk_size=chunk_size,
        concurrency=concurrency,
    )
    if not plan.accepted:
        raise ValueError(f"bivariate statistics rejected: {plan.rejection_reason}")

    pairs = iter_pair_observations(
        returns_by_listing,
        include_self=False,
        skip_same_isin=skip_same_isin,
    )
    rows: list[JsonRow] = []
    completed = 0
    if on_progress is not None:
        on_progress(completed, plan.theoretical_pair_count)
    executor = ProcessPoolExecutor(max_workers=plan.worker_count) if plan.worker_count > 1 else None
    try:
        for chunk in chunked_pairs(pairs, plan.chunk_size):
            if executor is None or len(chunk) <= 1:
                rows.extend(_build_bivariate_pair_statistics(pair) for pair in chunk)
            else:
                rows.extend(executor.map(_build_bivariate_pair_statistics, chunk))
            completed += len(chunk)
            if on_progress is not None:
                on_progress(completed, plan.theoretical_pair_count)
    finally:
        if executor is not None:
            executor.shutdown()
    return sort_pair_rows(rows)


def write_bivariate_statistics(
    paths: LakePaths,
    return_rows: Sequence[Mapping[str, Any]],
    *,
    skip_same_isin: bool = True,
    concurrency: int | None = None,
    version: str = BIVARIATE_STATISTICS_VERSION,
    bucket_count: int = DEFAULT_BUCKET_COUNT,
    max_pair_count: int = DEFAULT_MAX_PAIR_COUNT,
    chunk_size: int = DEFAULT_PAIR_CHUNK_SIZE,
) -> list[JsonRow]:
    """Write Bivariate Statistics rows to deterministic bucketed Gold paths.

    Rows are grouped into ``bucket_count`` Parquet buckets keyed by
    ``left_id % bucket_count`` instead of one file per pair, so file count grows
    sublinearly with pair count. A universe whose theoretical pair count exceeds
    ``max_pair_count`` is rejected before any pair is materialized or submitted
    to a worker. Pair-plan diagnostics are persisted as a job manifest for every
    call, including rejected ones.
    """
    returns_by_listing = index_returns(return_rows)
    plan = build_pair_plan(
        len(returns_by_listing),
        mode="dense",
        max_pair_count=max_pair_count,
        chunk_size=chunk_size,
        bucket_count=bucket_count,
        concurrency=concurrency,
    )
    _write_pair_plan_manifest(paths, version=version, plan=plan)
    if not plan.accepted:
        raise ValueError(
            f"bivariate statistics rejected for version {version!r}: {plan.rejection_reason}"
        )

    existing_by_bucket = _read_existing_buckets(paths, version, plan.bucket_count)
    cache_index: dict[str, JsonRow] = {}
    for bucket_rows in existing_by_bucket.values():
        for row in bucket_rows:
            cache_index[str(row["pair_key"])] = row

    pairs = iter_pair_observations(
        returns_by_listing,
        include_self=False,
        skip_same_isin=skip_same_isin,
    )
    final_by_bucket: dict[int, list[JsonRow]] = {}
    dirty_buckets: set[int] = set()
    executor = ProcessPoolExecutor(max_workers=plan.worker_count) if plan.worker_count > 1 else None
    try:
        for chunk in chunked_pairs(pairs, plan.chunk_size):
            fresh_targets: list[PairObservation] = []
            for pair in chunk:
                bucket = pair.left_id % plan.bucket_count
                cached = cache_index.get(_pair_key(pair.left, pair.right))
                if cached is not None and _cache_row_matches(cached, pair, version, bucket):
                    final_by_bucket.setdefault(bucket, []).append(cached)
                    continue
                fresh_targets.append(pair)
            if not fresh_targets:
                continue
            if executor is None or len(fresh_targets) <= 1:
                fresh_rows = [_build_bivariate_pair_statistics(pair) for pair in fresh_targets]
            else:
                fresh_rows = list(executor.map(_build_bivariate_pair_statistics, fresh_targets))
            for pair, row in zip(fresh_targets, fresh_rows, strict=True):
                bucket = pair.left_id % plan.bucket_count
                bucketed_row = dict(row)
                bucketed_row["version"] = version
                bucketed_row["bucket"] = bucket
                final_by_bucket.setdefault(bucket, []).append(bucketed_row)
                dirty_buckets.add(bucket)
    finally:
        if executor is not None:
            executor.shutdown()

    validate_rows(
        "bivariate_statistics",
        [row for bucket_rows in final_by_bucket.values() for row in bucket_rows],
    )
    _write_dirty_buckets(paths, version, existing_by_bucket, final_by_bucket, dirty_buckets)
    return sort_pair_rows([row for bucket_rows in final_by_bucket.values() for row in bucket_rows])


def _write_pair_plan_manifest(paths: LakePaths, *, version: str, plan: PairPlan) -> None:
    manifest = build_job_manifest(
        job_type="bivariate-statistics-plan",
        run_id=version,
        status="completed" if plan.accepted else "failed",
        row_counts={
            "listing_count": plan.listing_count,
            "theoretical_pair_count": plan.theoretical_pair_count,
            "chunk_size": plan.chunk_size,
            "worker_count": plan.worker_count,
            "bucket_count": plan.bucket_count,
            "expected_bucket_count": plan.expected_bucket_count,
            "estimated_memory_bytes": plan.estimated_memory_bytes,
            "max_pair_count": plan.max_pair_count,
        },
        resume_marker=plan.mode,
        error_summary=() if plan.accepted else ({"reason": plan.rejection_reason},),
    )
    write_job_manifest(paths, manifest)


def _read_existing_buckets(
    paths: LakePaths, version: str, bucket_count: int
) -> dict[int, list[JsonRow]]:
    """Read existing bucket files, discarding any bucket whose content is corrupt."""
    by_bucket: dict[int, list[JsonRow]] = {}
    for bucket in range(bucket_count):
        path = paths.gold_bivariate_statistics_bucket(version, bucket)
        if not path.exists():
            continue
        rows = read_rows(path)
        if any(int(row.get("bucket", -1)) != bucket for row in rows):
            # Corrupt or foreign bucket content must never masquerade as a cache hit.
            continue
        by_bucket[bucket] = rows
    return by_bucket


def _write_dirty_buckets(
    paths: LakePaths,
    version: str,
    existing_by_bucket: Mapping[int, list[JsonRow]],
    final_by_bucket: Mapping[int, list[JsonRow]],
    dirty_buckets: set[int],
) -> None:
    for bucket in sorted(set(existing_by_bucket) | set(final_by_bucket)):
        final_rows = sort_pair_rows(final_by_bucket.get(bucket, []))
        existing_keys = {str(row["pair_key"]) for row in existing_by_bucket.get(bucket, [])}
        final_keys = {str(row["pair_key"]) for row in final_rows}
        if bucket not in dirty_buckets and existing_keys == final_keys:
            continue
        path = paths.gold_bivariate_statistics_bucket(version, bucket)
        if not final_rows:
            path.unlink(missing_ok=True)
            continue
        write_rows(path, final_rows)


def _cache_row_matches(cached: JsonRow, pair: PairObservation, version: str, bucket: int) -> bool:
    date_start = pair.dates[0] if pair.dates else ""
    date_end = pair.dates[-1] if pair.dates else ""
    return (
        str(cached.get("version")) == version
        and int(cached.get("bucket", -1)) == bucket
        and str(cached.get("left_listing_key")) == _listing_key(pair.left)
        and str(cached.get("right_listing_key")) == _listing_key(pair.right)
        and str(cached.get("date_start")) == date_start
        and str(cached.get("date_end")) == date_end
        and int(cached.get("n_observations", -1)) == len(pair.dates)
    )


def _build_bivariate_pair_statistics(pair: PairObservation) -> JsonRow:
    covariance = sample_covariance(pair.left_values, pair.right_values)
    left_variance = sample_covariance(pair.left_values, pair.left_values)
    right_variance = sample_covariance(pair.right_values, pair.right_values)
    downside_correlation, downside_observations = _downside_correlation_with_count(
        pair.left_values, pair.right_values
    )
    return {
        "pair_key": _pair_key(pair.left, pair.right),
        "left_listing_key": _listing_key(pair.left),
        "right_listing_key": _listing_key(pair.right),
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
        "pearson_correlation": correlation_value(
            pair.left_values,
            pair.right_values,
            "pearson",
        ),
        "spearman_correlation": correlation_value(
            pair.left_values,
            pair.right_values,
            "spearman",
        ),
        "covariance": covariance,
        "left_variance": left_variance,
        "right_variance": right_variance,
        "left_beta_to_right": _ratio(covariance, right_variance),
        "right_beta_to_left": _ratio(covariance, left_variance),
        "downside_correlation": downside_correlation,
        "downside_observation_count": downside_observations,
        "lower_tail_dependence": _lower_tail_dependence(pair.left_values, pair.right_values),
        "tail_coexceedance_rate": _tail_coexceedance_rate(pair.left_values, pair.right_values),
        "tail_joint_loss_severity": _tail_joint_loss_severity(pair.left_values, pair.right_values),
        "tail_joint_event_count": _tail_events(pair.left_values, pair.right_values)[2],
        "rolling_tail_dependence_stability": _rolling_tail_dependence_stability(
            pair.left_values, pair.right_values
        ),
        "rolling_tail_coexceedance_stability": _rolling_tail_coexceedance_stability(
            pair.left_values, pair.right_values
        ),
        "rolling_correlation_stability": _rolling_correlation_stability(
            pair.left_values, pair.right_values
        ),
        "rolling_correlation_mean": _rolling_correlation_mean(pair.left_values, pair.right_values),
        "rolling_correlation_maximum": _rolling_correlation_maximum(
            pair.left_values, pair.right_values
        ),
        "rolling_correlation_trend": _rolling_correlation_trend(
            pair.left_values, pair.right_values
        ),
        "rolling_correlation_regime_switches": _rolling_correlation_regime_switches(
            pair.left_values, pair.right_values
        ),
        "rolling_spearman_stability": _rolling_correlation_stability(
            pair.left_values, pair.right_values, metric="spearman"
        ),
        "rolling_downside_stability": _rolling_downside_correlation_stability(
            pair.left_values, pair.right_values
        ),
        "drawdown_overlap_rate": _drawdown_overlap_rate(pair.left_values, pair.right_values),
        "drawdown_overlap_count": _drawdown_overlap_count(pair.left_values, pair.right_values),
        "drawdown_joint_severity": _drawdown_joint_severity(pair.left_values, pair.right_values),
        "rolling_drawdown_overlap_stability": _rolling_drawdown_overlap_stability(
            pair.left_values, pair.right_values
        ),
    }


def _downside_correlation(left: Sequence[float], right: Sequence[float]) -> float:
    """Correlation conditional on both daily log returns being negative."""
    return _downside_correlation_with_count(left, right)[0]


def _downside_correlation_with_count(
    left: Sequence[float], right: Sequence[float]
) -> tuple[float, int]:
    paired = [(a, b) for a, b in zip(left, right, strict=True) if a < 0 and b < 0]
    if len(paired) < 2:
        return 0.0, len(paired)
    downside_left, downside_right = zip(*paired, strict=True)
    return correlation_value(downside_left, downside_right, "pearson"), len(paired)


def _quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * probability)))
    return ordered[index]


def _tail_events(left: Sequence[float], right: Sequence[float]) -> tuple[int, int, int]:
    if not left or len(left) != len(right):
        return 0, 0, 0
    left_cutoff = _quantile(left, 0.05)
    right_cutoff = _quantile(right, 0.05)
    left_events = sum(value <= left_cutoff for value in left)
    right_events = sum(value <= right_cutoff for value in right)
    joint_events = sum(
        a <= left_cutoff and b <= right_cutoff for a, b in zip(left, right, strict=True)
    )
    return left_events, right_events, joint_events


def _lower_tail_dependence(left: Sequence[float], right: Sequence[float]) -> float:
    left_events, right_events, joint_events = _tail_events(left, right)
    return _ratio(joint_events, min(left_events, right_events))


def _tail_coexceedance_rate(left: Sequence[float], right: Sequence[float]) -> float:
    _, _, joint_events = _tail_events(left, right)
    return _ratio(joint_events, len(left))


def _tail_joint_loss_severity(left: Sequence[float], right: Sequence[float]) -> float:
    """Mean paired log loss when both series are in their respective lower 5% tails."""
    if not left or len(left) != len(right):
        return 0.0
    left_cutoff = _quantile(left, 0.05)
    right_cutoff = _quantile(right, 0.05)
    losses = [
        -(left_value + right_value) / 2
        for left_value, right_value in zip(left, right, strict=True)
        if left_value <= left_cutoff and right_value <= right_cutoff
    ]
    return sum(losses) / len(losses) if losses else 0.0


def _rolling_tail_dependence_stability(left: Sequence[float], right: Sequence[float]) -> float:
    """Standard deviation of sampled 60-observation lower-tail-dependence estimates."""
    if len(left) != len(right) or len(left) < 40:
        return 0.0
    window = min(60, len(left))
    step = max(1, window // 3)
    starts = list(range(0, len(left) - window + 1, step))
    if starts[-1] != len(left) - window:
        starts.append(len(left) - window)
    values = [
        _lower_tail_dependence(left[start : start + window], right[start : start + window])
        for start in starts
    ]
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def _rolling_tail_coexceedance_stability(left: Sequence[float], right: Sequence[float]) -> float:
    """Standard deviation of sampled 60-observation co-exceedance-rate estimates."""
    if len(left) != len(right) or len(left) < 40:
        return 0.0
    window = min(60, len(left))
    step = max(1, window // 3)
    starts = list(range(0, len(left) - window + 1, step))
    if starts[-1] != len(left) - window:
        starts.append(len(left) - window)
    values = [
        _tail_coexceedance_rate(left[start : start + window], right[start : start + window])
        for start in starts
    ]
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def _rolling_correlation_stability(
    left: Sequence[float], right: Sequence[float], *, metric: str = "pearson"
) -> float:
    """Standard deviation of sampled 60-observation rolling correlations."""
    correlations = _rolling_correlations(left, right, metric=metric)
    if len(correlations) < 2:
        return 0.0
    mean = sum(correlations) / len(correlations)
    return sqrt(sum((value - mean) ** 2 for value in correlations) / (len(correlations) - 1))


def _rolling_correlation_mean(left: Sequence[float], right: Sequence[float]) -> float:
    correlations = _rolling_correlations(left, right)
    return sum(correlations) / len(correlations) if correlations else 0.0


def _rolling_correlation_maximum(left: Sequence[float], right: Sequence[float]) -> float:
    return max(_rolling_correlations(left, right), default=0.0)


def _rolling_correlation_trend(left: Sequence[float], right: Sequence[float]) -> float:
    correlations = _rolling_correlations(left, right)
    return correlations[-1] - correlations[0] if len(correlations) >= 2 else 0.0


def _rolling_correlation_regime_switches(left: Sequence[float], right: Sequence[float]) -> int:
    correlations = _rolling_correlations(left, right)
    regimes = [value >= 0.70 for value in correlations]
    return sum(previous != current for previous, current in zip(regimes, regimes[1:], strict=False))


def _rolling_correlations(
    left: Sequence[float], right: Sequence[float], *, metric: str = "pearson"
) -> list[float]:
    if len(left) != len(right) or len(left) < 20:
        return []
    window = min(60, len(left))
    step = max(1, window // 3)
    starts = list(range(0, len(left) - window + 1, step))
    if starts[-1] != len(left) - window:
        starts.append(len(left) - window)
    return [
        correlation_value(left[start : start + window], right[start : start + window], metric)
        for start in starts
    ]


def _rolling_downside_correlation_stability(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 20:
        return 0.0
    window = min(60, len(left))
    step = max(1, window // 3)
    starts = list(range(0, len(left) - window + 1, step))
    if starts[-1] != len(left) - window:
        starts.append(len(left) - window)
    correlations = [
        _downside_correlation(left[start : start + window], right[start : start + window])
        for start in starts
    ]
    if len(correlations) < 2:
        return 0.0
    mean = sum(correlations) / len(correlations)
    return sqrt(sum((value - mean) ** 2 for value in correlations) / (len(correlations) - 1))


def _drawdown_overlap_rate(left: Sequence[float], right: Sequence[float]) -> float:
    """Share of days on which both assets are at least 5% below their prior peak."""
    left_drawdowns = _drawdowns(left)
    right_drawdowns = _drawdowns(right)
    if not left_drawdowns or len(left_drawdowns) != len(right_drawdowns):
        return 0.0
    overlap = sum(
        a <= -0.05 and b <= -0.05 for a, b in zip(left_drawdowns, right_drawdowns, strict=True)
    )
    return overlap / len(left_drawdowns)


def _drawdown_overlap_count(left: Sequence[float], right: Sequence[float]) -> int:
    """Count shared 5%-or-worse drawdown observations for one ISIN pair."""
    left_drawdowns = _drawdowns(left)
    right_drawdowns = _drawdowns(right)
    return sum(
        a <= -0.05 and b <= -0.05 for a, b in zip(left_drawdowns, right_drawdowns, strict=True)
    )


def _drawdown_joint_severity(left: Sequence[float], right: Sequence[float]) -> float:
    """Mean magnitude of overlapping drawdowns, expressed as a positive loss rate."""
    shared = [
        (a, b)
        for a, b in zip(_drawdowns(left), _drawdowns(right), strict=True)
        if a <= -0.05 and b <= -0.05
    ]
    return -sum((a + b) / 2 for a, b in shared) / len(shared) if shared else 0.0


def _rolling_drawdown_overlap_stability(left: Sequence[float], right: Sequence[float]) -> float:
    """Standard deviation of sampled rolling shared-drawdown overlap rates."""
    if len(left) != len(right) or len(left) < 20:
        return 0.0
    window = min(60, len(left))
    step = max(1, window // 3)
    starts = list(range(0, len(left) - window + 1, step))
    if starts[-1] != len(left) - window:
        starts.append(len(left) - window)
    overlaps = [
        _drawdown_overlap_rate(left[start : start + window], right[start : start + window])
        for start in starts
    ]
    if len(overlaps) < 2:
        return 0.0
    average = sum(overlaps) / len(overlaps)
    return sqrt(sum((value - average) ** 2 for value in overlaps) / (len(overlaps) - 1))


def _drawdowns(values: Sequence[float]) -> tuple[float, ...]:
    cumulative = 0.0
    peak = 0.0
    output: list[float] = []
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        output.append(exp(cumulative - peak) - 1.0)
    return tuple(output)


def _listing_key(listing: tuple[str, str, str]) -> str:
    isin, exchange, code = listing
    return f"{exchange}__{isin}__{code}"


def _pair_key(left: tuple[str, str, str], right: tuple[str, str, str]) -> str:
    return f"{_listing_key(left)}___{_listing_key(right)}"


def _ratio(numerator: float, denominator: float) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


__all__ = [
    "BIVARIATE_STATISTICS_VERSION",
    "build_bivariate_statistics",
    "resolve_worker_count",
    "write_bivariate_statistics",
]
