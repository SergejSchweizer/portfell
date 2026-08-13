"""Scalable Gold pair-statistics engine."""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from math import sqrt
from typing import Any

import polars as pl

from portfell.table_io import JsonRow

ListingKey = tuple[str, str, str]
ReturnsByListing = dict[ListingKey, dict[str, float]]

# Explicit resource policy for pairwise (bivariate) computation. A universe
# whose theoretical unordered-pair count exceeds DEFAULT_MAX_PAIR_COUNT must be
# rejected before pairs are materialized or worker tasks are submitted, unless
# a caller explicitly raises the limit. Default worker count uses every visible
# CPU core for statistics jobs; callers can still pass --concurrency to cap it.
DEFAULT_MAX_PAIR_COUNT = 500_000
DEFAULT_MAX_WORKERS = max(1, os.cpu_count() or 1)
DEFAULT_PAIR_CHUNK_SIZE = 5_000
DEFAULT_BUCKET_COUNT = 128
DEFAULT_BYTES_PER_PAIR = 200

PAIR_PLAN_MODES = frozenset({"dense", "sparse", "top_k"})


@dataclass(frozen=True)
class PairPlan:
    """Deterministic diagnostics computed before enumerating any pairs."""

    listing_count: int
    theoretical_pair_count: int
    mode: str
    chunk_size: int
    worker_count: int
    bucket_count: int
    expected_bucket_count: int
    estimated_memory_bytes: int
    max_pair_count: int
    accepted: bool
    rejection_reason: str | None


def resolve_worker_count(concurrency: int | None, *, max_workers: int = DEFAULT_MAX_WORKERS) -> int:
    """Resolve worker count from explicit concurrency or all visible cores."""
    if concurrency is not None:
        return max(1, concurrency)
    return max(1, min(max_workers, os.cpu_count() or 1))


def build_pair_plan(
    listing_count: int,
    *,
    mode: str = "dense",
    max_pair_count: int = DEFAULT_MAX_PAIR_COUNT,
    chunk_size: int = DEFAULT_PAIR_CHUNK_SIZE,
    bucket_count: int = DEFAULT_BUCKET_COUNT,
    concurrency: int | None = None,
    max_workers: int = DEFAULT_MAX_WORKERS,
    bytes_per_pair: int = DEFAULT_BYTES_PER_PAIR,
) -> PairPlan:
    """Compute a pair-materialization plan and reject oversized universes early."""
    if mode not in PAIR_PLAN_MODES:
        raise ValueError(f"unsupported pair plan mode: {mode}")
    if listing_count < 0:
        raise ValueError("listing_count must not be negative")
    if max_pair_count < 1:
        raise ValueError("max_pair_count must be positive")
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    if bucket_count < 1:
        raise ValueError("bucket_count must be positive")

    theoretical_pair_count = listing_count * (listing_count - 1) // 2
    accepted = theoretical_pair_count <= max_pair_count
    rejection_reason = (
        None
        if accepted
        else (
            f"theoretical_pair_count {theoretical_pair_count} exceeds max_pair_count "
            f"{max_pair_count} for mode '{mode}' with listing_count {listing_count}"
        )
    )
    return PairPlan(
        listing_count=listing_count,
        theoretical_pair_count=theoretical_pair_count,
        mode=mode,
        chunk_size=chunk_size,
        worker_count=resolve_worker_count(concurrency, max_workers=max_workers),
        bucket_count=bucket_count,
        expected_bucket_count=min(bucket_count, listing_count) if listing_count else 0,
        estimated_memory_bytes=theoretical_pair_count * bytes_per_pair,
        max_pair_count=max_pair_count,
        accepted=accepted,
        rejection_reason=rejection_reason,
    )


def chunked_pairs(
    pairs: Iterator[PairObservation], chunk_size: int
) -> Iterator[list[PairObservation]]:
    """Stream pair observations in deterministic, bounded-size chunks."""
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    chunk: list[PairObservation] = []
    for pair in pairs:
        chunk.append(pair)
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


@dataclass(frozen=True)
class PairObservation:
    left: ListingKey
    right: ListingKey
    left_id: int
    right_id: int
    dates: tuple[str, ...]
    left_values: tuple[float, ...]
    right_values: tuple[float, ...]


@dataclass(frozen=True)
class PairStatistics:
    observation: PairObservation
    pearson: float
    covariance: float


def index_returns(return_rows: Sequence[Mapping[str, Any]]) -> ReturnsByListing:
    indexed: ReturnsByListing = {}
    frame = pl.DataFrame([dict(row) for row in return_rows], infer_schema_length=None)
    if frame.is_empty():
        return indexed
    for listing_rows in frame.sort(  # pyright: ignore[reportUnknownMemberType]
        "isin", "exchange", "code", "date"
    ).partition_by("isin", "exchange", "code", maintain_order=True):
        rows = listing_rows.to_dicts()
        key = (str(rows[0]["isin"]), str(rows[0]["exchange"]), str(rows[0]["code"]))
        indexed[key] = {str(row["date"]): float(row["return"]) for row in rows}
    return indexed


def common_return_dates(returns_by_listing: ReturnsByListing) -> tuple[str, ...]:
    """Return the ordered calendar shared by every listing in one universe."""
    listings = tuple(sorted(returns_by_listing))
    if not listings:
        return ()
    dates = set(returns_by_listing[listings[0]])
    for listing in listings[1:]:
        dates.intersection_update(returns_by_listing[listing])
    return tuple(sorted(dates))


def iter_pair_observations(
    returns_by_listing: ReturnsByListing,
    *,
    include_self: bool,
    skip_same_isin: bool = False,
) -> Iterator[PairObservation]:
    listings = tuple(sorted(returns_by_listing))
    dates = common_return_dates(returns_by_listing)
    if not dates:
        return
    for left_id, left in enumerate(listings):
        right_start = left_id if include_self else left_id + 1
        for right_id, right in enumerate(listings[right_start:], start=right_start):
            if skip_same_isin and left[0] == right[0]:
                continue
            left_rows = returns_by_listing[left]
            right_rows = returns_by_listing[right]
            yield PairObservation(
                left=left,
                right=right,
                left_id=left_id,
                right_id=right_id,
                dates=dates,
                left_values=tuple(left_rows[item] for item in dates),
                right_values=tuple(right_rows[item] for item in dates),
            )


def iter_pair_statistics(
    returns_by_listing: ReturnsByListing,
    *,
    include_self: bool,
    skip_same_isin: bool = False,
) -> Iterator[PairStatistics]:
    for observation in iter_pair_observations(
        returns_by_listing,
        include_self=include_self,
        skip_same_isin=skip_same_isin,
    ):
        yield PairStatistics(
            observation=observation,
            pearson=incremental_pearson(observation.left_values, observation.right_values),
            covariance=sample_covariance(observation.left_values, observation.right_values),
        )


def sample_covariance(left_values: Sequence[float], right_values: Sequence[float]) -> float:
    if len(left_values) < 2 or len(left_values) != len(right_values):
        return 0.0
    state = OnlineCorrelation()
    for left, right in zip(left_values, right_values, strict=True):
        state.update(left, right)
    return state.sample_covariance()


def incremental_pearson(left_values: Sequence[float], right_values: Sequence[float]) -> float:
    if len(left_values) < 2 or len(left_values) != len(right_values):
        return 0.0
    state = OnlineCorrelation()
    for left, right in zip(left_values, right_values, strict=True):
        state.update(left, right)
    return state.value()


def spearman_correlation(left_values: Sequence[float], right_values: Sequence[float]) -> float:
    if len(left_values) < 2 or len(left_values) != len(right_values):
        return 0.0
    return incremental_pearson(_average_ranks(left_values), _average_ranks(right_values))


def _average_ranks(values: Sequence[float]) -> tuple[float, ...]:
    ordered = sorted(enumerate(values), key=lambda item: (item[1], item[0]))
    ranks = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][1] == ordered[start][1]:
            end += 1
        average_rank = (start + 1 + end) / 2.0
        for index, _value in ordered[start:end]:
            ranks[index] = average_rank
        start = end
    return tuple(ranks)


def correlation_value(
    left_values: Sequence[float], right_values: Sequence[float], metric: str
) -> float:
    if metric == "spearman":
        return spearman_correlation(left_values, right_values)
    return incremental_pearson(left_values, right_values)


@dataclass
class OnlineCorrelation:
    count: int = 0
    left_mean: float = 0.0
    right_mean: float = 0.0
    left_m2: float = 0.0
    right_m2: float = 0.0
    comoment: float = 0.0

    def update(self, left: float, right: float) -> None:
        self.count += 1
        left_delta = left - self.left_mean
        right_delta = right - self.right_mean
        self.left_mean += left_delta / self.count
        self.right_mean += right_delta / self.count
        self.comoment += left_delta * (right - self.right_mean)
        self.left_m2 += left_delta * (left - self.left_mean)
        self.right_m2 += right_delta * (right - self.right_mean)

    def value(self) -> float:
        if self.count < 2:
            return 0.0
        denominator = sqrt(self.left_m2 * self.right_m2)
        return 0.0 if denominator == 0 else self.comoment / denominator

    def sample_covariance(self) -> float:
        if self.count < 2:
            return 0.0
        return self.comoment / (self.count - 1)


def symmetric_pair_rows(
    left: ListingKey, right: ListingKey, value_field: str, value: float
) -> list[JsonRow]:
    rows = [pair_row(left, right, value_field, value)]
    if left != right:
        rows.append(pair_row(right, left, value_field, value))
    return rows


def pair_row(left: ListingKey, right: ListingKey, value_field: str, value: float) -> JsonRow:
    return {
        "left_isin": left[0],
        "left_exchange": left[1],
        "left_code": left[2],
        "right_isin": right[0],
        "right_exchange": right[1],
        "right_code": right[2],
        value_field: value,
    }


def sort_pair_rows(rows: Sequence[JsonRow]) -> list[JsonRow]:
    return sorted(
        rows,
        key=lambda row: (
            str(row["left_isin"]),
            str(row["left_exchange"]),
            str(row["left_code"]),
            str(row["right_isin"]),
            str(row["right_exchange"]),
            str(row["right_code"]),
        ),
    )


def limit_top_correlation_edges(
    rows: Sequence[JsonRow], top_k_per_left: int | None
) -> list[JsonRow]:
    if top_k_per_left is None:
        return list(rows)
    by_left: dict[int, list[JsonRow]] = {}
    for row in rows:
        by_left.setdefault(int(row["left_id"]), []).append(row)
    limited: list[JsonRow] = []
    for left_id in sorted(by_left):
        limited.extend(
            sorted(
                by_left[left_id],
                key=lambda row: (-abs(float(row["value"])), int(row["right_id"])),
            )[:top_k_per_left]
        )
    return limited


def bucket_correlation_edges(
    rows: Sequence[JsonRow], bucket_count: int
) -> dict[int, list[JsonRow]]:
    if bucket_count < 1:
        raise ValueError("bucket_count must be positive")
    by_bucket: dict[int, list[JsonRow]] = {}
    for row in rows:
        bucket = int(row["left_id"]) % bucket_count
        row_with_bucket = dict(row)
        row_with_bucket["bucket"] = bucket
        by_bucket.setdefault(bucket, []).append(row_with_bucket)
    return dict(sorted(by_bucket.items()))
